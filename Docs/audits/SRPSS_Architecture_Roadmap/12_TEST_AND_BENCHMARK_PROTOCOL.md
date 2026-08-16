# 12 — Test and Benchmark Protocol

Last reconciled: 2026-08-16

## Objective

Prove improvements against current `main` under equivalent authored scenarios without
sacrificing visualizer behaviour, first-visible response, lifecycle, image/widget quality,
monitor ownership or resource ownership.

Accepted delivery baseline: `Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md`.

Canonical `main.py` is the ordinary performance authority. Diagnostic is for frozen
runtime/lifecycle attribution, not ordinary performance or installed physical-wake acceptance.

## Standard Scenarios

- **S1 cold/warm static** — startup and idle baseline.
- **S2 each visualizer steady state** — same authored source across modes.
- **S3 visualizer temporal fidelity** — source→logical→presentation→paint, deliberate missed presentation opportunities.
- **S4 image transitions** — fixed source/cache set and representative transition families.
- **S5 combined normal operation** — visualizer + widgets + transitions.
- **S6 Settings/Edit recreation stress** — solved lifecycle regression coverage.
- **S7 image/resource churn** — sizes/aspects/transitions/cache pressure.
- **S8 quiescent runtime teardown** — tracked zero plus process/driver residuals.
- **S9–S12 host pressure** — CPU/disk/decode/GPU/mixed load.
- **S13 long soak** — post-warmup slopes/outlier timeline.
- **S14 topology/system lifecycle** — display route/DPR/resolution/system changes.
- **S15 texture identity** — retained current→old contract.
- **S16 logging/persistence** — equivalent scenarios across writer ownership.
- **S17 mixed-refresh presentation ownership** — 165 Hz + 60 Hz, fixed authored visualizer source/transitions.
- **S18 visualizer-disabled residual dispatch control** — Media remains enabled; visualizer absent from construction.
- **S19 physical monitor-off/wake recovery** — both displays physically off before/during screensaver activation, long idle, simultaneous and reversed sequential wake; ordinary installed non-diagnostic acceptance.
- **S20 visualizer configured-monitor absence/recovery** — return before grace, genuine absence beyond ~60 s, fallback once, later configured-monitor return-home once.

## Required Delivery Metrics

Frame interval tails; adaptive wake lateness; queued GUI dispatch wait/skips; paint-pending
wait/skips; request age; paint duration; event-loop lateness; first-visible latency.

Visualizer: source/event identity, authored logical timing, handoff/commit, update request,
paint, source/state age, generation/activation, protected edges/events and user visual result.

Lifecycle/topology: topology-event sequence, debounce restart, accepted snapshot/generation,
replacement decision, destruction-barrier stages, before/after native recovery boundaries,
D0/D1 registration/reveal/readiness, visualizer configured/fallback owner and absence-candidate identity.

## P1–P4 Delivery Gates

Preserve the existing P1 fidelity gate, P2 mixed-refresh production gate, P3 handoff
attribution gate and P4 residual-dispatch gate from `Current_Plan.md` and the Phase 5 delivery report.

No one exact FPS is a unit-test oracle; compare equivalent authored runs and stage distributions.

## P5-A/B Topology Authority Gate

Deterministic tests must prove:

- duplicate `WM_DISPLAYCHANGE` + Qt screen event storms yield one topology decision;
- every relevant event restarts the trailing-edge quiet window;
- a bounded maximum settle prevents endless postponement;
- accepted count/order/geometry/DPR is frozen into one snapshot/generation;
- a transient D0-only sample does not become a destructive D1-absent decision merely because D1 is still waking.

## P5-C Transaction Gate

Prove exactly one old-runtime retirement and one replacement construction per accepted
transaction. Strict Phase 3 GL deletion/currentness/barrier semantics remain unchanged.
All displays are registered before staged reveal; staggered reveal remains allowed.

Low-rate breadcrumbs must bracket recovery-critical native calls without changing behaviour.

## P5-D Visualizer Ownership Gate

- Existing same-display CUSTOM geometry/aspect stabilization remains intact.
- Monitor present in authoritative topology but asleep/not-ready/not-participating never arms fallback and never moves ownership.
- Settled authoritative absence arms one generation-owned candidate.
- Candidate gets **one coarse recheck at approximately 60 seconds**; exact timing is not tested and late execution under GUI load is acceptable.
- No periodic timer, polling loop, dedicated thread, worker wait or repeated retry chain exists.
- New topology generation invalidates/stales an old candidate.
- Return before the coarse check produces no fallback.
- Still absent at the coarse check permits exactly one fallback owner.
- Later configured-monitor return is detected by normal topology events; after existing runtime readiness, fallback retires and configured ownership returns once.
- Return-home has no reverse polling timer.
- Saved configured CUSTOM geometry remains the authority when ownership returns.

## P5-E Startup/Recovery Image Gate

Ordinary stable desktop→screensaver startup must retain anti-flash behaviour. Physical-wake
or topology-replacement construction must not synchronously depend on `screen.grabWindow(0)`;
use retained SRPSS replay/seed state or wait for the first real frame.

## P5-F Installed Physical-Off/Wake Gate

Run ordinary installed non-diagnostic screensaver cycles:

1. both monitors on → screensaver normal;
2. both monitors physically off before/during activation;
3. long idle/overnight-equivalent where practical;
4. wake both together;
5. repeat D0 then D1 and D1 then D0;
6. repeat with configured visualizer target temporarily late but present;
7. repeat with target genuinely absent >~60 s so fallback occurs once;
8. return target after fallback and confirm one event-driven return-home.

Pass only when both displays reveal, clocks continue advancing, Escape/context-menu/input
work, no Ctrl+Alt+Delete is required, transient participation does not migrate visualizer,
normal startup remains flash-free, and strict GL teardown/resource ownership stays healthy.

If a freeze remains, preserve the last entered/not-returned native breadcrumb and narrow the
next investigation. Do not add sleeps, forced paints, nested event pumping, timeout extensions,
GL retries or monitor polling.

## Checkpoint Rule

Risky slice passes focused gate → clean checkpoint → continue. Stop only on failed evidence,
repository conflict or affected visual judgement.
