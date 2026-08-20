# Visualizer Presentation Guardrails

Last updated: 2026-08-20

Read for visualizer cadence, source freshness, render state, fade/readiness, and presentation work.

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

The GUI/Quick boundary is an implementation detail but must be:

- bounded;
- latest-state oriented;
- generation-fenced;
- safe for Quick scene/render-thread ownership;
- independent of physical paint completion.

The migration should remove obsolete GUI `present_tick`/QRhiWidget ownership as those pixels move to
Quick, rather than wrapping it permanently inside another layer.

## 5. Physical presentation

The display's standalone `QQuickWindow` is the sole accelerated runtime presentation surface.

No:

- visualizer native overlay window;
- visualizer `QQuickWidget`;
- second accelerated surface;
- separate visualizer swap/vsync owner.

## 6. Readiness

Distinguish:

```text
presentation_ready
reactive_source_ready
```

Paused Spectrum may reveal presentation-owned idle state while source identity remains absent.

On Play, fresh current-generation/current-activation data replaces idle state in place.

## 7. Fade

One authored fade authority applies to the visualizer/card visual.

Do not create competing QWidget and Quick opacity owners for the same visible pixels.

During migration, temporary old/new paths must never both present the same visualizer simultaneously.

## 8. Source freshness

Measure separately:

- capture/source age;
- logical integration;
- logical publication;
- presentation synchronization;
- render consumption;
- physical delivery.

Smooth motion over stale audio is not healthy.

Do not retune Bubble/shader smoothing to conceal source staleness.

## 9. Pause / Play

Ordinary Pause/Play preserves:

- logical runtime;
- mode identity;
- warm source/capture policy;
- render identity where practical;
- no cold-start detour.

The migration may change the pixel owner; it must not reintroduce playback debounce or recreate the
logical runtime on ordinary Pause/Play.

## 10. Fidelity

Preserve all mode personality and current behavioural goldens.

BTF additionally binds Bubble trajectory, elasticity, transients, source freshness, logical cadence,
edge survival, state-to-screen timing, and final continuity.

## 11. Generation fencing

Generation/activation are ownership identity.

`0` is valid.

Retired state cannot enter a replacement Quick scene, trigger reveal, or mutate current render state.

## 12. Native renderer rule

A native/C++ visualizer renderer is not a migration phase.

Only consider localized native code if profiling of the migrated Quick implementation proves a
specific Python render callback materially limits the result.

Keep the same logical contract and the same display `QQuickWindow`.
