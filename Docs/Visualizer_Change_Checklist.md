# Visualizer Change Checklist

Last updated: 2026-08-19

Use for visualizer settings, presets, logical analysis, activation, compositor rendering, card
geometry, fade/readiness or CUSTOM work.

Also read `Docs/Guardrails/Runtime_Efficiency.md` for shared-runtime/performance changes.

## 1. Identity / Settings

- mode ids/labels: `visualizer_mode_registry.py`;
- grouped settings model stays symmetric;
- preset activation resolves through the canonical preset resolver;
- genuine same-mode preset/settings changes apply once;
- identical same-activation refresh is a no-op rather than duplicate technical work.

## 2. Logical Runtime

- visualizer source/simulation tick remains authoritative;
- every logical input integrates before presentation coalescing;
- no source/event cadence cuts;
- no paint-derived dt/acknowledgement;
- mode-owned history/envelopes/pending state reset only at real activation boundaries.

## 3. Analysis Freshness

For async audio/bar analysis:

- one task in flight;
- one newest pending source frame maximum;
- pending replaces older pending, never appends;
- completed valid DSP state commits before newest pending schedules;
- stale generation/activation work cannot schedule/publish after reset;
- task failure releases ownership without deadlocking the latest valid pending state.

Use delayed-compute tests, not only immediate fake executors.

## 4. Activation

One mode/preset switch must have one authoritative target transaction and one final engine
activation generation.

Bar-count resize, smoothing/floor reset and technical config must not each manufacture independent
intermediate activation generations inside the same switch.

Audio block-size restart is at most once when genuinely required.

## 5. Presentation Owners

Current path:

```text
logical visualizer state
    -> SpotifyBarsGLOverlay logical/resource owner
    -> CompositorVisualizerLayer
    -> display GLCompositorWidget QRhi/OpenGL surface
```

`SpotifyBarsGLOverlay` is not a presented overlay. Do not add:

- QOpenGLWidget/QRhiWidget inheritance;
- its own `update()` presentation stream;
- its own swap/vsync/context lifecycle;
- framebuffer snapshot assumptions;
- fake QPainter visualizer rendering.

## 6. Card / Geometry

One authoritative geometry snapshot feeds card texture, viewport, scissor, shader resolution,
fragment origin, mask and border.

Compositor DPR is the presentation DPR authority.

The QPainter-authored card source is cached by canonical logical-size/DPR/style identity and
uploaded only on revision changes. Steady visualizer frames do not recreate QPainter or re-upload
unchanged card pixels.

Real-GL tests must use non-zero X/Y and non-1 DPR; mock viewport tuple tests are insufficient.

## 7. Presentation Cadence

The display compositor owns physical presentation opportunities. Visualizer logical cadence stays
separate.

Remove/forbid:

- pending-until-paint;
- paint/swap acknowledgement;
- producer/display divisor gates;
- render self-requeue;
- repaint rescue timers;
- second visualizer presentation timer/surface.

A dispatch-pending guard ends when the queued GUI callback calls `QWidget.update()`.

Visualizer-only physical presentation may skip a scene revision already requested when no transition
or fade change requires another physical frame. This is not a logical/source cadence cap.

## 8. Readiness / Fade

Before visible fade:

- current QRhi/OpenGL generation ready;
- visualizer GL resources ready;
- card geometry/cache/GL texture ready;
- final engine generation/activation established;
- required fresh current frame/audio readiness satisfied;
- deterministic normal-runtime GL/program/resource preparation that would otherwise visibly hitch
  immediately after reveal is complete when that work is safe to perform pre-reveal.

Then one compositor-owned fade scalar controls both card and shader from zero to one. No halfway
QWidget/compositor ownership transfer.

Readiness is completion-driven, not a fixed sleep.

## 9. Playback

Immediate post-start health must distinguish STARTING from STALE. A just-started capture is not
restarted merely because the first callback has not happened yet.

Pause/resume should preserve GL/card resources. Warm resume uses warm capture. Cold restart happens
once.

## 10. CUSTOM / Edit

- edit snapshot comes from compositor-owned card+visualizer region;
- no `grabFramebuffer()` dependency on logical overlay;
- drag/resize is preview-only, not live GPU mutation per mouse event;
- Cancel resumes/restores once without re-entering cold startup staging;
- Save rebuilds/publishes the new authoritative rect once;
- cross-display save transfers sole compositor ownership and cleans old display ownership;
- do not confuse intentional edit transfer with temporary-monitor fallback;
- do not use broad settings/CUSTOM replay to restore unrelated preview-only widgets.

## 11. Lifecycle

- visualizer GL resources are tied to compositor QRhi generation;
- borrowed context is never destroyed/doneCurrent by SRPSS;
- hidden/cleared presentation state does not erase destruction authority;
- cleanup is idempotent after success and fail-closed on deletion failure;
- QRhi generation replacement releases old resources before reinit;
- final GL accounting returns to baseline.

## 12. Shared-Runtime Attribution

The 2026-08-19 baseline demonstrated that all five modes can run near intended steady logical cadence
once shared GUI/presentation waste is removed.

Therefore:
- do not call a future cadence regression “Bubble performance” merely because Bubble exposes it most
  clearly;
- compare mode-owned compute/render cost with shared GUI dispatch/timing/cache/recreation cost;
- preserve all-mode fidelity before changing mode algorithms;
- if a future dedicated logical-runtime thread is justified, it is mode-general and replaces one
  unsuitable cadence owner rather than adding a Bubble-specific side lane.

The current 4.7.2 baseline is a negative control against unnecessary mode-specific simplification.

## 13. Fidelity / Tests

Keep current logical goldens for all five modes. Add runtime-shaped tests for the actual owner being
changed. Reintroduce the defect in development where practical to prove the test fails.

Required installed review when relevant:

- all five mode feel/reactivity;
- all-mode switching;
- fade start/finish;
- play/pause/resume;
- 60 Hz + high refresh;
- CUSTOM move/resize/Cancel/Save;
- dual-display ownership;
- first-visible startup/recreation smoothness when GL/warmup ordering changes.

Tests/average FPS never overrule a visible fidelity regression.
