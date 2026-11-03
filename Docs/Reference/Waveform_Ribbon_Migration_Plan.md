# Waveform Ribbon | Production ownership, control migration and Studio implementation

**Current architectural/authoring plan, 3 November 2026.** This is the production-facing design companion to the live experiment/acceptance checklist in [`Waveform_Ribbon_Lab_Plan.md`](Waveform_Ribbon_Lab_Plan.md), parent gates in [`Current_Plan.md`](../../Current_Plan.md) §7.1 and visual authority in [`Waveform_Ribbon_Visual_Authority_20261103.md`](Waveform_Ribbon_Visual_Authority_20261103.md). The older WR-08 migration programme has **already produced a production candidate**; this document is not an instruction to restart the port or repeat already completed wiring.

**Supersession note:** Earlier claims in this document that the operator selected C+A once and for all, musical flow speed must never change, the mist is still entirely rejected, Orthographic merits equal visual tuning, or the old mode-specific Settings builder remains the appropriate UI are retired. The lead may change artistic/dynamics internals after an explicit checkpoint. Retain valid ownership, typed-state, preset, cost and renderer constraints. The original details remain in Git history and the actual source; never silently resurrect superseded directions.

## 1. Production owners, not duplicated subsystems

| Layer | Current authority | Production / Studio rule |
| --- | --- | --- |
| Canonical preset and controls | `core/settings/visualizer_mode_settings.py`, `core/settings/default_contract.py`, `ui/tabs/media/spec_mode_builder.py`, `widgets/spotify_visualizer/waveform_ribbon_parameters.py` | Exactly one setting schema, validation, Custom transition and persistence pipeline. Studio is a UI adapter. |
| Ribbon identities, bands, gradients, source routing | `core/waveform_ribbon_authoring.py` | Four capacity, three-old-card forward migration without count change. Existing 14×6 matrix is storage/legacy implementation, **not a required UI** or immutable future architecture. |
| Musical/typed logical state | `core/waveform_ribbon_dynamics.py`, existing Visualizer logical runtime and audio/feature owners | One clock, fixed-reference raw waveform bands and typed accents, source epochs, immutable published snapshots and consume-once events. No QML clock/hidden DSP. |
| 3D scene and material | `rendering/quick/scene3d/waveform.py`, `rendering/quick/scene3d/waveform_field.py`, `rendering/gl_programs/waveform_ribbon.py`, `rendering/gl_programs/waveform_atmosphere.py` | Retained production Scene3D/Quick renderer and legal context resource ownership. Scene preview uses same actual material, flow and motion. |
| Shared framed 3D and reflection | `core/settings/waveform_ribbon_camera.py`, shared framed camera, `Docs/Reference/Ribbon_Path.md`, `Docs/Reference/Scene3D_Resources.md` | **Perspective-only** authored scene camera, world-ground collision, bounded history and coherent reflections. Orthographic is retired as a scene-camera mode. |
| Settings old rejected builder | `ui/tabs/media/waveform_ribbon_builder.py`, `ui/widgets/waveform_ribbon_preview.py`, `ui/widgets/waveform_ribbon_editors.py` | **Replacement targets**, not reusable design mandates. Preserve only shared accepted Settings scaffolding and save-camera option. |
| Real music, lab and native evidence | `tools/visualizer_replay/waveform_ribbon_signal_audit.py`, `tools/labs/waveform_ribbon_recorded_input.py`, `tools/labs/waveform_ribbon_music_bakeoff.py`, `tools/waveform_ribbon_capture.py`, `tools/visualizer_live_check.py` | Same source, pose, preset, logical time and effective values for comparisons; no synthetic-only sign-off. |

### 1.1 Production reactivity policy after the operator pivot

- Waveform uses fixed-reference raw musical lanes, source identity, gradual sustained musical weight and typed transients; no song-normalized level learning and no cross-mode DSP retune. Dynamic Floor must not secretly control the musical body.
- **Travel speed is now music-reactive.** Idle/min speed looks roughly 3× too quick in current live usage. Actual travelling history/material must accelerate with musical energy (quick attack, gentle slower release) without speed jumps, visible history distortion, bead-like starts, collapse, changing viewport composition or renderer-side time integration. This **explicitly replaces** the older “flow never follows music” rule from the previous migration and concept/lab notes.
- C-primary elastic and A-style rolling twist are an existing implementation baseline, **not mandatory continued architecture**. Separate body shape, sustained carrier, typed impulses, accumulated axial rotation and independent musical colour/rim/particle pathways so future grammar changes don't require tearing down Settings/presets. Read real recordings and source traces before selecting any new grammar.
- Quiet idle state remains alive in a deliberately tiny way: very slow roll, subtle carrier, slow travelling low rim light and very few ambient particles. Do not author fake typed hits or hide weak real music under a raised constant musical floor.
- Rolling the *entire family* around its longitudinal axis must be an independently selectable/reactive motion with continuously integrated angle. All visible ribbons participate together when enabled; this is not camera yaw or arbitrary scene orbit. Individual ribbon twist/phase may coexist.
- Colourshift and rim light are prominent musical outputs, not just static palette edits. Avoid blooming several independent sources into white wash; keep regionally distinguishable hues and bright but controllable peak highlights.
- Preserve four-ribbon source/calibration independence, stable IDs, floor collision/clipping and the same transformed geometry for strands, reflection and atmosphere. Rebind/re-migrate controls when dynamics change, with explicit old→new mapping and compatibility tests.

### 1.2 Perspective-only camera retirement (new operator authority, 3 November 2026)

**Do not treat this as "Perspective first" or "Orthographic later."** The operator retired Orthographic as a user-facing 3D scene-camera mode across SRPSS after two unsuccessful visualizer attempts. The only authored camera projection for Waveform's Studio, Settings, presets, synthetic/live preview, tests and future framed 3D modes is **Perspective**. Preserve the current per-mode physical eye, lens/FOV, aspect behavior, clip policy, camera navigation, operator save-camera checkbox and world-space geometry. Screen-edge perspective stretching in EB is **not** an authorization to change EB.

- [ ] Remove/retire Waveform projection choice from mode specs, Studio and old Settings builder. Do not implement an Orthographic Studio inspector, camera preset, fallback renderer or A/B preview. If common framework still has a projection field, its effective public value must be single-valued Perspective; consider removing the selector entirely rather than showing a one-option combobox.
- [ ] Update framed-camera schema/normalization and canonical defaults at their real owners. Safely recognize historic Orthographic values from saved/imported/repair inputs, normalize to Perspective for rendering, and document whether metadata is preserved only for round-trip legacy custody. Never silently rewrite curated operator preset bytes during read; use explicit migration/write semantics as required by existing SSOT contracts.
- [ ] Remove dual-projection *Waveform acceptance* requirements, default tests and art tuning. Retain historical fixtures where they diagnose projection/math or past regressions; dedicated orthographic math may remain for shadow/technical orthographic passes if actually consumed.
- [ ] Focused check: opening old files, Save/Save As/Custom/reset, camera view persistence, Studio preview/production parity and a native Perspective frame at multiple viewports. Preserve accepted Perspective rendering in EB/Neon Lake through no-change checks, not a new EB camera redesign.
- [ ] If implementation cleanup is risky while Waveform is under active recovery, stage narrowly scoped schema/UI retirement and explicitly document temporary internal legacy handling. **No temporary path may restore a user-selectable or artistically supported Orthographic mode.**

## 2. The Qt Quick Waveform Studio is the new authoring surface

**Design source:** `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Audits\SRPSS_Waveform_Studio_Design_Pack_2026-11-03.zip` (operator-installed; not an included GODZIP asset). Its `Waveform_Studio_Concept_Mock.png` is the approved **visual ambition**. Its full MD explains reusable window shell, control families, lifecycle, theming and rejection tests. Follow it as a strong design brief, but do not hard-code mock pixels, current material parameters or currently weak reactivity into the reusable framework.

### 2.1 Explicit Settings → Studio → Settings lifecycle

1. Waveform **Custom** page retains `Open Waveform Studio` button and existing **save camera checkbox** (and only genuinely shared navigation/preset controls). Rejected mode-specific giant buckets, distant nonfunctional `Preview quiet → peak` and initial 84-cell raw matrix do **not** remain on this page as a second editing workflow.
2. On open, capture Settings identity, selected mode/preset, focus, screen, scroll, camera-save choice and live canonical values. Create/focus a single resizable in-process Qt Quick Studio. **Hide Settings only when Studio actually opens successfully**. On failure show a useful error and leave Settings usable.
3. Studio edits the existing canonical data through validated parameter adapters. A change from a curated preset behaves exactly as current Custom transition; named Save/Save As/Reset/Cancel/preset selection use existing supported semantics. Dirty state, undo/redo and restoration must be explicit. Avoid simultaneous hidden Settings events silently clobbering Studio edits.
4. Closing Studio restores same Settings window at prior monitor/location/page/tab/preset/scroll and focuses it; never destroy/recreate merely to switch authoring surface. Handle window-X, Escape, failed render, source switch, saver activation, Settings teardown, app shutdown and monitor removal without orphaned hidden windows or GL resources.
5. Mode/visualizer authority is singular: prevent two Studio instances/edit sessions against one preset. No independent configuration store, injected preset keys or unsafe override of curated operator presets.

### 2.2 Shared framework architecture, mode-owned bindings

| Reusable module concept | Single responsibility / evidence |
| --- | --- |
| Studio window/session controller | Show/hide/focus, reentry lock, fault recovery, multi-monitor DPI, life/retirement and parent Settings coupling. |
| Persistent Quick viewport adapter | Presents actual production Scene3D at deterministic logical input/time; selected/isolated ribbon overlay; safe editing gizmos; full-screen and small layout. GPU/context/thread costs and failure states tested. |
| Timeline & audio/source cockpit | Quiet/mid/peak, synthetic beat profiles, recorded real music, scrub/play/pause and truthful source/consumer meters. No second FFT/motion engine, and no unbounded synchronous main-thread playback. |
| Instrument registry & parameter adapters | Typed units, bounds, serialization, UI input scaling, undo/redo, accessibility, constraints, source-target relationships and no mode-specific hardcoding. |
| Scene selection & spatial gizmos | Direct dimensions, separation, axial roll, wave spacing and handles with safe geometry, correct world/local axes and numeric precision entry. |
| Curve/response editor | Graphable contribution mapping, source mix, attack/relax/elastic response and observable change with actual motion. Optional advanced legacy matrix view behind disclosure, not first-run. |
| Colour and material editor | Quiet/high gradient strips, draggable nodes, central/edge colour, material/opacity/highlights preview, colour transitions and localized crest light. |
| Population/lifetime editor | Particle birth distribution/spread/limit and 3s EoL fade timeline; separate strand motion/fade ~3–5s with tip/root ordering and reactivation. |
| Spatial volume editor | Mist clearing/softness in 3D cross-section, bounded distance falloff, light tint; floor reflection blur without exposing geometry invariants as unsafe settings. |
| Binding & theme facade | Uses shared SRPSS theme/settings tokens, consistent typography, focus states and deterministic source-to-editor linking. Window/theme skin never recolours authored scene. |

**Framework admission rule:** each instrument must be independently reusable for a second mode (Melt Pool or Concrete Rain) with different parameter schema, no duplicate authoring engine, and must be hooked to a real scene consumer and full canonical persistence. A standalone pretty QML demo without validated production adapter does not pass.

### 2.3 Semantic control choice, including range sliders

Use the instrument that matches the *meaning of the parameter*, not whatever widget is easiest to slap everywhere.

| Semantic intent / existing Waveform controls | Preferred editing instrument | Range-slider rule |
| --- | --- | --- |
| Number of ribbons, enable/disable, layer visibility and preset | Compact count/discrete selector and ribbon list with isolate/mute and direct selection | **Never** dual-range for count or modes. |
| Per-ribbon height, width, position/spacing, phase, carrier rate, axial roll | Visible 3D handles, rotation ring, single scalar precision fields/knobs with optional linked control | Quiet/peak pair only **if** the same geometric dimension deliberately has two actual musical envelope endpoints; otherwise one scalar. |
| Musical source mix and target routing | Source contribution meters/mix sliders plus a response curve and independently observable target preview; advanced matrix optional | No 84 default two-ended bars. Curves/sources/thresholds don't turn into faux ranges. |
| True quiet→peak response envelope (height excursion, accent brightness/count if both ends represent tied artistic states, etc.) | Compact dual-handle envelope with markers and visual interpolation, plus target curve/evidence | **Yes** when two endpoints are meaningful *correlated states*. Both handles must influence production output at calibrated quiet/hot, not random bounds or independent unrelated properties. |
| Musical attack/hold/release and spring behaviour | Graphical impulse response/envelope with movable control points, optionally scalars for exact timing | Generally **no**; these are temporal curves/timing parameters, not min/max intervals. |
| Quiet/peak colour stops, body gradient and peak shift | Editable two-strip gradient/colour node editor and live ribbon material preview | **No**; use gradient nodes, not RGB numerics or dual-range colour. |
| Rim glow, material opacity, lighting | Single controls, targeted visual preview and optional quiet/peak envelope where genuine | One scalar normally, legitimate two-ended brightness envelope where appropriate. |
| Particle birth region, horizontal/world spread and density | Bounded spatial emitter field, distribution curve/histogram, direct overlay, one numeric cap | **No** for spatial distribution; yes only for true musical quiet/peak density envelope. |
| Particle EoL and strand 3–5s lifetime/fade/reactivation | Birth/travel/fade timeline and single lifetime scalar; explicit bounded lifespan interval if truly authored | **No** if 'low/high' was mistakenly standing for life range or random distribution; a min/max band is legitimate only if both values actually represent lifespan bounds. |
| Mist clearance, density, distance and local light | 3D cross-section, spatial falloff curve, single intensity, colour selector | Usually **no** for geometry; use handles and falloff. A two-value interval may genuinely author world-space range only if semantics dictate. |
| Floor gaussian reflection colour-mass, roughness and floor brightness | Scene-local control and restrained radius/spread tools, numeric fine edit | **No** universal range; focus surgical effect, not texture research. |
| Camera save checkbox/projection | Shared checkbox / mode pickers; in-scene camera navigation | **Never** dual-range. |

Reject any editor where every parameter gets a dual-thumb slider by construction. Require a control inventory in the stage report: original key, semantic category, instrument, storage mapping, validation, actual low/high or spatial/temporal consumer, native evidence, and whether reusable.

## 3. Preview is the production truth, not a theatrical imitation

- The present `WaveformPreview` generates three offscreen static snapshots on request. A nonfunctional click and a placeholder remote from the editing context were reported. **Replace it** rather than simply embedding those three thumbnails in a prettier Studio.
- Use the retained Quick production scene/visualizer machinery with a safe instrumented viewport. Rendering may operate at a bounded quality while dragging, but the same material/geometry/logic rules and effective parameters must apply. No separate QML waveform geometry that only resembles production.
- A replayable 10-second deterministic source plus quick quiet/mid/peak thumbnails must show true bend, colour, family roll, travel acceleration, particle expiration and rim changes. The timeline's values and the production state should be mutually traceable. A full actual recorded clip, not synthetic-only examples, closes musical acceptance.
- On selecting a target, highlight the actual affected subset in the viewport, with diagnostic readouts for source→routed/temporal drive→drawn displacement/material energy. Missing camera, GL context failure or audio absence needs obvious errors rather than an inert button.
- Explicitly account for Qt Quick shared-context and renderer-thread ownership, resource lifetime, display/DPR changes and no duplicate simultaneous render storms. Real runtime performance under Studio preview and saver/display load is part of test evidence. Ensure safe teardown before Settings restoration.
- Static visual mock can be richer than current production scene; it is an *aspiration*, not proof that changing CSS/QML can deliver those pixels. Do not bake its colours or shapes as fake overlay imagery.

## 4. Production admission, tests and checkpoints

### Stage P1: provenance and semantic inventory
- [ ] Source-to-UI field inventory: names/units/bounds/current effective values, what is alive/unused/duplicated, legacy 14×6 data, saving owner and each real consumer. Capture current baseline, presets and dirty state. No preset/test value pins.
- [ ] Map next dynamics grammar (after audit) to a stable interface in the framework. If its semantics change, plan explicit migrations that preserve existing saved data as far as possible, with no hidden fallback or silent data loss.

### Stage P2: reusable shell, standalone visual instruments
- [ ] Prove Settings hide/open/error/restore/focus without significant new render owners. Integrate theme tokens and keyboard accessibility; test native multi-display/DPR and owner retirement.
- [ ] Prototype direct shape handles, curve editor and gradient strips using genuine typed adapters. Show objective source→control→serialization→production effect. No Studio copy of presets/motion simulation.

### Stage P3: real preview and complete authoring operations
- [ ] Route Studio preview through existing Waveform Quick scene and same logical audio/state; prove captured sample parity for quiet/mid/hot and chronology, not just static shader screenshots.
- [ ] Wire remaining visual instrument families to actual production controls; verify Save/Save As, Cancel, Reset, Custom transitions, operator-preserved camera-save checkbox, undo/redo, selected ribbon and source events; no lost hidden Settings state.
- [ ] Provide genuine example from at least one other future complex 3D mode's adapter, without building that mode's visualizer. This proves framework reuse instead of claiming it from class names.

### Stage P4: native acceptance and performance
- [ ] Make an operator-readable 5-minute workflow: choose ribbon, adjust vertical musical bend, compare quiet/hot, change gradient, widen particle emission, shorten fade, save Custom, close and reopen Studio, return to Settings, reopen and verify the same values. Record UI screenshots/video and tests at actual DPI.
- [ ] Reject unresponsive previews, numeric megagrids, pointless dual-range controls, page-sized settings drawers, UI theme mismatch, hidden window orphaning, context leaks, duplicated DSP/preset owners or a motion/camera mismatch between preview and saver.
- [ ] Measure the whole editor and native saver under reliable recorded-source load; use the same high-standard temporal and visual parity gates as any visualizer change. No builder is “finished” without actual hands-on authoring and operator UI sign-off.

### 4.1 Current technical facts and explicitly not-yet-accepted evidence

- Four-card forward migration and three initial presets are present as candidates. Do not force fourth ribbon into legacy authored three-ribbon scenes. The existing long-lens Perspective camera uses shared framed 3D mechanics; it is now the **only** supported scene projection. There is no Orthographic editing, acceptance, saved-view, preview or per-renderer parity branch to complete.
- Controlled PCM audits formerly showed raw floor OFF/ON parity for four 60s clips and passage medians about 0.46–0.74, but the live app still appeared dormant. The 3 November candidate changed the overly sharp passage curve and quiet event admission. **These are forensic leads, not post-change native acceptance**.
- The 3 November material receipt is `Docs/Reference/Images/Waveform_Ribbon_Material_Baseline_20261103.capture.json`. The newest supplied operator live screenshot provides appearance only; it cannot certify musical input, time evolution, cost or capture reproducibility.
- Existing loaded benchmark labels may be misleading: curated preset activation overwrote an intended fog Off comparison. Always verify exact effective applied settings in the same run. Earlier per-scene GPU numbers do not establish whole-frame game60 headroom.
- S3D-1 ribbon, S3D-2 particles, S3D-5 reflections and S3D-7 volumes are shared *dependency gates when touched*, not a requirement to restart/refactor all shared primitives before recovering Waveform. Any newly promoted primitive must be bounded, separately benchmarked, lifecycle-correct, dormant while Off and regression-checked against accepted modes.

## 5. Safety and completion semantics

- Operator-authorized experimentation **may replace** the current rendering technique, oscillator/elastic grammar and visual presentation. Checkpoint/push before overturning established decisions; document the rationale and an A/B. This is not permission to damage unrelated visualizers or override operator-authored presets without a recoverable path.
- `Waveform_Ribbon_Lab_Plan.md` records the live stages/evidence; this doc only owns production/UI architecture and migrations. When accepted, durable design belongs at the existing `Spec.md` / architecture/guide owner, not as duplicated live TODOs forever.
- Successful source tests establish invariants; successful native preview establishes rendered compatibility at specific poses; operator comparison/listening establishes actual perceptual fit. **All three are required**, along with performance/lifecycle evidence, to declare the whole Studio and waveform experience satisfactory.
