# Runtime Audit 2026-09-22 — Index, Register and Sequencing

**Status:** candidate queue. **Nothing here is admitted work** until the operator promotes an item into
`Current_Plan.md`. Items leave this folder when they are implemented and accepted (the durable rule moves to
its owning contract/guardrail, the failed-method lesson to `Docs/Historical_Bugs/`), or when they are rejected.
Delete closed items; this is a live checklist, not a changelog.

**Baseline audited:** `main` at `2ba9e15d` (5.0.5 FEEDS WORK v2). Performance reference remains CHK26 /
`a0bf70932c` (Index.md). Every claim below cites exact current source; numbers are measured unless marked
*estimate*.

## Documents

| Doc | Scope |
| --- | --- |
| [01_Presentation_And_Frame_Demand.md](01_Presentation_And_Frame_Demand.md) | Quick scene, GUI↔render sync, retained background, visualizer presentation commit, frame demand |
| [02_Visualizer_Pipeline.md](02_Visualizer_Pipeline.md) | BeatEngine tick, logical capture/publication, idle synthesis, authored clock |
| [03_Images_And_Transitions.md](03_Images_And_Transitions.md) | Transition first-frame work, Random selection persistence, image publication |
| [04_Providers_Widgets_And_Threads.md](04_Providers_Widgets_And_Threads.md) | Media/GSMTC, shared IO pool, family model notify granularity, Feed model, timer helpers, supervisor |
| [05_Lifecycle_GC_And_Durability.md](05_Lifecycle_GC_And_Durability.md) | GC freeze scope, caller-dead runtime residue, diagnostic oracles, context menu, verified-healthy seams |
| [06_Structure_Docs_And_Expandability.md](06_Structure_Docs_And_Expandability.md) | God-object owners, doc/source contradictions, considered-and-rejected list |
| [07_Historical_Bug_Cross_Audit.md](07_Historical_Bug_Cross_Audit.md) | This audit audited against every relevant historical bug; constraints each item inherits |

## Method

```text
governing docs (Index/Plan/Spec/Contracts/Guardrails + focused guardrails, R-87 chronology)
-> exact source of every hot or lifecycle-critical runtime owner
-> existing evidence (local 2026-09-22 dev run logs; built-in PERF_HUD/MEDIA_EVENT/GC_POLICY lines)
-> offline micro-benchmarks of the exact functions on the audited tree (idle dev machine; installed/heavy-load
   numbers will be larger)
-> historical-bug cross-audit (07) before any recommendation was finalized
```

No production code was changed by this audit.

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

## Register

| ID | Finding | Pri | Reward | Risk | Evidence |
| --- | --- | --- | --- | --- | --- |
| TX-01 | `[~]` 3D transitions built fracture/mesh geometry in Python on the render thread at the first transition frame (Glass default ≈25 ms; Crumble ≈11 ms; 128-piece Crumble ≈40 ms); now packed 3× faster and prepared on COMPUTE at batch resolution — frame-trace + physical check open | P1 | R3 | Low | measured |
| TX-02 | `[~]` Random rotation used persisted Settings as scratch space (2–6 `set()` + `save()` per rotation) **and overwrote the user-authored Slide/Wipe `direction`**; now session memory handed to the batch resolver — physical check + direction-semantics decision open | P1 | R2 | Medium | source + measured 1.9 ms idle |
| PR-01 | `[~]` Every visualizer publication (~90 Hz) re-resolves presentation (≈49 µs) and rewrote ~25 QML root properties + 3 QColors even when nothing changed; no-op projection now skipped (20.4 → 4.0 µs/publication idle) — resolve memo and frame-trace/physical checks open | P1 | R2 | Low | measured + CHK27 |
| LC-06 | `[~]` `get_default_settings()` rebuilt all canonical defaults (≈5.5 ms) per call on context-menu open (×2), image batches and per widget × display construction; now built once per profile, hot paths read sections — physical check open | P1 | R2 | Low | measured |
| PW-02 | Media refresh (the Visualizer's play/pause truth) shares the generic 4-worker IO pool with every network provider and RSS; `requests` timeouts do not bound DNS | P1 | R3 | Medium | source; needs fault injection |
| VZ-01 | While paused, the BeatEngine synthesizes a 256-sample sine waveform every tick for every mode (≈178 µs/tick ≈ 16 ms/s pure Python); only the Oscilloscope renderer reads the samples | P2 | R2 | Medium | measured |
| PW-01 | Every GSMTC timeline edge re-reads and re-hashes the whole album-art thumbnail (local run: 121 event refreshes, 85 thumbnail reads, 2 real artwork changes in 8.5 min) | P2 | R2 | Low | log-measured |
| PR-03 | `[~]` Custom background node replaced a 44-field frozen telemetry dataclass ~4× per transition frame on the render thread; now field updates + snapshot built on read (29.6 → 2.2 µs per frame idle) — frame-trace open | P2 | R1–R2 | Low | measured |
| PR-02 | Ordinary runtime connects `frameSwapped` to a queued per-frame GUI Python callback that republishes unchanged readiness | P2 | R1 | Low–Med | source + measured |
| PR-04 | Transition finalization deep-copies the 33 MB destination (`QImage.copy()`) during blocked sync and re-uploads it for the native branch although the custom node already uploaded it | P2 | R2 *est* | Medium | source; needs frame-trace |
| LC-01 | `gc.freeze()` runs once for generation 0 only; every replacement generation loses the gen-2 protection and retired gen-0 cyclic graph stays pinned until exit | P2 | R2 *est* | Medium | source; fold into R-84 exit run |
| PW-05 | Feed and Games-You-Follow each hand-roll parentless deadline `QTimer`s because `ThreadManager.single_shot` returns no cancel handle | P2 | R1 | Low | source |
| VZ-05 | Config-static render extras (~30–90 keys) are re-collected and re-frozen every tick for every mode | P2 | R1–R2 *est* | Medium | source; measure |
| VZ-03 | Tick phase breakdown (closure + dict + 9 timestamps) is recorded every tick though only read when perf-gated | P3 | R1 | Low | source |
| VZ-04 | Every mode's logical frame copies and validates the 256-sample waveform (≈34 µs/tick) | P3 | R1 | Low–Med | measured |
| PW-03 | Family models notify 30–67 properties through one `stateChanged` (Clock 1 Hz, Media per event) — the single-notify shape R-84 fixed for the context menu | P3 | R1 | Low | source |
| PW-04 | `FeedRowsModel.replace_rows` resets the whole list on any change; other families update in place | P3 | R1 | Low | source |
| PW-06 | `ProcessSupervisor` heartbeat spawns a new OS thread every 3 s (`threading.Timer` re-armed per check) | P3 | R1 | Low | source |
| PR-07 | `QuickSceneFactory` compiles every family QML component at startup (≈290 ms of 517 ms dev compile), active or not | P3 | R1 | Low | measured |
| LC-04 | Recurring-timer gap oracle is not reset on stop/rebase and its classifier still names retired QWidget owners (R-87 "172,987 ms `unknown_ui_thread_stall`" anomaly) | P3 | R1 | Low | source |
| LC-05 | Context-menu entries are refreshed *after* the menu is shown; operator-reported "2 QImage tasks per menu open" not yet reproduced | P3 | R1 | Low | source; open question |
| PR-05 | Any unrelated scene frame (widget animation, transition, menu) re-runs the Python visualizer render callback; local idle windows show 110–116 draws/s vs ~90 revisions/s | P3 | ? | High | log; architecture — operator only |
| ST-01 | `DisplayManager` is a 4.9k-line owner of ~12 concerns | P3 | R1 | Medium | source |
| DC-03..04 | Doc/source contradictions (retired-owner comments in the timer-gap classifier; `frameSwapped` guardrail vs source) | P3 | R1 | Low | source |

Parked / rejected candidates are listed in 06 §Considered and rejected so they are not re-audited.

## Recommended sequencing

Each wave is independently committable. Nothing below overrides `Current_Plan.md` ordering.

- [~] **Wave B (admitted) — measured runtime wins and the one authority defect:** TX-02 → LC-06 → TX-01 → PR-01 →
  PR-03 → PW-01 → VZ-01. Each is its own checkpoint with its acceptance lane (doc sections list the exact bar).
- [ ] **Wave C — evidence first, then decide:** PW-02 (IO starvation fault injection), LC-01 (piggy-back on the
  pending R-84 3–5-cycle Settings churn run: grep `[PERF][GC_POLICY] generation=2`), PR-04 (`--frame-trace` around
  one transition end), VZ-05 (per-tick capture timing already recorded in `_tick_phase_ms`).
- [ ] **Wave D — structure/durability:** PW-05 (cancellable `single_shot` handle; do before FEEDS Custom 2–4),
  PW-04, PW-03, PW-06, LC-04, LC-05, PR-07, ST-01.
- [ ] **Operator-only:** PR-05 (would change the selected custom-render primitive's composition; see
  Compositor_Architecture §6) and the parked VZ-07.

## Acceptance lanes used by this audit

| Lane | Use |
| --- | --- |
| Focused pytest named in each item | contract/regression bar |
| `--frame-trace` + `tools/frame_trace_report.py` | publication→draw, render-entry, background/transition stages |
| PERF_HUD (`viz_draw_fps` vs `viz_revision_hz`, `viz_age_ms`, `dt_max_ms`) | steady/transition freshness and redraw counts |
| `[MEDIA_EVENT] summary`, `[GC_POLICY]`, `[LIFECYCLE_BARRIER]`, `[LOG_QUEUE]` lines | owner-level counts already emitted |
| BTF active-music lane (Bubble_Temporal_Fidelity §18 Layer 4) | any item touching visualizer timing/payload (VZ-*, PR-01) |
| Installed D1-heavy + mixed-refresh operator review | final neutral-or-better vs CHK26 |

## Operator note captured during the audit

> "Every time the context menu is opened 2 new QImage tasks occur in the logs."

Tracked as LC-05 (05 §LC-05) with what was checked and what evidence would pin it down.
