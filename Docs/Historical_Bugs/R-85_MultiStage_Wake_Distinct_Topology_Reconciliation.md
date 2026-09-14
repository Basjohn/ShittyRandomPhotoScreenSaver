# R-85 — Multi-Stage Monitor Wake Presented Two Distinct Valid Topologies Seconds Apart

Date: 2026-09-14  
Status: Correctness Preserved / Installed Soak Validation Pending

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure Candidate

At wake from the overnight display-off soak, SRPSS performed two complete display-generation reconciliations. The first retired the long-lived LG-only generation when Windows exposed an MSI-only topology; roughly three seconds later Windows/Qt exposed the final MSI+LG topology and SRPSS rebuilt again. The second rebuild produced a noticeable wake-time event-loop tail.

At first glance this looked like missing monitor-event debounce.

## Investigation Result

The current topology owner already coalesces same-burst topology/metric/application edges for roughly **250 ms**. The two wake states were not duplicate adjacent signals inside that window:

- around 13:46:11 Windows/Qt exposed a settled **MSI-only** signature;
- that generation completed its destruction/rebuild barrier;
- around 13:46:14 Windows/Qt exposed the distinct final **MSI+LG** signature.

A generic multi-second debounce would therefore delay legitimate hotplug/removal handling and still could not know whether a seconds-long one-screen state is transient wake choreography or the user's true final topology.

No production topology change was admitted. R-79's correctness contract remains binding: reconcile authoritative signatures and prefer correct ownership over speculative wake smoothing.

## Regression Coverage

`tests/test_qtquick_monitor_wake_reconcile.py` now explicitly protects the distinction:

- multiple topology/metric/resume edges within the existing settle window coalesce to one reconciliation;
- a genuinely distinct topology that remains beyond that window is allowed to reconcile;
- a second distinct signature seconds later is also reconciled rather than hidden behind an arbitrary long debounce;
- existing same-signature wake/repair behavior remains covered.

No new probe is required. Existing lifecycle/topology diagnostics are the correct evidence source; `--perf` should not gain another wake-specific stream.

## Validation Target

Repeat physical two-display sleep/wake and display-off soaks, including mixed timing where one display returns several seconds before the other.

Require:

- final windows bind to the correct displays with no straddling, duplicate owners, stale generation, or empty surface;
- destruction barriers complete for each authoritative topology;
- same-burst duplicate edges still coalesce;
- genuinely distinct seconds-apart signatures are not suppressed;
- if wake-time rebuild cost becomes user-visible enough to optimize, first identify a reliable wake-specific settling signal rather than globally increasing debounce.

## Guardrail

Do not infer "duplicate topology event" merely from two rebuilds near wake. Compare authoritative signatures and timing. A debounce long enough to hide a real seconds-apart topology change is not a correctness-preserving optimization unless a separate wake-specific finality signal exists.
