# Tooling Authority Audit — stable route, re-audited 2026-09-03

Status: **CURRENT POST-CUTOVER TOOLING AUTHORITY**  
Current source basis: `ab6d5f6055507f85ae410fb40100069c30a752a5` (2026-09-03).  
The filename is retained as a stable documentation route; the old 2026-09-01 Phase-I keep/delete ledger is superseded by this content.

## Golden rule

```text
production runtime emits evidence
        ↓
current tests own deterministic contracts
        ↓
operator tools may author assets or observe/exercise one bounded current seam
```

A tool is not retained because it once helped. It stays executable only while it has a current unique job. Historical reports/goldens preserve evidence without requiring a dead executable harness.

Tooling may never:

- import/restore a deleted QWidget/GL/compositor/replay owner so an old harness passes;
- become a hidden in-process production startup/shutdown action;
- create a second test manifest beside `tests/run_chunked.py`;
- claim Visualizer physical freshness/reactivity from synthetic data alone;
- lower cadence/freshness/amplitude or disturb R-69/R-76 to improve counters;
- add polling/timers/fallback owners merely because a diagnostic wants easier sampling;
- silently mutate installed/user settings when a repo-local/schema-derived authoring path exists.

`R-72` remains the permanent production/tools import boundary.

## Current accounting

The exact top-level `tools/` tree at the source basis contains **48 files**:

- **22** build/schema/authoring/operator utilities;
- **11** focused probes/parsers/runtime evidence tools;
- **11** current Qt Quick smoke harnesses;
- **2** closed-P0 attribution harnesses retained temporarily as evidence;
- **2** architecture-selection spikes retained until J exit.

The old 2026-09-01 `20 manual delete now` executable set is already absent and must not be recreated. `tools/material_rollback_cleanup_gui.py` has also completed its one rejected-card-material cleanup job and is absent from current source. `tools/generate_visualizer_replay_fixtures.py` is absent too; fixture/golden authority survives without that executable.

## KEEP — build / schema / authoring / operator workflow

- `tools/build_layout.ps1`
- `tools/build_runner.py`
- `tools/check_ui_parity.py`
- `tools/convert_svg_to_png.py`
- `tools/convert_weather_svgs.py`
- `tools/default_settings_editor.py`
- `tools/defaults_foundry_core.py`
- `tools/download_weather_icons.py`
- `tools/generate_widget_theme_mirrors.py`
- `tools/godzip_foundry.py`
- `tools/godzip_foundry_core.py`
- `tools/regen_qrc.py`
- `tools/regenerate_defaults_artifacts.py`
- `tools/regenerate_defaults_snapshot_artifacts.py`
- `tools/regenerate_sst_defaults.py`
- `tools/regenerate_visualizer_shipped_presets.py`
- `tools/run_tests.py` — convenience delegate only; `tests/run_chunked.py` remains canonical.
- `tools/theme_foundry.py`
- `tools/theme_foundry_model.py`
- `tools/visualizer_preset_repair.py`
- `tools/widget_theme_foundry.py`
- `tools/widget_theme_foundry_model.py`

### Foundry boundaries

Theme/Widget Theme Foundries edit the production schemas and strict-reload saved output; they do not invent parallel theme schemas. GODZIP Foundry is repo/operator transfer tooling, never production runtime authority. Its persistent preferences belong repo-locally under `.godzip_foundry/`, not AppData/QSettings. Archive manifests describe included bytes; omission never means delete; debris deletion remains explicit/reversible under `/deleteme`.

Defaults/preset regeneration remains protected current tooling: derive from current schema/source truth, reject private/machine-local state, prefer check/dry-run before writes, and keep multi-file writes transactional where applicable. Never mutate an installed user profile as a convenience fallback.

## KEEP — focused current evidence / probes

- `tools/flicker_test.py` — Settings/Win32 investigation isolator; not general product acceptance authority.
- `tools/gsm_tc_spotify_video_probe.py`
- `tools/hardware_ingress_validator.py`
- `tools/image_change_perf_parser.py` — bounded image-admission/prefetch/GC correlation, not a generic health parser.
- `tools/image_worker_shm_lifecycle_harness.py`
- `tools/media_key_matrix_compare.py`
- `tools/media_key_matrix_harness.py`
- `tools/media_key_reality_harness.py`
- `tools/perf_measure.py` — passive external process/resource context; application PERF/QML/GPU/GC telemetry remains runtime authority.
- `tools/reddit_helper_task_harness.py`
- `tools/winprobe_observer.py`

Keep these only while they answer their narrow current question. Do not expand one into a generic framework because another subsystem needs evidence.

## KEEP — current Qt Quick smokes

- `tools/qtquick_abandonment_issues_smoke.py`
- `tools/qtquick_achievement_pulse_smoke.py`
- `tools/qtquick_blinds_smoke.py`
- `tools/qtquick_clock_smoke.py`
- `tools/qtquick_gmail_smoke.py`
- `tools/qtquick_media_smoke.py`
- `tools/qtquick_phase_c_effect_smoke.py`
- `tools/qtquick_reddit_smoke.py`
- `tools/qtquick_render_node_smoke.py`
- `tools/qtquick_visualizer_clip_smoke.py`
- `tools/qtquick_weather_smoke.py`

Phase-coded naming in `qtquick_phase_c_effect_smoke.py` is historical naming only; it exercises current transition owners. Smoke output is runtime evidence, not automatic visual parity.

## TEMPORARY EVIDENCE — closed P0 attribution harnesses

- `tools/gc_gen2_attribution_harness.py`
- `tools/viz_logical_gil_contention_harness.py`

These proved the P0-B retained-set Gen2 mechanism and P0-A Windows GIL-held enumeration mechanism respectively. Their findings are now protected by production policy/tests and the attribution record. They are **not** current product-performance authority and must not drive retuning after their owning leads are closed.

Disposition: keep through the remaining recreation/resource/J acceptance window for reproducibility; at J exit, re-check whether any unique diagnostic value remains. If not, delete them rather than canonizing one-off attribution experiments.

## J EXIT — architecture-selection evidence only

- `tools/presentation_benchmark_core.py`
- `tools/qtquick_presentation_spike.py`

These are bounded architecture-selection/negative-control evidence. Do not expand them. Delete them with spike-only tests once final compiled/installed/physical acceptance no longer needs that evidence.

## Already retired — do not resurrect

The old manual-delete list (replay/overlay/worker-push/phase benchmark/parser executables) is absent from current source. Specific anti-resurrection examples:

- no `tools/visualizer_replay.py` physical host;
- no `tools/generate_visualizer_replay_fixtures.py` executable requirement;
- no generic `transition_perf_health_parser.py` archaeology authority;
- no old overlay/Spotify-GL metrics parsers;
- no `material_rollback_cleanup_gui.py` after rejected-card-material debris was removed;
- no phase benchmark/recovery parser solely to make museum tests pass.

Fixture/golden data may remain useful independently of the executable that once produced it. Regenerate only through a current-owner route if a real contract requires regeneration.

## Permanent boundary / review questions

Before adding or retaining a tool:

- [ ] What exact current question does it answer that production telemetry/current tests cannot answer more directly?
- [ ] Does it exercise the current owner rather than a retired compatibility host?
- [ ] Is synthetic output clearly fenced from physical/freshness/reactivity claims?
- [ ] If it writes artifacts/settings, is scope explicit, repo-local where appropriate, validated and recoverable?
- [ ] Is it out-of-process unless its exact job genuinely requires current runtime construction?
- [ ] Does it avoid a second cadence/poller/timer/fallback owner?
- [ ] Would deleting it lose a real current capability rather than only historical convenience?

If the answer to the last question is no, delete the executable and preserve the lesson/evidence in docs/tests instead.
