# conexio 200 for Home Assistant

Tools to integrate the Prozeda **conexio 200** box into a smart home and make use
of the sensors and data it reads from various heating controllers.

The conexio 200 only has a web page, with no API. This repository reads the
same data the page uses (`medius_val.xml`), decodes it exactly like the
vendor JavaScript (`schema.html`) does, and publishes every value to Home
Assistant through MQTT discovery.

## Home Assistant app (add-on)

1. Make sure an MQTT broker runs (e.g. the **Mosquitto broker** app) and the
   MQTT integration is set up.
2. Settings → Apps → App store → ⋮ → Repositories → add
   `https://github.com/jdittr/conexion`.
3. Install **conexio 200**, set `url`, `username` and `password` of the
   conexio web interface, and start it.

A device "conexio 200" appears with one sensor per value, e.g.
`sensor.conexio200_s1`. See [conexio200/DOCS.md](conexio200/DOCS.md) for all
options and the list of values.

## Supported controllers

The controller type is detected from the data (`Reglerkennung`):

| ID | Controller | Values |
|----|-----------|--------|
| `053803ED` | 600 SR | S1–S10, Str, R0–R7, HE1–HE2, Q1–Q2, flex modules 1–2 |
| `053803F1` | HC 680 | S1–S10, R0–R7, HE1–HE3, Q1, flex modules 1–4 (incl. F*Q), RT1–RT4 |
| `05371771` | FWR 400 | S1–S6, R3, R0, HE1–HE2 |
| `053803F2` | FWR 1336 | S1–S6, R0–R7, HE1–HE2 |
| `053703EA` | FWRC 400 | S1–S6, R3, R0, HE1–HE2, stations 1–4 (S1–S4, DL, P, V) |
| anything else | Grandis 650 HK / 650 WN | S1–S10, Str, R0–R7, HE1–HE3, Q1–Q2, flex modules 1–4, RT1–RT4 |

Flex module / station values are only created for the modules the controller
reports.

## Standalone (without Home Assistant)

```sh
pip install "paho-mqtt>=2.1,<3"
CONEXIO_PASSWORD=... python conexio.py --url http://192.168.1.50 --once
CONEXIO_PASSWORD=... MQTT_PASSWORD=... python conexio.py --url http://192.168.1.50 \
    --mqtt-host broker --mqtt-username user
```

## Development

```sh
python -m unittest discover -s tests
```

The tests check every value against the offset the vendor parser reads.
