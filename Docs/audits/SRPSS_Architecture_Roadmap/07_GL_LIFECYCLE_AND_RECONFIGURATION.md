# 07 — GL Lifecycle and Reconfiguration

Last reconciled: 2026-08-16

## Current Boundary

Full stop–destroy–recreate for Settings and committed Edit remains solved architecture and
a regression contract. The compiled callback-retention/Diagnostic investigation is closed.
Do not reopen those incidents as performance tasks.

A separate physical-monitor path is now active in `Current_Plan.md` P5: both displays can
be physically off while the screensaver remains active, and wake can freeze one display,
leave the other blank and stall all ordinary Qt input until Ctrl+Alt+Delete disturbs the
Windows desktop/display state. The exact blocking native call is **not yet proven**.

Phase 3 did not provide installed physical-off→wake coverage, so P5 hardens the topology
transaction without weakening Phase 3 ownership.

## Durable Lifecycle Contract

- runtime coordinator admits stop/reload after originating owner frames return;
- retire old runtime generation and reject late publications;
- stop producers/timers before deleting display/GL ownership;
- make the sole owner context current for GL mutation/deletion;
- one numeric GL handle has one deletion owner;
- failed deletion retains ownership and fails closed;
- destroy compositor surfaces after child GL ownership is gone;
- destruction barriers prove release and never force it with GC/retry/event pumping;
- replacement construction waits for zero retired ownership;
- reveal waits for fresh current-generation authoritative state.

Physical-wake work may not replace these rules with hide/reuse, best-effort handle clearing,
worker-thread GL teardown, retry loops, timeout extensions or forced event pumping.

## Monitor Topology Transaction Contract

Topology notifications are inputs to one engine/display-manager decision owner.

```text
native/Qt monitor notification
        ↓
invalidate topology
        ↓
trailing-edge quiet settlement
        ↓
freeze authoritative snapshot/generation
        ↓
stop further old-runtime topology mutation
        ↓
retire old runtime exactly once
        ↓
strict GL cleanup + destruction barrier
        ↓
construct/register complete replacement
        ↓
staged display reveal/readiness
```

Every new relevant topology event during settlement restarts the quiet window; a bounded
maximum settlement deadline prevents endless postponement. Once destructive replacement
begins, it uses the frozen snapshot rather than repeatedly rereading a churning display set.

## Native Boundary Attribution

Because an indefinite native call can prevent Qt timers/barriers from firing, P5 adds
low-rate before/after breadcrumbs around only the small recovery-critical set: compositor
cleanup/context acquisition, offscreen/deferred context cleanup where relevant,
surface/compositor creation, display show/reveal, and staggered D0/D1 callbacks.

Breadcrumbs are observational. They must not introduce a watchdog that calls GL from the
wrong thread, retry `makeCurrent()`, pump nested events or change lifecycle decisions.

## Visualizer Ownership During Reconfiguration

Visualizer configured-monitor ownership is separate from same-display geometry correction.
A monitor that exists in settled topology but is not ready/participating remains the owner;
visualizer presentation may park/hide/defer until readiness.

Only genuine settled-topology absence may arm one coarse ~60-second generation-owned
confirmation. This callback is not a GL/lifecycle timeout and does not extend destruction
barriers. If still absent, fallback may occur once. Return-home is driven by later topology
and normal display readiness, with no polling or dedicated thread.

## Desktop Capture Boundary

`screen.grabWindow(0)` remains valid startup polish for a stable desktop→screensaver cold
start. During physical-wake/topology reconstruction it is removed from the critical path:
reuse retained SRPSS image/replay state or keep updates blocked until a real first frame.

## GPU Timing Contract

Ordinary `--perf` performs no query-driver calls. Explicit `--gpu-timing` uses sampled,
asynchronous/non-blocking timer queries where supported. Never `glFinish()` for a number.
Separate texture upload, shader/draw, swap/presentation/context, visualizer overlay/context
and CPU/event-loop delay.

## Verification

- strict zero GL ownership on teardown;
- no cross-thread/currentness errors;
- duplicate native+Qt monitor storms yield one topology decision/rebuild;
- D0-before-D1 and D1-before-D0 wake order do not cause overlapping old-runtime mutation;
- both-off long-idle installed wake restores both displays and input without Ctrl+Alt+Delete;
- temporary visualizer non-participation never migrates ownership;
- genuine absence may fallback once only after coarse grace; stable return restores configured owner once;
- ordinary cold-start anti-flash remains unchanged;
- no polling, dedicated monitor thread, retry loop or relaxed GL ownership is added.
