# Visualizer Post-Switch Performance Investigation — Closed Reference

Status: **CLOSED — NO PERSISTENT POST-SWITCH DEFECT REPRODUCED**
Historical oracle bug: `Docs/Historical_Bugs/R-80_ABC_EventLoop_Rolling_Window_Contamination.md`
Guardrail: `Docs/Guardrails/Performance_Optimization_Contract.md`

## Closure

The investigation is closed as active work. The repaired R-80 oracle showed that the intentionally abusive 25-switch sequence does **not** leave Bubble in a persistent degraded/poisoned state for the tested build/load. Rapid mode startup/transition work can hitch while the switches are actually happening; that is not actionable performance debt when it does not linger, leak, multiply owners/resources, or weaken later steady-state presentation.

The earlier `swap_sensitive` / “Quick-runtime recreation clears the tail” conclusion was invalid. `EventLoopStallRecorder` retained about 102.4 seconds of rolling history, so real switch-time stalls bled into later named windows and were scored as if they were fresh steady-state samples. R-80 corrected the oracle by giving causal windows independent period slices/reset boundaries and failing old unsliceable logs closed.

Corrected live A/B validation (`main_mc.py`, slot 1, four contention workers, `--usage --viz --perf --life`) produced A mean window-local p99 **5.87 ms** and B-after-25-switches **6.80 ms** (+0.93 ms / +15.8%), below both investigation regression gates. Both had three >25 ms events, ~89.9 Hz logical revision, 1.000 Bubble integration and ~60 Hz draw rate. There was no persistent B-only tail and therefore no reason to run C/recreation.

## Durable conclusions

Keep these only as bounded evidence and regression context:

- repeated render-host activation/retirement, including Sphere, converged to one active renderer; inactive resources retired and the shared quad did not multiply;
- the mandatory `_InheritedGlState.capture()/restore()` correctness fence was not the cause of the false settled tail and remains non-removable;
- repeated presentation/publication/present-request counts did not show runaway amplification;
- GUI `sync_present()` timing, Python thread census, GC, aggregate image-cache totals and native thread counts did not explain the false persistent signal;
- the Spectrum cold-paused activation correction discovered during testing remains a real product fix;
- the original long-run user-visible hitch was never re-established with a trustworthy oracle and has no active attribution campaign.

Do **not** turn the rapid 25-switch burst into a backlog item merely because it hitches while five heavyweight modes are repeatedly starting and retiring. Reopen performance work only when future logs or a directly observed run produce a **persistent, growing or otherwise traceable defect** after the triggering activity has ended.

## Retained diagnostics policy

Retain only tooling that is useful later without burdening ordinary runtime:

- `tools/visualizer_switch_abc_harness.py` and the opt-in in-app ABC driver remain as explicit operator diagnostics;
- `--viz-switch-telemetry` retains boundary-only render-host lifecycle/ownership telemetry, allocated only when explicitly admitted;
- R-80 window-local event-loop scoring remains under `--perf`/ABC diagnostics so future causal windows cannot reuse stale rolling history;
- repeated-switch lifecycle tests remain because they prove bounded ownership/retirement invariants.

The closed P4 presentation/fence timing module and its hot-path calls were removed. Ordinary Standard/MC runtime must not pay even an `is None` check per frame/draw/presentation edge for a closed investigation, and general logging must not carry investigation-only output.

## Reopen gate

There is **no scheduled soak, H-number branch or active performance task**. If future normal use or logs expose a genuine persistent/traceable issue, preserve that failing condition first, then use the smallest already-retained diagnostic that can answer a concrete missing fact. Add new instrumentation only after the actual defect is reproduced and only when existing evidence cannot localize it.

Correctness fences remain binding: GL-state isolation, fresh-source/admission fencing, stale-generation rejection, stale-frame/bleed prevention, authored ~90 Hz logical evolution, 60 Hz presentation target, source freshness and Bubble geometry/reactivity may not be weakened for performance work.
