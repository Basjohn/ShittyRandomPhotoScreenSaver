# 08 — Open Items: Evidence, Suggestions, Risks and Verdicts (2026-09-23)

Every item still open after Waves A–C and the stale-test pass, researched with evidence rather than estimates.
Measurements are on the dev machine (idle unless stated); operator runs cited by time are in `logs/` or
`logs/evidence_chest/0922_BeforeClaudeAuditWork`. **Verdict key:** **Do** (benefit clearly outweighs risk) ·
**Do with care** (worth it; named risk needs its bar) · **Decide** (product/architecture call for the operator) ·
**Close** (evidence shows no worthwhile benefit; delete from the queue) · **Park** (keep, no action now).

## Summary

| Item | Evidence (short) | Verdict |
| --- | --- | --- |
| PR-04 transition-end stall | ≈24.8 ms on the 4K Visualizer display per image change; **most of it is a Qt CPU pixel conversion caused by the `RGBA8888` label** (8.1 → 0.15 ms blocking on a real Quick window) | **Do with care** |
| Crumble crack complexity | dead above ≈1.26; whole range only moves irregularity 0.31 → 0.38 | **Decided by operator: much stronger shape mutation** |
| PW-02 Media IO starvation | mechanism proven by fault injection; real-world frequency unmeasured | **Decide** (cheap measurement first) |
| PW-03 notify granularity | one Clock `stateChanged` = 0.69–0.77 ms of GUI binding work, every second per clock | **Do with care** (Clock first) |
| LC-05 menu refresh after show | 6.6 ms median (15.5 ms first) rebuild while the menu is visible | **Do** |
| PR-01 resolve memo | 47.6 µs per publication ≈ 4.3 ms/s GUI | **Park** |
| VZ-04 waveform copy/validate | 38.4 µs/tick ≈ 3.5 ms/s logical thread | **Do with care** (Oscilloscope-only payload) |
| PR-02 frame-swap callback | 5.6 µs per swap ≈ 1.8 ms/s GUI at 165 Hz × 2 | **Park** |
| Crumble debris | debris on/off changes ≤0.22% of pixels at any progress | **Decide** (product) |
| Melt gloss / detail | gloss 0↔1 moves the wet band ≤3/255; detail ≈5/255 | **Decide** (product, with Melt rework) |
| PW-05 cancellable `single_shot` | 2 hand-rolled parentless deadline QTimers | **Do** before FEEDS Custom 2–4 |
| LC-01 GC freeze per generation | after a real replacement gen-2 = **1.2 ms** (11.7k unfrozen objects); pinned retired garbage 748 objects, 0 MB | **Close** |
| PR-05 repeat visualizer draws | 2.9% of draws, ≈5.8 ms/s render thread | **Close** (architecture risk ≫ benefit) |
| VZ-03 phase recording | 4.2 µs/tick ≈ 0.4 ms/s | **Close** |
| PW-06 supervisor Timer thread | 0.31 ms per 3 s ≈ 0.1 ms/s | **Close** |
| PW-04 Feed model reset | `replace_rows` already skips unchanged rows; resets only on real content change | **Close** |
| PR-07 eager QML compile | ≈210 ms at startup, startup-only | **Park** |
| ST-01 `DisplayManager` size | 4,855 lines | **Park** (move-only when touched) |
| VZ-05 epoch cache | 17–117 µs/tick left after the single-freeze fix | **Park** |
| VZ-07 sleep slicing | no evidence of harm | **Park** |
| Prefetch "double batch" | catch-up after a lookahead miss ("requested=2 retained=1") | **Close** (benign) |

---

## PR-04 — transition-end re-upload stall · **Do with care**

**Evidence.** Operator `--frame-trace` (2026-09-23 08:06): the first Quick cycle after every transition end is
24.7–24.8 ms on the 3840×2160 Visualizer display vs 2.8 ms steady (4.5 ms sync `QImage.copy()` + 13.5 ms upload).
New probe on a real `QQuickWindow` with the app's own OpenGL bootstrap, timing the frame that first uses a new 4K
texture:

| QImage format handed to `createTextureFromImage` | blocking prepare | sync → swap |
| --- | ---: | ---: |
| `Format_RGBA8888` (current, straight alpha) | **8.12 ms** | 19.5 ms |
| `Format_RGBA8888_Premultiplied` | **0.15 ms** | 10.6 ms |
| `Format_ARGB32_Premultiplied` | 0.19 ms | 16.7 ms |

`QImage` `RGBA8888 → RGBA8888_Premultiplied` alone costs 10.8 ms at 4K. Qt's scene-graph texture converts a
straight-alpha image to premultiplied on the render thread before every upload; the pixels are opaque, so that pass
does nothing but burn time.

**Suggestion.** (1) Guarantee opaque presentation pixels at capture (`image_boundary._capture_qimage`): FILL's
"perfect fit" path returns the scaled source directly, so a transparent PNG can carry alpha; composite it onto black
exactly as every other processing path already does. (2) Label the native branch `QImage` `Format_RGBA8888_Premultiplied`
— byte-identical for opaque pixels. (3) Separately, drop `.copy()` only after a Qt lifetime test (saves the 4.5 ms sync).

**Risks.** Transparent sources are the only behaviour change, and today they already differ between the transition
(straight RGBA sampled by the custom node) and steady native output (Qt-premultiplied = over black); step 1 makes both
the same as the steady look. R-60 texture identity and R-63 no-black-flash are untouched (same node, same timing).

**Benefit vs risk.** ≈8–10 ms of render-thread time removed per display per image change, on the Visualizer display
included, for a two-line change plus an opacity guarantee. **Clearly worth it.** Bars: transparent-PNG perfect-fit
capture test; native-branch format test; frame-trace before/after.

## Crumble crack complexity · **Operator decision (2026-09-23): much stronger shape/pattern mutation**

**Evidence.** Mean cell-area coefficient of variation over 12 seeds, 35 pieces: 0.306 (c=0.5) → 0.351 (1.0) → 0.382
(≥1.26, flat to 2.0). The only input is site jitter (`spread = min(.48, .38·c)`), which is bounded by the cell grid;
even an unclamped remap moves irregularity only to 0.388 at 2.0. A remap alone cannot deliver "much more effect".

**Design options (to combine), all inside `run_geometry`/Crumble shaders, prepared off-thread (TX-01):**

1. **Jagged fracture edges.** Subdivide each shared polygon edge into k segments with seeded perpendicular offsets
   derived from the edge's endpoints (the same trick `crumble_vertices` uses for crack phase), so both neighbours get
   the identical polyline and coverage stays gap-free. Complexity drives k and amplitude. Strongest visible change.
2. **Site distribution.** Complexity shifts from grid-jitter toward clustered/Poisson sites, mixing large slabs with
   small shards (shape *and* size variety).
3. **Secondary micro-cracks** in the crack-formation shader stage (branching fissures that do not split pieces),
   density scaled by complexity.
4. **Anisotropy** (optional): elongate cells along the fall direction at high complexity.

**Risks.** Seams/gaps if shared edges diverge (bar: coverage/seam oracle); crack-stage stroke coordinates must follow
the polyline; geometry cost grows with k (now off the render thread; keep the 128-piece build under ~40 ms on
COMPUTE); determinism per seed must hold (byte-identity bar per seed). The pinned pixel oracles and the strict xfail
in `test_qtquick_crumble_volume.py` get replaced by "each complexity step changes shape metrics monotonically".

**Benefit vs risk.** Operator-requested product change; risk is contained to Crumble with clear bars. **Admitted.**

## PW-02 — Media truth/commands share the FIFO IO pool · **Decide**

**Evidence.** Fault injection (`tests/test_media_io_starvation.py`): with four stalled network tasks, a transport
command and the activation refresh stay queued past 0.42 s. Real-world frequency is **unmeasured**: no log records IO
queue wait. (The `slow shared refresh total_ms≈2.4–2.9 s` startup warnings measure GUI delivery after the worker,
not IO queueing — startup GUI saturation, not PW-02.)

**Suggestion.** First make it measurable: add IO `queue_wait_ms_max` for `media_refresh`/`media_cmd` categories to the
existing `--perf` summary (opt-in, no new timer) and run the offline/DNS-blocked start physical check. If waits >150 ms
appear, add the Media-only serial lane (one lazy event-driven worker owned by the shared Media runtime). Reusing the
WinRT observation worker is rejected (teardown waits 2 s there).

**Risks of the lane.** One more thread and its retirement (R-30/R-53); a stuck WinRT await then blocks only Media (as
it blocks one IO worker today). **Benefit vs risk:** protects play/pause truth (a protected invariant) but only under
network stalls; do the cheap measurement before paying the lifecycle cost.

## PW-03 — one `stateChanged` for 30–67 properties · **Do with care (Clock first)**

**Evidence.** A live Clock presentation: one `stateChanged.emit()` costs **0.69–0.77 ms** of GUI-thread binding
re-evaluation with no value changes. The Clock emits once per second per instance (three clocks on two displays ≈
2–4.6 ms/s and a sub-millisecond GUI block every second). Media's model is twice the size and emits per event.

**Suggestion.** Split notifies into `styleChanged` (config epoch) and a small `timeChanged` (text/tick) for Clock;
then Media (`transportChanged`/`trackChanged`/`artworkChanged`). **Risks:** QML bindings that read a property whose
notify moves must be re-pointed; R-88 requires `customEditableChildRoles` to stay independent of the new signals.
**Benefit vs risk:** measurable, owner-local, low risk with the Edit/CUSTOM oracle tests. Worth it.

## LC-05 — context-menu entries rebuilt after the menu is shown · **Do**

**Evidence.** `_refresh_quick_context_menu` costs 6.6 ms median (15.5 ms first) per open (after LC-06) and runs after
`_on_context_menu_requested` has already opened the model, so the Repeater rebuilds visible rows.

**Suggestion.** Refresh before opening (reverse the connection order at `rendering/quick/runtime.py:228-231`) and skip
the rebuild when the entry tuple is unchanged. **Risks:** R-84 single-menu enforcement and U-05 focus/Ctrl semantics
(covered by `test_qtquick_context_menu*`). **Benefit vs risk:** removes a visible rebuild and most per-open cost; low risk.

## PR-01 remainder — presentation resolve per publication · **Park**

47.6 µs per publication ≈ 4.3 ms/s of GUI Python. A memo keyed on every resolve input is feasible but R-68/U-09
forbid a second geometry authority and a missed key would freeze geometry. Reopen only if a trace shows GUI
publication latency pressure.

## VZ-04 — every mode copies and validates the 256-sample waveform · **Do with care**

38.4 µs/tick ≈ 3.5 ms/s on the logical thread for modes that never draw samples. Suggestion: carry the samples only for
Oscilloscope (empty tuple elsewhere), mirroring VZ-01's demand. Risk: U-10/diagnostics that read `common.waveform`
(debug-level only). Worth doing with an Oscilloscope payload bar.

## PR-02 — per-frame queued `frameSwapped` readiness callback · **Park**

5.6 µs per swap ≈ 1.8 ms/s at 165 Hz on two displays. The guardrail (DC-04) still says the callback should not exist,
but removing it touches R-63 first-show/reveal ordering. Park until it is touched for another reason; keep DC-04 open.

## Crumble debris · **Decide (product)**

Changing debris from 0.65 to 0 or 1 alters **≤0.22%** of pixels at any progress (0.00% at 0.35 and 0.80). Debris is
effectively invisible. Either enlarge/increase debris (fold into the complexity work) or drop the control. The red
oracle stays until then.

## Melt gloss / detail · **Decide (product, with Melt rework)**

Inside the moving wet band (≈5% of the frame): gloss 0↔1 changes ≤3/255 (mean 0.15–0.19) even on textured images;
detail 1↔2 ≈5/255; depth 0↔1 ≈11/255. Gloss is effectively a dead control in the 1c6cf165 design. Decide the intended
strength with Melt's open visual acceptance; then re-express the oracles inside the band.

## PW-05 — cancellable `single_shot` · **Do (before FEEDS Custom 2–4)**

`feed_runtime.py:62` and `steam_followed_runtime.py:55` hand-roll parentless deadline `QTimer`s because
`ThreadManager.single_shot` returns no cancel handle; Custom 2–4 would multiply them. A handle moves those timers into
the generation-owned registry (R-65/R-27). Low risk, durability win.

## Closures (evidence shows no worthwhile benefit)

- **LC-01.** Real engine, freeze, full runtime replacement: unfrozen tracked objects 11,692 → gen-2 **1.2 ms**
  (vs 90.7 ms before freezing 141k objects); `gc.unfreeze()` then frees only 748 retired objects, 0 MB RSS. The
  predicted post-replacement stall does not exist. Close; delete the item.
- **PR-05.** 863 of 29,706 draws (2.9%) repeat a revision, ≈1.8 ms each ≈ 5.8 ms/s render thread. Fixing it changes
  the custom-render composition (Compositor_Architecture §6, High risk). Close.
- **VZ-03.** 4.2 µs/tick ≈ 0.4 ms/s. Close.
- **PW-06.** 0.31 ms per `threading.Timer` cycle every 3 s ≈ 0.1 ms/s; replacing it risks R-30 exit behaviour. Close.
- **PW-04.** `FeedRowsModel.replace_rows` returns early on equal rows; resets happen only on real content change
  (feed refresh cadence, minutes). Close.
- **Prefetch double batch (22:58:31).** `[CACHE] Protected near-future cache keys requested=2 retained=1` → the
  resume warmed two upcoming images for two displays (4 lines). Benign catch-up. Close.

## Parked

- **PR-07** (≈210 ms `QuickSceneFactory` compile, startup only) — lazy compile only helps disabled families.
- **ST-01** (`DisplayManager` 4,855 lines) — move-only extractions when a change touches a concern.
- **VZ-05 epoch cache**, **VZ-07 sleep slicing** — see 02.
