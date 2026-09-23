# 08 — Open Items: Evidence, Decisions and Remaining Action

Every item still open: its evidence, the operator decision of 2026-09-23 and the bar or prerequisite that remains.
Item detail lives in 01–05; `Current_Plan.md` owns the implementation order. Accepted items are summarised in 00
§Accepted.

**Decision key.** **Do** — admitted; implement with the named bars. **Do with care** — admitted; the named risk has a
bar that lands in the same slice. **Gated** — decided, but a named prerequisite test must pass before the code change.
**Watch** — parked with a named reopening trigger. **Park** — no action without new evidence. **Close** — no
worthwhile benefit; recorded in 06 §Considered and rejected.

## Evidence sources

| Source | Use |
| --- | --- |
| Idle dev-machine probes on the audited tree (2026-09-23) | per-call costs; installed/loaded numbers are larger |
| Operator runs 2026-09-22 22:53–22:59 and 2026-09-23 08:06–08:09 (`--frame-trace`) | `logs/evidence_chest/0922_BeforeClaudeAuditWork`; first PR-04 trace |
| **D1 heavy-load diagnostic soak, 2026-09-23 09:07–10:40 (≈92.5 min)** | `logs/evidence_chest/logsb86eee25f4.zip`; the operator cannot reasonably reproduce it |
| Grouped physical acceptance run, 2026-09-23 16:53–17:06 (two processes, each with a Settings round-trip) | active-music mode review, transitions, offline Media; only the second process's frame trace survives |
| **Acceptance run 2026-09-23 19:29–19:35** (≈6 min 18 s, generations 0–2, two Settings replacements, normal exit) | `--frame-trace` (1,736,134 records, none dropped); no native fault, no hang (watchdog armed twice for the replacements, never fired), one JPEG decoder warning; transitions Glass ×7, Melt ×4, Particle ×2, Burn, Crossfade, Exploding Tiles, Warp Dissolve, Wipe (no Crumble); six context-menu actions; visualizer mode switches; Media track changes |

The soak ran with `--perf`, `--usage`, handle attribution, visualizer/geometry/settings/lifecycle/cache/Steam/FEEDS
diagnostics and `--frame-trace` enabled, under heavy external load that eased near the end. **Use it for
event-correlated evidence only.** It is not an ordinary-runtime baseline: its raw global FPS, CPU percentage and
isolated event-loop maxima do not justify micro-optimizations. Trace quality: 24,793,350 records written, 117 dropped
(≈0.0005%); the retained rolling segments hold 3,355,809 records covering the final 717.46 s, with logical publish
≈89.91 Hz, GUI wake ≈88.26 Hz, render draw and frame swap ≈89.41 Hz. This supports the existing Qt Quick latest-wins
cadence architecture and does not reopen R-87 pacing. No native fault, no QML message and no hang capture were
recorded; the replacement watchdog armed six times (four Settings, two CUSTOM Edit round-trips) and never fired.

## Summary

| Item | Evidence (short) | Decision | Remaining |
| --- | --- | --- | --- |
| PW-04 Feed model reset | one changed row resets every delegate; 13 FEEDS IO tasks in the soak | **Watch** — FEEDS Custom 2–4 | stable-ID diff only if churn shows |
| PW-03 Media notify | 0.50 ms per emit × ≈0.25 refreshes/s ≈ 0.13 ms/s | **Close** (measured 2026-09-23) | — |
| PR-02 frame-swap callback | 5.6 µs × ≈89.4 swaps/s ≈ 0.5 ms/s (soak) | **Park** | DC-04 stays documented |
| PR-01 resolve memo | 47.6 µs per publication | **Park** | reopen only if publication latency points here |
| PR-07 eager QML compile | ≈0.2–0.3 s, startup only | **Park** | reopen if startup-to-reveal becomes a target |
| ST-01 / ST-02 large owners/files | 4,855-line `DisplayManager` | **Park** | move-only when a real change touches a clean seam |
| VZ-05 epoch cache | 17–117 µs/tick left after the single-freeze fix | **Park** | — |
| VZ-07 sleep slicing | no demonstrated problem | **Park** | — |
| LC-01, PR-05, PW-06, prefetch double batch | see §Closed | **Close** | — |

## Watch (parked with a trigger)

- **PW-04 Feed model reset.** `FeedRowsModel.replace_rows` returns early on an equal tuple, but one genuinely changed
  row still triggers `beginResetModel`/`endResetModel` and retires every delegate. The structural issue exists; it is
  not currently worth changing, because only 13 FEEDS IO tasks completed in the 92-minute soak. Trigger: FEEDS
  Custom 2–4 multi-source physical testing shows delegate/artwork churn on ordinary changed feeds; then implement a
  stable-ID row diff with `dataChanged`.
- **PW-03 Media notify — closed.** One Media `stateChanged` (67 bound properties) costs 0.50–0.51 ms of GUI binding work on a live bound card; the D1 soak had ≈1,400 Media refreshes in 92.5 min (≈0.25/s; timeline edges coalesced to ≥1 s), i.e. ≈0.13 ms/s on average and one ≈0.5 ms slice per edge. Not material.

## Parked

- **PR-02 — queued `frameSwapped` readiness callback.**
  - Cost: 5.6 µs per swap. In the soak that is ≈0.5 ms/s (≈89.4 swaps/s on the traced Visualizer display); at 165 Hz
    on two displays it is ≈1.8 ms/s.
  - Why park: startup/reveal ordering (R-63) is historically fragile.
  - Reopen only when the readiness/reveal machinery is already being changed, or profiling shows the callback has
    become material.
  - DC-04 stays documented as a known source/guardrail mismatch.
- **PR-01 resolve memo.**
  - Cost: 47.6 µs per publication ≈ 4.3 ms/s, spread over tiny publications.
  - Soak: publication ≈89.91 Hz vs GUI admission ≈88.26 Hz, i.e. small, useful latest-wins coalescing and no cadence
    collapse.
  - The retained item stays the comparison authority; no second geometry/presentation cache. Reopen only if GUI
    publication latency profiling points back here.
  - `viz_geometry_mismatches` went 0 → 1 once, at 10:38:32 during a late Spectrum/menu/mode interaction, with no QML
    message, fault or hang. The fail-closed stale-presentation guard was exercised; this is not a new bug. Preserve
    that guard in any presentation work.
- **PR-07 eager QML compile** (startup only): reopen if startup-to-reveal becomes a target.
- **ST-01 / ST-02:** move-only extraction, only when a real change already touches a clean ownership seam.
- **VZ-05 epoch cache.** The accidental double freeze was the real win. Soak:

  | Section | Scene FPS (median) | Revision rate (median) | Age (median) |
  | --- | ---: | ---: | ---: |
  | heavy, Bubble idle | ≈88.87 | ≈89.96 Hz | ≈20.9 ms |
  | late, lighter | ≈90.59 | ≈89.95 Hz | ≈13.58 ms |

  Audio lane: execution mean ≈1.58 ms, handoff mean ≈2.31 ms. No epoch-cache complexity without new evidence.
- **VZ-07 sleep slicing:** no demonstrated problem on a protected timing path.

## Closed (recorded in 06 §Considered and rejected)

- **LC-01 — narrowly, the feared post-replacement gen-2 stall.** After a real runtime replacement, 11,692 objects are
  unfrozen and a gen-2 pass takes 1.2 ms (vs 90.7 ms unfrozen). `gc.unfreeze()` frees only 748 retired objects, 0 MB.
  The soak had no gen-2 stall. It did record one 19.53 ms gen-1 collection, so this closure does not claim GC can
  never stall.
- **PR-05:** the soak had 1,803 repeated revisions in 64,150 draws (2.81%), matching the idle 2.9% (≈5.8 ms/s).
  Removing them means changing the custom-render composition (Compositor_Architecture §6).
- **PW-06:** 0.31 ms per `threading.Timer` cycle every 3 s ≈ 0.1 ms/s, and OS timer handles held at ≈13–14 through
  the soak. Replacing it would risk R-30 exit behaviour.
- **Prefetch double batch (22:58:31):** `[CACHE] Protected near-future cache keys requested=2 retained=1`. This is
  benign lookahead catch-up.
