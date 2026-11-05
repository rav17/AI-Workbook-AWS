# Data Model: Layered Rules and Customization Overlay

- **Rule layer files:** `.specify/rules/{org,team}.json` and `rules.json` (project). Same `Rule` schema as before; only `status: active` rules are effective.
- **Effective rule view:** a rule dict plus `layer` (`org|team|project`) and `conflict`; the result also lists `overridden` `{layer, id}` entries.
- **Overlay:** `.specify/custom/profiles/<id>.json` (a `Profile`) and `.specify/custom/sensors.json` (`{"sensors": [...]}`, the sensor schema).
- **Overlay item description:** `{type: profile|sensor, id, effect: add|override}`.
- **Validation:** overlay profiles must match the filename id; overlay sensors must not reuse the id of a required core sensor.
