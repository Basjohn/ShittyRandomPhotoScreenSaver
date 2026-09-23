# Runtime Audit 2026-09-22 — Index, Register and Sequencing

**Status:** operator decisions recorded 2026-09-23 (08). `Current_Plan.md` owns the admitted implementation queue and
its order; this folder holds the evidence, decisions and acceptance bars. Items leave this folder when they are
implemented and accepted (the durable rule moves to its owning contract/guardrail, the failed-method lesson to
`Docs/Historical_Bugs/`), or when they are closed (recorded in 06 §Considered and rejected so they are not re-audited).
This is a live checklist, not a changelog.

**Baseline audited:** `main` at `2ba9e15d` (5.0.5 FEEDS WORK v2). Performance reference remains CHK26 /
`a0bf70932c` (Index.md). Every claim below cites exact current source; numbers are measured unless marked
*estimate*.

## Documents

| Doc | Scope |
| --- | --- |
| [01_Presentation_And_Frame_Demand.md](01_Presentation_And_Frame_Demand.md) | Quick scene, GUI↔render sync, retained background, visualizer presentation commit, frame demand |
| [02_Visualizer_Pipeline.md](02_Visualizer_Pipeline.md) | BeatEngine tick, logical capture/publication, idle synthesis, authored clock |
| [03_Images_And_Transitions.md](03_Images_And_Transitions.md) | Transition first-frame work, Random selection persistence, image publication |
| [04_Providers_Widgets_And_Threads.md](04_Providers_Widgets_And_Threads.md) | Media/GSMTC, shared IO pool, family model notify granularity, Feed model, timer helpers |
| [05_Lifecycle_GC_And_Durability.md](05_Lifecycle_GC_And_Durability.md) | Caller-dead runtime residue, defaults, context menu, verified-healthy seams |
| [06_Structure_Docs_And_Expandability.md](06_Structure_Docs_And_Expandability.md) | God-object owners, doc/source contradictions, considered-and-rejected (incl. closed items) |
| [07_Historical_Bug_Cross_Audit.md](07_Historical_Bug_Cross_Audit.md) | This audit audited against every relevant historical bug; constraints each item inherits |
| [08_Open_Items_Research.md](08_Open_Items_Research.md) | Evidence sources (incl. the 2026-09-23 D1 soak), operator decision and remaining bar for every open item |

## Method

```text
governing docs (Index/Plan/Spec/Contracts/Guardrails + focused guardrails, R-87 chronology)
-> exact source of every hot or lifecycle-critical runtime owner
-> existing evidence (local 2026-09-22 dev run logs; built-in PERF_HUD/MEDIA_EVENT/GC_POLICY lines)
-> offline micro-benchmarks of the exact functions on the audited tree (idle dev machine; installed/heavy-load
   numbers will be larger)
-> historical-bug cross-audit (07) before any recommendation was finalized
-> operator evidence runs and the 2026-09-23 D1 heavy-load diagnostic soak (08 §Evidence sources)
```

The audit pass itself changed no production code; items implemented since carry `[~]`.

## Protected invariants (every item must be neutral or positive on all of these)

- Visualizer fidelity/reactivity, BTF, R-69; ~90 Hz authored logical cadence; newest-state semantics.
- Latency: source/snapshot age, state→paint, publication→draw (CHK26 GOLDEN references in R-87).
- Visible functionality and fidelity (pixels, authored transitions, fades, CUSTOM behaviour).
- Visualizer fps/cadence on 60 Hz and high-refresh displays; mixed-refresh behaviour.
- R-63 non-exact-cover geometry; `swapInterval=0`; one QQuickWindow per display; no Python display pacer; no
  `frameSwapped → requestUpdate()` loop; no env flags; diagnostics strictly opt-in.

## Scales

**Priority** — **P0** correctness/lifecycle defect with visible or crash risk · **P1** measured, owner-local,
protected-neutral win on latency/tails/visible hitch or a durability risk to protected behaviour · **P2**
measured waste/churn, durability or policy violation with low risk · **P3** hygiene, structure, startup-only, or
needs evidence before it is worth doing.

**Reward** — **R3** removes a visible-edge stall ≥10 ms or protects play/pause/reactivity truth · **R2** removes
≥5 ms/s steady thread time or a rare few-ms stall · **R1** <5 ms/s, startup-only, structural or diagnostic.

**Risk** — relative to the protected invariants above: Low / Medium / High.

**Status boxes** — `[ ]` not started · `[~]` implemented, awaiting validation (Guardrails rule) · `[x]` accepted.

**Decisions** — see 08's decision key (Do · Do with care · Gated · Watch · Park · Close).

## Register

| ID | Finding | Pri | Reward | Risk | Decision / status | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| TX-01 | `[~]` 3D transitions built fracture/mesh geometry in Python on the render thread at the first transition frame (Glass default ≈25 ms; Crumble ≈11 ms; 128-piece Crumble ≈40 ms); now packed 3× faster and prepared on COMPUTE at batch resolution | P1 | R3 | Low | landed; Glass/Tiles frame-trace + physical check open (soak: Crumble starts no longer show the old class) | measured + soak |
| TX-02 | `[~]` Random rotation used persisted Settings as scratch space (2–6 `set()` + `save()` per rotation) **and overwrote the user-authored Slide/Wipe `direction`**; now session memory handed to the batch resolver (Random keeps randomizing direction, operator 2026-09-23) | P1 | R2 | Medium | landed; physical check open | source + measured 1.9 ms idle |
| PR-01 | `[~]` Every visualizer publication (~90 Hz) re-resolved presentation (≈49 µs) and rewrote ~25 QML root properties + 3 QColors even when nothing changed; no-op projection now skipped (20.4 → 4.0 µs/publication idle) | P1 | R2 | Low | landed; physical check open; resolve memo **Park** | measured + CHK27 + soak |
| LC-06 | `[~]` `get_default_settings()` rebuilt all canonical defaults (≈5.5 ms) per call on context-menu open (×2), image batches and per widget × display construction; now built once per profile, hot paths read sections | P1 | R2 | Low | landed; physical check open | measured |
| PW-02 | Media refresh (play/pause truth) and transport commands share the FIFO 4-worker IO pool with network work; fault injection proves the queueing; the soak shows ≈1.9 s pool queue wait in the startup burst (not attributed by category) | P1 | R3 | Medium | **Do with care** — Media-only lane admitted (not the WinRT observation lane) | fault injection + soak |
| PR-04 | First Quick cycle after each transition end: ≈24.8 ms on the 4K Visualizer display (operator trace), 26.6–90.6 ms across ten soak endings; Qt's straight-alpha conversion is 8.12 ms of the idle case | P1 | R3 | Medium | Stage A **Do with care** (partial mitigation); Stage B **Gated** on a Qt lifetime test | frame traces + probe + soak |
| VZ-01 | `[~]` While paused, the BeatEngine synthesized a 256-sample sine waveform every tick for every mode; now only when Oscilloscope is active (paused tick 150.6 → 36.4 µs for other modes) | P2 | R2 | Medium | landed; physical paused/edge check open | measured |
| PW-01 | `[~]` Every GSMTC timeline edge re-read the whole album-art thumbnail; timeline-only refreshes now reuse held artwork for the same track (soak: `artwork_reused=1196` of 1,222 event refreshes) | P2 | R2 | Low | landed; visible artwork checks open | log-measured + soak |
| PR-03 | `[~]` Custom background node replaced a 44-field frozen telemetry dataclass ~4× per transition frame on the render thread; now field updates + snapshot built on read (29.6 → 2.2 µs per frame idle) | P2 | R1–R2 | Low | landed; frame-trace open | measured |
| PW-05 | `[~]` Feed and Games-You-Follow hand-rolled parentless deadline `QTimer`s because `ThreadManager.single_shot` returned no cancel handle; it now returns a `SingleShotHandle` and both use the registry | P2 | R1 | Low | landed; physical check open | source |
| VZ-05 | `[~]` Capture re-froze every render field twice per tick; single-freeze landed (2.4× faster) | P2 | R1–R2 | Low | landed; epoch cache **Park** | measured + soak |
| PR-02 | Ordinary runtime connects `frameSwapped` to a queued per-frame GUI Python callback that republishes unchanged readiness (≈0.5 ms/s in the soak) | P2 | R1 | Low–Med | **Park** (with DC-04) | source + measured + soak |
| VZ-03 | `[~]` Tick phase breakdown (closure + dict + 9 timestamps) was recorded every tick though only read when perf-gated; now built only with `--perf` | P3 | R1 | Low | landed | source + measured |
| VZ-04 | Every mode's logical frame copies and validates the 256-sample waveform (38.4 µs/tick) | P3 | R1 | Low–Med | **Do with care** (per-mode consumer bar, BTF lane) | measured |
| PW-03 | Family models notify 30–67 properties through one `stateChanged`; `[~]` Clock now splits a per-second `timeChanged` from its config/style epoch (tick 0.6 ms → 49 µs) | P3 | R1 | Low | Clock landed, physical check open; Media **Watch** | measured + soak |
| LC-05 | `[~]` Context-menu entries were refreshed *after* the menu was shown (6.6 ms median); now refreshed before `open_at()` | P3 | R1 | Low | landed; physical check open | source + measured |
| PW-04 | `FeedRowsModel.replace_rows` skips equal rows but resets the whole list when one row changes | P3 | R1 | Low | **Watch** — FEEDS Custom 2–4 | source + soak |
| PR-07 | `QuickSceneFactory` compiles every family QML component at startup (≈0.2–0.3 s dev), active or not | P3 | R1 | Low | **Park** | measured |
| ST-01 | `DisplayManager` is a 4.9k-line owner of ~12 concerns | P3 | R1 | Medium | **Park** (move-only on a touched seam) | source |
| DC-04 | Guardrail vs source conflict: per-frame `frameSwapped` Python callback (PR-02) | P3 | R1 | Low | documented; fixed only when PR-02 reopens | source |

Closed: LC-01, PR-05, PW-06 and the prefetch double batch (08 §Closed; 06 §Considered and rejected). Crumble and Melt
control rework is transition product work (`Docs/Future_Work/Transition_Expansion.md`), not a register item.

## Sequencing

`Current_Plan.md` (runtime audit section) owns the order of the admitted slices. Each slice is its own checkpoint with
the bars named in 08. Wave B `[~]` items stay in the plan until their physical checks pass.

## Acceptance lanes used by this audit

| Lane | Use |
| --- | --- |
| Focused pytest named in each item | contract/regression bar |
| `--frame-trace` + `tools/frame_trace_report.py` | publication→draw, render-entry, background/transition stages |
| PERF_HUD (`viz_draw_fps` vs `viz_revision_hz`, `viz_age_ms`, `dt_max_ms`) | steady/transition freshness and redraw counts |
| `[MEDIA_EVENT] summary`, `[GC_POLICY]`, `[LIFECYCLE_BARRIER]`, `[LOG_QUEUE]` lines; `--usage` `tm_delivery`/`tm_categories` | owner-level counts already emitted |
| BTF active-music lane (Bubble_Temporal_Fidelity §18 Layer 4) | any item touching visualizer timing/payload (VZ-*, PR-01) |
| D1 heavy-load diagnostic soak (08 §Evidence sources) | event-correlated evidence only; never raw global FPS/CPU/event-loop maxima |
| Installed D1-heavy + mixed-refresh operator review | final neutral-or-better vs CHK26 |
