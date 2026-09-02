# Current Plan — Qt Quick Production Migration

Last updated: 2026-09-02

## Current checkpoint

**PHASE H CLOSED. PHASE I ACTIVE.**

The production Qt Quick authority cutover, post-cutover functional/runtime correction work, and heavy-load H performance acceptance are complete at the current source checkpoint. The detailed H acceptance record is preserved in:

- `Docs/QtQuick_Migration/H_Phase_Closure_2026-09-01.md`
- `Docs/Historical_Bugs/README.md`
- `Docs/QtQuick_Migration/Post_Cutover_Operator_Observation_Ledger_2026-08-30.md`
- `Docs/Guardrails/Performance_Optimization_Contract.md` — canonical post-H performance admission/acceptance rules and modest/heavy reference envelopes.
- `Docs/Tooling_Audit_2026-09-01.md` — current I keep/delete/migrate authority for operator tools; production/tool boundary is protected by R-72.
- the superseded H5c/R6/R7 checkpoint documents retained for provenance.

Do **not** repopulate the active work queue with hundreds of stale completed H sub-items. Preserve H as a compact **completed checklist** here and keep the detailed evidence in its closure/historical records. If later evidence falsifies an accepted H contract, reopen the smallest demonstrated owner/incident and repair it; do not revive H wholesale.

**Checklist discipline is mandatory:** every phase in this plan has an explicit checkbox list. Completed phases keep a compact checked closure list; the active phase owns detailed actionable checkboxes; queued phases keep enough unchecked acceptance/work items that the next agent can enter them without reconstructing intent.

### Test-run qualification at H closure

The complete test tree was reconciled against current production/source authority. The closure environment has `pytest` and NumPy but does **not** have PySide6 or PyOpenGL, and `tests/conftest.py` imports PySide6 unconditionally. Therefore no new Qt aggregate pass count is claimed here.

The canonical maintained destination profile is now:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

`h-destination` remains a temporary compatibility alias only. The **first Phase-I gate** is to run `destination` in the normal project environment with PySide6/OpenGL available. A red is evidence to classify; it is never permission to restore a deleted QWidget/GL owner or a retired fallback.

### 2026-09-02 checkpoint user-environment validation gate

The 2026-09-01 `98/98` destination result below is historical evidence for that checkpoint, **not** validation of the current 2026-09-02 tree. The stacking/theme/wheel/dispatch checkpoint adds permanent regression bars and materially changes retained presentation/layout source, so the current tree requires a fresh destination run in the normal user environment:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

- [ ] **Run the refreshed `destination` profile in the user environment (PySide6/OpenGL available).** The maintained profile now explicitly includes `test_media_external_volume_contract.py`, `test_widget_stacking_display_plan.py`, `test_quick_authored_layout_mode_contract.py`, and the focused retained-menu Settings click-through regression `test_reddit_exit_logic.py::TestContextMenuClickThroughSuppression::test_menu_action_arms_pointer_guard_and_reddit_open_is_refused`. `test_qtquick_gmail_presentation.py` was already a destination target and contains the Gmail-side suppression regression.
- [ ] **Classify any new red; do not weaken the contracts to recover green.** The three source/pure contract files are already green in the checkpoint environment; the Settings-action regression and the existing Qt/QML Gmail regression require the normal PySide6 environment.
- [ ] **Keep physical acceptance separate from automated green.** The `[~]` items below for smart stacking/CUSTOM dormancy, Media/Visualizer wheel routing, Widget Theme/Card Surface application, and related retained visual behavior remain AWAITING PHYSICAL VALIDATION until exercised in the real application.

## Non-Blocking Auxiliary Work — live session queue

This is the high-visibility owner for bounded parity/polish issues being worked alongside I/J. These items do **not** block unrelated architecture work, but they must not disappear into chat history. Status discipline is strict: `[ ]` open, `[~]` implemented/analysed but **AWAITING VALIDATION**, `[x]` only after operator validation or a purely non-visual evidence task is conclusively closed. Do not promote `[~]` to `[x]` merely because source/tests look plausible.

- [x] **Bubble lifecycle fades — keep them.** Operator likes the fades visually, and paired logs show the recurring hitch class predates the fade slice: every sampled Gen2 collection aligned with a Bubble wall-clock gap while Bubble compute/FPS/cadence counters stayed healthy. The fades are scalar opacity/lifecycle state only and are not an evidence-backed removal target.
- [ ] **Bubble hitch root cause — J performance debt.** Attribute both GC-correlated and remaining non-GC stalls without lowering authored cadence/reactivity. New evidence: sampled Gen2 pauses around ~41–68 ms align with Bubble wall-clock gaps, newer/lighter-run Gen2 events can collect zero objects, and rolling/internal Bubble counters can miss the stop-the-world interval. Preserve this evidence in the performance guardrails and instrument pause/wall-clock attribution before changing collector policy.
- [x] **Card Shadow Extra Offset opposite-edge invariant.** Operator physically confirmed the third R-73 geometry mechanism no longer steals shadow coverage from the opposite edge when Extra Offset grows in the selected direction.
- [x] **Card shadows must never overpaint sibling widget content.** Operator physically validated the display-level ordinary-shadow underlay: close/overlapping widgets no longer allow a later sibling shadow to paint over earlier card content. R-74 owns the mechanism.
- [~] **Visualizer global card-shadow projection — AWAITING VALIDATION.** Retained Visualizer receives global shadow enabled/color/opacity/blur/direction/Extra Offset without per-tick settings polling; verify its physical card shadow and directional growth independently of the ordinary-card underlay slice.
- [~] **Clock separator parity — AWAITING VALIDATION.** Shared analogue/digital separator now targets 80% of text alpha, keeps the mode-neutral 1–8 px thickness contract, and has its own cheap retained hard shadow driven by the global text-shadow color/direction/offset (no MultiEffect/layer capture). Also validate analogue placement remains ~20% closer to the face without footer overlap.
- [ ] **Text-shadow extension option.** Keep the current cheap duplicate-glyph shadow as default. If a continuous/extruded directional text shadow is desired, implement a bounded duplicate-glyph trail rather than MultiEffect; do not add soft blur/offscreen capture casually.
- [~] **Startup widget flash-proof gate — Visualizer skip FIXED + PHYSICALLY VALIDATED; ordinary-family flash not reproduced (watch).** Instrumented single-display `main_mc` runs proved the orchestration was correct (ordinary roots created before prime, riding `fadeOpacity * startupRevealOpacity`) and isolated the only "skip" to the Visualizer: its GL bars are a custom `QSGRenderNode` that ignored the QML root's inherited opacity (so `startupRevealOpacity` faded only the card shell while the bars popped), and its authored scene fade was never wired into the Quick presentation. Fixes (Qt Quick-native, no legacy QWidget/`ShadowFadeProfile`/`push_spotify_visualizer_frame`): (1) `node.py` folds `inheritedOpacity()` into `content_fade` at the single render seam, only while fading; (2) `quick_display_visualizer_owner.py` eases `scene_fade` 0→1 once per activation via the pacer-driven `sync_present` + clock (no new timer). Operator confirmed the Visualizer now fades in cleanly with the cohort. Regression bars in `tests/test_qtquick_visualizer_fade_authority.py`. See `Docs/QtQuick_Migration/J_Reveal_Startup_Composition_Decomposition_2026-08-31.md` Area 1.
- [x] **Desktop -> first wallpaper -> synchronized widget reveal — PHYSICALLY VALIDATED.** The earlier "no crossfade at all" was a prior build; current source crossfades correctly. Cold runtime only (`runtime_generation == 0`): each selected `QScreen` is captured once before any Quick window is shown and published only as retained staging state (into `scene_controller.presentation_image`, so the first wallpaper resolves the crossfade branch, not direct-publish). Fixed 1300 ms retained Crossfade; only all-display finalization starts the shared reveal. R-63 non-exact-cover/1 px overscan preserved; no recurring timer/cover window/second surface. Operator + `[STARTUP_DESKTOP]` logs confirm the desktop→wallpaper crossfade. Watch multi-display cold starts for consistency.
- [~] **Edit-mode X / close-button contract — SLICE 5 ALIGNMENT IMPLEMENTED / AWAITING VALIDATION.** Session-local behavior remains unchanged: duplicate -> remove only that duplicate; singleton ordinary/casual widget -> working OFF only; Save commits; Cancel restores; no immediate provider destruction/persistence. The retained edit overlay now receives the session-owned absolute `resize_scale` and places every widget's X on the shared authored 32 px header/logo/refresh centreline after CUSTOM scaling instead of the old fixed `y: 8`; the same row is used for families with no refresh accessory. Gmail and Reddit are the only retained refresh-glyph families and both now render the refresh glyph at 70% opacity. Physically validate ordinary and enlarged/shrunk CUSTOM widgets before closure.
- [~] **Non-CUSTOM smart stacking + Media/Visualizer adjacency — SOURCE-COMPLETE / AWAITING PHYSICAL VALIDATION.** The retained Quick runtime now reconnects the existing presentation-neutral stacking architecture at `QuickDisplayPresenter`. When authored stacking is enabled, ordinary cards are packed deterministically across the full display rather than only one vertical lane: authored slot first, same-column neighbors next, then other canonical slots, then bounded edge-derived free gaps. A 10-card all-Top-Right stress case resolves collision-free in the pure planner; genuinely overfull displays fail explicitly instead of looping or adding a background solver. **CUSTOM is global, not a per-widget exception list:** authored stacking and the stronger Media/Visualizer adjacency subsystem are wholly dormant when (1) any persisted/effective family route is `Custom`, (2) the live retained Edit Layout transaction starts, or (3) a number-key saved-layout load begins its fenced runtime rebuild. Entering the live transaction disables authored layout before session geometry capture; disabling detaches the Media geometry observer/fixed obstacles and restores unstacked/base card rectangles. An uncommitted Visualizer returns to Media's plain authored slot while CUSTOM is active, so overlap remains legal without falling back to `(0,0)`; a committed Visualizer CUSTOM rect remains authoritative. Cancel re-enables ordinary layout only when persisted settings are globally non-CUSTOM, reinstalling adjacency/reflow once; Save and slot-load keep the retiring generation dormant for recreation. Media+Visualizer is otherwise a stronger independent ordinary relationship: Media remains fixed at its authored ordinary rectangle, Visualizer resolves to the vertical side with more usable space (top Media -> below, bottom Media -> above; horizontal fallback only when neither vertical side fits), and the pair is reserved as a fixed obstacle for other ordinary widgets. If the Media card is disabled, Visualizer still follows Media's authored ordinary anchor using its own current outer size and is reserved alone for optional stacking. Media preferred-size changes update the pair obstacle and trigger one authoritative reflow, not a duplicate pass. Reflow is event-driven only by preferred-size/topology/pair changes; no timer, worker, polling loop, per-frame callback, or cadence owner was added. Focused Qt-free theme/semantic/stacking/wheel/CUSTOM-boundary validation is green `55/55`; Qt/physical placement remains **AWAITING TEST VALIDATION** because PySide6 is unavailable in the current container.
- [~] **Whole-Media + Visualizer app-volume wheel routing — SOURCE-COMPLETE / AWAITING PHYSICAL VALIDATION.** Media accepts wheel volume over its entire retained presentation, not only the external volume rail, and routes discrete steps through the existing app-volume owner. Non-CUSTOM Visualizer emits the same event-bound step and `DisplayManager` forwards it to an already-admitted Media presentation, preferring the same display and then another live display; no duplicate Media runtime/service or cadence was created. CUSTOM edit mode explicitly disables both Media and Visualizer volume-wheel admission so resize wheel has sole ownership. Verify physical wheel behavior over Media card/rail and Visualizer, including split-display Visualizer/Media routing.
- [~] **Context Menu -> Settings click-through suppression — SOURCE-COMPLETE / AWAITING USER QT VALIDATION.** A retained context-menu action arms the shared monotonic pointer-suppression deadline before dispatching Settings, so the same passive-grab pointer gesture cannot also activate Gmail/Reddit content underneath the dismissed menu. Gmail message/inbox and Reddit URL open paths consult that shared guard; no timer, polling owner, worker or fallback browser path was added. The Gmail-side regression already lives in destination `test_qtquick_gmail_presentation.py`; the focused Settings-action/Reddit regression is now also a maintained destination target. Validate the refreshed destination profile in the normal PySide6 environment before closure.
- [~] **Media visual-parity baseline + external volume accessory — SLICE 9 SOURCE-COMPLETE / AWAITING PHYSICAL VALIDATION.** Slices 1–8 remain cumulative for accepted seek/header/mute/metadata placement, portrait-ish artwork, smart Spotify baked-letterbox correction + rounded masking, title-case + shrink-before-clip metadata, optional Album/Playback-State lines, compensated visible strokes, semantic theme roles, shared fades and cached direction-aware sub-surface shadows. Slice 9 implements the sole named post-parity geometry enhancement: app volume is now a scene-local **external right accessory rail, default ON when provider/runtime capability is available**, while the Media card keeps/reclaims its accepted ordinary content width. `OverlayWidget.rightAccessoryExtent/rightAccessoryContent` provides the reusable single-root accessory lane; it does not create a second card, model, lifecycle owner, poller, service or geometry authority, and the display-level card shadow deliberately excludes the accessory lane. Volume Track/Fill/Outline and seek Track/Fill/Shadow/Glow now have alpha-aware family swatches in collapsed `Volume Control` / `Seek Bar` buckets while still inheriting through Slice-8 semantic roles when left at canonical defaults. Header controls are grouped under `Header Appearance`. The Slice-8 accidental white app-volume fill regression is fixed by giving `media.volume.fill` its own local accepted volume fallback instead of borrowing the seek/progress accent. **Parity+ protection:** later J/J+ sweeps must not move volume back inside the card, steal the reclaimed card width, re-hardcode these semantic roles, or otherwise rework accepted Media geometry/shadows/strokes/fades unless a specifically named regression is opened. Event-owned Media runtime and preferred transport semantics remain untouched.
- [~] **Shared branded-header contract — SLICE 9 NORMALIZED / AWAITING VALIDATION.** Media, Gmail, Reddit, Achievement Pulse and Abandonment Issues consume one `BrandedHeader.qml` primitive rather than five independently drifting pills: 25 px logo box, 8 px logo/label gap, 20 px total horizontal padding, 36 px minimum pill height, 9 px radius, family-invariant 16.4 pt bold **ALL-CAPS** label, intrinsic pill widening with no header elide/clip, alpha-aware Header Fill + Border + Text roles, shared visible-stroke compensation, retained cheap text shadow, logo shadow, and a cached direction-aware **extension** shadow using the accepted Media transport-bar blur/offset profile. Gmail/Reddit `header_logo_px_adjust` remains retired and refresh glyphs remain on the common row at 70% opacity. Slice 9 fixes the apparent Steam-size exception at the asset boundary: the supplied `Steam_Logo.png` contains very large transparent margins, so both Steam families now use a tightly alpha-cropped derivative while preserving the same shared 25 px logo box—no Steam-only size multiplier exists. Steam authored-canvas families continue to pass `contentScale` into the shared stroke helper. Visualizer remains explicitly exempt. **Parity+ protection:** later family padding/alignment work may move each header as a whole within its card, but must not fork or silently retune shared pill geometry, casing, intrinsic-width behavior, swatches, logo/text shadows, refresh opacity/row alignment, header shadow contract, or reintroduce transparent-padding-driven logo-size exceptions without an explicit new visual requirement.
- [~] **Scale-aware line/stroke contract rollout — SLICE 8 FIRST WAVE IMPLEMENTED / AWAITING VALIDATION.** `OverlayWidget.scaleAwareStrokeWidthForScale()` remains the one reusable primitive. In addition to already-protected Media/header strokes, the first bounded rollout now covers Gmail message/boundary separators, Reddit/Reddit2 separators, Weather separators and selected Steam info/artwork/metric decorative borders/separators. Visualizer remains explicitly exempt. Continue incrementally after eyes-on validation; do not blanket-convert semantic/content-bearing geometry, and do not revert accepted uses during J/J+ parity sweeps.
- [~] **Widget-theme semantic visual-role resolution — SLICE 8 FOUNDATION, SLICE 9 BOUNDED OVERRIDE UI / AWAITING VALIDATION.** `ui/widget_visual_roles.py` owns one sparse semantic cascade: intentional per-widget override -> exact family/widget theme role -> shared semantic parent -> local/current semantic role -> preserved current fallback. `local.*` values are presentation context only and never serialize into `.srwtheme`. Schema v2 admits sparse optional roles while preserving a strict core role set and v1 core-theme migration. Consumers include shared branded headers; Media transport/mute/volume/progress; Gmail/Reddit/Weather/Clock separators and Gmail action-popup colors; Steam info/tooltip/artwork/gradient/metric roles; and the retained Context Menu palette. Slice 9 proves the intended UI discipline: semantic migration does **not** automatically expose every role, but high-value frequently authored family overrides may be surfaced inside collapsed semantic buckets. Media now exposes Volume Track/Fill/Outline and Seek Track/Fill/Shadow/Glow plus Header Fill/Border/Text while default-valued swatches remain implicit Inherit and an actually changed swatch becomes the family override. The volume-fill local fallback regression has a focused semantic test ensuring progress/seek accent cannot recolour default volume fill, while an authored `widget.accent` theme still can. Named-theme selection/persistence and retained palette application are now Phase 1b/1c **source-complete below**; remaining work in this lane is physical validation plus the bounded remaining semantic-role/literal audit.
- [~] **Shared artwork + Media metadata fade polish — SLICE 8 IMPLEMENTED / AWAITING VALIDATION.** Shared `ArtworkFadeImage.qml` now uses gentler event-driven fade-through timing (`200 ms` out / `340 ms` in) for Media and both Steam artwork families without another resident image or recurring animation owner. Media Title/Artist/Album now use `MediaMetadataColumn.qml`: authoritative provider/model strings update immediately while one small outgoing text column crossfades presentation-only (`240 ms` out / `340 ms` in). No polling, timer cadence, provider delay or stale metadata authority was introduced. Validate rapid track changes, Album hidden/visible state, long-name HorizontalFit behavior and Steam archive transitions before closure.
- [ ] **Widget Settings bucket decomposition — FOLLOW-UP UI ARCHITECTURE.** Media is the first cleanup exemplar: `Provider & Layout`, `Appearance`, `Header Appearance`, `Artwork`, `Transport Controls`, `Seek Bar`, `Volume Control`. Audit other overloaded widget pill sections incrementally rather than wholesale: prioritize Steam-family appearance/field sections, then Gmail/Reddit where behavior/provider controls and visual overrides are mixed. Reuse semantic bucket names such as `Header Appearance`; do not remove functionality, expose every theme role, or turn bucket layout into a second theme system. Bucket state remains UI presentation only.
- [~] **Context-menu submenu lifetime — IMPLEMENTED / AWAITING VALIDATION.** Parent/submenu hover ownership now dismisses a submenu after the pointer leaves both surfaces, with only a one-event-turn `Qt.callLater` handoff grace so pointer transfer into/out of the overlapping submenu does not self-close. Hovering another submenu still replaces it. No timer, polling loop, popup, or native window was added. Physically validate Transitions + Visualizers submenu traversal and leave/re-entry behavior before `[x]`.
- [~] **Reddit edit chrome / stale-envelope geometry seam — AWAITING VALIDATION.** Audit found a real H9 geometry seam rather than oversized handle primitives: uniform-transform Reddit/Reddit2 could render a correctly centred card inside an old aspect-mismatched committed outer rect while CUSTOM outlined/resized the invisible letterbox envelope. Admission now canonicalizes the session/edit rectangle to the actual visible retained-card bounds at the same centre/scale; Save retires only dead geometry and Cancel leaves visible pixels unchanged. The unused `custom_layout_runtime_vertical_content_resize` descriptor flag was removed because it falsely advertised a retired runtime geometry contract. Validate Reddit + Reddit2 handles and corner/wheel scale; if bars remain tall, capture the frame/card mismatch rather than changing handle primitives blindly.
- [ ] **Reddit ordinary/non-CUSTOM content contract.** Ordinary adjustment/resize interaction must preserve Reddit's newest-message cycling/content behavior rather than accidentally mutating geometry; audit Reddit and Reddit2 together.
- [~] **Spectrum extreme-viewport temporal scaling — IMPLEMENTED / AWAITING PHYSICAL VALIDATION (R-76).** Post-cutover audit found the accepted large-viewport smoothing rule stranded in the retired QWidget-era helper while the live Quick `SpectrumFrameRuntime` used one viewport-blind time constant. The old helper also incorrectly used the larger of width/height, so an extreme-wide card could be slowed even though Spectrum bar motion is vertical. Live Quick now scales only the existing presentation one-pole by expanded **vertical bar-field height** (canonical/wide remain exact), and solid-bar hysteresis keeps a canonical internal segment domain instead of retuning/resetting its rate zones as viewport height changes. BeatEngine/DSP smoothing, 0.55 upload transfer, height/amplitude boost, cadence, renderer segment geometry and source magnitude are untouched. Source-only viewport temporal profile GREEN `6/6`; physically validate canonical + extreme-wide + extreme-tall in continuous and segmented modes before `[x]`.
- [x] **Cross-mode extreme-viewport source audit (assessment only).** Bubble, Oscilloscope, Sine and DevCurve were traced by authored axis -> viewport geometry -> temporal state -> physical pixel transfer. No second source-proven scaling bug was found. Sine extreme-wide X travel / extreme-tall Y motion and DevCurve extreme-wide normalized travel remain explicit physical watchpoints; do not tune them without operator evidence. Canonical contract/table lives in `Docs/Guardrails/Visualizer_Presentation.md` §9A and the 2026-09-02 audit doc.

## H closure summary

### H completed checklist

- [x] One selected physical display -> one standalone `QQuickWindow` -> one threaded Quick scene graph/runtime scene.
- [x] Old `DisplayWidget` / QRhiWidget / `GLCompositorWidget` physical presentation authority remains deleted.
- [x] H1a/H1b lifecycle/recreation/terminal retirement accepted.
- [x] H2/H3/H3b/H4 family/product runtime semantics accepted.
- [x] H5a/H5b visualizer routing/topology accepted physically.
- [x] H5c visualizer reactivity/performance accepted at the heavy-load H boundary; residual optimization debt moved to J.
- [x] H6 Media CUSTOM Settings lock semantics accepted.
- [x] H7 visible Exit response accepted.
- [x] H8 middle-click same-mode preset cycling/Custom round-trip accepted physically.
- [x] H9 ordinary-family uniform resize accepted, including absolute persisted 40% floor and Gmail whole-card scaling.
- [x] R6 native-`QCursor` Halo architecture accepted and protected.
- [x] R7 transactional image admission/prefetch wake accepted; timer/manual transitions are the same performance class.
- [x] R-63 black-flash prevention accepted with `black=0`; bounded mixed-DPR shared-edge pixel overshoot tolerated rather than risking exact-cover fullscreen promotion.
- [x] Media fast polling retired in favor of event ownership plus slow reconciliation/watchdog.
- [x] Final heavy-load Visualizer audio lane/state work materially reduced GC frequency without sacrificing logical cadence/reactivity.
- [x] H closure docs/tests reconciled enough to hand authority to the phase-neutral `destination` profile and Phase I cleanup.

The final heavy-load performance evidence is intentionally **not** an invitation to chase counters further inside H. Representative accepted evidence:

```text
Visualizer logical publication: ~89-90 Hz when active
Typical snapshot age:           ~18-22 ms
Audio analysis mean compute:    ~1.86 ms
Audio callback work:            ~0.067 ms
Generic per-frame Future path:  0
Final heavy-load gen-0 rate:    ~9.8 collections/s
Final heavy-load gen-2 rate:    ~0.39/min
Residual deep gen-2 pauses:     ~130-146 ms in that run
```

Those residual deep pauses are real J/end-performance debt. They are **not** permission to reduce authored work, cadence, freshness, response amplitude, motion, viewport scaling, newest-state semantics, or visible fidelity.

## Golden guardrails carried into I/J

Performance work in I/J must also follow `Docs/Guardrails/Performance_Optimization_Contract.md`. That document owns the permanent rule that **freshness/reactivity and latency-tail quality outrank prettier aggregate counters**, plus the 2026-09-01 heavy/modest reference envelopes.

### 1. Visualizer reactivity/freshness is sacred

Priority order remains binding: authored fidelity/reactivity outranks lifecycle counters, frame-pacing averages, task-count elegance and FPS cosmetics.

Never “fix” performance or extreme geometry by:

- lowering the authored/logical Visualizer cadence;
- adding a debounce/catch-up FIFO/backlog between current source and newest-state presentation;
- allowing stale source/snapshot age to rise while pixels continue;
- globally compressing Bubble head radius, pulse amplitude, motion, Ghost/history displacement or another mode's authored reaction as viewport extent grows;
- applying a second `baseline/current` or `1 / viewport_extent` compensation to state already normalized into renderer-content coordinates;
- retuning DSP/gain/cold-play response to hide a presentation/geometry defect;
- restoring per-frame generic `Future`/task submission for audio analysis;
- removing the stable previous-bars packet snapshot merely to improve allocation counters without a replacement correctness proof.

**R-69 is the golden Bubble scaling lesson.** Canonical, wide and tall CUSTOM geometry must preserve the same authored response character. Bubble's renderer-facing head radius stays the authored fraction of actual card height. Ghost consumes already-normalized history exactly once. The accepted compact ripple-wake projection is a separate effect and must not be generalized to head/Ghost state. If an extreme full-expansion head is visually too large, fix only a proven upper visual tail without flattening the full response curve.

Apply the same reasoning to Spectrum/Oscilloscope/Sine/DevCurve: geometry adaptation may reframe/reflow/smooth presentation, but may not quietly weaken musical response.

### 2. Visualizer audio compute ownership

Current accepted path:

```text
one shared BeatEngine
-> one persistent serial visualizer.audio_analysis compute lane
-> one in flight + newest pending source replacement
-> retained detached DSP state across ordinary frames
-> rebuild only at real config/activation/reset epoch boundaries
-> immutable newest logical/render publication
```

No generic Future fallback. Lane creation failure must be loud. Config/reset crossing an in-flight computation fences the stale result. Keep the small stable previous-bars tuple because the live silence path may mutate the backing list in place.

Further GC work belongs near the end of J and must start from allocation/lifetime evidence. Do not tune collector thresholds simply to make counters prettier, and do not trade response latency/reactivity for fewer collections. 2026-09-01 operator-log comparison now supplies a concrete symptom seam: every observed generation-2 collection in both sampled runs coincided with a Bubble wall-clock tick spike (~41-68 ms GC pauses / ~46-64 ms Bubble dt spikes), including newer-run Gen2 scans that collected zero objects. The two log builds contain no Bubble runtime change between them, so this is evidence of a pre-existing stop-the-world hitch class, not evidence that the later lifecycle fades caused it. Investigate retained allocation/lifetime roots and visibility of pause telemetry; do not remove the scalar-only fades or relocate forced collections without a mechanism.

Historical performance record: `Docs/Historical_Bugs/R-71_Visualizer_Audio_Per_Frame_Task_And_DSP_State_Allocation.md`.

### 3. R-63 seam / black-flash priority

The no-black-flash contract outranks exact shared-edge pixel perfection.

Current native evidence on the operator's mixed-DPR pair showed Display 0's intended exterior/top overscan rounding to a `2561`-device-pixel window over a `2560`-pixel monitor, overlapping Display 1 by one device pixel. That explains the intermittent seam pixel.

A **bounded 1px overshoot is acceptable** while `black=0` remains true. Any later refinement must derive device-space coverage from actual monitor rectangles/DPR and remain valid across different resolutions, coordinates, monitor ordering and DPR combinations (including 1.0/1.25/1.5/1.75/2.0 and mixed-DPR). Never hard-code the current monitor pair, force exact cover, or remove R-63 overscan generically.

### 4. CUSTOM resize authority

Ordinary CUSTOM scale is absolute against stable authored/preferred size, persisted across sessions, with shared **40% floor**. A new session must not treat an already-scaled committed rectangle as a fresh 100% baseline.

Reddit/Reddit2, Media and Gmail use whole-card retained `uniformScaleTransform`; fixed chrome/text/rows/spacing scale with the card. Gmail's model width is already outer width; only row-derived preferred height receives the shell inset. Visualizer remains on its independent `uniform_visual_scale` + `viewport_extent` contract.

### 5. Media event ownership

Do not restore fast Media polling or process-probe fallback. Native GSMTC event/session observation is primary. The slow reconciliation/watchdog is deliberate safety coverage and degraded observation must be conspicuous in logs.

### 6. Native Cursor Halo

Passive pointer motion must not become QML scene invalidation again. Halo position/visibility is native cursor presentation through `QuickCursorController`/`QCursor`; QML retains only semantic interaction/Ctrl state where needed. The orphan `rendering/quick/qml/CursorHalo.qml` is I deletion residue, not a dormant fallback.

## Phase I — ACTIVE: caller-proven residue reconciliation

I is intentionally source-driven cleanup. It must make the tree tell the truth about the already-accepted destination; it must not redesign production behavior.

### I0 — deterministic destination gate

- [x] Apply the H-closure test/doc patch. (Present in current tree.)
- [x] Manually delete the **Immediate manual deletions** tombstone tests — already removed (not tracked in git).
- [x] Ran the destination gate in the real PySide6/OpenGL environment (2026-09-01):

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

- [x] **Destination gate GREEN — 98/98 (2026-09-01).** All 21 classified reds reconciled without restoring any retired owner: visualizer engine stubs (`set_transient_lane_config`); the Ctrl/interaction provider-injection cluster rewired to the event-driven `SharedCtrlCoordinator` publish/subscribe + `interaction_mode_enabled` model (R6/§4.5); source-text/data-shape assertions realigned to current source (R-63 single-edge overscan, `cursor_controller.close` teardown, `_custom_resize_scale` size payload, the startup-crossfade `_present_quick_image` anchor, the ContextMenu QWidget-in-comment guard); two transition-admission tests rewritten to the R7 transactional contract (reject-not-snap; a broadcast second image starts per-screen routed transitions); `retained_model_lifetime` family items given a real QML component; and the startup-reveal tests moved onto a GUI `QApplication`. **One red was a genuine current-source defect, not drift:** a superseded compute callback could release a serial-lane slot a newer same-activation owner held — fixed in `widgets/spotify_visualizer/beat_engine.py` with an activation-aware guard (strengthens R-71 fencing). Multi-file `pytest` cross-contaminates Qt teardown — always classify reds with the per-target-isolated `destination` runner.
  - [x] Historical-bug record written: `Docs/Historical_Bugs/R-75_Superseded_Compute_Callback_Released_Held_Serial_Lane_Slot.md`.

### Immediate manual deletions

These are already caller/contract-proven enough that preserving them adds fake authority:

- [x] Delete `tests/test_settings_sync.py` — already removed (not tracked in git).
- [x] Delete `tests/test_phase_e_effect_corruption.py` — already removed.
- [x] Delete `tests/test_visualizer_preset_cycling_runtime.py` — already removed.

Generated test cache (`tests/.pytest_cache/`, `tests/**/__pycache__/`, `*.pyc`) is never source authority and can be removed locally at any time.

### I1 — exact stale-owner test/tool reconciliation

Use `Docs/TestSuite.md` as the live inventory. Highest-confidence residue already identified:

- [ ] Reconcile old GL/compositor transition and rendering tests.
- [ ] Reconcile old compositor metrics/GPU-query/fallback tests.
- [ ] Reconcile old visualizer physical-host/card geometry tests.
- [ ] Reconcile `tests/test_spotify_visualizer_widget.py` importing deleted overlay/host code.
- [x] Tooling audit proved `tests/test_visualizer_replay.py` + `tools/visualizer_replay.py` have no current executable owner; delete them while preserving current fixtures/goldens/temporal/BTF contracts.
- [ ] Reconcile old MC physical-window implementation tests where current Quick role/policy tests own the surviving contract.
- [ ] For every candidate deletion/rehome: identify the exact surviving product-neutral contract and prove its current owner/test first.
- [ ] Do not mass-delete by filename/phase prefix; record each resolved owner/removal in `Docs/TestSuite.md` / cleanup ledger.


### I1A — tooling authority cleanup

- [x] Audit every `tools/` executable against current post-H owners rather than filename/phase age.
- [x] Remove the dead in-process PERF parser hook from `main.py`; production now only emits/flushes evidence (`R-72`).
- [x] Make `tools/run_tests.py` delegate to canonical `tests/run_chunked.py` instead of owning a second suite manifest.
- [x] Re-home the still-useful ImageWorker SHM proof as `tools/image_worker_shm_lifecycle_harness.py`.
- [x] Re-audit defaults regeneration tooling against the current schema/atomic-write safety contract.
- [x] Reject `bubble_parity_harness.py` as R-69 authority: it has no viewport/domain/DPR/presentation-scaling oracle.
- [x] Reject the generic `transition_perf_health_parser.py`/synthetic Visualizer distribution harness as permanent authority; current instrumentation + focused tests own those contracts.
- [x] Apply the manual tool/test deletions in `Docs/Tooling_Audit_2026-09-01.md` — verified: all 20 tools and all 7 tool-coupled tests are already removed from the tree.
- [x] Run `test_tooling_ownership.py` in the real project environment as part of `destination` — passed in the 2026-09-01 gate (not among the 21 reds).
- [x] Confirm no production Python imports `tools`/`scripts` analysis modules after the deletion batch — enforced GREEN by `test_tooling_ownership.py`.
- [ ] Carry only `presentation_benchmark_core.py` + `qtquick_presentation_spike.py` as explicitly non-authoritative architecture-selection evidence until J physical acceptance, then delete them.

### I2 — source/tool residue

After exact caller search:

- [x] Delete orphan `rendering/quick/qml/CursorHalo.qml` — removed 2026-09-01 after proving no `.py`/`.qml`/`.qrc`/`qmldir` reference (only docs/history mention it).
- [x] Remove caller-dead Media process-probe helpers retired by event ownership — none remain; `psutil` survives only in the two KEEP out-of-process sampler tools.
- [~] **R-77 coordinated QWidget/compositor residue retirement — IMPLEMENTED / AWAITING DESTINATION + PHYSICAL VALIDATION.** The first raw-quarantine attempt proved the 25 files were not independently removable from R-76 because startup still crossed compatibility imports. The superseding slice rewrites/re-homes every surviving caller first (logical frame capture, logical-only tick pipeline, neutral QObject/type seams), then retires the 25 obsolete modules in the same checkpoint. Source-only cleanup gate is GREEN; the included GUI `deletelater` utility is reversible and must be run only after installing the replacement callers. See R-77 + I2 manifest.
- [x] Reconcile regeneration/default tools against current Settings/Quick schema; audit completed 2026-09-01 and current atomic/schema-derived pipeline is protected.
- [ ] Preserve neutral transition registry/settings/math/shaders and neutral visualizer DSP/logical algorithms used by Quick.
- [~] Re-run exact caller/import searches after each residue batch so deletion does not create hidden compatibility fallback pressure. R-77 exact production-name/import sweep is GREEN after coordinated rewrite; destination/startup validation remains required.

`Future_Cleanup.md` owns the detailed deletion ledger.

### I3 — whole-tree truth restoration

After bounded residue batches:

- [ ] Run the maintained destination authority:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

- [ ] Run the broad whole-tree gate:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

- [ ] Confirm the first command remains GREEN production authority.
- [ ] Drive the second away from deleted-owner/museum failures until it is a useful broad gate again.
- [ ] Sweep current docs/test inventory after the final residue batch so source, tests and authority documents agree before I closes.

### I exit checklist

- [ ] Canonical `destination` profile GREEN in the real project environment.
- [ ] No current tests import deleted physical owners merely to preserve migration history.
- [ ] Whole-tree collection has no caller-dead-owner import failures.
- [ ] Source/tool residue has exact caller proof before deletion.
- [ ] No compatibility alias/fallback can silently recreate a second presenter/analysis/polling authority.
- [ ] `Docs/TestSuite.md`, `Future_Cleanup.md`, migration docs and source agree on owner map.
- [ ] No change violates the golden Visualizer/R-63/Media/CUSTOM guardrails above.
- [ ] Historical-bug records exist for any newly resolved or instructively failed I incidents before the phase is closed.
- [ ] `Current_Plan.md` is compactly rolled forward to J with the completed I checklist retained as closure evidence.

## Phase J — queued after I

J is final visual/fidelity/installed/physical acceptance and intentional polish. The detailed matrix lives in `Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md`.

Front-load the mandatory image-oracle parity work (`images/migration/Ideal (PreMigration)/` vs `Current (PostMigration)/`) when vision-capable tooling is available.

### J queued checklist

- [ ] Perform family visual-parity pass against the pre/post migration image oracle.
- [ ] Restore/verify alignment and snap guides.
- [ ] Verify/fix context-menu and theme correctness.
- [ ] Complete remaining Visualizer presentation polish, including any proven extreme Bubble full-expansion tail, **without weakening R-69 reactivity**.
- [ ] Consider device-space R-63 seam refinement only if it preserves `black=0` generically across DPR/resolution combinations; bounded overshoot remains preferable to black flash risk.
- [ ] Fix latency/telemetry accounting so recreation boundaries cannot report stale pre-recreation timestamps as multi-second live latency.
- [ ] Run late-J performance work under `Docs/Guardrails/Performance_Optimization_Contract.md`: target rare active latency tails and proven useless allocation/lifetime work before average counters.
- [ ] Work the live bounded parity/polish queue in **Non-Blocking Auxiliary Work** above without duplicating its checkbox authority here; unresolved auxiliary items may carry forward explicitly, but must not disappear.
- [ ] Verify resource plateau across recreation/soak (RSS/USS, VRAM, threads, handles, workers/caches) without destroying useful bounded caches merely to reduce Task Manager numbers.
- [ ] Recheck both modest-load quality and representative-heavy graceful degradation after any performance change.
- [ ] Complete compiled/frozen/installed 1/2/N-display/DPR/topology acceptance.
- [ ] Complete final family-specific parity/polish acceptance from `Remaining_J_Final_Installed_Acceptance_Decomposition.md`.
- [ ] Reconcile remaining historical-bug records, including failed methods worth preserving.
- [ ] Remove migration-only harness/planning debris only after acceptance evidence exists.
- [ ] Run final maintained destination + broad suite gates and reconcile docs before J closes.

### Committed J+ Widget Theme + card-material work — non-blocking for J close

- [x] **Design questions resolved / Phase 1a merged (Claude `f0564449`).** Compiled Default Dark is unconditional fallback; `.srwtheme` IO/catalogue/resolver + Keep Synced/Custom/material state machine are present. `Custom` remains Settings data, not a theme file.
- [x] **Palette precedence resolved:** Widget Theme card roles are global/default baseline values; explicit existing `widgets.<family>.card.*` values win for that family. Per-family swatch edits remain family-specific and do not create Widget Theme `Custom`. Context Menu has no family override layer and consumes Widget Theme palette directly.
- [~] **Schema-v2 semantic-role foundation / first projection wave implemented in Slice 8.** Sparse optional roles inherit through one resolver; Default Dark preserves accepted current pixels; current family swatches act as implicit Inherit only when still equal to canonical defaults; first Media/header/separator/Steam/Context-Menu consumers are wired at construction/generation boundaries. Pure semantic tests are green `13/13`; physical visual validation remains outstanding. Named-theme UI/application is now owned by the source-complete Phase 1b/1c items immediately below.
- [~] **Phase 1b persistence + Themes/Widgets UI — SOURCE-COMPLETE / AWAITING QT + PHYSICAL VALIDATION.** Structured `widget_theme` persistence is admitted as a first-class root; startup resolves/publishes the selected catalogue/theme before retained presentation construction. Widgets -> General -> Appearance owns the shared Card Surface, Card Border and Surface Style controls once for all widget families; this is not duplicated per family. Editing the shared Card Surface/Border freezes the active resolved optional palette into Settings-owned `Custom` and disables Keep Synced. Theme catalogue/selection/current-active state is process-local construction authority, not a new runtime poller. The retained runtime is rebuilt around Settings changes, so no second live-theme subscription/cadence owner is required. The canonical defaults JSON and both SST defaults artifacts are regenerated transactionally with the structured `widget_theme` root and pass the defaults-foundry drift check under a Qt-free package shim.
- [~] **Phase 1c retained palette/material snapshot — SOURCE-COMPLETE / AWAITING QT + PHYSICAL VALIDATION.** The shared Widget Theme card surface/border is now the baseline for ordinary retained families when their family card values remain canonical/default; genuinely authored family values still win as explicit overrides. Visualizer consumes the same shared card-shell baseline without touching its DSP/viewport/reactivity contract. Default Dark's shared card RGBA was reconciled to the accepted ordinary-family pixels so inheritance itself is visually neutral. Renderer-facing material admission remains Normal-only: Theme Default may preserve a theme's Glass/Acrylic recommendation in state, but the active retained material snapshot is clamped to Normal until the shared/lazy material path exists.
- [ ] **Complete the bounded remaining semantic-role/literal audit before material expansion.** Walk the remaining retained families for presentation literals that should inherit an existing semantic role; classify each literal rather than blanket-theming it. Preserve explicit family overrides, Default Dark pixel parity, Visualizer reactivity/scaling exemptions, and the rule that semantic migration does not automatically create a Settings swatch. Reconcile any newly admitted role in schema/default/theme tests and the relevant collapsed Settings bucket only when it is genuinely user-authored/high-value.
- [ ] Phases 2–7: measured one-shared-per-display Glass/Acrylic material path; no per-card capture/blur owner, second window, or Settings HWND backdrop reuse.

## Authority order

For current work:

```text
exact source / exact test tree
-> Current_Plan.md
-> Spec.md
-> Docs/Contracts.md
-> Docs/Guardrails.md + focused subsystem references
-> Docs/TestSuite.md / Future_Cleanup.md
-> physical/log evidence
-> historical records for mechanism/failed-method lessons
```

Historical documents preserve what happened; they do not override current owner maps. Conversely, current source must not erase a binding historical lesson merely because a tempting shortcut looks locally cleaner.
