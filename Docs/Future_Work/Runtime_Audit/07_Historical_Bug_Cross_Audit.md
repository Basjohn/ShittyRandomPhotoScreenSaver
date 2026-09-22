# 07 — Historical Bug Cross-Audit (the audit, audited)

Every recommendation in 01–06 was checked against the historical records it could revive. Records read in full
for this pass: R-03, R-07, R-22, A-06, R-24, R-27, R-30, R-33, R-47, R-50, R-51, R-53, R-60, R-61B, R-62, R-63,
R-65, R-66, R-68, R-71, R-72, R-77, R-80, R-84, R-87, R-88, U-05 (head), U-09, U-10 (head),
Defaults_Canonical_Schema_Dedup; plus the guardrail-embedded summaries of R-54, R-69, R-76, R-86.

Verdicts: **Safe** (no plausible revival path) · **Safe with constraints** (constraints are now written into the
item) · **Blocked** (needs operator/architecture decision before any work).

## Recommendations changed by this cross-audit

| Item | Original idea | Changed because | Now |
| --- | --- | --- | --- |
| PR-01 | cache the last applied presentation in the scene controller | U-09 / R-68: two geometry authorities poisoned CUSTOM | compare against the retained item's own record; no parallel cache |
| PR-01 | skip the present request when presentation is unchanged | R-62 / R-61B / R-27: deferring or coalescing visible state made Bubble late and flat | `request_present()` stays once per accepted publication; only no-op property writes are skipped |
| VZ-01 | skip idle synthesis entirely for non-line modes | R-87 CHK12: line-mode readiness keys on waveform *generation* | generation keeps advancing every paused tick; only sample synthesis becomes demand-driven |
| PR-02 | defer readiness observation until needed | R-63: deferring first show made startup worse (image→black→image) | first-show/reveal ordering untouched; observer re-arms on readiness-changing edges; surface probes kept |
| PW-01 | throttle Media refreshes on timeline storms | R-66: event ownership must feed the one owner; no cadence substitution | refresh count unchanged; only the query *scope* narrows on timeline-only edges |
| PW-06 | non-daemon persistent heartbeat thread | R-30: an owned timer/loop kept Python alive after exit | must never keep the process alive; daemon semantics unless join is proven on every exit path |
| LC-01 | dedicated GC soak | R-84: "last handle-discovery run"; no more discovery soaks | evidence read from the already-requested R-84 3–5-cycle Settings run |
| TX-02 | repair clobbered Slide/Wipe directions in existing profiles | R-33 / Defaults dedup: never rewrite installed profiles implicitly | stop the writes; no automatic profile repair; release-note only |
| LC-02 | delete the sync methods | R-77: file/method deadness must be proven as a caller transaction | remove methods + fields + imports + `utils/lockfree` + test in one commit with import-closure proof |
| TX-01 | global geometry cache | R-51: shared GL handles gave two contexts one deletion identity | precompute **CPU bytes** only; VAO/VBO stay per render context |

## Item-by-item verdicts

| Item | Relevant records | Revival path considered | Verdict / constraint |
| --- | --- | --- | --- |
| TX-01 | R-51, R-78, R-87, Transition checklist | shared GL ownership; changed fracture output; transition borrowing visualizer cadence | Safe with constraints: byte-identical geometry per seed (existing oracles); per-context GL; no new clock |
| TX-02 | R-65, R-33, Defaults dedup, R-06 | admission before mutation; fail-closed empty pool; implicit profile rewrite | Safe with constraints: batch spec carries the choice; empty pool withholds destination loudly; operator decides direction semantics |
| LC-06 | R-84, R-24, Defaults authority tests | menu-time broad invalidation (R-24); defaults authority drift | Safe: pure memoization of an immutable result; callers still get private copies |
| PR-01 | R-62, R-61B, R-27, U-09, R-68, R-69, R-73, R-74 | delayed presentation; second geometry authority; response compression; skipped shadow updates | Safe with constraints: equality covers shell style (shadow fields live in the record), fades/transitions still project, CUSTOM path unchanged, presentation values never altered (R-69 untouched) |
| PW-02 | R-66, R-41, R-83, R-29, R-40, U-05 | Media polling fallback; unowned threads; provider cadence changes; media-key routing | Safe with constraints: only the executor owner changes (existing affinity lane), no poll, key capture/dispatch untouched (U-05 is open) |
| VZ-01 | R-03, R-87 CHK12, U-10, BTF | dead/flat paused Sine; stale line-mode reveal; Oscilloscope contract drift | Safe with constraints: identical phase math and sequences for Osc; generation semantics unchanged; active-music BTF lane |
| PW-01 | R-66, ArtworkFadeImage contract | polling; missed artwork; unchanged re-upload | Safe with constraints: full query on properties/playback/activation/reconcile/wake/command; keep reading until the track has artwork |
| PR-03 | R-87 retained pixel oracles | diagnostic oracle drift | Safe: snapshot schema and pixel-capture paths unchanged |
| PR-02 | R-63, R-07, R-27 | reveal regression; black flash; added UI work | Safe with constraints (above); it removes UI work |
| PR-04 | R-60, R-50, R-52, R-63, CHK21 | texture identity rekey; retained pins; shared-memory lifetime; black flash; losing native steady ownership | Evidence first; any repair keeps one DPR owner, byte budgets, owner-context release and native steady presentation |
| VZ-02 | R-47, env-flag policy | diagnostic code on the frame path breaking pushes | Safe: deletion only |
| LC-01 | R-53, R-71, R-84 | forced collection; threshold tuning; extra soak | Safe with constraints: no `gc.collect`, no thresholds; evidence from R-84 run |
| LC-02 | R-77, R-27 | independent deletion breaking imports | Safe with constraints (transaction removal) |
| PW-05 | R-65, R-27, R-30 | generation-less delayed claims; rescue timers; timer ownership at exit | Safe: moves timers *into* the generation-owned registry |
| VZ-05 | R-22, A-06, R-71 | cross-activation bleed; shared mutable snapshot | Safe with constraints: epoch reset inside the activation transaction; immutable reuse only; poison tests |
| VZ-03 | R-72, instrumentation opt-in rule | tooling in production | Safe |
| VZ-04 | U-10, R-22 | Oscilloscope contract; payload bleed | Safe with constraints: Oscilloscope payload unchanged; per-mode consumer bar |
| PW-03 | R-84, R-88 | notify changes making Edit role arrays depend on moving values | Safe with constraints: `customEditableChildRoles` stays independent of the new signals |
| PW-04 | R-88 | delegate identity churn | Safe: it reduces delegate churn |
| PW-06 | R-30, R-84 | exit hang; handle churn | Safe with constraints (above) |
| PR-06 | R-47 | logging code raising on the frame path | Safe with constraints: the rate limiter must not raise; `note_error` unchanged |
| PR-07 | R-07, import dormancy | startup reveal ordering; eager family imports | Safe: compile still completes before the owning window is shown |
| LC-03 | R-30, R-27, R-77 | timer ownership at exit | Safe: removes an idle owner |
| LC-04 | R-80, R-87 | rolling-history contamination | Safe: resets epochs; diagnostics only |
| LC-05 | R-84, R-24, U-05 | menu rebuild tails; broad invalidation; focus/Ctrl-halo | Safe with constraints: single-menu enforcement and focus/Ctrl semantics unchanged |
| PR-05 | R-87 CHK5/CHK10, Compositor_Architecture §6 | second custom-render primitive; composite pass | **Blocked**: operator architecture decision |
| ST-01 / ST-02 | R-26, U-09, R-79, R-85, R-53, R-88, R-23 | routing/topology/Edit behaviour drift during refactor | Safe only as move-only extractions with existing tests unchanged |
| DC-01..04 | Documentation_Maintenance | deleting a product requirement to match a bug | Safe: DC-01 is a superseded design; DC-04 fixes source, not the guardrail |

## Historical classes checked with no audit item touching them

- Settings UI/theme (R-01, R-09, R-18, R-28, R-32, R-43, R-56, R-61, U-04): no Settings UI change proposed.
- Visualizer preset/persistence authority (R-04, R-05, R-06, R-11, R-12, R-13, R-58): no preset path touched
  (TX-02 touches transitions only).
- Retired Blob/Goo (R-14, R-17, R-36, R-46, A-02, A-05): no revival.
- Viewport/response scaling (R-69, R-76, R-55, R-25, U-07, U-02): no presentation value, smoothing or DSP change is
  proposed; PR-01 only skips writes of *equal* values.
- Bubble cadence (R-54, BTF): no gate, token clock or batching introduced anywhere.
- Presenter/pacing (R-86, R-87 false trails): no swap-interval, pacer, `frameSwapped` feedback, GIL-switch, priority
  or fence removal proposed; PR-05 is explicitly blocked.
- Helper/URL handoff (R-02): ST-01's link router extraction is move-only; queue-admission authority unchanged.
- Topology (R-79, R-85, R-26): no topology behaviour change proposed.

## Residual risk statement

The only items with Medium risk that are also P1 are TX-02 (product-semantics decision on direction honouring) and
PW-02 (lane ownership change on the Media path). Both carry an explicit evidence or decision step before
implementation. No item removes a fence, lowers cadence, adds a timer/poller/thread/clock, or adds ordinary-runtime
instrumentation.
