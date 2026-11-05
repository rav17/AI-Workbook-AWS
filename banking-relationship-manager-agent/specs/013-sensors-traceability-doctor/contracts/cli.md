# CLI Contract

- `sensors list` - configured sensors (id, kind, stages, required).
- `sensors run <stage>` - run sensors for the stage; exit 1 if any fail. Records results and one `sensor_run` audit event per sensor (`sensor=<id> status=<pass|fail>`).
- `trace [--require-tests]` - print the matrix; exit 1 when uncovered requirements (or untested ones with `--require-tests`).
- `doctor` - one line per check `ok|warn|fail name: detail`; exit 1 on any fail. `--json` supported.
- `gate approve <stage>` - when `.specify/sensors/sensors.json` exists, refuses unless required sensors for the stage have fresh passing results; audit detail gets ` sensors=<ids>`.
- Option `--sensors-file` (default `.specify/sensors/sensors.json`).
