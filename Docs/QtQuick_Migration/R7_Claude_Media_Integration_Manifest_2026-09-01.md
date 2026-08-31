# R7 + Claude Media integration manifest — 2026-09-01

R7 image/surface integrity work is based on the R6+H9 checkpoint. The operator's local repository additionally contains Claude's event-driven Media commit:

`2e7a9242dabbc838c5ac212e57c25a269f8cf23f`

Claude-owned paths in that commit:

- `Current_Plan.md` (merged into the R7 plan in this checkpoint)
- `Docs/Qt_QML_Observability.md`
- `core/media/media_controller.py`
- `widgets/media_runtime.py`
- `tests/run_chunked.py`
- `tests/test_media_event_observation.py`
- `tests/test_media_runtime.py`

The attached operator smoke is assessed in `H_Media_Event_Observation_Physical_Smoke_2026-09-01.md`.

Do not restore the retired active Media poll or introduce a second controller/query owner. The event-driven implementation remains authoritative while its broader physical gate is completed.
