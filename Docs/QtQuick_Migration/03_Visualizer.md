# 03 — Visualizer Qt Quick Migration

Status: technical decomposition only
Last updated: 2026-08-20

Cross-links:

- `Current_Plan.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- `Docs/Visualizer_Reference.md`
- `Future_Cleanup.md`

## 1. Preserve the part that already works

Keep `VisualizerLogicalRuntime`.

It remains:

- the only mode-general authored visualizer clock;
- independent of GUI/render cadence;
- latest-state oriented;
- generation-owned;
- no catch-up;
- BTF-bound for Bubble.

Do not migrate logical simulation to:

- QML;
- QSG render thread;
- `FrameAnimation`;
- physical refresh;
- a new per-mode timer.

## 2. Current presentation seam that must change

The current compositor layer can hold a `VisualizerRenderState` whose handle references the live
visualizer owner and heavy mutable arrays.

That was acceptable only because publication and paint were both GUI-thread owned.

It is **not** the Quick render-thread contract.

Do not let the new render node read a live `SpotifyVisualizerWidget`/QObject.

## 3. Extract a non-pixel visualizer runtime owner

The Quick path must not instantiate a hidden QWidget just to own:

- playback state;
- presets/settings;
- BeatEngine source;
- logical runtime;
- mode state;
- CUSTOM identity.

Extract/construct a presentation-independent visualizer runtime/controller.

Possible decomposition:

```text
VisualizerRuntimeController
    settings/mode/preset activation
    BeatEngine/source ownership
    playback edge ownership
    VisualizerLogicalRuntime
    latest logical snapshot publication

QuickVisualizerPresentation
    geometry/fade/readiness
    retained card visual
    QSGRenderNode visual content
```

Keep source/provider logic in Python.

## 4. Immutable latest snapshot

Define a render-thread-safe snapshot.

Representative fields:

```text
runtime_generation
activation_id
mode
playing
logical_timestamp
fade
card_rect
DPR/render geometry identity

common:
    energy bands
    color/style parameters

Spectrum:
    bars / peaks / ghost state

Oscilloscope:
    waveform geometry/state

Sine:
    sine layer state

Bubble:
    positions
    radii/extra data
    trails
    pop/transient state
    ghost/tail state
    authored style

DevCurve:
    active layer data / order / offsets / alpha
```

The exact payload should come from existing logical state where possible.

Do not deep-copy arbitrary QWidget object graphs.

Use bounded immutable arrays/tuples/owned numpy buffers or another proven immutable snapshot shape.

One latest slot per activation/display presentation.

## 5. Synchronization

Preferred seam:

```text
logical publication
    -> latest immutable snapshot
    -> GUI/Quick item marks state dirty
    -> updatePaintNode/synchronize while GUI blocked
    -> render node receives complete snapshot
```

No render-thread lock that can block on provider/network/GUI work.

No one-GUI-callback-per-logical-tick requirement.

Coalesce naturally: latest state wins.

Protect short-lived authored edges explicitly.

## 6. Quick visualizer item

Use a sub-rect custom render item/node inside the display Quick scene.

The item's geometry is the visualizer card geometry.

Render node owns GL programs/resources.

Reuse current:

- mode fragment shaders;
- shared vertex shader where valid;
- renderer uniform upload helpers;
- Bubble data format/math;
- stencil/mask logic after converting window-space assumptions to Quick item/window geometry.

Do not route through an offscreen QWidget card texture as the final design.

## 7. Card visual

Port the visualizer/card chrome to retained Quick presentation.

Preserve:

- background opacity;
- border;
- radius;
- card shadow;
- header/text;
- card fade;
- geometry;
- current color/customization.

The custom GL visual content and retained card chrome must share one authoritative geometry source.

Do not maintain a hidden QWidget as geometry authority.

## 8. Geometry

Create one presentation geometry structure per committed visualizer state.

It feeds:

- Quick item x/y/width/height;
- GL viewport/scissor;
- shader logical resolution;
- framebuffer origin where required;
- mask/border radius;
- CUSTOM edit geometry.

The display `QQuickWindow`/QScreen owns DPR.

No visualizer-local stale DPR.

## 9. Fade/readiness

Keep separate:

```text
presentation_ready
reactive_source_ready
```

Presentation ready requires:

- visualizer Quick item exists;
- geometry committed;
- renderer resources ready;
- card chrome drawable;
- intentional state available.

Paused Spectrum may reveal idle bars without fabricated source identity.

Fade one parent/presentation opacity authority where practical.

Do not use a shadow/effect enable/disable toggle as the fade animation.

## 10. Mode requirements

### Spectrum

- idle bars perceptibly visible while paused;
- source identity absent until real source;
- Play replaces idle bars in place;
- peaks/ghosting preserved.

### Oscilloscope

- exact line count and persistence behaviour;
- idle authored motion preserved.

### Sine

- authored idle motion;
- line/layer persistence;
- no mode-specific presentation clock.

### Bubble

BTF mandatory.

Preserve:

- trajectories;
- collision/elastic feel;
- trails/tails;
- ghost/pop/transients;
- source freshness;
- logical Hz;
- protected edges.

No retune to hide presentation issues.

### DevCurve

Preserve all active layer:

- enabled state;
- order;
- alpha;
- offsets;
- outline;
- ghosting;
- mode tuning.

## 11. Pause / Play

Ordinary Pause/Play:

- same logical runtime;
- no window/item recreation;
- no source debounce;
- warm source policy preserved;
- visible state changes promptly;
- current expected-state confirmation contract preserved.

Do not make Quick activation state a second playback authority.

## 12. CUSTOM

Visualizer becomes an ordinary participant in the Quick edit scene.

No special QWidget screenshot shell required.

During edit:

- suspend/hold authored geometry ownership exactly as required by CUSTOM;
- edit presentation geometry;
- Save commits canonical custom layout;
- Cancel restores baseline;
- logical runtime/source remains correctly owned.

## 13. Lifecycle

On retirement:

```text
close visualizer publication
-> join VisualizerLogicalRuntime
-> invalidate snapshot generation
-> Quick item loses admission
-> render-node GL resources destroyed on render owner
-> QML/item/controller roots destroyed
```

Do not let visibility determine destruction authority.

## 14. Tests/gates

Permanent:

- one logical clock;
- generation 0;
- all five modes;
- source freshness;
- protected edges;
- BTF;
- Pause/Play;
- Spectrum idle;
- CUSTOM;
- Settings recreate;
- stale activation/generation rejection.

Quick-specific:

- render thread distinct;
- snapshot immutable/thread safe;
- no live QWidget/QObject render access;
- geometry non-zero origin + non-1 DPR;
- card/shader alignment;
- clean resource deletion;
- physical cadence.

## 15. Commit cadence

Push after:

1. non-pixel runtime/controller split;
2. immutable snapshot bridge;
3. Quick card/geometry;
4. Spectrum;
5. Oscilloscope + Sine;
6. Bubble + BTF;
7. DevCurve;
8. all-mode lifecycle/perf closure.
