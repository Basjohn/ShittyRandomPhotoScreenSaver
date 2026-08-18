# Presentation / Cadence Change Preflight

Last updated: 2026-08-18

Rejected-mechanism register for current QRhi single-surface presentation. It does not override
`Current_Plan.md`.

## 1. Architecture Epoch

Current production direction is **one accelerated QRhi/OpenGL compositor surface per display**.
The Spotify visualizer is a layer inside that surface. Any historical record describing a
separate visualizer `QOpenGLWidget`/`QRhiWidget` is evidence from the previous architecture.

## 2. Rejected Mechanisms

| Mechanism | Why rejected | Still rejected now? |
|---|---|---|
| producer timestamp/display-rate divisor | quantizes 90–100 Hz sources and changes visible cadence | yes |
| pending-until-paint admission | Qt delivery delay becomes scheduler backpressure | yes |
| paint/swap acknowledgement | producer/presentation deadlines depend on consumer completion | yes |
| render callback self-`update()` loop | creates independent repaint loop/UI pressure | yes |
| repaint rescue/requeue timer | more GUI pressure without fixing delivery | yes |
| admission before logical integration | loses/decays authored events before publication | yes |
| source/event decimation | lowers fidelity to improve FPS | yes |
| catch-up replay | bursts stale visual states after a stall | yes |
| separate visualizer presentation surface | measured material shared-GUI/presentation cost; sibling QRhi was worse | yes |
| transition-scoped timer driving a separate visualizer surface (R-61/R-62) | freezes/degrades visualizer and couples it to transition lifecycle | yes |

## 3. Adaptive Timer Clarification

Older docs said `AdaptiveTimerStrategy` was “disqualified in any scope.” That statement belonged
to the old separate-visualizer-surface experiments and is superseded by the single-surface
architecture.

Current distinction:

**Forbidden**

- using adaptive timer as visualizer source/simulation cadence;
- using a transition-only liveness scope so visualizer presentation stops when transition ends;
- using it to pace another visualizer QWidget/QRhiWidget;
- making paint completion release its next deadline.

**Allowed/current**

- one display compositor physical presentation strategy targeting the display refresh;
- liveness remains active while either a transition or visualizer needs animated presentation;
- it presents the freshest already-integrated scene state.

## 4. Dispatch Guard Clarification

One cross-thread `dispatch_pending` flag is allowed only to prevent duplicate queued Python GUI
callbacks.

Lifecycle:

```text
timer/deadline
   -> queue GUI callback (dispatch_pending=true)
   -> GUI callback executes
   -> QWidget.update()
   -> dispatch_pending=false
```

A later deadline is then eligible even before paint. A second flag that stays latched until paint
and rejects deadlines is the forbidden pending-until-paint family regardless of its variable name.

## 5. Visualizer Logical / Presentation Boundary

```text
audio/events
   -> analysis/logical integration at authored cadence
   -> current generation/activation render state
   -> sole display compositor presentation opportunity
```

Presentation may sample latest current state. It may not modify logical time, source/event cadence
or mode state.

## 6. Short-Lived Edge Rule

Latest-state sampling alone is insufficient where an approved visible response can exist for a
single logical publication. Protect/assert the actual visible state/edge, not only its trigger.

## 7. No Instrumentation Escalation By Default

When source/current architecture already identifies a policy-violating owner, fix the owner and
use existing passive evidence. Do not add another diagnostic family simply to prove an already
known paint-ack latch, duplicate surface, cold startup compile or duplicate activation transaction
exists.

New instrumentation is justified only when the next architectural decision genuinely cannot be
made from current source + existing evidence.

## 8. Runtime Evidence

Use the owning sidecars:

- `screensaver_perf.log`: display delivery/frame evidence;
- `screensaver_spotify_vis.log`: logical/state/source-age visualizer evidence;
- `screensaver_lifecycle.log`: lifetime/cleanup;
- `screensaver.log`: human narrative/WARNING+.

High paint/update ratios are not proof of useful physical presentation.

## 9. Required Acceptance

For presentation changes require:

- logical/fidelity goldens remain green;
- 60 Hz remains effectively refresh-limited;
- high-refresh result materially reflects removal of known admission loss;
- state-to-paint remains healthy;
- source age/reactivity does not regress;
- no GUI callback backlog growth;
- no new presentation timer/surface;
- installed visual review when feel/fade is affected.
