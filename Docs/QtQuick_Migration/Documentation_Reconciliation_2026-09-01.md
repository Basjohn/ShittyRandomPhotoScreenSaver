# Documentation / Test-Suite Reconciliation — 2026-09-01

Authority remains `Current_Plan.md`. This note records a documentation-only sweep after repo checkpoint `2e43a0cb` (R7 + event-driven Media). It changes no production owner or runtime behavior.

## Reconciled authority and safety wording

- J visual parity is governed first by the paired family oracle under `images/migration/Ideal (PreMigration)/` and `images/migration/Current (PostMigration)/` for pixels/details the pair shows. Release screenshots and historical source are secondary context, never implementation authority.
- Media has one explicit current-over-old visual exception: preserve the post-migration transport/control bar. Do not infer other Media exceptions from the current screenshot.
- Ordinary branded logo + name/header groups must scale with their cards and recover cross-family alignment. Missing CUSTOM/Edit alignment/snap guide lines are mandatory J parity restoration.
- Weather's intermittent `preferredContentHeight` binding loop is J geometry/parity debt by default; escalate back to H only if physical evidence proves functional/committed geometry corruption or lifecycle instability.
- R-63 overscan remains mandatory. R7's exterior-edge narrowing is an implemented hypothesis awaiting physical proof; do not describe the seam as solved until a real run proves both zero black flashes and zero shared-edge pixel residue.
- R1-R5 H5c checkpoint files are provenance only. R5 Halo performance was physically rejected. R6 native-`QCursor` performance architecture is the living cursor boundary; never restore moving-QML Halo state just to satisfy stale tests.
- Media steady-state fast polling is retired. Observation failure is loud/degraded + slow watchdog only; dead process-probe helpers are cleanup residue, not permission to restore polling.
- Image replacement after a base image exists is fail-closed: competing changes do not mutate queue truth, active transitions are not cancelled/snapped for replacement, and a destination is not direct-published merely because transition preparation failed.

## Maintained test profile: exact reconciliation still required

At checkpoint `2e43a0cb`, `tests/run_chunked.py` already includes `test_qtquick_h9_uniform_resize.py` and `test_media_event_observation.py`, but it still lacks these three surviving destination targets:

```text
test_visualizer_viewport_scaling_contracts.py
test_runtime_perf_policy_contracts.py
test_media_runtime.py
```

Add those three to `H_DESTINATION_PROFILE` in the exact cohesive worktree before the next aggregate H-profile claim, then run collection preflight. Do not publish a new target/pass count until that exact reconciled profile has run.

The previous 79/85 result is historical only. Six files remain in the maintained profile but contain stale assertions; **do not delete the files and do not restore retired production seams to satisfy them**:

- `test_qtquick_auxiliary.py` — replace retired `update_halo_pointer` / `halo_visible` / `pointer_position_changed` expectations with R6 native-cursor/event-cached state contracts.
- `test_qtquick_visualizer_bubble.py`, `test_qtquick_visualizer_devcurve.py`, `test_qtquick_visualizer_item.py` — update checkpoint-specific diagnostic/telemetry literals while preserving current behavior/ownership assertions.
- `test_bubble_viewport_reflow.py` — replace retired `_render_radius_in_world` helper use with current authored-pixel/radial/ring-spacing projection contracts.
- `test_s_hotkey_workflow.py` — update the test double to accept current `_show_next_image(origin=...)`; production `origin=` is current instrumentation/admission truth.

Whole-file obsolete/non-current cases are different and are tracked in `Docs/TestSuite.md`: old nonexistent black-flash/QML-capture filenames must not be recreated, tombstone/historical corruption tests can be removed in I, and legacy QWidget/GL presenter harnesses are I reconciliation residue rather than destination authority.

## Sweep outcome

The living plan, J docs, migration README, operator ledger, TestSuite and Future Cleanup now use the same authority/status story. Historical H5c checkpoints are explicitly fenced as superseded/provenance where necessary. Any future contradiction should be resolved in favor of `Current_Plan.md` + exact source + current physical evidence, then propagated back into `Docs/TestSuite.md` and the relevant living decomposition rather than silently patched in one document only.
