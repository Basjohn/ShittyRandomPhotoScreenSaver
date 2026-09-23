# 08 — Open Items: Evidence, Decisions and Remaining Action

Every item still open after Waves A–C: its evidence, the operator decision of 2026-09-23 and the bar or prerequisite
that remains. Item detail lives in 01–05; `Current_Plan.md` owns the implementation order. Crumble and Melt control
rework is transition product work owned by `Docs/Future_Work/Transition_Expansion.md`, not runtime cleanup.

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
| LC-05 menu refresh after show | 6.6 ms median (15.5 ms first) rebuild while visible | **Do** — `[~]` landed | physical check |
| VZ-03 phase recording | 4.2 µs/tick of diagnostic work at rest | **Do** — `[~]` landed | next `--perf` slow tick |
| PW-05 cancellable `single_shot` | two hand-rolled parentless deadline `QTimer`s | **Do** — `[~]` landed | physical check |
| PW-03 Clock notify | 0.69–0.77 ms GUI per 1 Hz emit per clock; live tick 597–618 → 48–50 µs after the split | **Do with care** — `[~]` landed | physical check |
| VZ-04 waveform payload | 38.4 µs/tick for modes that never draw samples | **Do with care** — `[~]` landed | BTF Layer 4 active-music review |
| PR-04 Stage A — opaque pixels + premultiplied label | soak: 10 transition ends 26.6–90.6 ms; Qt conversion 8.12 → 0.15 ms idle | **Do with care** — `[~]` landed, partial mitigation | post-change frame trace of the whole cycle |
| PR-04 Stage B — drop `.copy()` | ≈3–4.5 ms sync | **Gated** | Qt/PySide lifetime test first |
| Crumble complexity + debris | irregularity 0.31 → 0.38 across the range; debris ≤0.22% of pixels | **Product rework** | geometry rework, not a remap |
| Melt gloss / detail | gloss ≤3/255 in the wet band; detail ≈5/255 | **Product rework** | intended min/mid/max first |
| PW-04 Feed model reset | one changed row resets every delegate; 13 FEEDS IO tasks in the soak | **Watch** — FEEDS Custom 2–4 | stable-ID diff only if churn shows |
| PW-03 Media notify | 0.50 ms per emit × ≈0.25 refreshes/s ≈ 0.13 ms/s | **Close** (measured 2026-09-23) | — |
| PR-02 frame-swap callback | 5.6 µs × ≈89.4 swaps/s ≈ 0.5 ms/s (soak) | **Park** | DC-04 stays documented |
| PR-01 resolve memo | 47.6 µs per publication | **Park** | reopen only if publication latency points here |
| PR-07 eager QML compile | ≈0.2–0.3 s, startup only | **Park** | reopen if startup-to-reveal becomes a target |
| ST-01 / ST-02 large owners/files | 4,855-line `DisplayManager` | **Park** | move-only when a real change touches a clean seam |
| VZ-05 epoch cache | 17–117 µs/tick left after the single-freeze fix | **Park** | — |
| VZ-07 sleep slicing | no demonstrated problem | **Park** | — |
| LC-01, PR-05, PW-06, prefetch double batch | see §Closed | **Close** | — |

## Admitted slices

### LC-05 — context-menu entries refreshed after the menu is shown · Do

**Evidence.** `_refresh_quick_context_menu` costs 6.6 ms median (15.5 ms first) per open after LC-06. It runs after
`QuickDisplayRuntime._on_context_menu_requested` has already called `open_at()` (connection order at
`rendering/quick/runtime.py:228-231`), so when entries changed the Repeater rebuilds rows that are already visible.

**Decision.** Make the DisplayManager refresh complete before `open_at()` with the smallest ordering change. The
model's `replace_entries()` already returns early on an equal tuple (`rendering/quick/context_menu.py:375`) and stays
the only "entries unchanged" check: no second equality cache and no new menu-state owner. Preserve R-84 single-menu
enforcement, U-05 focus/Ctrl halo/keyboard semantics and action admission.

**Bars.** The entries present when the menu opens are the refreshed ones (fails with today's order);
`test_qtquick_context_menu*`; physical open/close feel.

### VZ-03 — per-tick phase instrumentation always on · Do (low priority)

**Evidence.** 4.2 µs/tick ≈ 0.4 ms/s. Small, but it is diagnostic work at rest, which the opt-in rule forbids.

**Decision.** Source check: the closure, dict and nine `perf_counter()` samples are local to `logical_tick`
(`widgets/spotify_visualizer/tick_pipeline.py:1422-1530`), and `--perf` is a process-wide flag set once at logging
setup, so the gate is contained. Skip the recording when perf is off. Keep the slow-tick warning and its phase
breakdown identical when perf is on. If the change turns out to need wider tick-pipeline surgery, park it instead;
0.4 ms/s is not worth that risk.

**Bars.** Perf-off ticks build no phase record; the perf-on slow-tick message format is unchanged.

### PW-05 — cancellable `ThreadManager.single_shot` · Do (before FEEDS Custom 2–4)

**Evidence.** `single_shot` already owns generation fencing, a registry, `_srpss_cancel_single_shot` and payload
release in `_finish(execute=False)`, but it returns `None`. So `widgets/feed_runtime.py:59` and
`widgets/steam_followed_runtime.py:48` hand-roll parentless `QTimer`s outside the registry, and Custom 2–4 would
multiply them. Soak: OS timer handles stayed ≈13–14 for 92 minutes, so this is ownership/durability work, not a repair
of an observed leak.

**Decision.** Return a small `SingleShotHandle`, **not** the `QTimer`. A call made off the UI thread creates its timer
later on the UI thread, so there is no timer to return synchronously.

- The handle is created immediately.
- `cancel()` is idempotent and works before the timer exists; timer creation is then skipped.
- A created timer binds to its handle; a later cancel goes through the existing `_finish(execute=False)`, releasing
  the callback payload and owner references as today.
- Firing marks the handle completed.
- Generation-wide retirement stays authoritative. The handle is not a second timer registry or lifecycle owner.

Migrate both families; their injectable `schedule` seams stay, and their deadline closures already carry the owner
generation. Delete both `_default_schedule` copies.

**Bars.**
- A cancel before timer creation (an off-UI-thread call) is honoured.
- A cancel after creation works.
- A cancel after the timer fires is a no-op.
- Cancelling releases the payload.
- Generation retirement still cancels.
- The Feed and Games-You-Follow deadline tests are unchanged.

### PW-03 — Clock notify split · Do with care (Clock only)

**Evidence.** One Clock `stateChanged.emit()` costs 0.69–0.77 ms of GUI binding re-evaluation even with no value
change. Each clock emits once per second.

**Decision.** Split a few semantic epochs — high-rate time/tick state versus style/config — not one signal per
property. `customEditableChildRoles` stays independent of the new signals (R-88); Edit/CUSTOM contracts unchanged.
Media is a separate later decision (§Watch). No repository-wide notify refactor.

**Bars.** Before/after binding cost on a live Clock; Clock Edit/CUSTOM oracle tests unchanged.

### VZ-04 — waveform samples only for Oscilloscope · Do with care

**Evidence.** Every mode copies and validates the 256-sample waveform: 38.4 µs/tick ≈ 3.5 ms/s of logical-thread
Python, although only Oscilloscope reads `common.waveform`. Soak: the audio lane ran 37,822 steps with 0 publication
rejects and 0 worker failures, so this is contained efficiency work, not a cadence rescue.

**Decision.** Acquire and copy samples only while Oscilloscope is the mode; other modes carry `waveform=()`.
`waveform_count` and the latest waveform generation are a separate authority from the sample payload and stay
unchanged (Sine/line-mode readiness, R-87 CHK12).

**Bars.**
- A per-mode test pins which modes consume the sample payload, so a future mode cannot silently read an omitted field.
- Readiness is unchanged.
- The BTF active-music lane passes.

### PR-04 — transition-end native re-upload · Stage A Do with care, Stage B Gated

**Evidence.**

- Operator trace, 2026-09-23 08:06: the first Quick cycle after each transition end takes 24.7–24.8 ms on the
  3840×2160 Visualizer display, against 2.8 ms steady.
- Soak: all ten retained transition endings show a large first post-transition cycle.
  - Total 26.62–90.58 ms (median ≈58.9 ms).
  - Sync 4.58–21.52 ms.
  - Render/upload 21.88–68.99 ms.
  - That is 5.5–9.9× the median of the following 60 cycles.
  - The last two, after external load eased, still cost ≈26.6 and 34.7 ms. The ≈24.8 ms event was not a fluke.
- Idle probe on a real `QQuickWindow` with the app's own OpenGL bootstrap, timing the frame that first uses a new 4K
  texture:

  | `QImage` format given to `createTextureFromImage` | blocking prepare | sync → swap |
  | --- | ---: | ---: |
  | `Format_RGBA8888` (current, straight alpha) | **8.12 ms** | 19.5 ms |
  | `Format_RGBA8888_Premultiplied` | **0.15 ms** | 10.6 ms |
  | `Format_ARGB32_Premultiplied` | 0.19 ms | 16.7 ms |

  Qt's scene-graph texture converts a straight-alpha image to premultiplied on the render thread before upload. For
  opaque pixels that pass only burns time.

**Stage A (admitted).**

1. **Make the background `PresentationImage` genuinely opaque, with one explicit compositing rule:** a transparent
   source is composited over black, the colour every other processing path already uses.
   - `capture_qimage` is a generic boundary (processed images via `display_image_route`, startup screen grabs via
     `startup_desktop_capture`), so do not blanket-convert there.
   - The one processing branch that can leak alpha is FILL's perfect-fit return in `rendering/image_processor_async.py`;
     every other branch paints onto a black-filled result.
   - Put the guarantee at that processing boundary, confirm that screen grabs are opaque, and document the rule.
2. **Label the native retained-background `QImage` `Format_RGBA8888_Premultiplied`**
   (`render/background_image_node.py:174`). This is byte-identical for opaque pixels. Never label non-opaque pixels
   premultiplied.

Stage A removes the conversion only. Under load, render/upload is the larger component, so Stage A is a **partial
mitigation**. PR-04 stays open until a post-change frame trace measures the complete transition-end cycle.

**Stage B (gated).** Dropping `.copy()` saves ≈3–4.5 ms of sync. It first needs a real Qt/PySide lifetime test proving
that the immutable `PresentationImage.rgba8` storage stays valid for as long as QSG/texture creation may reference it.
Do not infer synchronous consumption. Do not trade R-50/R-60/R-63 lifetime, texture-identity or no-black-flash safety
for it.

**Rejected:** moving the upload earlier (it only relocates the stall into the transition). **Blocked:** a zero
re-upload handoff (PySide 6.9.1 binds no `fromNative`, `createFrom` or `nativeTexture`).

**Bars (Stage A).**
- Transparent-PNG FILL perfect-fit oracle.
- Native image-format oracle.
- Retained-background/VRAM/texture accounting tests.
- Frame trace before/after on the 4K Visualizer display.
- Physical no-black-flash transition end.

## Product rework (transition work, not runtime cleanup)

`Docs/Future_Work/Transition_Expansion.md` §Control rework owns the design and bars. Evidence behind the decisions:

- **Crumble.** Irregularity 0.306 at complexity 0.5 → 0.351 at 1.0 → 0.382, flat from ≈1.26 to 2.0; an unclamped
  remap reaches only 0.388. Changing debris from 0.65 to 0 or 1 alters ≤0.22% of pixels at any progress.
- **Melt.** Inside the moving wet band (≈5% of the frame): gloss 0↔1 changes ≤3/255, detail 1↔2 ≈5/255, depth 0↔1
  ≈11/255. The soak contained no useful Melt sample and does not inform this work.

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
