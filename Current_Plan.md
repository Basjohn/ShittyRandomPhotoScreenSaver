# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-31 — R5 physical/log evidence has been assessed. The complete Bubble wake-footprint repair is physically accepted for the tested problematic viewport shapes, and replacement-runtime prefetch reseeding is log-validated (100% scaled-cache hits / zero worker fallbacks in the supplied R5 run). Cursor Halo performance is physically REJECTED: moving the retained QML Halo still devastates presentation FPS, while context-menu suppression restores high FPS. Source review now localizes two surviving hot paths that R5 failed to remove: every passive mouse move still crosses `QQuickWindow -> Python` and queries live interaction/Ctrl providers, and the visible Halo itself moves/restarts inactivity inside the retained QML scene, dirtying the same composited scene as the Visualizer. The one-display MC discriminator is relevant because MC short-circuits the Settings-backed interaction-mode provider and also runs the 60 Hz output; both differences must be removed from the hot path rather than guessed around. A separate CUSTOM geometry defect is also admitted into H: ordinary Reddit/Media corner+wheel resize currently scales the outer rect plus only a partial family payload, not the complete retained presentation, causing Reddit content escape/persisted bad geometry and Media internal spacing/alignment drift. No prior accepted Bubble/prefetch/reactivity repair is discarded. H remains open.

Outside of Codex Work Began @ 61decb33f6ebb107b2997928077e9d56d5faa8a1

## Current checkpoint

G remains accepted. The H production-authority cutover and caller-proven deletion of the old physical host remain accepted architecture. **H is still OPEN. I is NOT admitted.**

### H item ledger (live checklist)

Move a row between groups only when its state genuinely changes; do not keep a stale status line beside a newer one.

**Closed**

- [x] H1a — repeated dual-display Settings/CUSTOM recreation hang
- [x] H1b — terminal Quick retirement / Clock model lifetime
- [x] H2 — Media artwork provider identity
- [x] Black flash (recurring/activation) — fullscreen-flip PresentMode transitions; fixed by the 1px overscan (`R-63`). See the black-flash slice.

**Pending**

- [ ] H5a — CUSTOM Visualizer independent display admission
- [ ] H5b — Spectrum topology + shaping + renderer-transfer repair (**implementation + focused parity GREEN; primary live reactivity GREEN; topology/recreation/preset gate pending**)
- [ ] H5c — end-to-end visualizer reactivity parity audit (**R5 physical/log run assessed: Bubble complete-wake repair accepted at tested problem shapes; prefetch reseed/cache path physically/log GREEN; Cursor Halo R5 architecture physically FAILED and is reopened below; GC + residual warm-cache natural/manual delta remain open**): Bubble reactivity/tail presentation, Spectrum idle handoff, Oscilloscope resize flicker, readiness/final-render audit
- [ ] H6 — CUSTOM Settings size-lock scope
- [ ] H8 — Visualizer middle-click preset hotswap (**implementation + deterministic gates GREEN; physical cycling/recreation acceptance pending**)
- [ ] H9 — CUSTOM ordinary-widget uniform resize contract (**IMPLEMENTED: single uniform retained-presentation scale (`OverlayWidget.uniformScaleTransform`) for Reddit/Reddit2 + Media, derived from outer-rect/baseline ratio; CUSTOM resize is geometric, font/artwork stay Settings-owned; Gmail/Weather/Steam/Clock audited inert. Deterministic gates GREEN; physical Reddit + Media falsifiers `AWAITING PHYSICAL VALIDATION`.**)
- [ ] H7 — Exit visible-response/perf classification (likely J after measurement)

**New observations / J carry**

- [ ] Visualizer does not fade in on startup while ordinary widgets do — reveal-consistency bug (decomposed under "Reveal / startup composition" below).
- [ ] Context-menu theme colours do not follow the active theme; the menu remains stuck on one palette despite being a themed element. Treat as J presentation/theme parity unless source inspection exposes a functional settings-authority defect.
- [ ] Aspiration: desktop -> application crossfade reveal, widgets fading in afterwards — J Parity+.

The last Codex-run maintained `h-destination` profile was GREEN (84/84 at the outside-work anchor; prior black-flash baseline `b4e8ce40`). This outside-Codex source-only checkpoint cannot execute that PySide6 profile, so **84/84 must be rerun in the normal project environment before claiming the checkpoint integrated**; the supplemental checkpoint profiles are 16/16 viewport/coherence plus 4/4 runtime/performance GREEN. H is not closed by unit tests alone: every H/H-J row in the operator ledger must be reconciled and the final dual-display source-mode smoke must remain physically clean.

Detailed evidence: `Docs/QtQuick_Migration/H_Post_Cutover_Runtime_Reality_Corrections.md`  
Operator backlog: `Docs/QtQuick_Migration/Post_Cutover_Operator_Observation_Ledger_2026-08-30.md`

## Permanent Qt/QML observability baseline

Qt/QML has a diagnostic plane separate from Python logging. `core/logging/qt_message_capture.py` is therefore permanent always-on infrastructure, not temporary H instrumentation.

Normal source/runtime acceptance now reads **both**:

```text
screensaver.log       Python/runtime narrative + WARNING+
screensaver_qml.log   direct Qt/QML message-handler evidence
```

The Qt/QML capture must be installed before `QApplication` / `QQmlEngine` creation and remain active through final Qt teardown. A clean run still creates `screensaver_qml.log` and records capture session markers; the previous `delay=True` behavior, where a clean run produced no file at all, is retired because “file missing” was ambiguous with “capture failed.”

The sidecar records timestamp, severity, PID, thread identity, Qt category, source file/line/function when available, sequence, and message. It is direct/synchronous and independently rotated so Qt/QML failures are not dependent on the ordinary asynchronous log queue.

Unexpected Qt/QML warnings/errors that correlate with the current migration surface are first-class evidence. Do not call a physical H/J gate GREEN merely because `screensaver.log` is clean.

This is **not** an OS-level fd-2 tee. Raw non-Qt native stderr remains a separate diagnostic plane. Do not add `os.dup2` redirection casually: a true tee changes crash persistence, subprocess inheritance and shutdown semantics. See `Docs/Qt_QML_Observability.md`.

## Production architecture — binding

```text
selected physical display
-> DisplayManager semantic orchestration
-> one QuickDisplayUnit
-> one QuickDisplayRuntime
-> one standalone threaded QQuickWindow
-> one retained Quick scene
-> one display-owned WidgetRuntimeManager
-> canonical capability + per-instance monitor admission
-> retained ordinary/CUSTOM/input/context/auxiliary/transition owners
-> zero-or-one admitted visualizer edge per display
-> exactly one product-level visualizer owner across participating displays
```

Do not restore `DisplayWidget`, QRhiWidget/GLCompositor presentation, `QQuickWidget`, a QWidget compatibility facade, a hidden QWidget presenter, a second accelerated surface, a second visualizer owner/pacer, or a software/QRhi fallback.

Other binding invariants:

- Python owns semantic/settings/provider/runtime truth; QML consumes bounded presentation state and emits semantic actions.
- `QuickSceneController` owns Quick item creation/retirement.
- One `WidgetRuntimeManager` per display generation.
- No duplicate provider/service manager, BeatEngine/source owner, logical visualizer runtime, mailbox/bridge, CUSTOM owner or cadence owner.
- Old-generation admission closes and authored/logical work joins before scene/window retirement; generation `0` is valid.
- Fallbacks are product-authorized, destination-owned and fail-loud.
- QML reports preferred content size only; Python owns anchor + margin + clamp + x/y + final outer rect.
- CUSTOM committed geometry outranks family/default geometry.
- Outside CUSTOM, Visualizer effective position/monitor routing follows Media.
- In committed CUSTOM, Visualizer owns its own persisted monitor/geometry, may overlap and may live on another selected display from Media.
- Bubble authored cadence remains presentation-independent; the display Quick frame pacer is the sole GUI presentation opportunity.
- Bubble Temporal Fidelity remains binding. Do not reduce cadence or retune physics merely to hide a presentation problem.

## Closed H1 — preserve, do not reopen without regression evidence

### H1a reconstruction

`2220782d` changed ordinary-family assembly to build all admitted retained family QML first and activate successfully built families afterward. The operator then completed 3 Settings recreation cycles + 5 CUSTOM Save/Continue cycles in one dual-display process without a watchdog dump.

### H1b terminal retirement

Terminal shutdown now has a terminal-purpose destruction barrier, staged finalization, safe Settings helper event filters and retained-model lifetime long enough for QML item retirement. Later physical runs prove:

```text
application_exit barrier arms
-> Quick roots retire
-> barrier completes (~200–250 ms)
-> ThreadManager/process finalization
-> clean code=0 exit
```

No `BackgroundRenderItem::` slot error, Windows access violation, Clock null-model retirement storm or Settings event-filter exception remains in the accepted physical gate.

The former failure is historical evidence only; do not keep its old “required next work” in active plan text.

## Closed H2 — Media artwork provider identity

Current production `MediaFamilyAdapter` obtains the `MediaArtworkImageProvider` already registered on the scene factory's `QQmlEngine` via the host and injects that exact provider into `MediaPresentationModel`. The old private-per-card provider split is gone.

The operator's latest source-mode run physically confirms Media artwork now displays.

**Preserve as permanent cross-layer contract:** decoded artwork must publish into the exact engine-registered provider that resolves `image://mediaartwork/<identity>`.

Historical artwork fade/presentation quality is **not H2**. Artwork currently appears but lacks the nicer historical transition/fade; that is a named J Parity+ row.

## Active H work — execute in order

### H5a — CUSTOM Visualizer must remain independent of Media's display route

**Status: newest physical logs prove routing/construction on the requested display, then expose and source-localize a cross-display Media playback-model binding defect. The narrow binding repair and two-live-unit regression are implemented; physical confirmation remains open.**

Non-CUSTOM Visualizer follows Media's effective monitor. CUSTOM Visualizer owns its own persisted monitor/geometry and may live on another selected display. `QuickDisplayUnit.is_visualizer_participant()` does not require Media on that display. The sole Visualizer owner still consumes the existing effective Media presentation model for playback truth even when that model belongs to another active display unit; no Media copy is constructed on the Visualizer display.

Trace once per generation:

```text
spotify_visualizer.position / monitor
media.monitor
custom decision
effective monitor
requested screen
participant set
CUSTOM failover state
chosen unit
construct result / reject reason
```

Do not redesign routing or re-couple Visualizer ownership to a same-screen Media card.

Closure checklist:

- [x] Emit one bounded `[VIS_ROUTING]` record for the generation's initial admission decision; correlate later grace/fallback/reclaim outcomes through `[VIS_FAILOVER]`.
- [x] Read the newest record on a CUSTOM-Visualizer-on-a-different-display config: generations 1/2 correctly choose/admit screen 1 with Media on screen 0 and no failover, but every Bubble frame stays `playing=False`.
- [x] Localize the first wrong source seam: owner construction and `_bind_quick_visualizer_media()` looked up `media` only through the chosen Visualizer unit, so a split route found no model and never initialized/connected playback.
- [x] Resolve the already-admitted retained Media model across the active display set (same-display preferred), then use that exact model for initial playback and the sole `stateChanged` connection. Do not construct/mirror Media on the Visualizer display.
- [x] Add a two-live-unit production-construction regression: Media model only on screen 0, CUSTOM Visualizer owner only on screen 1, one owner, cross-display state change reaches `set_playing(True)`.
- [x] Confirm `QuickDisplayUnit.is_visualizer_participant()` admits the CUSTOM Visualizer's persisted display without Media there.
- [x] Non-CUSTOM Visualizer still follows Media's effective monitor (no regression).
- [x] Maintained `h-destination` revalidated GREEN (78/78) after the cross-display playback-binding repair.
- [ ] Dual-display source smoke shows the CUSTOM Visualizer on its own display.

Technical route: `Docs/QtQuick_Migration/H5_Visualizer_Routing_And_Spectrum_Decomposition_2026-08-30.md`.

### H5b — Spectrum saturation + wrong functional presentation topology

**Status: major source repair physically validated; Spectrum is recognizable/reactive again. Pause handoff briefly reaches zero before the correct idle floor and remains open under H5c diagnostics.**

The direct comparison against known-good `3fe5df687387b6b6a121142372c43a7719442386` found four concrete ownership/presentation losses, including the second historical creator translation discovered during implementation:

- [x] **Topology translation:** historical `spectrum_render_mode -> spectrum_single_piece` restored at the logical owner; legacy boolean remains fallback-only.
- [x] **Color-topology translation:** historical `spectrum_unique_colors -> spectrum_rainbow_per_bar` restored at the presentation owner.
- [x] **Shared source/engine shaping:** mirror/shape nodes/notches/wave/profile/lane strengths/drop speed now route through one presentation-neutral configuration-time applier into the existing BeatEngine. Historical full-model semantics are preserved even while another mode is visible because the notch/shaping state feeds shared pre-mode audio lanes.
- [x] **Renderer transfer:** historical bar+peak `0.55` transfer restored exactly at the Quick Spectrum shader-input boundary; logical bars remain canonical.

Live closure checklist:

- [x] No old creator/catch-all QWidget configuration façade restored.
- [x] No new BeatEngine/source/timer/cadence/poller added; source values apply only on existing configure/mode-activation edges.
- [x] Add focused Quick-owner/configuration + renderer-transfer tests.
- [x] Execute the focused source/configuration/renderer-transfer suite in the normal PySide6 project environment: `10/10` GREEN and promoted into the maintained H profile.
- [x] R1 physical re-measure confirms real music is recognizable and strongly reactive after the known repairs; the prior saturated/unusable response is gone.
- [ ] Physical topology/lifecycle gate: `bars` presets are continuous columns; segmented presets remain intentionally segmented; mode switch/recreation/preset swap preserve topology and shaping. The in-place preset leg depends on H8 rather than a fabricated test route.

If Spectrum saturates or weakens again, find the first bad S-stage; do not apply global visualizer gain.

H5b still must not change Bubble/shared cadence to make Spectrum look better.

Technical route: `Docs/QtQuick_Migration/H5_Visualizer_Routing_And_Spectrum_Decomposition_2026-08-30.md`.  
Reactivity evidence/decomposition: `Docs/QtQuick_Migration/H5c_Visualizer_Reactivity_Parity_Audit_Decomposition_2026-08-31.md` and `Docs/QtQuick_Migration/Visualizer_Reactivity_Historical_Current_Evidence_Matrix_2026-08-31.md`.

### H5c — historical-vs-Quick visualizer reactivity parity audit

**Status: ACTIVE H audit. Post-R3 physical logs accepted Bubble outline scaling, exposed Bubble wake/ghost presentation multiplication, a Spectrum capture-identity idle race, high-scale Oscilloscope stale-geometry flicker, and presentation/performance stalls that now have dedicated observability. Geometry/reactivity repairs remain authoritative unless their own falsifier fails.**

What is already established / implemented:

- [x] Core `audio_worker`, `BeatEngine`, energy-band, feature-frame, signal, oscilloscope-contract, technical-config and transient-bus source is byte-identical historical/current; bar computation is behaviorally identical apart from a type-only import path.
- [x] Healthy ~90 Hz authored Bubble cadence does not prove live music energy is admitted; intentional idle-energy motion can continue at full authored cadence.
- [x] Mechanical historical-live-consumer audit completed: the split already owns Oscillo/Sine/DevCurve generated fields and technical controls; the actual stranded live set was three Bubble logical controls, two historical Spectrum creator translations, and the shared Spectrum source/engine block. Retired `*_growth` is excluded.
- [x] Restore Bubble `bubble_group_drift`, `bubble_collision_pop_mode`, `bubble_big_visual_smoothing` at the authored logical owner.
- [x] Restore the historical shared Spectrum notch/shaping source contract. **This is cross-mode relevant:** absent configured notches, unchanged `fft_to_bars()` falls back to fixed `4/10` bass/mid split indices instead of preset-normalized boundaries (for example about `14/31` at Bubble's 48-bar domain), changing source lanes before mode-specific logic.
- [x] Historical Bubble renderer energy uniforms are a dead end and were not restored.
- [x] Add bounded `[VIS_SOURCE_CONFIG]`, `[VIS_TECH_CONFIG]`, `[VIS_REACTIVITY]` and Play/Pause T0-T7 telemetry at existing boundaries only; no diagnostic timer/cadence/large-array logging.
- [x] Add one focused new parity test file covering source routing, Bubble controls, Spectrum translations/`0.55` transfer, and the reactivity-critical technical zero/false contract.
- [x] Verify the existing Quick technical owner already preserves per-mode bar count, explicit audio block size, `dynamic_floor=False` + manual floor, adaptive/manual sensitivity, dynamic-range boost, input gain and **`agc_strength=0.0` as no AGC**. These were already correct and are not duplicated by the new source applier.
- [x] Record the golden coverage gap: replay/presentation goldens largely begin after authored feature state exists, so GREEN goldens do not prove live preset -> BeatEngine/audio-worker configuration reachability. Do not regenerate goldens for this repair.
- [x] Execute focused parity and shown-Quick tests in the normal PySide6 environment; the current DevCurve logical/shader tests and targeted real-Quick captures are GREEN.
- [ ] Physically re-measure all five modes under real music after the shared source repair.
- [x] Capture warm + cold Play/Pause T0-T7 traces. Cold Bubble reaches fresh ready input/publication in ~93.8 ms; warm resume reaches fresh publication in ~20.0 ms. This disproves source/capture latency as the reported multi-second visual ramp.
- [x] Prove Bubble `source_ready` admits valid current audio promptly; do not weaken generation/activation freshness fencing.
- [x] Sine paused idle is physically present; apply a paused-only +20% motion parity adjustment (`0.14 -> 0.168`, `0.22 -> 0.264`) without changing live/music gain or adding a timer.
- [x] Bubble B0-B5 physical trace: fresh current source, strong real-music energy and ~90 Hz one-step-per-tick integration are healthy. Remaining dead appearance is downstream. Remove the protected-edge full-geometry override so Quick always renders the newest authored Bubble frame; protected edges retain consume-once metadata only.
- [x] Play edge audit: restore historical `engine.wake()` before playback commit; reduce cold-only reactivity ramp from 1.5 s to 1.0 s while preserving warm-resume no-ramp and generation/activation freshness fencing. Correct T3/T5 sampling so diagnostics measure real edge timing.
- [x] DevCurve source comparison: Quick had invented delayed ghost fills/outlines even though the historical shader never consumed its ghost setting. Remove that presentation/runtime work; keep saved ghost settings inert for historical parity. The remaining jagged edge had a second source-proven migration delta: logical-pixel AA width was multiplied by independent CUSTOM visual scale (`0.75` in the observed profile), narrowing coverage. Restore the historical `1.15 / inner_h` mapping.
- [x] Bubble's remaining magnitude loss is quantified and source-proven: the active `772.831/280 = 2.760x` height domain divided final radius before Quick, while the old renderer interpreted the same radius against actual card height. Preserve position/trail world normalization and restore card-height-normalized radius. ~~The first repair inverse-mapped collision/spawn radius and correction distances by `domain_h`;~~ the later dedicated pair/overlap falsifier disproved that height-owned geometry and supersedes it with canonical content-space collision/spawn policy. B6/B7 final-simulation/frozen-big plus B8 logical/device-pixel telemetry remain valid around Play/Pause.
- [x] First corrected B9 run physically confirms dramatically better / almost close-worthy magnitude. The short Play trace reaches fresh source in `105.7 ms` (`6 ms` source age), sustains ~`89 Hz` / `1.000` integration, and carries matching B6/B7/B8 radii to about `76` logical px (`114` device px at DPR `1.5`).
- [x] Remove the source-proven display-only hard 13-19% radius hold band at authored `bubble_big_visual_smoothing=1.0`; preserve source/pulse authority, cadence and latest-state delivery.
- [x] Latest physical run confirms magnitude and Play/Pause are much better but rejects the first settling correction: hero radius still rapidly flickers because target hover can alternate between micro and macro correction rates. Continuously interpolate the effective rate across the settle/drop thresholds, preserve exact large-edge `40 Hz` rise / `22 Hz` drop endpoints, and expose one stable tracked Bubble's target/display/delta/step/rate/mix through existing bounded B6-B8 logs.
- [ ] Physically validate breathing Bubble contraction/elasticity after continuous rate interpolation; no source, gain, pulse, timer, cadence or authored-setting change is admitted.
- [x] Restore bounded transient influence at the existing stream/drift motion owner: consume each kick/snare/vocal event once, lift the existing stream-burst envelope immediately, decay through its existing state, and cap the added drift drive at `0.18`. A same-body event/no-event oracle proves greater renderer-facing short-window stream and drift displacement with identical pulse and radius sequences; authored settings, source gain, cadence and clocks are unchanged.
- [ ] Physically validate that stream speed and drift speed/amount now respond perceptibly to transients without looking overdriven. Interpret B6-B8 `stream_step`/`drift_step` as pre-collision motion-stage contributions, not final post-collision trajectory distance.
- [ ] Re-measure DevCurve basic preset after historical ghost no-op and logical-pixel AA restoration. `[VIS_DEVCURVE_TRANSIENT]` must trigger from the historically consumed bass lane only; the prior package's 51 mid/high-only samples were not evidence of a failed transient layer.
- [x] Spectrum pause handoff source race localized: one logical capture could resolve bars with `playing=True` and then reread live playback as `False` while assembling the outer frame, producing an impossible paused frame carrying playing-state bars below the idle floor. Use one captured playback identity through the whole frame; **do not raise/retune the existing ~0.24 idle floor**. **AWAITING VALIDATION:** pause from live playback should enter the idle bars directly rather than hit zero/stale-playing bars first.
- [ ] Complete Oscilloscope final renderer-input comparison as a control. Post-R3 high-vertical flicker also exposed a cross-mode presentation seam: geometry-mismatched snapshots were being consumed as a blank clear. Retained Quick now leaves the mismatched snapshot unconsumed and keeps the last coherent pixels until matching geometry arrives; **AWAITING VALIDATION** during aggressive live resize.
- [x] Preserve current scale/viewport sizing contracts and Bubble's expanded position/motion world; radius remains the historical fraction of actual card height. Collision/spawn policy now evaluates radius/gaps in canonical renderer-content units and projects only positional corrections back to the expanded world; canonical `1x1` stays exact. Retired `*_growth` controls are not parity targets.
- [x] Add a production-path Bubble viewport A/B that consumes the same transient at canonical, wide and tall extents and compares final head/trail displacement in content coordinates, event-consumption count and radius sequence. It proved the old fixed world delta lost `1 / domain_axis` of visible motion; project stream/drift once onto the expanded domain and compute nonbaseline trail smear in content space. Canonical BTF, consume-once delivery, transient envelope, authored controls and radius sequence remain unchanged; motion diagnostics now retain renderer-normalized meaning.
- [x] Extend the same viewport oracle to swirl and group drift. Swirl tangent/radial math and birth radius were still measured in expanded-world coordinates, distorting orbit direction and spawn offset by aspect; solve nonbaseline swirl geometry in content space and project birth offsets once. Deterministic diagonal/random group-drift cells require no further source change.
- [x] Correct source-proven Bubble entry/exit/cluster/retry spatial literals that shrank by `1 / domain_axis` at larger extents. Seeded directional refill, cluster spread, surface exit, contraction retirement, overlap-retry bounds and pre-entry prediction A/Bs now project one content distance onto the relevant logical axis; canonical literals and random-draw order remain exact.
- [x] Isolate post-collision rebound with a preloaded-impulse canonical/wide/tall A/B. The falsifier failed exactly by `1 / domain_axis`; project impulse application once onto each expanded axis. Canonical `1x1` arithmetic remains unchanged.
- [x] ~~Leave Bubble collision detection/correction height-domain-owned after the impulse repair.~~ Dedicated two-bubble and spawn-overlap A/Bs disproved that assumption: wide/tall storage made pair distance anisotropic and viewport height changed effective radius/gap policy. Evaluate collision + spawn overlap in canonical renderer-content space, project only corrections back into the expanded world, and preserve canonical arithmetic.
- [x] Keep the collision repair out of the Python hot-path hole: precompute inverse domain axes/margins once per collision call; non-canonical pair checks add reciprocal multiplies, not per-pair division/helper calls. No new pass or pair-complexity increase.
- [x] Correct the separately proven Spectrum viewport-height transfer duplication: Python already computes the capped height boost; both presenters now use that helper and the shader consumes the resolved boost once. Preserve the independent historical `0.55` bar/peak transfer. **AWAITING VALIDATION:** shown-Quick canonical/tall physical comparison.
- [x] Oscilloscope/Sine viewport falsifier: `Vertical Shift` used a fixed `20..80 px` clamp, so the same setting weakened sharply on tall CUSTOM viewports. Scale only that authored placement range by viewport-height extent; line/glow stroke ownership remains uniform-visual-scale-only. **AWAITING VALIDATION:** canonical/tall line-spacing comparison.
- [x] DevCurve viewport falsifier: Quick projected authored outline/specular controls by baseline/current axes, then the shader clamped them back to canonical normalized floors/bounds. Apply authored bounds before projection and project Quick safety floors/bounds through the same axis transfer; legacy shader branch remains canonical.
- [x] DevCurve cross-axis falsifier: specular X width was projected but its derived Y radius inherited X-normalized units, stretching the lobe on tall-only and wide-only viewports. Upload one CPU-resolved X->Y normalized ratio and use it for the derived vertical radius; also scale the AA safety floor. No per-fragment division or extra render pass. **AWAITING VALIDATION:** DevCurve basic preset at canonical + tall/wide.
- [x] Bubble motion-tail projection re-falsified at canonical, wide, tall, `2x2`, and approximately the operator's `1.724x2.914` viewport: head + all three trail samples + trail strength remain invariant in renderer content space. Do not add another tail-domain multiplier.
- [x] Post-R3 physical run proved the remaining high-scale tail/"ghost bubble" abundance is presentation multiplication, not simulation population: active Bubble count remained ~43–49 and trail payload ~531–612 floats while tall viewports visually exposed several ripple sources per bubble. R4 correctly compressed each rendered trail sample's offset from its owning bubble back toward baseline-pixel footprint on expanded axes. **PHYSICALLY REJECTED AS SUFFICIENT post-R4:** the new canonical/wide/tall screenshots show the tall card remains the clear clutter outlier because the complete ripple field around each compact source still scales with viewport height. Retain the source-centre correction as one component; the complete-wake repair is owned below.
- [x] Bubble shader performance guard: existing wake work is up to `fragments × bubbles × 3 samples`, so larger CUSTOM area can magnify pre-existing fragment cost even when simulation count is constant. Add an output-preserving square/radius reject before `length`/`sin`/`exp`; no new pass, history buffer, allocation or cadence owner. **AWAITING PERF VALIDATION** via the new HUD/log metrics.
- [x] Bubble outline scaling: source explained the operator report (fixed authored-pixel stroke versus radius growing with viewport height). Replace the heavy `1.2 px @ r=.04` baseline rule with a radius-proportional ~`3.75%` stroke plus authored-pixel safety bounds; this preserves roughly the prior large-card appearance while dropping canonical `r=.04` to ~0.4 px. **PHYSICALLY GREEN post-R3:** operator reports thickness good at normal, low and extremely large scales.
- [ ] Bubble Ghost contract: current UI promises a fading afterimage and exposes `bubble_ghost_decay`, but retained Quick uploads only Ghost alpha and the shader draws a static `1.18x` halo; decay is not consumed. The shared current/legacy shader path does not establish the intended historical implementation. Keep this OPEN / **AWAITING HISTORICAL ORACLE OR PHYSICAL CONTRACT DECISION**; do not fake a repair by merely wiring decay into the halo.
- [x] Focused outside-Codex source-only checkpoint profiles are GREEN: `16/16` viewport/presentation-coherence contracts plus `4/4` runtime/performance contracts. They are supplemental only: the supplied ZIP has no `.git` and not the maintained full `tests/` tree/PySide6 environment, so they do not replace Codex's reported `h-destination 84/84`.
- [x] Rebuild passive `--perf` visibility without a second cadence owner: each display HUD derives scene FPS / `dt_max` / pacer target+skip% / active-or-last transition timing from existing `frameSwapped`; the Visualizer HUD derives Quick draw FPS / logical revision rate / snapshot age / geometry-mismatch count. Text/log aggregation is ~1 Hz and owns no render/update timer.
- [x] Add origin-aware image-change tracing (`timer`, `manual_next`, startup/retry) across queue selection, random-transition resolution, worker scheduling/start, per-display cache/worker source, UI handoff and transition admission. One thread-safe trace crosses UI/compute/UI; no polling/sleeping is introduced.
- [x] Natural-vs-manual cache archaeology: at least one bad natural transition re-prescaled exact display-ready images that had already been warmed and then evicted by deeper speculative prefetch. Protect only the exact predicted next display batch from ordinary LRU eviction; hard item/byte caps remain absolute and can override protection. Log protected count under `--perf`.
- [x] Legacy `GCController` is migration debris: it was never instantiated and its Python-frame disable/enable/manual-idle-GC model does not match threaded Qt Quick. `RuntimeGCPolicy` remains the accepted RUN owner: preserve generation-0 automatic collection, never force `gc.collect()`, observe expensive collections, and restore exact interpreter thresholds/callback state at RUN exit. **R4 PHYSICAL RESULT REJECTS THE CURRENT THRESHOLDS AS SUFFICIENT:** the latest run recorded four gen-2 pauses at ~99.8–134.2 ms, including one zero-object scan. Do not hide this with lower Visualizer cadence; reassess allocation pressure + threshold policy after R5 Halo/Bubble/readiness repairs under the GC target below.
- [x] **R4 CHECKPOINT LOGS/PHYSICAL EVIDENCE RECEIVED AND ASSESSED:** the requested natural/manual transitions and aggressive visualizer extents were exercised. The run isolates Cursor Halo motion as a severe FPS destroyer while ordinary mouse movement with Halo suppressed by the retained context menu is harmless; physically rejects R4 Bubble source-centre compression as sufficient on tall viewports; exposes a post-Settings/CUSTOM prefetch lifecycle hole; and shows gen-2 GC pauses worsening to ~100–134 ms. Spectrum/Oscilloscope/other deterministic prior repairs remain governed by their own falsifiers rather than global choppiness.
- [x] **POST-R4 PERF/POINTER TARGET — R5 attempted hot-path split + duplicate-pointer repair:** R5 removed pointer coordinates from auxiliary-state/root-property publication and made Halo admission blank the native cursor. **PHYSICAL RESULT: PERFORMANCE REJECTED / pointer-coherence behavior retained as useful.** The new run reproduces the catastrophic movement degradation with no meaningful improvement; context-menu suppression still restores ordinary-cursor motion without the collapse. Source audit shows why R5 was insufficient: `QuickDisplayWindow.mouseMoveEvent()` still routes every passive move through `QuickInputController -> RuntimeInputOwner`, which calls live interaction/Ctrl providers; normal interaction-mode resolution reaches the Settings manager under locks/cache lookup, while MC short-circuits `is_mc_build() -> True` and context-menu-active returns before that provider path. Separately, `HoverHandler.point.position -> CursorHalo.x/y` still moves a visible retained QML item and restarts its inactivity `Timer` on every pointer-coordinate change, dirtying the same QQuickWindow scene that owns the Visualizer. R5 optimized only the old auxiliary publication subset, not these two surviving hot paths. **DO NOT REVERT the one-cursor semantic fix.**
- [ ] **POST-R5/R6 PERF/POINTER TARGET — remove Cursor Halo from the composited scene and from passive Python mouse-move work:** replace the moving retained-QML fake pointer with a real window/native `QCursor` whose pixmap(s) render the Halo appearance, so OS/Qt cursor motion does not dirty the wallpaper/Visualizer/widget scene. Cache interaction-mode/Ctrl admission as event-updated generation-scoped facts; passive mouse movement must not query Settings/providers or republish unchanged semantic state. Preserve the accepted one-cursor behavior: Halo admission means the window cursor itself is the Halo; context-menu/semantic suppression restores the ordinary cursor immediately. Preserve the two-second inactivity contract without restarting a Python/QML timer at mouse-poll rate (deadline/last-motion semantics are acceptable; any fade must remain bounded and scene-independent). Add source/runtime instrumentation/contracts proving pointer movement alone cannot request Quick scene presentation. Physical acceptance must compare moving Halo vs moving ordinary cursor with the context menu on the same high-refresh display; no reduced Visualizer cadence, mouse throttling, second cursor owner, polling fallback or silent degradation. **Do this before re-tuning GC so the next allocation/GC run has a clean attribution boundary.**
- [x] **POST-R4 BUBBLE WAKE TARGET — compact-source repair physically insufficient:** canonical/wide/tall screenshots physically reject R4 source-centre-only sufficiency; vertical is the clear outlier. Preserve Bubble simulation/history/head radius/reactivity and the accepted source-centre compression. R5 adds a Quick-only authored-pixel radial transfer for each source's complete wake: ripple radius/cap and ring spacing now remain baseline-pixel authoritative while whole-card uniform scale stays independent; legacy shader behavior is explicitly identity-gated. The strengthened falsifier measures source displacement + full physical ripple extent at canonical, wide, tall, `2x2`, and approximately `1.724x2.914`. Bubble Ghost/Decay remains separate/open. **IMPLEMENTED R5 / SOURCE-ONLY GREEN / PHYSICALLY ACCEPTED for the tested excess-ghost/motion-tail viewport problem. Preserve.**
- [x] **POST-R4 TRANSITION READINESS TARGET — reseed prefetch after runtime recreation:** timer/manual still share `_show_next_image()`, but the R4 logs exposed a generation/lifecycle hole after Settings/CUSTOM replacement: healthy exact-next prefetch stopped, cache misses rose, and rotations fell back to ~200–500 ms ImageWorker scaling. R5 uses `authoritative_first_frames_ready` to request one generation-fenced deferred reseed through the existing prefetch owner/cardinality bit. **R5 LOG VALIDATION GREEN:** `runtime_ready_reseed` fires after recreation; end-of-run cache flow records `scaled_hits=16`, `scaled_misses=0`, `worker_requests=0`, `worker_fallbacks=0`, with regular prefetch resume passes. Preserve this repair. Residual warm-cache natural-vs-manual presentation loss remains OPEN and is now cleaner to isolate.
- [ ] **POST-R4/R5 GC TARGET:** GC remains a separate multiplicative presentation axis. The R5 run still records gen-2 pauses of ~102.8, 102.0, 119.7 and 111.6 ms (including zero-object scans); the MC RUN summary alone reports `(3955, 188, 3)` gen0/gen1/gen2 collections. R5 did not remove the surviving passive-mouse provider path or retained-scene Halo motion, so do not infer allocation pressure was meaningfully tested cleanly. Re-measure after the corrected Halo architecture, then repair retained allocation pressure/policy without forced GC or reduced Visualizer cadence.
- [ ] Performance watch for J/H validation: post-R3 logs show authored Visualizer cadence ~89.8 Hz while five stale-frame/latency episodes reach ~0.67–5.0 s; repeated gen-2 GC pauses are ~30–43 ms and natural transition preparation can include ~120–230 ms ImageWorker prescales. System load was modest. Treat simulation cadence, scene presentation, GC and image-preparation contention as separate axes.
- [ ] **J performance-history boundary:** viewport-scaling work already present at the outside-Codex SHA may itself have changed GPU/presentation cost. This source ZIP has no trustworthy pre-scaling A/B, so do not assume the handoff state was performance-neutral; when Git/history and comparable logs are available, compare the pre-scaling boundary against `61decb33f6ebb107b2997928077e9d56d5faa8a1` before blaming later H5c repairs.

Detailed live checklist and repair sequence: `Docs/QtQuick_Migration/H5c_Visualizer_Reactivity_Parity_Audit_Decomposition_2026-08-31.md`.  
Exact historical/current evidence matrix and next source paths: `Docs/QtQuick_Migration/Visualizer_Reactivity_Historical_Current_Evidence_Matrix_2026-08-31.md`.  
Safety checkpoint / applied-vs-pending handoff: `Docs/QtQuick_Migration/H5c_Implementation_Checkpoint_2026-08-31_R3_Outside_Codex.md` (R2 remains historical evidence).
Latest performance repair checkpoint: `Docs/QtQuick_Migration/H5c_Performance_Pointer_Wake_Readiness_Checkpoint_2026-08-31_R5_Outside_Codex.md` (R4 observability checkpoint remains historical evidence).

### HIGH PRIORITY H/J bridge — event-driven Media runtime; retire active high-frequency polling

**Status: architecture decision accepted / implementation pending. This remains high priority after the bounded R5 source-proven repairs and may be pulled forward if Media polling/contention obstructs physical validation.**

The shared Media architecture is already correctly cardinalized: one `_SharedMediaRuntimeOwner` owns the configured controller/provider, accepted snapshot and query pipeline across display presenters. Keep that owner. The migration target is to replace its normal active `1000 -> 2000 -> 2500 ms` polling cadence with GSMTC/WinRT event-assisted dirty notifications feeding the **same** owner/query path. A slow reconciliation heartbeat remains allowed as correctness instrumentation; it is **not** a silent fallback state source.

Closure / safety checklist:

- [ ] First build a Windows reality harness against the exact installed `winrt.windows.media.control` package and prove which manager/session change events are reliable for: session list/current-session churn, playback state, metadata/artwork and timeline changes. Record add/remove token semantics and callback thread/apartment behavior before production wiring. Do not code against guessed event names/lifetimes.
- [ ] Extend `BaseMediaController` with one narrow presentation-neutral observation contract (start/stop event observation + dirty callback/capability). No QObject/QML/display ownership enters the controller. Existing command/query APIs remain the only provider mutation/read path.
- [ ] `WindowsGlobalMediaController` owns native manager/session subscriptions on one explicitly controlled WinRT lifetime. Native callbacks do **no media query, image decode, logging flood, UI mutation or presenter access**; they only generation-fence and enqueue/coalesce a tiny dirty reason toward the shared owner.
- [ ] `_SharedMediaRuntimeOwner` remains the sole refresh/query/snapshot authority. Many native events coalesce to at most one refresh in flight plus one pending dirty edge; event bursts cannot create parallel GSMTC awaits or per-display queries.
- [ ] Session identity replacement is transactional: subscribe new identity only through the controller owner, retire old session tokens deterministically, and fence every callback by runtime/provider/session generation. No stale callback can revive a retired Settings/recreation generation.
- [ ] Preserve command confirmation semantics: user Play/Pause/Next/Previous/Seek may request an immediate/coalesced refresh, but command completion and provider events must converge on the same owner rather than creating a second confirmation poller.
- [ ] Retain one **slow reconciliation heartbeat** (target deep-idle scale, e.g. ~30 s unless evidence chooses another value) solely to detect dropped native events/session disappearance and provider liveness. Every heartbeat is identifiable in perf logs. If it discovers a state change that should have arrived by event, increment/log `[MEDIA_EVENT][MISSED_EVENT]` with provider/session/reason; never silently normalize missed delivery as ordinary operation.
- [ ] **No silent polling fallback. Migration endpoint:** failure/unavailability of required event observation must emit a loud `[MEDIA_EVENT][DEGRADED]` ERROR/diagnostic state. Do not automatically resume the old 1–2.5 s active polling loop. If a temporary compatibility poll is ever needed during development, it must be explicitly gated, loudly logged/counted on activation and every recovery, and removed before this item can close.
- [ ] Teardown order is a first-class gate: close event admission -> detach session tokens -> detach manager tokens -> fence/join any queued dirty delivery -> retire controller -> retire shared owner/presenters. Repeated dual-display Settings recreation, provider changes, CUSTOM cycles and clean app exit must show zero late native callback/native termination.
- [ ] Perf/behavior acceptance: steady active playback produces near-zero periodic Media queries between real changes; event→accepted-snapshot latency is measured; no duplicate runtime/controller/query owner appears; Media controls/artwork/timeline remain correct; reconciliation finds no unexplained missed events in an ordinary run.
- [ ] Keep the broader polling audit evidence: low-frequency usage/system-mute/RSS/weather/Gmail/clock responsibilities are not automatically defects. Migrate another poller only when its provider offers a trustworthy event contract and the change reduces contention without weakening lifecycle correctness.

### H6 — CUSTOM Settings may lock only size-authoring controls

**Status: exact current source and runtime-shaped Settings contract are GREEN; operator revalidation remains open.**

For Media, canonical CUSTOM size-lock metadata is only:

```text
media_font_size
media_artwork_size
```

CUSTOM itself must not disable progress/seek/glow/volume/mute feature controls. Normal feature/provider dependency gates still apply. A complete current-source setter audit finds no secondary CUSTOM disable owner: `_refresh_custom_resize_lock_state()` touches only descriptor-owned controls, while progress/glow and provider-volume state are owned by their normal dependency refreshes. The normal profile currently persists the reported combination (`Custom`, Spotify, transport/progress/glow/volume/mute enabled), and a real `WidgetsTab` built from that exact state reports only font/artwork disabled.

Do not invent a force-enable repair while the current source/runtime contract is GREEN. Re-open Settings from the current build; if controls still look disabled, capture the exact control/parent enabled tuple and style state before changing ownership.

Closure checklist:

- [x] Audit every current Media/lock `setEnabled()` owner: no secondary CUSTOM path exists; progress/glow and provider-volume gates are independent semantic owners.
- [x] Runtime-shaped exact-state test proves CUSTOM locks only `media_font_size` + `media_artwork_size`; progress toggle/height/shadow/glow/colour and volume/mute remain effectively enabled under their true dependencies.
- [x] Existing dependency-off tests prove transport-off and unsupported-provider states remain disabled; no force-enable behavior was added.
- [x] Full `test_widgets_tab.py` + descriptor suite passes `126/126`.
- [ ] Operator re-open the Media Settings page on the current build and confirm only the two size-authoring controls are grey. If not, record the control plus parent/grandparent enabled tuple.

Technical route: `Docs/QtQuick_Migration/H6_Custom_Settings_Lock_Scope_Decomposition_2026-08-30.md`.

### H8 — Visualizer middle-click preset hotswap

**Status: implementation and deterministic gates GREEN; physical cycling/recreation acceptance pending.**

Historical runtime behavior and bug records prove that middle-click on the live Visualizer stepped to the next preset in the **current mode**, including the special user-owned Custom slot. H8 now admits the gesture at `QuickDisplayWindow` before neutral input fallback, through a dedicated retained Visualizer middle-click admission. Generic `RuntimeInputController` remains presentation-neutral and keeps its established right/left semantics.

Required product contract:

```text
middle-click inside active retained Visualizer
-> advance exactly one preset in the current mode, with wraparound
-> mode identity does not change
-> leaving Custom snapshots its exact user-owned payload
-> returning to Custom restores that payload
-> no next-image / exit / context-menu side effect
```

`request_mode_change()` still rejects a target equal to the current mode. The distinct `request_preset_change()` transaction reuses the existing owner/controller/BeatEngine hidden boundary, hard-joins the outgoing logical runtime, admits one fresh target identity and reveals it through the existing fade. A second request while any visualizer transition is active is consumed but dropped before another activation can begin.

Preset persistence is one narrow Settings transaction: replace the `widgets.spotify_visualizer` child and its canonical root `visualizer_custom_presets` companion cache only. It never emits or refreshes the whole `widgets` mapping, so Media siblings remain untouched. Schema v4 migrated the shipped flat Bubble cache to the nested per-mode shape; schema v5 strips the shipped route leak (`monitor` and any other non-mode-owned admission/layout fields) from every cached mode. Presets and Custom own only the normalized active-mode payload. A missing mode snapshot is seeded from its persisted raw mode payload before the first runtime mutation. Curated application uses replace semantics.

Work this after H5/H6 source changes to avoid overlapping visualizer-activation churn, but close it before H re-closes.

Closure checklist:

- [x] Add a middle-button retained semantic admission at `QuickDisplayWindow`; inside active Visualizer is consumed before neutral input, outside remains inert.
- [x] Same-mode preset activation transaction through the existing visualizer owner/controller/BeatEngine (NOT `request_mode_change()`), wraparound, mode identity unchanged.
- [x] Custom slot round-trips losslessly; shipped flat cache migrates once and missing-mode first use snapshots pre-mutation raw state.
- [x] Atomic visualizer-child + canonical Custom-cache persistence uses replace semantics; no whole-`widgets` refresh and Media remains unchanged.
- [x] Preset/Custom payload ownership excludes widget admission, `position`, `monitor` and CUSTOM geometry; schema v5 migrates leaked caches and runtime/Settings restore preserves the live route.
- [x] No next-image/exit/context-menu side effect; one source/pacer, stale-generation fencing, fresh-frame admission and overlap rejection preserved.
- [ ] Operator middle-click through several presets in Bubble and Spectrum, round-trip Custom, then recheck Settings recreation, CUSTOM Save/Continue and restart/reload with clean logs. Confirm requested monitor, owning display, outer rect and viewport extent remain the same across each recreation.

Technical route: `Docs/QtQuick_Migration/H8_Visualizer_Middle_Click_Preset_Cycle_Decomposition_2026-08-30.md`.

### H9 — CUSTOM ordinary-widget uniform resize contract

**Status: IMPLEMENTED (single uniform retained-presentation scale); deterministic gates GREEN; physical Reddit + Media falsifiers `AWAITING PHYSICAL VALIDATION`.** Do not mark H9 closed until the operator runs the two physical falsifiers below. J still owns final visual polish and Media's separate app-volume-child parity.

New physical evidence (original defect): Reddit wheel/corner resize could produce a narrower committed shell while rows escape below/outside it, and Save/reinit faithfully replayed that broken state. Media resize changed the shell but pulled metadata/artwork/chrome toward new container centres and altered observable spacing instead of uniformly enlarging/shrinking the authored presentation.

Root cause (as fixed): `QuickCustomLayoutOwner._apply_uniform_scale()` scaled `baseline_global_rect` uniformly **and** scaled a couple of Settings-like values via `scale_quick_size_payload()` (`font_size` for Reddit, `font_size + artwork_size` for Media). Retained QML then relaid the rest of each card from many *unscaled* authored constants/floors (`spacing`, row-height floors, margins, progress/control bands, vertical-centre anchors, shell/chrome), so the outer rect and the content were not one scale. A committed CUSTOM rect outranks content-driven preferred size on replay, so the mismatch persisted after Save/recreation.

**Implemented mechanism — one real uniform retained-presentation scale (opt-in):**

- `OverlayWidget.qml` gained `uniformScaleTransform` (bool, default false) + a derived `presentationScale`. When a family opts in, the whole authored card (shared card shell + every composed primitive) is laid out **once** at its content-driven baseline size in a fixed `overlayAuthoredRoot` container and scaled as one coordinate relationship (`transformOrigin: Center`, `Math.min(width/preferredW, height/preferredH)` so it is uniform and letterboxes centred rather than distorting a single axis). Text, spacing, row heights, artwork, chrome, borders/shadows and pointer/hit geometry now enlarge/shrink together (distance-field text scales without re-rasterising).
- The scale is **derived** from the Python-assigned outer rect / baseline-preferred ratio — no `presentation_scale` is pushed or persisted, there is no QML->Python size feedback, and Python/session stays the sole outer-rect/anchor/clamp authority. The owner already assigns `outer = baseline * scale`; QML recovers the same factor from geometry.
- `RedditPresentation.qml` and `MediaPresentation.qml` set `uniformScaleTransform: true`. Their CUSTOM resize is now **purely geometric**: `custom_layout_size.py` returns a geometry-only (`{}`) payload for the `reddit_font` / `media_scale` modes (`UNIFORM_TRANSFORM_RESIZE_MODES`), and the Reddit/Media payload handlers ignore any (stale) `font_size`/`artwork_size` so a pre-H9 committed layout replays as a correct uniform scale from geometry alone. Font/artwork stay Settings-owned — nothing Settings-like is mutated or persisted by a temporary CUSTOM resize.
- Gmail/Weather/Steam/Clock are **audited and left on their existing payload path** (opt-out, `presentationScale` stays 1, `overlayAuthoredRoot` fills the assigned rect exactly): the shared shell change is inert for them, the strongest non-regression guarantee. Clock in particular keeps `clock_font` because of its analogue/digital variant-geometry derivation and geometry store, and pure-text font scaling is already coherent for it.

Files: `rendering/quick/qml/OverlayWidget.qml`, `rendering/quick/qml/RedditPresentation.qml`, `rendering/quick/qml/MediaPresentation.qml`, `rendering/quick/custom_layout_size.py`, `rendering/quick/widgets/reddit.py`, `rendering/quick/widgets/media.py`. Regression: `tests/test_qtquick_h9_uniform_resize.py` (added to the `h-destination` profile).

Repair target / falsifier:

- [x] One actual **uniform retained-presentation scale** for the resizable falsifier families — outer rect, text, spacing, row heights, artwork, chrome, borders/shadows and hit geometry in one authored coordinate relationship — proven by `test_reddit_uniform_scale_is_min_ratio_and_preserves_aspect` and the band/row invariance bars. No whole-widget scale approximated by mutating Settings-like payload values.
- [x] Deterministic: Reddit content stays contained by the scaled card at shrink/grow bounds (`test_reddit_rows_stay_contained_by_scaled_card_on_shrink_and_grow`); Media header/main-band/content keep authored placement under resize (`test_media_bands_keep_authored_placement_under_resize`); committed replay ignores a stale scaled-font payload and derives the same uniform scale from geometry (`test_committed_replay_ignores_stale_font_payload_and_keeps_uniform_scale`).
- [ ] **`AWAITING PHYSICAL VALIDATION` — Reddit/Reddit2:** operator confirms wheel + corner resize preserve baseline aspect and row containment at shrink/grow bounds (no entries escape the selected card), and Save -> runtime recreation -> CUSTOM re-entry reproduces the exact coherent visual and rect.
- [ ] **`AWAITING PHYSICAL VALIDATION` — Media:** operator confirms wheel/corner resize preserves the authored relative placement/spacing of provider header, metadata, artwork, progress and controls (no independent band recentering), and Save/recreation round-trips it. (App-volume child intentionally not entrenched; J may still split it.)
- [x] Single Python/session geometry authority, cross-display transfer, Cancel, layout slots, family enable state and the Visualizer scale-vs-viewport contract preserved — no second geometry owner, feedback loop, polling or silent fallback (`test_qtquick_custom_layout_owner.py` transfer/cancel/save, `test_uniform_transform_scope_is_reddit_and_media_only`, `test_visualizer_rect_payload_scaling_is_unchanged`, all GREEN).
- [x] Gmail/Weather/Steam/Clock audited against the shared mechanism and shown inert (`test_non_transform_family_shell_change_is_inert`, `test_qtquick_family_size_policy.py`, `test_qtquick_clock_custom_variant_geometry.py` GREEN). Family-specific authored baseline shapes remain; the resize operation is coherent.

### H7 — Exit visible-response/performance classification

The current clean run routes Exit immediately and completes the terminal Quick barrier in ~250 ms. Script-mode recursive `__pycache__` cleanup then consumes additional terminal time.

Remeasure **visible window dismissal** separately from legal retirement and developer housekeeping. If visible dismissal is prompt, carry remaining tail/pycache policy into J/performance or cleanup rather than reopening lifecycle ownership.

## Interleaved black-flash / first-visible-frame reality slice

**Status: SOLVED (recurring flash). Root cause MEASURED with PresentMon: the exact-cover borderless window is non-deterministically promoted to a hardware fullscreen-flip presentation, and the composition <-> `Hardware: Legacy Flip` PresentMode transitions present the black/stale frames on the LG/Display-1 output (4K 60 Hz secondary TV). Fix: a 1px coverage-preserving overscan (`_fullscreen_compat_geometry`) keeps the window non-exact-cover, so it stays in stable `Composed: Copy with GPU GDI` and never transitions. 6/6 flashing-prone launches -> black=0, operator-confirmed no flashes. Two earlier repairs (deferred first-show, event-driven surface-refresh) physically FAILED and were removed.**

This operator-approved No Quota interleave keeps the remaining H5-H8 work evidence-driven rather than generic J polish.

Physical `[QUICK_SURFACE]` evidence after the first repair split the symptom:

```text
startup:
window can become visible with no real PresentationImage -> native black clear exposed

A -> B -> A focus:
window_active_changed coincides with flash while visible/exposed/scene graph/image identity stay stable

first context-menu open on each display:
two rapid flashes possible; retained image + scene graph stay stable; later same-display open is clean
```

An old wallpaper/image was physically glimpsed during a flash, but with no matching image-publication event. Treat this as stale/native/back-buffer exposure, not image-selection state.

**New binding evidence (single-window MC A/B):** running one continuous MC process and switching the sole SRPSS window between outputs gave: LG/Display-1 only -> black flashes; MSI/Display-0 only -> completely clean; LG/Display-1 again -> black flashes. The defect **follows the LG output (a 60 Hz TV, DPR 1.5, physical 3840x2160) even when it is the ONLY SRPSS window.** This kills the earlier "secondary window / two-window activation" framing.

**Removed as physically failed (do not reintroduce):**

- deferred first-show (`prepare_on_screen()` / `commit_prepared_show()` gating the native show on first `PresentationImage`) — it made startup visibly WORSE (image -> black -> image); reverted to the immediate `show_on_screen()`;
- event-driven surface-refresh (`_request_background_surface_continuity()` -> `BackgroundRenderItem.request_surface_refresh()` + `QQuickWindow.update()` on activation/menu) — it did not improve the focus/menu flash; removed.

**Kept:** production proof-colour-band removal (opt-in only); `[QUICK_SURFACE]` telemetry (passive); real-image readiness semantics (`intentional_base_frame_ready`) independent of the removed show gate. Focused regression `tests/test_qtquick_black_flash_contract.py` now pins only proof opt-in + readiness.

**Failed approaches (physically disproven — do NOT retry):**

- [x] Persistent scene graph + graphics (`setPersistentGraphics/SceneGraph(True)`) — operator saw no change; telemetry: SG is never invalidated mid-flash, so persistence cannot matter.
- [x] Event-driven surface-refresh redraw on activation/menu (`BackgroundRenderItem` refresh + `QQuickWindow.update()`) — did not improve focus/menu flash. Removed.
- [x] Deferred first-show (gate native show on first image) — made startup visibly worse (image -> black -> image). Removed.
- [x] VSync ON (`swapInterval=1`) alone — no reliable reduction; single-run counts are inside a large launch-to-launch variance band.
- [x] Drop `SplashScreen` role — non-deterministic: identical code gave 0 flashes one launch, 15 the next (both operator-corroborated). Not a reliable fix.
- [x] `WS_EX_NOACTIVATE` / `WindowDoesNotAcceptFocus` / DWM-transition-disable / Ctrl-poll replacement — PROHIBITED (feature loss); never a valid endpoint.

**Solution (measured + operator-confirmed):**

- [x] Coverage-preserving 1px overscan (`QuickDisplayWindow._fullscreen_compat_geometry`, `x-1,y-1,w+2,h+2`). PresentMon proof: exact-cover baseline showed `Hardware: Legacy Flip` present rows with black/stale events clustered at the composition<->flip transitions; height-1 (3/3) and overscan (3/3) launches stayed 100% `Composed: Copy with GPU GDI` with black=0. Overscan chosen over height-1 because it loses no visible row. This recovers the historical `_FULLSCREEN_COMPAT_WORKAROUND` principle. Regression: `tests/test_qtquick_window.py::test_fullscreen_compat_geometry_overscans_without_losing_coverage`.

Remaining (minor, separate seam): operator still saw at most ~1 flash on startup — the show-before-first-frame interval, distinct from the resolved recurring/activation flash. Carry to J unless it recurs.

Diagnostic method for future presentation issues (ephemeral, NOT committed to the repo): run `C:\tools\PresentMon\PresentMon.exe` capture-all (`--timed N --qpc_time --output_file …`, works unelevated; process rows resolve, `SwapChainAddress` is `0x0` without elevation) alongside a DXGI Desktop-Duplication (`dxcam`) near-black/stale detector timestamped in QPC, then compare `PresentMode`/`AllowsTearing` in a +/-250 ms window around each detected frame. Drive activation with Win32 `SetForegroundWindow` (no cursor motion, so the mouse-move exit gesture never fires). See `Docs/Qt_QML_Observability.md`.

Constraints honored: no feature loss; no `WS_EX_NOACTIVATE`/`WindowDoesNotAcceptFocus`; no DWM transition disabling; no Ctrl-poll replacement; no permanent diagnostic env var/tool; no second surface. Independent/hardware flip is an optimization, not a correctness requirement — SRPSS stays correct in ordinary composition.

Technical route:
`Docs/QtQuick_Migration/J_Black_Flash_Surface_Continuity_Decomposition_2026-08-30.md`.

## Reveal / startup composition

The recurring flash above is solved; the remaining work here is the *reveal* — how a display goes from nothing to full application state — and its consistency across widgets. This is J Parity+ quality, not H correctness, but it is decomposed here because it shares the startup/first-frame owners: `rendering/quick/startup_reveal.py` (`QuickStartupRevealCoordinator`, one generation-scoped opacity scalar) and `DisplayPresenter.set_family_fade_opacity()` -> per-family `set_fade_opacity()` -> QML `fadeOpacity`.

### Residual startup micro-flash (low priority)

- [ ] Operator sees at most ~1 barely-perceptible flash on startup, not consistently reproducible — the show-before-first-rendered-frame interval on the LG output, distinct from the solved activation flash. **Not a standalone concern.** Promote only if it becomes consistent, or fold it into the crossfade reveal below. Do NOT reintroduce the failed deferred-show; any first-frame gate must be measured (PresentMon / `[QUICK_SURFACE]`), not assumed.

### Visualizer does not fade in on startup — reveal-consistency bug

**Status: operator-observed; source seam identified.**

Ordinary families fade in via one coordinated scalar (`QuickStartupRevealCoordinator` -> `set_family_fade_opacity` -> each `bound_widget_ids` presentation's `set_fade_opacity` -> `fadeOpacity`). The **visualizer is not an ordinary family** (not in `bound_widget_ids`; it is the separate retained visualizer owner + render bridge), so the shared fan-out never touches it, and `startup_reveal.py` explicitly leaves the visualizer its "independent authored startup/fade authority" — which in practice does not fade it in, so it pops while every other widget fades.

- [ ] Confirm the exact visible behavior (instant pop vs a different authored curve).
- [ ] Locate the visualizer's own reveal/opacity authority (or prove it has none on the fresh-frame admission path).
- [ ] Choose ONE owner: (a) extend the coordinated reveal scalar to the retained visualizer item's root opacity — a presentation-only fan-out like the family one, no new timer/cadence/pacer; or (b) drive the visualizer's existing authored fade from the same generation-scoped reveal completion. Prefer (a) for consistency; it must not disturb the render bridge, the single source/pacer, stale-generation fencing or fresh-frame admission.
- [ ] Regression: the reveal scalar reaches the visualizer item's root opacity, and reveal completion still fires exactly once.

Constraints: presentation-only opacity; no second cadence/source/pacer; fade only the root opacity, never the visualizer's render/content timing; preserve all-five visualizer fidelity.

### Aspiration — desktop -> application crossfade reveal (J Parity+, optional)

**Status: operator aspiration, only if achievable cleanly; NOT required for H, and never as another workaround layer.**

Target sequence:

```text
existing desktop (last composed frame)
-> crossfade into the application base image/state
-> widgets fade in AFTER the base is presented (staggered on their own fade)
```

- [ ] Feasibility first: under DWM the app cannot read the desktop's pixels, so a true desktop->app crossfade likely means presenting the app initially transparent and raising base opacity — which risks the desktop showing through (an underlay-leak class). Measure (capture the composed output) before committing to any implementation.
- [ ] If feasible, base-image reveal and widget reveal become two ordered phases of the same `QuickStartupRevealCoordinator` (base first, then the family + visualizer fan-out) — not two owners.
- [ ] This would subsume both the residual micro-flash and the visualizer-fade bug, but only as one coherent reveal contract.
- [ ] Hard constraints: one retained window/scene; no second/cover surface; no repaint loop; the fixed overscan/present-mode contract stays intact; do not reintroduce any removed experiment.

Technical route: `Docs/QtQuick_Migration/J_Reveal_Startup_Composition_Decomposition_2026-08-31.md`.

## Observations intentionally carried to J unless a deterministic H seam appears

Bubble reactivity is **no longer in this carry bucket**: the historical/current audit found source-proven configuration-ownership defects and promoted the end-to-end response investigation to H5c. Preserve the currently good Bubble partial/CUSTOM resizing while H5c proceeds.

### Black/test-frame/focus/context flashes

The recurring/activation black flash on the LG/Display-1 output is SOLVED (fullscreen-flip-promotion PresentMode transitions; fixed by the coverage-preserving overscan — see the black-flash slice above). A minor startup-only flash may remain (show-before-first-frame) and is carried to J unless it recurs. The two prior bounded repairs failed and were removed; do not reintroduce them.

## H re-closure gate

H closes only when (live checklist):

- [x] H1 reconstruction + terminal-retirement regressions remain GREEN
- [x] H2 artwork provider identity remains GREEN and real artwork remains visible
- [x] recurring/activation black flash resolved and not reintroduced (`R-63` overscan)
- [ ] CUSTOM Visualizer can own a different selected display from Media while non-CUSTOM still follows Media (H5a)
- [ ] Spectrum has non-degenerate data + canonical topology + restored engine-shaping/render-transfer parity after switch/recreation (H5b)
- [ ] historical-vs-current visualizer reactivity audit closes the live-consumer config gaps, Bubble weak response, Play/Pause edge delay and Sine idle transport without adding clocks/owners/global tuning (H5c)
- [ ] CUSTOM Settings locks only size-authoring controls (H6)
- [ ] middle-click hotswaps exactly one preset in-place, lossless Custom round-trip, no mode change / no Media disturbance (**deterministic GREEN; physical H8 acceptance pending**)
- [ ] ordinary CUSTOM wheel/corner resize is genuinely uniform and persists/replays without Reddit content escape or Media internal-spacing drift (H9 — **implemented + deterministic gates GREEN; physical Reddit + Media falsifiers `AWAITING PHYSICAL VALIDATION`**)
- [ ] Exit visible response measured/understood with clean natural termination (H7)
- [ ] unexpected `screensaver_qml.log` warnings/errors on these paths reconciled
- [x] maintained `h-destination` GREEN after the bounded fixes (`84/84`, 2026-08-31)
- [ ] every unresolved ledger row whose phase includes H is closed or explicitly carried to J with evidence
- [ ] a short dual-display source-mode smoke is GREEN

Only when every box is checked may I start.

## I — blocked residue reconciliation

I remains source/test/tool residue cleanup only. Do not use it to absorb current runtime failures and do not restore legacy presentation to satisfy stale tests.

## J — Parity+ destination

J is **Parity+**: proven historical user-visible quality/behavior is the floor where it was better, not the ceiling. Preserve genuine Quick improvements and fix historical shortcomings rather than reproducing bugs.

Read together:

```text
Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md
Docs/QtQuick_Migration/J_Visual_Parity_Runtime_Acceptance_Addendum_2026-08-30.md
Docs/QtQuick_Migration/J_ParityPlus_Historical_Visual_Interaction_Reference_2026-08-30.md
Docs/QtQuick_Migration/Post_Cutover_Operator_Observation_Ledger_2026-08-30.md
Docs/Qt_QML_Observability.md
```

Primary broad visual references are the 4.7.2/4.7.0 release screenshots and `15099d3` remains useful for older UI/presentation archaeology. **Visualizer reactivity is a specific exception:** the user-supplied `3fe5df6` tree is the known-good pre-Qt-Quick behavioral oracle for Bubble/Oscillo/Sine/Spectrum/DevCurve semantics. Historical code is never implementation authority; reproduce its behavior through current Quick owners.

Named J cells include:

- startup/focus/context-menu/transition black flash and apparent test-colour-band flash — recurring/activation flash SOLVED (`R-63` overscan); residual startup micro-flash + reveal work decomposed under "Reveal / startup composition";
- actual gentle reveal/fade — including the visualizer-does-not-fade-in bug and the desktop -> application crossfade aspiration (see "Reveal / startup composition");
- Media Parity+: proportions, artwork sizing/chrome, **artwork change fade**, header/control-strip balance, optional metadata;
- preserve the newer transport strip where it is better;
- Media-dependent app-volume child widget: its established/default presentation is a separate adjustable adjacent/outside item with its own geometry; an integrated form is optional only when explicitly selected;
- Gmail clipping/refresh/header alignment;
- Achievement Pulse packing/icon/count allocation;
- one coherent visible pointer treatment (no OS cursor + halo duplication);
- ordinary non-CUSTOM free-space composition, especially Media + Visualizer, without dog-piling;
- CUSTOM overlap/cross-display authority untouched by ordinary collision avoidance;
- coherent context-submenu hover-leave lifetime;
- context-menu colours must resolve from the active theme rather than remaining stuck on a single palette; preserve one theme authority and avoid a menu-specific duplicate palette owner;
- all-five visualizer eyes-on fidelity after H restores Spectrum data/topology;
- after H5c restores functional historical reactivity/timing, any remaining Bubble fine visual feel/parity without sacrificing BTF or its currently good partial resizing;
- mixed refresh/DPR, off/wake, A->B->A focus/topology, installed performance tails and clean exit;
- low-priority CUSTOM/Edit guide visibility: existing grid/guide presentation must actually publish useful snap/alignment guides during editing; do not invent a second layout owner;
- low-priority Quick-native performance/debug overlay parity if the product affordance is still desired; it must consume read-only current metrics and must not resurrect legacy GL presenter/profiler ownership;
- **Qt/QML sidecar review as part of physical acceptance**, not console-only inspection.

### J-Media app-volume child widget — separate by default

**Status: actionable J Parity+ restoration; current Quick presentation is incorrectly folded into the Media card and no separate/integrated settings selector exists yet.**

The app-volume control is a child/accessory of Media, not an independent widget-family capability. It depends on an effective Media presentation and provider app-volume capability, follows Media's effective display route and lifecycle, and reuses the existing Media presentation model plus its one `MediaVolumeRuntimeService` lease/action seam. The established toggle outcome and migration default are a separate retained Quick item beside the Media card. An in-card form may remain only as an explicit optional presentation variant.

Closure checklist:

- [ ] Restore a distinct retained app-volume child item with its own bounds, hit target and adjustable geometry; do not implement the default by reserving width inside `MediaPresentation.qml`.
- [ ] Existing settings and missing-variant migration resolve to **separate**; integrated resolves only from an explicit user-selected option.
- [ ] Ordinary layout places the child adjacent/outside Media. CUSTOM persists an own child rect/size payload in Media's effective display bucket; it does not gain an independent monitor setting or route.
- [ ] The child presentation is admitted/visible only while Media and app-volume capability are effective, and its retained item hides/retires with Media. Shared service lifecycle remains Media-owned/setting-gated, never child-owned.
- [ ] Both presentation variants use the existing Media presentation model plus its one `MediaVolumeRuntimeService` lease/action seam; no QWidget resurrection, second Media card, duplicate model, controller, poller or service.
- [ ] Focused retained-item, default-selection, dependency/lifecycle, CUSTOM round-trip and no-duplicate-runtime tests are GREEN; release-screenshot comparison confirms the default adjacent/outside outcome physically.
