# R-87 — Qt Quick High-Refresh Freshness / Scheduler Regression

Status: **[~] OPEN FOR SCHEDULING HEADROOM / CHK15 IS THE OPERATOR-ACCEPTED GOLDEN PERFORMANCE BASELINE**

The early sections below preserve the historical regression and its former closure gates. They must not be read as saying CHK15 is visibly broken: the CHK14 runtime evidence was frozen into CHK15, and the operator then reported excellent heavy mixed-refresh smoothness on both displays. Remaining R-87 work is resilience/headroom only and is governed by the CHK15 neutral-or-better rule near the end of this document.

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

At Checkpoint 5, wallpaper transition demand was still independent and used the now-retired `frameSwapped -> QWindow.requestUpdate()` feedback loop. That historical mechanism caused the visualizer render node to be revisited on transition scene frames even when no newer logical visualizer revision existed. The HUD correctly separated `viz_draw_fps` (render-node invocations) from `viz_revision_hz` (fresh logical revisions). CHK5 raw dual-display evidence later proved the feedback loop over-drove D0 and CHK10 replaced it with the native `FrameAnimation` + per-display gate; **do not read this historical paragraph as current architecture**. Checkpoint-3 HUD data demonstrates the draw/revision distinction at smaller scale: light median draw/revision **90.06 / 89.98 Hz**; settled-heavy **90.05 / 89.96 Hz**; and within settled-heavy, transition-active median draw/revision **99.84 / 89.94 Hz** versus transition-idle **90.00 / 89.96 Hz**, with nearly unchanged median state age (**18.65 vs 17.81 ms**).

Qt documentation says `frameSwapped` means a frame has been **queued for presenting**, and only promises at-most-one-per-vsync behavior when vertical synchronization is enabled. Qt also documents that `swapInterval=0` makes the threaded render loop stop relying on vsync to drive animations, while window updates still flow through `QWindow.requestUpdate()`. Independent KDAB scene-graph material likewise separates synchronization, render-thread execution and swap. These sources explain why a diagnostic can report 250/120 queued/rendered scene frames on 165/60 Hz panels, but they do **not** prove physical presentation rate or SRPSS smoothness. Installed traces and operator-visible motion remain authoritative.

### Planning lock from the combined Checkpoint-3 + Checkpoint-5 evidence

1. **Keep the event-driven latest-wins visualizer admission.** It has both quantified Checkpoint-3 and operator-observed Checkpoint-5 support. Do not restore the display-refresh Python QTimer and do not raise Bubble logical cadence merely to chase panel Hz.
2. **Keep the runtime-purity work.** No QWidget/QPixmap/synchronous foreground fallback should return; none of the new evidence points back at image topology as the steady-heavy root.
3. **Historical pre-ingestion conclusion, superseded by CHK5 raw dual-display evidence:** Checkpoint-3 alone did not implicate transition draws, but CHK5 later proved a D0/high-refresh transition overdrive. CHK10 has already replaced that feedback loop. Do not repeat the optimization or restore it.
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

## Historical acceptance gate — superseded by CHK15 golden-baseline posture

The following was the pre-CHK15 rescue gate and remains useful historical context, **not the current admission rule**. The binding rule is now CHK15 neutral-or-better headroom work. Before CHK15 acceptance, R-87 was considered open until installed evidence demonstrated all of the following:

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




## Checkpoint-5 D1-only light -> heavy control — second installed validation

A second CHK5 D1-only run was supplied after the rare dual-display run. It is an important control because it separates the high-refresh D0 transition problem from the D1 residual crawl.

Trace health:
- **220,402 records**
- **0 dropped**
- **0 writer errors**
- writer priority successfully applied as **Windows below-normal / no priority boost**

Using the usage sampler's system-load rise as coarse phase boundaries:
- **light:** publication->draw **8.36 ms median / 14.50 ms p95**;
- **active heavy loading:** **13.24 / 24.50 ms**, p99 **47.66 ms**;
- **settled heavy:** **14.06 / 19.61 ms**, p99 **28.26 ms**.

Bubble remains essentially fixed at the authored ~90 logical publications/s. This independently confirms the main CHK3 finding: the new publication-driven admission path is not starving the producer or GUI; the remaining settled-heavy freshness loss persists downstream of admission.

The transition split is the important correction to avoid overgeneralizing the dual-display diagnosis:
- settled-heavy **idle** publication->draw: **14.34 ms median / 22.98 ms p95**;
- settled-heavy **transition-active**: **12.92 / 15.37 ms**;
- HUD heavy transition-active draw rate is only ~**92/s median**, compared with ~**90/s idle**.

So the uncapped `frameSwapped -> requestUpdate()` transition loop is a **real D0/high-refresh overdrive problem**, proven by the dual-display binary, but it is **not the primary D1 settled-heavy cause**. The transition-driver repair should be judged as a D0 waste/tail fix and an architectural correctness improvement. Do not claim it closes R-87 if D1 still carries ~14–20 ms heavy-load publication->draw age.

The existing fine-grained markers remain required for the D1 residual:
`QUICK_SYNC_CONSUME -> QUICK_SYNC_READY -> RENDER_BEGIN -> RENDER_DRAW`.

Decision rule remains unchanged:
- render-body delta dominant -> bounded C++/QRhi hot-seam spike may be justified;
- sync-ready->render-begin dominant -> investigate Qt/render-loop scheduling instead;
- no broad visualizer rewrite without trace evidence.


## 2026-09-15 CHK10 transition-driver repair — Qt-owned tick, per-display render gate

The rare CHK5 dual-display binary established a separate high-refresh defect on top of the remaining D1 heavy-load residual: D0 transition-active visualizer draws rose to ~286.9/s while fresh logical revisions remained ~89.9/s, and D0 heavy transition-active publish->draw rose to 24.15 ms median versus 6.94 ms idle. The later D1-only CHK5 control prevented overgeneralizing that result: settled-heavy D1 transition-active was 12.92/15.37 ms median/p95 versus 14.34/22.98 ms idle, so the transition feedback loop is a D0/high-refresh overdrive bug, not the primary D1 residual.

Research was deliberately multi-source before changing production:
- Qt `FrameAnimation` public documentation describes it as synchronized with Qt animation updates and explicitly recommends it over short-interval `Timer` for custom per-frame animation.
- Qt `QQuickFrameAnimation` source shows an infinite `QAbstractAnimationJob`, so it participates directly in Qt's animation driver rather than introducing an SRPSS clock.
- Qt threaded render-loop source explicitly switches to a system animation timer when any exposed window has `swapInterval == 0` (and in multiple-window/bad-vsync cases), rather than using buffer swap as the animation clock.
- Qt animation-driver source derives that fallback interval from the primary screen refresh rate.
- Independent KDAB scene-graph material confirms the separation among GUI sync, render-thread rendering, and `frameSwapped`; it was used as corroboration only.

That research rejected two tempting but wrong shapes:
1. **Do not restore a Python display-refresh timer.** That is the architecture the migration is removing.
2. **Do not use a bare global FrameAnimation as the whole answer.** On mixed refresh, Qt's fallback animation driver can tick from the primary-screen interval, so a bare job could overdrive a 60 Hz secondary or underdrive a faster secondary.

Current post-CHK9 implementation:
- `QuickFramePacer` keeps its historical diagnostics name but is now only a transition demand/lifecycle coordinator. It has no `QTimer`, no `frameSwapped` connection, no `QWindow.requestUpdate()` continuation loop, and no per-frame Python callback.
- `DisplayScene.qml` owns a `FrameAnimation`. Python publishes only transition active/inactive plus the bound display's nominal refresh Hz on lifecycle/display edges.
- On each native animation tick, QML advances a per-display due-time gate. If the display interval is due, it invokes `BackgroundRenderItem.update()`, the inherited C++ `QQuickItem` slot. At most one update is requested per native tick. Missed intervals are skipped, not repaid as a burst.
- `BackgroundRenderNode` still samples `TransitionRun` from monotonic time. Authored transition duration/progress and transition rendering semantics are unchanged; the change is only who supplies frame opportunities.
- Hide/pause/resume/retarget/retirement still gate demand explicitly. Starting native demand without a live QML root fails loudly; an idempotent inactive publication after root destruction is tolerated for clean teardown.

Source/static validation at this boundary: **29/29 directly executable architecture contracts green; all 896 Python files compile.** PySide/Windows rendering remains unexecuted in this container.

Acceptance for this repair is intentionally narrow and evidence-led:
- D0/high-refresh transition-active draw rate should fall from the CHK5 ~287/s overdrive toward the display's actual opportunity while transition duration and visible smoothness remain healthy.
- Bubble fresh logical cadence remains ~90/s; do not raise it to panel Hz.
- D1 heavy-load age is **not** expected to disappear from this change. Use the already-added `QUICK_SYNC_READY -> RENDER_BEGIN -> RENDER_DRAW` markers to decide whether the remaining D1 delta is sync work, post-sync/pre-render-callback render-entry time, or Python/OpenGL render-body time.
- Do not request another dual-display run merely to validate this repair; a D0-only high-refresh run can validate overdrive removal, and a routine D1-only run can validate the fine markers.

Known Qt public-API limitation to preserve in future handoffs: under `swapInterval=0`, Qt's fallback animation driver is based on the primary-screen interval. A high-refresh secondary may therefore not receive transition opportunities faster than that global driver. Do not silently add a second timer/clock to compensate. Measure first.


## 2026-09-15 CHK11 candidate — native-driver restart/retarget hardening

A post-CHK10 source audit found no surviving production frame-driving `frameSwapped` feedback; remaining uses are observation/trace or bounded smoke-tool frame boundaries. Three lifecycle details were tightened before installed validation:

- `DisplayScene.qml` now explicitly calls `FrameAnimation.reset()` when native transition demand starts, making the elapsed-time restart contract explicit rather than relying only on implicit animation-job restart state.
- `transitionFrameTargetHz` changes clear the per-display next-due deadline, so a live 60<->165 Hz retarget cannot carry one deadline computed from the previous display cadence.
- `QuickFramePacer.stop()` no longer clears its visibility pause flag. Demand and visibility suspension are separate owners; stopping demand while hidden cannot make a subsequent transition active until visibility explicitly resumes the pacer.

The gate still permits at most one `BackgroundRenderItem.update()` request per native animation tick and repays no missed intervals. Qt/PySide documentation independently confirms that `FrameAnimation.reset()` resets frame/elapsed values without changing running state and that `QQuickItem.update()` is the supported public slot for scheduling `updatePaintNode()` on `ItemHasContents` items. Those sources support the shape; they do not replace installed evidence.

Source-only preservation remains **29/29 GREEN** and all **896 Python files compile**. This environment has neither PySide6 nor `qmllint`, so QML load/render remains an installed checkpoint gate.


## 2026-09-15 CHK10 installed side-regression: hot mode change can reveal a dead live source

This is **not evidence against the successful publication-driven Quick pacing direction**. It is a separate visualizer activation/source-ownership regression exposed while attempting a D0 light -> heavy CHK10 validation.

At approximately **17:38:23**, the installed log shows `spectrum -> oscilloscope`:

- logical runtime stop/join succeeds;
- BeatEngine activation commits **generation=4 activation=4**;
- logical runtime restarts at the authored ~90 Hz cadence;
- authored technical config changes audio block size **128 -> 256**;
- the running PyAudioWPatch backend is restarted and logs `negotiated_block=256`;
- Oscilloscope then becomes `ready=True source=4/4`, yet repeated diagnostics show all-zero live energy and `source_age_ms=-1.0` while playback remains true.

The visualizer is therefore not blank because Quick failed to instantiate/draw the selected mode. The control identity and logical runtime survive, but the target is revealed with no authoritative live audio behind it.

The current line-mode source-ready contract is implicated: Oscilloscope/Sine use `get_latest_generation_with_waveform()` for source generation. The BeatEngine marks waveform generation as soon as raw samples are consumed, while `source_timestamp` comes from the authoritative analysis-frame commit. A raw zero/empty callback after restart can consequently make generation identity look fresh before authoritative live analysis exists. That is sufficient to explain `ready=True` + `source_age_ms=-1.0` + blank/idle-only visual behavior.

The same switch also exposes a second ownership risk: changing per-mode capture block size restarts the *live* WASAPI stream. Earlier 128<->256 restarts in the same run happened to recover, but the Oscilloscope restart reported success and did not restore useful live source state. Backend start success is therefore not proof of post-restart capture authority.

**Required repair, without architectural rollback:** strengthen playing line-mode reveal to require post-activation authoritative live-source evidence, and remove or properly transact live capture restarts caused by mode-specific block-size changes. Do not restore the old display-refresh QTimer pacer, QWidget/QPixmap presentation fallbacks, or synchronous image/runtime escape paths; CHK3/CHK5 installed evidence independently proves those removals improved freshness substantially.


## 2026-09-15 CHK12 hotswap root cause — orphaned FFT slot ownership

The CHK10 `Spectrum -> Oscilloscope` blank-card/idle-only failure is now pinned below Quick presentation. The installed log showed Oscilloscope activation identity advancing to 4/4 and at least one raw waveform callback arriving, while the serial analysis lane froze permanently at **8456 accepted / 8456 completed / 8455 published** and the logical runtime continued at ~90 Hz. That combination rules out “Quick failed to instantiate the new mode” and is stronger than the earlier preliminary suspicion of a dead WASAPI restart.

The actual ownership race was in `cancel_pending_compute_tasks()` + result completion. During hotswap the logical runtime is stopped, configuration changes invalidate the compute gate, but the public activation id intentionally remains old until the transaction commits. If the final old FFT callback returned in that interval, the old same-activation heuristic could interpret the newer gate as proof that a successor already owned the slot and leave `_compute_task_active=True`. With the logical producer stopped, no successor necessarily existed. After commit, every new audio frame was therefore held behind a phantom in-flight FFT forever.

Repair:
- every admitted FFT submission has a unique slot token;
- a completion may release only its own token;
- a stale callback cannot clear a genuinely newer token;
- a busy `lane.submit()` rejection cannot steal ownership because the rejected token rolls back to the previous real owner;
- stopping the lane clears active token, active flag and one newest pending source because stopped compute lanes intentionally suppress callback delivery;
- Oscilloscope/Sine playing-state readiness now also requires a matching authoritative analysis timestamp. Matching raw-waveform generation alone cannot reveal a supposedly-live target. Paused authored idle is preserved.

Direct real-engine regression execution proves the installed race shape, inverse newer-owner safety, busy-rejection safety and stop cleanup. The broader source boundary remains **29/29 GREEN** and all **896 Python files compile**. Audio block-size 128/256 capture behavior is deliberately unchanged in this checkpoint: PortAudio/WASAPI restart semantics remain a separate resilience question, not part of the proven root-cause repair.

This regression does **not** invalidate the performance architecture. Do not restore Python display-refresh pacing, generic QWidget/QPixmap publication, or synchronous fallback paths. The immediate performance queue after installed hotswap validation remains D0 native transition-driver validation followed by D1 fine-marker localization.


## 2026-09-15 — CHK14 diagnostic localization: split the Python/OpenGL render body before another run

No rendering policy is changed in this slice. CHK3/CHK5 already prove that the publication-driven Quick architecture is substantially better; CHK10/13 preserve the Qt-owned transition driver and honest native-rate diagnostics. The next unresolved D1 question is where the settled-heavy post-sync time actually goes.

The explicit `--frame-trace` now keeps the same binary format/version while adding nested render-only events: `RENDER_PREP_READY`, `RENDER_HOST_BEGIN`, `RENDER_GL_STATE_READY`, `RENDER_MODE_BEGIN`, `RENDER_MODE_READY`, `RENDER_HOST_READY`. This splits the old `RENDER_BEGIN -> RENDER_DRAW` bucket into node preparation, clip setup, render-host/OpenGL-state work, actual selected-mode drawing, state restoration and post-host bookkeeping. The reporter emits both full-run distributions and timeline-window summaries. Old traces remain readable because the new event IDs are optional.

Static audit found `_InheritedGlState.capture()`/restore on every visualizer draw, including multiple `glGet*`/`glIsEnabled` queries. Qt 6 documentation says `QSGRenderNode` must assume arbitrary incoming state, while `QQuickWindow` also says external-command handling is implicit for render nodes and Qt 6 limits useful `changedStates()` reporting to viewport/scissor. Therefore the current state fence is a **candidate overhead**, not something to remove from documentation alone. Installed sub-stage timings decide.

The same evidence rule applies to the bounded C++/QRhi spike: PySide/Shiboken necessarily routes the C++ virtual render callback into the Python override, but no source consulted here quantifies SRPSS's GIL cost. C++ becomes active only if installed trace shows the render-host/mode-render portion is the heavy-load delta. If `QUICK_SYNC_READY -> RENDER_BEGIN` dominates instead, C++ rendering is the wrong fix.

Source preservation: **51/51** directly runnable contracts green; **896/896** Python files compile.


## 2026-09-15 — CHK14 installed D1 torture run / CHK15 diagnostic freeze

This assessment was intentionally formed **before** asking the operator how the session felt. The evidence archive is `cfdabe39-1d4c-4682-8335-56e5f1964c7d.zip`; the runtime reports source head `22dd8d4d4c5290e5a82f6bcea9f6555e9fd8ae78`. The run is D1-only and deliberately abusive: repeated visualizer mode/shape changes, widget disable/re-enable work, two Settings lifecycles, and long settled windows.

### Evidence quality
- frame trace: **1,710,531 records**, **0 dropped**, **0 writer errors**; all CHK14 nested render markers are present;
- async log queue: zero dropped/debug/info/other records and zero writer errors at shutdown;
- Qt/QML capture: **0 messages / 0 warnings / 0 errors / 0 critical**;
- native-fault capture: no fault;
- every Settings/runtime destruction barrier completed;
- usage telemetry shows a clean light period followed by an external-load step beginning around **18:54:44**, after which system CPU remains roughly ~40% for the heavy portion.

### Clean Bubble light vs settled-heavy decomposition
Use the settled windows, not whole-run aggregates contaminated by torture:

| Stage | Light `18:46:50–18:54:20` median / p95 | Heavy `19:02:45–19:06:50` median / p95 | Reading |
|---|---:|---:|---|
| publish→GUI wake | **0.10 / 0.66 ms** | **0.43 / 2.49 ms** | worsens but remains small |
| GUI snapshot→Quick sync | **4.96 / 5.86 ms** | **5.32 / 8.08 ms** | real pre-sync scheduling tail growth |
| Quick sync work | **0.030 / 0.056 ms** | **0.065 / 0.148 ms** | negligible; not the bug |
| sync-ready→render-begin | **1.04 / 1.53 ms** | **1.76 / 7.09 ms** | **largest newly-localized heavy tail** |
| render-begin→draw | **2.39 / 5.51 ms** | **1.66 / 6.78 ms** | not dominant; median improves |
| actual mode draw | **0.31 / 2.53 ms** | **0.25 / 4.31 ms** | secondary tail only |
| inherited GL-state capture | **0.21 / 0.43 ms** | **0.13 / 0.29 ms** | specifically not the heavy delta |
| publish→draw | **8.64 / 13.25 ms** | **13.32 / 17.07 ms** | residual remains visible in freshness |

The new fine markers therefore answer the CHK14 fork: **the next target is Qt/render-thread scheduling/admission under external CPU contention, not a C++/QRhi renderer migration and not removal of the inherited-GL-state fence.** The Python sync body is tiny. The render body has some tail growth but does not own the median degradation; the largest p95 expansion is the wait from completed sync to render-node entry, with a smaller snapshot→sync tail increase.

The Windows/Qt event-loop evidence is consistent with scheduling contention rather than a deterministic renderer cost: event-loop period p95 rises from roughly **0.85 ms light** to **~1.96 ms settled-heavy**, while sync-ready→render-begin p95 expands by ~5.6 ms. This is correlation, not yet a scheduling-policy prescription. Do **not** jump directly to boosting the render thread. First attribute the native render thread at low cadence (priority/CPU/runnable or context-switch evidence where practical) and research Qt/Windows scheduling behavior.

### CHK12 hotswap repair receives strong installed validation
The torture run contains **24 mode activations**, i.e. four complete cycles through:

`Bubble → DevCurve → Sphere → Spectrum → Oscilloscope → Sine → Bubble`

including cycles on both sides of a full Settings runtime teardown/reconstruction. Every activation obtains a fresh post-reset analysis frame. All **eight** Oscilloscope/Sine activations become live with finite authoritative source ages around **8–10 ms**. The analysis lane continues monotonically through the run and shutdown with zero busy/stopped/cancelled submissions; the CHK10 phantom-slot failure does not recur. This is strong log-level installed validation of the CHK12 slot-token/readiness repair.

### CHK10 native transition driver receives D1 installed validation
During transition-active D1 samples, Qt's global animation driver ticks around **166 Hz** (primary-screen cadence), but the per-display gate issues retained-background update requests around **60 Hz**. Bubble logical revisions remain ~90/s; D1 visualizer draw rate rises only from ~90/s idle to ~93/s transition-active. The old as-fast-as-renderable `frameSwapped→requestUpdate()` loop is therefore not present on D1.

This does **not** substitute for the remaining D0-only high-refresh check. The rare CHK5 dual-display trace proved D0 used to overdrive ~287 draws/s; a future D0-only run can confirm the new gate bounds D0 near its display opportunity. Do not ask for another dual-display run unless a genuinely cross-display question returns.

### Torture does not leave a persistent degradation tail
- heavy pre-torture publish→draw: **13.72 / 16.90 ms** median/p95;
- heavy settled after repeated mode/shape churn + first Settings reconstruction: **13.28 / 17.02 ms**;
- heavy after the second Settings reconstruction: **13.97 / 16.91 ms**.

The run therefore shows no accumulating freshness collapse from repeated hotswap/Settings/widget churn. Lifecycle barriers complete each time, and there is no QML/native-fault evidence. Logs cannot prove every visual detail, but they do reject the old pattern of hidden teardown/ownership accumulation as the dominant performance problem in this session.

### CHK15 planning decision
1. Preserve this run as an **assessment-only** checkpoint; no production optimization is justified in CHK15.
2. Make Qt/render-thread scheduling attribution under CPU pressure the active R-87 research target. Prefer low-rate native-thread telemetry and multi-source Qt/Windows research; avoid another hot-path logger.
3. Keep C++/QRhi **shelved**. Reactivate only if later installed traces show `RENDER_MODE_BEGIN→RENDER_MODE_READY` or other render-body work becoming the dominant load-dependent delta.
4. Keep `_InheritedGlState` fence intact; this run does not support it as a performance culprit.
5. Keep Bubble ~90 Hz logical cadence and the event-driven latest-wins admission architecture.
6. Keep the QML `FrameAnimation` per-display transition gate; D1 evidence validates its intended bound.
7. D0-only transition validation remains outstanding; no dual-display rerun is required.
8. Once this blind diagnosis is checkpointed, operator subjective feel can be compared against the evidence without contaminating the initial attribution.

### Secondary anomaly retained without contaminating R-87 attribution
`screensaver_perf.log` emitted two huge `_on_rotation_timer` gap warnings (~172,987 ms near 18:55:22 and ~152,734 ms near 19:05:29), tagged `unknown_ui_thread_stall`. They occur around manual/image-transition/timer-reset activity and are **not accompanied by a matching visualizer freshness collapse, failed lifecycle barrier, QML fault, or trace loss**. Treat this as a separate timer-oracle/reset-semantics audit item: prove whether manual rotation/re-arm invalidates the expected-period baseline before interpreting these warnings as real UI-thread stalls. Do not use them to overturn the CHK15 scheduling diagnosis.

## CHK15 operator acceptance / golden-baseline decision (2026-09-15)

After the blind CHK14 runtime evidence analysis was frozen into CHK15, the operator reported the mixed-refresh heavy run felt **great on both displays at
all times**, with **no noticed crawl**. D0 remained smooth despite Bubble correctly remaining near its authored ~90 Hz logical
cadence on a ~165 Hz panel, and slide transitions — historically the strongest heavy-load canary — were almost perfectly smooth.

This subjective report agrees with the architectural direction but changes the acceptance posture: CHK15 is now the **golden
performance/freshness baseline**, not merely an intermediate R-87 checkpoint. Remaining work is scheduling-starvation/headroom
research. Any change must be neutral or better against CHK15 in both installed metrics and operator-visible smoothness. It is not
acceptable to improve one percentile by reducing Bubble cadence/reactivity, restoring duplicate display-refresh draws, adding
fallback ownership/timers, or worsening mixed-refresh/transition/hotswap behavior.

Reference installed baselines:
- D1 single-display heavy settled publication→draw ~13.3 ms median / 17.1 ms p95;
- D1 mixed-refresh heavy ~12.6 / 16.9 ms;
- D0 mixed-refresh heavy ~7.5 / 25.4 ms, with the fat p95 **not operator-visible as crawl in this accepted run**;
- CHK14 D1 torture trace adopted/frozen by CHK15: 1,710,531 records, 0 dropped, 0 write errors;
- CHK12 hotswap fix survives repeated modes, Settings rebuilds and widget/shape churn;
- native per-display transition gating remains mandatory; the historical unbounded swap-feedback loop stays forbidden.

At the CHK15 decision point, the primary residual was still framed as Qt/render-thread scheduling/admission headroom under
contention. The CHK16 physical scheduler trace below supersedes that hypothesis by ruling ordinary runnable starvation out for the
captured D1-heavy condition. CHK15 remains the bisect/rollback reference if any later experiment makes motion, slide transitions,
frame freshness or latency worse.

## 2026-09-15 — CHK16 external scheduler-attribution tooling (no production change)

CHK15 remains the golden rollback/bisect baseline. CHK16 adds only an external evidence lane: `tools/scheduler_trace_capture.py`
uses Windows Performance Recorder's built-in `GeneralProfile.Light` and defaults to **memory mode** for a short capture so the
observer does not add continuous ETL disk I/O to the workload. It records WPR begin/end markers, wall/perf-counter anchors, one
collector-health snapshot before stop, and optional post-capture `xperf tracestats`. It does not poll or query the SRPSS render hot
path and it changes no thread priority.

The first capture is deliberately **D1 pure-heavy**, not light→heavy. CHK14 already supplies the clean light comparison; this new
trace exists to answer one missing question during the known heavy condition: when `QUICK_SYNC_READY→RENDER_BEGIN` grows, is the
render thread predominantly **Ready** (OS scheduler/CPU starvation), **Waiting** (Qt queue/wake/resource admission), or already
**Running** (unisolated render-thread work)? In WPA, use CPU Usage (Precise), filter to the existing render-thread TID carried by
lifecycle telemetry, and inspect Ready(s), Waits(s), SwitchInTime, ReadyingThreadId/Process and priority/context-switch evidence.

A later production candidate must still receive a low-load sanity check before becoming a new baseline, but repeating light inside
this first attribution capture is unnecessary. No D0 or dual-display run is requested by this lane.



## 2026-09-15 — CHK16 physical scheduler attribution result / CHK17 narrowed seam

The one planned D1 pure-heavy Windows scheduler capture was completed. This closes the initial scheduler fork; it must not become a
recurring operator burden. The 60.101 s capture was healthy (no WPR loss reported) and identified Quick render TID `14044`.
Offline reduction found **63.920% Waiting / 35.050% Running / only 1.004% Ready**. Ready->Running latency was
**0.002600 ms median / 0.004900 ms p95 / 0.073238 ms p99** across 100,882 ready/run pairs.

**Conclusion:** ordinary Windows runnable starvation is **not supported by this trace**. Do not boost render-thread priority on the
basis of R-87's remaining tails.

The existing `QUICK_SYNC_READY -> RENDER_BEGIN` label also required correction. In the physical capture it measured
**1.9918 / 5.5349 ms median/p95**, but the interval was ~76.9% Running / 22.3% Waiting / 0.7% Ready overall and ~42.8% Running /
55.3% Waiting / 1.9% Ready in the p95 tail. It is therefore a **post-sync/pre-render-callback render-entry interval**, not a pure
Windows scheduling wait: Qt continues scenegraph work after SRPSS's sync callback before eventually entering the Python
`QSGRenderNode.render()` callback.

Most Waiting time in that interval ended while SRPSS threads sharing a known **CPython-created thread bootstrap** were running
(~86.7% overall / ~81.1% p95 tail). That does **not** identify the IO pool, audio lane, or any specific worker and does not prove GIL
contention. It does make Python callback/GIL admission a bounded hypothesis worth testing before any scheduler-policy change.

CHK17 adds explicit-`--frame-trace`-only markers around whole visualizer analysis and around `_smooth_analysis_bars(...)` separately.
The latter is useful because it is pure Python; `tools/frame_trace_report.py` now reports its temporal overlap with all and p95-tail
render-entry gaps. No ordinary-runtime timer/thread/pacer is added. No cadence/reactivity/smoothing behavior is changed.

The raw ETL was very large and is now explicitly a **local-only temporary artifact**. It must not be uploaded, placed in a GODZIP or
requested again by default. The capture tool now reduces locally to `scheduler_attribution.json/.txt` and deletes the ETL after a
successful reduction unless `--keep-etl` is explicitly selected for local deep-dive work.


## 2026-09-15 — CHK17 physical overlap result: smoothing exonerated, bounded GIL-timeslice A/B admitted

CHK17's ordinary D1-heavy frame trace produced **299,893 records (3 dropped, 0 write errors)** under a stronger external CPU load than CHK14's golden-heavy window (roughly ~55% versus ~40% system CPU through much of the settled portion). The new markers falsified the easiest Python-side explanation rather than confirming it.

`_smooth_analysis_bars(...)` measured only **0.036 / 0.067 ms median/p95**. Although smoothing temporally intersects many long render-entry gaps because the lanes run concurrently at high cadence, it occupies only **0.26% of all `QUICK_SYNC_READY -> RENDER_BEGIN` gap time and 0.42% of p95-tail gap time**. It is not a credible repair target. Do not reduce smoothing quality/cadence.

Whole visualizer analysis measured **1.899 / 3.264 ms**. Render-entry gaps intersecting analysis were longer (**6.664 ms median**) than those with no overlap (**2.875 ms**), but measured analysis occupied only **12.77% of all gap time / 21.49% of p95-tail gap time** and render entry did not strongly cluster immediately after analysis completion. The result supports broader concurrent-Python/GIL pressure as a hypothesis, not `compute_bars_from_samples()` itself as the stall.

The full-run render-entry distribution was **5.310 / 8.934 ms** and settled windows remained about **5.32 / 8.89 ms**. That stable ~5 ms floor under contention is close to CPython's default thread-switch interval and matches the mechanism already documented by the project's older GIL-contention harness. Because correlation is insufficient, CHK18 adds an **opt-in only** `--gil-switch-1ms` A/B. Absence leaves interpreter policy untouched; admission applies `sys.setswitchinterval(0.001)` for the process and logs previous/active values.

This is not a new architecture and not a permanent optimization. It changes no Qt priority, display pacing, logical Bubble cadence, analysis cadence, renderer, transitions or fallback policy. Accept only if an installed D1-heavy B run at comparable load improves the render-entry/freshness path **and** is subjectively neutral-or-better against CHK15. Otherwise reject it and continue at the Qt/scenegraph callback boundary. No repeat ETL/WPR capture is needed.

## 2026-09-15 — CHK18 1 ms GIL A/B rejected; CHK19 native render attribution complete; CHK20 predecessor trace

The CHK18 D1-heavy B run explicitly activated `--gil-switch-1ms`; startup logged **5.000 ms -> 1.000 ms**, so this was a valid installed A/B rather than a no-op launch. The targeted render-entry interval did **not** improve: `QUICK_SYNC_READY -> RENDER_BEGIN` moved from CHK17 **5.310 / 8.934 ms median/p95** to CHK18 **5.592 / 8.905 ms**. Visualizer analysis worsened **1.899 / 3.264 -> 3.724 / 5.519 ms** and publish->draw p95 worsened **18.902 -> 22.771 ms**. The operator also reported that **the 1 ms run felt worse**. Under CHK15's neutral-or-better rule that subjective regression is binding. The global switch-interval experiment is rejected and removed; do not revive it as product policy.

CHK19 then used Qt's native `QSG_RENDER_TIMING` output for one short D1-heavy attribution run. It produced **5334** native frame summaries: total **10 / 17 ms median/p95**, sync **0 / 4 ms**, render **9 / 14 ms**, swap **0 / 4 ms**, with ~**88.27%** of component time in native render. One manual **Burn** transition was identifiable from ~**22:38:27 -> 22:38:36** (~8.535 s). Splitting it out leaves the conclusion intact: steady pre-transition render ~**7.96 ms mean / 13 ms p95**, Burn ~**9.77 ms / 17 ms**, steady post ~**7.83 ms / 12 ms**; sync/swap barely move. Burn therefore adds genuine render work but does not manufacture the steady-state render dominance.

Absolute CHK19 native timings are **observer-contaminated** and must not become a baseline. `QSG_RENDER_TIMING` generated **26,791** high-rate `qt.scenegraph.time.*` DEBUG messages. SRPSS's process-wide Qt capture synchronously wrote/flushed them and CHK19 also echoed them to the terminal, adding work on the threads being observed. Do not request a repeat simply to remove this contamination. CHK20 retires the in-app `--qsg-render-timing` admission; the token is retained only as a mode-parser compatibility no-op, the historical reducer remains, and externally enabled scenegraph-time DEBUG chatter no longer echoes to the console.

The qualitative phase result remains useful and resolves a prior wording error. `QUICK_SYNC_READY` is emitted at the end of the visualizer item's sync/updatePaintNode work, while `RENDER_BEGIN` is emitted only when Qt later reaches `VisualizerRenderNode.render()` during scene rendering. Therefore `QUICK_SYNC_READY -> RENDER_BEGIN` is **not a pure scheduler/callback wait**. It includes native scenegraph rendering of content that precedes the visualizer node. This agrees with the CHK16 ETW result that the render thread was not spending meaningful time Ready-but-unscheduled.

The visualizer's own internal stages remained broadly CHK17-shaped despite CHK19's noisy observer (`RENDER_PREP_READY -> RENDER_HOST_BEGIN` ~**0.657 / 5.798 ms** CHK17 vs **0.549 / 5.638 ms** CHK19; actual mode draw ~**0.298 / 3.162 ms** vs **0.318 / 3.911 ms**). Native render dominance is therefore not evidence that Bubble's mode renderer suddenly costs ~8–10 ms.

CHK20 adds explicit-`--frame-trace`-only markers around the predecessor full-screen `BackgroundRenderNode`: render begin, texture ready, draw begin, draw ready, render ready. The node is z=0 and precedes the visualizer subtree; its marker `auxiliary` stores transition run id (`0` steady), allowing ordinary and transition frames to be separated. `tools/frame_trace_report.py` now reports these stages and their overlap with the visualizer render-entry interval. This is diagnostic-only and adds no ordinary-runtime sink/timer/pacer.

Measure before changing GL state fences. The background steady path contains OpenGL state queries/restoration and the visualizer clip/stencil path still has a repeatable p95 tail, but neither is authorized for deletion merely because it looks suspicious or because documentation permits fewer declared states. Correctness and CHK15 visible behavior remain binding.

No dedicated CHK20 A/B is required. Let the new predecessor markers ride on the **next otherwise-useful ordinary D1 `--frame-trace` run**. C++/QRhi remains conditional and is still not justified by current evidence.

