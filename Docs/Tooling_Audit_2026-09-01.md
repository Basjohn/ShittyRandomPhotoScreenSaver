# Tooling Authority Audit — 2026-09-01

Status: **CURRENT I AUTHORITY FOR `tools/` CLEANUP**

This audit was performed after Phase H closed and the Qt Quick destination became production authority.
Its purpose is to prevent old migration/investigation executables from becoming accidental architecture authority.

## Golden rule

```text
production runtime emits evidence
        ↓
focused current tests own deterministic contracts
        ↓
operator-side tools may observe or exercise a bounded external/runtime seam
```

A tool is not retained because it once helped. It stays executable only when it has a current, unique job.
Historical reports/goldens preserve evidence; they do not require preservation of a dead executable harness.

Current audited accounting after adding the re-homed ImageWorker harness: **40 current keep, 2 temporary architecture-selection tools queued for J deletion, 20 manual-delete tools = 62 tool files accounted for.** The new ImageWorker harness supersedes one of those 20 old names; applying the deletion list leaves 42 executable/support tool files.

### Tooling may never

- import/restore a deleted QWidget/GL/compositor/replay owner merely so an old harness passes;
- become an in-process production shutdown/startup action;
- create a second test manifest beside `tests/run_chunked.py`;
- claim Visualizer freshness/reactivity from synthetic DSP/simulation data alone;
- treat lower CPU/RAM/GC counters as permission to weaken R-69 cadence/reactivity/freshness;
- silently mutate installed/user settings when a repo-local/schema-derived path exists.

`R-72` records the production-shutdown parser authority failure that triggered the permanent production/tools boundary.

## Current keep set

### Canonical operator/build/schema tools

- `tools/build_layout.ps1`
- `tools/build_runner.py`
- `tools/check_ui_parity.py`
- `tools/convert_svg_to_png.py`
- `tools/convert_weather_svgs.py`
- `tools/download_weather_icons.py`
- `tools/regen_qrc.py`
- `tools/run_tests.py` — compatibility convenience only; delegates to canonical `tests/run_chunked.py`.
- `tools/theme_foundry.py`
- `tools/theme_foundry_model.py`
- `tools/default_settings_editor.py`
- `tools/defaults_foundry_core.py`
- `tools/regenerate_defaults_artifacts.py`
- `tools/regenerate_defaults_snapshot_artifacts.py`
- `tools/regenerate_sst_defaults.py`
- `tools/regenerate_visualizer_shipped_presets.py`
- `tools/visualizer_preset_repair.py`

The defaults regeneration family is **current and protected**: current schema sources are used, artifacts are constructed in memory, private fields are rejected, check/dry-run exists where applicable, and multi-file writes are transactional/rollback-safe. Do not recreate `R-33` by adding installed-profile mutation as a convenience fallback.

### Current focused runtime/external evidence

- `tools/perf_measure.py` — independent out-of-process process-tree sampler. Context only; application PERF telemetry remains freshness/GPU/GC/presentation authority.
- `tools/image_change_perf_parser.py` — narrow image-admission/prefetch/GC aggregation only. It is retained because it answers one bounded cross-event question; it is not a generic application-health parser.
- `tools/image_worker_shm_lifecycle_harness.py` — current R-52 spawned ImageWorker/shared-memory plateau and disposal proof.
- `tools/gsm_tc_spotify_video_probe.py`
- `tools/hardware_ingress_validator.py`
- `tools/media_key_matrix_compare.py`
- `tools/media_key_matrix_harness.py`
- `tools/media_key_reality_harness.py`
- `tools/reddit_helper_task_harness.py`
- `tools/winprobe_observer.py`
- `tools/flicker_test.py` — investigation-only Settings/Win32 isolator; not ordinary acceptance authority.

### Current focused Qt Quick smokes

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

These remain focused physical/runtime evidence for current Quick owners. Phase-named wording in `qtquick_phase_c_effect_smoke.py` is historical naming only; the harness exercises the current transition implementation.

### Current fixture generation

- `tools/generate_visualizer_replay_fixtures.py` — retain only as the deterministic synthetic `FeatureClip` fixture generator used by current feature-frame/fixture contracts. The old executable replay presenter is retired; fixture data/goldens remain evidence.

## Keep temporarily; delete in J after final physical/installed acceptance

These are bounded architecture-selection evidence and explicitly **not current product-performance authority**:

- `tools/presentation_benchmark_core.py`
- `tools/qtquick_presentation_spike.py`

They already label themselves as spikes/negative controls. Do not expand them. Delete them and their spike-only tests in J once final compiled/installed/physical acceptance no longer needs architecture-selection evidence.

## Manual delete now — no redeeming current executable authority

The following are I deletion residue. Historical documents that mention their old names stay historical.

- `tools/bubble_parity_harness.py` — simulation-only historical comparison; **no viewport/domain/DPR/presentation scaling oracle**, therefore incapable of catching R-69. Current Bubble viewport/reactivity/BTF tests are stronger.
- `tools/manual_preset_cleanup.py` — one-off persisted-state mutator superseded by current preset/schema owners.
- `tools/overlay_log_parser.py` — retired overlay telemetry.
- `tools/perf_integration_harness.py` — imports deleted Media/Visualizer/GL physical owners.
- `tools/phase1_measurement_benchmark.py` — Phase-1 measurement experiment; current instrumentation + external sampler supersede it.
- `tools/phase3_lifecycle_harness.py` — migration lifecycle evidence already captured historically.
- `tools/phase4_image_worker_shm_harness.py` — **superseded by** `tools/image_worker_shm_lifecycle_harness.py`.
- `tools/phase4_resource_harness.py` — count/resource migration harness superseded by application usage telemetry + `perf_measure.py`.
- `tools/phase5_frame_owner_benchmark.py` — imports deleted compositor metrics owner.
- `tools/phase5_thread_manager_benchmark.py` — synthetic general-executor benchmark from a Visualizer investigation; Visualizer no longer uses per-frame general executor tasks and the benchmark can misdirect optimization.
- `tools/qtquick_p0_presentation_benchmark.py` — imports deleted replay runtime and belongs to architecture selection, not destination acceptance.
- `tools/recovery_evidence_parser.py` — broken self-importing compatibility parser for a missing historical base.
- `tools/run_qtquick_p0_light_01.ps1`
- `tools/run_worker_push_p0_light_01.ps1`
- `tools/slide_metrics_parser.py` — old Slide/GL metric schema.
- `tools/spotify_vis_metrics_parser.py` — old GL/overlay Visualizer metric schema; never reconnect it to `main.py`.
- `tools/transition_perf_health_parser.py` — overgrown generic archaeology parser. Current app instrumentation already owns the useful telemetry; focused parsers/tests should exist only for a demonstrated bounded question.
- `tools/visualizer_distribution_harness.py` — synthetic/private `_fft_to_bars` scoring duplicates stronger maintained DSP/reactivity tests and is not presentation/scaling authority.
- `tools/visualizer_replay.py` — imports deleted replay physical owner. Preserve fixtures/goldens and current temporal tests, not the dead executable host.
- `tools/worker_push_presentation_benchmark.py` — imports deleted physical Visualizer/presenter owners.

## Tool-coupled tests to delete/rehome in I

Delete these with the executable owner after confirming the supplied H-closure test patch/current owner map is present:

- `tests/test_phase1_measurement_benchmark.py`
- `tests/test_phase3_runtime_lifecycle.py`
- `tests/test_qtquick_p0_presentation_benchmark.py`
- `tests/test_recovery_evidence_parser.py`
- `tests/test_transition_perf_health_parser.py`
- `tests/test_visualizer_replay.py`
- `tests/test_worker_push_presentation_benchmark.py`

Do **not** delete fixture/golden tests merely because the old replay executable is gone. Current tests such as Bubble cadence/BTF/viewport, Spectrum smoothing and feature-frame/temporal-golden tests own the surviving behavior contracts.

## Permanent boundary tests

`tests/test_tooling_ownership.py` is destination coverage. It protects:

- production Python never importing `tools`/`scripts` analysis modules;
- `tools/run_tests.py` delegating to `tests/run_chunked.py` rather than owning a second suite list;
- attached-PID resource observation remaining passive;
- the re-homed ImageWorker SHM harness using the current spawned-worker/image-pipeline owner.

## Audit discipline for future tools

Before retaining or adding a tool, answer all of these:

- [ ] What exact current question can this tool answer that built-in instrumentation/current tests cannot answer more directly?
- [ ] Does it exercise the current owner rather than a deleted compatibility host?
- [ ] Is its output incapable of being mistaken for physical/freshness/reactivity proof when it is synthetic?
- [ ] If it mutates artifacts/settings, is scope explicit, repo-local by default, validated and rollback-safe?
- [ ] Is the tool out-of-process unless its job genuinely requires current runtime construction?
- [ ] Is there one canonical owner for the underlying test/telemetry/schema contract?
- [ ] Would deleting the tool lose an actual capability, rather than only convenience or historical nostalgia?

If the final answer is “no unique capability,” delete the executable and preserve only the historical evidence that still matters.

## Preset/default tooling result

The preset/default tooling was audited separately because stale mutators can destroy authored Visualizer behavior even when runtime ownership is correct.

Current disposition:

- `tools/manual_preset_cleanup.py` — **DELETE**. One-off persisted-state mutator; no current ownership value.
- `tools/visualizer_preset_repair.py` — **KEEP**. It repairs curated source presets through the current Visualizer mode/schema/migration owners, writes recoverable backups, audits stale/deprecated payload shapes, and re-synchronizes shipped artifacts. Batch Repair All now defers release/manifest synchronization until the batch boundary instead of remirroring the whole curated tree once per file.
- `tools/regenerate_visualizer_shipped_presets.py` — **KEEP**. Source of truth is `presets/visualizer_modes`; generated targets are the manifest and Media Center release mirror. It now provides read-only `--check` / `--dry-run` modes so operators can prove drift without mutating the tree.
- `tools/regenerate_defaults_artifacts.py` + wrappers / Defaults Foundry — **KEEP**. These are current-schema/default owners, build output in memory, reject private/machine-local state and use transactional writes. Visualizer defaults are normalized through the current schema-v5 boundary; they do not treat curated runtime preset selection/custom backup state as canonical defaults.
- Build-runner preset-manifest regeneration remains a **generated-artifact/build responsibility**, not runtime preset ownership.

Guardrail: curated preset tooling may repair/regenerate repository artifacts, but must never become a second runtime preset owner, directly edit installed profile preset state as a convenience cleanup, or restore retired Visualizer presentation contracts. Prefer read-only audit/check modes before mutating commands.

Current curated-tree static audit (2026-09-01): 26 preset JSON files inspected; no duplicate preset slots, non-contiguous authored slots, `custom_preset_backup` blocks, or known deprecated authored/global keys were found. This complements, but does not replace, the real-environment preset tests.

