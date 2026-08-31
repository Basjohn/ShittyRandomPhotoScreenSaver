# Visualizer Presentation Guardrails

Last updated: 2026-08-29

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

### Configuration ownership follows the consumer

Do not classify visualizer settings by legacy widget field location, Settings subsection, or by whether a name sounds
"visual" or "technical". If authored logical evolution or a Spectrum/Oscilloscope/Sine/Bubble/DevCurve mode-owned logical
frame runtime consumes the value, the value must be available through presentation-neutral resolved logical/runtime
configuration. Renderer-only colour/glow/card/chrome/style remains presentation-owned. Do not solve missing neutral
configuration by copying every `SpotifyVisualizerWidget` attribute into the controller.

The canonical resolved technical cache is also split by consumer:

- floor/sensitivity/audio-block/dynamic-range/AGC/input-gain/kick-lane and similar DSP inputs go through the **single
  controller-owned shared BeatEngine/audio-worker boundary**;
- transient pulse/clamp and mode transient-mix values consumed by authored logical evolution live on controller-owned logical
  state even though their settings provenance is "technical";
- bar-count changes must keep controller `bar_count`, shared-engine reconfiguration/generation, and the logical display-bar
  mirror/freshness state coherent;
- legacy overlay mirrors do not survive merely because the old QWidget technical applier wrote them.

Needing the shared BeatEngine is not a reason to retain a QWidget owner.

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

### Bridge population is an ownership bar

A `VisualizerSnapshotBridge` connected to the Quick item is not sufficient. Exactly one GUI/Quick synchronization owner must:

```text
latest VisualizerLogicalFrame
+ current resolved presentation state
-> identity-fenced VisualizerRenderSnapshot
-> existing bridge
-> retained Quick visualizer consumer
```

It may coalesce latest state. It may not add a second timer/cadence, FIFO/catch-up queue, producer wait, paint acknowledgement
or call into legacy `present_tick()`/QWidget/compositor presentation. The resolved presentation record used to compose the
snapshot must also be committed to the retained item at the same synchronization boundary so geometry/policy cannot be resolved
twice into conflicting states.

A test that calls `VisualizerSnapshotBridge.take_for_render()` directly proves the bridge contract only. Destination delivery
requires the real retained `VisualizerRenderItem`/render-node synchronization path to admit the exact identity-fenced snapshot.

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
- valid inherited scissor/stencil state that genuinely corresponds to real framebuffer contents is
  honored (composed with, not cleared); the failed `QSGClipNode` handoff proved arbitrary PySide clip
  metadata is not trustworthy, so this is only the narrower compose-with-valid-state guarantee;
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

Viewport extent changes how much layout/world is available. The required retained CUSTOM edge operations change one viewport axis independently:

```text
left/right edge -> viewport width only
top/bottom edge -> viewport height only
```

All five current production modes must support this destination operation, including Bubble. The core capability policy is
landed for all five modes; do not reintroduce a false Bubble gate as a workaround for viewport defects.

Do not implement wide/tall visualizers by stretching a rendered texture or scaling X and Y independently. Do not use a
retired per-mode growth value as a hidden viewport-extent alias.

Where a logical mode needs spatial bounds, viewport metrics enter the logical runtime as configuration. Ordinary committed
extent is truth outside edit mode; an active CUSTOM working extent is a temporary higher-precedence override. Save commits
the new extent, Cancel restores the old committed extent, and ending CUSTOM removes the override without assuming canonical
`(420,280)`. Bubble is the strict case: positions/trails reflow through the expanded logical world, circles remain round,
and authored render radius remains a fraction of actual card height rather than being divided by domain height. Velocity,
collision and BTF semantics stay coherent: collision/spawn radii and collision-only gap/correction distances multiply by
`domain_h` when mapped back into the expanded world, with an exact canonical 1x1 no-op. Geometry never becomes a clock.

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

Bubble stream/drift movement remains renderer-content-relative across viewport extents: project each nonbaseline axis once
into the expanded logical world and solve trail smear in content coordinates. Do not compensate viewport loss with input
gain, authored speed/control retuning, a new timer, or a second motion state.

Bubble wake history and Bubble-head magnitude are separate contracts. Stored trail history remains content-space invariant and
head radius/reactivity may legitimately follow actual card height, but the Quick wake is an authored presentation effect: each
trail source's **complete** visible footprint (source separation, ripple radius/cap and ring spacing) must remain baseline-pixel
authoritative under edge-resized wide/tall viewports. Correcting only the three trail-source centres is insufficient. This rule
does not define the separate Bubble Ghost/Decay product contract.

## 14A. Product display admission and semantic input

Current product semantics admit one visualizer instance. Resolve its requested monitor against participating Quick displays
before constructing the visualizer owner. Exactly one display owns the controller/logical runtime/Quick edge for an admitted
activation; other displays construct none. Preserve committed/CUSTOM geometry and requested-display fallback/transfer
semantics.

Double-click inside the retained visualizer cycles visualizer mode. Only if family/visualizer semantic hit admission declines
the event may the display-level fallback advance to the next image.

## 14B. Hard retirement barrier

The sole authored `VisualizerLogicalRuntime` is non-daemon generation-owned work. Stop/join failure blocks visualizer and
owning-display generation retirement. Never detach the bridge, report successful owner retirement or continue terminal window
teardown while that runtime remains owned.

## 15. Generation fencing

Generation/activation are ownership identity.

`0` is valid.

Retired state cannot enter a replacement Quick scene, trigger reveal, or mutate current render state.

## 16. Native renderer rule

A native/C++ visualizer renderer is not a migration phase.

Only consider localized native code if profiling of the migrated Quick implementation proves a
specific Python render callback materially limits the result.

Keep the same logical contract and the same display `QQuickWindow`.
