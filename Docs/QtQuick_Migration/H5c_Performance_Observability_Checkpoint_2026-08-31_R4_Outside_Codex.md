# H5c Performance / Observability Checkpoint — R4 Outside Codex — 2026-08-31

Outside of Codex Work Began @ `61decb33f6ebb107b2997928077e9d56d5faa8a1`

This checkpoint supersedes the R3 outside-Codex working tree for active work. R3 remains historical evidence for the viewport-scaling slice. This document records the first physical run after R3 plus the bounded source changes made before the next logs checkpoint. It does **not** claim the maintained PySide6 `h-destination` profile has been rerun.

> **SUPERSEDED CHECKPOINT / PROVENANCE ONLY.** Do not use this file as live repair or status authority. `Current_Plan.md` owns sequence; R6 native-`QCursor` Halo and R7 image/prefetch/seam work supersede the pointer/image-pipeline portions. Preserve only findings explicitly carried forward by current living docs.

## Physical evidence accepted from the post-R3 run

- [x] Bubble outline thickness is now physically good at normal, low and very large tested scales. Preserve the R3 radius-proportional outline transfer.
- [x] Bubble reactivity is broadly good enough that no prior reactivity/scaling repair is reopened from this run; global presentation stalls still muddy fine judgement.
- [x] Bubble high-vertical motion-tail/"ghost bubble" abundance is real. Telemetry does **not** show a corresponding population explosion: active bubbles remain roughly `43–49` and trail payload roughly `531–612` floats. Treat this as renderer presentation multiplication, not simulation spawning.
- [x] Spectrum is broadly recognizable/reactive across scales. Do not retune scale/reaction from this run merely because scene presentation is choppy.
- [x] Spectrum pause currently drops through zero/stale state before later entering the existing idle bars. This is a handoff defect, not evidence that the idle floor needs to be raised.
- [x] Oscilloscope can flicker during aggressive high-vertical resize.
- [x] System load was modest while the visible experience still hitched. CPU/GPU utilization alone is therefore not a sufficient falsifier for scene contention/presentation stalls.
- [x] Manual induced transitions are materially smoother than naturally timed transitions in the observed run. Treat origin (`timer` versus `manual_next`) as first-class evidence.

## Source repairs added after R3

### Bubble tail presentation and shader cost

- [x] Preserve authored Bubble/history coordinates exactly.
- [x] Compress only each rendered history sample's offset from its owning Bubble on expanded viewport axes, keeping the wake footprint under baseline-pixel authority instead of letting three history sources separate into several obvious extra bubbles at ~3x height.
- [x] Add cheap output-preserving ripple bounds before the expensive per-fragment `length` / `sin` / `exp` path. This does not reduce Bubble count/history, add a pass, add a timer or alter simulation cadence.
- [ ] **AWAITING PHYSICAL VALIDATION:** tall Bubble wake should become compact without reducing reactivity or changing Bubble population.
- [ ] Bubble Ghost remains semantically open: retained Quick still implements a static expanded halo and does not consume `bubble_ghost_decay`. Do not counterfeit temporal ghosting until the historical/product contract is decided.

### Spectrum pause identity

- [x] Capture one playback identity for the logical frame and reuse it through final frame assembly. Do not resolve bars under one `playing` state and label the outer frame with a later live reread.
- [ ] **AWAITING PHYSICAL VALIDATION:** live -> pause should enter the already-authored idle bars directly rather than briefly hit zero/stale-playing values.

### Resize coherence / Oscilloscope flicker candidate

- [x] A visualizer snapshot whose viewport geometry no longer matches the committed presentation is left unconsumed; retained Quick keeps the last coherent pixels until a matching snapshot arrives instead of clearing the visualizer to blank.
- [ ] **AWAITING PHYSICAL VALIDATION:** aggressive resize should no longer create blank/flicker frames from this mismatch seam. This does not assert all Oscilloscope high-scale flicker is solved.

## Performance evidence and instrumentation

The post-R3 logs distinguish authored cadence from presentation quality:

- authored Visualizer cadence remains approximately `89.8 Hz`;
- five observed stale/latency episodes range roughly `0.67 s` to `5.0 s`;
- repeated generation-2 GC pauses are approximately `30–43 ms`, often with zero collected objects;
- naturally timed image changes can perform display prescales around `120–230 ms` before transition admission;
- exact display-ready images were observed being warmed, evicted by deeper speculative prefetch, then re-prescaled when the natural timer later consumed them.

Changes:

- [x] `--perf` display HUD: passive `frameSwapped` aggregation of scene FPS, `dt_max`, frame-pacer target/skip percentage and active/last transition timing. No new frame/update timer.
- [x] `--perf` Visualizer HUD: Quick draw FPS, logical revision rate, snapshot age and geometry-mismatch count. Aggregated/logged at ~1 Hz.
- [x] Image-change trace: one thread-safe trace labels `timer`, `manual_next`, startup/retry and marks queue selection, transition selection, worker submission/start, per-display processing source, UI handoff and transition admission.
- [x] `tools/image_change_perf_parser.py`: source-only/read-only parser for timer-vs-manual admission, worker/cache source, GC and protected-prefetch evidence.
- [x] Exact predicted next display-ready cache keys receive advisory eviction priority over deeper speculative prefetch. Hard item/byte limits remain absolute.

## Garbage collection architecture

The old `GCController` was not instantiated in the retained Qt Quick runtime. Its pre-Quick design also assumed a Python-owned frame boundary and attempted disable/enable/manual collection around that boundary.

R4 replaces that runtime ownership with a conservative RUN-lifetime policy:

- [x] preserve the interpreter's generation-0 threshold;
- [x] make deep generation scans less frequent rather than scheduling them elsewhere;
- [x] never call `gc.collect()`;
- [x] observe/log expensive collections;
- [x] restore exact original thresholds and callback registration at RUN exit;
- [x] no GC timer/poller and no render-frame ownership.
- [ ] **AWAITING PHYSICAL VALIDATION:** compare gen-2 count/max pause and whole-process memory trend. If memory rises materially, tune from evidence rather than reintroducing arbitrary forced collections.

## Polling audit / high-priority Media migration

The broad audit does not support a blanket "timers are bad" rewrite. Most periodic providers are already low cadence or semantically periodic. Media is the important high-frequency candidate: while active its single shared owner currently queries approximately `1.0 -> 2.0 -> 2.5 s`, backing off only when idle.

The accepted migration target is documented as the **HIGH PRIORITY H/J bridge** in `Current_Plan.md`:

- keep exactly one `_SharedMediaRuntimeOwner`;
- use proven GSMTC/WinRT native changes only as coalesced dirty/wake signals into that same owner/query path;
- native callbacks never query/decode/mutate UI;
- generation/session token lifetime and teardown are explicit;
- one slow reconciliation heartbeat is allowed only to detect missed events/liveness;
- any missed event is counted/logged `[MEDIA_EVENT][MISSED_EVENT]`;
- required event-observation failure is loudly `[MEDIA_EVENT][DEGRADED]`;
- **no automatic return to the old 1–2.5 s active polling loop** at the migration endpoint.

Do not production-wire guessed WinRT events. First prove the exact installed package's event names/token removal/callback threading in a Windows reality harness.

## Source-only checkpoint gates

- [x] viewport/presentation-coherence contracts: `16/16` GREEN under `python -m unittest -v tests.test_visualizer_viewport_scaling_contracts`.
- [x] runtime/performance contracts: `4/4` GREEN under pytest.
- [x] the previously reported source-only test "hang" is not reproducible: the viewport profile completes in ~`0.014 s`; the runtime/perf profile in ~`0.07 s` in the current sandbox.
- [ ] The maintained PySide6 `h-destination 84/84` belongs to the outside-Codex SHA and **has not been rerun here**.

## Next operator log checkpoint

Run with `--perf` and preserve ordinary/QML/perf/visualizer/cache-relevant logs.

- [ ] Let multiple transitions happen **naturally by timer**; also perform several manual Next transitions.
- [ ] Note visible hitch start relative to the later transition; do not intentionally induce every transition because the timer/manual difference is now diagnostic.
- [ ] Bubble: canonical + very tall/wide, motion tails, Ghost enabled/disabled, reactivity and collision/rebound. Thickness needs no special retest unless it regresses.
- [ ] Spectrum: play continuously, pause, wait for idle, resume; include canonical and tall.
- [ ] Oscilloscope: aggressive vertical resize specifically looking for flicker/blanking.
- [ ] Sine/DevCurve: canonical/tall/wide sanity and visible smoothness.
- [ ] Read HUD only as evidence; the logs carry the same metrics for exact correlation.
- [ ] Correlate `[PERF][IMAGE_CHANGE]`, `[PERF][GC_POLICY]`, `[PERF_HUD]`, cache source/protection and `screensaver_qml.log` before attributing a hitch to the transition shader itself.

