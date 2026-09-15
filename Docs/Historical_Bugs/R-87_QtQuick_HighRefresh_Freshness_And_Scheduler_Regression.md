# R-87 — Qt Quick High-Refresh Freshness / Scheduler Regression

Status: **[x] COMPLETELY FUCKED — OPEN / NOT SOLVED**

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

R-87 remains **[x] COMPLETELY FUCKED** until an installed build demonstrates all of the following:

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

