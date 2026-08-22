# Visualizer Change Checklist

Last updated: 2026-08-22

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

Logical code does not mutate QWidget, Quick items, GPU resources, or presentation geometry.

## 3. Quick migration presentation seam

```text
logical/source
-> immutable latest snapshot
-> Quick visualizer item synchronization
-> render-thread QSGRenderNode
-> QQuickWindow
```

Do not let the render node read live `SpotifyVisualizerWidget`/QObject mutable state.

## 4. Modes and presentation policy

Preserve all five current mode personalities:

- Spectrum;
- Oscilloscope;
- Sine;
- Bubble;
- DevCurve.

All five remain `CARD + CARD_INTERIOR`.

Future explicitly authored modes may use `FRAMELESS + VIEWPORT_RECT` without a second window or
renderer architecture.

## 5. Retired legacy card-height controls

Do **not** port these into Quick geometry, snapshots, presets or mode descriptors:

```text
spectrum_growth
osc_growth
sine_wave_growth
bubble_growth
devcurve_growth
```

They are pre-Quick presentation customization, not authored mode behavior.

The Quick baseline uses one canonical viewport aspect for every current mode. Mode/preset changes do
not resize that baseline viewport.

## 6. Source/readiness

Separate:

```text
presentation_ready
reactive_source_ready
```

Paused Spectrum idle remains perceptibly visible without fabricated source identity.

## 7. Card / clipping

For carded modes, custom GL remains above card fill, below frame/border, and inside the rounded inner
card path.

Prefer scene-graph clip ownership (`QSGClipNode`) and have `QSGRenderNode` honor incoming scissor/
stencil state. Do not shrink authored content to hide bleed and do not copy old centred-QPainter mask
constants into Quick.

## 8. Geometry

One authority feeds Quick item, shell/card, clip, GL viewport/resolution, DPR and CUSTOM.

Keep distinct:

```text
canonical baseline viewport/aspect
uniform visual scale
viewport extent
```

Whole-size operations:

```text
scroll wheel -> uniform scale, baseline aspect preserved
corner drag  -> uniform scale, baseline aspect preserved
```

Future Phase-G viewport operations:

```text
left/right edge -> viewport width only
top/bottom edge -> viewport height only
```

Viewport expansion changes available world/layout, never final-pixel X/Y stretching.

## 9. Cadence

No pending-until-paint, paint acknowledgement, producer/display divisor, render self-loop, second
logical clock, or second accelerated surface.

Presentation pacer may request Quick frames while custom GL content is dynamic.

## 10. Playback

Pause/Play preserves logical runtime and warm source semantics.

Do not make QML state a second playback authority.

## 11. Bubble

BTF remains binding.

Viewport-bound changes enter as geometry/configuration and may not become another clock.

No algorithm retune to compensate for presentation defects.

## 12. Lifecycle

- generation zero valid;
- logical runtime joins;
- stale snapshots rejected;
- render resources destroyed on render owner;
- hidden state does not erase destruction authority.

## 13. CUSTOM

Use real Quick presentation geometry/session.

No permanent QWidget snapshot shell.

If viewport-edge resizing lands, persist uniform scale and viewport extent separately and preserve
corner/scroll whole-size behavior.

## 14. Installed gates

- all five modes;
- shared canonical baseline aspect;
- baseline aspect preserved by uniform scale;
- wide/tall compatibility without anisotropic stretching;
- carded rounded clipping;
- frameless-policy scene proof;
- Bubble eyes-on/BTF;
- Pause/Play;
- Spectrum idle;
- Settings/recreate;
- CUSTOM Save/Cancel;
- mixed refresh;
- clean shutdown.

Commit and push each landed visualizer slice.
