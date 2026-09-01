# Current Plan — Qt Quick Production Migration

Last updated: 2026-09-01 — latest Bubble CUSTOM falsifier assessed. Operator physically confirms Bubble reacts well outside CUSTOM and at near-canonical CUSTOM rectangles, but loses visible radius/motion/Ghost response as CUSTOM width or height diverges. The new logs exonerate source cadence and the GC/audio lane for this symptom: through the bad shapes Bubble still publishes about 88-92 revisions/s with zero geometry mismatches and healthy pulse/event/stream values. Source/history audit instead proves a presentation-scaling regression: the recent extreme-tall `head_radial_scale` globally compressed the historically height-normalized head radius, while the newly-added Ghost incorrectly reused the R4 ripple-wake `baseline/current` axis compression even though BubbleSimulation had already normalized history into renderer-content coordinates. The head multiplier is removed; the accepted R4/R5 ripple-wake compression remains untouched; Ghost consumes normalized history once with a modestly gentler fade; the +1 authored-pixel extreme-size outline bonus remains. The earlier CUSTOM presentation-rebase repair is now log-validated independently and is archived as R-68. Extra-wide Spectrum smoothing remains physically improved. Retained DSP-state reuse remains worth keeping and no collector threshold/cadence change is admitted: this ~178 s stress run completed 11,643/11,643 analysis steps with 11,638 state reuses and ~1.826 ms mean execution, but GC still recorded `(3420, 163, 3)` with gen-2 pauses `99.49`, `112.71`, `112.88 ms`; the stable previous-bars tuple remains because the silence path mutates the live list and this recreation-heavy run is not clean evidence that the safety snapshot itself causes those deep scans. R7 native telemetry still proves the intermittent seam is a +1 device-pixel right overlap from Display 0 mixed-DPR rounding; black flash remains absent and overscan remains protected. Media remains healthy. Historical records R-64..R-69 are current; R-69 deliberately preserves the failed global Bubble radius/Ghost viewport-compression method while its contract restoration awaits physical validation. Gmail recreation/edit-dimension and the eventual GC root fix still require durable records once physically validated.

Outside of Codex Work Began @ 61decb33f6ebb107b2997928077e9d56d5faa8a1

## Current checkpoint

G remains accepted. The H production-authority cutover and caller-proven deletion of the old physical host remain accepted architecture. **H is still OPEN. I is NOT admitted.**

### H item ledger (live checklist)

Move a row between groups only when its state genuinely changes; do not keep a stale status line beside a newer one.

**Closed**

- [x] H1a — repeated dual-display Settings/CUSTOM recreation hang
- [x] H1b — terminal Quick retirement / Clock model lifetime
- [x] H2 — Media artwork provider identity
- [x] H3 — Reddit production opener / saver-vs-interactive product action
- [x] H3b — Clock runtime mode-toggle persistence + CUSTOM geometry recreation
- [x] H4 — Media Play/Pause/seek provider-result semantics (physical Spotify validation passed)
- [x] Black flash (recurring/activation) — fullscreen-flip PresentMode transitions; fixed by the 1px overscan (`R-63`). See the black-flash slice.
- [x] H5a — CUSTOM Visualizer independent display admission (operator physically validated 2026-09-01; tests pending final reconciliation)
- [x] H5b — Spectrum topology + shaping + renderer-transfer repair (operator physically validated 2026-09-01; tests pending final reconciliation)
- [x] H8 — Visualizer middle-click preset hotswap (deterministic + operator physical acceptance; tests pending final reconciliation)
- [x] H7 — Exit visible-response/perf classification (operator physical acceptance)

**Pending**

- [ ] H5c — final visualizer/performance closure: physically validate the repaired Bubble CUSTOM scaling/Ghost contract, finish the remaining Bubble/Spectrum/Osc/DevCurve reactivity checks, continue evidence-led GC/allocation-pressure work, reconcile active high-refresh schedulability/freshness, and close the R7/R-63 seam. R6 native-cursor performance boundary remains protected; ordinary pointer visual parity is J and must never restore scene-bound mouse-rate motion.
- [ ] H6 — CUSTOM Settings size-lock scope (small final physical Settings check remains unless already covered by the final operator smoke)
- [ ] H9 — CUSTOM ordinary-widget uniform resize contract: cross-family scaling/floor physically strong; Gmail Save/reinit containment is the remaining falsifier.

**New observations / J carry**

**Binding J visual-parity oracle (highest visual authority):** the repository now carries paired family screenshots under `images/migration/Ideal (PreMigration)/` and `images/migration/Current (PostMigration)/`. For J user-visible geometry/density/alignment/chrome decisions, the family-specific `Ideal (PreMigration)` image is the primary achievable target and the corresponding `Current (PostMigration)` image is the explicit regression/comparison baseline. This paired repository oracle outranks prose descriptions, release-wide screenshots and historical-source inference for the pixels it actually shows. **Explicit operator exception: for Media, the current post-migration transport/control bar is the only current Media visual treatment presently preferred over the old implementation; preserve that strip while using the Ideal image as the default target for the rest of the Media composition unless a later operator decision says otherwise.** Agents must not infer additional exceptions from the current screenshot or substitute their own taste for the pictured target. The set currently covers Abandonment Issues, Achievement Pulse, Gmail, Media, Reddit and Weather; Clock is intentionally absent because its current Quick presentation is already acceptable. J must inspect the relevant pair before changing any of those families.

- [ ] Visualizer does not fade in on startup while ordinary widgets do — reveal-consistency bug (decomposed under "Reveal / startup composition" below).
- [ ] Context-menu theme colours do not follow the active theme; the menu remains stuck on one palette despite being a themed element. Treat as J presentation/theme parity unless source inspection exposes a functional settings-authority defect.
- [ ] Aspiration: desktop -> application crossfade reveal, widgets fading in afterwards — J Parity+.

The maintained `h-destination` profile is **not currently all-GREEN**. The last completed profile run before the newest R6/R7/Media contract wiring was 79/85. The six red **files survive, but specific assertions in them are stale and must not drive production backwards**: `test_qtquick_auxiliary.py` still names the retired QML Halo seams; `test_qtquick_visualizer_bubble.py`, `test_qtquick_visualizer_devcurve.py` and `test_qtquick_visualizer_item.py` contain accumulated Bubble/visualizer telemetry expectations from earlier checkpoints; `test_bubble_viewport_reflow.py` still references retired `_render_radius_in_world`; and `test_s_hotkey_workflow.py` has an old `_show_next_image` test double that does not accept the current `origin=` contract. H9's 8/8 uniform-resize falsifiers and its broad affected surface were GREEN. The maintained runner must also include the current R4-R7 source contracts (`test_visualizer_viewport_scaling_contracts.py`, `test_runtime_perf_policy_contracts.py`) and both Media event-owner suites (`test_media_event_observation.py`, `test_media_runtime.py`). **Do not quote a new aggregate pass/target count until that exact reconciled profile is actually run.** Reconcile the six stale assertions against current source, never by restoring retired seams. H is not closed by unit tests alone: every H/H-J row in the operator ledger must be reconciled and the final dual-display source-mode smoke must remain physically clean.

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
- Do not invent fallbacks. A fallback exists only when an explicit product contract names it; any such route must be destination-owned, bounded and fail-loud. Silent compatibility fallback is prohibited.
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

- [x] **Topology translation:** historical `spectrum_render_mode -> spectrum_single_piece` restored at the logical owner; legacy boolean is compatibility-read-only for old saved settings and is not an alternate runtime owner/path.
- [x] **Color-topology translation:** historical `spectrum_unique_colors -> spectrum_rainbow_per_bar` restored at the presentation owner.
- [x] **Shared source/engine shaping:** mirror/shape nodes/notches/wave/profile/lane strengths/drop speed now route through one presentation-neutral configuration-time applier into the existing BeatEngine. Historical full-model semantics are preserved even while another mode is visible because the notch/shaping state feeds shared pre-mode audio lanes.
- [x] **Renderer transfer:** historical bar+peak `0.55` transfer restored exactly at the Quick Spectrum shader-input boundary; logical bars remain canonical.

Live closure checklist:

- [x] No old creator/catch-all QWidget configuration façade restored.
- [x] No new BeatEngine/source/timer/cadence/poller added; source values apply only on existing configure/mode-activation edges.
- [x] Add focused Quick-owner/configuration + renderer-transfer tests.
- [x] Execute the focused source/configuration/renderer-transfer suite in the normal PySide6 project environment: `10/10` GREEN and promoted into the maintained H profile.
- [x] R1 physical re-measure confirms real music is recognizable and strongly reactive after the known repairs; the prior saturated/unusable response is gone.
- [x] Physical topology/lifecycle gate: operator validated continuous-vs-segmented topology plus lifecycle/preset behavior on 2026-09-01. Full test reconciliation remains deferred to the supplied complete test-folder checkpoint.

If Spectrum saturates or weakens again, find the first bad S-stage; do not apply global visualizer gain.

H5b still must not change Bubble/shared cadence to make Spectrum look better.

Technical route: `Docs/QtQuick_Migration/H5_Visualizer_Routing_And_Spectrum_Decomposition_2026-08-30.md`.  
Reactivity evidence/decomposition: `Docs/QtQuick_Migration/H5c_Visualizer_Reactivity_Parity_Audit_Decomposition_2026-08-31.md` and `Docs/QtQuick_Migration/Visualizer_Reactivity_Historical_Current_Evidence_Matrix_2026-08-31.md`.

### H5c — historical-vs-Quick visualizer reactivity parity audit

**Status: ACTIVE H audit, now concentrated on final performance/freshness and physical closure. Post-R3 physical logs accepted Bubble outline scaling, exposed Bubble wake/ghost presentation multiplication, a Spectrum capture-identity idle race, high-scale geometry/presentation mismatch, and presentation/performance stalls with dedicated observability. The latest apparent Bubble 'dead reactivity' regression is source-disproven: live Bubble pulse/event/radius data remained active, while CUSTOM working-geometry edits caused the bridge to reject fresh revisions for 8-11 s. A CUSTOM-only presentation-rebase repair is implemented and awaits replay. Geometry/reactivity repairs remain authoritative unless their own falsifier fails.**

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
- [ ] Complete Oscilloscope final renderer-input comparison as a control. Post-R3 high-vertical flicker exposed a cross-mode presentation seam: outside CUSTOM, geometry-mismatched snapshots must remain unconsumed so stale geometry never becomes authority. **CUSTOM PRESENTATION REBASE LOG-VALIDATED / ARCHIVED AS R-68:** while an editor session is active, the editor's working rect is the explicit temporary presentation authority. The prior failing run drove Visualizer revision rate to `0 Hz` and snapshot age to ~`8-11 s` because fresh logical snapshots still carried the producer's old presentation record and were rejected. `VisualizerSnapshotBridge.take_for_render()` now rebases only that presentation record while an active CUSTOM session owns working geometry; outside CUSTOM strict rejection remains. The latest extreme Bubble run holds roughly `88-92 Hz` logical revisions with zero geometry mismatches through domains up to about `4.662x8.313` and `2.362x1.000`, proving the remaining visible weakness is a separate scaling-contract defect, not stale snapshot admission. Keep the rebase; still physically compare Oscilloscope for blank/flicker.
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
- [ ] **Bubble extreme-tall head footprint — FIRST CORRECTION PHYSICALLY REJECTED / SCALING CONTRACT RESTORED (R-69):** the first Quick-only `head_radial_scale` capped all head radii beyond ~`1.75x` authored height. The newest operator run proves that was the wrong seam: non-CUSTOM and near-canonical CUSTOM react well, while tall/wide CUSTOM progressively loses visible radius response despite healthy source/simulation metrics. Historical/source contract is explicit that Bubble radius remains a fraction of actual card height and must not inherit `1 / domain` viewport compensation. Remove the global head multiplier and preserve the smooth `0..+1` authored-pixel extreme-size outline bonus. **AWAITING PHYSICAL VALIDATION:** CUSTOM tall/wide reactivity must now match the near-canonical feel. Restoring that binding contract may intentionally make an extreme-tall full-expansion head very large again. That is accepted for this validation checkpoint rather than sacrificing reactivity. If the full-expansion tail remains genuinely oversized, the next correction must target only the proven upper expansion tail (or another source-proven seam), never multiply the entire radius sequence by viewport extent; R-69 records the failed method so it is not retried.
- [ ] **Spectrum extreme-viewport presentation smoothing — IMPLEMENTED / WIDE PHYSICALLY IMPROVED; TALL+ORDINARY FINAL CHECK REMAINS:** the ~`3.59x` vertical run and the 2026-09-01 follow-up extra-wide run were reactive but visually lost smoothness. Spectrum's existing presentation-only one-pole time constant now scales by the larger of `viewport_width/authored_width` and `viewport_height/authored_height`, capped at `4x`; `max`, not axis multiplication, prevents double-smoothing when both axes are large. The newest operator run reports the extra-wide case visibly better. Canonical and smaller cards are unchanged, source/engine bars are untouched, stall-snap remains intact, and no new timer/interpolation owner exists. Reconfirm the extreme-tall case and ordinary-size response before closing.
- [ ] **Bubble Ghost/Decay — PRODUCT CONTRACT DECIDED; FIRST EXTREME-VIEWPORT TRANSFER REJECTED / CORRECTED:** operator wants a slow afterimage fade and confirms the first retained implementation becomes too weak as CUSTOM width/height diverges. BubbleSimulation already projects its three history samples into renderer-normalized content coordinates. The first Ghost pass then incorrectly reused `u_trail_axis_scale`—the separately accepted R4 compact-source correction for the ripple wake—thereby applying a second `baseline/current` suppression to Ghost displacement (about 12% of vertical displacement at the logged `8.313x` height and ~42% on the `2.362x` wide case). Ghost now consumes the normalized history directly while the R4/R5 ripple wake remains untouched. The fade curve is also modestly gentler (`bubble_ghost_decay` still owns faster/slower lifetime; no new setting or cadence). Renderer upload of `u_ghost_decay` remains fixed. No second pass, history owner, timer, scheduler or allocation cadence is added. **AWAITING PHYSICAL VALIDATION:** tall/wide Ghost displacement should remain perceptible and decay more gently without restoring the old excess-ripple clutter.
- [x] Focused outside-Codex source-only checkpoint profiles are GREEN: `16/16` viewport/presentation-coherence contracts plus `7/7` runtime/performance contracts (`23/23` combined). They are supplemental only: this outside-Codex environment cannot replace the maintained full PySide6 profile. The last completed maintained-profile run before R6/R7/Media wiring reported 79/85; the six stale assertion-bearing files are enumerated in `Docs/TestSuite.md` §3A and must be reconciled without restoring retired seams. The exact maintained runner also still needs the three permanent targets named there before the next aggregate claim.
- [x] Rebuild passive `--perf` visibility without a second cadence owner: each display HUD derives scene FPS / `dt_max` / pacer target+skip% / active-or-last transition timing from existing `frameSwapped`; the Visualizer HUD derives Quick draw FPS / logical revision rate / snapshot age / geometry-mismatch count. Text/log aggregation is ~1 Hz and owns no render/update timer.
- [x] Add origin-aware image-change tracing (`timer`, `manual_next`, startup/retry) across queue selection, random-transition resolution, worker scheduling/start, per-display cache/worker source, UI handoff and transition admission. One thread-safe trace crosses UI/compute/UI; no polling/sleeping is introduced.
- [x] Natural-vs-manual cache archaeology: at least one bad natural transition re-prescaled exact display-ready images that had already been warmed and then evicted by deeper speculative prefetch. Protect only the exact predicted next display batch from ordinary LRU eviction; hard item/byte caps remain absolute and can override protection. Log protected count under `--perf`.
- [x] Legacy `GCController` is migration debris: it was never instantiated and its Python-frame disable/enable/manual-idle-GC model does not match threaded Qt Quick. `RuntimeGCPolicy` remains the accepted RUN owner: preserve generation-0 automatic collection, never force `gc.collect()`, observe expensive collections, and restore exact interpreter thresholds/callback state at RUN exit. **R4 PHYSICAL RESULT REJECTS THE CURRENT THRESHOLDS AS SUFFICIENT:** the latest run recorded four gen-2 pauses at ~99.8–134.2 ms, including one zero-object scan. Do not hide this with lower Visualizer cadence; reassess allocation pressure + threshold policy after the R6 Halo physical/log gate while preserving the accepted R5 Bubble/readiness repairs, under the GC target below.
- [x] **R4 CHECKPOINT LOGS/PHYSICAL EVIDENCE RECEIVED AND ASSESSED:** the requested natural/manual transitions and aggressive visualizer extents were exercised. The run isolates Cursor Halo motion as a severe FPS destroyer while ordinary mouse movement with Halo suppressed by the retained context menu is harmless; physically rejects R4 Bubble source-centre compression as sufficient on tall viewports; exposes a post-Settings/CUSTOM prefetch lifecycle hole; and shows gen-2 GC pauses worsening to ~100–134 ms. Spectrum/Oscilloscope/other deterministic prior repairs remain governed by their own falsifiers rather than global choppiness.
- [x] **POST-R4 PERF/POINTER TARGET — R5 attempted hot-path split + duplicate-pointer repair:** R5 removed pointer coordinates from auxiliary-state/root-property publication and made Halo admission blank the native cursor. **PHYSICAL RESULT: PERFORMANCE REJECTED / pointer-coherence behavior retained as useful.** The new run reproduces the catastrophic movement degradation with no meaningful improvement; context-menu suppression still restores ordinary-cursor motion without the collapse. Source audit shows why R5 was insufficient: `QuickDisplayWindow.mouseMoveEvent()` still routes every passive move through `QuickInputController -> RuntimeInputOwner`, which calls live interaction/Ctrl providers; normal interaction-mode resolution reaches the Settings manager under locks/cache lookup, while MC short-circuits `is_mc_build() -> True` and context-menu-active returns before that provider path. Separately, `HoverHandler.point.position -> CursorHalo.x/y` still moves a visible retained QML item and restarts its inactivity `Timer` on every pointer-coordinate change, dirtying the same QQuickWindow scene that owns the Visualizer. R5 optimized only the old auxiliary publication subset, not these two surviving hot paths. **DO NOT REVERT the one-cursor semantic fix.**
- [x] **POST-R5/R6 PERF/POINTER TARGET — PERFORMANCE PHYSICALLY ACCEPTED; VISUAL POINTER PARITY OPEN:** the moving retained-QML `CursorHalo`/`HoverHandler` path is removed from `DisplayScene.qml`. `QuickCursorController` renders/caches the configured shape into the window's native `QCursor`; Qt/the window system owns physical cursor movement, so pointer coordinates no longer move a retained scene item or write scene-root Halo properties. Interaction mode is an event-updated `QuickInputState` fact initialized once at runtime construction and pushed on context-menu Settings changes; cross-display Ctrl truth is event-broadcast by `SharedCtrlCoordinator` using generation-safe `(runtime_generation, screen_index)` keys. During admitted Halo motion `QuickDisplayWindow.mouseMoveEvent()` bypasses `RuntimeInputOwner` entirely and only updates `last_motion_ns`; the remaining controller mouse-move route exists solely for the classic non-interaction >10 px exit gesture. The 2 s inactivity contract uses one armed deadline timer plus a bounded six-step native-cursor fade; the timer is never restarted at mouse polling rate and there is no polling fallback. **R6 physical result:** sustained pointer movement no longer causes any observed Visualizer FPS collapse and the high-refresh display can approach cap under heavy system load. Preserve this architecture. **Open visual falsifier:** the operator sees only an ordinary-looking cursor, not an obvious Halo/custom treatment. Logs report `halo_enabled=True`, `native_cursor_visible=False`, `halo_shape=cursor_light`, `pointer_owner=native_qcursor`; reconcile native cursor artwork/selection/inactivity visually without ever restoring a moving QML cursor or mouse-rate state publication.
- [x] **POST-R4 BUBBLE WAKE TARGET — compact-source repair physically insufficient:** canonical/wide/tall screenshots physically reject R4 source-centre-only sufficiency; vertical is the clear outlier. Preserve Bubble simulation/history/head radius/reactivity and the accepted source-centre compression. R5 adds a Quick-only authored-pixel radial transfer for each source's complete wake: ripple radius/cap and ring spacing now remain baseline-pixel authoritative while whole-card uniform scale stays independent; legacy shader behavior is explicitly identity-gated. The strengthened falsifier measures source displacement + full physical ripple extent at canonical, wide, tall, `2x2`, and approximately `1.724x2.914`. Bubble Ghost/Decay remains separate/open. **IMPLEMENTED R5 / SOURCE-ONLY GREEN / PHYSICALLY ACCEPTED for the tested excess-ghost/motion-tail viewport problem. Preserve.**
- [x] **POST-R4/R5 TRANSITION READINESS TARGET — R7 IMPLEMENTED / AWAITING PHYSICAL VALIDATION:** replace the process-wide `_prefetch_resume_scheduled` latch with a `(runtime_generation, token, reason)` claim. A newer generation supersedes any stale claim even when an old delayed callback is generation-rejected before its body runs. While image/transition work is pending, the claim waits without a periodic recheck; `DisplayManager` now reconciles whole-batch completion *before* emitting `transition_completed`, so the final authoritative completion event schedules the existing post-transition cooldown/resume. Direct replacement first-frame publication also closes its batch before `authoritative_first_frames_ready`, so runtime-ready reseeding cannot wait for a transition event that will never exist. One legitimate remaining cooldown delay is allowed; there is no ~100 ms transition-pending poll loop. Preserve exact-next protection and hard cache bounds. **Physical/log gate:** every replacement generation that logs `runtime_ready_reseed` must subsequently schedule useful exact-next warmup; no stale latch and no transition-pending rearm storm.
- [ ] **POST-R4/R5/R6 GC TARGET — FUTURE + PER-FRAME DEEP-SNAPSHOT CHURN REMOVED; RETAINED STATE MEASURABLY HELPS, DEEP-PAUSE ROOT STILL OPEN:** the original ~6.5 min RUN submitted ~`26,220` `visualizer.audio_analysis` Future/task jobs and logged gen-2 pauses `94.66`, `123.09`, `85.78 ms`. The long-lived serial compute lane removed that task/Future churn without queue depth or fallback. The first lane run still deep-copied the worker NumPy/history/transient graph every frame and showed `(4489, 214, 4)` collections over ~227 s with gen-2 max `107.02 ms`. Retaining one detached DSP state across ordinary serial-lane frames, rebuilding only across fenced gate/activation/config/reset boundaries, is **logically validated and worth keeping**: the cleaner ~332 s run completed `22616/22616` lane steps, `dsp_state_reuses=22602` vs `rebuilds=14`, zero generic executor tasks/busy/stopped/callback failure, mean execution ~`1.668 ms` and handoff ~`2.074 ms`; GC was `(4050, 192, 3)`, about `12.2` gen-0 collections/s and ~`0.54` gen-2/min, but still paused `68.14`, `117.58`, `79.96 ms`. The newest ~178 s aggressive CUSTOM/recreation stress run keeps the lane healthy (`11643/11643`, `dsp_state_reuses=11638`, rebuilds `5`, mean execution ~`1.826 ms`) yet reports `(3420, 163, 3)` collections and gen-2 pauses `99.49`, `112.71`, `112.88 ms`. That stress run is not a clean A/B for one small per-request allocation because it includes four runtime recreations and its gen-2 collections reclaim hundreds-to-thousands of objects. `_smoothed_bars` is mutated in place by the silence/decay path, so keep the small stable `tuple(self._smoothed_bars)` correctness snapshot until evidence justifies a different ownership buffer. Threshold policy remains untouched. The technical-config repair for `kick_lane_gain` / `spectrum_lane_transient_mix` and state-epoch fencing remain binding. **NEXT GC WORK:** preserve reaction cadence/freshness, use the next cleaner run plus lifecycle/object evidence to identify the next retained/cyclic allocation source before any threshold tuning.
- [x] **IMAGE-CHANGE / TRANSITION INTEGRITY — R7 CORE IMPLEMENTED; NATURAL/MANUAL PERF CHECK ACCEPTED / FINAL PHYSICAL SEAM GATE REMAINS:** the `22:46:59` timer+manual overlap proved the old replacement contract could snap an active run to destination and then reuse its cached batch spec. `_try_begin_image_change_work()` is now the transactional gate used before `image_queue.next()` / history mutation: if loading, pending batch, running transition, or batch opening is unavailable, the request is rejected without advancing image truth. `_present_quick_image()` no longer cancels an active transition for replacement and treats reaching publication with one active as an invariant error. Once a source image exists, `resolve_quick_transition_spec() -> None` withholds the destination and fails loudly instead of direct-publishing it; direct publication is reserved for the legitimate no-source first frame. Perf tracing now distinguishes `base_image_published` from `transition_started`. A coalesced extra intent is not required for correctness: timer/manual may simply be skipped while the transaction is busy. Follow-up logs show non-startup timer transitions (~`253-330 ms`) and manual Next transitions (~`269-314 ms`) in the same broad completion range; there is no evidence of a separate slow natural-transition path. Operator reports no returning black flash. **Remaining physical gate:** hammer overlap still must preserve zero bare flashes/snaps, zero transition-spec mismatch, and admitted-only queue/image truth while the separate R-63 seam reaches zero.
- [ ] **R-63 / ONE-PIXEL SEAM — DEVICE-SPACE ROOT CAUSE PROVEN; BLACK=0 OVERSCAN MUST REMAIN:** the one-edge logical repair preserved the PresentMon-proven non-exact-cover anti-fullscreen-flip principle and operator still reports no returning black flash, but the intermittent seam moved to Display 1's left edge. The new one-shot native telemetry now explains it exactly. Screen 0 reports `window_device=(0,-2,2561,1442)` against `monitor_device=(0,0,2560,1440)`, while screen 1 begins at device `x=2560`. The intended top-only logical overscan therefore acquires an unintended **+1 device-pixel right overlap** through mixed-DPR logical->native rounding (`1707 logical * 1.5 = 2560.5`). Screen 1 itself has no left overscan. This matches the observed single seam pixel. **Do not remove or shrink R-63 overscan generically.** The next repair must preserve the non-exact-cover/native-composition protection while correcting only the rounded shared device edge, then physically prove both `black=0` and `seam=0`. No speculative edge change is included before that device-space-safe implementation is justified.
- [x] **CUSTOM Save/Continue apparent "crash" — CLEAN EXIT / CLICK-THROUGH CONFIRMED AND FOLLOW-UP CLEAN:** the earlier session did not crash: immediately after `save_continue`, retained Reddit admitted `open_url`, then Exit was requested and the process ended normally with code `0`. The bounded runtime-pointer suppression guard is now armed before overlay removal and Reddit admission independently respects it. In the newest replay the logs explicitly suppress `mousePress`, `mouseDoubleClick`, `mouseRelease` and a later `redditOpenRequested` during the retirement interval, with no unintended URL/Exit recurrence. Passive mouse movement remains untouched for R6. Keep the diagnostic seam but do not hold H open for this unless it reproduces.
- [ ] **PERF HUD `dt_max` semantics:** very large multi-second values in this run occur primarily on demand-light displays with `viz_mode=none` and scene FPS around `0.7-2 Hz`; the HUD currently measures the longest interval between `frameSwapped` events, so an intentional no-demand gap is reported like an active rendering stall. Active Visualizer samples are instead tens of ms with occasional ~`100-205 ms` spikes. Treat multi-second idle `dt_max` as telemetry ambiguity, not proof of an 8 s render block; retain the active spikes as real contention evidence. Do not add a timer merely to make this metric look smaller.
- [ ] **PERF HUD `skip` semantics / residual schedulability:** `skip` is the fraction of *target pacer deadlines* already overdue when `QuickFramePacer` services them and therefore collapsed into one freshest `window.update()` instead of issuing a catch-up burst; it is not a direct GPU dropped-frame percentage. At `164.835 Hz` one target interval is only ~`6.07 ms`, so ordinary event-loop lateness produces a much larger skip percentage than on the 60 Hz display. Latest non-idle screen-0 samples have median skip ~`7.2%` and p90 ~`33.5%`; screen 1 median is `0%`. Keep using it as a main-thread/scheduling contention signal alongside scene FPS, `dt_max`, Visualizer revision age and event-loop late percentiles, not as a standalone frame-loss metric.
- [ ] Performance watch for J/H validation: R6 Halo remains exonerated from catastrophic cursor scene pressure. The retained DSP-state cut materially reduced allocation/GC pressure in the cleaner A/B, but gen-2 still reaches ~`113-118 ms`; do not call GC closed yet. The latest Bubble run is also a useful discriminator: revision rate/snapshot age remain healthy while visible response collapses only as CUSTOM viewport extent diverges, proving **presentation scaling can fail independently of source freshness**. High-refresh pacer skip remains a scheduling-contention signal rather than literal dropped-frame percentage, and active Visualizer `dt_max` spikes remain distinct from multi-second demand-light no-swap gaps. Media event ownership remains healthy. Treat authored Visualizer cadence, presentation scaling, presentation freshness, scene scheduling, GC, image readiness, transition rendering and background-service contention as separate multiplicative axes.
- [ ] **J performance-history boundary:** viewport-scaling work already present at the outside-Codex SHA may itself have changed GPU/presentation cost. This source ZIP has no trustworthy pre-scaling A/B, so do not assume the handoff state was performance-neutral; when Git/history and comparable logs are available, compare the pre-scaling boundary against `61decb33f6ebb107b2997928077e9d56d5faa8a1` before blaming later H5c repairs.

Detailed live checklist and repair sequence: `Docs/QtQuick_Migration/H5c_Visualizer_Reactivity_Parity_Audit_Decomposition_2026-08-31.md`.  
Exact historical/current evidence matrix and next source paths: `Docs/QtQuick_Migration/Visualizer_Reactivity_Historical_Current_Evidence_Matrix_2026-08-31.md`.  
Safety checkpoint / applied-vs-pending handoff: `Docs/QtQuick_Migration/H5c_Implementation_Checkpoint_2026-08-31_R3_Outside_Codex.md` (R2 remains historical evidence).
Latest image/surface integrity checkpoint: `Docs/QtQuick_Migration/H_Image_Transition_Prefetch_Seam_Checkpoint_2026-08-31_R7_Outside_Codex.md`. R6 Cursor Halo remains the accepted pointer-performance checkpoint; R5/R4 remain historical evidence.

### HIGH PRIORITY H/J bridge — event-driven Media runtime; active high-frequency polling retired

**Status: IMPLEMENTED at repo commit `2e7a9242`; deterministic gates GREEN; now corroborated by both the earlier short smoke and the 2026-09-01 long diagnostic run; broader provider-switch/frozen validation remains open.** The old `1000 -> 2000 -> 2500 ms` active poll and 5s/30s idle stages are retired. The existing single `_SharedMediaRuntimeOwner` remains the sole query/snapshot owner; native GSMTC dirty edges now feed that same accepted-snapshot path, with one ~30s reconciliation/liveness watchdog. Latest summaries again report `stale_rejected=0`, `missed=0`, `degraded=False`; operator-observed reactions were prompt. The numerous event refreshes are timeline/event edges, not evidence that the fast polling ladder returned.

Durable architecture: `BaseMediaController` exposes a narrow presentation-neutral observation contract; `WindowsGlobalMediaController` retains the GSMTC manager + provider-matched session and owns their add/remove event tokens; native callbacks do no query/decode/presentation work and are generation-fenced before handing a tiny dirty reason to the shared owner. The shared owner hops to the UI thread and coalesces to at most one refresh in flight + one pending dirty edge, unified with command confirmation. Timeline-only events are bounded by an event-armed coalescing floor, not a recurring cadence. Observation failure is loud `[MEDIA_EVENT][DEGRADED]` and watchdog-only — the fast poll never silently returns.

Short installed run evidence (2026-08-31 23:57–23:59): four observation lifetimes all logged `Native GSMTC observation established ... session_bound=True`; real Spotify timeline/playback edges arrived; summaries were `stale_rejected=0 missed=0 degraded=False`; the QML capture recorded zero messages; repeated Settings reconstruction and final exit completed normally. This is enough to absorb the architecture, not enough to close its broad physical gate. The one ~2.2s slow Media warning is activation wall time (`worker_ms≈46`), not a resurrected steady-state one-second poll stream.

Closure / safety checklist:

- [x] Exact installed WinRT event/token/threading reality proven before production wiring.
- [x] Presentation-neutral controller observation contract; no second Media owner/model/query path.
- [x] Manager/session token ownership, transactional rebind and generation fencing.
- [x] Event storm coalescing; command confirmation converges on the same owner.
- [x] One slow reconcile/liveness watchdog with `[MEDIA_EVENT][MISSED_EVENT]`; no silent fast-poll fallback.
- [x] Short installed repeated-recreation smoke: observation re-established every generation, real events received, `stale_rejected=0`, `missed=0`, `degraded=False`, zero QML messages, clean exit.
- [ ] **AWAITING BROADER PHYSICAL VALIDATION:** repeated dual-display Settings + CUSTOM Save/Continue/reload, explicit provider switches, installed/frozen build and clean app exit show no late native callback/native termination, stale-generation snapshot, leaked token or unexplained `[MEDIA_EVENT][MISSED_EVENT]`; track/playback/timeline remain prompt, artwork still publishes into the active-engine `MediaArtworkImageProvider`, and cross-display Visualizer playback binding remains intact.
- [ ] Keep the known boundary visible: a configured provider that is playing but never current/selected may rely on the ~30s watchdog until session/current-session churn promotes it; do not conceal that with a restored fast poll.
- [ ] Separate cleanup candidate only: `WindowsGlobalMediaController.is_app_process_running` + `_win_*_process_exists` / `get_provider_process_exe_names` are now unused by production after idle-poll retirement. Remove only in a bounded cleanup slice.
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

**Status: implementation + deterministic gates GREEN; operator physically validated H8 cycling/recreation on 2026-09-01. Full stale-test reconciliation remains an H re-closure task, not a reason to reopen the runtime contract.**

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
- [x] Operator physically validated middle-click preset cycling, Custom round-trip and recreation behavior on 2026-09-01. Tests have not been rerun against the later source tree yet; reconcile them at the final H test-correction gate.

Technical route: `Docs/QtQuick_Migration/H8_Visualizer_Middle_Click_Preset_Cycle_Decomposition_2026-08-30.md`.

### H9 — CUSTOM ordinary-widget uniform resize contract

**Status: IMPLEMENTED in `c038f66c`; deterministic H9 gates GREEN; operator physically reports the sizing contract is vastly superior and the catastrophic non-uniform resize behavior is no longer the active failure. Keep Save/recreation/containment as final correctness checks. J owns the remaining composition/alignment polish and Media's separate app-volume-child parity. Do not revert to partial Settings-like payload scaling to chase those visuals.**

Original physical defect: Reddit wheel/corner resize could produce a narrower committed shell while rows escaped below/outside it, and Save/reinit faithfully replayed that broken state. Media resize changed the shell but pulled metadata/artwork/chrome toward new container centres and altered observable spacing instead of uniformly enlarging/shrinking the authored presentation.

Implemented mechanism:

- `OverlayWidget.qml` owns an opt-in `uniformScaleTransform` and derived `presentationScale`. Opted-in families lay out the whole authored card once at baseline size inside one retained root and scale that root uniformly using the assigned outer rect / preferred-size relationship. Text, spacing, rows, artwork, chrome, borders/shadows and hit geometry therefore move together.
- The scale remains **derived presentation**, not persisted authority: Python/session still owns the outer rect. There is no QML->Python size feedback, second geometry owner, timer, poll or fallback.
- Reddit/Reddit2, Media **and Gmail** opt in. Their authored family sizing remains Settings-owned; stale pre-H9 `font_size`/`artwork_size` payload is ignored where applicable and the retained presentation derives one scale from the committed outer rect. Gmail's fixed header/row minima now shrink with the card instead of escaping below it.
- Ordinary CUSTOM resize owns one private absolute `_custom_resize_scale` metadata value with a shared **40% floor**. Save/recreation/CUSTOM re-entry restores that absolute scale instead of rebasing an already-shrunken committed rect to `1.0`, so repeated sessions cannot compound the minimum toward zero. Existing H9 geometry-only Reddit/Media entries and pre-migration Gmail entries infer their current absolute scale once from committed geometry vs authored `preferredContentWidth/Height`, then persist it on Save. Visualizer's separate `visualizer_rect`/viewport contract is explicitly excluded.
- Weather/Steam/Clock remain on their existing family payload contracts for now; the same absolute CUSTOM scale metadata/floor applies to ordinary session geometry without converting them into second geometry owners.
- New `tests/test_qtquick_h9_uniform_resize.py` provides 8/8 deterministic falsifiers and the broad H9-affected surface (~285 tests) passed in the normal project environment.

Physical closure falsifiers:

- [x] Deterministic: whole retained Reddit/Media presentation scales as one relationship; geometry-only replay contract covered.
- [x] **Physical final check — Reddit/Reddit2:** operator reports ordinary-family scaling is working exceptionally well after the absolute-floor/uniform-transform repair. Residual alignment/dead-space polish is J, not H9.
- [x] **Physical final check — Media:** operator reports ordinary-family scaling is working exceptionally well after the uniform-transform repair. Remaining artwork utilisation, frame thickness, refresh/header placement and alignment are J visual parity.
- [x] Preserve single Python/session geometry authority, cross-display transfer, Cancel, layout slots, family enable state and current Visualizer scale-vs-viewport contract.
- [ ] **Physical final check — Gmail / HEIGHT CONTAINMENT FIXED, EDIT-WIDTH REGRESSION CORRECTED / AWAITING REPLAY:** uniform preview scaling and the shared absolute 40% floor remain good, and adding shell compensation fixed the post-reinit bottom escape. The latest operator run then exposed a narrower regression: CUSTOM's editable shell reported extra width and could not align with peers. Source audit confirms `gmailModel.contentWidth` is already the authored outer-card width, while only the row-derived `contentHeight` excludes shell inset. `GmailPresentation.qml` therefore reports `preferredContentWidth: gmailModel.contentWidth` unchanged and adds `shellInset` only to preferred height. Re-run align/resize -> Save/Continue -> recreation -> CUSTOM re-entry and require both truthful edit width and contained rows/header/text, with no scale compounding below 40%.
- [x] **Shared floor replay check — ordinary families:** operator reports the other widget families scale exceptionally well with the persisted absolute floor; no cumulative shrink/distortion complaint remains. Gmail recreation containment is the one active H9 falsifier below.
- [x] Weather remains outside the retained uniform-transform opt-in. The separately observed intermittent `preferredContentHeight` QML binding loop is **carried to J geometry/parity acceptance**, not an H9 blocker, unless future evidence shows it corrupts committed geometry or lifecycle before H closes.

### H7 — Exit visible-response/performance classification

The current clean run routes Exit immediately and completes the terminal Quick barrier in ~250 ms. Script-mode recursive `__pycache__` cleanup then consumes additional terminal time.

Operator physically validated H7 visible Exit response on 2026-09-01. Legal retirement remains ~250 ms-class and subsequent developer/cache housekeeping is not an H lifecycle blocker. Keep any script-mode cleanup optimisation in J/cleanup rather than reopening exit ownership.

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

**Kept:** production proof-colour-band removal (opt-in only); `[QUICK_SURFACE]` telemetry (passive); real-image readiness semantics (`intentional_base_frame_ready`) independent of the removed show gate. The old `tests/test_qtquick_black_flash_contract.py` reference is not current test-tree authority; current R6/R7 source bars live in `tests/test_runtime_perf_policy_contracts.py` and physical R-63/PresentMode evidence remains mandatory.

**Failed approaches (physically disproven — do NOT retry):**

- [x] Persistent scene graph + graphics (`setPersistentGraphics/SceneGraph(True)`) — operator saw no change; telemetry: SG is never invalidated mid-flash, so persistence cannot matter.
- [x] Event-driven surface-refresh redraw on activation/menu (`BackgroundRenderItem` refresh + `QQuickWindow.update()`) — did not improve focus/menu flash. Removed.
- [x] Deferred first-show (gate native show on first image) — made startup visibly worse (image -> black -> image). Removed.
- [x] VSync ON (`swapInterval=1`) alone — no reliable reduction; single-run counts are inside a large launch-to-launch variance band.
- [x] Drop `SplashScreen` role — non-deterministic: identical code gave 0 flashes one launch, 15 the next (both operator-corroborated). Not a reliable fix.
- [x] `WS_EX_NOACTIVATE` / `WindowDoesNotAcceptFocus` / DWM-transition-disable / Ctrl-poll replacement — PROHIBITED (feature loss); never a valid endpoint.

**Solution (measured + operator-confirmed):**

- [x] Coverage-preserving non-exact-cover overscan (`QuickDisplayWindow._fullscreen_compat_geometry`). PresentMon proof established the R-63 principle: exact-cover baseline produced `Hardware: Legacy Flip` transitions with black/stale frames, while overscan kept composition stable with black=0. **R7 refines the geometry from all-edge overscan to one virtual-desktop exterior edge** to stop perturbing a mixed-DPR shared seam while still remaining larger than the exact screen rect and losing no visible pixel. The original anti-flip evidence remains binding; the refined shape must re-pass `black=0` plus seam=0 physically.

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
- [x] CUSTOM Visualizer can own a different selected display from Media while non-CUSTOM still follows Media (H5a — operator validated 2026-09-01; final tests still to rerun)
- [x] Spectrum has non-degenerate data + canonical topology + restored engine-shaping/render-transfer parity after switch/recreation (H5b — operator validated 2026-09-01; final tests still to rerun)
- [ ] historical-vs-current visualizer reactivity audit closes the live-consumer config gaps, Bubble weak response, Play/Pause edge delay and Sine idle transport without adding clocks/owners/global tuning (H5c)
- [ ] CUSTOM Settings locks only size-authoring controls (H6)
- [x] middle-click hotswaps exactly one preset in-place, lossless Custom round-trip, no mode change / no Media disturbance (H8 — deterministic GREEN + operator validated 2026-09-01; final tests still to rerun)
- [ ] ordinary CUSTOM resize contract is physically strong across families and absolute-floor replay is accepted; Gmail Save/reinit containment remains the sole active H9 falsifier
- [x] Exit visible response measured/understood with clean natural termination (H7 — operator validated 2026-09-01)
- [ ] unexpected `screensaver_qml.log` warnings/errors on these paths reconciled
- [ ] maintained `h-destination` fully GREEN after current source/test reconciliation (last completed pre-R6/R7/Media run: 79/85 historical only; exact six stale assertion-bearing files plus the three missing permanent runner targets are listed in `Docs/TestSuite.md` §3A; do not claim a new aggregate until that exact reconciled profile runs)
- [ ] every unresolved ledger row whose phase includes H is closed or explicitly carried to J with evidence
- [ ] historical bug archive reconciled before H closure/test-correction handoff: R-64 Cursor Halo, R-65 transactional image/prefetch, R-66 Media event ownership, R-67 absolute CUSTOM resize/re-entry, R-68 CUSTOM Visualizer presentation-authority rebase, and R-69 failed Bubble extreme-viewport global radius/Ghost compression now exist. Do not bury later validated incidents only in this plan: Gmail recreation/edit-dimension containment and the eventual GC allocation-pressure root fix need durable records once their current corrections physically validate. R-69 already records the Bubble extreme-viewport failed correction before final acceptance because failed methods are binding historical evidence, not disposable scratch work. R-63 itself should absorb the final mixed-DPR device-edge seam lesson when closed rather than spawning a duplicate incident.
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

**Binding J visual authority is the paired repository oracle** under `images/migration/Ideal (PreMigration)/` versus `images/migration/Current (PostMigration)/` for every covered family; inspect that pair first and treat the Ideal image as the visible target for details it actually shows. The 4.7.2/4.7.0 release screenshots are secondary broad-composition references, and `15099d3` remains useful for older UI/presentation archaeology. **Visualizer reactivity is a specific exception:** the user-supplied `3fe5df6` tree is the known-good pre-Qt-Quick behavioral oracle for Bubble/Oscillo/Sine/Spectrum/DevCurve semantics. Historical code is never implementation authority; reproduce its behavior through current Quick owners.

**Front-load the visual oracle work in J when the acting model/agent can inspect images reliably.** For the six covered ordinary families (Abandonment Issues, Achievement Pulse, Gmail, Media, Reddit, Weather), paired-image comparison is an early mandatory J tranche, not end-of-phase polish. An agent with weak/unreliable vision may briefly defer implementation to a vision-capable pass, but it may not downgrade, replace, or close these cells from prose alone; the paired Ideal images remain the highest authority and must be physically reconciled before J closes.

**CUSTOM/Edit alignment/snap guide lines are also a mandatory J parity restoration.** The visible guide lines that existed pre-migration are currently absent in Quick Edit mode even though guide presentation/seams exist. Restore useful centre/peer/edge/safe-gutter relationship lines through the existing Python snap/layout authority; do not create QML geometry truth or a second layout owner. This is no longer a low-priority affordance.

Named J cells include:

- startup/focus/context-menu/transition black flash and apparent test-colour-band flash — recurring/activation flash SOLVED (`R-63` overscan); residual startup micro-flash + reveal work decomposed under "Reveal / startup composition";
- actual gentle reveal/fade — including the visualizer-does-not-fade-in bug and the desktop -> application crossfade aspiration (see "Reveal / startup composition");
- Media Parity+: proportions, **make artwork larger/use available card space rather than leaving avoidable dead area**, thinner artwork border/frame, **artwork change fade**, header/control-strip balance, optional metadata, and restore refresh-button parity at the card's top-right/outside the provider header rather than embedding it in the header;
- **Media exception is narrow:** preserve the current post-migration transport/control bar because it is the only current Media visual treatment explicitly judged superior to the old one. Do not use that exception to preserve the rest of the current Media composition by default;
- Media-dependent app-volume child widget: its established/default presentation is a separate adjustable adjacent/outside item with its own geometry; an integrated form is optional only when explicitly selected;
- Gmail clipping/refresh/header alignment;
- all ordinary-family logos + header text must share coherent baseline/vertical alignment across Media/Reddit/Gmail/Weather/Steam/Clock where present **and must scale with the widget/card rather than remaining effectively fixed-size while the card grows/shrinks**. Treat logo + provider/family name as one authored header relationship; do not solve family alignment/scaling with duplicated per-family shell owners;
- Reddit Parity+: reduce unnecessary dead horizontal gap between the age/time column and post-title column while preserving legibility, truncation and the now-correct uniform resize/containment contract;
- Weather resize geometry: the intermittent `WeatherPresentation.qml` `preferredContentHeight` binding loop observed during scaling is **J geometry/parity debt by default**. Source-localize the cycle and require repeated resize + Save/recreation with zero binding-loop warnings before Weather J acceptance; only pull it back into H if it demonstrably corrupts functional/committed geometry before H closes.
- Achievement Pulse packing/icon/count allocation;
- one coherent visible pointer treatment (no OS cursor + halo duplication);
- ordinary non-CUSTOM free-space composition, especially Media + Visualizer, without dog-piling;
- CUSTOM overlap/cross-display authority untouched by ordinary collision avoidance;
- coherent context-submenu hover-leave lifetime;
- context-menu colours must resolve from the active theme rather than remaining stuck on a single palette; preserve one theme authority and avoid a menu-specific duplicate palette owner;
- all-five visualizer eyes-on fidelity after H restores Spectrum data/topology;
- after H5c restores functional historical reactivity/timing, any remaining Bubble fine visual feel/parity without sacrificing BTF or its currently good partial resizing;
- mixed refresh/DPR, off/wake, A->B->A focus/topology, installed performance tails and clean exit;
- **CUSTOM/Edit alignment/snap guide parity:** restore the missing visible alignment lines early in J; existing grid/guide presentation must actually publish useful centre/peer/edge/safe-gutter relationships during editing and clear them transactionally; do not invent a second layout owner;
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
