# Changelog

## 1.0.0

- First release as a Home Assistant app.
- Decoder rewritten to follow the vendor `schema.html` parser for all
  controller types; fixes several wrong offsets of the old script (e.g. HE on
  the 600 SR, flex values on the HC 680, module count on the FWRC 400).
- MQTT discovery with one device, availability and per-key exclude / names.
