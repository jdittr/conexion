# conexio 200

Reads the Prozeda conexio 200 web interface and publishes all values to Home
Assistant via MQTT discovery. Needs an MQTT broker; with the Mosquitto broker
app the credentials are picked up automatically.

## Options

| Option | Description |
|--------|-------------|
| `url` | Base URL of the conexio, e.g. `http://192.168.1.50` |
| `username` / `password` | Web interface login (digest auth, default user `admin`) |
| `scan_interval` | Seconds between reads (default 10; the vendor page uses 1) |
| `device_id` | Prefix for unique IDs, entity IDs and topics (default `conexio200`) |
| `device_name` | Device name in Home Assistant |
| `names` | Optional display names, `KEY=Name`, e.g. `S1=Kollektor` |
| `exclude` | Keys not to create, e.g. `RT1` for unused room sensors |
| `mqtt_host`, `mqtt_port`, `mqtt_username`, `mqtt_password` | Only for a broker other than the Mosquitto app |
| `topic_prefix` | MQTT topic prefix (default `conexio`) |

Removing a key via `exclude`, or a flex module that disappears, also removes
its entity.

## Values

| Key | Meaning | Unit | Decoding (as in the vendor page) |
|-----|---------|------|----------------------------------|
| `S1`…`S10` | Temperature sensors | °C | value / 10 |
| `Str` | Str (irradiance / power) | W | value |
| `R0`…`R7` | Relay / pump outputs | % | value / 2 |
| `HE1`…`HE3` | High-efficiency pump (PWM) outputs | % | value / 100 |
| `Q1`, `Q2` | Heat yield | kWh | see below |
| `F<n>S1`…`F<n>S4` | Flex module n sensors | °C | value / 10 |
| `F<n>R1`…`F<n>R3`, `F<n>HE` | Flex module n outputs | % | value / 2 |
| `F<n>Q` | Flex module n heat yield (HC 680) | kWh | 32-bit counter |
| `RT1`…`RT4` | Room temperature sensors | °C | value / 10 |
| `S<n>S1`…`S<n>S4` | FWRC station n sensors | °C | value / 10 |
| `S<n>DL` | FWRC station n flow (`l/I` on the page) | L/min | value / 10 |
| `S<n>P` | FWRC station n pump | % | value |
| `S<n>V` | FWRC station n valve | % | value × 100 |
| `modules` | Number of flex modules / stations reported | | |

Heat yield: on the Grandis 650 `Q1` is the sum of two 16-bit words, on the
600 SR the sum of four, exactly as the vendor page computes it. On the HC 680
the counters are 32 bit; unlike the vendor page, the low word is read
unsigned so the counter does not jump back by 65536.

Sensors that are not connected show the value the controller reports, e.g.
`RT1` = 250.0 °C. Add such keys to `exclude`.

## Notes

The conexio sometimes refuses a single connection. One failed read is only
logged; after three failures in a row the entities become unavailable.
