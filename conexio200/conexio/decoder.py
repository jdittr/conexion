"""Decoder for the conexio 200 ``medius_val.xml`` hex string.

This mirrors the ``Parser()`` function of the vendor page ``schema.html``
step by step: the vendor code walks through the hex string with a cursor,
reads 16-bit words (4 hex characters) and skips unused words in between.
Each controller type (``Reglerkennung``) has its own walk. Keeping the same
structure here makes it easy to compare the two side by side.

Deliberate deviations from the vendor code:

* 32-bit energy counters (HC 680) are combined as unsigned 32-bit values.
  The vendor decodes the low word as *signed*, which makes the counter jump
  back by 65536 kWh whenever the low word is >= 0x8000.
* Values of flex modules / stations beyond the reported module count are
  left out instead of being hidden in the page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Kinds of values, as rendered by the vendor fTableEntry* functions.
#   kind: (scale applied to the raw signed word, unit)
KINDS: dict[str, tuple[float, str | None]] = {
    "T": (0.1, "°C"),      # fTableEntryT   temperature sensor          value/10
    "S": (1, "W"),         # fTableEntryS   "Str" (irradiance / power)   value
    "R": (0.5, "%"),       # fTableEntryR   relay / pump output          value/2
    "H": (0.01, "%"),      # fTableEntryH   high-efficiency pump (PWM)   value/100
    "DL": (0.1, "L/min"),  # fTableEntryDL  flow rate ("l/I" on the page) value/10
    "StP": (1, "%"),       # fTableEntryStP station pump                 value
    "StV": (100, "%"),     # fTableEntryStV station valve                value*100
    "Q": (1, "kWh"),       # fTableEntryQ   heat yield
    "N": (1, None),        # number of flex modules / stations
}

# Reglerkennung -> model name. Anything unknown uses the Grandis 650 walk,
# exactly like the vendor page (its final ``else`` branch).
MODELS = {
    "053803ED": "600 SR",
    "053803F1": "HC 680",
    "05371771": "FWR 400",
    "053803F2": "FWR 1336",
    "053703EA": "FWRC 400",
}
DEFAULT_MODEL = "Grandis 650 HK/WN"


class DecodeError(ValueError):
    """The response does not contain a usable data string."""


@dataclass
class Value:
    key: str
    kind: str
    value: float | int

    @property
    def unit(self) -> str | None:
        return KINDS[self.kind][1]


@dataclass
class Reading:
    controller_id: str
    model: str
    size: int
    values: dict[str, Value] = field(default_factory=dict)

    def as_dict(self) -> dict[str, float | int]:
        return {k: v.value for k, v in self.values.items()}


class _Cursor:
    """Walks the hex string like the vendor's global ``string`` variable."""

    def __init__(self, data: str, start: int) -> None:
        self.data = data
        self.pos = start
        self.values: dict[str, Value] = {}

    def skip(self, chars: int) -> None:
        self.pos += chars

    def word(self) -> int:
        """Unsigned 16-bit word; missing data reads as 0 (vendor: NaN -> 0)."""
        chunk = self.data[self.pos:self.pos + 4]
        self.pos += 4
        try:
            return int(chunk, 16)
        except ValueError:
            return 0

    def signed(self) -> int:
        """fDecode_signed()"""
        value = self.word()
        return value - 65536 if value > 32767 else value

    def put(self, key: str, kind: str, raw: int) -> None:
        value: float | int = raw * KINDS[kind][0]
        if kind in ("T", "DL"):
            value = round(value, 1)
        elif kind == "H":
            value = round(value, 2)
        if isinstance(value, float) and value.is_integer() and kind not in ("T", "DL"):
            value = int(value)
        self.values[key] = Value(key, kind, value)

    def entry(self, key: str, kind: str) -> None:
        """fTableEntry<kind>(key): read one signed word and store it."""
        self.put(key, kind, self.signed())

    def entries(self, kind: str, *keys: str) -> None:
        for key in keys:
            self.entry(key, kind)

    def counter32(self, key: str) -> None:
        """High word * 65536 + low word, as unsigned 32 bit."""
        high = self.word()
        low = self.word()
        self.put(key, "Q", (high << 16) | low)


def _sensors(c: _Cursor, count: int) -> None:
    c.entries("T", *(f"S{i}" for i in range(1, count + 1)))


def _relays(c: _Cursor) -> None:
    c.entries("R", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R0")


def _flex_block(c: _Cursor, n: int) -> None:
    """One flex module: 4 sensors, 3 relays, 1 HE output."""
    p = f"F{n}"
    c.entries("T", f"{p}S1", f"{p}S2", f"{p}S3", f"{p}S4")
    # The vendor renders F*HE with fTableEntryR (value/2), not fTableEntryH.
    c.entries("R", f"{p}R1", f"{p}R2", f"{p}R3", f"{p}HE")


def _station_block(c: _Cursor, n: int) -> None:
    """One fresh-water station of the FWRC 400."""
    p = f"S{n}"
    c.entries("T", f"{p}S1", f"{p}S2", f"{p}S3", f"{p}S4")
    c.entry(f"{p}DL", "DL")
    c.entry(f"{p}P", "StP")
    c.entry(f"{p}V", "StV")


def _walk_600sr(c: _Cursor) -> int:
    _sensors(c, 10)
    c.entry("Str", "S")
    c.skip(24)
    _relays(c)
    c.skip(4)
    c.entry("HE1", "H")
    c.skip(4)
    c.entry("HE2", "H")
    c.skip(12)
    heat = c.signed() + c.signed()
    c.skip(8)
    c.entry("Q2", "Q")
    c.skip(32)
    heat += c.signed() + c.signed()
    c.put("Q1", "Q", heat)
    c.skip(44)
    _flex_block(c, 1)
    c.skip(12)
    _flex_block(c, 2)
    c.skip(16)
    return c.signed()


def _walk_hc680(c: _Cursor) -> int:
    _sensors(c, 10)
    c.skip(28)
    _relays(c)
    c.entries("H", "HE1", "HE2", "HE3")
    c.skip(36)
    for n in range(1, 5):
        _flex_block(c, n)
        c.skip(12)
    modules = c.signed()
    c.counter32("Q1")
    for n in range(1, 5):
        c.counter32(f"F{n}Q")
    c.skip(4)
    c.entries("T", "RT1", "RT2", "RT3", "RT4")
    return modules


def _walk_fwr400(c: _Cursor) -> None:
    _sensors(c, 6)
    c.skip(8)
    c.entries("R", "R3", "R0")
    c.entries("H", "HE1", "HE2")


def _walk_fwr1336(c: _Cursor) -> None:
    _sensors(c, 6)
    c.skip(12)
    _relays(c)
    c.entries("H", "HE1", "HE2")


def _walk_fwrc400(c: _Cursor) -> int:
    _sensors(c, 6)
    c.skip(8)
    c.entries("R", "R3", "R0")
    c.entries("H", "HE1", "HE2")
    c.skip(16)
    for n in range(1, 5):
        _station_block(c, n)
        c.skip(20)
    return c.signed()


def _walk_grandis650(c: _Cursor) -> int:
    _sensors(c, 10)
    c.entry("Str", "S")
    c.skip(24)
    _relays(c)
    c.entries("H", "HE1", "HE2", "HE3")
    c.skip(16)
    c.put("Q1", "Q", c.signed() + c.signed())
    c.skip(8)
    c.entry("Q2", "Q")
    c.skip(44)
    for n in range(1, 5):
        _flex_block(c, n)
        c.skip(12)
    modules = c.signed()
    c.skip(20)
    c.entries("T", "RT1", "RT2", "RT3", "RT4")
    return modules


WALKS = {
    "053803ED": _walk_600sr,
    "053803F1": _walk_hc680,
    "05371771": _walk_fwr400,
    "053803F2": _walk_fwr1336,
    "053703EA": _walk_fwrc400,
}

# Keys that belong to flex module F<n> or fresh-water station S<n>.
_MODULE_KEY = re.compile(r"^(?:F(\d)(?:S\d|R\d|HE|Q)|S(\d)(?:S\d|DL|P|V))$")


def module_of(key: str) -> int | None:
    """Return the flex module / station number a key belongs to, if any."""
    m = _MODULE_KEY.match(key)
    if not m:
        return None
    return int(m.group(1) or m.group(2))


def extract_data(response: str) -> str:
    """Return the hex string inside ``<data>...</data>``."""
    match = re.search(r"<data>\s*([0-9A-Fa-f]+)\s*</data>", response)
    if not match:
        raise DecodeError("no <data> element with hex content in response")
    return match.group(1).upper()


def decode(data: str) -> Reading:
    """Decode the hex string (content of ``<data>``) into named values."""
    data = data.strip().upper()
    if len(data) < 12 or not re.fullmatch(r"[0-9A-F]+", data):
        raise DecodeError(f"not a conexio data string ({len(data)} chars)")
    size = int(data[0:2], 16)
    controller_id = data[2 * size - 24:2 * size - 16]
    model = MODELS.get(controller_id, DEFAULT_MODEL)
    walk = WALKS.get(controller_id, _walk_grandis650)

    cursor = _Cursor(data, 10)  # 2 chars size + 8 chars header
    modules = walk(cursor)
    values = cursor.values

    if modules is not None:
        values["modules"] = Value("modules", "N", modules)
        for key in list(values):
            n = module_of(key)
            if n is not None and n > modules:
                del values[key]

    return Reading(controller_id=controller_id, model=model, size=size,
                   values=values)
