"""Tests for the decoder.

The offset tables below were derived by hand from the vendor ``Parser()``
in ``schema.html`` (character offsets into the content of ``<data>``).
Run with:  python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "conexio200"))

from conexio.decoder import DecodeError, decode, extract_data  # noqa: E402

SAMPLE = "<xml><data>" + (
    "E90DE1C51F009A012B0204010C00F501C001510185015C003500000007FF5B0000FF5B"
    "0003000000000000000000000000000000C8000000000000000001610003000300000D"
    "1F04800638028900005209000200000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000003809C409C409C409C400"
    "0000000000000000000000053803EE4E3A00000000080CAA"
) + "</data></xml>"


def synthetic(controller_id: str) -> str:
    """Data string where the word at character offset p holds the value p."""
    size = 0xF0
    chars = ["F0"]
    for p in range(2, 2 * size, 4):
        chars.append(f"{p:04X}")
    data = "".join(chars)
    start = 2 * size - 24
    return data[:start] + controller_id + data[start + 8:]


SENSORS10 = {f"S{i}": 10 + 4 * (i - 1) for i in range(1, 11)}
SENSORS6 = {f"S{i}": 10 + 4 * (i - 1) for i in range(1, 7)}
RELAYS_78 = {k: 78 + 4 * i for i, k in
             enumerate(["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R0"])}


def flex(n: int, start: int) -> dict:
    keys = ["S1", "S2", "S3", "S4", "R1", "R2", "R3", "HE"]
    return {f"F{n}{k}": start + 4 * i for i, k in enumerate(keys)}


def station(n: int, start: int) -> dict:
    keys = ["S1", "S2", "S3", "S4", "DL", "P", "V"]
    return {f"S{n}{k}": start + 4 * i for i, k in enumerate(keys)}


class OffsetTests(unittest.TestCase):
    """Each value must come from the offset the vendor parser reads."""

    def check(self, controller_id, model, offsets, extra=None):
        reading = decode(synthetic(controller_id))
        self.assertEqual(reading.model, model)
        values = reading.values
        for key, offset in offsets.items():
            v = values[key]
            scale = {"T": 0.1, "R": 0.5, "H": 0.01, "S": 1, "DL": 0.1,
                     "StP": 1, "StV": 100, "Q": 1}[v.kind]
            self.assertAlmostEqual(v.value, round(offset * scale, 2), 5,
                                   msg=f"{key} expected offset {offset}")
        for key, expected in (extra or {}).items():
            self.assertEqual(values[key].value, expected, key)
        expected_keys = set(offsets) | set(extra or {})
        self.assertEqual(set(values) - {"modules"}, expected_keys - {"modules"})

    def test_grandis650(self):
        offsets = {**SENSORS10, "Str": 50, **RELAYS_78,
                   "HE1": 110, "HE2": 114, "HE3": 118, "Q2": 154,
                   **flex(1, 202), **flex(2, 246), **flex(3, 290),
                   **flex(4, 334),
                   "RT1": 402, "RT2": 406, "RT3": 410, "RT4": 414}
        self.check("053803EE", "Grandis 650 HK/WN", offsets,
                   {"Q1": 138 + 142, "modules": 378})

    def test_600sr(self):
        offsets = {**SENSORS10, "Str": 50, **RELAYS_78,
                   "HE1": 114, "HE2": 122, "Q2": 154,
                   **flex(1, 242), **flex(2, 286)}
        self.check("053803ED", "600 SR", offsets,
                   {"Q1": 138 + 142 + 190 + 194, "modules": 334})

    def test_hc680(self):
        offsets = {**SENSORS10, **RELAYS_78,
                   "HE1": 110, "HE2": 114, "HE3": 118,
                   **flex(1, 158), **flex(2, 202), **flex(3, 246),
                   **flex(4, 290),
                   "RT1": 382, "RT2": 386, "RT3": 390, "RT4": 394}
        q = {"Q1": 338, "F1Q": 346, "F2Q": 354, "F3Q": 362, "F4Q": 370}
        extra = {k: (o << 16) | (o + 4) for k, o in q.items()}
        extra["modules"] = 334
        self.check("053803F1", "HC 680", offsets, extra)

    def test_fwr400(self):
        offsets = {**SENSORS6, "R3": 42, "R0": 46, "HE1": 50, "HE2": 54}
        self.check("05371771", "FWR 400", offsets)

    def test_fwr1336(self):
        relays = {k: 46 + 4 * i for i, k in
                  enumerate(["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R0"])}
        offsets = {**SENSORS6, **relays, "HE1": 78, "HE2": 82}
        self.check("053803F2", "FWR 1336", offsets)

    def test_fwrc400(self):
        offsets = {**SENSORS6, "R3": 42, "R0": 46, "HE1": 50, "HE2": 54,
                   **station(1, 74), **station(2, 122), **station(3, 170),
                   **station(4, 218)}
        self.check("053703EA", "FWRC 400", offsets, {"modules": 266})


class SampleTests(unittest.TestCase):
    def test_sample(self):
        reading = decode(extract_data(SAMPLE))
        self.assertEqual(reading.controller_id, "053803EE")
        self.assertEqual(reading.model, "Grandis 650 HK/WN")
        v = reading.as_dict()
        self.assertEqual(v["S1"], 15.4)
        self.assertEqual(v["S2"], 29.9)
        self.assertEqual(v["S10"], 5.3)
        self.assertEqual(v["R7"], 100)
        self.assertEqual(v["Q1"], 0x0D1F + 0x0480)
        self.assertEqual(v["modules"], 0)
        self.assertNotIn("F1S1", v)  # no flex module connected

    def test_negative_temperature(self):
        data = synthetic("053803EE")
        data = data[:10] + "FF5B" + data[14:]
        self.assertEqual(decode(data).as_dict()["S1"], -16.5)

    def test_garbage(self):
        with self.assertRaises(DecodeError):
            extract_data("<html>login</html>")
        with self.assertRaises(DecodeError):
            decode("XYZ")


if __name__ == "__main__":
    unittest.main()
