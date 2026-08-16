# 14 — Failure Triage Map

Last reconciled: 2026-08-16

Use this map to find owners, not symptom patches. Accepted delivery evidence:
`Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md`.

## Frame gap / missed high-refresh deadlines

Split adaptive wake lateness, queued GUI dispatch wait/skips, already-dispatched
paint-pending wait/skips and paint duration. Do not treat request age as one timer problem.

## Visualizer enabled: 165 Hz under-delivery / sibling slowdown

If logical publications and auxiliary visualizer `update()` requests remain one-for-one,
this is bad smell 1. Fix presentation-request ownership; do not lower visualizer cadence.

## Requests suppressed but no-visualizer control is still better

This is remaining visualizer-family handoff/preparation cost. Split producer/state build,
pure-data preparation, Qt overlay commit, presentation request and paint before moving work.

## Visualizer disabled but 165 Hz still misses deadlines

This is bad smell 2. If dispatch-pending dominates while wake lateness is healthy, inspect
concrete queued GUI callbacks; do not tune adaptive timer frequency or add repaint rescue.

## Physical monitors off, then wake leaves D0 frozen / D1 blank / input dead

This is the P5 physical-wake incident family, not ordinary FPS starvation.

Check in order:

1. topology-event receipt and debounce restart;
2. accepted authoritative topology snapshot/generation;
3. whether more than one owner mutated/re-anchored/replaced the same runtime;
4. transaction start/retire-once/destruction barrier;
5. last **entered but not returned** recovery-native breadcrumb (compositor cleanup/context acquisition, deferred/offscreen context cleanup if involved, surface/compositor creation, display show/reveal, D0/D1 staged callbacks);
6. D0/D1 registration and readiness sequence.

If the event loop is stuck inside a native call, Qt timeout timers may not fire. Do not
respond by extending lifecycle timeouts, retrying GL, pumping nested events or moving GL teardown to a worker.

## Visualizer jumps to another display while configured monitor is waking

Treat temporary non-participation as **not absence**. If configured monitor exists in the
accepted topology, hold/park/defer ownership there and keep same-display geometry correction.
Do not arm the ~60-second grace merely because `WidgetManager`/surface/participation is late.

## Configured visualizer monitor genuinely disappears

Only after settled authoritative topology says the target is absent may one generation-owned
absence candidate be armed. One coarse ~60-second check may fallback once if absence remains.
No polling, periodic timer or dedicated thread.

## Configured monitor returns after fallback

Normal topology settlement plus existing display-runtime readiness should retire the
fallback and return ownership once. Do not add a reverse timer or “is it back?” polling loop.
If geometry is wrong after return, debug same-display layout stabilization separately from ownership.

## Black flash / desktop flash introduced during wake fix

First distinguish ordinary stable cold startup from recovery. `grabWindow(0)` is intentionally
retained for normal desktop→screensaver anti-flash startup. Only topology/wake reconstruction
should bypass synchronous desktop capture and seed from retained SRPSS state/first real frame.

## Separate visualizer GL surface suspected

Current A/B/C evidence shows only modest C-over-B gain. Do not begin one-surface-per-display
work unless post-P2/P3 evidence changes that conclusion.

## Window activation correlation

Treat activation as a correlate unless a focus-only same-process intervention proves ownership.
The stronger A/B/C presentation evidence does not require activation as root cause.

## Bubble/Spectrum visual changes

Check shared delivery/presentation ownership first. Do not change Bubble physics/cadence or
Spectrum authoritative logical smoothing without direct mode-owned evidence and approval.

## Temporary A/B/C diagnostic code encountered

P0 removal debt. Keep passive delivery-stage metrics; do not build production behaviour on monkeypatches.

## Memory flat but excessive

Separate RSS/private commit, mappings/stacks, child processes, tracked CPU/GL bytes and VRAM.
Flat is not automatically acceptable; do not trim/recycle/GC to beautify graphs.
