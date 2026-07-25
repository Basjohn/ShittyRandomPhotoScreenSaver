# Phase Report — P00: Freeze, Inventory, and Evidence Preservation

## Metadata

- Branch at Phase 0 capture: `recovery-00edb57`; current completed checkpoint: `main`
- Commit before: `00edb57a3076b845cb8ee4b6cb7f36ea83411f0c`
- Commit after: Phase 1 checkpoint on `main`; Gate 0 is closed by `Docs/phase_reports/P01_MEASUREMENT_FOUNDATION.md`
- Date: 2026-07-25
- Codex/session: architecture recovery kickoff
- Environment manifest: recorded below
- Related decisions: ADR-A through ADR-J in the recovery roadmap

## Phase objective

Create a reproducible recovery starting point without changing runtime behaviour.

## Hypothesis

The supplied baseline and donor archives, combined with a static source ownership inventory, are sufficient to identify the first measurement seams without importing donor control flow or changing visualizer, lifecycle, transition, or image behaviour.

Phase 1 subsequently completed the measurement checkpoint on main, based on baseline 0edb57a3076b845cb8ee4b6cb7f36ea83411f0c. Donor 7376bb9bb380253f3bd14079e65d7bdbca062fad remains reference-only/read-only; this report preserves the Phase 0 capture context rather than an active branch instruction.

## Invariants protected

- Visualizer: no equations, presets, cadence, rendering, or expected output changed.
- Lifecycle: no Settings/Edit or GL teardown code changed.
- Frame pacing: no scheduler, timer, paint, or update path changed.
- Memory: no cache or resource lifetime changed.
- Threading: no pool, task, timer, queue, or callback path changed.

## Repository and evidence freeze

| Check | Result |
|---|---|
| Current branch | `recovery-00edb57` |
| Current commit | `00edb57a3076b845cb8ee4b6cb7f36ea83411f0c` |
| Recovery ancestry | `00edb57` is `HEAD`; ancestor check passed |
| Donor ref | `donor-7376bb9` -> `7376bb9bb380253f3bd14079e65d7bdbca062fad` |
| Working tree | Not clean before this tranche; documentation recovery work and `.codex/` were already dirty/untracked |
| Donor archive | `logs/evidence_chest/logs7376bb9.zip` |
| Donor SHA-256 | `2E0E125BF4D8877D55EFFAFEEE82CC3367EB9B4A319669122F372801878B0D74` |
| Baseline archive | `logs/evidence_chest/logs00edb57.zip` |
| Baseline SHA-256 | `90AF3A54058FEBD54E961CA56FFFBDDD26D8AB4204EC605C1E8C4C4305E5DAEB` |
| Extraction | `head_7376bb9/` and `baseline_00edb57/`, both ignored by `/logs/*` |

The original archives were not modified. `logs7376bb9.zip` is the canonical donor filename; stale `logs.zip` references were corrected.

## Environment manifest

- OS: `Get-ComputerInfo` reports Windows 10 Pro compatibility name, 64-bit, build 26200
- Python: 3.11.9 at `C:\Python311\python.exe`
- PySide6: 6.9.1
- CPU: AMD Ryzen 9 5900X, 12 cores / 24 logical processors
- RAM: 34,275,409,920 bytes (31.9 GiB)
- GPU: NVIDIA GeForce RTX 4090, driver 610.62, 24,564 MiB dedicated memory
- Current displays:
  - screen 0, MSI G321Q: 1707x960 logical, DPR 1.5, 164.835 Hz
  - screen 1, LG TV: 2560x1440 logical, DPR 1.5, 60 Hz
- Evidence display records:
  - screen 0: 1707x959 logical at `(0, 0)`, DPR 1.5, target 165 Hz
  - screen 1: 2560x1439 logical at `(2560, 0)`, DPR 1.5, target 60 Hz
- Power profile: Balanced
- Audio source: PyAudioWPatch loopback on `Speakers (Realtek(R) Audio) [Loopback]`
- Runtime flags: debug plus `--perf --usage --viz --geo --set --life --cache`; verbose disabled
- Image/display settings observed: 40-second rotation, fill mode, shuffle enabled, history 50, local ratio 55%, image cache 24 items / 1024 MiB
- Visualizer target display: screen 1

## Visualizer modes and authored presets in both evidence runs

| Mode | Preset | Bars | Block | Sensitivity | Floor / AGC |
|---|---|---:|---:|---:|---|
| Bubble | Preset 1 (Deep Sea) | 48 | 128 | 0.550 | manual 0.300, AGC 0.000 |
| Dev Curve | Preset 2 (Rainbow Rapids) | 35 | 256 | 1.350 | manual 0.150, AGC 0.100 |
| Spectrum | Preset 1 (Organs) | 35 | 128 | 0.970 | manual 0.420, AGC 0.340 |
| Oscilloscope | Preset 1 (Electric) | 32 | 256 | 0.400 | manual 0.120, AGC 0.450 |
| Sine Wave | Preset 1 (Wobble Groove) | 40 | 128 | 1.200 | manual 0.400, AGC 0.650 |

## Evidence scenario timelines

The timestamps below are reconstructed from the preserved logs. They distinguish logged events from conditions that the archives cannot prove.

### Baseline `00edb57` — 2026-07-23 19:37:45 to 19:46:11

| Time | Logged scenario event |
|---|---|
| 19:37:45 | Screensaver starts with 40-second rotation, fill mode, shuffle, two displays, Spotify visualizer on screen 1, and Bubble / Preset 1 (Deep Sea). |
| 19:39:01 | CUSTOM layout reload is requested. This causes a complete stop, display cleanup/recreation, generation change, and restart; it is not a Settings dialog cycle. |
| 19:40:22–19:42:32 | Curated-mode sequence is Bubble -> Dev Curve -> Spectrum -> Oscilloscope -> Sine Wave -> Bubble. |
| 19:43:14–19:43:24 | Bubble reports 11.99 s, 12.80 s, and 22.25 s latency events associated with visualizer transition-end/start triggers. The causal source is not proven by the logs. |
| 19:43:38–19:43:50 | One Settings cycle is requested, the dialog runs, and a full-style display/GL restart completes. Logged lifecycle time is 12,233.5 ms, including 9,410.2 ms in the dialog; `sources_changed=False`. |
| 19:46:10–19:46:11 | Terminal cleanup/shutdown. |

### Donor `7376bb9` — 2026-07-22 09:30:06 to 10:03:17

| Time | Logged scenario event |
|---|---|
| 09:30:06 | Screensaver starts with 40-second rotation, fill mode, shuffle, two displays, Spotify visualizer on screen 1, and Bubble / Preset 1 (Deep Sea). |
| 09:32:13–09:35:36 | Curated-mode sequence is Bubble -> Dev Curve -> Spectrum -> Oscilloscope -> Sine Wave -> Bubble. |
| 09:45:48–09:47:01 | Settings cycle 1 closes with a full-style restart. Logged lifecycle time is 72,361.6 ms, including 71,464.1 ms in the dialog; `sources_changed=False`. |
| 09:48:16–09:55:24 | Settings cycle 2 closes with another full-style restart after an approximately seven-minute dialog interval. Cleanup records thousands of paint waits and one timeout per adaptive timer. |
| 10:01:30–10:01:32 | Rotation interval changes from 40 seconds to 180 seconds and runtime state is recreated. |
| 10:02:21–10:02:29 | Settings cycle 3 closes with another full-style restart. |
| 10:03:17 | Evidence run ends. |

Both runs include normal image rotations, random transitions, active overlays, and periods of Spotify playback. Neither archive proves the operator's exact manual intent, background application load, disk contention, GPU contention, or a controlled audio-input waveform. Those remain explicit comparability limits rather than missing logged scenario events.

## Code inspected

### Baseline / recovery

- Runtime and Settings/Edit sequencing: `engine/screensaver_engine.py`, `engine/engine_lifecycle.py`, `engine/display_manager.py`.
- Display and compositor: `rendering/display_widget.py`, `rendering/gl_compositor.py`, `rendering/gl_compositor_pkg/`.
- GL programs/resources: `rendering/gl_programs/`, `core/resources/manager.py`.
- Transition state: `rendering/transition_controller.py`, `transitions/`.
- Image work: `engine/image_pipeline.py`, `utils/image_prefetcher.py`.
- Timer/task ownership: `rendering/adaptive_timer.py`, `rendering/render_strategy.py`, `core/threading/manager.py`.
- Visualizer simulation/presentation: `widgets/spotify_visualizer/`, `widgets/spotify_bars_gl_overlay.py`.

### Donor

The same ownership sites were inspected at `7376bb9`, plus donor-only/high-impact seams in `rendering/gl_programs/context_identity.py`, `rendering/gl_compositor_pkg/spotify_visualizer_layer.py`, `rendering/image_upload_payload.py`, and donor GL work in `engine/display_manager.py` / `rendering/display_widget.py`.

Detailed ownership and call-site conclusions are in `P00_SOURCE_OWNERSHIP_INVENTORY.md`.

## Changes made

- Added a read-only archive parser at `tools/recovery_evidence_parser.py`.
- Added focused parser tests and realigned the stale visualizer documentation-reference test with current canonical ownership.
- Generated ignored derived evidence for both archives: summary JSON, frame-window CSV, task-rate CSV, memory CSV, GPU CSV, lifecycle CSV, visualizer-gap CSV, deduplicated warnings/errors, and retained unknown lines.
- Recorded environment, scenario, visualizer presets, ownership, and evidence conclusions.
- Corrected the donor evidence filename contract to `logs7376bb9.zip`.
- Updated the live checklist and active plan without claiming Gate 0 completion.

## Changes explicitly not made

- No runtime Python module was changed.
- No donor code was copied, cherry-picked, or merged.
- No visualizer constants or expected data were changed.
- No lifecycle, compositor, transition, cache, task, timer, or GL behaviour was changed.
- No archive or extracted source log was edited.

## Tests added/changed

- `tests/test_recovery_evidence_parser.py`
- `tests/test_visualizer_doc_references.py` (removed deleted-audit and misplaced top-level tooling assertions; retained canonical-reference and stale-path checks)

## Validation

- `python -m py_compile tools/recovery_evidence_parser.py tests/test_recovery_evidence_parser.py` — passed.
- `python -m pytest tests/test_recovery_evidence_parser.py tests/test_visualizer_doc_references.py -q --tb=short` — 8 passed.
- Both documented archive-parser commands completed and reproduced the preserved SHA-256 values.
- `git diff --check` — passed; only the repository's existing LF-to-CRLF warnings were emitted.

## Runtime scenarios executed

No new SRPSS runtime scenario was executed in Phase 0. The supplied baseline and donor runs were parsed. This report does not treat the two archives as laboratory-identical runs.

## Evidence comparison

| Metric | Baseline `00edb57` | Donor `7376bb9` | Interpretation |
|---|---:|---:|---|
| Usage duration | 8m 26s | 33m 11s | Not identical duration |
| CPU app median / max | 64.4% / 107.9% | 38.5% / 101.5% | Both can approach one logical core |
| Total submissions/sec median / max | 78.2 / 171.0 | 77.0 / 177.9 | High recurring task rate in both |
| Paint-window `dt_max` median / max | 66.8 / 149.7 ms | 72.6 / 147.2 ms | Window aggregates do not expose p99 |
| Visualizer microgap p95 max | not emitted | 1047 ms | Donor exposes severe tail starvation |
| Visualizer microgap max | not emitted | 8656 ms | Donor burst-delivery evidence |
| RSS median / peak | 1547 / 1771 MiB | 1522 / 1840 MiB | Both exceed target investigation gate |
| Private commit median / peak | 4529 / 5142 MiB | 3583 / 4113 MiB | Donor lower, still excessive |
| Dedicated VRAM median / peak | 1491 / 1873 MiB | 645 / 923 MiB | Donor resource work improves bounds |
| GPU busy median / peak | 14.7% / 32.4% | 8.8% / 25.5% | CPU-heavy despite low GPU busy |

Important limits:

- These logs contain aggregate frame windows, not every raw frame interval, so p50/p90/p95/p99 cannot be reconstructed honestly.
- The baseline archive contains one Settings/recreation sequence, not the required lifecycle loop.
- The donor archive does not contain the literal final cross-thread `QOpenGLContext` line; that remains an externally observed failure requiring controlled reproduction.
- The 22-second baseline latency outlier is retained, not discarded. It occurs in Bubble around visualizer transition-end/start triggers before the Settings request, but the causal source is not proven; it must not be presented as a steady-state metric.

## Visualizer fidelity result

- Deterministic replay: unavailable; Phase 2 blocker remains.
- Spectrum manual review: supplied user observation favours baseline; no new review performed.
- Bubble manual review: supplied user observation favours baseline elasticity/reactivity; no new review performed.
- Irregular-presentation test: unavailable.

## Lifecycle result

The baseline log records complete display cleanup/recreation and no literal cross-thread context error in the supplied archive. This is evidence, not a pass of the 50/50/50 lifecycle gate.

## Memory/resource result

Baseline RAM/private-commit/VRAM do not plateau within acceptable bounds. Donor VRAM is materially better, but donor memory remains above investigation gates and donor lifecycle/presentation architecture is rejected.

## Unexpected findings

- The baseline already contains adaptive-timer and compute-pool presentation machinery; recovery cannot treat every adaptive-timer concept as donor-only.
- ResourceManager tracks GL cleanup callbacks, but tracking alone does not prove current-context deletion.
- Baseline and donor task-rate medians are similar in these archives; donor complexity did not solve recurring submission pressure.
- The roadmap and several core docs used two donor archive names. The preserved filename is now canonicalized as `logs7376bb9.zip`.
- The visualizer documentation-reference test still enforced a deleted audit file, an obsolete Spec heading, and top-level ownership of a focused repair tool; the test now follows the canonical document boundaries.

## Failures and rejected approaches

- The workspace patch helper repeatedly failed during sandbox initialization. Repository edits used exact, workspace-validated replacements as a tooling fallback.
- Superseded: the Phase 1 checkpoint supplied the clean committed recovery point and closed Gate 0; see `Docs/phase_reports/P01_MEASUREMENT_FOUNDATION.md`.

## Rollback instructions

- Remove `tools/recovery_evidence_parser.py` and `tests/test_recovery_evidence_parser.py`.
- Revert the Phase 0 ownership-alignment changes in `tests/test_visualizer_doc_references.py`.
- Remove this report and its inventory.
- Revert only the Phase 0 checklist/path edits; do not revert the pre-existing recovery documentation wholesale.
- Derived evidence under `logs/evidence_chest/derived/` is ignored and may be regenerated from the preserved ZIPs.

## Gate decision

- [x] Pass
- [ ] Fail
- [ ] Pass with explicit deferred issue

Current state: **complete**. The Phase 1 checkpoint supplied the clean committed recovery point and closes Gate 0; see `Docs/phase_reports/P01_MEASUREMENT_FOUNDATION.md`.

## Live checklist updates

The roadmap checklist and `Current_Plan.md` now record Gate 0/1 completion and Phase 2 as the active next slice.
