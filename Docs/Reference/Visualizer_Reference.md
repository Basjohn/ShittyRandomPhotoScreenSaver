# Visualizer Reference

Current visualizer behavior and accepted presentation architecture.

## 1. Modes

Visualizer uses its own logical production and viewport/scale geometry; ordinary-widget retained-child Edit normalization does
not own its paint or cadence.

`core/settings/visualizer_mode_registry.py` is the sole catalog authority. `VISUALIZER_MODE_IDS` / descriptors own current
membership, display names, shell/clip policy, lazy runtime/renderer/Settings/capture wiring and capability metadata. **Do not
mirror the registry here as a hand-counted list.** Adding a descriptor must automatically join registry-derived Settings,
dormancy, switching and harness coverage.

This reference documents shared policy plus mode-specific exceptions where they matter. Experimental status is an admission
state, not permission to create a private scheduler/presentation engine. Shared-profile routing is explicit descriptor
metadata. Spectrum-family 3D modes reuse the shared DSP implementation but own their persisted technical and source profiles; old borrowed values are promoted only once. **Spectrum bar shaping is a descriptor-declared capability**, not a universal BeatEngine operation. Only Spectrum, Extruded Spectrum and Shockwave evaluate authored Spectrum shape nodes/lane strengths. Bubble and Sphere consume raw FFT/zone/control/transient data without that stage. Sine heartbeat and Dev Curve layer motion consume a pre-AGC musical-energy output instead of shaped Spectrum bars; Dev Curve applies its separate authored layer shaper in its logical runtime. Oscilloscope retains waveform analysis. The single shared engine fences the policy on every activation/compute snapshot, with no second DSP/capture authority. Bubble's accepted response is protected by differential synthetic PCM tests against the former shaper-enabled path (energy, transient, onsets and adaptive-floor history); never replace this with static curated preset-value assertions. Heavy implementation resources remain lazy and retire through the normal owner.

### Settings declarations

`core/settings/visualizer_mode_settings.py` owns every registered original mode's body declarations; `iter_mode_settings()` is
the membership authority. Canonical defaults and editable presets own values. The model, appliers and lazy body use
the same declared type/range/owner, while bespoke editors retain named Custom build/load/collect entries.

Control types: `Slider`, `Toggle`, `Choice`, `Colour` and the **visual controls** (2026-10-18) `Range` (two
values on one bar, low <= high, persisted `[low, high]`: the reactive quiet..loud span), `Triangle` (three shares
summing to 1 placed by one node, e.g. Fuse / Pop / Bounce) and `Direction` (`[around, height]` degrees on a disc,
around wrapping, height clamped; "arrow" for a stream, "light" for a light; equal height bounds make a compact
angle dial for 2D directions such as gradients, shadows or screen-plane rays, a visual replacement for 8-way
direction drop-downs). Their widgets live in
`ui/widgets/visual_controls.py` (`RangeSlider`, `TriangleMapper`, `DirectionMapper`) so any Settings builder
(Transitions, widgets) can adopt them: they paint the shared slider's theme tokens (groove, fill, 16x10 pill
handle, hover/pressed, and the page's single last-moved highlight via `shared_styles.mark_last_moved_control`),
repaint on theme change, ignore the wheel, offer keyboard control and an accessible description, and save once per
gesture or keyboard step (`valueCommitted`; the value label follows `valueChanged`). Use `when` conditionals and
nested buckets heavily so a body shows only what the current choices use.

Spline Curve's scalar controls are logical-owned, including ghost and foreground styling, because its logical frame
snapshot consumes them. Its four-layer spline editor remains Custom with independent nodes, power, enabled/alpha/offset,
opaque outlines and ranked stacking. The shared builder preserves paired FX toggles, signed offsets, conditional rows
and existing buckets. Loading either scalar controls or the Custom editor emits no save or preset-change signal.

Extruded Spectrum's scalar controls and live orbit ranges are spec-owned. Its composite Rainbow surface selector,
mirrored/linear shape editor and shared smoothing controls remain Custom entries; Bar Appearance and technical controls
retain their existing tab/descriptor owners. A `source=True` control keeps the descriptor's existing source-profile
projection: shaping reaches BeatEngine, and ordinary ghost aliases reach their shared logical/presentation consumers.
Generic appliers create no unused private attributes for these authored source keys. Availability metadata keeps the
rejected cast-shadow controls disabled during build, preset load and reset while retaining their saved values. Orbit
turn/tilt remain excluded from the body/preset payload, and Rainbow Ghost remains independently editable.

Spectrum's scalar declarations retain its distinct consumer routes: source response enters BeatEngine, render mode
maps once to the logical solid-bar boolean, and Unique Colours maps once to the existing per-bar presentation field.
Declared input hooks reuse canonical alias migration; obsolete UI attribute/save paths are retired. Render-style buttons,
shape/lane authoring and smoothing stay Custom, with the shared Bar Appearance/Rainbow groups outside the body. The spec
preserves Spectrum's signal policy, slider-position conversion, conditional rows and the wider saved border-radius range
than its UI slider offers. Nested hydration restores the caller's prior signal-block state.

Sphere's response and frame-snapshotted styling declarations feed its existing configure-owned immutable logical bundle.
Mirror and bodyless orbit remain presentation-owned; Finish is persisted authoring-only metadata. Frequency Zones,
Finish and combined RGBA/alpha controls remain Custom hooks. `enabled_when` disables visible controls while preserving
latent values; it cannot override an unavailable capability. Recommended slider marks remain UI guidance. Trusted runtime
admission retains Sphere's explicit errors for malformed values and its direction normalization. Derived control/consumer
memberships are cached as immutable declaration data, so frame extraction adds no recurring membership allocation.

Bubble's body settings use that same spec for model fields, admission, serialization, lazy controls and existing
logical/presentation consumers. Drift plus Swirl is a Custom projection of the single `bubble_drift_direction` key;
it creates no persisted Swirl toggle. The core gradient semantic resolver promotes old directions once at model/UI
ingress, and collection/serialization stamps the current version. Ghost enablement feeds both existing consumers
once, while opacity/decay remain presentation-owned and tail length remains logical-owned. Rainbow, Bar Appearance
and Technical keep their external owners; the existing Layout bucket has no body controls.

Bubble preserves its distinct domains: pulse sliders/storage span `0..2` but runtime caps at `1`; stream reactivity
spans `0..2` with runtime cap `1.25`; stream-speed cap authors `0.5..4` while storage/runtime admit `0.1..4`;
contraction authors `0..1` while storage/runtime admit `0..2`. UI hydration retains truncating slider conversion,
except Ghost Decay's existing rounding; integral population/probability ingress truncates. Friendly choice labels
persist canonical codes, and size labels retain their existing thousandths units. Other invalid/out-of-domain
imports are repaired by the canonical typed spec rather than retained in a second permissive Bubble model path.
This declaration migration does not change simulation, renderer equations, audio analysis or cadence. Full-output
native replay/GPU comparison is routed through `Docs/Reference/Harness_Index.md`; audible/physical timing remains
subject to Bubble Temporal Fidelity.

### Spectrum-family ghost and rainbow ownership

Spectrum and Extruded Spectrum expose separate **Rainbow Ghost** controls in their existing Ghost settings. Each setting persists under its own mode (`spectrum_rainbow_ghost`, `extruded_spectrum_rainbow_ghost`) and colours **only existing falling-peak geometry**, not the bars, faces, edges or reflection. A ghost uses its own enabled/opacity/decay ownership and remains visible when the authored bar border is black or transparent. Spectrum's segmented and solid paths use the same spectral ghost rule; a ghost must never be recoloured a second time by Rainbow Borders. Extruded uses its existing Scene3D ghost-column pass and hue, not a second texture, draw loop, clock or BeatEngine. Both advance colours on their existing Spectrum logical animation time; dormant/disabled modes create no extra work. User-authored presets are editable and are not golden-value test fixtures. Real GL tests must verify visible peak-only pixels with dark borders and bar-fill independence.

## 1A. Registered modes vs enabled modes

Per-mode admission/dormancy is implemented. `core/settings/visualizer_mode_registry.py` owns all registered descriptors and lazy wiring; persisted `mode_activation` owns user mode admission; the top-level Visualizers Settings tab builds mode bodies lazily and keeps disabled/unselected bodies dormant. The ownership distinction is:

```text
all registered canonical modes
    -> schema/default/migration/persisted settings authority

currently enabled modes
    -> Settings mode pills, selection/cycling, frame-runtime construction, renderer import/construction
```

Disabled modes retain their configuration without contributing meaningful runtime work. If the Visualizer family is enabled, at least one mode remains enabled, but any registered mode may be the sole enabled mode when explicitly admitted. Canonical per-mode activation defaults decide initial admission; experimental modes should remain dormant by default unless product acceptance explicitly promotes them. Admission must remain behaviorally transparent to cadence, source freshness, presets, renderer transfer, scale/extent and Bubble/BTF.

### 1B. Experimental mode policy after the shared Scene3D foundation

Sphere is the legacy migration case, **not** the template for building another private renderer stack. A new experimental
mode created after shared Scene3D exists joins the canonical registry, logical snapshot/cadence contract, shared
Scene3D/compute/resource/material/quality substrate, lifecycle and dormancy owners immediately. "Experimental" means
default-off/not-yet-product-accepted and permits private reaction semantics and mode-owned settings; it does not mean
private scheduling/presentation authority or a disposable GPU engine. Promotion to stable should normally change
admission/status/defaults and close acceptance gates, not require reimplementing the mode on a second substrate.

### Direct 3D interaction geometry

For unframed 3D modes, Alt+right starts a native press-scoped origin in the current display's direct CUSTOM transaction. An Alt+wheel resize may keep that transaction open; a later Alt+right press must rebase the move origin to the **current** rectangle before applying the new pointer delta, otherwise stale unscaled positions teleport the stage. Freeform 3D whole-stage wheel scaling preserves the stage **centre** (subject to display-edge clamp), while planar/ordinary widgets retain their own established anchor rule. These whole-stage paths may not create a timer or borrow geometry from a sibling layout profile. Framed Neon Lake
Basin routes the same Alt inputs to internal scene pan/scale instead, with no CUSTOM geometry transaction; see
[Neon Lake Basin](Neon_Lake_Basin.md).

Framed 3D modes also admit ordinary held-left orbit after Qt's drag threshold in interaction/Ctrl mode.
The actual retained card/stacking determines admission. Glyphs, visualizer descendants and higher controls
retain first refusal; lower passive handlers cannot veto the visible card. Windows confinement uses the real
client pixel rectangle, preserves foreign owners and retains failed cleanup at the existing runtime deletion
gate. Release/reset/menu/Edit/mode/focus/topology/close cancel through one unwind. Cursor hiding/reveal reuses
the existing fade timer/cache; held motion adds no polling, timer or cursor allocation. Stock native-arrow
states explicitly decline because no alpha raster is available; existing menus already exclude orbit.
An existing exclusive/mouse grab must retain its complete press/release sequence even below the card. The
lower-passive-handler exception does not authorize stealing that sequence; the candidate's remaining gap
and its required falsifier are tracked in `Current_Plan.md` → Shared camera gestures.

Framed 3D modes reuse `VisualizerPresentation.qml` for a noninteractive keyboard/mouse hint at the top right.
A pointer entry gently reveals the supplied artwork with the hover chrome; fade-out begins after five seconds even
if the pointer stays inside. Internal movement, menu dismissal and Ctrl changes do not restart the visit;
leaving/re-entering admits another visit.
The retained animation is suppressed during Edit/direct layout gestures, menus, hidden/borderless presentations and
modes without framed scene transforms. Disabling hints or retiring/hiding the presentation also retires its passive observer
and clears the visit. It adds no input hitbox, polling, Python timer or settings read on pointer motion.
Widgets → General → Appearance owns **Show Glyphs** (`input.always_show_glyphs`, unchanged storage key) and the
independent **Show 3D Control Hints** (`input.show_3d_control_hints`, default on). Both use the normal deferred
Widgets save/close-flush and reset path. Hint artwork is immutable RCC content sourced from `ui/assets/widgets/visualizer/`.

## 2. Capability model

Capability is mode-owned and registry/test-discovered, not inferred from catalog position or a fixed number of modes. Shared
rules are:

- every admitted mode participates in the retained Visualizer reveal/fade and lifecycle owner;
- live audio reactivity requires a fresh current source; playback/presence semantics remain mode-specific;
- idle self-animation and presentation-owned idle scenes are explicit mode behavior, never a generic clock entitlement;
- shell/clip/viewport/orbit/overflow/rotation/prepared-reveal behavior comes from descriptor capability or the mode's immutable
  presentation parameters;
- new modes extend registry-derived capability tests instead of requiring prose count updates.

Paused Spectrum remains intentionally mixed: presentation may remain ready while reactive source readiness is false. That
exception does not create a second source/cadence authority.

## 3. Logical cadence

Primary owner:

`VisualizerLogicalRuntime`

Supporting logical/source modules remain Python.

Durable accepted flow:

```text
source / engine
    -> sole VisualizerLogicalRuntime
    -> mode-owned logical frame runtime / capture (spectrum/oscilloscope/sine/bubble/devcurve/sphere)
    -> immutable latest logical publication
    -> GUI/Quick synchronization owner
        -> current resolved presentation state
        -> complete VisualizerRenderSnapshot
        -> existing VisualizerSnapshotBridge
    -> Quick take-for-render (not a paint ack)
    -> one QSGRenderNode / lazy mode renderer
    -> render-node-local SDF/stencil clip
    -> retained Quick shell/chrome
    -> admitted display's standalone QQuickWindow
```

Bridge binding alone does not prove delivery: a complete current snapshot must actually be composed, published and admitted by the retained visualizer item.

Old GUI `present_tick`/compositor presentation is retired production architecture. Any surviving reference belongs to historical evidence or caller-dead residue and must not be restored merely to satisfy an old harness.

## 4. Presentation ownership

Destination:

- visualizer pixels live inside the display's sole `QQuickWindow`;
- no separately presented visualizer surface;
- no `QQuickWidget`;
- no independent swap/vsync owner;
- no self-driven visualizer repaint loop.

The historical `SpotifyBarsGLOverlay` presenter is retired. A surviving import/reference is cleanup residue unless exact caller proof identifies a neutral non-presentation contract.

## 5. Logical / presentation split

Logical worker owns plain-data evolution.

Presentation side owns:

- current immutable scene state;
- presentation policy;
- presentation geometry;
- optional shell/chrome;
- content clipping;
- fade/reveal;
- GPU resource use;
- physical presentation.

The worker does not mutate Quick items or GPU resources.

**Musical onsets (event-driven modes).** The transient bus publishes each onset as an immutable `MusicalOnset`
(`widgets/spotify_visualizer/transient_bus.py`): a process-wide serial (it never restarts, not even with a replaced
bus), the analysis timestamp, the kind, the clipped strength (0..1), the unclipped magnitude (0..3: how far above its
adaptive threshold, relative to it, so a big hit still differs from a medium one), the absolute post-noise-floor,
pre-AGC loudness it happened at (the bus's own input is loudness-normalised, so a near-silent passage triggers as
readily as a loud one) and its presence (that loudness against a 6 s running level). The last 16 are one tuple the
audio lane replaces per onset; `BeatEngine.get_onset_events(after_serial)` returns the ones a consumer has not taken.
Sampling the bus's per-frame onset flag instead depended on the analysis and logical cadences lining up. Bars:
`tests/test_qtquick_shockwave_grid.py`. The shared primitive for Shockwave Grid, Reactive Particle Field and lightning.
`BeatEngine.get_musical_level()` reads the latest frame's (loudness, presence), the same measurement an onset there
carries, for modes whose events come from elsewhere (Voxel Sphere); near-silence does not drain the running level.
What an onset *earns* follows one shared rule beside them (`musical_weight`, `musical_emphasis` on the fixed
loudness scale; nothing learned from the track). Real scales (loudness 3-17 in music, presence about 1): `Docs/Guides/Visualizer_Reactivity_Authoring.md` 2A. Bars: `tests/test_transient_bus.py`.

**Shared 3D view and lines.** Every 3D Visualizer orbits and projects through `SCENE3D_ORBIT_GLSL` /
`scene3d_orbit_project` (`rendering/gl_programs/scene3d.py`): turn about the vertical axis, tilt toward the camera
about a `pivot` that then sits at an `anchor` in front of a pinhole camera; a mode supplies only those constants and
its own fit (Extruded Spectrum pivots at mid-bar; Neon Lake Basin pivots about the basin centre). Lines use the shared
screen-pixel coverage helpers; Neon adds curved surface wire coordinates through its dedicated reference. A new 3D
mode reuses the shared projection instead of copying it. See [Neon Lake Basin](Neon_Lake_Basin.md).

**Prepared reveal (3D modes).** A mode whose descriptor sets `prepared_reveal` (Extruded Spectrum, Shockwave Grid)
offers `prepare_step(frame)`: on a hidden frame (content fade 0) the render host lets it compile or allocate one unit
of what its first visible frame of that activation would create (a program, a mesh, the stream ring, the target, the
glow chain, the backdrop copy), at least `PREPARE_SPACING_S` (30 ms) apart, and records the (mode, activation) as
prepared; a visible draw records it too. The owner keeps a mode or preset reveal in `waiting_target` (fade 0) until the
render thread reports the activation prepared, and reveals anyway after `_PREPARED_REVEAL_DEADLINE_S` (1.5 s) so a
window that renders nothing cannot strand the activation. Nothing is preloaded: only the incoming activation prepares,
and only what its parameters need. Measured at a 1600x900 card (RTX 4090), first visible frame: Extruded 6-8 ms ->
3-4 ms, Shockwave Grid with glow 22 ms (139 ms with a cold driver shader cache) -> 4 ms; the steps themselves cost
0.5-11 ms each on hidden frames. The first hidden frame of a session also imports the renderer's modules (~20 ms
once, shared with the 3D transitions once those have run). Bars: `tests/test_visualizer_prepared_reveal.py`.

Audio analysis uses one persistent serial `visualizer.audio_analysis` compute lane with one in-flight packet plus newest-pending source replacement. Detached DSP state is retained across ordinary frames and rebuilt/fenced only at real config/activation/reset epochs; no generic per-frame Future/task fallback is part of the current architecture.

System loopback capture has one separate native owner: the shared BeatEngine lazily creates its
`visualizer.audio_capture` affinity lane on ThreadManager's dedicated `audio_capture` worker.  Device/backend creation,
open, restart and release remain serial on that worker. The GUI changes one newest desired state and admits at most one
drain; a blocked open cannot grow a lifecycle queue. Pending open is `STARTING`, and callback grace begins at native
success. Restart reports admission; failure is logged by the owner. Stop immediately fences generation, activation and
buffer identity at final callback publication. Failed close retains native ownership in the backend and the affinity
lane's `resource_held` observation; a joined worker alone does not close the lifecycle barrier. The Windows selector is
the canonical PyAudioWPatch WASAPI path; it is not an environment-variable switch to another backend.
Capture opens the authored block once: positive values are exact and Auto uses the native driver's unspecified value
`0`. Rejected opens are loud failures, not admission to a sequence of alternative block sizes. The shared BeatEngine
registry retains the actual owner graph while capture is opening, draining or holding failed-release resources.

Configuration follows the consuming owner. Values used by authored logical evolution or mode-owned frame runtimes are
presentation-neutral resolved configuration; renderer-only style/chrome is presentation-owned. Legacy widget attribute
location and Settings subsection are not ownership rules.

The resolved technical cache is deliberately not monolithic: DSP/capture controls apply through the controller-owned shared
BeatEngine/audio-worker boundary, while technical-origin transient controls that authored logical evolution reads live on
controller-owned logical state. Bar-count reconfiguration keeps controller, engine generation and logical display-bar
mirror/freshness state coherent. Legacy overlay-only mirrors have no current role without an exact retained consumer.

## 6. Latest-state semantics

One slot/latest wins.

No FIFO, catch-up, or paint acknowledgement.

Every authored event integrates before later state may supersede it.

## 7. Presentation policy

Do not assume every possible visualizer must draw a card.

Minimum policy vocabulary:

```text
shell:
    CARD
    FRAMELESS

clip:
    CARD_INTERIOR
    VIEWPORT_RECT
```

Descriptors that use the shared card path select `CARD + CARD_INTERIOR`; free-standing modes may select `FRAMELESS + VIEWPORT_RECT`. New modes must declare policy explicitly. The registry, not this prose, owns which modes currently use each policy.

That removes card background/frame/shadow while preserving the same QQuickWindow, presentation root,
fade/lifecycle and assigned viewport.

## 8. Presentation geometry

One authoritative display-local geometry snapshot feeds:

- outer shell/card rect where present;
- inner content rect;
- custom render item;
- viewport/scissor/scene clip;
- DPR;
- mask/border;
- CUSTOM geometry;
- uniform visual scale;
- content viewport extent/aspect.

Do not create separate QWidget and Quick pixel geometry authorities.

Do not represent freeform aspect changes by stretching final rendered pixels.

## 9. Clip

For current carded modes, custom GL remains clipped to the rounded **inner card path** so it sits
visually above the fill and below the frame/border.

Historical R-21 proves that shrinking the content geometry to hide bleed is not acceptable.

The selected Quick implementation is **one render-node-local SDF/stencil clip host** inside the same
`QQuickWindow`/`QSGRenderNode`. The `QSGClipNode -> QSGRenderNode` handoff was attempted under PySide 6.9.1
and **failed** that runtime's bar (rounded cases exposed stencil metadata whose framebuffer contents did not
match; rectangular cases could expose an invalid sentinel scissor). Any proposal to replace the current clip owner
must first repeat that proof on the current runtime; version advancement by itself does not reopen the failed handoff.
That failed handoff is
**not a selectable implementation** and must not be reopened or kept as a fallback unless new
contradictory evidence later justifies it.

The local host can compose with valid inherited clip state: when a genuine incoming scissor/stencil
value corresponds to real framebuffer contents it nests above it, and it restores the temporary stencil
contents and every touched direct-GL state before returning to Qt. The nested real-GL clip smoke proves
exactly that narrower fact; it does **not** prove that arbitrary real PySide `QSGClipNode` metadata is
trustworthy.

Quick clip geometry must derive from Quick chrome; do not copy centred-QPainter border formulas.

Frameless modes normally use a rectangular viewport clip.

## 10. Card / frameless shell

### Carded policy

Preserve visual fidelity:

- background;
- border/radius;
- card shadow;
- opacity;
- customization;
- alignment;
- fade.

Stable shell pixels must not be expensively rebuilt every visualizer frame.

### Frameless policy

Architecture permits a mode to omit:

- background;
- border/frame;
- card shadow.

FRAMELESS + VIEWPORT_RECT remains inside the same retained Quick scene/lifecycle; it omits card chrome rather than creating another surface. A mode may additionally declare overflow capability, in which case its renderer can extend beyond the local viewport without inventing a card or second presentation owner.

Frameless does not mean display-global or separate-window rendering.

## 11. Canonical aspect, scale and viewport extent

Quick deliberately retires the pre-Quick per-mode preferred-height/growth customization:

```text
spectrum_growth
osc_growth
sine_wave_growth
bubble_growth
devcurve_growth
```

Those values altered card height independently of common width and were already ignored once CUSTOM
geometry owned the old visualizer. They are not authored mode behavior and are not current
settings.

Modes using the shared card policy share one canonical baseline viewport aspect ratio. A mode switch or
preset load does not change viewport/card shape.

That canonical baseline aspect is **1.5**. It is the sensible DEFAULT shape for ordinary non-CUSTOM
layout, not a universal invariant. Distinguish three concepts:

- **default/baseline aspect (1.5)** — the default shape for the shared card policy;
- **resolved runtime size** — for normal non-CUSTOM layout the layout owner resolves an appropriate
  width from widget/media/free-space rules and derives height from the 1.5 baseline aspect (screen-fit
  clamps uniformly); mode presets tune authored visual behaviour, never viewport/card dimensions;
- **explicit viewport extent** — the logical/render world, which required CUSTOM edge operations intentionally push off
  1.5 (all modes reflow, never anisotropic final-pixel stretch).

The literal `420x280` (`CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE`) arose from layout history and is
**not** a required/sacred visible or runtime size. It is retained only as an internal reference
coordinate extent corresponding to the 1.5 aspect, useful for normalization and authored stroke/radius
scaling (e.g. DevCurve's baseline content extent). Do not freeze runtime visualizers to 420x280, and do
not delete the 1.5 default aspect in favour of arbitrary mode-specific card shapes; the retired
`*_growth` values are not an alternate aspect/height authority.

Visualizer geometry then distinguishes:

```text
uniform scale
```

from:

```text
viewport width / viewport height
```

Whole-size operations preserve the baseline aspect:

```text
scroll-wheel resize -> uniform scale
corner-handle resize -> uniform scale
```

Required retained CUSTOM edge operations change viewport playroom at the same scale:

```text
left/right edge -> viewport width only
top/bottom edge -> viewport height only
```

Expected adaptation at constant scale:

- Spectrum reflows/redistributes bars across available width/height;
- Bubble expands/reflows its position, trail and motion world without stretching circles; stream/drift deltas project once per expanded axis, nonbaseline trail smear is solved in renderer-content coordinates, and swirl orbit/birth geometry removes the independent domain axes so visible travel does not fall by `1 / domain_axis` or distort with aspect; its authored radius projects through the equal-area canonical height described below; collision/spawn policy remains canonical normalized content-space separation, with unchanged BTF event behavior;
- Bubble lifecycle distances (entry depth/margin, cluster spread, exit/drain and contraction grace, overlap retry and pre-entry prediction) are likewise renderer-content values projected once per expanded axis; canonical literals and random draw order remain exact;
- Oscilloscope/Sine/DevCurve adapt domain while keeping stroke scale;
- Sphere uses aspect-correct projection and stays round.

Every registered mode is viewport-resize-capable through its declared presentation policy; carded and frameless policies adapt their authored domain through their own geometry contract. The core Bubble capability/reflow path is landed. Do not reintroduce a Bubble false gate to conceal an implementation defect. Committed viewport truth remains separate from temporary CUSTOM working geometry; any newly reproduced spatial defect must preserve authored Bubble response and the binding BTF contract rather than reviving phase-specific gates.

## 12. Bubble / BTF

`Docs/Guardrails/Bubble_Temporal_Fidelity.md` is binding.

Bubble is a canary for shared timing and must not receive mode-specific cadence hacks to hide
presentation defects.

Viewport geometry changes are spatial configuration, not logical cadence authority.
Bubble radius and response project through `sqrt(content_width * content_height / 1.5)`. This explicit
operator correction preserves complete radius excursions across equal-area shapes rather than making wide
views weak and tall views oversized. The same actual-area metric sizes outlines, with a framebuffer-pixel
coverage footprint independent of saved logical extent/uniform-scale encoding. Bubble-local specular offsets and
ellipse orientation retain the canonical content aspect at the same scale/inset. The Quick payload
retains the already validated immutable BubbleFrame tuples; native uploads still use persistent
render-thread float32 buffers.

Consume-once kick/snare/vocal events forward-carry a bounded motion accent through Bubble's existing stream-burst state.
This affects stream/drift displacement, not authored motion settings, pulse/radius authority, cadence, or clock ownership.
Canonical/wide/tall runs of the same event must retain equal content-space head/trail travel, one event delivery and an
identical radius sequence. Raw expanded-world displacement is not a valid cross-viewport reactivity comparison.

## 13. Playback

Pause/Play preserves:

- logical runtime identity;
- mode identity;
- source/capture policy;
- no visualizer pause debounce;
- prompt visible authored state change.

Historical/current `BeatEngine` retains the same cold-Play ramp and warm-capture policy. Newly introduced visible delay must be localized across Media truth -> owner -> source freshness -> mode readiness -> publication -> retained draw rather than hidden by retuning the historical ramp.

Normal Pause/Play must not turn into renderer/window recreation. Current timing/reactivity authoring guidance lives in `Docs/Guides/Visualizer_Reactivity_Authoring.md`; Bubble-specific temporal evidence remains in `Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

**Reactivity without Dynamic Floor:** no mode may depend on Dynamic Floor (it learns a level from the track and degrades as a song continues). `get_bubble_energy_bands` divides by `_raw_bass_avg`, which only adapts while the floor is ON; floor-OFF it equals the manual floor and pins the lanes. A mode needing floor-independent body response reads raw lanes on fixed real-scale references through its own getter, as Extruded Bubble does with `get_extruded_bubble_body_bands`, and is measured against 2D Bubble with Dynamic Floor ON (Parity+). Method, measurements and tools: `Docs/Guides/Visualizer_Reactivity_Authoring.md` §13A; general lessons for new modes (driver saturation, block size, authored maxima, collisions on kinematic motion, test thresholds): §13B.

## 14. CUSTOM / Edit

CUSTOM/Edit preserves one authoritative committed geometry.

Control UI may remain QWidget if appropriate.

Live runtime pixels belong to the Quick scene; edit plumbing must not recreate a
second accelerated presentation surface.

**CUSTOM geometry identity is mode-compatible, not merely 2D versus 3D.** The generic CUSTOM schema already supports
arbitrary `geometry_variant` values under one widget/display key. Visualizer descriptors therefore expose two separate facts:
`geometry_kind` selects interaction mechanics (`planar` or `freeform_3d`) while `layout_profile` selects the persisted CUSTOM
variant. Current planar modes share `planar`; Extruded, Shockwave and Sphere use `3d:extruded_spectrum`,
`3d:shockwave_grid` and `3d:sphere`. A future pair of modes may deliberately share a profile only when their stage geometry is
actually compatible. This remains one CUSTOM session/commit/hydration owner, not per-mode X/Y settings and not a second 3D
store. A hidden hot-swap restores the target profile before reveal and never lends the outgoing profile to a missing target;
missing profiles begin from authored baseline. Legacy `default` / `freeform_3d` are one-way migration input claimed by at most
one canonical profile, never permanent competing authorities.

For `freeform_3d`, the saved rectangle is a **stage/viewport**, not a promise that the currently projected scene fills it.
Edit keeps that rectangle as the only persisted geometry while also showing a derived projected content envelope and a
perspective-correct read-only wireframe cage. The cage consists of eight renderer-consistent projected vertices, twelve edges
and an `N` at the canonical north/far face centre. It is paint/orientation chrome only: never a snap/collision/persistence,
Fit Scene, movement or resize authority. Extruded derives it from its production projection/fit, Shockwave from its production
camera projection, and Sphere from its stage/perspective convention. These records update only on relevant Edit/view/geometry
edges, not per-audio-frame. Turn/tilt and optional internal scene pan/scale remain mode-owned view settings, excluded
from artistic presets and never copied into layout profiles. For framed Neon Lake Basin, the fixed card owns selection
and its internal guide stays clipped derivative paint; see [Neon Lake Basin](Neon_Lake_Basin.md).

Required visualizer resize semantics:

```text
scroll wheel   -> uniform visual scale
corner handles -> uniform visual scale
left/right     -> viewport width
top/bottom     -> viewport height
```

Viewport resizing is part of the current CUSTOM contract, not optional QoL and not permission to stretch a
rendered image. Save/Cancel and layout slots preserve scale and extent separately.

Modes whose descriptor sets `content_rotation_capable` admit the shared CUSTOM **content quarter-turn** control. Orientation is layout/presentation state, not a Visualizer setting or preset value: a sparse `content_rotation_quarters_by_mode` map lives inside the existing CUSTOM `size_payload`, keyed by canonical mode ID, with missing/zero meaning 0°. A legacy global `content_rotation_quarters` scalar is interpretation-only compatibility input; new writes use the per-mode map. Odd quarter-turns swap the effective logical viewport axes before authored mode presentation and the shared render contract maps that logical world back into the unchanged physical card. This preserves stored X/Y/extent/uniform scale and avoids stretching finished pixels. Save/Cancel, layout slots, display transfer and Restore semantics remain in the existing CUSTOM owner. Rotation is event-driven and adds no timer, poller, alternate Visualizer cadence or per-frame Settings lookup. Modes without `content_rotation_capable` remain excluded through descriptor capability metadata, so the feature cannot couple an ineligible frameless mode back into the carded-mode contract.

## 14A. Visualizer display admission / semantic mode + preset cycles

Current product semantics admit one visualizer instance. Python orchestration resolves the requested monitor against actual
participating Quick displays and constructs exactly one visualizer owner. Non-owning displays do not duplicate controller,
source or authored logical runtime ownership. Preserve committed/CUSTOM geometry and the established requested-monitor
fallback/transfer behavior.

Retained visualizer double-click means cycle visualizer mode. The global display double-click means next image only when no
retained family/visualizer semantic hit consumes it.

Retained visualizer **middle-click** is a separate runtime action: advance exactly one preset in the current mode, wrapping
through that mode's curated slots and Custom without changing mode identity. `Custom` is a user-owned snapshot, not an
ordinary preset payload: leaving it snapshots the exact current Custom state and returning restores that state. Runtime preset
cycling persists only the visualizer settings subtree and must not refresh unrelated Media/widget state. Quick/QML may report
the retained hit; Python owns preset resolution, activation and persistence.

"Exact current Custom state" means the mode-owned authored payload only. Widget admission, `position`, `monitor`, and outer
CUSTOM geometry are separate live authorities and must remain unchanged while a preset or Custom snapshot is applied.

## 14B. Retirement

Visualizer generation retirement requires successful stop/join of the sole authored logical runtime. Failed join is a hard
barrier and leaves the owner/generation unresolved; it is not permission to detach presentation and continue display teardown.

## 15. Validation

Use:

- deterministic authored-behavior goldens;
- logical scheduler tests;
- BTF;
- source freshness tests;
- real renderer/output tests where visibility matters;
- canonical settings/preset -> technical-engine/logical/presentation owner routing;
- real retained-item snapshot consumption rather than direct bridge-drain-only proof;
- Quick runtime-shaped presentation checks;
- card-inner clip tests;
- cardless-policy scene test;
- default/wide/tall geometry tests;
- lifecycle generation tests;
- installed manual review.

A test name does not prove it exercises the real output path.

## 16. 3D scene foundation (optional for modes)

Extruded Spectrum and Shockwave Grid use the shared 3D foundation the transitions use. Voxel Sphere also uses its GPU
resource/ring substrate while its reaction semantics remain mode-owned and its authoring/product promotion remains in
`Docs/Reference/Sphere_Visualizer.md` (already operator-accepted). The binding lessons in
`Docs/Reference/Transitions.md` ("3D foundation lessons") apply to modes as well.

**Framed physical camera (the standard for framed 3D modes).** Extruded Bubble's camera is the standard
(operator 2026-10-24): `core/settings/framed_camera.py` owns orbit, dolly (Scene Scale), eye-translating pan,
Camera Position, Camera Field of View and bounded eye admission; `widgets/spotify_visualizer/view_orbit.py` owns
held-key flight on the capture clock. A mode opts in with `framed_camera="module:SPEC"` on its descriptor and gets
W/A/S/D flight, Q/E yaw, Shift+W/S pitch, held-left orbit, Alt+right pan, Alt+wheel dolly, R home and the control
hint. Its renderer resolves the eye through the same functions (bounded by its floor hook over the exact card) and
projects with that eye; Neon Lake's `BasinView` is the raster example, EB's ray-traced scene the volume example.
Specs: `core/settings/extruded_bubble_camera.py`, `core/settings/neon_lake_camera.py`.

- **GLSL:** include `SCENE3D_GLSL` from `rendering/gl_programs/scene3d.py` (camera with a real near plane, lighting,
  planar shadows, streaks, integer hash, impulse and departure helpers). Every function has a CPU mirror in the same
  module, checked on the GPU by `tests/test_scene3d_glsl_mirrors.py`.
- **GL helpers:** `rendering/quick/scene3d/`: `MeshResources` (programs, meshes, depth clear), `SceneTarget`
  (multisampled target sized to the card's pixel rect), `blend_scope`, the shared particle and planar-shadow passes,
  and the bendable grid (`grid.py`: a Spectrum Terrain or Waveform Ribbon writes only its `sceneDisplace`). Draw inside
  `with target.scope(frame, samples, resources): ...` in the mode's `render`; the clip host already wraps that call,
  so the composite stays inside the card clip.
- **Time:** only the snapshot's logical time. Never real seconds and never a new clock (one authored clock, R-69,
  Bubble Temporal Fidelity).
- **Resources:** owned by the mode renderer, reused while the card fits its 64 px allocation bucket (a CUSTOM resize
  drag does not reallocate per frame), released in the renderer's `release_resources` when the mode retires or is
  disabled. Nothing is allocated per frame.
- **Cost / quality:** continuous Visualizers and one-shot transitions retain separate internal budget tables because
  their sustainable cost differs, while the current shared 3D Settings surface uses one vocabulary: **Auto / High /
  Balanced / Performance / KAK** plus explicit per-feature disable/override controls. `Auto` resolves before admission,
  never per frame; `KAK` is the minimum-viable base effect with optional expensive facilities off. Each mode may still
  own artistic parameters and explicit overrides. Per-frame Python GL calls remain the primary CPU hazard.
- **Motion blur:** a mode may pass `motion_blur=True` to `scope` and write its screen motion inside
  `velocity_writes()`, evaluating its points at the snapshot's logical t and t - shutter (never real time).
- **Fence:** the Visualizer fence is unchanged (CHK26-protected hot path; modes that do not use a target pay nothing);
  `SceneTarget.scope` itself restores framebuffers, viewport and scissor, including when the scene raises.

## 16B. Neon Lake Basin (Shockwave identity)

[Neon Lake Basin](Neon_Lake_Basin.md) owns the terrain/water authoring, curved wire rendering, growth, sky/sun,
framed-card clipping, internal scene pose and resource contracts. The mode ID and settings prefix remain
`shockwave_grid`; its independent CUSTOM profile remains `3d:shockwave_grid`. It is a normal bordered card whose
3D scene always stays inside the rounded interior. The old overflow setting and flat-grid fit/reach path are retired.

The existing musical source remains authoritative: the mode projects its owned technical and Spectrum frequency
profile onto the shared source implementation. Its bounded onset ring consumes each serial once, spaces admission
by passage intensity, preserves deterministic origins and onset strength, and ages/drops events on the logical
capture clock. Water retains that travelling crest/trough/echo response. Terrain growth uses separate eight-region
attack/release envelopes from the resolved bars; paused Spectrum idle bars never become musical growth. The renderer
consumes immutable events and growth rather than owning another simulation or clock. Current visual acceptance and
cost work remain in the live plan, not the retired flat-grid acceptance description.

## 16A. Extruded Spectrum

The first Visualizer on the shared foundation (`rendering/quick/visualizer/implementations/extruded_spectrum.py`,
GLSL and CPU mirrors in `rendering/gl_programs/extruded_spectrum_program.py`).

- **Authored state:** Extruded Spectrum reuses Spectrum's frame-runtime and one source/shaper implementation, while it
  owns its technical response, bar fill/border/opacity, mirrored layout, nodes, notches, lane strengths, profile floor,
  falloff, ghosts, smoothing and solid-bar stabilization. Before the ownership migration it was a live Spectrum-profile
  borrower: activation resolved Spectrum's currently selected preset. Thus there was no single hidden hard-coded Extruded
  response. On the canonical fresh/default path, Spectrum preset 0 is **Organs**, so the effective pre-migration Extruded
  profile was Organs in full: 35 bars, 128-sample blocks, Dynamic Floor ON / 0.42 baseline, Output Lift ON, AGC 0.34,
  Input Gain 0.98, Recommended Sensitivity OFF / 0.97, Kick Lane Gain 1.70, Transient Pulse 1.0, Clamp 1.85, Kick Lane Mix
  0.90, mirrored layout, the Organs nodes/notches/lane strengths, wave amplitude 0.15, profile floor 0.20, falloff 0.72,
  smoothing 0.50 and ghost 0.59 / decay 0.18. Old inputs missing owned fields still receive a one-time promoted copy of
  their selected Spectrum preset; no runtime setting follows Spectrum afterwards.

  Canonical Extruded defaults and every shipped Extruded curated preset now freeze that complete default-Organs effective
  response into `extruded_spectrum_*` keys while their **3D finish/material settings remain independently authored**. Live orbit remains separate from art presets.
  The one historical presentation exception is fill alpha: old Extruded rendered the borrowed Organs fill opaquely, so the
  owned colour preserves Organs RGB `[12,12,12]` with alpha 255 rather than importing Organs' planar alpha 230. A schema-11
  repair recognizes only the accidentally generated schema-10 Extruded bundle (33 bars / 512 samples plus its matching
  generic response anchors) and replaces only fields still equal to those generated values, including the newly owned kick
  lane mix. User deviations survive. `ExtrudedSpectrumFrame` remains a `SpectrumFrame`; its height transfer equals Spectrum's
  (`extruded_height` mirrors the upload ×0.55, pow 1.15, height scale, 0.95 cap; tested).
- **Presentation-only keys** (`extruded_spectrum_*`): depth, tilt, turn, colouring (Spectral Faces / Spectral
  Edges / Bar Colours), hue drift, gloss, mirror faces, reflection, body alpha, smooth edges, optional shared Scene3D
  shadow and allow overflow. Hue drift advances with logical time only.
- **Edge lines** are drawn by the shader along each face's border. Smooth Edges (on by default) measures them in true
  screen pixels (`fwidth` of the face coordinates): each line keeps its head-on width converted to screen
  pixels along that axis, but never narrower than 1.2 smoothed pixels, so faces seen at an angle keep a ramped line
  instead of one foreshortened below a pixel; head-on (Glass Floor) the lines
  are unchanged. Off, lines are sized as if seen head-on. Smooth Edges also doubles the tier's multisampling
  (High 8x instead of 4x: +0.035 ms GPU at a full 2560x1440 card).
- **3D Detail** (3D Settings tab, its own row under 3D Visualizers; `extruded_quality`): High 4x multisampling,
  Balanced 2x, Performance single-sampled; Mirror Faces on those, off at KAK (the tier's `reflections`).
- **Translucent order** (body, ghost columns, floor reflection): exact for any view without OIT. The bar records reach the
  shader in a painter's order (`extruded_draw_order`: farthest from the orbit's eye along the row first, the eye from
  `scene3d_orbit_eye`; the boxes occupy disjoint x slabs, so that order is exact and two bars on opposite sides of the
  eye never cover each other), each carrying its bar index; the translucent passes drop faces turned from the eye, so
  a box never blends over itself (winding-independent, so the mirrored reflection is right too). Each box now blends
  once. Ghost/reflection alpha retains the opacity its front and back faces used to add up to, a(2 - a), clamped first
  (the reflection's authored alpha exceeds 1 above the floor line). Body alpha remains its directly authored opacity.
- **Material alpha:** fill RGBA controls face coverage; the border alpha independently retains edge coverage. Body Alpha
  multiplies that combined surface alpha. Spectral Edges supplies its own opaque spectral edge colour; Bar Colours uses
  the authored edge RGBA. Fully opaque bodies use depth writes; translucent bodies use the same ordered visible-face path
  without depth writes. Ghost and floor-reflection opacity remain independent authored axes.
- **Shadow:** the optional Scene3D directional pass projects the **full cuboid silhouette** onto the floor using the
  canonical shadow direction/style and mode-owned strength. Every box vertex is projected by height, so vertical faces fill
  the sweep between the base footprint and shifted top footprint; the previous top-cap-only translation could sit under the
  bar/reflection and read as no cast shadow. Overlapping projected faces use a single-alpha union rather than stacking darkness.
  It uses the shared pass/state fence; disabled or transparent shadows draw no pass. The ceiling-height sweep participates in
  render-target reach, so it cannot be clipped by the body-only bounds.
- **Mirror Faces** (0 by default) gives the faces, never the edge lines, a polished mirror surface reflecting
  the wallpaper; procedural brushed/hash grain is intentionally absent because it produced visible vertical ribbing across
  bright reflected faces. An invented studio environment reads as washout/sheen and is not the product contract. The displayed photograph is
  downsampled once per image change (`widgets/spotify_visualizer/backdrop.py`, 512 on the longer side, ~1.3 ms on
  the GUI thread at 4K) by the Visualizer's owner, only while the mode reflects (the descriptor's
  `backdrop_setting` above zero on a tier with reflections; the scene tells the owner when the photograph changes),
  carried in the mode's parameters (`backdrop`, immutable bytes) and uploaded once into the renderer's own
  mipmapped texture (`BackdropEnvironment`); a face shows it where the pixel sits, displaced by the reflected ray
  toward a near virtual eye (so it varies across the row and slides as the view turns), sharper with Gloss. It
  replaced reading back the target being drawn every 6th frame (a ~0.55 ms GPU stall each): at a full 2560x1440 card
  GPU median (p90) is now 0.097 (0.098) ms with Mirror Faces on, against 0.10 (0.60) before. No GL texture is
  shared with the background, so PR-04's lend/reclaim lifetime is untouched; widgets beneath are no longer
  reflected, only the wallpaper. The reflection never switches in one frame: a new wallpaper
  goes into a second slot and crossfades from the old one, and the first one fades in from no reflection (Voxel
  Sphere's Mirror Cubes share this). A wallpaper a transition brings in changes with the transition: the runtime
  announces the destination photograph and duration at the transition's start (`scene_controller.incoming_image`),
  the owner makes its copy then (~1-1.5 ms on the GUI thread at 1440p-4K, only while a mode reflects) and the
  reflection crossfades over the transition's duration, so it has finished when the scene adopts the photograph;
  otherwise over `BackdropEnvironment.BLEND_S` (2 s) of logical time. With Mirror Faces at 0,
  or no reflections, nothing is made or held. Preset 4 (Chrome Organ) pairs it with Spectral Edges and the floor
  reflection.
- **Rendering:** one instanced box draw per admitted pass from per-bar std430 records (level, peak) on the stream ring at
  binding 3, into a tier-resolved multisampled `SceneTarget` laid over the card in overlay mode. Passes: optional directional
  shadow, opaque or translucent bars, floor reflection (fades to zero at the field bottom), and ghost columns for the peaks.
  S17 material lighting.
- **Fit:** `extruded_fit` frames the projected bounding box of the tallest possible field for the current tilt, turn,
  depth and reflection, so no setting can push the scene out of the rectangle; with overflow on (default), the scene
  keeps its front-on scale and is not contained to its frame: the target covers everything the bars can draw for the
  view (`extruded_reach`, every bar at the ceiling plus its reflection), grown in `REACH_STEP` steps and clamped to
  the window (`reach_item_frame`). This overflow policy belongs to Extruded Spectrum; framed Neon Lake Basin
  always clips its internal scene instead. Stacking: the Visualizer layer is
  above every widget and below only the OSD, Edit chrome and the context menu (`DisplayScene.qml`).
- **CUSTOM quarter-turn** is not offered (Turn orbits the field instead).
- **Live view pose:** Sphere, Extruded Spectrum and Neon Lake Basin declare turn/tilt through
  `view_orbit_settings`. W/A/S/D holds one immutable `ViewOrbitMotion`; the logical capture evaluates it at its own
  timestamp, independent of OS key repeat. Alt+left-drag uses the same orbit owner. The GUI owner settles the reached
  view once through canonical Settings when the gesture finishes or the owner retires; ordinary frames write nothing.
  These are mode-specific live view settings, excluded from curated artwork and Custom art snapshots. Ordinary art
  hydration cannot reset the view or switch an orbit edit to Custom. The mode's independent CUSTOM `layout_profile` remains
  stage geometry, with no camera authority.
- **Framed camera policy is declared, never keyed on a mode id (FC, 2026-10-18):** descriptor fields
  `view_orbit_turn_wraps` (False clamps turn: Neon Lake's landscape), `view_orbit_inertia` (a released drag coasts:
  Sphere), `scene_pan_envelope` (anchor x/y, upper reference y, left/right margins bounding pan at each zoom: Neon Lake;
  identical to its former bounds over a dense scale/pan grid) and `view_auto_rotate_settings` (Auto Rotate After
  seconds, Speed degrees/s). Orbit is rotation of the view (turn/tilt); pan and zoom are the separate scene transform.
  **Auto Rotate** swivels turn only, round a full circle (wrapping modes only), after that long without camera input;
  a completed startup or mode/preset swap (the orbit-admission edge) starts it at once, so a preset's starting view
  is where it begins. The GUI thread publishes one immutable `AutoRotate` record (armed at that edge and when
  orbiting stops, dropped by any camera input, which first settles the swivelled turn so the view never snaps); the
  logical capture evaluates it at its frame time. No timer, polling or per-frame write; the swivel is never
  persisted. Tests: `test_visualizer_view_orbit.py` (swivel, wait, input takeover, off/clamped/undeclared).
- **Reusable framed 3D camera contract (planned consolidation):** Neon Lake's working internal-camera
  input and canonical presentation pose are the reference for **all future bordered 3D Visualizers**, including
  Extruded Bubble, Cubes, Aurora, Ember Swarm and Waveform Ribbon. Promote its capability into the existing
  descriptor/view-orbit/scene-transform owners under §4A FC *before* building another mode; do not duplicate
  the renderer's bounds/pan logic or add a second camera store. A framed mode supplies a declared pivot, fit,
  safe turn/tilt limits, bounded internal pan/zoom and valid near-plane/content coverage for its own material.
  Persisted live view state remains presentation-only and mode-specific, excluded from artwork/CUSTOM layout geometry.
  Use card-interior clipping and the existing gesture/input ownership. Explicit capability gating protects
  unframed Sphere and Extruded Spectrum's original free-orbit policy. Prove Neon Lake parity, both displays,
  minimum/maximum card size, aspect/DPR, dormant-zero-cost and resize legibility before reusing the capability.
  `Docs/Reference/Scene3D_Resources.md` defines the required depth/transparency/shadow prerequisites for
  a framed transparent 3D consumer; `Current_Plan.md` owns their implementation order.
- **Framed scene exception:** Neon Lake Basin additionally declares `scene_transform_settings` for scene scale and
  pan X/Y. Its complete five-key view pose persists independently of art and layout Save/Cancel. WASD and Alt+left
  orbit inside the card; Alt+right pans inside it; Alt+wheel scales about the interior centre, using either Qt wheel
  axis. They never move/resize the card or alter its viewport, in ordinary interaction or Edit. See
  [Neon Lake Basin](Neon_Lake_Basin.md) for admission, persistence and clipping.
- **Gated modes:** `_GATED_MODES` in `visualizer_mode_registry.py` holds registered modes that are not yet offered
  (empty since Extruded Bubble opened, 2026-10-18): they own defaults, a spec, presets, a runtime and a renderer, but are never
  selectable, cycled, offered in Guided Setup or listed in the 3D tab, and get no runtime work. The gate opens in code,
  never through an environment flag; tests open it for themselves with `monkeypatch` when they exercise the body.
- **Framed preset starting views:** optional top-level `starting_view` JSON metadata contains exactly the mode's
  descriptor-declared pose keys. `core/settings/visualizer_view_orbit.py` validates complete finite numeric values
  against the same typed controls; malformed, foreign, missing or out-of-range leaves reject the record loudly.
  The existing live-view owner applies a starting pose once on a changed Settings preset selection or runtime cycle.
  Missing optional metadata means canonical mode defaults on that selection. A raw activation with no live pose
  also seeds it; complete Settings hydration, restart, mode reentry and ordinary saves preserve the current pose.
  Custom artwork retains the live view and never caches a separate camera. Save Preset As offers **Include current
  camera view when saving**, checked initially for framed modes only, and exports the settled Settings pose outside
  the artwork snapshot. Ordinary orbit gestures never rewrite a preset. Explicit override and repair/reindex tooling
  preserve valid starting metadata. Existing preset files need no automatic rewrite, and old camera leaves embedded
  in artwork remain inert. There is no preset-camera cache, timer, renderer lookup or additional layout authority.
- **Whole-stage gestures:** for unframed 3D modes, Alt+right and Alt+wheel retain the existing direct CUSTOM
  move/resize transaction outside Edit. Press-time move origins rebase to the current rectangle after scaling; wheel
  scaling preserves the stage centre subject to display-edge clamping. One completed gesture commits through the
  existing Save boundary. During Edit, those whole-stage operations use the active `CustomLayoutSession`, without
  opening a second direct session. Orbit still settles through its separate view-settings owner. Native product-input
  blocking remains binding; descriptor admission routes only the selected mode's supported gestures. Without Alt,
  outside the admitted Visualizer, or outside interaction/Ctrl/Edit admission, pointer behavior is unchanged.

- **Cost** at a card filling a 2560x1440 display (the worst case; RTX 4090), median (p90): about 0.7 (0.8) ms CPU
  submit and 0.09 (0.10) ms GPU per frame; Mirror Faces 0.10 (0.62) ms GPU, the p90 being every sixth frame's
  backdrop copy.
- **Regression reference (accepted, not an open gate):** each preset with live music on both displays (Visualizer freshness alongside 3D
  transitions); edge lines at strong tilt/turn with Smooth Edges on and off; Mirror Faces' horizon and softboxes
  while orbiting; W/A/S/D feel (step size, held-key pace), the view surviving a restart independently of art presets;
  Extruded Allow Overflow near screen edges.
- **Guided Setup preview:** rendered by the foundry through the production capture and renderer
  (`_RENDERED_VISUALIZER_PREVIEWS`); legacy screenshot sheets are not catalog authority.

## 16C. Oscilloscope

**Operator accepted and fully validated, 2026-10-12.** Reopen only for a concrete regression or a newly changed feature.

Rebuilt from scratch on 2026-10-11 (operator: the old mode had very bad Settings UX and unreliable, disappointing
output). An analog scope's phosphor beam drawing the music itself. Settings: its spec in
`core/settings/visualizer_mode_settings.py`; trace math and reaction rules with GLSL in
`rendering/gl_programs/oscilloscope_program.py`; state in `widgets/spotify_visualizer/oscilloscope_frame_runtime.py`;
renderer `rendering/quick/visualizer/implementations/oscilloscope.py`.

- **Audio:** while Oscilloscope is the mode (and only then: `set_waveform_history_demand`, declared per tick from
  `mode_capabilities.consumes_waveform_samples`), the capture callback keeps a contiguous history of the newest 4096
  samples across callbacks, taken from each whole block before analysis trims it, with the device's actual rate
  (`get_waveform_history` / `get_waveform_history_rate`). Spans and delays convert at that rate. Paused, the engine's
  idle waveform is drawn; replay serves a recording's full capture history (`tools/music_recorder.py` clips).
- **Picture:** Trace (a triggered sweep: a rising zero crossing of the smoothed signal chosen among the recent ones
  as the one that best continues the previous trace, so a steady tone stands still; spans longer than the trace's 384
  points draw each bin's low and high in time order, never an aliased subsample; the sweep runs past both item
  edges along its axis, so the card's inner clip cuts it under the border rather than it stopping short, while the
  graticule keeps the screen's margin), Ring (the trace clockwise around a
  circle, ends eased to the circle) or Phase (the signal against itself Phase Delay later, turned 45 degrees, its
  narrow axis widened toward the other's spread: shape only). Detail low-passes the drawn audio (about 1.5 kHz at 0,
  every sample at 1); Gain scales the DC-free signal on a fixed scale with a tanh soft limit (nothing learned from
  the track).
- **Afterglow:** earlier traces (one per 1/45 s, at most 15) kept by the frame runtime and fading on the logical
  clock; the renderer keeps no history and no clock. A display change clears them.
- **Reactions** (the shared musical rule, `transient_bus`): the beam's drive is `musical_weight` x `passage_ramp`
  (quietest passage 0.3), eased up in 0.08 s and down in 0.7 s; each musical onset, taken once by serial, flares the
  beam (`flare_strength`: weight x emphasis on the fixed loudness scale x hit size x the passage's share), decaying
  over 0.3 s; the tone is the pre-AGC analysis spectrum's centroid, eased (Spectral Colour tints the beam warm for bass,
  cool for treble). Hit Flare scales the flare's thickening and light; Loudness Glow how much the drive brightens.
- **Rendering:** every trace's points (float32, back to back) go to one std430 array on a stream ring (binding 3) and
  one instanced draw: each segment a quad whose fragment measures its distance to the segment (anti-aliased at any
  width, with a white-hot centre), dimmer where the beam moves fast with Analog Beam up (a CRT's writing speed), faded
  near the centre in Phase. Segments and traces combine by their maximum in a single-sample overlay `SceneTarget`
  (joints never bead, the picture is bit-repeatable), with the optional graticule (Grid 10 x 8 with ticks, or
  Crosshair) drawn first. The beam's light goes to the emission attachment and the target's bloom adds the glow;
  Glow 0 allocates no emission attachment or bloom; the light combines by its maximum too, so overlaps and afterglow
  never stack glow. `prepare_step` compiles, allocates the ring and the target on hidden frames before the reveal
  (`prepared_reveal`). CUSTOM quarter turns: everything is laid out in the rotated content (the logical content rect)
  and only each vertex turns into the item's physical space, a rigid quarter turn, so widths and anti-aliasing stay
  exact.
- **Owned analysis controls:** Voxel Sphere's subset (bar count, block size, sensitivity, floors, input gain,
  transient clamp), since the onsets and loudness it reacts to come from that analysis. It owns no Rainbow or shared bar
  colours. Every pre-rework key is retired (`core/settings/visualizer_retired_modes.py`).
- **Curated presets:** Phosphor (green Trace on a grid), Neon Halo (Ring, spectral tint), Lissajous (Phase, gold, long
  afterglow), Amber Terminal (dense amber Trace, analog beam). Authored content: never test fixtures.
- **Regression reference (accepted, not an open gate):** the look and the presets on real music on both displays (card and wallpaper behind it),
  trigger steadiness on sustained notes, afterglow pace, flare and loudness-glow feel through quiet and loud passages,
  Settings body UX, and cost against the other modes (`tools/overhead_baseline.py --match oscilloscope`).
