"""Entry point: ``python -m conexio``.

Inside Home Assistant the options come from ``/data/options.json`` and the
MQTT broker from the Supervisor services API. Outside, everything can be
given on the command line (see ``--help``).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
import urllib.request

from .client import ConexioClient
from .decoder import DecodeError

_LOG = logging.getLogger("conexio")
OPTIONS_FILE = "/data/options.json"


def _supervisor_mqtt() -> dict:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return {}
    request = urllib.request.Request(
        "http://supervisor/services/mqtt",
        headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response).get("data", {})
    except Exception as err:  # noqa: BLE001 - only used as a fallback
        _LOG.warning("No MQTT service from the Supervisor: %s", err)
        return {}


def _parse_names(entries: list[str]) -> dict[str, str]:
    names = {}
    for entry in entries or []:
        key, sep, name = entry.partition("=")
        if sep and key.strip() and name.strip():
            names[key.strip()] = name.strip()
        else:
            _LOG.warning("Ignoring name entry %r (expected KEY=Name)", entry)
    return names


def _options(argv: list[str]) -> dict:
    parser = argparse.ArgumentParser(
        prog="conexio",
        description="Read a Prozeda conexio 200 and publish to MQTT.")
    parser.add_argument("--url", help="base URL of the conexio, e.g. http://192.168.1.50")
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=os.environ.get("CONEXIO_PASSWORD"),
                        help="or set CONEXIO_PASSWORD")
    parser.add_argument("--scan-interval", type=int, default=None)
    parser.add_argument("--mqtt-host")
    parser.add_argument("--mqtt-port", type=int)
    parser.add_argument("--mqtt-username")
    parser.add_argument("--mqtt-password", default=os.environ.get("MQTT_PASSWORD"),
                        help="or set MQTT_PASSWORD")
    parser.add_argument("--device-id")
    parser.add_argument("--once", action="store_true",
                        help="read once, print the values as JSON and exit")
    args = parser.parse_args(argv)

    options: dict = {}
    if os.path.exists(OPTIONS_FILE):
        with open(OPTIONS_FILE, encoding="utf-8") as handle:
            options = json.load(handle)
    for key, value in vars(args).items():
        if value is not None and value is not False:
            options[key] = value
    return options


def main(argv: list[str] | None = None) -> int:
    options = _options(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(
        level=str(options.get("log_level", "info")).upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not options.get("url"):
        _LOG.error("No conexio URL configured")
        return 2
    client = ConexioClient(options["url"], options.get("username", "admin"),
                           options.get("password", ""))

    if options.get("once"):
        reading = client.read()
        print(json.dumps({"controller_id": reading.controller_id,
                          "model": reading.model,
                          "values": reading.as_dict()}, indent=2,
                         ensure_ascii=False))
        return 0

    from .mqtt import Publisher  # paho is only needed for MQTT mode

    broker = _supervisor_mqtt()
    host = options.get("mqtt_host") or broker.get("host")
    if not host:
        _LOG.error("No MQTT broker: install the Mosquitto broker app or set mqtt_host")
        return 2
    publisher = Publisher(
        host=host,
        port=int(options.get("mqtt_port") or broker.get("port") or 1883),
        username=options.get("mqtt_username") or broker.get("username"),
        password=options.get("mqtt_password") or broker.get("password"),
        device_id=options.get("device_id", "conexio200"),
        device_name=options.get("device_name", "conexio 200"),
        topic_prefix=options.get("topic_prefix", "conexio"),
        discovery_prefix=options.get("discovery_prefix", "homeassistant"),
        names=_parse_names(options.get("names", [])),
        exclude=set(options.get("exclude", [])),
    )

    deadline = time.monotonic() + 15
    while not publisher.client.is_connected() and time.monotonic() < deadline:
        time.sleep(0.2)

    running = True

    def _stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    interval = max(1, int(options.get("scan_interval", 10)))
    failures = 0
    _LOG.info("Polling %s every %d s", client.base, interval)
    while running:
        started = time.monotonic()
        try:
            reading = client.read()
            publisher.publish(reading)
            if failures:
                _LOG.info("conexio reachable again")
            failures = 0
            _LOG.debug("%s", reading.as_dict())
        except (OSError, DecodeError) as err:
            failures += 1
            # One missed poll is normal for this box; mark offline after 3.
            log = _LOG.warning if failures in (1, 3) else _LOG.debug
            log("Reading the conexio failed (%d in a row): %s", failures, err)
            if failures >= 3:
                publisher.offline()
        while running and time.monotonic() - started < interval:
            time.sleep(0.5)

    publisher.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
