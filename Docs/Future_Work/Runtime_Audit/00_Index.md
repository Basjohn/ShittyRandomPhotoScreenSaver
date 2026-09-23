# Runtime Audit 2026-09-22 — Index, Register and Sequencing

**Status:** the implementation queue was accepted on 2026-09-23 (operator run 19:29–19:35 with `--frame-trace`, earlier physical runs and automated bars) and PR-04's native texture handoff on 2026-09-24 (operator run 23:47 with `--frame-trace` plus a frozen-build probe); see §Accepted. Only the watched and parked items below remain. Items leave this folder when they are implemented and accepted (the durable rule moves to its owning contract/guardrail, the failed-method lesson to `Docs/Historical_Bugs/`), or when they are closed (recorded in 06 §Considered and rejected so they are not re-audited). The folder is historicalised once the watched and parked items are closed or moved to a backlog. This is a live checklist, not a changelog.

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

## Register (open)

| ID | Finding | Pri | Reward | Risk | Decision / status | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| PW-04 | `FeedRowsModel.replace_rows` resets the whole list when one row changes | P3 | R1 | Low | **Watch** — FEEDS Custom 2–4 | source + soak |
| PR-02 | Ordinary runtime connects `frameSwapped` to a queued per-frame GUI Python callback (≈0.5 ms/s) | P2 | R1 | Low–Med | **Park** (with DC-04) | source + soak |
| PR-01 memo | Presentation re-resolve per publication (47.6 µs) | P3 | R1 | Low | **Park** | measured |
| PR-07 | `QuickSceneFactory` compiles every family QML component at startup (≈0.2–0.3 s dev) | P3 | R1 | Low | **Park** | measured |
| ST-01/02 | `DisplayManager` 4.9k-line owner; very large files | P3 | R1 | Medium | **Park** (move-only on a touched seam) | source |
| VZ-05 cache | Epoch cache for config-static render extras (17–117 µs/tick left) | P3 | R1 | Medium | **Park** | soak |
| VZ-07 | Logical runtime sleeps in 4 ms slices | P3 | R1 | Low | **Park** | source |
| DC-04 | Guardrail vs source conflict: per-frame `frameSwapped` Python callback (PR-02) | P3 | R1 | Low | documented; fixed only when PR-02 reopens | source |

Closed: LC-01, PR-05, PW-06, PW-03 Media and the prefetch double batch (06 §Considered and rejected).

## Accepted (2026-09-23)

Each row keeps only what traces a future issue back to the change.

| ID | Change | Commits | Durable home / bar | Closing evidence |
| --- | --- | --- | --- | --- |
| TX-01 | Fracture geometry prepared on COMPUTE; a render thread takes the in-flight preparation instead of rebuilding it; vectorised prism builder | `da2de88e`, `50f38551` | `tests/test_transition_run_geometry.py` | 19:29 trace exposed duplicate builds (Glass first frames 102–134 ms / 40–60 ms); fixed with a bar that fails on the old path; Tiles run clean. The 23:47 trace showed the preparation never matched in production (R-95: monitor-rect vs R-63 window aspect); fixed 2026-09-24 |
| TX-02 | Random rotation is session memory, never a Settings write | `e3c6ce82` | R-92; `tests/test_transition_distribution.py` | run: Random rotations with no Settings writes |
| LC-05 | Context-menu entries refresh before the menu opens | `ca86367c` | context-menu entry test | run: six context-menu actions |
| LC-06 | Canonical defaults built once per profile | `f84439f2` | defaults tests | run: two Settings replacements, three generations |
| PR-01 | Steady equal publications skip the QML shell projection | `3598c8fb` | publication tests | run: mode switches, startup/replacement fades; operator: no regression |
| PR-03 | Background telemetry notes without dataclass `replace()` | `e80336c9` | telemetry tests | trace: background render normal |
| PR-04 A | Opaque wallpaper pixels at both processing owners; premultiplied native label | `8541cb82` | Guardrails §Wallpaper pixel opacity; `tests/test_wallpaper_opaque_pixels.py` | operator: no black flash; transparent sources are an automated contract |
| PR-04 B | Native `QImage` wraps the presentation bytes (no deep copy) | `48b11565` | `tests/test_qtquick_native_image_lifetime.py` | trace: first post-transition sync 0.33–1.53 ms (was ≈4.6 ms) |
| PR-04 native | The retained background adopts the transition's destination GL texture through Qt's exported `QSGOpenGLTexture::fromNative` (ctypes on the loaded `Qt6Quick`; no PySide release binds it, no compiled helper); the texture host stays the only owner/deleter (lend/reclaim) and the next run reuses it as its source | `e744d119` | Guardrails §Presentation texture ownership; `tests/test_qtquick_native_texture_handoff.py`, `tests/test_qtquick_native_texture_handoff_gl.py` (real GL; six reintroduced ownership faults each caught) | 23:47 trace: first cycle after a transition end on the 4K Visualizer display 3.3–11.1 ms (median ≈7; was median 19.3), 26 of 26 completed runs adopted, no fallback; frozen Nuitka probe: adoption, deletion by identity, pixel parity with Stage B, GL state untouched, one `qt6quick.dll` |
| PW-01 | Timeline-only Media refreshes reuse the held artwork | `aa57c284` | Media refresh tests | run: `artwork_reused` 43 of 47 event refreshes, track changes |
| PW-02 | Media refresh and commands on a dedicated `media` lane | `a8e38012`, `468ec0cc` | Spec §Media lane; R-93 | operator offline/network-stress run |
| PW-03 Clock | Clock ticks notify only the time epoch | `e8ef729c` | clock presentation tests | run: clock on screen throughout |
| PW-05 | `single_shot` returns a cancellation handle; Feed/Games-You-Follow deadlines in the generation registry | `1f60f0c8` | `tests/test_single_shot_handle.py` (incl. a due deadline firing once) | automated |
| VZ-01 | Paused idle waveform synthesized only for Oscilloscope | `ccb9c615` | `tests/test_visualizer_idle_waveform_demand.py` (all six modes) | automated |
| VZ-03 | Tick phase recording only under `--perf` | `17fc2276` | `tests/test_visualizer_tick_phase_diagnostics.py` | automated |
| VZ-04 | Waveform samples only for sample-consuming modes | `a9878340` | `mode_capabilities.consumes_waveform_samples`; payload tests | BTF Layer 4 PASS (Bubble, Oscilloscope, Spectrum, Dev Curve, Voxel Sphere); Sine's quieter-level pulse accepted as authored behaviour |
| VZ-05 | Render fields frozen once per tick | `99a94a21` | tick tests | soak |

Defects this audit found are recorded as R-89 (cross-file native abort), R-90 (Core Audio double release), R-91
(orphaned workers), R-92 (TX-02), R-93 (PW-02) and R-95 (TX-01's prepared geometry never matched under R-63 overscan; found in the 23:47 trace).

## Sequencing

No implementation slice remains; watched and parked items keep their triggers (08).

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
