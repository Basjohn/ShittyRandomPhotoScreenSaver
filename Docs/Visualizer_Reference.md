# Visualizer Reference

Last updated: 2026-09-02

Current visualizer behavior and accepted presentation destination.

## 1. Modes

Canonical current mode ids remain owned by the settings/mode registry:

- `spectrum`
- `oscilloscope`
- `sine_wave`
- `bubble`
- `devcurve`

The mode registry may also own cheap presentation policy metadata. Do not put renderer objects or
heavy implementation imports into it.

## 1A. Registered modes vs enabled modes — planned modularization boundary

Current source already has a canonical descriptor registry and some active-descriptor consumers, but per-mode product enable/disable is **not yet a complete production contract**. The planned modularization is decomposed in `Docs/QtQuick_Migration/Visualizer_Mode_Modularization_And_Settings_Tab_Decomposition_2026-09-02.md`.

The destination distinction is:

```text
all registered canonical modes
    -> schema/default/migration/persisted settings authority

currently enabled modes
    -> Settings mode pills, selection/cycling, frame-runtime construction, renderer import/construction
```

Disabled modes must retain their configuration without contributing meaningful runtime work. If the Visualizer family is enabled, at least one mode remains enabled, but any current mode may be the sole enabled mode. This future admission layer must be behaviorally transparent to cadence, source freshness, presets, renderer transfer, scale/extent and Bubble/BTF.

Do not treat this section as evidence that per-mode enablement is already implemented. `Current_Plan.md` owns admission.

## 2. Capability model

| Mode | Idle reveal | Idle self-animation | Presentation-owned idle scene | Fresh current source required for **live audio reactivity** |
|---|---:|---:|---:|---:|
| Bubble | yes | yes | no | yes |
| Spectrum | yes | no | yes | yes |
| Sine | yes | yes | no | yes |
| Oscilloscope | yes | yes | no | yes |
| DevCurve | yes | yes | no | yes |

Paused Spectrum remains intentionally mixed:

```text
presentation_ready = true
reactive_source_ready = false
source identity = absent
```

Idle reveal/self-animation and live audio reactivity are separate contracts. A mode may remain visibly alive while paused or while awaiting a fresh source, but real music must not be treated as current reactive input until generation/activation identity is authoritative. Healthy authored cadence or idle motion therefore does not prove live-source reactivity.

## 3. Logical cadence

Primary owner:

`VisualizerLogicalRuntime`

Supporting logical/source modules remain Python.

Durable accepted destination flow:

```text
source / engine
    -> sole VisualizerLogicalRuntime
    -> mode-owned logical frame runtime (spectrum/oscilloscope/sine/bubble/devcurve)
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

Old GUI `present_tick`/compositor presentation is retired production architecture. Any surviving reference belongs to historical evidence or caller-dead I residue and must not be restored merely to satisfy an old harness.

## 4. Presentation ownership

Destination:

- visualizer pixels live inside the display's sole `QQuickWindow`;
- no separately presented visualizer surface;
- no `QQuickWidget`;
- no independent swap/vsync owner;
- no self-driven visualizer repaint loop.

The historical `SpotifyBarsGLOverlay` presenter is retired. A surviving import/reference is I residue unless exact caller proof identifies a neutral non-presentation contract.

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

Audio analysis uses one persistent serial `visualizer.audio_analysis` compute lane with one in-flight packet plus newest-pending source replacement. Detached DSP state is retained across ordinary frames and rebuilt/fenced only at real config/activation/reset epochs; no generic per-frame Future/task fallback is part of the destination.

Configuration follows the consuming owner. Values used by authored logical evolution or mode-owned frame runtimes are
presentation-neutral resolved configuration; renderer-only style/chrome is presentation-owned. Legacy widget attribute
location and Settings subsection are not ownership rules.

The resolved technical cache is deliberately not monolithic: DSP/capture controls apply through the controller-owned shared
BeatEngine/audio-worker boundary, while technical-origin transient controls that authored logical evolution reads live on
controller-owned logical state. Bar-count reconfiguration keeps controller, engine generation and logical display-bar
mirror/freshness state coherent. Legacy overlay-only mirrors have no destination role without an exact retained consumer.

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

All five current production modes remain:

```text
CARD + CARD_INTERIOR
```

A future mode may explicitly opt into `FRAMELESS + VIEWPORT_RECT`.

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
`QQuickWindow`/`QSGRenderNode`. The `QSGClipNode -> QSGRenderNode` handoff was attempted and **failed**
its pinned PySide 6.9.1 runtime bar (rounded cases exposed stencil metadata whose framebuffer contents
did not match; rectangular cases could expose an invalid sentinel scissor). That failed handoff is
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

### Future frameless modes

Architecture permits a mode to omit:

- background;
- border/frame;
- card shadow.

This is useful for a free-standing 3D object such as the planned deformable sphere.

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
geometry owned the old visualizer. They are not authored mode behavior and are not destination
settings.

All five current Quick modes share one canonical baseline viewport aspect ratio. A mode switch or
preset load does not change viewport/card shape.

That canonical baseline aspect is **1.5**. It is the sensible DEFAULT shape for ordinary non-CUSTOM
layout, not a universal invariant. Distinguish three concepts:

- **default/baseline aspect (1.5)** — the default shape shared by all five modes;
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
- a future 3D sphere uses aspect-correct projection and stays round.

All five current modes support this destination operation and the core Bubble capability/reflow path is landed. Do not
reintroduce a Bubble false gate to conceal an implementation defect. Current G4 audit work is narrower: keep committed
viewport truth separate from the temporary CUSTOM working override and close the remaining nonbaseline Bubble spatial edge
cases without changing authored behavior. `Current_Plan.md` owns the exact open correction list.

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

Historical/current `BeatEngine` retains the same cold-Play ramp and warm-capture policy. Migration-added visible delay must be localized across Media truth -> owner -> source freshness -> mode readiness -> publication -> retained draw rather than hidden by retuning the historical ramp.

The migration must not turn normal Pause/Play into renderer/window recreation. Detailed timing/readiness work lives in `Docs/QtQuick_Migration/H5c_Visualizer_Reactivity_Parity_Audit_Decomposition_2026-08-31.md`.

## 14. CUSTOM / Edit

CUSTOM/Edit preserves one authoritative committed geometry.

Control UI may remain QWidget if appropriate.

Live runtime pixels belong to the Quick scene after migration; edit plumbing must not recreate a
second accelerated presentation surface.

Required visualizer resize semantics:

```text
scroll wheel   -> uniform visual scale
corner handles -> uniform visual scale
left/right     -> viewport width
top/bottom     -> viewport height
```

Viewport resizing is part of the destination CUSTOM contract, not optional QoL and not permission to stretch a
rendered image. Save/Cancel and layout slots preserve scale and extent separately.

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
