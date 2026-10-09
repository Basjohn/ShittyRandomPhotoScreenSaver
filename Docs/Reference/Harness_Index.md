# Harness Index

Compact routing for recurring regression, attribution and installed-acceptance commands.

`Docs/TestSuite.md` is the canonical live test inventory/retirement ledger. This file routes useful
commands and runtime harnesses; it is not an exhaustive manifest and does not decide whether a legacy
test still has architectural authority.

Harness success is evidence, not automatic final visual/timing/lifecycle sign-off. Run each harness in
the environment appropriate to the claim it makes; physical cadence, GPU utilization, subjective
motion feel and real multi-monitor topology require corresponding Windows/Qt/OpenGL/hardware evidence.

SRPSS does not use hosted repository CI as the normal local acceptance path unless the operator
explicitly requests it.

## 1. Targeted tests first

For retained ordinary Edit changes, the shared native painter test (`tests/test_qtquick_child_mapped_geometry.py`) covers clipped/applied transforms and repeated family-owned normalization values. Combine it with the specific family scene tests (Clock, System Stats, Friend Pulse, Weather, Achievement Pulse or Abandonment Issues) and the import-free lifetime/paint source contracts. Stable role identity and real painted bounds must both pass; a green source scan cannot certify native gesture responsiveness.

Ordinary widget pixels and resize geometry: `python -m tools.ordinary_widget_resize_capture
--output logs/widget_resize_normalization/before`. The retained long-term harness,
comparison command and evidence boundaries are documented in
[Ordinary_Widget_Resize_Capture.md](../Guides/Ordinary_Widget_Resize_Capture.md).

Offline Visualizer reactivity evidence is test/fixture-owned: `python -m pytest tests/test_visualizer_replay.py -q` exercises deterministic replay assertions against retained fixtures/goldens. The **old physical-host** Visualizer replay executable is retired; do not recreate its deleted physical host merely for convenience. This does **not** retire the active deterministic post-DSP `tools.visualizer_replay` module/CLI or `tests/test_visualizer_replay.py`; those consume independent frozen test settings and reviewed replay floors (see `Docs/TestSuite.md` §7). Use live PERF/installed evidence for scheduler/delivery/presentation questions. Real-scale input is recorded, not synthesised: `python -m tools.visualizer_replay.record NAME --seconds 60` (play music first) captures live loopback through a private, Settings-configured BeatEngine with no window and writes a schema 2 clip (`RealScaleLanes`, production units) to `logs/visualizer_recordings/` (local: it is the operator's music) plus a summary of the real ranges; `replay_clip(clip, "sphere", preset=N)` replays it. Purpose: the S19 Sphere golden and ramp retune. On those clips, `python -m tools.visualizer_replay.sphere_ramp` measures Sphere's reaction rate and size per passage-intensity band, and `python -m tools.visualizer_replay.mode_audit` audits Spectrum, Oscilloscope, Sine Wave, DevCurve and Shockwave Grid for the reactivity guide's warning signs (level, motion, ceiling/zero occupancy). Replay feeds what production would: the recorded 64 waveform samples as a full 256-sample block, and on schema 2 clips the continuous lane derived from raw bars through the replayed mode's own smoothing. Schema 1 fixtures carry no musical level, so an audible v1 frame reads as ordinary music in a full passage (`SCHEMA_1_MUSIC`). DevCurve's level is constant by design (its reaction is a zero-mean undulation around the authored contour); judge it by swing from the resting contour per layer. `python -m tools.visualizer_replay.sphere_golden` is the S19 Sphere promotion golden (behavioural replay of the curated goldens on a deterministic clip, visual captures through the production render host; `--visual` review sheets; `--write`/`--write-visual` only for intended changes); `replay_clip(..., overrides=..., snapshots_at=...)` serves Settings-model overrides and published snapshots for such captures.

The maintained real-music recorder admits frames only after its capture owner receives a valid PCM callback. An asynchronous
open failure or a recording deadline reached before the first callback raises and writes no clip; valid silent PCM remains
recordable. Capture and private ThreadManager retirement still run through the recorder's existing finalization owner.

**Canonical local real-music corpus.** The operator-authored current set is `balanced.jsonl`, `heavy1.jsonl`,
`quiet_intro.jsonl` and `quiet_intro2.jsonl` under `logs/visualizer_recordings/`. They are intentionally not normal GODZIP
payload and must not be replaced by synthetic clips when a plan/guardrail asks for real recorded music. `recorded_clips()` is
the selection authority: suffixed archived/derived takes such as `*_v1`, later `*_vN`, and `*_noevents` stay on disk for
comparison/history but are excluded from the current corpus automatically. Keep committed fixtures/goldens and these local
recordings conceptually separate: fixtures/goldens provide deterministic regression contracts; the four recordings provide
real-scale musical dynamics for reaction/judder/ramp measurement.

Bubble radius evidence uses production-object identity rather than nearest-position matching. The accepted render-release
envelope has an instant-release negative control:

```powershell
python -m tools.visualizer_replay.bubble_judder --compare-release --px-per-unit 300 --min-px 0.5 --report logs/bubble_judder_acceptance/release_recordings.json
python -m pytest tests/test_bubble_render_judder.py tests/test_bubble_fidelity_report.py -q
```

Add `--fixtures --frozen --clip broadband_noise` for committed fixture evidence. Reports retain input/settings/source
fingerprints, all/tiny-radius alternation, dot/outline crossings, paired frame-aligned extrema/excursion and bounded
input-window examples. `--px-per-unit` supplies a radius projection; the tool does not measure a display. First radius
movement during already moving music is not a causal audio-latency oracle. Physical delivery and isolated response bars remain separate.

Prefer the smallest test set that can falsify the current slice:

```powershell
pytest path\to\test_file.py -q --tb=short
```

Use `Docs/TestSuite.md` to identify current/permanent, environment-gated, obsolete and rehome test ownership.

For current destination-authority work, use the maintained profile owned by `Docs/TestSuite.md`:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

Maintained profiles isolate selected targets in fresh pytest subprocesses so queued Qt/QQuick teardown from one target cannot
poison an unrelated result. `--chunks` groups/logs those isolated targets; it is not four giant shared Qt processes.

The whole-tree wrapper is a broad **reconciliation/regression diagnostic**, not the primary product gate:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

Do not treat a red whole-tree run as proof the active slice failed until the relevant failure/log and owner classification are
inspected. A completed pytest summary followed by a process that never exits strongly suggests shutdown/lifecycle ownership and
should be isolated rather than hidden with a longer timeout.

### GODZIP Foundry operator commands

Launch `python tools\godzip_foundry.py` from the current repo environment. The DIFF tab provides **LOCAL vs GIT HEAD** (complete staged + unstaged + untracked + deleted non-ignored worktree bytes) and **GODZIP vs LOCAL**. Agents can use the same engine headlessly: `python tools\godzip_foundry.py --diff-local`, or `--diff-godzip <zip>`; add `--diff-output <path>` to write instead of stdout. These diff commands are read-only. The CMD tab's **RUN CHUNKED SUITE** button enters and runs `python tests\run_chunked.py --chunks 4 --log` in captured PowerShell. It is a broad whole-tree reconciliation run, **not** the isolated `destination` product gate above. RUN SCRIPT accepts a deliberate pasted command, while CLEAR & PASTE only replaces the editor text. Captured mode provides Stop Run, a bounded transcript and results export; external-terminal mode does not capture results or report completion. The APPLY tab refreshes discovered ZIP locations on entry without re-inspecting the currently selected archive. These buttons do not change test authority or allow output to stand in for physical validation.

Runtime product builds leave their package evidence as direct loose files under `logs/`: `<build-stem>_report_<stamp>.xml`
from Nuitka plus `<build-stem>_footprint_<stamp>.json` with current artifact/published bytes, largest files/top-level
buckets and QRC source-reference sizes. Those files are deliberately picked up by ordinary LOGZIP. Use them to answer
what the **current** build actually contains before changing Nuitka inclusion/exclusion policy.

## 1A. Qt/QML sidecar evidence

For any runtime-shaped or physical Quick/QML claim, collect and inspect both:

```text
logs/screensaver.log
logs/screensaver_qml.log
```

A successful capture eagerly creates `screensaver_qml.log` with a session marker even when Qt emits zero messages. Missing sidecar therefore means the Qt/QML evidence plane is unavailable and the run cannot prove “no QML errors.”

Focused capture validation: `pytest tests/test_qt_message_capture_contract.py tests/test_qt_message_capture_qml_runtime.py -q --tb=short`. The second test requires real PySide6/QQmlEngine.

Relevant Qt/QML warning/error lines must be correlated to the same timestamp window before calling a runtime/physical claim GREEN. Use `Docs/Guides/Qt_QML_Observability.md` for capture semantics and the raw-stderr boundary.

For FEEDS source/artwork identity investigations, add `--feeds`. This opts into the bounded `screensaver_feeds.log` sidecar; FEEDS diagnostic INFO/DEBUG does not belong in the ordinary main/verbose logs. Expected source/artwork retirement is scheduler cancellation, not a task failure, and its diagnostic WARNING is sidecar-only while the FEEDS sidecar is active. Genuine FEEDS failures remain ERROR evidence in both central logging and the FEEDS sidecar. The sidecar is event-emitted by admitted FEEDS work only and creates no diagnostic polling cadence. Contract coverage lives in `tests/test_feed_diagnostics_sidecar.py`; current Custom reflow and cross-family clickable-affordance guards live in `tests/test_feed_custom_reflow_contract.py` and `tests/test_external_link_hover_affordance.py`.

## 1B. Tooling authority

Use `Docs/Reference/Harness_Index.md` plus `Docs/TestSuite.md` before preserving an old script; absent retired tooling belongs to source history, not a recreated audit file. Production code must never import operator analysis tools (`R-72`). Built-in PERF/usage/QML telemetry is the primary application-health evidence; retain external parsers only for a narrow demonstrated cross-event question.

### Bounded self-terminating RUN sessions

For repeated startup, soak or teardown acceptance, prefer the RUN-only `--exit-after` CLI over an external process kill or window-close script:

```powershell
python main_mc.py --exit-after 15 /s
python main_mc.py --exit-after=60 /s
```

The value is seconds. The countdown is armed only after `ScreensaverEngine.start()` succeeds and immediately before the RUN Qt event loop begins. It owns one `QTimer.singleShot` callback and no recurring cadence, worker or ThreadManager task. The callback requests the existing terminal authority with `engine.stop(reason="cli_exit_after")`; Quick retirement, worker/service shutdown, persistence durability and `QApplication.quit()` therefore follow the normal product path. Without `--exit-after`, no timer/callback is created. The switch is ignored outside RUN mode. Invalid, non-finite or non-positive values fail RUN startup with exit code 2 rather than leaving an unattended test running forever.

For declarative sequential matrices over the same product-owned terminal path, use `tools/run_matrix.py`:

```powershell
python tools/run_matrix.py --matrix <matrix.json> --output-dir <new-evidence-directory>
```

The version-1 JSON document contains 1–100 `cases`. Each case has a unique `name`, an optional canonical `entrypoint`
(`main_mc.py` by default, or explicit `main.py`), an `argv` list containing `/s` exactly once plus admitted diagnostic flags,
and a positive `exit_after_seconds` value (maximum 3600). The harness appends `--exit-after` itself. Example:

```json
{
  "schema_version": 1,
  "cases": [
    {"name": "ordinary-run", "argv": ["/s"], "exit_after_seconds": 15},
    {"name": "diagnostic-run", "entrypoint": "main_mc.py", "argv": ["/s", "--debug", "--life", "--fresh"], "exit_after_seconds": 15}
  ]
}
```

Admitted optional flags are `--debug`/`-d`, `--verbose`/`-v`, `--perf`, `--usage`, `--handle-attribution`, `--viz`, `--geo`,
`--life`, `--cache`, `--steam`, `--feeds`, `--noupdates`, `--set`, `--fresh`, `--frame-trace` and `--gui-stall-stacks`; the last
requires `--frame-trace`. `--set` enables settings diagnostics. `--fresh` explicitly clears product log files at startup;
completed snapshots in evidence subdirectories remain preserved. Arbitrary values and caller-supplied `--exit-after` are rejected.

The MC wrapper sets persisted `input.interaction_mode=True` through the canonical Settings manager, making its ordinary
interactive RUN route less disruptive; explicit `main.py` exercises the ordinary screensaver entrypoint. The coordinator
itself never writes settings or supplies an environment override. `main_diagnostic.py` is excluded because it resolves a
different per-user diagnostic log root. Choose a new dedicated evidence directory, for example `logs/run_matrix/<name>`;
existing directories are refused. After each child exits, the harness snapshots canonical logs and retained rotations,
including settings diagnostics and binary frame-trace segments, before launching the next child. `run_matrix.json` and
one-line JSON on stdout record source path/hash, Git revision/status, local source-tree digest (including JSON settings/presets), exact argv, exit code,
matched fault lines and artifact paths. Attribution failures are explicit. Stdout/stderr are preserved beside each snapshot.

Cases continue sequentially after failed or unavailable cases. A nonzero child exit or current-run native-fault match marks
a case failed. Passing also requires new main RUN and AUTO_EXIT armed/deadline markers plus matching QML session start/end.
Missing markers, unreadable evidence or a run boundary lost to truncation/retention produce `unavailable`, not a pass. Fault
scanning follows the pre-run byte boundary across rotations so retained old faults do not fail a new run. The matrix exits
nonzero for failed or unavailable evidence.

Full MC runs need write access to their canonical per-user settings and cache directories as well as the repository log
directory. Use the tool's normal approval boundary when a restricted shell denies those writes. A child stalled before
RUN never reaches the product-owned countdown; preserve a deliberately interrupted investigation as failed/aborted
evidence, rather than treating it as a shutdown acceptance case. R-107 records the denied-write startup mechanism.

This coordinates the current saved RUN configuration and diagnostic CLI flags; it does not select persisted display,
Visualizer or transition settings. Physical display, mode/effect and visual acceptance still requires the relevant operator
configuration and evidence. The harness has no external timeout or kill path: `--exit-after` remains the sole bounded shutdown
mechanism.

Ten-run startup/terminal-retirement acceptance can therefore stay deliberately simple:

```powershell
$FaultPattern = "Windows fatal exception|access violation|BufferError|memoryview has 1 exported buffer"

1..10 | ForEach-Object {
    Write-Host "`n========== RUN $_ / 10 =========="
    python main_mc.py --debug --frame-trace --fresh --exit-after 15 /s

    $Code = $LASTEXITCODE
    $Fault = ((Test-Path ".\logs\native_faults.log") -and
              (Select-String ".\logs\native_faults.log" -Pattern $FaultPattern -Quiet)) -or
             ((Test-Path ".\logs\screensaver.log") -and
              (Select-String ".\logs\screensaver.log" -Pattern $FaultPattern -Quiet))

    if ($Code -ne 0 -or $Fault) {
        Write-Host "FAILED ON RUN $_ : EXIT=$Code FAULT=$Fault"
        break
    }
    Write-Host "PASS $_ / 10"
}
```

This is intentionally blocking: each child owns its own normal terminal shutdown and PowerShell advances only after that process has fully exited. Do not replace it with `Stop-Process`, parent-Python termination or broadcast `WM_CLOSE`; those bypass the runtime-destruction authority and can also terminate the GODZIP Foundry host that launched the script.

Current independent resource observation:

```powershell
python tools\perf_measure.py --pid <PID> --duration 30
```

Current ImageWorker shared-memory lifecycle proof:

```powershell
python tools\image_worker_shm_lifecycle_harness.py --cycles 50 --width 3840 --height 2160
```

For the speculative Qt source-batch isolation probe, run the same harness with `--parent-baseline` and then
`--prefetch`, each with `--cycles 50 --warmup-cycles 10` and distinct `--output-dir` paths. Both modes use the same
source at twice target size. The baseline measures the retired parent Qt work; prefetch exercises the production
supervisor callback, returns two display derivatives from one child decode, checks byte parity/retirement and reports
parent handoff plus child scale durations. It creates no QGuiApplication or per-request thread.

For a bounded selected-quality replay, use `--prefetch --resample-filter lanczos --sharpen --cycles 2
--warmup-cycles 1 --source "C:\path\photo.png" --output-dir "C:\path\diagnostic-output"`. Hamming and Smooth
use the same `--resample-filter` selector. Source files are read-only; omitting `--source` generates a temporary
fixture. The report records filter/sharpen identity, byte parity and mapping retirement. The parent-baseline lane
remains Smooth without sharpening, so its Qt timing label cannot silently describe another filter.

Use available two-display `--perf --frame-trace` logs for live P0 evidence; no minimum transition count is required.
Keep diagnostic flags with the evidence so sampler cost can be interpreted. `python tools\frame_trace_report.py logs\screensaver_frame_trace.bin` reports handoff median/p95 and
`late_overlapping_handoff` for both Visualizer render and draw intervals; absent handoff evidence is unavailable,
not a zero-overlap pass. Preserve PERF/QML/trace sidecars from the same run and count completions with
`python tools\image_change_perf_parser.py logs\screensaver_perf.log`. `Current_Plan.md` owns the acceptance status.
`python tools\frame_trace_cadence.py logs\screensaver_frame_trace.bin [--seconds]` reports Visualizer presentation
cadence from the same trace: per-second publications/draws/repeated draws by transition state, and publication/swap
gap frequency and periodicity with the logical dt, and classifies each presentation stall (Current_Plan N1). Plain
`--frame-trace` remains the low-observer binary trace. Add `--gui-stall-stacks` only when all-thread Python stacks are
needed for a steady-state GUI-wake stall; that companion is separately admitted and disarms during lifecycle windows. Its
dedicated observer thread is created/retired through the central affinity-lane threading infrastructure so the sampler remains
independent of product work queues without owning a raw ad-hoc thread or a second product cadence.


`tests/run_chunked.py` is the maintained test-runner entrypoint. Do not add a secondary test-runner facade or bypass the runner's profile-isolation policy.

### Retained Visualizer causal/lifecycle diagnostics — no active investigation

The post-switch performance investigation is closed, but two explicitly admitted diagnostics remain useful if future normal use/logs expose a persistent or traceable Visualizer issue:

```powershell
python tools\visualizer_switch_abc_harness.py auto --condition A --layout-slot 1 --workers 4 --log logs\screensaver_perf.log --out logs\abc_A.auto.json --rep-out logs\abc_A.json --run-cmd "python main_mc.py --usage --viz --perf --life"
python tools\qtquick_visualizer_switch_smoke.py
```

`visualizer_switch_abc_harness.py` uses the R-80 window-local event-loop oracle and fails old rolling-only causal logs closed. `--abc-drive` and `--viz-switch-telemetry` are explicit diagnostic admissions; the retained render-host ownership telemetry is boundary-only and allocates only when admitted. The closed P4 per-frame/per-draw presentation/fence timing hooks were removed and must not be restored without a new reproduced defect and a concrete missing fact.

These harnesses are **not scheduled work** and rapid-switch startup hitching alone is not a defect. Reopen only from future evidence that persists/grows after the triggering activity. R-80 is the permanent historical oracle/failure record.

## 2. Quick transition regression harnesses

For the expanded effects, render deterministic textured progressions through the production GL host:

```powershell
./.venv/Scripts/python.exe tools/transition_contact_sheet.py --effect glass_shatter --direction center_out --output-dir <output-directory>
./.venv/Scripts/python.exe tools/transition_contact_sheet.py --effect pixel_accretion --width 3840 --height 2160 --output-dir <output-directory>
./.venv/Scripts/python.exe tools/transition_contact_sheet.py --effect melt_drip --source <source-photo> --destination <destination-photo> --animate --output-dir <output-directory>
./.venv/Scripts/python.exe tools/transition_contact_sheet.py --effect glass_shatter --quick-smoke --windows 2 --output-dir <output-directory>
```

The tool accepts optional `--source` / `--destination` photos. `--animate` writes a 60-frame, two-second WebP progression. `--quick-smoke` reuses the existing threaded Quick harness for two generations and hide/show; inspect reported physical-screen count because a request for two windows cannot prove two-display behavior when only one screen is connected. Effect IDs and ownership are in `Docs/Reference/Transitions.md`. Offscreen timing and captures do not close operator heavy-load/freshness acceptance.

These commands are retained regression/acceptance harnesses for the current Quick transition implementations; they are not an implementation checklist.

### Blinds

```powershell
python tools\qtquick_blinds_smoke.py --direction horizontal --windows 1
python tools\qtquick_blinds_smoke.py --direction vertical   --windows 1
python tools\qtquick_blinds_smoke.py --direction diagonal   --windows 1
```

Use `--windows 2` only when physical multi-display evidence is intentionally being exercised.

### Parameterized effects

```powershell
python tools\qtquick_phase_c_effect_smoke.py --effect <effect> --case <case> --windows 1
```

Canonical case families include:

- Diffuse: rectangle, membrane, lines, diamonds, amorph, random;
- Ripple: count1, count3, count8;
- Crumble: top, bottom, random-weighted, random-choice, age-weighted;
- Particle: authored modes/directions including directional variants, swirl and converge;
- Burn: six directions plus smoke/ash toggle cases.

Use exact tool/source case names if they differ from this human-readable summary.

## 3. Transition discriminator expectations

The real-GL smokes protect parameter-sensitive transition behavior. Do not create a separate strengthening project merely because this section is detailed.

For parameter-sensitive cases hold constant, as applicable:

```text
source image
destination image
seed
logical/framebuffer size
progress
effect time
```

and vary only the parameter being tested.

Effect-specific midpoint/contrast oracles supplement exact endpoints:

- Diffuse: shape-specific spatial properties must reject a plain wipe/crossfade substitute;
- Ripple: count1/count3/count8 produce distinct radial/ring structure;
- Crumble: release weighting changes deterministic closed-prism departure, rough broken sides and parent-bound chip debris;
- Particle: direction/mode changes centroid/angular/radial structure;
- Burn: front/core/glow/char progression is distinct from a wipe; smoke/ash toggles prove their own
  regions but do not replace core-burn proof.

Do not restore retired mosaic assumptions: Crumble owns weighted parent release and polygon-seam debris, not a mosaic mode.

## 4. Transition request/uniform and GL-state tests

Direct parameter -> uniform wiring and common GL-state-fence coverage are ordinary focused pytest
regressions. They supplement rather than replace the real-GL wrappers.

The common fence includes the exception path where renderer execution raises.

See `Docs/TestSuite.md` and `Docs/Guides/Transition_Change_Checklist.md`.

## 5. Visualizer authored-fidelity evidence

The old Visualizer replay executable is retired because it imported the deleted replay physical owner. **Do not restore that host.**

Preserve authored evidence through current temporal/BTF/viewport tests plus `tests/fixtures/visualizer_replay/`, `tests/goldens/visualizer_replay/` and `tests/goldens/visualizer_temporal/`. The former replay-fixture generator is no longer in the current tree; fixture/golden data remains evidence and must not be regenerated through a resurrected replay presenter.

Do not regenerate goldens merely because implementation ownership changed. For Bubble, apply `Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

## 6. Visualizer logical-runtime permanent gates

Search current tests by contract rather than stale test names when needed:

```powershell
rg -n "VisualizerLogicalRuntime|generation 0|mode switch|Spectrum|Pause|BTF|single clock|thread affinity" tests
```

Required properties include:

- sole authored mode-general logical clock;
- every authored logical step integrated before presentation coalescing;
- latest-state semantics, no FIFO/catch-up;
- no paint acknowledgement;
- no producer/display divisor;
- no source/event decimation;
- no display-refresh logical cap;
- worker cannot mutate GUI/Quick/GPU;
- generation zero valid;
- protected renderer-visible Bubble consequences survive coalescing;
- source freshness separate from presentation;
- worker joins cleanly;
- local SDF/stencil clip composes/restores valid inherited framebuffer state;
- 1.5 default aspect / wide/tall compatibility without anisotropic distortion.

These are permanent/future-integration gates, not instructions to rerun closed architecture-selection work.

## 7. Qt Quick runtime checks

The Qt Quick presenter is accepted architecture. Use focused runtime evidence for the seam being changed rather than rerunning old architecture-selection experiments.

Focused Quick harnesses prove as relevant:

- standalone `QQuickWindow`;
- threaded scene graph;
- current-generation state delivery;
- first intentional frame;
- immutable render-boundary state;
- Settings/recreate;
- topology/binding loss;
- resource cleanup;
- exact transition/visualizer/widget contract being changed.

## 8. Capability/runtime ownership regression routing

### 8.1 Capability/ownership foundation

Focused tests already guard:

- widget family catalog and environment gating;
- canonical activation settings/helpers;
- Visualizers capability dependency on Media while retaining special runtime ownership;
- effective transition Random pool filtering and final activation/hardware admission;
- Widgets/Transitions `SETUP`, live lazy navigation and hidden-page save safety;
- runtime widget factory creation filtered by family activation;
- global-singleton Visualizer CUSTOM 30-second failover/reclaim generation/lifecycle rules.

When touching that foundation, route through current test ownership in `Docs/TestSuite.md`; common files
include:

```text
tests/test_widget_family_catalog.py
tests/test_capability_activation.py
tests/test_transition_distribution.py
tests/test_visualizer_failover_reclaim.py
```

This list is routing, not a frozen manifest. Resolve exact test functions and current existence from `tests/run_chunked.py` and the source tree before running a command.

### 8.2 Shared runtime/service ownership

Permanent owner tests cover:

- family-exclusive providers/models;
- timers/polls/refresh callbacks;
- processes/workers;
- shared-service references;
- generation/model registration;
- clean deactivation retirement/reactivation;
- fresh-process deactivated import/construction dormancy.

Treat this as current capability/dormancy architecture and do not infer full provider/process dormancy from factory-creation gating alone.

### 8.3 Settings capability UI regression

Preserve focused Settings/runtime cases for:

- Widgets/Transitions `SETUP` opening without heavy deactivated module imports;
- pills appearing/disappearing live with activation;
- selected deactivated page returning to `SETUP` immediately;
- Settings save/recreate retaining inactive detailed configuration;
- lazy hidden pages not overwriting stored values;
- transition renderer dormancy;
- Random effective-pool correctness;
- explicit zero-activated-transition state repair.

Provider/model/resource retirement assertions stay at the actual neutral owner; do not move them back into presentation tests.

### 8.4 Current broad routing

The related implementation/physical acceptance is closed. Use the current focused gates in this index and `Docs/TestSuite.md`, not old command bundles.

The maintained `destination` profile is the ordinary broad architecture regression route:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

Use smaller focused files/nodeids first for the slice being changed. The destination profile covers deterministic/runtime-shaped Quick
display/unit/family/CUSTOM/input/transition/visualizer ownership, including the stronger technical-config + real retained-item
visualizer boundary. It intentionally does **not** turn operator-hardware-dependent QScreen/topology cells into an ordinary automated
gate.

Real two-display identity/topology, A -> B -> A physical ingress, mixed refresh/DPR, off/wake and final installed
multi-display acceptance remain physical evidence. Run those cells separately/isolated when the claim requires the operator's
actual hardware.

### 8.5 Friend Pulse / System Stats retained-card evidence

Use the focused source/runtime/QML suites before the shared architecture gate. The smoke tool instantiates the production
Quick host/components and writes standard, busy and shared-40%-floor captures for Friend Pulse Grid/Rows/Strict plus
System Stats. It also captures the six-friend responsive three-column Grid. The harness uses inert fixture services and
never contacts Steam or starts the product sampler.

```powershell
python -m pytest tests/test_steam_friend_pulse.py tests/test_friend_pulse_runtime.py tests/test_qtquick_friend_pulse_presentation.py tests/test_friend_pulse_stack_predictor.py tests/test_system_stats_source.py tests/test_system_stats_runtime.py tests/test_qtquick_system_stats_presentation.py tests/test_system_stats_settings.py -q
python -m pytest tests/test_steam_links.py tests/test_secure_url_launcher.py tests/test_qtquick_family_product_actions.py -q
python tools/qtquick_friend_system_stats_smoke.py --output-dir <capture-directory>
python tools/check_defaults_authority.py
```

The preserved bounded System Stats source admission harness remains:

```powershell
python tools/system_stats_s0_probe.py --condition cpu-ram --samples 3 --interval-seconds 10
python tools/system_stats_s0_probe.py --condition cpu-ram --samples 3 --interval-seconds 10 --contention-workers 2
```

See `Docs/Reference/System_Stats_Widget.md` for the current product contract plus the preserved CPU/RAM admission and rejected GPU/VRAM evidence.


## 9. Physical evidence

When internal callbacks are insufficient, capture OS/display-boundary evidence and correlate it to
intentional active-motion windows.

Do not interpret startup/capture rows before intentional presentation as active-animation cadence holes.
Do not infer continuous displayed FPS from sparse/non-occupancy GDI `DisplayedTime` rows.
Use p95/p99/tails/severe gaps plus phase correlation when cadence evidence is actually needed.

Current display-topology/Visualizer failover must be assessed against its active Quick coordinator and `Docs/Guardrails/Visualizer_Presentation.md`, not the retired pre-Quick R-26 grace implementation. If a real off/asleep/late-return symptom recurs, collect hardware evidence instead of assuming source inspection proves physical acceptance.

## 10. Runtime diagnostics

Use only relevant existing diagnostic flag families such as:

```text
--perf
--usage
--viz
--geo
--set
--life
--cache
--steam
--feeds
```

Keep observer overhead named. Do not invent another probe family when existing evidence can answer the
question.

Memory evidence comes from the existing `--usage` (plus `--life` for generation edges) logs:
`python tools/memory_slope_report.py <log dir> --warmup-minutes 20` reports, per process and generation,
warm-plateau slopes of private commit, USS, RSS, handles, image-cache bytes and VRAM, and each replacement's
settled step. A step that repeats on equivalent rebuilds is retention; one bounded step is first use. Growth in
private commit that USS does not share is committed memory that is no longer resident (R-97).
`--handle-attribution` adds the Windows handle-type sidecar in ordinary runs. The dedicated Diagnostic product admits the same existing helper automatically at 30-second cadence so bounded frozen-runtime runs can resolve per-event handle growth without another long soak.

Which kind of memory grows is answered from outside the process: `python tools/win_memory_map.py capture --wait
--at 20 60 --trace 5` waits for the saver, takes a VMMap-style map at each minute mark (image, mapped, heap with
its owner heap, large heap blocks, thread stacks by start module, CPython arenas, other `VirtualAlloc`; commit and
resident per category) and prints the diff; `--trace` adds private commit and working set every N seconds to a
CSV. It only reads the target (no remote thread, no suspension), so it costs the saver nothing. `snapshot --pid`
and `diff a.json b.json` work on single maps. Compare maps at the same display count and warm-up.

Linux development only: `python tools/linux_xvfb_hotplug_churn.py --cycles N` runs the unmodified app on
Xvfb/Mesa with RandR monitors, adds and removes the second monitor, and reports each generation's reveal latency
and memory. A hang gets a `py-spy` dump. `--covered-display` keeps a display that is never exposed, which
exercises the stalled-sibling reveal on real Quick windows. It is not Windows evidence (R-96).

## 11. Lifecycle

Check as relevant:

- logical runtime stop/join;
- stale-state fencing;
- generation zero;
- Quick scene/window retirement;
- render-resource retirement;
- deactivated capability retirement at the current owning runtime;
- no retired callback publication;
- no background thread/process preventing test/product shutdown.

A pytest summary followed by a process that never exits should be diagnosed as ownership/lifecycle
failure rather than hidden by larger timeout values.

## 12. Historical / retired harnesses

Historical harnesses may describe QOpenGLWidget/QRhiWidget/GLCompositor paths. They remain evidence, not current architecture instructions. A surviving harness that asserts a retired physical presenter is obsolete unless `Docs/TestSuite.md` identifies a still-valid neutral behavior that must first be rehomed to the current owner.

Do not copy a historical presentation mechanism back into Qt Quick merely because its old harness is detailed.
