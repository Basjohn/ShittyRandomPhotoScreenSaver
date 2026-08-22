# Visualizer Reference

Last updated: 2026-08-22

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

## 2. Capability model

| Mode | Idle reveal | Idle self-animation | Presentation-owned idle scene | Fresh real source required for reactive playback |
|---|---:|---:|---:|---:|
| Bubble | yes | yes | no | no |
| Spectrum | yes | no | yes | yes |
| Sine | yes | yes | no | no |
| Oscilloscope | yes | yes | no | no |
| DevCurve | yes | yes | no | no |

Paused Spectrum remains intentionally mixed:

```text
presentation_ready = true
reactive_source_ready = false
source identity = absent
```

## 3. Logical cadence

Primary owner:

`VisualizerLogicalRuntime`

Supporting logical/source modules remain Python.

Current durable flow (landed Phase-D boundary):

```text
source / engine
    -> sole VisualizerLogicalRuntime
    -> mode-owned logical frame runtime (spectrum/oscilloscope/sine/bubble/devcurve)
    -> immutable latest-state publication
    -> VisualizerSnapshotBridge
    -> Quick synchronization boundary (take-for-render; not a paint ack)
    -> one QSGRenderNode / lazy mode renderer
    -> render-node-local SDF/stencil clip
    -> retained Quick shell/chrome
    -> one standalone QQuickWindow per physical display
```

During migration, old GUI `present_tick`/compositor code may still exist as reference/current
production.

It is not destination architecture.

## 4. Presentation ownership

Destination:

- visualizer pixels live inside the display's sole `QQuickWindow`;
- no separately presented visualizer surface;
- no `QQuickWidget`;
- no independent swap/vsync owner;
- no self-driven visualizer repaint loop.

The historical `SpotifyBarsGLOverlay` name may temporarily survive as state/resource code during
migration. It is not a presentation-surface contract.

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
- **explicit viewport extent** — the logical/render world, which the Phase-G edge operation may
  intentionally push off 1.5 (modes reflow, never anisotropic final-pixel stretch).

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

Later Phase-G edge operations intentionally change viewport playroom at the same scale:

```text
left/right edge -> viewport width only
top/bottom edge -> viewport height only
```

Expected adaptation at constant scale:

- Spectrum reflows/redistributes bars across available width/height;
- Bubble changes domain/aspect without stretching circles/velocities;
- Oscilloscope/Sine/DevCurve adapt domain while keeping stroke scale;
- a 3D sphere uses aspect-correct projection and stays round.

Phase D builds/tests the geometry seam. Phase G owns the interactive edge-resize QoL.

If a mode cannot safely support viewport resizing without harming authored behavior, ordinary whole-size
scale remains valid and that mode may be marked viewport-resize-incapable.

## 12. Bubble / BTF

`Docs/Guardrails/Bubble_Temporal_Fidelity.md` is binding.

Bubble is a canary for shared timing and must not receive mode-specific cadence hacks to hide
presentation defects.

Viewport geometry changes are spatial configuration, not logical cadence authority.

## 13. Playback

Pause/Play preserves:

- logical runtime identity;
- mode identity;
- source/capture policy;
- no visualizer pause debounce;
- prompt visible authored state change.

The migration must not turn normal Pause/Play into renderer/window recreation.

## 14. CUSTOM / Edit

CUSTOM/Edit preserves one authoritative committed geometry.

Control UI may remain QWidget if appropriate.

Live runtime pixels belong to the Quick scene after migration; edit plumbing must not recreate a
second accelerated presentation surface.

Phase-G preferred visualizer resize semantics:

```text
scroll wheel   -> uniform visual scale
corner handles -> uniform visual scale
left/right     -> viewport width
top/bottom     -> viewport height
```

Viewport resizing is non-blocking QoL, not permission to stretch a rendered image.

## 15. Validation

Use:

- deterministic authored-behavior goldens;
- logical scheduler tests;
- BTF;
- source freshness tests;
- real renderer/output tests where visibility matters;
- Quick runtime-shaped presentation checks;
- card-inner clip tests;
- cardless-policy scene test;
- default/wide/tall geometry tests;
- lifecycle generation tests;
- installed manual review.

A test name does not prove it exercises the real output path.
