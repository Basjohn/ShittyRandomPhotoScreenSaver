# R-03 — 2026-04-18 — Sine Idle Motion Dead/Flat During Paused State (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final resolved state:** Sine idle now remains visibly alive while paused, preserves authored travel direction semantics, and avoids drift/snap artifacts when resuming from idle.
- **Observed failure pattern:**
  - paused Sine intermittently showed zero visible travel despite shader recompiles and passing tests
  - one attempted fallback produced a flat/near-flat visual line
  - later fallback restored motion but introduced out-of-sync lane drift, snap-back, and direction inversion vs authored travel
- **Failed approaches worth preserving:**
  - shader-only idle-phase tweaks without hard runtime payload checks
  - lane-1-only travel fallback (ineffective when visible emphasis came from other lanes)
  - absolute wall-clock shift magnitudes in fallback phase math (precision loss risk inside shader phase arithmetic)
  - per-line multiplier drift in paused fallback (visual de-sync then snap-back)
- **Why the final solution worked:**
  - moved idle fallback authority into renderer upload logic (active-lane aware), not just shader assumptions
  - used bounded incremental idle phase accumulation (wrapped), not absolute-time magnitude injection
  - corrected fallback direction semantics to match existing Sine travel contract (`1=left`, `2=right`)
  - enforced phase-coherent fallback across active lines to remove lane drift/snap artifacts
  - added paused diagnostics at overlay state + uniform upload boundaries so runtime payload mismatches can be seen directly in logs
- **Takeaways:**
  - for paused-idle visual bugs, tests must verify behavior contracts but runtime diagnostics must verify actual per-frame payload values
  - do not use unbounded time-based shift magnitudes in renderer fallback paths
  - preserve authored direction semantics across all fallback layers

## Record Provenance

This standalone file preserves the complete former inline `R-03` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
