# Visualizer Presentation Guardrails

Last updated: 2026-08-18

Read after `Docs/Presentation_Change_Preflight.md` for any visualizer cadence, source freshness,
render-state, fade/readiness or presentation work.

## 1. Current Architecture Boundary

There are two authorities, not two presentation surfaces:

1. **Visualizer logical/source authority** — audio analysis, mode simulation, authored dt,
   events/edges, smoothing and current render-state publication.
2. **Display presentation authority** — the display's single QRhi/OpenGL compositor chooses
   physical presentation opportunities and draws the latest valid state.

`SpotifyBarsGLOverlay` is not a surface anymore. It is a logical state/geometry/visualizer-GL
resource owner. Actual pixels are rendered through the compositor visualizer layer.

## 2. Logical Cadence Rules

- preserve source/audio cadence and authored visualizer tick semantics;
- integrate every logical input before any presentation coalescing;
- never derive logical dt/event consumption from paint;
- never pause simulation until paint;
- never introduce a second recurring visualizer presentation timer;
- never mutate authoritative logical arrays in compositor render callbacks.

## 3. Physical Presentation Rules

The display compositor's existing adaptive render strategy may be the sole **physical
presentation strategy** for the display when its liveness includes the visualizer.

It is not a visualizer simulation clock.

### R-61 / R-62 scope

R-61 and R-62 rejected binding a separately presented visualizer surface to a
transition-scoped timer/deferral design. The failures were real and remain negative controls.

They do **not** prohibit the one-surface architecture from using the display compositor's own
presentation strategy once visualizer rendering is part of that same scene and visualizer
liveness keeps that strategy active outside transitions.

Do not read the old phrase “AdaptiveTimerStrategy disqualified in any scope” literally across the
new architecture epoch. The durable rule is: **no transition-scoped/paint-coupled mechanism may
become visualizer logical authority or a second-surface presentation hack.**

## 4. Admission / Coalescing

A queued GUI-dispatch guard may prevent duplicate Python callbacks only until the queued callback
actually calls `QWidget.update()`.

After that callback returns, a later display deadline may request another update even if Qt has
not painted yet. Qt owns paint-event coalescing.

Forbidden:

- pending-until-paint;
- paint/swap acknowledgement;
- producer timestamp display-rate gate;
- repaint rescue/retry;
- render callback self-requeue;
- source/event decimation;
- catch-up replay of skipped render snapshots.

## 5. Protected Visible Edges

Bubble and other authored short-lived responses may exist for fewer logical publications than
physical presentation opportunities. Tests must protect the **actual visible edge/state**, not
merely the trigger event.

Presentation may skip stale intermediate snapshots only after logical state has integrated. It may
not erase an approved short-lived response without an explicit bounded edge/state contract.

## 6. Source Freshness

Compositor state-to-paint age and upstream audio/analysis age are separate.

If state-to-paint is healthy but the visualizer feels late, inspect the source/analysis pipeline.
Do not compensate by reducing smoothing or changing shader maths without evidence.

For asynchronous analysis:

- at most one compute may be in flight per owner;
- one newest pending source frame may replace an older pending frame;
- no FIFO/backlog/catch-up queue;
- completed valid DSP state commits before launching the latest pending work;
- generation/activation replacement discards stale pending/in-flight publication.

## 7. Startup / Mode / Playback Readiness

A visible fade must not begin before the single-surface renderer/card resources needed to draw it
are ready for the current QRhi/runtime generation.

Readiness may include:

- current compositor QRhi/OpenGL generation;
- visualizer programs/VAO/VBO/mask resources;
- authoritative card geometry and current card texture revision;
- final current engine generation/activation;
- required first fresh frame/audio readiness.

Readiness is state-driven, not a fixed sleep.

Ordinary play/pause should not destroy/recreate visualizer GL resources. Warm capture/resume should
remain warm. Cold restart happens once when actually necessary.

## 8. Fade Authority

The compositor owns visualizer/card pixels from fade zero through completion. A hidden logical
QWidget's `QGraphicsOpacityEffect` cannot be a competing pixel owner.

Preserve the authored fade duration/easing unless explicitly changed, but expose one scalar to both
card texture and visualizer shader. No midway owner handoff, flash, slam or full-opacity fallback.

## 9. Fidelity

Preserve:

- Bubble simulation/dt/one-in-flight semantics, positional/extra/trail state and transients;
- Spectrum source smoothing/presentation behaviour;
- Sine/Oscilloscope waveform/ghost/transient behaviour;
- DevCurve mode state;
- mode reset isolation;
- CUSTOM geometry/DPR;
- source freshness and mode personality.

Do not weaken goldens because presentation plumbing changed.

## 10. Validation

Runtime-shaped tests must exercise:

- 60 Hz and high refresh;
- irregular GUI stalls;
- transition overlap and transition-free visualizer presentation;
- startup, mode change, pause/resume;
- generation/context replacement;
- short-lived Bubble visible edge;
- source age and state-to-paint separately;
- no callback backlog after paint admission is removed.

Installed manual review remains required for visual feel/timing changes.
