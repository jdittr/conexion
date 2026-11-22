"""Publish readings to MQTT with Home Assistant discovery."""

from __future__ import annotations

import json
import logging
import re

import paho.mqtt.client as mqtt

from . import __version__
from .decoder import Reading, Value

_LOG = logging.getLogger(__name__)

# Home Assistant metadata per value kind.
_HA_META: dict[str, dict] = {
    "T": {"device_class": "temperature", "state_class": "measurement",
          "suggested_display_precision": 1},
    "S": {"state_class": "measurement", "icon": "mdi:white-balance-sunny"},
    "R": {"state_class": "measurement", "icon": "mdi:pump"},
    "H": {"state_class": "measurement", "icon": "mdi:pump"},
    "DL": {"device_class": "volume_flow_rate", "state_class": "measurement"},
    "StP": {"state_class": "measurement", "icon": "mdi:pump"},
    "StV": {"state_class": "measurement", "icon": "mdi:valve"},
    "Q": {"device_class": "energy", "state_class": "total_increasing"},
    "N": {"entity_category": "diagnostic", "icon": "mdi:puzzle"},
}

_NAMES = {"modules": "Flex modules", "Str": "Str"}


class Publisher:
    def __init__(self, host: str, port: int, username: str | None,
                 password: str | None, device_id: str, device_name: str,
                 topic_prefix: str = "conexio",
                 discovery_prefix: str = "homeassistant",
                 names: dict[str, str] | None = None,
                 exclude: set[str] | None = None) -> None:
        self.device_id = re.sub(r"[^a-z0-9_]", "_", device_id.lower())
        self.device_name = device_name
        self.base = f"{topic_prefix}/{self.device_id}"
        self.state_topic = f"{self.base}/state"
        self.status_topic = f"{self.base}/status"
        self.discovery_prefix = discovery_prefix
        self.names = names or {}
        self.exclude = exclude or set()
        self._announced: set[str] = set()
        self._fresh = True
        self._model: str | None = None

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=f"conexio-{self.device_id}")
        if username:
            self.client.username_pw_set(username, password)
        self.client.will_set(self.status_topic, "offline", qos=1, retain=True)
        self.client.on_connect = self._on_connect
        self.client.reconnect_delay_set(1, 60)
        self.client.connect_async(host, port)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            _LOG.error("MQTT connect failed: %s", reason_code)
            return
        _LOG.info("Connected to MQTT broker")
        # Re-announce after (re)connect, e.g. when the broker lost its
        # retained messages; Home Assistant also restarts send a birth
        # message, but retained configs cover that.
        self._fresh = True

    def _discovery_topic(self, key: str) -> str:
        return (f"{self.discovery_prefix}/sensor/{self.device_id}/"
                f"{key.lower()}/config")

    def _config(self, value: Value, reading: Reading) -> dict:
        key = value.key
        config = {
            "name": self.names.get(key, _NAMES.get(key, key)),
            "unique_id": f"{self.device_id}_{key.lower()}",
            "default_entity_id": f"sensor.{self.device_id}_{key.lower()}",
            "state_topic": self.state_topic,
            "value_template": "{{ value_json['%s'] }}" % key,
            "availability_topic": self.status_topic,
            "device": {
                "identifiers": [self.device_id],
                "name": self.device_name,
                "manufacturer": "Prozeda",
                "model": f"conexio 200 / {reading.model}",
                "model_id": reading.controller_id,
                "sw_version": __version__,
            },
            "origin": {"name": "conexio200",
                       "sw_version": __version__,
                       "support_url": "https://github.com/jdittr/conexion"},
            **_HA_META[value.kind],
        }
        if value.unit:
            config["unit_of_measurement"] = value.unit
        return config

    def _announce(self, reading: Reading) -> None:
        keys = {k for k in reading.values if k not in self.exclude}
        if self._fresh or self._model != reading.model:
            # Start over: re-send every config and clear configs of
            # excluded keys that an earlier run may have announced.
            self._fresh = False
            self._model = reading.model
            self._announced = set(reading.values) & self.exclude
        for key in sorted(keys - self._announced):
            payload = json.dumps(self._config(reading.values[key], reading))
            self.client.publish(self._discovery_topic(key), payload,
                                qos=1, retain=True)
        # Remove entities that are no longer delivered (e.g. a flex module
        # was removed, or a key was added to the exclude list).
        for key in sorted(self._announced - keys):
            self.client.publish(self._discovery_topic(key), "", qos=1,
                                retain=True)
        if keys != self._announced:
            _LOG.info("Announced %d sensors for %s (%s)", len(keys),
                      reading.model, reading.controller_id)
        self._announced = keys

    def publish(self, reading: Reading) -> None:
        if not self.client.is_connected():
            _LOG.warning("MQTT not connected, skipping update")
            return
        self._announce(reading)
        state = {k: v for k, v in reading.as_dict().items()
                 if k not in self.exclude}
        self.client.publish(self.state_topic, json.dumps(state), qos=0,
                            retain=False)
        self.client.publish(self.status_topic, "online", qos=1, retain=True)

    def offline(self) -> None:
        if self.client.is_connected():
            self.client.publish(self.status_topic, "offline", qos=1,
                                retain=True)

    def close(self) -> None:
        self.offline()
        self.client.loop_stop()
        self.client.disconnect()
