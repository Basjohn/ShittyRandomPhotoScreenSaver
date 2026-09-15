# R-87 — Qt Quick High-Refresh Freshness / Scheduler Regression

Status: **[~] OPEN — SIGNIFICANTLY IMPROVED ON CHECKPOINT 3 AND OPERATOR-OBSERVED CHECKPOINT 5 / NOT SOLVED**

This status is intentionally pessimistic. It does **not** mean the current source is unusable or that every attempted repair failed; it means SRPSS has repeatedly produced plausible FPS/cadence numbers while operator-visible motion remained worse than the known-good Qt Quick releases. Do not mark this solved from source review, averages, or a short quiet-machine run. Physical mixed-refresh Windows validation under both low and UE5-class pressure is required.

## Symptom

The first 5.0.0/5.0.1 Qt Quick builds were visibly smoother under the same two-display workload and tolerated heavy external system pressure better. Current builds can report healthy Bubble logical cadence (~90 revisions/s) and apparently healthy scene FPS while motion still hitches or, on the 60 Hz display under pressure, feels like a slow crawl.

The failure is strongest on the 164.835 Hz display under system contention, but it is not simply a high-refresh FPS shortage. On the 60 Hz display, Edit mode can render well above 90 FPS while the Bubble state being drawn is still tens of milliseconds old.

## Durable evidence — do not require the original logs

The useful readings from the 2026-09-14/15 investigation are preserved here because the raw log archives may disappear:

- Smooth pre-fix control, healthy D0 Bubble: about **164.6 FPS**, **0% median pacer skip**, **~10.1 ms median drawn visualizer age**, while logical Bubble revisions remained ~90 Hz.
- SettingsLifetime-era D0 Bubble: about **155.7 FPS**, **~3% median skip**, **~17.8 ms median drawn age**, with the same ~90 Hz logical producer.
- Long supervisor build soak, low load: about **166 FPS median**, essentially **0% skip**, **~9–10 ms** age. Under later UE5-class pressure the same build fell to about **121 FPS**, **~19% skip**, **~22 ms** median age.
- One-process/shared-COMPUTE A/B under roughly comparable ~50–55% system CPU improved D0 to about **134 FPS** and reduced app threads from roughly **113 to ~97**, but did not restore old pressure resistance.
- Smooth control process topology: one image worker, roughly **92–95 app threads**, about **813 MiB** child private commit. Supervisor-era topology: foreground + speculative image workers, roughly **111–128 app threads**, about **1.62 GiB** combined child private commit.
- Current A/B on D1 under high pressure could render about **102–111 scene FPS with a 60 Hz pacer** while drawn visualizer state was still **~28–30 ms old**. Therefore "render Bubble at 90+ FPS" is not by itself a repair.
- The smooth control often rendered D1 Bubble at only **~60–61 FPS** while drawn-state age was commonly **~7–15 ms**, and it looked smooth.
- A later low-pressure Edit-mode observation on D1 reached about **256.5 FPS**, with the Bubble producer still about **89.8 revisions/s**. Edit mode therefore creates additional Qt Quick update demand and is not a steady-runtime FPS yardstick.
- A fast September 12 control under roughly **50% median system CPU** held a 60 Hz Bubble window essentially at target with zero pacer skip for long periods. Current builds also cope much better at 60 Hz than at 165 Hz. The lost headroom is disproportionately damaging when the presentation opportunity is only ~6.07 ms.

## 2026-09-15 Checkpoint-3 installed frame-trace result — architecture finally moved in the right direction

This is the first installed run after the event-driven Quick-admission/frame-trace cut that materially changes the R-87 picture. Preserve it even if the raw archive disappears. The operator ran D1 from light workstation load into a heavy external application with most diagnostics enabled and reported:

- light load: seemingly perfect;
- while the heavy application was actively loading: visible crawl, undesirable but substantially less important than settled behavior;
- heavy application fully loaded in the background: pretty good, roughly **90 FPS**, typically **16-20 ms** visualizer age, with about half or less of the prior crawl.

The trace itself closed cleanly with **284,830 fixed binary records, 0 dropped records, 0 write errors**, so the phase evidence is not based on a lossy diagnostic stream. Whole-run counts were **47,368 logical publications, 46,442 Quick sync consumptions, 48,723 render draws and 48,987 swaps**. Whole-run publication->draw was **13.57 ms median / 17.11 ms p95 / 25.98 ms p99**.

For phase comparison, the boundaries below are inferred from the Quick window losing foreground activation at ~16:07:42 and the independent usage sampler's system-load climb; they are not claimed as exact operator annotations:

- **Light steady (~16:06:25-16:07:42):** publication->GUI wake **0.13 / 0.97 ms median/p95**; publication->Quick sync **5.28 / 6.38 ms**; publication->draw **8.14 / 14.21 ms**, p99 **15.37 ms**. Quick sync->draw was **2.81 / 6.63 ms**.
- **Heavy application loading (~16:07:42-16:09:15):** publication->GUI wake **0.35 / 2.65 ms**; publication->Quick sync **5.78 / 14.15 ms**; publication->draw **13.20 / 22.61 ms**, p99 **47.93 ms**; publication->swap p95 **27.55 ms**, p99 **51.14 ms**. This is a broad external-load disturbance rather than one isolated SRPSS queue.
- **Settled heavy background load (~16:09:15-16:14:00, before later Settings/mode interaction):** publication->GUI wake **0.42 / 1.70 ms**; publication->Quick sync **5.93 / 7.66 ms**; publication->draw **14.03 / 16.92 ms**, p99 **23.10 ms**; publication->swap **14.60 / 17.58 ms**, p99 **24.01 ms**. Quick sync->draw is now the conspicuous steady-load delta at **7.89 / 9.98 ms**, versus **2.81 / 6.63 ms** in light load.

This result is decisive on direction: **fresh-state production and GUI admission are no longer the primary steady-load problem.** The event-driven latest-wins mailbox/wake must stay. The next measurement should split `QUICK_SYNC_CONSUME -> RENDER_DRAW`, because the current trace cannot tell whether the extra ~5 ms settled-load cost is Qt's post-sync render scheduling, Python/PySide render-thread execution, or the actual OpenGL render body. Add trace markers rather than guessing or starting another execution-topology A/B. Checkpoint 4/5 contain further purity/pacer reductions and were not exercised by this run.

## 2026-09-15 Checkpoint-5 dual-display result — rare cross-display evidence, raw binary ingested

The operator then ran **Checkpoint 5** in the opposite direction, heavy load -> light load, with both displays active and most diagnostic flags enabled. This is especially valuable because dual-display runs are disruptive and should not become the routine evidence request. The raw Checkpoint-5 archive became visible only after this assessment was written. **Checkpoint 6 intentionally preserves this operator-evidence assessment before binary ingestion**; ingest the archive immediately after CHK6 and replace/augment these observations with quantified trace evidence rather than guessing:

- D0 (165 Hz class) is **tremendously smoother than pre-Checkpoint-3 behavior**, with only occasional residual crawl, despite the visualizer reporting roughly 90 fresh revisions/draws in ordinary steady state.
- D1 is likewise much improved overall.
- During wallpaper transitions the reported visualizer draw rate can rise to roughly **250/s on D0** and **120/s on D1**, then return toward ~90 after the transition.
- The run spent most of its time under heavy load, then entered Settings, with a light-load tail.

This is **not a dynamic 90 Hz presentation cap**. Checkpoint-5 source has an authored logical visualizer cadence of `_DEFAULT_MAX_FPS = 90.0`; that cadence produces fresh immutable visualizer revisions. In steady state, the new event-driven architecture requests the retained visualizer item only when a fresh publication arrives, so visualizer draw rate naturally converges toward the ~90 Hz producer instead of redrawing unchanged state at panel refresh. A 165 Hz display can still look materially smoother because fresh state can reach the next presentation opportunity with lower quantization/scheduling delay even when state itself changes ~90 times/s.

Wallpaper transition demand is independent. While a wall-time transition is active, `QuickFramePacer` requests successive whole-window frames through `frameSwapped -> QWindow.requestUpdate()`. The visualizer render node is therefore visited on those scene frames too, even when no newer logical visualizer revision exists. The HUD intentionally reports these as separate quantities: `viz_draw_fps` counts render-node draw invocations; `viz_revision_hz` counts fresh logical revision advance. They must not be conflated. Checkpoint-3 HUD data already demonstrates the same effect at smaller scale: light median draw/revision **90.06 / 89.98 Hz**; settled-heavy **90.05 / 89.96 Hz**; and within settled-heavy, transition-active median draw/revision **99.84 / 89.94 Hz** versus transition-idle **90.00 / 89.96 Hz**, with nearly unchanged median state age (**18.65 vs 17.81 ms**).

Qt documentation says `frameSwapped` means a frame has been **queued for presenting**, and only promises at-most-one-per-vsync behavior when vertical synchronization is enabled. Qt also documents that `swapInterval=0` makes the threaded render loop stop relying on vsync to drive animations, while window updates still flow through `QWindow.requestUpdate()`. Independent KDAB scene-graph material likewise separates synchronization, render-thread execution and swap. These sources explain why a diagnostic can report 250/120 queued/rendered scene frames on 165/60 Hz panels, but they do **not** prove physical presentation rate or SRPSS smoothness. Installed traces and operator-visible motion remain authoritative.

### Planning lock from the combined Checkpoint-3 + Checkpoint-5 evidence

1. **Keep the event-driven latest-wins visualizer admission.** It has both quantified Checkpoint-3 and operator-observed Checkpoint-5 support. Do not restore the display-refresh Python QTimer and do not raise Bubble logical cadence merely to chase panel Hz.
2. **Keep the runtime-purity work.** No QWidget/QPixmap/synchronous foreground fallback should return; none of the new evidence points back at image topology as the steady-heavy root.
3. **Do not optimize transition-time duplicate visualizer draws pre-emptively.** Checkpoint-3 settled-heavy age was essentially the same with transition active vs idle. If future trace shows meaningful contention from these draws, optimize with evidence.
4. **Use the already-added fine trace boundaries next:** `QUICK_SYNC_CONSUME -> QUICK_SYNC_READY -> RENDER_BEGIN -> RENDER_DRAW -> FRAME_SWAP`. The main unresolved settled-heavy question is whether time is spent in sync work, waiting to begin rendering, or inside Python/OpenGL rendering.
5. **Keep C++/QRhi conditional.** `RENDER_BEGIN -> RENDER_DRAW` dominance would support a small render bridge spike; `QUICK_SYNC_READY -> RENDER_BEGIN` dominance would argue for render-loop/scheduling work instead. Do not begin a broad visualizer rewrite.
6. **Do not demand more two-display runs casually.** The Checkpoint-5 dual-display run is rare evidence. New marker validation can be D1-only unless a later result specifically requires a cross-display answer.
7. **Heavy-application load-in crawl is secondary.** Reduce it opportunistically, but settled-heavy residual crawl is the primary remaining acceptance target.
8. **Clarify diagnostics.** Preserve log schema if needed, but UI/report wording should distinguish scene swaps/render-node draws from fresh logical revisions so `250 fps` cannot be misread as 250 fresh Bubble states or 250 physical presentations.

Research references used only as architectural guidance, never as acceptance proof:

- Qt `Window::frameSwapped`: https://doc.qt.io/qt-6/qml-qtquick-window.html
- Qt `QWindow::requestUpdate`: https://doc.qt.io/qt-6/qwindow.html
- Qt Quick scene graph / multi-window and `swapInterval=0` animation behavior: https://doc.qt.io/qt-6/qtquick-visualcanvas-scenegraph.html
- KDAB render-stage/thread description: https://www.kdab.com/integrate-opengl-code-qt-quick-2-applications-part-2/


### Binary ingestion addendum — 301,730 records, zero drops, transition feedback loop exposed

The raw archive later became visible and was fully ingested. Trace integrity is clean: **301,730 records, 0 dropped records, 0 write errors**. Usage telemetry shows the heavy interval at roughly **44.5-50.8% system CPU** until the post-Settings light tail. The visualizer's logical publication cadence remains ~90/s throughout clean D0/D1 heavy/light phases.

Clean heavy phases:

- **D1 / 60 Hz (16:19:54-16:22:10):** 12,223 publications over 136 s (~89.9/s); publish->wake **0.43 ms median / 2.30 p95**; publish->Quick-sync **5.94 / 10.34 ms**; publish->draw **13.18 / 16.72 ms**; sync->draw **6.75 / 10.00 ms**; repeated draws **3.49%**; HUD age **17.23 ms median**.
- **D0 / 165 Hz class (16:22:30-16:25:30):** 16,186 publications over 180 s (~89.9/s); publish->wake **0.43 / 5.36 ms**; publish->Quick-sync **2.31 / 15.51 ms**; publish->draw **7.32 / 26.32 ms**; sync->draw **5.09 / 14.05 ms**; repeated draws **4.98%**; HUD age **10.58 ms median**. D0 therefore has dramatically better median freshness than D1 while retaining occasional large tails, matching the physical report.

The D0 tail is strongly tied to the remaining application-owned transition continuation:

- **Heavy D0 idle:** publish->draw **6.94 ms median / 18.04 p95**, wake **0.35 ms median**, publish->sync **2.14 ms**, sync->draw **4.78 ms**.
- **Heavy D0 transition-active:** publish->draw **24.15 / 29.29 ms**, wake **4.09 ms**, publish->sync **13.91 ms**, sync->draw **9.95 ms**.
- **Light D0 transition-idle:** publish->draw **4.13 ms median**.
- **Light D0 transition-active:** publish->draw **12.40 ms median**; HUD visualizer draws **~286.9/s median** while logical revisions remain **~89.9/s**.

D1 is much less affected by transition demand: heavy active vs idle publish->draw **14.62 vs 12.89 ms**, and light **7.81 vs 7.34 ms**. This display asymmetry is exactly what an as-fast-as-possible swap feedback chain would produce: D0's 2560x1440 scene can cycle far faster than the 3840x2160 D1 scene when `swapInterval=0`. The 250-300/s D0 draw bursts are therefore **real render-node invocations, not a diagnostic lie and not fresh Bubble states**. They are a side effect of `frameSwapped -> requestUpdate()` transition ownership.

After Settings/runtime churn and transitions settle, the light controls return to the intended state: D0 pre-transition settled window is ~90 revisions/s, ~93 median draws/s and **3.79 ms median publish->draw**; D1 post-transition settled window is ~90/90 with **7.09 ms median publish->draw** and only **0.69% repeat draws**. There is no persistent 90 Hz display cap.

**Architecture consequence:** preserve ~90 Hz Bubble logical cadence and latest-wins admission. Replace the remaining transition swap-feedback loop with a properly paced Qt Quick/animation-driver-owned retained update mechanism; do not use a Python display-refresh timer. Research the exact Qt-native mechanism before editing production, and use installed results as the deciding evidence.

**Trace correction completed in continuation CHK8 before trusting new swap latency:** CHK5 proved the old `FRAME_SWAP` attribution reused the last visualizer draw identity on later scene-only swaps, creating fake multi-second publish->swap ages after transfers/absence. Those CHK5 full-run swap tails remain invalid historical diagnostics; `RENDER_DRAW` and upstream boundaries were valid. The repaired tracer now gives each real visualizer draw a render-thread sequence token and emits `FRAME_SWAP` only when that token advanced since the prior swap. The token is consumed before the bounded trace-ring write so dropped diagnostics cannot be misattributed later. The latch is lock-free on the render-thread draw/swap boundary and adds no presentation wait. Source regression coverage verifies one sequence increment per actual draw and no repeated-swap resurrection.

## What the numbers mean

Average scene FPS and logical cadence are necessary but not sufficient. The important chain is:

`logical state produced -> admitted/published -> Quick sync -> drawn/presented`

Current failures often happen after the producer: Bubble can continue at ~90 Hz with zero publication rejection while the state actually reaching a draw is one or more presentation opportunities older than in the smooth control.

`dt_max` is also not a sole smoothness oracle. The smooth control itself can contain 20–40 ms one-second worst-swap gaps. Use frame-spacing tails together with **fresh-state age**, pacer skip, system pressure and operator-visible motion.

## Hypotheses / attempted methods

### Rejected or insufficient

- **Bubble logical cadence was accidentally throttled to 60 Hz:** rejected. Current D1 logs still show ~90 logical revisions/s; normal Quick pacer behavior is byte-equivalent to the smooth control.
- **QuickFramePacer was recently changed:** rejected. Timing behavior is unchanged across the smooth-control -> current boundary; current differences are diagnostic naming only.
- **Visualizer render bridge/item/node became more expensive:** no meaningful source delta found across the contemporaneous boundary.
- **Generic GPU saturation:** unsupported. GPU-busy telemetry was low in representative runs; the failure tracks scheduling pressure/freshness better than raw GPU utilization.
- **Generic telemetry/logging volume:** insufficient. The smooth control ran the same broad diagnostic flag family and could remain smooth. Later deep sidecars can still have their own observer effect and must be explicitly admitted.
- **GUI event-loop latency alone:** insufficient. D0 can show healthy ~1–3 ms GUI p95 windows while physical swap/freshness still degrades.
- **System Stats / Steam widgets:** no convincing causal signal; operator disable/re-enable experiments did not materially restore smoothness.
- **Gmail/Reddit hidden QML delegates:** valid inefficiency and repaired, but too small and chronologically insufficient as the root. Keep the projection fix.
- **Force `swapInterval=1`:** R-86 installed A/B was materially worse and was rolled back. Keep release-era `swapInterval=0`.
- **Use the ~220 FPS Edit-mode peak as the performance target:** rejected as a benchmark. Edit mode creates additional scene demand; it remains useful only as proof of available headroom / uncapped update demand.
- **Simply force D1 normal Bubble to 90 FPS:** not yet justified. Current D1 Edit can already exceed 100 FPS while drawing ~28–30 ms-old state. More draws of stale state can increase contention without restoring freshness.

### Partial wins, not closure

1. **Separate speculative image process / supervisor.**
   - Correctly isolated image-prefetch CPU work and later gained a supervisor-owned blocking response listener so generic IO workers no longer sat in `await_response`.
   - Shared-memory/correlation/generation cleanup was healthy.
   - But the second frozen Python/image process added roughly 20–30 native threads and ~800 MiB extra child private commit. Under contention it reduced high-refresh headroom. Removing it improved comparable-pressure D0 behavior, so the persistent second process is not the preferred production topology.

2. **Supervisor-owned response listener.**
   - Keep it. It is sound general process infrastructure and removed a real IO-pool waiter. It is not the root smoothness fix and does not require keeping a speculative process alive.

3. **Return scaled speculation to the parent shared COMPUTE pool.**
   - Reduced process/thread footprint and recovered some D0 headroom.
   - Still insufficient because `ThreadManager.TaskPriority.LOW` is passive metadata on a FIFO `ThreadPoolExecutor`; the 4K `QImage.scaled()` work therefore runs at ordinary OS thread priority and can compete with Qt Quick under pressure.

4. **Current experiment: one genuinely demoted in-process background CPU lane.**
   - Keep R-82 liveness/correctness, single-flight scaled speculation, bounded/latest-useful backlog, byte cap, generation fences, raw-parent release discipline, QImage-only worker processing, and foreground authority for Lanczos/sharpen.
   - Remove both bad execution locations: no second Python process and no ordinary-priority shared COMPUTE worker.
   - ThreadManager owns one lazy serial worker. On Windows it requests `THREAD_PRIORITY_BELOW_NORMAL` and disables dynamic priority boosts before executing best-effort work. If the demotion contract cannot be installed, speculative work fails closed rather than silently competing at normal priority.
   - This is **awaiting installed evidence** and must not be called solved from code/tests.

## R-80 -> R-86 preservation audit

Do **not** solve R-87 by reviving the large-tail bugs fixed immediately before it.

- **R-80:** corrected the event-loop oracle's rolling-history contamination. The corrected recorder existed in the smooth control; rollback cannot explain or repair R-87.
- **R-81:** Clock slot/state replay correctness existed in the smooth-control era; unrelated to steady frame scheduling.
- **R-82:** raw-parent/derivative ownership and orphan-budget reclamation are mandatory. The subtle performance interaction is that repaired liveness means speculation now keeps running instead of sometimes dying after ~11 completions. Preserve correctness; change the execution policy, not the ownership fix.
- **R-83:** Reddit sub-ms cooldown recursion fix is edge-triggered and existed in the smooth control. Do not restore recursive re-arm behavior.
- **R-84:** preserve Toolhelp topology sampling, detached image publication, context-menu notification separation, and handle-attribution findings. Those repairs removed expensive GUI/GIL work or narrowed a real lifetime problem. Deep handle attribution is now explicitly opt-in and must not silently ride ordinary `--usage`.
- **R-85:** multi-stage monitor wake/topology correctness is independent and must stay.
- **R-86:** interval-1 hypothesis was physically worse and is already rolled back. Do not retry it as generic Qt advice.

The smoother buggy runtime is evidence, **not a rollback target**.

## Qt / Windows mechanism notes

Qt Quick's threaded render loop and multiple top-level windows are sensitive to synchronization and scheduling latency, especially with mixed refresh rates and an unsynchronised (`swapInterval=0`) presentation policy. A few milliseconds of extra runnable CPU work can consume a 165 Hz presentation opportunity without reducing the 90 Hz logical producer.

Windows creates ordinary threads at normal priority and recommends below-normal/lowest priority for processor-intensive background threads so foreground work can preempt them. Windows also dynamically boosts threads as they leave waits; a speculative lane should not receive that wake-up boost. The current background-lane experiment therefore installs a true native scheduling policy rather than trusting SRPSS `TaskPriority` metadata.

## Acceptance gate

R-87 remains **OPEN / NOT SOLVED** until installed evidence demonstrates all of the following:

1. Low-load D0 remains near the good-control behavior without harming D1.
2. Under the same UE5-class external load that used to be tolerated, D0 high-refresh Bubble materially improves versus the ~121 FPS supervisor / ~134 FPS shared-COMPUTE states **and visibly feels smooth**.
3. D1 under pressure no longer has the "high FPS but crawl" failure; drawn-state age/freshness must improve, not merely scene FPS.
4. Bubble logical cadence/reactivity remains ~90 Hz and no mode loses authored motion/amplitude/ghost behavior.
5. R-82 scaled-prefetch liveness remains correct indefinitely; no orphaned derivative budget, raw-parent leak, stale-generation publication or foreground ImageWorker fallback returns.
6. No PID/handle/thread/private-commit mammoth tail returns. The new lane should add at most one lazy in-process thread, not another process/native thread team.
7. Settings/Edit/topology lifecycle fixes remain clean; no resurrection of R-80 through R-86 correctness defects.

If this lane does not materially help installed pressure behavior, stop changing image topology. The next cut is Qt Quick publication/sync/presentation scheduling itself, ideally behind a dedicated opt-in sidecar. Do not add more normal-runtime telemetry and do not reduce visualizer fidelity/cadence to manufacture prettier metrics.

## 2026-09-15 single-display D1 load ladder — R-87 background lane did not close the bug

Operator-visible evidence from the R-87 one-display/60 Hz MC run must survive even if the raw logs disappear:

- Around **10:52**: definite degradation during medium/light workstation load.
- Around **10:54**: at least two additional visible degradation episodes.
- Around **10:57**: workstation load was reduced, but not yet to light.
- Around **10:59**: light load only (primarily browsers). Motion improved relative to the marked degraded periods.
- Around **11:06**: began loading a heavy UE5 game; crawl/hitch pressure returned/worsened.

During this run the R-87 background CPU lane reported its intended one-worker, Windows below-normal/no-boost policy. Bubble logical cadence remained around its authored ~90 revisions/s. Therefore R-87's scheduler-demoted speculative scaling lane is retained as a sane background-work policy but **did not solve the crawl**. Stop cycling speculative-image execution topology as the primary fix. The next active cut is publication/sync/draw observability (`--frame-trace`), Qt Quick-native event-driven presentation demand, and removal of runtime legacy QPixmap/synchronous presentation escape hatches.

