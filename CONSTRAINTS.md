# Constraints

Last reviewed: 2026-11-07

## Floor (always enforced)
- No new suppressions (`# noqa`, `# type: ignore`) and no bare `except:`.
- No stubs or silent failures; no skipped or deleted tests without a reason in the commit message.
- No secrets, private paths, telemetry, network calls or remote fonts.
- Colors stay `#rrggbb`; generated `skins/` is committed after `python3 tools/build.py`.
- Tests never touch real profiles or Omarchy hooks (temporary `HERMES_HOME` and `XDG_CONFIG_HOME`).
- This file is not weakened to make a change pass.

## Enforced with numbers
| Dimension | Rule | Checked by | Runs at |
|---|---|---|---|
| Tests | all green (today: 22 pass) | `python3 -m unittest discover -s tests` | every change |
| Integration | green against a Hermes checkout | `"$HERMES_REPO/venv/bin/python" tests/hermes-integration.py` | before release |

No linter or CI is configured.

## Measured ratchets (must not get worse)
| Metric | Today | Command | Direction |
|---|---|---|---|
| Suppressions / bare except | 0 | `git grep -nE "# noqa\|# type: ignore\|except:" -- '*.py' \| wc -l` | stays 0 |
| Skipped tests | 0 | `git grep -nE "skip\(\|skipIf\|skipUnless\|expectedFailure" -- tests \| wc -l` | stays 0 |

## Exceptions
| ID | Rule | Path | Reason | Expires |
|---|---|---|---|---|
