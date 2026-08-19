# P2 Performance Evidence Ledger

Last updated: 2026-08-19 22:49 SAST

## Loaded three-architecture comparison

| Architecture | Provenance | System CPU steady median | Logical service | 165 Hz median | 165 Hz acceptance | 60 Hz median | UI queued | Result |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Operator baseline / GUI tick | SHA not embedded | ~47.2% | ~74.7 Hz long-window median | **72.1** | **68.99%** | **47.7** | ~80 | load collapse predates worker |
| Dedicated worker + push | self-ID `8ac2421e...` | ~41.3% | **~89.7 Hz** | **111.35** | **75.58%** | **52.4** | ~10427 | best known loaded state |
| Dedicated worker + pull | `8ac2421e...` + uncommitted pull | ~43.5% | **~89.6 Hz** | **94.2** | **66.40%** | **49.3** | ~91 | callback count lower; product worse than push; lost-wakeup regression |

## Updated conclusions

### Dedicated worker

**CONFIRMED BENEFICIAL / RETAIN**

Under load it preserves authored logical service near ~90 Hz instead of the baseline ~60–80 Hz collapse.

It also materially improves physical transition delivery relative to the operator baseline.

### GUI callback count as primary bottleneck

**REJECTED**

Baseline and pull both have low queued-UI totals but perform worse than worker+push.

Callback count is not a valid performance oracle.

### Pull presentation

**PROVISIONAL / CURRENTLY NEGATIVE**

No demonstrated product advantage over worker+push.

Loaded performance is worse.

Tail dispatch/frame-gap behavior is worse.

Sporadic visualizer spawn/lost-wakeup is unique to pull.

### Playback flapping

**INHERITED BASELINE DEFECT**

Baseline logs already show pause-state wobble and pause/resume churn.

Do not blame K or pull for originating it.

### Shared GUI physical presentation under load

**COMMON SYSTEMIC DEFECT**

Exists in baseline, worker+push and worker+pull.

Adaptive timer wake timing remains much healthier than GUI dispatch service.

This is the next larger architecture boundary once the codebase is returned to the strongest known worker state.
