# Development conventions

Use documented Hermes Python `ctx` APIs only (`register_command`, `register_cli_command`).
Never patch core, touch real profiles or Omarchy hooks during tests (use temporary
HERMES_HOME and XDG_CONFIG_HOME), or select a theme on load. Selection happens only
through Hermes' own writer: `hermes config set display.skin <name>`.

One directory per theme under `themes/<slug>/` (colors.toml, optional skin.yaml and
meta.json). After changing themes run `python3 tools/build.py` and commit the
generated `skins/`. Keep colors `#rrggbb`. No private paths, credentials, telemetry,
network calls or remote fonts.

Run `python3 -m unittest discover -s tests`. The integration test needs a Hermes
checkout: `HERMES_REPO=... "$HERMES_REPO/venv/bin/python" tests/hermes-integration.py`.
