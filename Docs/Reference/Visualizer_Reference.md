# Visualizer Reference

Current visualizer behavior and accepted presentation architecture.

## 1. Modes

Visualizer uses its own logical production and viewport/scale geometry; the ordinary-widget retained-child semantic Edit role and normalization contracts do not apply to its paint or cadence. A widget Edit performance fix must not introduce a second Visualizer scheduler, alter Bubble temporal fidelity, or substitute a QML child-role rectangle for the renderer-owned viewport.

Canonical current mode ids remain owned by the settings/mode registry:

- `spectrum`
- `oscilloscope`
- `sine_wave`
- `bubble`
- `devcurve`
- `sphere` — experimental, FRAMELESS, dormant by default
- `extruded_spectrum` — FRAMELESS, dormant by default; Spectrum's bars as lit 3D columns
- `shockwave_grid` — FRAMELESS, dormant by default; a neon grid floor rippled by onset shockwaves

The first five are the established carded technical modes. Extruded Spectrum (section 16A) is a permanent mode that
borrows Spectrum's frame runtime, technical profile and bar colours and owns only its 3D presentation (Shockwave Grid,
16B, likewise). A borrower sees the lender as the lender shows itself: the activation payload resolves each lender
(`get_profile_lender_modes`) through the lender's own active preset after the borrower's, so Extruded Spectrum reacts
exactly as Spectrum's selected preset does; before 2026-10-03 it read the raw stored `spectrum_*` keys or Spectrum's
factory defaults and could sit pinned at full height. Sphere is a registered experimental mode with separate frameless presentation policy and, **before S19**, no user-facing technical-controls profile; it temporarily resolves a hidden Spectrum-backed technical state that S19 will replace deliberately after golden capture. The mode registry may also own cheap presentation/capability metadata. Do not put renderer objects or heavy implementation imports into it.

## 1A. Registered modes vs enabled modes

Per-mode admission/dormancy is implemented. `core/settings/visualizer_mode_registry.py` owns all registered descriptors and lazy wiring; persisted `enabled_modes` owns user mode admission; the top-level Visualizers Settings tab builds mode bodies lazily and keeps disabled/unselected bodies dormant. The ownership distinction is:

```text
all registered canonical modes
    -> schema/default/migration/persisted settings authority

currently enabled modes
    -> Settings mode pills, selection/cycling, frame-runtime construction, renderer import/construction
```

Disabled modes retain their configuration without contributing meaningful runtime work. If the Visualizer family is enabled, at least one mode remains enabled, but any registered mode may be the sole enabled mode when explicitly admitted. The default enabled-mode set intentionally excludes experimental Sphere, so Sphere remains dormant until the user enables it. Admission must remain behaviorally transparent to cadence, source freshness, presets, renderer transfer, scale/extent and Bubble/BTF.

### 1B. Experimental mode policy after the shared Scene3D foundation

Sphere is the legacy migration case, **not** the template for building another private renderer stack. A new experimental
mode created after shared Scene3D exists joins the canonical registry, logical snapshot/cadence contract, shared
Scene3D/compute/resource/material/quality substrate, lifecycle and dormancy owners immediately. "Experimental" means
default-off/not-yet-product-accepted and permits private reaction semantics and mode-owned settings; it does not mean
private scheduling/presentation authority or a disposable GPU engine. Promotion to stable should normally change
admission/status/defaults and close acceptance gates, not require reimplementing the mode on a second substrate.

## 2. Capability model

| Mode | Idle reveal | Idle self-animation | Presentation-owned idle scene | Fresh current source required for **live audio reactivity** |
|---|---:|---:|---:|---:|
| Bubble | yes | yes | no | yes |
| Spectrum | yes | no | yes | yes |
| Sine | yes | yes | no | yes |
| Oscilloscope | yes | yes | no | yes |
| DevCurve | yes | yes | no | yes |
| Sphere (experimental) | yes | yes | no | yes |
| Extruded Spectrum | yes | no | yes | yes |
| Shockwave Grid | yes | no | yes | yes |

Paused Spectrum remains intentionally mixed:

```text
presentation_ready = true
reactive_source_ready = false
source identity = absent
```

While paused, the shared BeatEngine synthesizes idle waveform *samples* only when the logical step declares Oscilloscope as the active mode (`set_idle_waveform_demand`, set before every tick); every paused tick still advances the waveform generation that Sine/Oscilloscope readiness keys on, and idle bars/energy still animate for every mode.

Idle reveal/self-animation and live audio reactivity are separate contracts. A mode may remain visibly alive while paused or while awaiting a fresh source, but real music must not be treated as current reactive input until generation/activation identity is authoritative. Healthy authored cadence or idle motion therefore does not prove live-source reactivity.

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

The five established technical modes remain:

```text
CARD + CARD_INTERIOR
```

Experimental Sphere is currently:

```text
FRAMELESS + VIEWPORT_RECT
```

Future modes must declare one of these policies explicitly.

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

### Current carded modes

Preserve visual fidelity:

- background;
- border/radius;
- card shadow;
- opacity;
- customization;
- alignment;
- fade.

Stable shell pixels must not be expensively rebuilt every visualizer frame.

### Frameless modes

Architecture permits a mode to omit:

- background;
- border/frame;
- card shadow.

Sphere and Extruded Spectrum are the current examples: free-standing 3D objects using FRAMELESS + VIEWPORT_RECT while remaining inside the same retained Quick scene/lifecycle. With Allow Overflow on, Extruded Spectrum's node is unbounded and its scene may extend past the viewport rectangle; there is still no card to draw.

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

The five established carded modes share one canonical baseline viewport aspect ratio. A mode switch or
preset load does not change viewport/card shape.

That canonical baseline aspect is **1.5**. It is the sensible DEFAULT shape for ordinary non-CUSTOM
layout, not a universal invariant. Distinguish three concepts:

- **default/baseline aspect (1.5)** — the default card shape shared by the five established carded modes;
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

All six registered modes are viewport-resize-capable through their declared presentation policy; the five established carded modes share the card geometry contract, while Sphere uses its frameless viewport policy. The core Bubble capability/reflow path is landed. Do not reintroduce a Bubble false gate to conceal an implementation defect. Committed viewport truth remains separate from temporary CUSTOM working geometry; any newly reproduced spatial defect must preserve authored Bubble response and the binding BTF contract rather than reviving phase-specific gates.

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

## 14. CUSTOM / Edit

CUSTOM/Edit preserves one authoritative committed geometry.

Control UI may remain QWidget if appropriate.

Live runtime pixels belong to the Quick scene; edit plumbing must not recreate a
second accelerated presentation surface.

Required visualizer resize semantics:

```text
scroll wheel   -> uniform visual scale
corner handles -> uniform visual scale
left/right     -> viewport width
top/bottom     -> viewport height
```

Viewport resizing is part of the current CUSTOM contract, not optional QoL and not permission to stretch a
rendered image. Save/Cancel and layout slots preserve scale and extent separately.

The five established carded modes also admit the shared CUSTOM **content quarter-turn** control. Orientation is layout/presentation state, not a Visualizer setting or preset value: a sparse `content_rotation_quarters_by_mode` map lives inside the existing CUSTOM `size_payload`, keyed by canonical mode ID, with missing/zero meaning 0°. A legacy global `content_rotation_quarters` scalar is interpretation-only compatibility input; new writes use the per-mode map. Odd quarter-turns swap the effective logical viewport axes before authored mode presentation and the shared render contract maps that logical world back into the unchanged physical card. This preserves stored X/Y/extent/uniform scale and avoids stretching finished pixels. Save/Cancel, layout slots, display transfer and Restore semantics remain in the existing CUSTOM owner. Rotation is event-driven and adds no timer, poller, alternate Visualizer cadence or per-frame Settings lookup. Voxel Sphere remains excluded through descriptor capability metadata so this feature cannot couple the isolated frameless 3-D mode back into the carded-mode contract.

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

A mode may build on the shared 3D foundation the transitions use. No Visualizer has completed adoption yet; Voxel
Sphere is the active promotion target and remains behaviourally private until its S19 golden passes. Plan and hazards:
`Current_Plan.md`. The binding lessons in
`Docs/Reference/Transitions.md` ("3D foundation lessons") apply to modes as well.

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
  their sustainable cost differs, but the eventual user-facing 3D Settings surface uses one vocabulary: **Auto / High /
  Balanced / Performance / KAK** plus explicit per-feature disable/override controls. `Auto` resolves before admission,
  never per frame; `KAK` is the minimum-viable base effect with optional expensive facilities off. Each mode may still
  own artistic parameters and explicit overrides. Per-frame Python GL calls remain the primary CPU hazard.
- **Motion blur:** a mode may pass `motion_blur=True` to `scope` and write its screen motion inside
  `velocity_writes()`, evaluating its points at the snapshot's logical t and t - shutter (never real time).
- **Fence:** the Visualizer fence is unchanged (CHK26-protected hot path; modes that do not use a target pay nothing);
  `SceneTarget.scope` itself restores framebuffers, viewport and scissor, including when the scene raises.

## 16B. Shockwave Grid

A neon grid floor in perspective (`rendering/quick/visualizer/implementations/shockwave_grid.py`, GLSL and CPU
mirrors in `rendering/gl_programs/shockwave_grid_program.py`), the first Visualizer with its own authored events.

- **Authored state:** Spectrum's frame runtime, technical profile and bar colours, extended by
  `ShockwaveGridFrameRuntime` (`widgets/spotify_visualizer/shockwave_frame_runtime.py`) with a bounded event ring:
  each musical onset the transient bus publishes (at least 0.09 s after the last, only while playing) becomes one
  event, born when the onset happened, with a deterministic origin (from its admission number; kicks nearer the
  front middle) and the onset's strength. Onsets are taken exactly once by serial (see "Musical onsets" below). Events are aged on the logical clock at capture, dropped after 3.2 s, at most 16 held.
  `ShockwaveGridFrame.events` carries them aged, so the renderer has no clock or history of its own. Live events (or
  Scroll) keep Spectrum's animation clock running, so frames publish while waves move.
- **Picture:** one draw of the shared triangle grid (180x120 cells) displaced in the vertex shader: each event a
  circular crest with a shallow trough behind, travelling at Wave Speed and fading over 1.1 s; Spectrum's bars raise a
  ridge along the far edge (Horizon). Lines are analytic in the fragment shader (anti-aliased by their on-screen
  width), turning toward the crest colour on crests and the ridge, over a dark translucent floor (Floor). The grid
  fades out at its far edge and sides.
- **Reactivity** (operator 2026-10-03: too lively at near-silence, big hits drowned among medium ones, wanted idle
  motion and brighter glow where it is loudest). A wave's strength is `shockwave_strength` of the onset's magnitude,
  loudness and presence (`MusicalOnset`): no wave below an absolute loudness (`SHOCKWAVE_QUIET`) or when quiet
  against the running level (`SHOCKWAVE_PRESENCE`: a near-silent passage of a loud track), and the onset's presence
  against the track's usual onset presence (followed by the frame runtime from a neutral 1.0) sets how much it stands
  out: a hit 1.6x the usual reaches about 2.9x a medium one, capped at 2. Strengths under 0.12 make no wave. Above 1 a
  wave grows taller more slowly, widens, brightens and trails an echo ring at 0.62 of its speed, so the biggest
  moments look different, not just larger. The crest light follows the strength, and the horizon ridge is up to 40%
  brighter where Spectrum's bars are loudest. **Idle Swell** (Waves bucket, 0.35 by default) sweeps a soft ridge
  smoothly from side to side over 11 s, so the grid moves between beats (it keeps the animation clock running).
  Bars: `tests/test_qtquick_shockwave_grid.py`.
- **Glow** uses the overlay bloom of `SceneTarget` (`Docs/Reference/Scene3D_Resources.md`): the lines emit their
  light into the emission attachment and the glow is added over the wallpaper. Glow 0 allocates no emission
  attachment or bloom chain.
- **View:** turn a full circle and tilt from level to straight down about the grid's centre, from a camera beyond the
  grid's reach (`shockwave_camera`); `shockwave_fit` frames the visible grid and the highest ridge between 10% and 96%
  of the field for every view. W/A/S/D and Alt + drag orbit it (`view_orbit_settings`), Allow Overflow lets it pass the
  rectangle. CUSTOM quarter-turn is not offered.
- **Guided Setup preview:** rendered by the foundry with three fixture onsets fed through a minimal transient-bus
  stand-in (`_PREVIEW_ONSETS`).
- **Cost** at a card filling a 2560x1440 display (RTX 4090), median: 0.6 ms CPU submit and 0.07 ms GPU without glow;
  1.0 ms and 0.16 ms with glow (the bloom passes), 3 or 16 live waves alike.
- **3D Detail** (3D Settings tab, its own row under 3D Visualizers; `shockwave_quality`): High 4x multisampling,
  Glow, a 180x120 grid; Balanced 2x, Glow, 128x85; Performance single-sampled, no Glow, 64x43; KAK the same at 48x32
  (`shockwave_grid_cells`). Measured as above with Glow 0.8: GPU median 0.17 / 0.13 / 0.04 / 0.04 ms, CPU 1.0 / 1.2 /
  0.65 / 0.67 ms (the bloom chain's calls go with the Glow).
- **Physical checks (open):** the reactivity on real music: calm at near-silence and between songs, ordinary beats
  against big drops, the idle swell's pace; wave timing (kicks vs. snares, busy tracks hitting the 16-event cap),
  the presets on both displays, glow strength, the horizon ridge, orbiting, and Allow Overflow near screen edges.

## 16A. Extruded Spectrum

The first Visualizer on the shared foundation (`rendering/quick/visualizer/implementations/extruded_spectrum.py`,
GLSL and CPU mirrors in `rendering/gl_programs/extruded_spectrum_program.py`).

- **Authored state:** Spectrum's. The descriptor names Spectrum's frame runtime, technical profile and shared-bar
  profile, so bars, peaks, the R-76 temporal treatment, the shape editor and energy distribution are Spectrum's own.
  `ExtrudedSpectrumFrame` is a `SpectrumFrame` with the mode's presentation parameters; the height transfer equals
  Spectrum's (`extruded_height` mirrors the upload ×0.55, pow 1.15, height scale, 0.95 cap; tested).
- **Presentation-only keys** (`extruded_spectrum_*`): depth, tilt, turn, colouring (Spectral Faces / Spectral
  Edges / Bar Colours), hue drift, gloss, mirror faces, reflection, smooth edges, allow overflow. Hue drift advances
  with logical time only.
- **Edge lines** are drawn by the shader along each face's border. Smooth Edges (on by default) measures them in true
  screen pixels (`fwidth` of the face coordinates): each line keeps its head-on width converted to screen
  pixels along that axis, but never narrower than 1.2 smoothed pixels, so faces seen at an angle keep a ramped line
  instead of one foreshortened below a pixel (the jagged edges reported 2026-10-03); head-on (Glass Floor) the lines
  are unchanged. Off, lines are sized as if seen head-on. Smooth Edges also doubles the tier's multisampling
  (High 8x instead of 4x: +0.035 ms GPU at a full 2560x1440 card).
- **3D Detail** (3D Settings tab, its own row under 3D Visualizers; `extruded_quality`): High 4x multisampling and
  the wallpaper copy for Mirror Faces every 6 frames, Balanced 2x and every 12, Performance single-sampled and every
  24, KAK single-sampled with Mirror Faces off. Measured at a full 2560x1440 card (Smooth Edges and Mirror Faces on,
  RTX 4090), GPU median (p90) High 0.10 (0.60) ms -> Balanced 0.07 (0.30) -> Performance 0.06 (0.06) -> KAK 0.05
  (0.05): the p90 is the copy's stall, rarer down the tiers. CPU stays ~0.7 ms (H7 targets it).
- **Mirror Faces** (0 by default) gives the faces, never the edge lines, a faintly brushed mirror surface reflecting
  the wallpaper (operator 2026-10-03: a made-up studio read as washout and sheen). What Quick drew under the
  Visualizer (wallpaper, and widgets beneath it) is copied from the render target into a small mipmapped texture
  (`BackdropEnvironment`, 512 on the longer side); a face shows it where the pixel sits, displaced by the reflected
  ray toward a near virtual eye (so it varies across the row and slides as the view turns), sharper with Gloss.
  Reading the target being drawn costs a fixed GPU stall (~0.55 ms at any region size, RTX 4090), so the copy is
  refreshed every 6 rendered frames and reused between (reflections may trail the wallpaper by a few frames; about
  0.1 ms per frame on average). With Mirror Faces at 0 nothing is copied or held. The Visualizer is lent no
  presentation texture: borrowing the background node's would couple its PR-04 lend/reclaim lifetime to a second
  node and still not match fit/crop or widgets. Preset 4 (Chrome Organ) pairs it with Spectral Edges and the floor
  reflection.
- **Rendering:** one instanced box draw per pass from per-bar std430 records (level, peak) on the stream ring at
  binding 3, into a 4× multisampled `SceneTarget` laid over the card in overlay mode. Passes: opaque bars, the floor
  reflection (fades to zero at the field bottom), translucent ghost columns for the peaks. S17 material lighting.
- **Fit:** `extruded_fit` frames the projected bounding box of the tallest possible field for the current tilt, turn,
  depth and reflection, so no setting can push the scene out of the rectangle; with overflow on, the scene keeps its
  front-on scale and the target grows by `EXTRUDED_OVERFLOW_PAD` of the item height.
- **CUSTOM quarter-turn** is not offered (Turn orbits the field instead).
- **Live view orbit (W/A/S/D):** a 3D freeform mode names its (turn, tilt) settings in the descriptor's
  `view_orbit_settings` and one step of each in `view_orbit_steps` (2 degrees). DisplayManager publishes "a 3D view is
  shown" to every display's input owner on owner creation/retirement and mode completion (an event fact, no provider
  read per key). While it is shown, W/S tilt the camera up/down and A/D move it left/right at a steady 30 steps a
  second (60 degrees) while held, several keys at once. The rate runs on the logical clock, never on OS key repeat
  (which stops repeating an older key once another is pressed: the "stuck" orbit of 2026-10-03): the input owner
  publishes the held keys' combined direction when it changes, the GUI thread replaces one immutable
  `ViewOrbitMotion` (view at a moment + rates) on the presentation state, and the logical capture evaluates it at its
  own frame time (`widgets/spotify_visualizer/view_orbit.py`). The GUI thread is the only writer; release settles the
  reached view into the settings (freeze, write, drop, so no capture sees a half update). Turn goes a full circle and
  wraps (-1..1 is -180..180 degrees); tilt runs from level to straight down (0..1 is 0..90 degrees) about the bars'
  mid-height. Nothing is saved while orbiting: the result is written once, through the atomic runtime-preset
  persistence, when no key is held and no drag is on, when the Visualizer retires mid-orbit, or never if a preset
  replaced the view (held keys then carry on from the preset's view). On a curated preset the edit moves the mode to
  Custom holding what was shown (`core/settings/visualizer_view_orbit.py`), as a Settings edit would. With no 3D view
  shown W/A/S/D exit like any other key. The S key no longer opens Settings (the context menu does).
- **Alt + left drag** on the shown Visualizer in interaction (or Ctrl) mode orbits it too: a step per 4 pixels, the
  scene turning toward the drag and the camera rising as you drag down. The display runtime lends its own input
  owner the scene's `visualizer_contains_scene_position` hit test; the input owner drops it (with any held keys or
  drag) when its admission closes. While a drag is on, pointer motion is routed to the input owner even in
  interaction mode. A drag's steps are fractions per mouse move, so every relay of `view_orbit_requested` carries
  floats (an int relay once truncated them all to zero; `tests/test_visualizer_view_orbit.py` drives the real window
  and runtime). Without Alt, off the Visualizer or outside interaction/Ctrl mode, pointer behaviour is unchanged.
- **Alt + right drag / Alt + wheel** (the same admission: a shown 3D Visualizer under the pointer, interaction or Ctrl
  mode) move and resize it outside Edit. The input owner takes Alt + right before the context menu and Alt + wheel
  before the Visualizer's volume wheel (`QuickDisplayWindow.wheelEvent`; Qt may report the wheel as horizontal with
  Alt held); every other press or wheel is untouched. A gesture runs through Edit's own session machinery in
  `QuickCustomLayoutOwner` (`begin_direct_visualizer_gesture`): a session holding only the Visualizer, its display
  bound chrome-less (`bind_direct_custom_layout_session`: no overlay model or guides, native and widget input not
  blocked), authored placement quiesced as Edit does. The move follows the pointer exactly, clamped to its display
  (no invisible magnetic snap, no display transfer); the wheel is Edit's uniform resize. It ends at the drag's release,
  or when Alt is released after wheeling (one gesture, finished once, whichever ends last), and commits through
  Edit's `save` once: the same persistence and live promotion, nothing written when nothing changed, and no Edit-close
  input guard. Edit never inherits one (starting Edit commits it first; Edit's keys follow `is_editing`, not a
  gesture); teardown, Settings and layout slots treat it as an open session (`is_active`). Nothing is held between
  gestures. Bars: `tests/test_visualizer_direct_gestures.py` (the input owner, and the real display unit + Visualizer
  + owner seam).
- **Cost** at a card filling a 2560x1440 display (the worst case; RTX 4090), median (p90): about 0.7 (0.8) ms CPU
  submit and 0.09 (0.10) ms GPU per frame; Mirror Faces 0.10 (0.62) ms GPU, the p90 being every sixth frame's
  backdrop copy.
- **Physical checks (open):** each preset with live music on both displays (Visualizer freshness alongside 3D
  transitions); edge lines at strong tilt/turn with Smooth Edges on and off; Mirror Faces' horizon and softboxes
  while orbiting; W/A/S/D feel (step size, key-repeat pace), the view surviving a restart, and a curated preset
  becoming Custom after an orbit; Allow Overflow near screen edges.
- **Guided Setup preview:** rendered by the foundry through the production capture and renderer
  (`_RENDERED_VISUALIZER_PREVIEWS`), since the operator's screenshot sheet predates the mode.

