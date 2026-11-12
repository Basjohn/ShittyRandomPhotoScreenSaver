# Tooling

Every script and harness the project keeps: where it is, what it does, its command line, who may run it, what it
reads and writes, and which tests and documents describe it. Compiled on 12 Nov 2026 from the tools' own argparse
and source (no tool was run to produce it; `--help` of a tool is authoritative where this page and the tool differ).

Routing of the recurring acceptance commands (what to run for which claim) stays in
[Harness_Index.md](Harness_Index.md); depth for one area stays in the document named in its row. This page is the
inventory: if a tool exists it has a row here.

**Keeping it current.** Whoever adds, renames, removes or changes the flags of a tool edits its row in the same
commit (a new file under `tools/`, `scripts/` or `native/spike_p1/python/` without a row is an incomplete change).
The Orchestrator Handbook's "where everything is" table points here. A tool nobody calls goes to the
[Candidates to retire](#candidates-to-retire) table first; nothing is deleted without the operator's word
(operator rule: keep useful tools).

## Conventions in this page

- `PY` is `.venv\Scripts\python.exe` run from the repository root (a worktree agent uses the main checkout's venv,
  see `Docs/Guardrails/Agent_Worktree_Rules.md`). `-m tools.x.y` modules run from the repository root.
- **Who** column: **ANY** = any agent, because the tool is offscreen/headless/read-only (no visible window, no load,
  no build, no network); **LEAD** = the lead only; **OP** = the operator only (real windows, real hardware, network,
  or a destructive step); **GH** = runs on GitHub's runners through the workflows, never on this machine; **LIB** =
  an importable helper, not a command.
- **Out** column: "layout" = the tool writes through `tools/artifact_paths.py` into
  `.artifacts/evidence/<area>/<topic>/<YYYYMMDD>_<label>/` (or `.artifacts/webp/...`), its `--output`/`--out`
  argument defaults there and an explicit one must lie inside it, and `tools/evidence_media.py` publishes the files
  unchanged on success (a failed run's owner scratch is kept and printed). "scratch" = `.artifacts/scratch/<owner>/`.
  A tool that writes elsewhere says where.
- Flags are copied from the tool's argparse. `[x]` optional, `x|y` choices, `x...` repeatable, `=D` default.
- Rules that bind every row: builds only through GitHub (`tools/build_runner.py --mode github`); load runs
  (`game60`, `tools/gpu_load_generator.py`, `--load`) only by the lead after the operator's yes, at most 10
  minutes, never a baseline; `tools/d1_run.py` visible runs only by the lead and never on the primary display, agents
  use `--hidden`; no live Reddit anywhere (stub DNS/transport); no environment-variable flags; evidence only through
  `tools/artifact_paths.py`; no visible windows in probes and tests; presets are authored content (no tool lists,
  counts or pins preset names or contents).

## Start here: the twenty most used

| # | Tool | Use it to | Who |
|---|---|---|---|
| 1 | `tools/artifact_paths.py` | find or make an evidence/scratch path (`evidence_dir(area, topic, label)`); `areas` lists the vocabulary; `prune-scratch [--apply]` | ANY (`--apply`: LEAD) |
| 2 | `tools/evidence_media.py` | publish scratch to evidence, encode a frame sequence to one animated WebP (`animated_webp`) | LIB |
| 3 | `tools/agent_handover.py` | see every agent worktree, its journal, save an interrupted agent's work (`--commit`), retire after merge (`--retire`) | LEAD |
| 4 | `tests/run_chunked.py` | `--isolated [--changed]` at milestones; `--profile destination`; focused files otherwise | ANY (focused), LEAD (whole suite) |
| 5 | `tools/impacted_tests.py` | which test files a change can affect (`--why FILE` explains one) | ANY |
| 6 | `tools/build_runner.py` | the only build entry: `--mode github --run --select standard media_center ...`; `--smoke-test` validates routing | LEAD (GH) |
| 7 | `tools/github_remote_build.py` | the remote contract behind it (`run --target ...`); workflow steps `manifest`, `stage-native` | LEAD (GH) |
| 8 | `tools/d1_run.py` | the real saver on one named display, bounded, frames and logs back; `--hidden` for agents | LEAD (visible), ANY (`--hidden`) |
| 9 | `tools/visualizer_live_check.py` | live-shape check of a Visualizer mode, invisible windows, recorded music; the default `--load none` is safe | ANY (default), LEAD (`--load game60`) |
| 10 | `tools/run_matrix.py` | declarative matrix of bounded RUN sessions over the product's `--exit-after` | LEAD |
| 11 | `tools/release_media.py` | showcase WebPs for transitions and Visualizer modes into `assets/webp/` (judge a new effect by looking) | ANY |
| 12 | `tools/overhead_baseline.py` | cost of every transition and mode before/after a shared change (`--compare`) | ANY |
| 13 | `tools/transition_contact_sheet.py` | deterministic transition frames through the production GL host (`--effect`, `--animate`) | ANY (not `--quick-smoke`) |
| 14 | `tools/visualizer_replay/record.py` | record real music as a replay clip (`record NAME --seconds 60`; GUI: `tools/music_recorder.py`) | OP (needs music playing) |
| 15 | `tools/visualizer_replay/owner_worker_gate.py`, `live_engine_gate.py`, `owner_render_parity.py` | native core identity gates: the engine worker against in process (frames, session, drawn pixels) | ANY |
| 16 | `tools/compute_pass_identity.py` | bit-for-bit before/after of the scene3d compute passes (`record`, `compare`, `paired`) | ANY |
| 17 | `tools/conventions_identity.py` | bit-identity of every transition and mode across a conventions change (`record`, `compare`, `pairs`) | ANY |
| 18 | `tools/vulkan_shader_readiness.py` | does every shader compile with `qsb` for every backend (`--out`) | ANY |
| 19 | `native/spike_p1/python/run_n06.py`, `import_check.py` | native module drivers: Vulkan device ownership rounds; GPU-free import and Qt-binding check | ANY (module from `release\native_module\`) |
| 20 | `tools/frame_trace_report.py`, `frame_trace_cadence.py` | read a `--frame-trace` binary (handoff median/p95, late overlap, presentation cadence) | ANY |

## 1. Workflow and evidence plumbing

| Path | What it does and how to run it | Who | Out | Tests / docs |
|---|---|---|---|---|
| `tools/artifact_paths.py` | The one owner of every path a tool writes. `PY tools/artifact_paths.py areas` (declared areas, mode ids with product names); `prune-scratch [--apply] [--max-age-h 24]` (dry run by default; reports, never deletes, PNG frame sequences, WebPs over 10 MB and `profile/` folders). API: `evidence_dir`, `evidence_arg`, `webp_arg`, `checked_output`, `repository_root`, `default_evidence`. | ANY; `--apply` LEAD | the layout itself | `test_artifact_paths_contract.py` (lists every unrouted writer with its reason); Harness_Index §0 |
| `tools/evidence_media.py` | Publishes owner scratch to the evidence folder unchanged on success; `animated_webp` (24 fps, < 10 MB); `redirect_output`, `finish`. | LIB | layout | `test_evidence_media.py` |
| `tools/agent_handover.py` | State of every agent worktree (branch, commits ahead, uncommitted files, journal, running processes). `PY tools/agent_handover.py [worktree ...]`; `--commit` saves uncommitted work as a "WIP (handover)" commit; `--retire` copies the named worktrees' evidence into the main checkout, then removes them. Never pushes, merges or stops anything. | LEAD | commits / `.artifacts` of main | Orchestrator_Handbook §5-6; Agent_Worktree_Rules |
| `tools/naming_reference.py` | Generates `Docs/Reference/Naming.md` (every product name and its persisted id). `--check` (default, exit 1 if stale) or `--write`. | ANY | `Docs/Reference/Naming.md` | `test_naming_reference.py` |
| `tests/run_chunked.py` | The maintained test runner. `PY tests/run_chunked.py [targets] [--chunks 4] [--profile NAME] [--isolated [--jobs N] [--changed [--base HEAD]]] [--timeout-seconds 900] [--log] [--no-preflight] [-v] [--extra ...]`. `--profile` cannot combine with targets; `--changed` needs `--isolated`. | ANY (focused files), LEAD (`--isolated` at milestones) | `logs/` with `--log` | Docs/TestSuite.md; Harness_Index §1 |
| `tools/impacted_tests.py` | Which test files a change can affect (import graph). `PY tools/impacted_tests.py [files ...] [--base HEAD] [--why TESTFILE] [--lazy-hops 1]`. Feeds `run_chunked --changed`. | ANY | stdout | `test_visualizer_expansion_capability.py`; TestSuite |
| `tools/music_recorder.py` | GUI (Qt) for a friendly 60-second system-loopback clip (`PY tools/music_recorder.py`; also GODZIP Foundry, FOUNDRIES, TOOLS). Shares `RecorderSession` with `visualizer_replay/record.py`. | OP (needs audio, opens a window) | `logs/visualizer_recordings/` (the operator's music, local) | `test_music_recorder.py`; Harness_Index §1 |

## 2. Build (builds run only through GitHub workflows)

| Path | What it does and how to run it | Who | Out | Tests / docs |
|---|---|---|---|---|
| `tools/build_runner.py` | The Build Foundry (tkinter GUI, stdlib only) for Normal, Repo Venv and GitHub Remote builds. `PY tools/build_runner.py [--mode normal\|venv\|github] [--smoke-test] [--run [--select JOB ...]] [--iscc PATH] [--debug]`. `--run` is headless and needs `--mode github`; job keys `standard media_center reddit_helper standard_installer media_center_installer linux linux_mc native_module`. `--smoke-test` prints a JSON routing/fingerprint check and opens nothing. A local Normal/Venv build is operator-only; agents never build. | LEAD (`--mode github`), OP (local modes) | `release/`, `logs/` build logs | `test_build_runner.py` and 17 more; Docs/Guides/GitHub_Remote_Build.md |
| `tools/github_remote_build.py` | The GitHub Remote contract: `run --target standard\|media_center\|native_module [--branch B]` (target repeatable; builds on GitHub runners, downloads, validates, publishes into `release/`); workflow-side `manifest --target T --commit C --token X --out F [--run-id --run-attempt]` and `stage-native --build-dir D [--target native_module]`. Run by the lead from a pushed commit. | LEAD | `release/<payload>/` | `test_github_remote_build.py`, `test_native_module_build.py`; GitHub_Remote_Build.md |
| `tools/build_evidence.py` | Portable operator-build evidence bundle; never invokes a compiler. | LIB (operator) | bundle folder | `test_build_evidence.py` |
| `tools/frozen_build_audit.py` | Frozen module audit and deterministic source provenance. `PY tools/frozen_build_audit.py fingerprint\|verify\|compare [--root P] [--receipt P] [--report P] [--expected H] [--artifact P]`. Build-side; called from the build workers. | LEAD / GH | receipt/report paths given | `test_frozen_build_audit.py` |
| `tools/regen_qrc.py` | Regenerates the binary Qt resource packs (`ui/resources/assets.rcc`, `onboarding_assets.rcc`) with one PySide toolchain. `PY tools/regen_qrc.py [--python P] [--qrc MANIFEST --output RCC] [--check]` (`--check` fails when regeneration is needed). | ANY (`--check`); the `.rcc` are git-ignored and copied into a worktree | `ui/resources/*.rcc` | `test_qrc_regeneration.py` |
| `tools/build_layout.ps1` | The frozen build's layout and QML import allowlist (owned here; dot-sourced by the build workers). | LIB | none | `test_build_layout.py`, `test_build_layout_qt_version_fence.py` |
| `tools/qml_import_contract.py` | The allowlist above, readable from Python so a test fails on an unreviewed QML import before a release build does. | LIB | none | `test_build_layout.py` |
| `tools/check_qml_source_contract.py` | Headless build preflight for duplicate direct QML property assignments. `PY tools/check_qml_source_contract.py` (exit code). | ANY | stdout | called by the build workers |
| `tools/nuitka_worker_qt_plugin.py` | Nuitka user plugin: importing PySide6 loads no Qt GUI module in a compiled worker process. | LIB (build) | none | `test_nuitka_worker_qt_plugin.py`, `test_frozen_build_audit.py` |
| `tools/native_sdk_fetch.py` | Fetches the pinned Qt SDK (qtbase + qtdeclarative) and Vulkan-Headers for the native module, sha256-checked. `--prefix DIR \| --print-qt-version` (one required), `[--keep-downloads]`. Downloads: the workflow runs it; never run it on this machine. | GH | SDK prefix outside the repository | `test_native_sdk_fetch.py`; GitHub_Remote_Build.md ("The native module") |
| `tools/python314_probe.py` | Fail-fast Windows runtime/ABI probe for the Python 3.14 cutover. `PY tools/python314_probe.py`. | ANY | stdout | `test_python314_migration_contract.py`; Docs/Guides/Python314_Cutover.md |
| `scripts/venv/build_nuitka.ps1` | Canonical standard (screensaver) Nuitka worker: `[-EntryPoint main.py] [-AppName SRPSS] [-Console] [-KeepExe] [-ReinstallVenvDeps] [-PrepareEnvironmentOnly] [-BuildTarget screensaver] [-DistributionName screensaver] [-LogStem build_nuitka] [-BuildWorkspace normal\|venv] [-OnefileCacheName onefile] [-ProductNameOverride S] [-DescriptionOverride S] [-DiagnosticArtifactName SRPSS_Diagnostic]`. Called by the runner and the workflow. | GH | `release/`, `logs/*_report_*.xml`, `*_footprint_*.json` | `test_build_layout.py`, `test_build_closeout_contract.py` |
| `scripts/venv/build_nuitka_mc_onedir.ps1` | Canonical Media Center one-dir worker: `[-EntryPoint main_mc.py] [-AppName SRPSS_Media_Center] [-Console] [-ReinstallVenvDeps] [-BuildWorkspace normal\|venv]`. | GH | as above | as above |
| `scripts/venv/build_reddit_helper.ps1` | Reddit helper worker: `[-EntryPoint helpers/reddit_helper_worker.py] [-AppName SRPSS_RedditHelper] [-Console] [-ReinstallVenvDeps]`; output `release/reddit_helper/SRPSS_RedditHelper.exe`. | GH | `release/reddit_helper/` | `test_build_runner.py`, `test_reddit_helper_task_harness.py` |
| `scripts/build_nuitka.ps1`, `scripts/build_nuitka_mc_onedir.ps1`, `scripts/build_reddit_helper.ps1` | Compatibility entry points that forward to the `scripts/venv/` workers with `-BuildWorkspace normal` (same parameters). Do not reintroduce global-Python builds. | OP | as the workers | `test_build_closeout_contract.py` |
| `scripts/build_qtquick_smoke.ps1` | Builds (and with `-Run` runs) the bounded Phase A render-node smoke: `[-Run] [-Windows 1\|2] [-PhaseDelayMs 400]`; output `build/a4_qtquick_smoke/` (ignored). A local compile and a window: operator-only. | OP | `build/a4_qtquick_smoke/` | `test_qtquick_build_packaging.py` |
| `scripts/SRPSS_Installer.iss`, `scripts/SRPSS_MediaCenter_Installer.iss` | The canonical Inno Setup installers, compiled locally by the runner from the downloaded payloads (`--iscc` points at `ISCC.exe`). | LEAD | `release/` installers | `test_installer_contract.py`, `test_build_closeout_contract.py` |
| `scripts/reddit_helper_task_template.xml` | The Task Scheduler XML template the Reddit helper task is rendered from. | LIB | none | `test_reddit_helper_task_harness.py` |

## 3. Real-saver runs (the product itself, bounded)

All of these start `main.py` / `main_mc.py` from source. An agent runs them only invisibly (`--hidden`, or
`visualizer_live_check` with its default empty-region windows) and never with a load.

| Path | What it does and how to run it | Who | Out | Tests / docs |
|---|---|---|---|---|
| `tools/d1_run.py` | The saver on ONE named display, bounded, with grabbed frames, logs and the frame trace. `PY tools/d1_run.py --list-displays`; `--display N` (D1 = 1) `[--allow-primary: never]` `[--seconds 30, max 600] [--entry mc\|main] [--profile DIR] [--mode ID] [--preset N] [--viz-set K=V...] [--setting DOTTED.KEY=JSON...] [--clip PATH\|none] [--clip-start S] [--diag NAME...] [--updates] [--app-arg=TOKEN...] [--step AT:KIND:ARG...] [--crop NAME...] [--item OBJ] [--crop-size 32] [--zoom 4] [--hidden] [--with-hidden-display N] [--startup-grace 90] [--teardown-grace 45] [--out DIR] [--label L]`. `--help` prints the ready recipes. Steps: `grab:LABEL`, `screen:LABEL` (refused with `--hidden`), `key:NAME`, `move\|click\|rclick\|dblclick:X,Y` or `:@objectName`. Fail-closed: exit 2 refused, 3 failed run, 4 watchdog, 5 a visible window on another monitor. | LEAD (visible), ANY (`--hidden`) | layout `display/d1_run` | `test_d1_run.py`, `test_only_display_cli.py`; Harness_Index "Display 1 run harness" |
| `tools/visualizer_live_check.py` | Live-shape check of a Visualizer mode: the real MC saver, windows with an empty region (no pixel, no click), recorded music as loopback, optional game-like load; reports the age chain, usage cost, hitches/min, process tree. `PY tools/visualizer_live_check.py --mode ID [--preset N] [--set K=V...] [--seconds 120] [--load none\|game60 (default none since 12 Nov)] [--visible] [--clip PATH\|none] [--clip-start S] [--out DIR] [--label L] [--display-off AT:FOR,...] [--settings-roundtrip AT,...] [--roundtrip-memory census,collect,tracemalloc,map] [--mode-switch AT,...] [--app-arg=TOKEN...] [--resource-readings [--settle 5]]`. **An agent must pass `--load none`**: the default starts the game60 load, which is lead-only. `--visible` takes a display: LEAD only. Exits 3 on a shown dialog, a failed switch or an early exit, 4 on resource growth. | ANY with `--load none`; LEAD for `game60` | layout `visualizers/<mode>/live_check` | `test_visualizer_live_check.py`, `test_live_check_resources.py`, `test_live_check_settings_roundtrip.py`; Visualizer_Change_Checklist 1C |
| `tools/live_check_mode_switch.py`, `live_check_settings_roundtrip.py` | The mode-switch and Settings-round-trip drivers `visualizer_live_check` runs inside the saver. | LIB | json beside the run | `test_live_check_settings_roundtrip.py` |
| `tools/live_check_resources.py` | External resource readings (handles, threads, RSS, mappings, growth verdict) for `--resource-readings`; read from outside the saver. | LIB | `resource_*.json` | `test_live_check_resources.py` |
| `tools/run_matrix.py` | Sequential matrix of bounded RUN sessions. `PY tools/run_matrix.py --matrix FILE.json --output-dir NEW_DIR`. JSON: `schema_version 1`, 1-100 `cases` each `name`, optional `entrypoint`, `argv` with `/s` once plus admitted diagnostic flags, `exit_after_seconds` (max 3600). Snapshots logs after each child; exit non-zero for failed or unavailable evidence. No external timeout: `--exit-after` is the only bounded shutdown. | LEAD | the dedicated output dir (must be new) | `test_run_matrix_harness.py`; Harness_Index §1B |
| `tools/eb_live_phases.py` | The real MC saver with tool-only timers on Extruded Bubble's render stages and logical publish; medians/p90/p99 and drift-solver restarts at exit. `PY tools/eb_live_phases.py --out FILE -- <main_mc args incl --log-dir=SCRATCH>`. Real windows and real load: operator-visible. | LEAD | `--out` | `test_visualizer_live_check.py`; Harness_Index §12 |

## 4. Performance, load and attribution

Judge GPU cost relative to the Crossfade control, record system usage beside every figure, and compare against
`tools/baselines/overhead/` (see [Benchmarks.md](Benchmarks.md)). Offscreen timings never close operator
heavy-load acceptance.

| Path | What it does and how to run it | Who | Out | Tests / docs |
|---|---|---|---|---|
| `tools/overhead_baseline.py` | Every showcase transition and Visualizer mode offscreen, round-robin against a Crossfade control. `PY tools/overhead_baseline.py [--size 1920x1080 (use 2560x1440)] [--frames 48] [--passes 3] [--max-rounds 12] [--only transitions\|visualizers\|surfaces\|node_path] [--match TEXT] [--compare OLD.json] [--compare-only OLD NEW]`. A full run writes `tools/baselines/overhead/<date>_<commit>.json` (commit it when it is the reference); `--match` writes `<date>_<commit>_<match>.json`. | ANY | `tools/baselines/overhead/` | Benchmarks.md; `test_transition_lifecycle_contract.py` companion |
| `tools/baselines/overhead/*.json` | Stored baselines (data, 22 files, 2026-10-10 to 2026-11-11, including `_backdrop` and `_node-path` variants). Read-only reference for `--compare`. | data | | Benchmarks.md |
| `tools/bench_stability.py` | `PairedBench`, `BenchCase`, `LoadGate`, `ThreadCpuClock`, `SystemSampler`: the measurement machinery that keeps timings trustworthy on a busy machine. | LIB | none | `test_bench_stability.py` |
| `tools/visualizer_cost_probe.py` | One mode's render cost offscreen through the production host. `PY tools/visualizer_cost_probe.py MODE [key=value ...] [--size 2560x1440] [--frames 48] [--passes 3] [--calls]` (`--calls` adds GL and Python calls per frame, the load-proof signal). | ANY | stdout | Benchmarks.md |
| `tools/eb_gpu_stage_cost.py` | Extruded Bubble GPU cost per render stage by skip variants (whole-frame `GL_TIME_ELAPSED`, round-robin). `--clip PATH [--preset 1] [--size 1662x888] [--frames 60] [--rounds 3] [--throughput] [--compare K=V] [--wall]` (`--wall` is for use under the load generator: lead). | ANY (LEAD with `--wall` under load) | stdout | Extruded_Bubble/Investigation.md |
| `tools/waveform_gpu_stage_cost.py` | Waveform GPU cost per render stage by skip variants. `--clip PATH [--preset 2] [--size 3875x1450] [--start 20] [--frames 30] [--rounds 3] [--extra 4] [--whole] [--set K=JSON...] [--json FILE]`. | ANY | `--json` | Harness_Index (none) |
| `tools/eb_logical_cost_probe.py` | Extruded Bubble's logical tick CPU cost by phase from a real recording; no window, no GL. `--clip PATH [--preset 1] [--set K=JSON...] [--start 0] [--duration 30] [--alloc] [--profile N] [--json FILE]`. | ANY | `--json` | Performance_Optimization_Contract.md |
| `tools/studio_drag_profile.py` | Cost of each mouse move and each frame of one slider drag in a hidden Studio. `[--mode waveform_ribbon] [--key PROPERTY_ID] [--frames 30] [--moves-per-frame 4] [--json FILE]`. | ANY | `--json` | `test_waveform_studio_replay_budget.py`; Visualizer_Studio.md |
| `tools/spectrum_studio_replay_budget.py` | GUI-thread cost of Spectrum Studio exact replays frame by frame. `[--budget 0.008] [--out FILE]`. | ANY | `--out` | `test_spectrum_studio_replay_budget.py` |
| `tools/gpu_load_generator.py` | **LEAD only, after the operator's yes, at most 10 minutes, end-of-chain worst case, never a baseline.** Game-like competing load in its own processes. `--seconds S --profile game60\|game85 [--fps F] [--gpu PCT] [--cpu PCT] [--passes N] [--buffer-mb 64] [--compute-per-copy N] [--priority normal\|above\|high]` (legacy `--busy`, `--packet-ms`). Prints `ready` when calibrated. Check for stray instances before any idle measurement. | LEAD | stdout | Harness_Index §12; Agent_Worktree_Rules |
| `tools/perf_measure.py` | Read-only resource sampler of an SRPSS process. `--pid N \| --launch` (one required) `[--duration 30] [--interval 0.5] [--startup-wait 4] [--output FILE]`. `--launch` starts a real saver: LEAD. | ANY (`--pid` of a hidden run), LEAD (`--launch`) | `--output` | `test_tooling_ownership.py` |
| `tools/frame_trace_report.py` | Summarises the binary `--frame-trace` (publication/draw timing, handoff median/p95, `late_overlapping_handoff`). `PY tools/frame_trace_report.py TRACE [--timeline-seconds S]`. | ANY | stdout | `test_frame_trace.py`; Performance_Optimization_Contract.md |
| `tools/frame_trace_cadence.py` | Visualizer presentation cadence from the same trace: per-second publications/draws, publish/swap gap frequency, stall classes. `TRACE [--seconds] [--publish-gap-ms 16] [--swap-gap-ms 25] [--refresh SCREEN=HZ...]`. | ANY | stdout | Harness_Index §1B |
| `tools/image_change_perf_parser.py` | Image-change admission, cache, GC and HUD telemetry from `screensaver_perf.log`. `LOG ...`. | ANY | stdout | `test_runtime_perf_policy_contracts.py` |
| `tools/image_worker_shm_lifecycle_harness.py` | ImageWorker shared-memory lifecycle and parent-handoff evidence. `[--cycles 50] [--width 3840] [--height 2160] [--warmup-cycles 10] [--timeout-ms 15000] [--output-dir DIR] [--source IMG] [--resample-filter F] [--sharpen] [--prefetch \| --parent-baseline] [--no-shutdown-transfer]`. | ANY | layout `performance/image_worker_shm` | `test_tooling_ownership.py`; Image_Quality.md |
| `tools/qsg_render_timing_report.py` | Qt Quick scenegraph timing from `screensaver_qml.log`. `QML_LOG`. | ANY | stdout | `test_qsg_render_timing_report.py` |
| `tools/memory_slope_report.py` | Warm-plateau slopes of private commit, USS, RSS, handles, cache bytes and VRAM, and per-replacement steps, from `--usage` logs. `LOG_DIR [--warmup-minutes 20] [--settle-minutes 1]`. | ANY | stdout | Harness_Index §10; R-97 |
| `tools/win_memory_map.py` | VMMap-style native memory map of a running process, read from outside. `snapshot [--pid N] [--out FILE]`; `diff A B [--top 30]`; `capture [--pid N] [--wait] --at MIN... [--out-dir DIR] [--trace SECONDS]`. Compare at the same display count and warm-up. | ANY (hidden run) / LEAD | layout `memory` | Harness_Index §10 |
| `tools/scheduler_trace_capture.py` | Bounded external WPR scheduler capture while SRPSS is in a stable heavy state (R-87). `capture [--duration-s S] [--profile P] [--out-dir D] [--label D1_heavy] [--srpss-log-dir D] [--filemode] [--keep-etl]`. Needs an elevated Windows trace and a heavy live saver: LEAD, with the operator. | LEAD | out-dir | `test_scheduler_trace_capture.py` |
| `tools/scheduler_trace_reduce.py` | Reduces one WPR ETL to a tiny attribution report. `CAPTURE_DIR --srpss-log-dir DIR [--render-tid N] [--output-json F] [--output-text F] [--delete-etl]`. | LEAD | outputs | Harness_Index (none) |
| `tools/visualizer_switch_abc_harness.py` | A/B/C causal oracle for Visualizer switches (R-80 window-local event-loop). Subcommands `contention [--workers 4] [--seconds 400]`, `score --log LOG [--out F]`, `classify --a F... --b F... --c F... [--out F]`, `auto --condition A\|B\|C --log LOG [--run-cmd CMD] [--layout-slot 1] [--workers 4] [--contention-seconds 600] [--deadline-seconds 1200] [--out F] [--rep-out F]`. `contention` and `auto` start CPU contention and the real app: LEAD. | LEAD (`contention`, `auto`); ANY (`score`, `classify`) | `--out` | `test_visualizer_switch_abc_harness.py`; Harness_Index §1B |
| `tools/qtquick_visualizer_switch_smoke.py` | Real-GL repeated mode-switch lifecycle smoke for the inline Quick host (opens a window). `[--cycles 5] [--hold-seconds 2] [--deadline-seconds 60] [--sequence a,b,...]`. | OP | stdout | R-80; Harness_Index §1B |
| `tools/gc_gen2_attribution_harness.py`, `tools/viz_logical_gil_contention_harness.py` | Headless GC and GIL-contention attribution for the closed P0 Visualizer hitch. No flags. See also Candidates to retire. | ANY | stdout | Native_Core_P2_Audit.md |
| `tools/SRPSS_R80_ABC_Runner_GUI_v2.py` | The corrected R-80 ABC oracle runner (GUI). See Candidates to retire. | OP | | Harness_Index §13 |

## 5. Native core (engine worker, shaders, native module)

All of these draw or run through the production owners offscreen or in unshown runtimes and never show a window or
open a device. The hidden host (`tools/expanded_visualizer_evidence.py: HiddenDisplayHost`) needs
`rendering.quick.bootstrap.configure_quick_graphics` before the application and refuses to start otherwise.

| Path | What it does and how to run it | Who | Out | Tests / docs |
|---|---|---|---|---|
| `tools/compute_pass_identity.py` | Each scene3d compute pass through its real owner on fixed inputs in a hidden GL context: outputs, GL calls, GPU time, texture memory. `record --out DIR [--passes a,b,...]`; `compare BEFORE AFTER` (bit for bit, prints memory changes); `paired --out DIR [--ref REV=HEAD] [--passes ...] [--rounds 41]` (the revision's owners alternated with the working tree's in one process). | ANY | layout | Scene3D_Resources.md; Current_Plan N1.2/N1.7 |
| `tools/conventions_identity.py` | N1.4's bit-identity proof: every transition and Visualizer mode drawn through its production renderer. `record --out DIR [--part transitions\|modes\|all] [--only IDS...]`; `compare BEFORE AFTER`; `pairs --out DIR [--ref REV=HEAD]` (each changed fragment source at the revision against the working tree, with the conventions flip as sensitivity control). | ANY | layout | `test_conventions_include.py` |
| `tools/vulkan_shader_readiness.py` | Discovers every shader source the product renders with, bakes each with `qsb` for every shipped target, reports pass/fail and causes (N1.3 census). `--out DIR`. | ANY | layout | `test_vulkan_shader_readiness.py` (ratchet in N5's order) |
| `tools/visualizer_replay/owner_worker_gate.py` | The production owner on the engine worker: identity, real-time and cost gates. `--out DIR [--modes M...] [--seconds 5.5] [--realtime 3] [--cost 3] [--skip-identity] [--skip-realtime] [--skip-cost]`. | ANY | layout | 15 tests (`test_visualizer_display_move_retarget.py`, `test_framed_view_*`); Native_Core_P2_Engine_Design.md |
| `tools/visualizer_replay/live_engine_gate.py` | P2b gates on the live-engine rig: the session in process equals the session in the worker. `--out DIR [--seconds 60] [--modes M...] [--clips C...] [--scenarios steady pause_warm pause_cold reentry switch] [--order production] [--stress] [--paced] [--paced-seconds 3]`. | ANY | layout | 13 tests; same design doc |
| `tools/visualizer_replay/owner_render_parity.py` | Drawn pixels of both paths at non-default settings, mirrored into the production `DisplayScene.qml` in a hidden texture. `--out DIR [--modes ...] [--variants a b] [--sampling single product] [--seconds 5.5] [--skip-controls]`; `single` is exact and judged. | ANY | layout `native_core` | `test_visualizer_owner_render_parity.py` |
| `tools/visualizer_replay/engine_worker_gate.py` | Identity gate of the engine worker against the in-process tick on the operator's recordings. `--out DIR [--seconds 30] [--recording STEM...]`. | ANY | layout | Native_Core_P2_Engine_Design.md |
| `tools/visualizer_replay/owner_production_replay.py` | The owner's own configure-and-start path replayed over a shipped clip. `--out DIR [--root DIR] [--modes ...] [--seconds 1.5]`. | ANY | `--out` | `test_visualizer_owner_production_path.py` |
| `tools/visualizer_replay/engine_main_cost.py` | The in-process tick's and DSP's cost per tick per mode (P2b decision record). `--out DIR [--seconds 20] [--modes ...]`. | ANY | layout | Native_Core_P2_Audit.md |
| `tools/visualizer_replay/live_engine_cost.py` | What P2b removes from the main process, measured on the live engine. `--out DIR [--seconds 20] [--modes ...] [--sections live take gil]`. | ANY (it measures; no load) | layout | same |
| `tools/visualizer_replay/engine_read_audit.py` | Which beat-engine attributes the logical tick reads, per mode (the live-input surface). Module, no CLI. | ANY | stdout | same |
| `tools/visualizer_replay/live_audio.py` | `recorded_pcm` and `RecordedLoopback`: a recording's native PCM played into the worker's capture callback in real time, never a device. | LIB | none | gates above |
| `native/spike_p1/python/run_n06.py` | N0.6 driver: the module owns the Vulkan instance and device. `--module-dir DIR [--round facts\|device\|lifecycle\|owners\|translucent (=facts)] [--label n06] [--cycles 10] [--long-cycles 40] [--force-no-second-queue]`. Uses an invisible Quick window; module from `release\native_module\`. | ANY | layout `native_core/n06` | Native_Core_P3_Decisions.md |
| `native/spike_p1/python/n06_windows.py` | Helpers for it: the invisible window and the Win32 reads that need no pixel. | LIB | none | |
| `native/spike_p1/python/import_check.py` | GPU-free check that the module imports into the venv's PySide6 and binds to that Qt. `--module-dir DIR --expect-qt X.Y.Z [--without-quick] [--json FILE]`. Also the workflow's check. | ANY / GH | `--json` | `test_native_module_build.py` |
| `native/spike_p1/python/run_spike.py` | P1 toolchain spike driver. `--module-dir DIR [--part all\|rhi\|gil\|hybrid\|quick] [--backend d3d11\|d3d12\|vulkan\|opengl] [--label spike]`. `quick` and the backends open GPU contexts; judge before running. | ANY (offscreen parts) | layout `architecture/native_core_p1` | Native_Core_P1_Spike.md; GitHub_Remote_Build.md |
| `native/spike_p1/python/frozen_probe.py` | Entry point of the operator's Nuitka probe of the spike. `--out DIR --part rhi\|hybrid\|quick [--backend d3d11]`. Compiled builds are GitHub-only. | OP | `--out` | |
| `native/spike_p1/build.cmd`, `CMakeLists.txt`, `cmake/`, `src/`, `shaders/`, `README.md` | The C++ module's sources and the workflow's one CMake invocation. Never built locally; `native-module.yml` builds it (`tools/build_runner.py --mode github --run --select native_module`). | GH | `release/native_module/` | native/spike_p1/README.md |

## 6. Visualizer modes

Production never imports these; real recorded music is the input (`logs/visualizer_recordings/`, the operator's
local clips: `balanced`, `heavy1`, `quiet_intro`, `quiet_intro2` are the canonical corpus; shipped Studio clips
live in `assets/production/studio_clips`). Pixels are evidence, not listening acceptance. Capture folders must be
new. `-m tools.visualizer_replay.X` means `PY -m tools.visualizer_replay.X`. Method and traps:
`Docs/Guides/Visualizer_Reactivity_Authoring.md`, `Docs/Guides/Visualizer_Visual_Tuning.md`,
`Docs/Guides/Visualizer_Change_Checklist.md`, [Visualizer_Reference.md](Visualizer_Reference.md).

### 6.1 Replay core, recording and generic audits

| Path | What it does and how to run it | Who | Out | Tests / docs |
|---|---|---|---|---|
| `tools/visualizer_replay/__init__.py`, `driver.py`, `engine.py`, `metrics.py`, `floors.py` | The deterministic offline replay: `driver` (replay through the logical and Quick snapshot owners, `MODES = spectrum oscilloscope bubble devcurve`, real-scale `sphere shockwave_grid`), `engine` (immutable fixture at the BeatEngine post-DSP seam), `metrics` (presenter-independent metrics), `floors` (reviewed lower bounds; calibration never runs inside assertions). | LIB | none | 332 tests import the package; TestSuite §7 |
| `tools/visualizer_replay/__main__.py` | The replay CLI: `-m tools.visualizer_replay [--candidate NEW.json] [--report NEW.html]` (both refuse to overwrite). | ANY | `--report` in layout | `test_visualizer_replay.py` |
| `tools/visualizer_replay/record.py` | Records live loopback into a schema 2 clip with no window. `-m tools.visualizer_replay.record NAME [--seconds 60]` (play music first; names normalise to snake_case, existing and `_vN`/`_noevents` names refused). | OP | `logs/visualizer_recordings/` | Harness_Index §1; `Docs/Reference/Visualizer_Reference.md` |
| `tools/visualizer_replay/mode_audit.py` | Reactivity audit (level, motion, ceiling/zero occupancy) on recorded music. `-m ...mode_audit [--modes M...] [--save FILE] [--compare SAVED]`; modes `spectrum oscilloscope devcurve shockwave_grid bubble`. | ANY | `--save` | TestSuite |
| `tools/visualizer_replay/analysis_controls_audit.py` | Which Audio Analysis controls change a mode's published frame. `[--modes ...] [--clips growing_pains human] [--seconds S] [--only SUFFIX...] [--out DIR] [--list]`. | ANY | `--out` | `test_audio_analysis_controls.py` |
| `tools/visualizer_replay/cadence_parity.py` | Behaviour at other logical cadences. `[--modes bubble ...] [--clips ...]`. See Candidates. | ANY | stdout | |
| `tools/visualizer_replay/pcm_reanalysis.py` | `reanalyzed_bubble_bands()`: the one seam that recomputes body-band DSP from recorded native PCM (used by `--reanalyze-pcm`). | LIB | none | 6 tests |
| `tools/visualizer_replay/capture_time_strip.py` | Side-by-side time strip from capture MP4s. `--ffmpeg EXE --output PNG [--start 0] [--step 0.25] [--count 8] [--width 640] RUN_DIR...`. | ANY | `--output` | Reactivity_Authoring.md |
| `tools/freeze_visualizer_settings.py` | Freezes resolved Visualizer settings as test fixtures. `[MODE ...] [--output FILE]`. A deliberate fixture change. | ANY | `tests/` fixture | `_visualizer_frozen_settings.py` |

### 6.2 Per mode

| Path | What it does and how to run it | Who | Out | Tests / docs |
|---|---|---|---|---|
| `tools/neon_lake_capture.py` | Neon Lake (`shockwave_grid`) art through the production GL host, no settings writes. `[--output P] [--size 1300x750] [--dpr 1] [--window WxH] [--set K=JSON...] [--preset 1] [--event AGE,X,Z,STRENGTH...] [--suite] [--clip PATH [--start 0] [--duration 8] [--fps 12] [--resize SIZES] [--resize-smooth] [--gif] [--rgb-roi x0,y0,x1,y1] [--all-frames]]`. | ANY | layout `visualizers/shockwave_grid/capture` | `test_neon_terrain_growth.py`; Neon_Lake_Basin.md |
| `tools/visualizer_replay/neon_lake_music_response.py` | The song's envelope against what the lake, island and shore do. Subcommands `music --clips C --out F`; `response --clips C --out F [--preset 1] [--size 722x1086] [--fps 15] [--start 0] [--duration S] [--set K=JSON...] [--continuous]`; `report --music F --response NAME=PATH.npy... --out F`. | ANY | `--out` | `test_neon_lake_music_response_chain.py` |
| `tools/extruded_bubble_capture.py` | Extruded Bubble through the production GL host from a real clip. `--clip PATH [--output DIR] [--size 1300x750] [--window WxH] [--start 0] [--duration 4] [--fps 6] [--set K=JSON...] [--gif] [--passes] [--preset 1]`. `--passes` times each draw by program (read shares, not totals). | ANY | layout `visualizers/extruded_bubble/capture` | `test_extruded_bubble_tiny_temporal.py`; Extruded_Bubble/Target.md |
| `tools/extruded_bubble_source_audit.py` | Read-only EB source/geometry diagnostic with documented negative findings; not an acceptance test. `[--output FILE]`. See Candidates. | ANY | `--output` | TestSuite 1774, 1787 |
| `tools/visualizer_replay/extruded_bubble_forensics.py` | Bounded, tool-only production replay observation and paired GPU interventions. `--clip PATH --output DIR [--preset 1] [--start 0] [--duration 60] [--size 1672x941] [--set K=JSON...] [--capture] [--probe-controls] [--reanalyze-pcm] [--passes] [--gif] [--fps 6]`. Without `--capture` no GL. | ANY | layout | `test_extruded_bubble_recorded_reactivity.py`; Harness_Index §6 |
| `tools/visualizer_replay/bubble_response_comparison.py` | Paired real-input, same-window 2D Bubble / EB response custody. `--clip PATH --output DIR [--duration 12] [--eb-preset 1] [--bubble-preset 1] [--size 1672x941] [--window START,STOP...] [--reanalyze-pcm] [--set K=JSON...]`. | ANY | layout | same test; Reactivity_Authoring §13A |
| `tools/visualizer_replay/bubble_breathing_continuity.py`, `bubble_breathing_overlay.py` | Per-identity breathing from that comparison: `DIR [--min-seconds 2] [--report FILE]`; `DIR --window START,STOP --output PNG [--ids 4]`. | ANY | layout | Reactivity_Authoring.md |
| `tools/visualizer_replay/bubble_reference_capture.py` | The accepted original Bubble as a real-recording response comparator. `--clip PATH --output DIR [--duration 12] [--fps 12] [--size 1672x941] [--preset 1]`. | ANY | layout | EB Investigation |
| `tools/visualizer_replay/extruded_bubble_coverage_probe.py`, `extruded_bubble_ray_probe.py`, `extruded_bubble_held_bands.py`, `extruded_bubble_world_probe.py` | EB probes, each run as `-m`: coverage `--output DIR`; ray `--clip PATH --output DIR [--preset 1] [--at 3] [--size 1672x941]`; held bands `--output FILE [--simulation-ref COMMIT]`; world `--clip PATH --output DIR [--preset 1] [--at 4] [--size 1672x941]`. Fresh output directories. | ANY | layout | `test_extruded_bubble_world_probe_camera.py`; Harness_Index §6 |
| `tools/visualizer_replay/extruded_bubble_log_inventory.py` | Reads log ZIPs without extracting; EB-only receipts. `--directory DIR --output FILE`. | ANY | layout | EB Investigation |
| `tools/visualizer_replay/extruded_bubble_projection_gate_probe.py`, `extruded_bubble_range_energy_audit.py` | Qt-free EB camera/near-layer discontinuity probe on the authored presets; quiet/loud Range audit. Each `[--json]`. | ANY | stdout | `test_tool_preset_identity.py`, `test_extruded_bubble_range_energy_audit.py` |
| `tools/visualizer_replay/extruded_bubble_traces.py` | EB reactive signals on real recordings as a PNG of traces. `-m ...extruded_bubble_traces OUT_DIR [CLIP ...]` (positional; defaults to two shipped clips). | ANY | `OUT_DIR` in layout | TestSuite |
| `tools/visualizer_replay/eb_chain_population_probe.py` | Free-chain population per logical tick, blinks per chain. Positional `[CLIP=anything_mixed2] [PRESET=1] [SECONDS=40] [OUT_DIR]`. | ANY | layout `visualizers/extruded_bubble/chain_population` | EB Investigation |
| `tools/visualizer_replay/eb_collision_probe.py`, `eb_control_audit.py`, `eb_screen_stats.py` | EB collisions on real music (`[CLIP=human_heavy1] [--preset 1]`); does each reactive control's authored range reach what is shown (`[CLIP ...] [--preset N...] [--realized] [--keys K...]`); on-screen bubbles per size (`[--preset N...] [--at S...] [--clip C] [--size 1672x941] [--set K=V...]`). | ANY | stdout | Visual_Tuning.md |
| `tools/visualizer_replay/eb_simulation_support.py` | Qt-free EB simulation and synthetic startup fixtures for tests and audits. | LIB | none | 18 tests |
| `tools/visualizer_replay/eb_shaft_mesa_compile.py` | Optional Linux Mesa/EGL shaft shader link gate, no Qt. See Linux. | ANY (Linux) | stdout | EB Investigation |
| `tools/labs/extruded_bubble_lab.py`, `extruded_bubble_references.py` | See Labs. | | | |
| `tools/visualizer_replay/bubble_judder.py` | Bubble radius judder on recorded music or fixtures. `[--px-per-unit 300] [--min-px 0.5] [--tiny-max-px 8] [--frozen] [--fixtures] [--clip NAME...] [--compare-release] [--report FILE]`. | ANY | `--report` | `test_bubble_render_judder.py`; Bubble_Temporal_Fidelity.md |
| `tools/visualizer_replay/bubble_fidelity.py` | Identity-preserving Bubble observations and frame-aligned A/B evidence. | LIB | none | `test_bubble_fidelity_report.py` |
| `tools/visualizer_replay/bubble_parity.py` | Save/compare full original-Bubble replay outputs. `--output DIR [--recordings DIR] [--compare DIR] [--gpu]`. | ANY | layout | `test_bubble_parity_capture.py` |
| `tools/visualizer_replay/bubble_particle_glow.py` | Light profiles, flicker metric, paired GPU cost. Subcommands `profile [--at S...]`, `flicker [--start 20] [--seconds 3] [--fps 45] [--steady .01] [--strip-frames 18] [--crop x y w h]`, `shimmer`, `perf [--frames 24] [--passes 3] [--max-rounds 8] [--extent-list canonical tv]`, `frames`, `packets`; common `--out-dir DIR [--prefix glow] [--clip balanced] [--recordings DIR] [--preset 0] [--extent canonical\|tv\|WxH] [--set K=JSON...] [--variant production\|aliased] [--radius 16]`. | ANY | `--out-dir` | `test_bubble_ambient_*`; Bubble_Temporal_Fidelity.md |
| `tools/visualizer_replay/bubble_shape_invariance.py`, `bubble_shape_strip.py` | Does a card's shape change Bubble's perceived speed/size/density (`[--clip NAME] [--fixture] [--recordings DIR] [--seconds 30] [--preset N...] [--report FILE]`); offscreen GL strips on several shapes (`--out-dir DIR [--clip balanced] [--preset 0] [--start 8] [--step-frames 9] [--rows 8] [--prefix P]`). | ANY | layout | R-170; TestSuite §7 |
| `tools/qtquick_sphere_smoke.py` | Bounded real Quick Sphere capture and callback-cost proof (opens a window). `[--output PNG] [--material All\|Chrome\|Obsidian\|Magma\|Silver\|Water] [--width 1440] [--height 800] [--extent-width 420] [--extent-height 280] [--scale 1.2] [--frames 80] [--checkerboard] [--preset-settings] [--bass .65] [--mid .75] [--high .35] [--transient 0]`. | OP | layout `visualizers/sphere/materials` | Sphere_Visualizer.md |
| `tools/visualizer_replay/sphere_ramp.py` | Sphere reaction rate and size per passage-intensity band on recorded clips. `[--preset N...]`. | ANY | stdout | `test_visualizer_replay_real_scale.py`; Sphere_Visualizer.md |
| `tools/visualizer_replay/sphere_golden.py` | The S19 Sphere promotion golden. `[--write] [--visual] [--write-visual]` (`--write*` only for an intended, documented change; writes `tests/goldens`). | ANY | layout `visualizers/sphere/golden_review`; goldens | `test_sphere_promotion_golden.py` |
| `tools/visualizer_replay/devcurve_capture.py` | Recorded music through Spline Curve's (`devcurve`) logical path and the Quick host, offscreen. `--clip PATH --output DIR [--preset 1] [--start 20] [--duration 4] [--fps 45] [--size 960x360] [--label run] [--strip-every 3] [--strip-width 480] [--strip-columns 2] [--png-all] [--canonical] [--set K=JSON...]`. | ANY | layout | Harness_Index §6 |
| `tools/visualizer_replay/devcurve_reactivity_audit.py`, `devcurve_continuous_kicks.py` | Drive distributions and space-time maps (`--clip PATH... --output DIR [--preset 1] [--seconds S] [--recorded-bands] [--map-start S] [--map-seconds 20] [--label run]`); kicks in continuous play (`--clip PATH... --preset 1 --output DIR [--label run]`, repeat a clip to pair identical kicks). | ANY | layout | Reactivity_Authoring.md |
| `tools/waveform_ribbon_capture.py` | Recorded native PCM through the production Waveform mode and retained GL host, no settings writes. `--clip PATH [--output DIR] [--preset 1] [--start 20] [--duration 4] [--fps 12] [--size 820x718] [--ffmpeg EXE] [--edge-viewport] [--viewports WxH,...] [--set K=JSON...] [--png-all]`. Presets are displayed 1-based. | ANY | layout | 4 tests; Waveform_Ribbon_Migration_Plan.md |
| `tools/waveform_fidelity_frames.py` | Before/after fidelity frames. `capture --clip PATH --preset N --out DIR [--size 3875x1450] [--start 20] [--frames 12] [--fps 45]`; `compare BEFORE AFTER --out DIR`. | ANY | `--out` | Native_Core_P2_Engine_Design.md |
| `tools/visualizer_replay/waveform_music_response.py` | The song's envelope against what the ribbon does. `music --clips C --out F`; `response --root DIR --inputs PATH --out F [--presets 1,4,7] [--mode M] [--direction D] [--breathing X]`; `report --music F --response NAME=PATH.npy... --out F`. | ANY | `--out` | Reactivity_Authoring.md |
| `tools/visualizer_replay/waveform_ribbon_breathing_probe.py` | Reaction over whole songs in continuous play. `record --clip PATH... --output DIR`; `analyse INPUT... --output DIR [--presets 1,...,7] [--traces] [--view]`; `recorded INPUT... --output DIR`. | ANY | layout | Waveform_Ribbon_Migration_Plan.md |
| `tools/visualizer_replay/waveform_ribbon_motion_audit.py` | Recorded PCM to realised geometry against a same-clip idle control. `--clip PATH --output DIR [--preset 1\|2\|3 (=3)] [--start 5] [--seconds 40] [--span 18] [--set K=JSON...] [--trace]`. | ANY | layout | Harness_Index §6 |
| `tools/visualizer_replay/waveform_ribbon_signal_audit.py` | Native-PCM floor A/B and pooled raw/music statistics. `--clips PATH... --output DIR [--seconds 60] [--preset 1\|2\|3] [--block 128\|256\|441\|512\|1024 (=256)] [--mode-output]`. | ANY | layout | Waveform_Ribbon_Migration_Plan.md |
| `tools/visualizer_replay/waveform_ribbon_tail_probe.py` | Tail stagger of the published cloth at fixed scene x. `[--presets 1,...,7] [--legacy]` (`--legacy` is the negative control). | ANY | stdout | `test_waveform_tail_continuity.py` |
| `tools/spectrum_decor_evidence.py` | Spectrum customization evidence: pixel identity, showcase renders, GPU cost. Subcommands `baseline PATH`, `compare PATH`, `showcase PATH [--only TEXT]`, `presets PATH [--clip human] [--scale 1]`, `cost [PATH]`. | ANY | `PATH` in layout | `test_qtquick_visualizer_spectrum.py` |
| `tools/qtquick_visualizer_clip_smoke.py` | Focused real-GL proof for the inline clip and mode ports (opens a window). `--policy rounded\|rect\|nested\|spectrum\|oscilloscope\|bubble\|devcurve [--visualizer-case canonical\|scaled\|wide\|tall\|idle\|ghost\|trail\|pop\|shadow\|specular]`. | OP | stdout JSON | `test_qtquick_visualizer_clip_smoke.py` |

### 6.3 Studios, clips and presets

| Path | What it does and how to run it | Who | Out | Tests / docs |
|---|---|---|---|---|
| `tools/waveform_studio_capture.py` | Hidden capture of a real mode Studio shell rendering the production scene (no window, in-memory store, nothing saved). `[--output DIR] [--mode waveform_ribbon] [--preset 3] [--size 1600x900] [--fixture peak] [--time 5] [--clip ID] [--source-time S] [--compare PNG] [--framing ID] [--theme SRTHEME] [--transparent] [--tag S] [--set K=JSON...] [--card-extent live\|WxH] [--border PX] [--workspaces a,b] [--object ID] [--expand a,b\|all] [--pick-node N] [--scroll PX] [--dock-open] [--help-open] [--preset-menu] [--viewport-expanded] [--brush MODE_ID [--brush-mode Raise\|Lower\|Flatten\|Water] [--brush-strength 0..1] [--brush-radius R]]`. | ANY | layout `studio/waveform_capture` | `test_studio_tooltip.py`; Visualizer_Studio.md |
| `tools/studio_shape_capture.py` | The Studio's shape instrument in its states (real mouse events, hidden). `[--output DIR] [--mode spectrum] [--theme SRTHEME] [--dpr 1] [--size 1600x900] [--preset 1] [--states rest,hover,drag,selected,strength,add_hint] [--whole rest,drag] [--set K=JSON...] [--tag S]`. | ANY | layout `studio/shape_instrument` | `test_studio_shape_instrument.py` |
| `tools/build_studio_clips.py` | Builds the Studios' shipped audio clips (`assets/production/studio_clips`) from native recordings. `[--recordings DIR] [--check]` (`--check` rebuilds in memory, fails on a committed difference). | ANY (`--check`) | `assets/production/studio_clips` | `test_studio_shipped_clips.py` |
| `tools/studio_clip_loop.py` | Seamless loop points, seam baking and measuring for the shipped clips. | LIB | none | `test_studio_clip_loop.py` |
| `tools/studio_clip_loop_report.py`, `studio_clip_loop_wrap.py`, `studio_clip_length_cost.py` | Measured seam (`[--out DIR] [--before-rev REV]`); the picture at a clip's wrap per Studio (`[--clip growing_pains] [--family F...] [--out DIR]`); what clip length costs (`[--recordings DIR] [--seconds 30] [--out DIR]`). | ANY | `--out` | Visualizer_Studio.md "Studio clips" |
| `tools/visualizer_preset_author.py` | Writes a curated preset from Settings values alone. `--mode ID --values SCENES.json --scene NAME --index N --title S [--description S]`. Authored content: writes one preset file the lead asked for; no tool lists presets. | LEAD / ANY when briefed | `presets/visualizer_modes/` | `test_visualizer_preset_author.py` |
| `tools/visualizer_preset_repair.py` | Interactive preset repair (GODZIP Foundry, TOOLS) and batch modes. `[--repair-all [--mode ID...]] [--audit-curated] [--reindex-curated]` (no flag = interactive GUI). | OP (GUI); ANY (batch) | `presets/visualizer_modes/` | 11 tests; Visualizer_Preset_Repair.md |
| `tools/regenerate_visualizer_shipped_presets.py` | Validates or regenerates the repo-local shipped preset artifacts. `[--check \| --dry-run]` (both read-only). | ANY | `--check` none | `test_visualizer_preset_tree.py` |

## 7. Transitions

| Path | What it does and how to run it | Who | Out | Tests / docs |
|---|---|---|---|---|
| `tools/transition_contact_sheet.py` | Deterministic transition frames through the production GL host. `[--effect glass_shatter] [--width 960] [--height 540] [--direction D] [--seed 713] [--source IMG] [--destination IMG] [--animate] [--quick-smoke [--windows 1\|2 (=2)]] [--output-dir DIR]`. `--animate` writes a 60-frame two-second WebP. `--quick-smoke` opens real windows: operator-visible. Render on personal wallpapers; keep seen candidates. | ANY (not `--quick-smoke`) | layout `transitions/<effect>/contact_sheet` | 71 tests import it; Transitions.md |
| `tools/qtquick_blinds_smoke.py` | Real-GL wrapper of the Quick Blinds smoke. `--direction horizontal\|vertical\|diagonal [--windows 1\|2] [--output DIR]`. `--windows 2` only for intentional multi-display evidence. Opens a window. | OP | layout | Harness_Index §2 |
| `tools/qtquick_phase_c_effect_smoke.py` | Parameterised Phase C effects (Ripple, Crumble, Particle, Burn). `--effect E [--case C] [--windows 1\|2] [--output DIR]`; use the source's exact case names. Opens a window. | OP | layout | `test_qtquick_phase_c_effect_smoke.py` |
| `tools/qtquick_render_node_smoke.py` | Production-shaped threaded Qt Quick lifecycle smoke. `[--windows 2] [--generations 1] [--hide-show-cycles 0] [--exit-via-input] [--topology-recreate] [--size WxH] [--phase-delay-ms 350] [--transition-id crossfade] [--transition-direction D] [--slide-motion-style Linear\|Elastic\|Wobble\|Flex\|Perspective Push] [--output DIR]`. Opens windows; the tests drive it. | OP (tests: ANY) | layout | 6 tests; Transitions.md |
| `tools/gl_object_ledger.py` | Live GL object names per kind (textures, buffers, VAOs, FBOs, renderbuffers, queries, programs, shaders, syncs): a leak and first-frame-allocation detector. Importable; no CLI. | LIB | none | `test_transition_lifecycle_contract.py` |
| `tools/release_media.py` | Registry-derived showcase WebPs through production offscreen owners (README and release media). `PY tools/release_media.py --list`; `[--output-dir DIR] [--kind transition\|visualizer] [--id ID] [--variant V] [--clip PATH] [--start-seconds 0] [--duration-seconds S] [--capture-width 1280] [--width 960] [--fps 30] [--max-bytes N]` (10 MiB ceiling for Visualizers). One showcase per new or reworked effect; review it yourself. | ANY | `assets/webp/trans`, `assets/webp/viz` (product assets, not evidence) | `test_release_media.py`; [Release_Media.md](Release_Media.md) |
| `tools/overhead_baseline.py`, `tools/conventions_identity.py` | Transition cost and identity: see sections 4 and 5. | | | |

## 8. Evidence and capture (widgets, surfaces, Guided Setup, product assets)

Hidden-host captures render real pixels with no window (offscreen QPA, `QT_QPA_FONTDIR=C:/Windows/Fonts`, or the
hidden product host that calls the product's Quick graphics configuration). Anything that opens one real Quick
window is operator-only (probes never show visible windows).

| Path | What it does and how to run it | Who | Out | Tests / docs |
|---|---|---|---|---|
| `tools/expanded_visualizer_evidence.py` | Expanded Visualizer evidence: digests, the ordinary round trip, display-wide renders; owns `HiddenDisplayHost` (24 tests import it). `[--output DIR] [--webp FILE] [--seconds 12] [--digests-only]` (`--digests-only` runs on a tree without the M2 route). | ANY | layout + webp | Expanded_Visualizer plan; Native_Core_P2 docs |
| `tools/now_playing_edit_sheet.py` | Now Playing in Fullscreen Edit beside the Media card's own Edit: resize-gesture sheets and `geometry.json`, hidden host. `--output DIR [--label before\|after]`. | ANY | layout `visualizers/shared/expanded_now_playing` | Expanded Visualizer plan 1C.3 |
| `tools/card_surface_capture.py` | Every card on a surface material, one at a time, on the production scene, never on screen. `[--label run] [--output DIR] [--wallpaper IMG] [--theme NAME] [--materials normal glass] [--visualizer-materials normal glass acrylic] [--only WIDGET...] [--fill-variants] [--sheet A B] [--media-controls DPR...]`. The default wallpaper is a path on the operator's machine. | ANY | layout `widgets/card_surfaces` | `test_card_surface_panels.py`; Card_Surface_Materials.md |
| `tools/surface_material_capture.py` | Card surface materials on the production display scene. `[--wallpapers IMG...] [--output DIR] [--sheets] [--smoke] [--cadence] [--cost] [--legibility] [--legibility-themes NAME...] [--theme-sheet NAME...] [--style [--themes A B]] [--dpr 1] [--card-set main\|lists] [--compare-legibility BEFORE AFTER]`. | ANY | layout `widgets/surface_material` | 6 tests; Card_Surface_Materials.md |
| `tools/ordinary_widget_resize_capture.py` | Fixed retained-card pixels and geometry before/after normalisation. `-m tools.ordinary_widget_resize_capture [--output DIR] [--families abandonment_issues achievement_pulse weather] [--compare BEFORE AFTER [--max-channel-delta 0]]`. Captures for `--compare` stay lossless PNG in owner scratch. | ANY | layout `widgets/resize_capture` | `test_ordinary_widget_resize_capture.py`; [Ordinary_Widget_Resize_Capture.md](../Guides/Ordinary_Widget_Resize_Capture.md) |
| `tools/ordinary_widget_stack_capture.py` | Fixed-snapshot packing review (reuse the resize harness). `-m ...ordinary_widget_stack_capture [--output DIR]`. | ANY | layout `widgets/stack_capture` | same guide |
| `tools/qtquick_abandonment_issues_smoke.py`, `qtquick_achievement_pulse_smoke.py`, `qtquick_clock_smoke.py`, `qtquick_gmail_smoke.py`, `qtquick_media_smoke.py`, `qtquick_reddit_smoke.py`, `qtquick_weather_smoke.py`, `qtquick_friend_system_stats_smoke.py` | Render that widget's retained states through ONE real Quick window (inert fixtures; Friend Pulse/System Stats never contact Steam or start the sampler; Reddit uses fixtures only). Each `[--output-dir DIR]`. Visible window: operator-only. See Candidates (superseded in part by the hidden captures above). | OP | layout `widgets/<name>_smoke` | none; Harness_Index §13, §8.5 |
| `tools/settings_native_corners.py` | The real Windows Settings or Studio HWND over controlled light/dark native backgrounds. `--label L --material glass\|acrylic\|mica\|frosted\|smoked\|off [--window settings\|studio] [--theme T \| --dark-theme T --light-theme T] [--dark-background IMG] [--light-background IMG] [--text-evidence] [--background-pole both\|dark\|light] [--page sources\|themes\|accessibility] [--extra-border-device-px PX...] [--border-growth centre\|outward] [--region-before-accent] [--qt-scale-factor F] [--studio-mode ID]`. Shows a real window. | OP | layout `settings` | `test_settings_native_corner_analysis.py`; Settings_Theme_Architecture.md |
| `tools/onboarding_preview_foundry.py` | Builds the deterministic Guided Setup preview assets without showing a window. `[--output DIR (ui/assets/onboarding/source)] [--gl-worker] [--widgets-only [--family F...]] [--assemble-manifest]` (internal `--widgets-worker`, `--audit-log`, `--guard-probe`). Writes product assets; MSAA jitter is accepted; keep same-picture files, no manual restore before `--assemble-manifest`. | LEAD | `ui/assets/onboarding/source` (product assets, then `regen_qrc`) | 21 tests; Guided_Setup.md |
| `tools/onboarding_sheet_previews.py` | Cuts Guided Setup widget previews out of an operator screenshot sheet. `[--sheet PNG (tools/onboarding_sources/MEGASHEET.png, git-ignored, operator-supplied)] [--output DIR] [--no-manifest]`. | LEAD | `ui/assets/onboarding/source` | `test_artifact_paths_contract.py`; Guided_Setup.md |
| `tools/visualizer_capture_core.py`, `tools/visualizer_capture_studio.py` | Operator GUI (`PY tools/visualizer_capture_studio.py`) over `release_media.py`; the core orchestrates it. Output `assets/temp`. | OP (GUI) | `assets/temp` | `test_artifact_paths_contract.py` |
| `tools/convert_svg_to_png.py` | SVG to transparent PNG with Qt. `SOURCE_DIR [--output DIR] [--size 64] [--keep-svg]`. Writes product icon assets. | ANY | `--output` (product assets) | |
| `tools/convert_weather_svgs.py`, `tools/download_weather_icons.py` | One-off weather-icon convert/fetch helpers (no flags). `download_weather_icons` uses the network. See Candidates. | OP | weather icon assets | |
| `tools/srpss_border_studio.py`, `tools/srpss_border_core.py` | Border Studio: drag-and-drop GUI that converts images to frame-preserving animated WebP borders. `PY tools/srpss_border_studio.py [FILE ...]`; the core is the converter. | OP | beside the inputs / chosen folder | `test_artifact_paths_contract.py` |

## 9. Themes, settings and foundries

| Path | What it does and how to run it | Who | Out | Tests / docs |
|---|---|---|---|---|
| `tools/theme_foundry.py`, `theme_foundry_model.py` | Schema-v6 semantic Settings theme editor and its pure model. `PY tools/theme_foundry.py [--repo DIR] [--open THEME.srtheme] [--validate THEME.srtheme] [--dump-schema]` (`--validate` and `--dump-schema` print and exit, no GUI). | ANY (`--validate`, `--dump-schema`); OP (GUI) | `themes/` | `test_theme_foundry_model.py` |
| `tools/widget_theme_foundry.py`, `widget_theme_foundry_model.py` | Schema-v3 `.srwtheme` editor and its Qt-free model. `[THEME.srwtheme] [--repo DIR]`. | OP (GUI) | `themes/widgets/` | `test_widget_theme_foundry.py` |
| `tools/theme_sorter_foundry.py`, `theme_sorter_model.py` | Theme Sorter: Settings/Widget theme inspection and pair operations. `[--repo DIR] [--themes-dir DIR]`. | OP (GUI) | `themes/` | `test_theme_sorter_model.py`; [Theme_Sorter_Foundry.md](../Guides/Theme_Sorter_Foundry.md) |
| `tools/generate_widget_theme_mirrors.py` | Mirrored `.srwtheme` files from the curated Settings theme pack. No flag: changes nothing, prints the regeneration plan. `--fill-materials` (each linked mirror's `surface_material` only); `--drop-retired-roles` (retired colour roles from every Widget theme only); `--regenerate-all` (refuses while it would overwrite a hand-authored mirror or delete another `.srwtheme`) with `--overwrite-authored` and `--delete-unlinked` naming those intents. Edits authored content: LEAD. | LEAD | `themes/widgets/` | 7 tests incl. `test_widget_theme_mirror_generator_safety.py` |
| `tools/theme_legibility.py` | Every text role of a theme pair against what it is composed over, on its material. `[--themes-root DIR] [--themes NAME...] [--light] [--card-materials] [--json FILE]`. | ANY | `--json` | `test_theme_material_legibility_contract.py` |
| `tools/foundry_chrome.py`, `tools/godzip_foundry_theme.py`, `tools/godzip_themes/` | Shared frameless chrome and appearance picker for the standalone Foundry tools; the Settings-theme bridge; the frozen ThemeSpec snapshot (55 `.srtheme` files, read by `build_runner.py` and the Foundries; deliberately a snapshot, not the product's `themes/`). | LIB / data | none | `test_surface_opacity_adjust.py` |
| `tools/godzip_foundry.py`, `godzip_foundry_core.py`, `godzip_logzip_retention.py`, `godzip_script_runner.py` | GODZIP Foundry: Git-aware manifest ZIP create/apply/debris review, DIFF tab (`generate_local_diff`, `generate_godzip_diff` in the core), CMD tab, LOGZIP retention. `PY tools/godzip_foundry.py [--repo DIR] [--open ZIP]` (the former `--diff-*` flags no longer exist). Foundries tab launches Music Clip Recorder and Visualizer Preset Repair. | OP (GUI); the core is importable | GODZIP archives; `.deleteme` for explicit debris moves | `test_godzip_foundry_core.py`, `test_godzip_foundry_script_runner.py` |
| `tools/default_settings_editor.py`, `tools/defaults_foundry_core.py` | GUI for the canonical Normal and MC defaults and its transaction helpers. `PY tools/default_settings_editor.py [--smoke-test]` (`--smoke-test` builds the offscreen UI, validates discovery and tooltips, exits). | ANY (`--smoke-test`); OP (GUI, writes defaults) | the defaults owner | `test_default_settings_editor.py`, `test_defaults_projection.py`; [Defaults_Guide.md](../Guides/Defaults_Guide.md) |
| `tools/check_defaults_authority.py` | Fail-fast audit of canonical defaults ownership. `PY tools/check_defaults_authority.py`. | ANY | stdout | `test_defaults_schema_authority.py` |
| `tools/settings_window_probe.py` | Records every top-level window this process creates while Settings opens (WinEvent hook; the dialog is visible). `--out FILE [--profile-settings JSON] [--opens 2] [--tabs] [--tab KEY] [--open-bucket] [--dwell-ms 1500] [--launch [--launch-s 12] [--exit-wait-s S] [--launch-script PY] [--profile-folder SRPSS]] [--self-test] [--hang-dump-s 90]`. | OP | `--out` | Harness_Index §8.3 |
| `tools/flicker_test.py` | Settings-dialog flicker reproduction and constructor-phase isolator (opens windows). `PY tools/flicker_test.py [VARIANT 1-70]`. | OP | stdout | `test_settings_dark_qss_retirement_contract.py` |
| `tools/winprobe_observer.py` | External Win32 window/foreground observer for flicker investigations. `--out FILE [--duration-s 8] [--sample-ms 5] [--include-all] [--pid N]`. | OP | `--out` | Harness_Index §13 |

## 10. Tests and static checks

| Path | What it does and how to run it | Who | Out | Tests / docs |
|---|---|---|---|---|
| `tests/run_chunked.py`, `tools/impacted_tests.py` | See section 1. | | | |
| `tools/test_durability_audit.py` | High-signal audit for accidental brittleness in the suite (read-only). `PY tools/test_durability_audit.py`. | ANY | stdout | `test_test_suite_durability.py`; Guides/Test_Durability.md |
| `tools/test_oracle_review.py` | Review-only scanner for brittle source oracles and operator-intrusive tests. `PY tools/test_oracle_review.py`. | ANY | stdout | `test_test_oracle_review.py` |
| `tools/default_pin_scan.py` | Lists test assertions that may copy today's canonical defaults. `[--summary]`. | ANY | stdout | `test_default_pin_scan.py` |
| `tools/check_ui_parity.py` | Static parity checks for Settings UI widgets. `[PATH ...=ui/tabs] [--root DIR] [--skip PATH...]`. See Candidates. | ANY | stdout | |
| `tools/pytest_qt_noenv.py` | Opt-in `QApplication` fixture: `-p tools.pytest_qt_noenv` for focused GL tests that own their storage. | LIB | none | 3 tests; TestSuite |
| `tests/studio_worker_probe.py` | Test-only helpers for Studio clip-worker lifetime: `-m tests.studio_worker_probe clip SETTINGS OUTPUT SECONDS \| parent READY_FILE [unbound] \| suspended READY_FILE [unbound]`. | LIB (tests) | `.ready` file | `test_studio_worker_lifetime.py` |
| `verify_compile.py` (repository root) | `py_compile` of three hard-coded UI files. See Candidates. | ANY | stdout | |

## 11. Linux (development and CI only; software rendering proves correctness, never performance)

| Path | What it does and how to run it | Who | Out | Tests / docs |
|---|---|---|---|---|
| `tools/linux_build.py` | Builds the Linux screensaver or MC product (Nuitka standalone folder, installer, tarball). `[--output release/linux] [--jobs N] [--dry-run] [--profile screensaver\|mc]`. On the GitHub Ubuntu runner (`linux-build.yml`); `--dry-run` prints the Nuitka command only. | GH | `release/linux/` | `test_linux_mc_build_contract.py`, `test_build_linux_declarations.py` |
| `scripts/linux/build.sh` | Shell front for it: `[--profile screensaver\|mc] [--output DIR] [--jobs N] [--dry-run]`; needs `.venv-linux` from `setup.sh --system-deps --build`. | GH | as above | Linux_Guide.md |
| `scripts/linux/build_from_windows.ps1` | Triggers the Linux workflow for a pushed branch, follows it, downloads the tarball. `[-Branch B] [-Mode Auto\|Dispatch\|Tag] [-OutDir D] [-Commit SHA] [-Profile screensaver\|mc]`; needs `gh auth login`. | LEAD | `-OutDir` | Linux_Guide.md |
| `scripts/linux/setup.sh` | Creates `.venv-linux`, installs the pinned requirements, compiles the Qt resource packs. `[--python P] [--venv DIR] [--system-deps] [--headless] [--build]`. | GH / Linux dev | `.venv-linux` | Linux_Guide.md |
| `tools/linux_headless.py` | Shared Linux headless launch environment (Xvfb start, Mesa GL 4.6 override, `require_linux`) and the profile seeding script. | LIB | none | `test_linux_mc_build_contract.py` |
| `tools/linux_pytest.py` | pytest under private Xvfb with the 4.6 Core override. `PY tools/linux_pytest.py [--display :96] [--chunked] [--] PYTEST_ARGS`; `--chunked` forwards to `tests/run_chunked.py` (`--isolated --jobs 3`). | ANY (Linux) | `logs/` | Linux_Compatibility.md |
| `tools/linux_run_headless.py` | Runs SRPSS headless on Linux (Xvfb + Mesa), captures screenshots and log findings. `[--work-dir D] [--out D] [--display :97] [--geometry 1920x1080x24] [--mode /s\|/c] [--seconds 20] [--shots S,S] [--images 8] [--synthetic-images] [--interval 5] [--keep-widgets] [--no-seed] [-- main.py args]`. | ANY (Linux) | layout `display/linux_headless` | Linux_Guide.md |
| `tools/linux_smoke_dist.py` | Smoke test of an installed frozen Linux build on isolated Xvfb (GL 4.6 Core present, scene appears, `--exit-after` exits clean, `/c` stays open). `PY tools/linux_smoke_dist.py PRODUCT_DIR`. | GH | layout `display/linux_smoke_dist` | `test_build_linux_declarations.py` |
| `tools/linux_xvfb_hotplug_churn.py` | The unmodified app on Xvfb/Mesa with RandR monitors: add and remove the second monitor, report each generation's reveal latency and memory. `[--work-dir D] [--out D] [--display :98] [--cycles 1] [--hold 15] [--gap 5] [--timeout 30] [--images 24] [--interval 5] [--entry PY] [--covered-display]`. Not Windows evidence (R-96). | ANY (Linux) | layout `display/linux_hotplug_churn` | Linux_Guide.md |
| `tools/visualizer_replay/eb_shaft_mesa_compile.py` | EB shaft shader link gate on Mesa/EGL, no Qt or OpenGL Python modules. | ANY (Linux) | stdout | EB Investigation |

## 12. Migration and one-off tools

| Path | What it does and how to run it | Who | Out | Tests / docs |
|---|---|---|---|---|
| `tools/artifact_migration.py` | One-off: moves the pre-layout flat evidence (and `logs/evidence_chest`) into the evidence layout and rewrites references. `plan [--table FILE]`, `refs`, `apply` (copies, verifies size and count, then deletes; resumable) `[--source DIR] [--chest DIR]`. | LEAD | the layout | `test_artifact_migration.py` |
| `tools/settings_migration_audit.py` | Pre-migration against current settings-defaults completeness and diff. `[--ref deleteme/PreSettings] [--json]`; the default reference tree is not in git; the test imports `resolvable_key_gaps`. | ANY | stdout | `test_settings_defaults_completeness.py` |
| `scripts/cutover_python314.ps1`, `scripts/python314_runtime.ps1` | **Destructive** CPython 3.14 cutover: deletes the repository `.venv` with no backup, reinstalls pinned dependencies, validates the ABI, optionally uninstalls 3.11 (`[-UninstallPython311]`); the runtime script is the shared base-interpreter discovery. Run only after importing the superseding full GODZIP. | OP | `.venv` | `test_python314_migration_contract.py`; Python314_Cutover.md |

## 13. Probes (one question each; operator hardware, real windows or network)

| Path | What it does and how to run it | Who | Out | Tests / docs |
|---|---|---|---|---|
| `tools/cursor_exit_native_harness.py` | Native reproduction of "the cursor keeps its changed shape after exit" (windows, real pointer). `[--path all\|esc_hand\|esc_halo\|link_hand\|click_blank\|move_blank\|stay_hand\|stay_halo] [--trials 1 (cap 20)] [--still-s 2] [--max-wait-s 120] [--verbose] [--production-flags] [--no-prime] [--qt-leave]`. | OP | stdout | `test_qtquick_exit_native_arrow.py`; Contracts.md |
| `tools/cursor_exit_observer.py` | What Windows itself shows as the cursor while the saver exits (windowless observer). `[--label run] [--out DIR] [--duration-s 600] [--interval-ms 10] [--process PREFIX...]`. | OP | layout `input/cursor_exit` | `test_cursor_exit_observer.py` |
| `tools/hardware_ingress_validator.py` | U-05 hardware ingress validation of a launched MC. `[--profile-mode isolated\|live\|mirrored] [--focus-policy strict\|realistic] [--mc-window-flags default\|splash] [--scenario focused_idle\|focused_clicked\|manual_focus\|focus_transition] [--observe-seconds 12] [--response-timeout-s 2.5] [--launch-timeout-s 45] [--output-dir D] [--no-safe-click-guards] [--no-refocus-before-observe] [--manual-focus-seconds 6]`. | OP | layout `input/hardware_ingress` | |
| `tools/media_key_reality_harness.py`, `media_key_matrix_harness.py`, `media_key_matrix_compare.py` | Media/key routing investigations for MC (U-05): observer-backed reality harness (`--scenario ...` as above); the matrix harness (`--launch mc\|run\|none [--pid N] [--no-isolate-appdata] [--focus-policy] [--scenarios a,b] [--profile-mode] [--no-safe-click-guards] [--allow-probe-without-focus] [--no-require-runtime-contract]`); and the compare runner (`[--launch mc\|run] [--profile-mode] [--policies strict,realistic] [--scenarios a,b] [--launch-timeout-s 40]`). | OP | layout `media/` | |
| `tools/gsm_tc_spotify_video_probe.py` | Standalone Spotify GSMTC live-thumbnail cadence probe. `[--seconds 15] [--poll-hz 60] [--save-frames 8]`. | OP | stdout/frames | |
| `tools/steam_followed_g0_probe.py` | Read-only Steam followed-games feasibility probe (network): `--probe \| --news-probe` (one required). Never a live-network test. | OP | stdout | `test_steam_games_followed_g0.py` |
| `tools/feed_probe.py` | Native feed probe for CUSTOM addresses and the shipped NEWS publishers (network). `[--url URL...] [--catalog] [--category C] [--json FILE]`; probe on demand only. | OP | `--json` | Feeds.md |
| `tools/system_stats_s0_probe.py` | Non-product System Stats S0 source measurement. `[--condition baseline\|cpu-ram\|gpu\|all] [--samples 5] [--interval-seconds 10] [--contention-workers 0] [--out FILE]`. `--contention-workers` spawns load: LEAD. | OP / LEAD | `--out` | System_Stats_Widget.md |
| `tools/reddit_helper_task_harness.py` | The Reddit helper's Windows Task Scheduler contract. `--action smoke-test\|render-helper-xml\|storage-recovery-test\|installed-storage-audit\|packaged-helper-smoke\|acl-fixture-test [--task-name N] [--helper-exe P] [--queue-dir D] [--log-dir D] [--signal-dir D] [--session-ticket T] [--base-dir D]`. No live Reddit; the actions touch Task Scheduler and ACLs. | OP | stdout | `test_reddit_helper_task_harness.py` |

## 14. Labs and archive (`tools/labs/`; sidecars, never imported by production)

Lab gates and plans: [Waveform_Ribbon_Lab_Plan.md](Waveform_Ribbon_Lab_Plan.md),
[Ribbon_Path.md](Ribbon_Path.md), [Bubble_Gradient.md](Bubble_Gradient.md),
`Docs/Guides/Visualizer_Labs.md`. All render offscreen: ANY.

| Path | What it does and how to run it | Out | Tests |
|---|---|---|---|
| `tools/labs/waveform_ribbon_lab.py` | Waveform Ribbon scene lab (world-first floor, waveform, distance mist). `--output DIR [--cards DIR] [--board primary\|fog] [--recipe NAME=complete]`. | layout | `test_waveform_ribbon_lab.py` |
| `tools/labs/waveform_ribbon_targets.py` | WR-00 target table for the approved board; measurement only. `--cards DIR --output DIR [--renders DIR] [--board primary\|fog]`. | layout | `test_waveform_ribbon_targets.py` |
| `tools/labs/waveform_ribbon_preflight.py` | WR-00 reference custody and projection fixtures. `--output DIR [--archive ZIP] [--fog-board PNG]`. | layout | `test_waveform_ribbon_preflight.py` |
| `tools/labs/waveform_ribbon_music_bakeoff.py` | Audio-synchronised full-reactivity comparison on recorded PCM. `--recording PATH --ffmpeg EXE [--start 20] [--seconds 20] [--output DIR] [--proof-only]`. | layout | |
| `tools/labs/waveform_ribbon_reactivity.py`, `waveform_ribbon_recorded_input.py`, `ribbon_lighting.py`, `render_target.py` | Lab-only deterministic sources and head dynamics; the adapter over the recorded-PCM authority; optical reduction of ribbon history; the shared context-owned offscreen target (`render_target`: 15 tests import it). Libraries. | none | `test_waveform_ribbon_reactivity.py`, `test_ribbon_lighting.py` |
| `tools/labs/ribbon_material_probe.py` | S3D-1 filament material cards. `--output DIR [--cards DIR] [--frames 90]`. | layout | `test_ribbon_material.py` |
| `tools/labs/ribbon_frame_probe.py`, `ribbon_path_probe.py`, `ribbon_strip_probe.py` | Early WR probes: CPU width-frame cards `[--output DIR]`; WR-01a CPU geometry `[--output DIR]`; WR-02a native oriented-strip proof and draw cost `--output DIR [--frames 90]`. See Candidates. | layout | |
| `tools/labs/extruded_bubble_lab.py` | EB composition lab (section 4A primitives per operator mock, beside the mocks). No argparse. | `Docs/Reference/Extruded_Bubble/` target paths | |
| `tools/labs/extruded_bubble_references.py` | Resolves the current EB target paths from their sole asset registry, before GL. Library. | none | `test_extruded_bubble_references.py` |
| `tools/labs/bubble_gradient_mapper_lab.py` | Two-endpoint Bubble gradient lab with the production renderer. `[--capture PNG]`. | layout | |
| `tools/baselines/`, `tools/godzip_themes/` | Data, see sections 4 and 9. `tools/onboarding_sources/` (MEGASHEET.png, Visualizers.png) is git-ignored, exists only in the main checkout and is the operator's input to `onboarding_sheet_previews.py`. | | |

## 15. Product entry points that act as tools, and runnable modules elsewhere

| Path | Use |
|---|---|
| `main.py`, `main_mc.py` | The product. RUN diagnostics: `--debug/-d --verbose/-v --perf --usage --handle-attribution --viz --geo --life --cache --steam --feeds --noupdates --set --fresh --frame-trace --gui-stall-stacks` (the last needs `--frame-trace`). Bounded runs: `--exit-after SECONDS /s` (RUN only; the product's own terminal path) and `--only-display INDEX` (one screen, numbered as the logs number them). `--log-dir=DIR` redirects logs (a CLI argument, never an environment variable). `tools/d1_run.py`, `tools/run_matrix.py` and `tools/visualizer_live_check.py` wrap these. Contracts: Harness_Index §1B, §10. |
| `main_diagnostic.py` | The dedicated Diagnostic product entry (own per-user diagnostic log root; excluded from `run_matrix`). |
| `.github/workflows/windows-build.yml`, `linux-build.yml`, `native-module.yml` | The only build paths; driven by `tools/github_remote_build.py` / `scripts/linux/build_from_windows.ps1`. |
| `.github/tests/test_linux_mc_build_contract.py` | A Linux MC build-selection test kept beside the workflows. |
| `.github/tools/linux_smoke_dist.py` | A byte-near copy of `tools/linux_smoke_dist.py` (differs by one `mkdir(parents=True)`); the workflow runs the `tools/` one. See Candidates. |
| `tests/_*.py` (`_display_manager_doubles.py`, `_gl_test_utils.py`, `_invisible_windows.py`, `_settings_context_stub.py`, `_feed_transport_cancel_probe.py`, `_network_stall_harness.py`, `_qt_exit_tripwire_probe.py`, `_msaa_render_noise.py`, `_visualizer_frozen_settings.py`, `_visualizer_presentation.py`, reference-form modules) | Test infrastructure the rules point agents at: shared doubles, the invisible-window pattern (opacity 0, transparent for input, tool window), frozen settings. Not commands. |

## Candidates to retire

Nothing is deleted without the operator's word (keep useful tools; labs that add no product overhead stay). Evidence is
what a grep of `tests/`, `Docs/` (outside the historical-bug entries and audit snapshots), `.github/` and other tools
found on 12 Nov 2026, counting an import or a path mention as a caller. "Newer" names the tool that does the job now.

| Tool | Evidence it is dead or superseded | Newer / keeper | Confidence |
|---|---|---|---|
| `verify_compile.py` (root) | Compiles three hard-coded UI files; no caller anywhere; `python -m py_compile` and the test suite cover it. | `tests/run_chunked.py` preflight collection | high |
| `.github/tools/linux_smoke_dist.py` | Copy of `tools/linux_smoke_dist.py` (193 lines each, one line differs); no workflow, test or doc runs the copy. | `tools/linux_smoke_dist.py` | high (delete the copy, keep the tool) |
| `tools/convert_weather_svgs.py`, `tools/download_weather_icons.py` | One-off weather-icon helpers; only `test_artifact_paths_contract.py` (an unrouted-writer list) and one Harness_Index line mention them; `convert_weather_svgs` repeats `convert_svg_to_png`. | `tools/convert_svg_to_png.py` | medium |
| `tools/SRPSS_R80_ABC_Runner_GUI_v2.py` | GUI front for the R-80 oracle; no test, no tool or doc caller beyond one Harness_Index line; the CLI `visualizer_switch_abc_harness.py auto/score/classify` does the same job and has a test. | `tools/visualizer_switch_abc_harness.py` | medium |
| `tools/gc_gen2_attribution_harness.py`, `tools/viz_logical_gil_contention_harness.py` | Attribution for the closed P0 Visualizer hitch; no test; the lesson is recorded (GIL-held C calls); the live check reports the GIL share and `--usage` the sampler cost. | `visualizer_live_check.py`, `--usage` | medium |
| `tools/check_ui_parity.py` | Static Settings-UI parity scan; no test, no caller, one Harness_Index line; real-dialog tests replaced stub-host checks. | tests that open the real `SettingsDialog` | medium |
| `tools/extruded_bubble_source_audit.py` | Read-only diagnostic whose violations were its documented purpose; EB is accepted; no test, only TestSuite notes. | `visualizer_replay/extruded_bubble_forensics.py` | low (documented as a diagnostic) |
| `tools/visualizer_replay/cadence_parity.py`, `eb_collision_probe.py`, `eb_chain_population_probe.py`, `extruded_bubble_coverage_probe.py`, `extruded_bubble_held_bands.py`, `extruded_bubble_traces.py` | EB/Bubble one-question probes with no test; mentioned only in Harness_Index and the EB investigation record; EB is accepted ("reused only when a concrete regression is reopened"). | `extruded_bubble_forensics.py`, `bubble_response_comparison.py` | low |
| `tools/labs/ribbon_frame_probe.py`, `ribbon_path_probe.py`, `ribbon_strip_probe.py` | Early WR-01a/WR-02a probes (CPU cards, strip proof) from before the production Waveform mode; no test; `Ribbon_Path.md` only. | `tools/waveform_ribbon_capture.py`, `tools/labs/waveform_ribbon_lab.py` | low |
| `tools/qtquick_*_smoke.py` for Abandonment, Achievement Pulse, Clock, Gmail, Media, Reddit, Weather, Friend/System Stats (8 tools) | No test; only Harness_Index lists them; each opens a real window; the hidden `card_surface_capture`, `surface_material_capture` and `ordinary_widget_resize_capture` render the same cards without one. Keep until the operator wants the retained-state sheets. | hidden captures in section 8 | low |
| `tools/hardware_ingress_validator.py`, `media_key_reality_harness.py`, `media_key_matrix_harness.py`, `media_key_matrix_compare.py` | Four overlapping U-05 harnesses (same scenarios, same flags); no test; no doc beyond Harness_Index. | one of them, chosen by the operator | low |
| `tools/artifact_migration.py` | One-off move of the pre-layout flat folders (has a test); retire once the lead confirms `plan`/`refs` report nothing left. | the layout owner | low |
| `tools/settings_migration_audit.py` | Its default reference tree `deleteme/PreSettings` is not in git; only the library function `resolvable_key_gaps` is used (by a test). | keep the function, retire the CLI | low |

## Documented usage that disagrees with the code

| Document (file:line) | Says | Code (file:line) |
|---|---|---|
| `Docs/Reference/Harness_Index.md:95` | `mode_audit` audits "Spectrum, Oscilloscope, Sine Wave, DevCurve and Shockwave Grid" | `tools/visualizer_replay/mode_audit.py:33`: `MODES = ("spectrum", "oscilloscope", "devcurve", "shockwave_grid", "bubble")` (Sine Wave is retired; Bubble is in) |
| `Docs/Reference/Harness_Index.md:864` | `agent_handover.py` offers state and `--commit` | `tools/agent_handover.py` also has `--retire` (copy the named worktrees' evidence here, then remove them; `Docs/Guides/Orchestrator_Handbook.md:51,98` uses it) |
| `Docs/Reference/Harness_Index.md:909` | `generate_widget_theme_mirrors.py` lists `--fill-materials`, `--regenerate-all`, `--overwrite-authored`, `--delete-unlinked` | `tools/generate_widget_theme_mirrors.py:496,512` also has `--drop-retired-roles` |
| `Docs/Reference/Harness_Index.md:28-29` | the area vocabulary ends at `...themes`, `tests`, `architecture` | `tools/artifact_paths.py:126-146` also declares `native_core` and `materials` (`run_n06.py:72` writes `native_core/n06`; `qtquick_sphere_smoke.py:280` writes `visualizers/sphere/materials`) |
| `Docs/Reference/Harness_Index.md:865` | `visualizer_live_check.py` "`--load game60\|none`" without saying which is the default | Fixed 12 Nov: the default was `game60` (an agent omitting the flag started the lead-only load); it is now `none`, and both docs say so |

## Counts

236 files carry a row (every `.py`, `.ps1`, `.sh`, `.iss` and `.xml` under `tools/` including `tools/labs/` and
`tools/visualizer_replay/`, `scripts/` including `scripts/linux/` and `scripts/venv/`, and `native/spike_p1/python/`),
each counted once in the section where it first appears. Data folders (`tools/baselines/overhead/` 22 JSON,
`tools/godzip_themes/` 55 `.srtheme`) and the C++ module sources are described, not counted. Libraries (LIB)
are importable helpers, not commands.

| Section | Files |
|---|---|
| 1 Workflow and evidence plumbing | 6 |
| 2 Build (tools and `scripts/`) | 21 |
| 3 Real-saver runs | 7 |
| 4 Performance, load and attribution | 24 |
| 5 Native core (incl. `native/spike_p1/python`) | 18 |
| 6 Visualizer modes, Studios, presets | 69 |
| 7 Transitions | 6 |
| 8 Evidence and capture | 23 |
| 9 Themes, settings, foundries | 20 |
| 10 Tests and static checks | 5 |
| 11 Linux | 9 |
| 12 Migration and one-off | 4 |
| 13 Probes | 11 |
| 14 Labs | 13 |
| Total | 236 |

Page generated by hand from the tools' own argparse and source, so it can drift: when a row and `--help` disagree,
`--help` wins and the row is wrong (fix it in the same commit).

