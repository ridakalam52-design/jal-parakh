# Built with AgentFoundry

This change was made in the **AgentFoundry desktop IDE** (v0.1.80, Linux build, signed in as `ridakalam52`) on **28 October 2026**.

## What was done in AgentFoundry

- Opened this repository as a project in AgentFoundry.
- Used **SMART-Code** (AgentFoundry's bundled coding agent, Cloud · Smart mode, free trial credits) with this task:
  add a `GET /api/strip-chart` endpoint that returns every supported strip parameter with its BIS/WHO limits
  and, where available, the colour-chart swatches, moving the chart ramps into one shared module, with tests.
  SMART-Code read the codebase, planned the change and wrote the first version of all files below.
- Sent SMART-Code a second, review-feedback turn (full source citation + `source_short`, `{value, hex}` swatch
  objects, script import path, stronger tests), which it applied.
- Finished the review by hand: simplified how `scripts/make_demo_strips.py` builds `CHART`, and added tests that
  pin the original colour values. Regenerated the demo images and confirmed they are byte-for-byte unchanged.
- Ran the test suite in AgentFoundry's integrated terminal: `100 passed`.

## Files changed

| File | Change |
| --- | --- |
| `app/strip_chart.py` | New. The colour ramps keyed by canonical parameter keys; hex helpers. |
| `app/main.py` | New `GET /api/strip-chart` endpoint. |
| `scripts/make_demo_strips.py` | Imports the ramps from `app/strip_chart.py` instead of keeping its own copy. |
| `tests/test_strip_chart.py` | New tests for the endpoint, limits, sources and chart equivalence. |

## The endpoint

`GET /api/strip-chart` returns `{"standard": "BIS IS 10500:2012", "chart_note": ..., "params": [...]}`. Each
parameter carries its English and Hindi names, unit, acceptable / permissible / low limits, health flag,
`limit_text`, full `source` citation and `source_short` (BIS or WHO), plus `swatches` (`[{"value", "hex"}]`) or
`null` when the demo chart has no row for it.

The swatches are the reference chart used to draw the **synthetic demo strips**, not a lab standard. The live
reader always matches pads against the chart printed in the user's own photo.

## Screenshots

- `smartcode-prompt.png`: the project open in AgentFoundry with the SMART-Code chat and the task.
- `tests-passing.png`: the new `app/strip_chart.py` open in the editor and `pytest -q` passing in the AgentFoundry terminal.
