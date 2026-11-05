# Plan: AI-DLC extras pack

Data only, no engine change: uses plugin stages (018), plugin profiles and sensors (020) and the `section` sensor with `profiles` scope (025).

- Files: `plugin.json`, `stages.json`, `profiles/*.json`, `sensors.json`, `templates/*.md`, `README.md`.
- Stages load once at import, so tests use a subprocess against an isolated copy.
- Templates are guidance only; no code reads them.
