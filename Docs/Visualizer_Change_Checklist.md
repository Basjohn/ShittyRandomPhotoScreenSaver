# Visualizer Change Checklist

Last updated: 2026-08-20

Use for visualizer settings, presets, logical analysis, activation, rendering, card geometry,
fade/readiness, playback or CUSTOM work.

Read:

- `Current_Plan.md`
- `Docs/QtQuick_Migration/03_Visualizer.md` during migration
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md` for Bubble

## 1. Logical runtime

`VisualizerLogicalRuntime` remains current/destination authored cadence owner.

Exactly one runtime per enabled generation.

No GUI/Quick/render clock advances simulation.

## 2. Worker ownership

Logical code does not mutate:

- QWidget;
- Quick items;
- GPU resources;
- presentation geometry.

## 3. Quick migration presentation seam

Destination:

```text
logical/source
-> immutable latest snapshot
-> Quick visualizer item synchronization
-> render-thread QSGRenderNode
-> QQuickWindow
```

Do not let the render node read live `SpotifyVisualizerWidget`/QObject mutable state.

## 4. Modes

Preserve all five:

- Spectrum;
- Oscilloscope;
- Sine;
- Bubble;
- DevCurve.

Keep mode personality/goldens.

## 5. Source/readiness

Separate:

```text
presentation_ready
reactive_source_ready
```

Paused Spectrum idle remains perceptibly visible without fabricated source identity.

## 6. Card/geometry

One authority feeds:

- Quick item rect;
- GL viewport/scissor;
- shader resolution/origin;
- mask/border;
- CUSTOM.

No hidden QWidget geometry authority in the final Quick path.

## 7. Cadence

No:

- pending-until-paint;
- paint acknowledgement;
- producer/display divisor;
- render self-loop;
- second logical clock;
- second accelerated surface.

Presentation pacer may request Quick frames while custom GL content is dynamic.

## 8. Playback

Pause/Play preserves logical runtime and warm source semantics.

Do not make QML state a second playback authority.

## 9. Bubble

BTF remains binding.

No algorithm retune to compensate for presentation defects.

## 10. Lifecycle

- generation zero valid;
- logical runtime joins;
- stale snapshots rejected;
- render resources destroyed on render owner;
- hidden state does not erase destruction authority.

## 11. CUSTOM

Use real Quick presentation geometry/session.

No permanent QWidget snapshot shell.

## 12. Installed gates

- all five modes;
- Bubble eyes-on;
- Pause/Play;
- Spectrum idle;
- Settings/recreate;
- CUSTOM Save/Cancel;
- mixed refresh;
- clean shutdown.

Commit and push each landed visualizer slice.
