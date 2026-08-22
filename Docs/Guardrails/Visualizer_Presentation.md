# Visualizer Presentation Guardrails

Last updated: 2026-08-22

Read for visualizer cadence, source freshness, render state, fade/readiness, shell/clip policy,
geometry, and presentation work.

For Bubble also read `Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

## 1. Ownership

Accepted direction:

```text
audio / analysis
        ↓
VisualizerLogicalRuntime
        ↓ latest logical/render state
Quick presentation bridge
        ↓
display QQuickWindow scene/render owner
        ↓
physical presentation
```

`VisualizerLogicalRuntime` remains the sole authored visualizer clock.

It owns:

- authored deadline/dt;
- source snapshot consumption;
- mode simulation;
- envelopes/events/transients;
- visual-only logical motion;
- latest plain-data publication.

It does **not** mutate:

- QWidget;
- QQuickItem/QObject scene state directly from the worker;
- QPixmap/QPainter;
- GPU/GL/RHI resources.

## 2. One logical clock

Forbidden logical owners:

- recurring GUI visualizer timer;
- AnimationManager visualizer listener;
- per-mode logical timer/thread;
- physical compositor/render timer;
- Quick animation driver as simulation authority.

Qt Quick may present at display cadence while logical simulation remains independently authored.

## 3. Latest-state rule

Latest wins after authored integration.

No:

- FIFO;
- backlog;
- catch-up;
- one GUI callback per logical publication as a requirement;
- paint/present acknowledgement.

Protected short-lived visible edges require explicit survival tests.

## 4. Quick presentation bridge

The GUI/Quick boundary must be:

- bounded;
- latest-state oriented;
- generation-fenced;
- safe for Quick scene/render-thread ownership;
- independent of physical paint completion.

The migration removes obsolete GUI `present_tick`/QRhiWidget ownership as pixels move to Quick rather
than wrapping it permanently inside another layer.

## 5. Physical presentation

The display's standalone `QQuickWindow` is the sole accelerated runtime presentation surface.

No:

- visualizer native overlay window;
- visualizer `QQuickWidget`;
- second accelerated surface;
- separate visualizer swap/vsync owner.

## 6. Shell policy is not mode rendering

Do not hard-code "visualizer always owns a card" into the render host.

Resolve a lightweight presentation policy before render-thread admission.

Minimum policies:

```text
shell:
    CARD
    FRAMELESS

clip:
    CARD_INTERIOR
    VIEWPORT_RECT
```

All current five modes remain:

```text
CARD + CARD_INTERIOR
```

A future explicitly authored frameless mode may use:

```text
FRAMELESS + VIEWPORT_RECT
```

`FRAMELESS` removes card background/frame/shadow only. It does not create a new native window and does
not grant unrestricted display-wide drawing.

Shell policy must not become a second playback/mode clock.

## 7. Clip contract

Carded custom-GL content must remain:

```text
above card fill
below visible frame/border
inside rounded inner card path
```

Historical R-21 is binding evidence that shrinking the GL render rect to hide bleed is wrong because
it changes authored content geometry.

The exact pinned PySide 6.9.1 scene-graph clip-node proof failed. Current Quick ownership is one
render-node-local SDF/stencil host:

- `CARD_INTERIOR` uses the rounded canonical inner-card geometry;
- `VIEWPORT_RECT` uses the same host with zero radius;
- the host and mode draw use the same render-target viewport;
- supplied RenderState scissor/stencil values are honored;
- direct GL does not clear or overwrite scene-graph clip contents as if it owned the framebuffer;
- temporary stencil contents and every touched direct-GL state are restored.

Do not preserve the failed clip-node route as a second selectable implementation.

## 8. Card interior geometry

Do not copy QWidget/QPainter mask constants into Quick.

Historical centred-pen math such as:

```text
1px inset + border_width / 2
```

was specific to the old painted-card implementation.

Qt Quick card border geometry is different; derive the content clip from the actual retained Quick
shell.

One canonical geometry authority owns:

- outer card;
- border width;
- inner content path;
- inner radius;
- content rect;
- DPR.

Card frame and custom GL may not use competing geometry calculations.

## 9. Geometry: one baseline aspect; scale and viewport extent are distinct

All five current modes share one canonical baseline viewport aspect in the Quick architecture. Mode changes and mode presets do not resize that baseline viewport. The legacy per-mode `spectrum_growth`, `osc_growth`, `sine_wave_growth`, `bubble_growth`, and `devcurve_growth` card-height controls are retired and must not be copied into Quick.

The visualizer geometry model must distinguish:

```text
uniform_visual_scale
```

from:

```text
content_viewport_size / extent
```

Uniform scale changes the whole authored visual size while preserving the canonical baseline aspect. Scroll-wheel and corner-handle resize use uniform scale.

Viewport extent changes how much layout/world is available. Only the explicit Phase-G left/right or top/bottom edge resize changes one viewport axis independently.

Do not implement wide/tall visualizers by stretching a rendered texture or scaling X and Y
independently. Do not use a retired per-mode growth value as a hidden viewport-extent alias.

Where a logical mode needs spatial bounds, committed viewport metrics may enter the logical runtime as
configuration. They do not become another clock.

## 10. Readiness

Distinguish:

```text
presentation_ready
reactive_source_ready
```

Paused Spectrum may reveal presentation-owned idle state while source identity remains absent.

Readiness depends only on resources actually required by the resolved shell policy. A frameless mode
must not wait for card resources it does not own.

On Play, fresh current-generation/current-activation data replaces idle state in place.

## 11. Fade

One authored fade authority applies to the complete visualizer presentation root (the single
animation/progress owned by `presentation_fade`).

That one authority resolves into two DERIVED per-layer values on
`ResolvedVisualizerPresentation`, mirroring the legacy scene-fade/gpu-fade split:

- `scene_fade` -> the presentation-root/card opacity (`scene_controller` applies it via
  `root.setOpacity`);
- `content_fade` -> the GL content opacity fed to shader `u_fade` by every mode renderer; it is the
  Quick-era successor of the authored bars-stagger fade (`bars_fade_from_progress`), so content arrives
  after the card is established.

`content_fade` is a distinct LAYER value, not a second clock. It must always be a pure function of the
same fade progress as `scene_fade`; never drive it from an independent animation/timer and never treat
it as a permanent second fade authority. (Pre-cutover the Quick publisher leaves it at 1.0 because the
live fade animation is not yet wired into the Quick path.)

For carded modes the authority fades shell + content coherently.

For frameless modes it fades content without manufacturing invisible card dependencies.

Do not create competing QWidget and Quick opacity owners for the same visible pixels, and do not add a
second Quick fade animation/clock for the visualizer content.

During migration, temporary old/new paths must never both present the same visualizer simultaneously.

## 12. Source freshness

Measure separately:

- capture/source age;
- logical integration;
- logical publication;
- presentation synchronization;
- render consumption;
- physical delivery.

Smooth motion over stale audio is not healthy.

Do not retune Bubble/shader smoothing to conceal source staleness.

## 13. Pause / Play

Ordinary Pause/Play preserves:

- logical runtime;
- mode identity;
- warm source/capture policy;
- render identity where practical;
- no cold-start detour.

The migration may change the pixel owner; it must not reintroduce playback debounce or recreate the
logical runtime on ordinary Pause/Play.

## 14. Fidelity

Preserve all current-mode personality and behavioral goldens.

BTF additionally binds Bubble trajectory, elasticity, transients, source freshness, logical cadence,
edge survival, state-to-screen timing, and final continuity.

Non-default viewport aspect must not be implemented by anisotropically stretching Bubble circles,
line widths, or future 3D objects.

## 15. Generation fencing

Generation/activation are ownership identity.

`0` is valid.

Retired state cannot enter a replacement Quick scene, trigger reveal, or mutate current render state.

## 16. Native renderer rule

A native/C++ visualizer renderer is not a migration phase.

Only consider localized native code if profiling of the migrated Quick implementation proves a
specific Python render callback materially limits the result.

Keep the same logical contract and the same display `QQuickWindow`.
