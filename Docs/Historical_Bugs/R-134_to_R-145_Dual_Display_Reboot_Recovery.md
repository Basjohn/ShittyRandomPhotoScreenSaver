# R-134 through R-145 | Dual-display collapse recovered after Windows restart

Date: 2026-10-09  
Status: **PHYSICALLY RECOVERED / ROOT CAUSE UNKNOWN**; closed as an active performance blocker by operator report, not as a proven application fix.

## Symptom and causality

On the RTX 4090, mixed-refresh dual-display (2560×1440 + 3840×2160) Windows desktop, SRPSS abruptly became severely laggy at launch, during transitions and in ordinary interactive use, even when the widgets were disabled. The same host could run demanding Unreal Engine 5 games normally. After a full Windows **restart**, the operator reports that SRPSS performance returned to near-perfect. **Neither R144 nor R145 produced that recovery** in the operator's account. Their concurrency/containment changes remain useful source-level safeguards, but cannot be credited as the cause.

Two new archives `logs13afa0ec4116Godzip144.zip` and `logs13afa0ec4116Godzip145.zip` are **both post-restart** runs. The earlier distressed traces referenced in the R145 handoff were recorded before recovery. Comparison is directional, not an A/B controlled application version experiment. R144 includes two launch sessions; the R144 final cache/handle figures below refer to its second (02:17–02:19) session. Durations, transitions, window generations, instrumentation, and Visualizers differ between runs.

## Historical measurements | before restart versus after

| Metric | Earlier bad state (reported R134–R143) | Recovered R144 | Recovered R145 |
|---|---|---|---|
| Operator physical verdict | Severe dual lag, including widgets disabled | Near-perfect after system restart | Near-perfect after system restart |
| 4K/display-1 steady swap gaps >25 / >50 / >100 ms | **49 / 10 / 1**, from `logs13afa0ec412.zip` R134; max **243 ms** | **11 / 2 / 0**; max **94.647 ms** | **13 / 4 / 0**; max **80.634 ms** |
| 4K steady swap median / p99 | Historical aggregate not supplied in these two new archives | **11.020 / 13.956 ms** | **11.028 / 14.293 ms** |
| 4K render background begin→ready median / p95 | Prior R143 ordinary transition draw median ~**0.9 ms** (not same end-to-end measure) | **0.464 / 0.963 ms** | **0.437 / 0.982 ms** |
| First-use Qt Quick cycle / image preparation | R143 early 1440p **92 ms** and 4K **105 ms** Qt sync/render spikes; one no-widgets startup image-prep **212 + 137 ms**, plus **71 ms** worker-complete→GUI callback | Startup image worker **123.2 + 129.9 ms** in first session (different images/configuration) | **197.6 + 176.9 ms** worker prescale and **257.68 ms** worker-complete→GUI delivery on first startup; GUI startup widget callbacks also active |
| Foreground event-loop lateness, final session summary | R143 no >25 ms wake delays in one all-widgets-disabled run; not an explanation for the physical regression | p95 **1.15 ms**, p99 **1.31 ms**, >25 **1** | p95 **1.10 ms**, p99 **1.60 ms**, >25 **2** (one >50) |

The R134 and recovered >25 ms counts have different measurement windows; treat them as descriptive evidence, **not normalized rates or definitive statistical improvement**. A render trace may have idle/non-rendering gaps, startup and teardown, and monitor-specific presentation behavior; steady-swap statistics above use `tools/frame_trace_report.py` lifecycle-aware filtering. R145 raw all-gap maximum was ~6.67 seconds around a lifecycle/idle gap and is **not** a 6.67-second steady render stall. The user's physical verdict is the primary acceptance evidence.

## Post-restart image cache and speculative processing audit

| Signal | R144 (second session, final) | R145 (final) | Meaning |
|---|---|---|---|
| Cache size/cap | 4/16 objects; 73.8/256 MiB | 5/16 objects; 105.5/256 MiB | Bounded; no forced churn/eviction during sample |
| Scaled foreground hits / misses | 8 / 2 (80.0% hit) | 14 / 2 (87.5% hit) | Warmed derivatives reused |
| Scaled prefetch complete / requested | 12 / 13 | 19 / 19 | R144 one source still incomplete at shutdown, not a proven stuck queue; R145 completes all |
| Prefetch resumes scheduled / run | 5 / 5 | 8 / 8 | Deferred liveness observed; no stranded registered resume in sample |
| Protected near-future | protection log and 2 retained in late R144 cycles | protection log and 2 retained in late R145 cycles | Respects next-two derivative protection |
| Shared-memory segments created / consumed / live at final shutdown | 14 / 14 / **0** | 21 / 21 / **0** | No dangling final shared memory; close/unlink failures 0 |
| Binary speculative parent handoff median / p95 / bytes | 7.149 / 14.954 ms, 269,107,200 bytes, 12 handoffs | 8.148 / 19.654 ms, 446,054,400 bytes, 19 handoffs | Still meaningful copy pressure; cannot infer scheduler priority solely from timing |
| Image-worker authority failures | **0** | **0** | Foreground authority intact in sampled transitions |

Cache logs show repeated scaled `Cache hit` followed by intentional `Removed from cache` as the foreground **consumes** the derivative. These are not budget evictions; `evictions=0`. Additional speculative lookahead fills the cache again. R145 source releases cache logging and evicted-image last references outside the mutex; R144 source places the existing parent-side speculative listener at native below-normal priority, distinct from the Qt rendering thread and from the project's queue-ordering `TaskPriority.LOW`. Neither optimization can be individually measured as a cause of the reboot recovery from these two captures, and the R145 cache-lock change is not directly observable as mutex hold duration in current logs.

## Process, thread, handle and memory lifetime

- **R145:** usage samples every 15 s across ~3 min show **57 application-family threads** through sample 8, then **73** from sample 9 onward when the process topology briefly changes **3 processes/2 children → 4/3 → 3/2** during Settings/runtime replacement. After that replacement the count remains 73 for five samples, rather than increasing each interval. The 16-thread step is **not proof of a leak**, but short runs do not establish overnight durability. R144's second launch similarly steps 54→70 when the extra process appears.
- Independent native handle sidecar for the R145 main PID: **1773 → 1953 → 1955 → 1914** at approximately 0/60/120/180 s. After startup this **plateaus and declines**. R144's second sidecar: **1747 → 1917 → 1905** at 0/60/120 s. The startup rise must not be misreported as a persistent slope. The sidecar's `forced=true` refers to its controller stopping, **not** an SRPSS native crash.
- R145 at the end: ~**898.6 MiB main RSS**, ~**1836.1 MiB main private commit**; private commit fluctuated around **1267–2045 MiB** in later samples while resident memory stayed roughly **855–920 MiB**. The final sample had ~**1018 MiB GPU dedicated memory**. Large private-commit oscillations are a **watch item**, not proof of monotonic growth or image-cache leakage. Longer unattended comparison remains the owner of memory-slope claims (see R-97 and R-84).
- R145 `native_faults.log` records clean capture enable/close only. `screensaver_qml.log` records 0 Qt/QML messages. R144 had two clean native sessions and only one unrelated `QFont::setPointSize(-1)` warning in its first session; none in its second.

## Suspected external state (unproven)

1. **Most likely candidate:** a stale Windows graphics-session/DWM/driver presentation or cross-monitor scheduling state, especially with mixed refresh, OpenGL Qt Quick scenes, and multiple swap chains. UE5 can remain smooth if it uses a different present/API path. No ETW, PresentMon or GPUView capture of the bad state exists to prove this.
2. Alternate: long-running GPU-driver memory residency/allocator/synchronization trouble or OS session-wide resource contention, reset by the restart.
3. Alternate: an unrelated overlay/hook/capture/desktop-management process disrupting Qt's window presentation while leaving a fullscreen game less affected. Do not assert one was present without evidence.
4. Less likely as the **primary reboot-resolved root cause**: SRPSS foreground cache contention, prefetch listener priority or transition draw shader work; the isolated source fixes remain valid but the reboot itself was decisive.

If the condition reappears, preserve **bad-state diagnostics before restarting**: Windows uptime, NVIDIA driver and display refresh/HDR/VRR configuration, DWM/monitor configuration, GPU engine and VRAM metrics, presence of overlays/capture hooks, both-display `--frame-trace --usage --handles` and a targeted PresentMon/ETW graphics trace if available. Compare the *same binary and screen/transition configuration* immediately before and after reboot. Avoid arbitrary process-priority overrides or Qt repaint/scheduler loops. Do not reopen the P0 live blocker on a speculative explanation alone; reopen upon reproducible physical degradation.

## Source corrections worth keeping (separate incidents)

- R139/R141: `QRunnable.create()` ownership/callable lifetime and serial generation-owned idle `NoStage` work restored crash-free startup in operator tests. R142's special traced-background NameError was fixed in R143. Do not attribute either to the older dual-display lag.
- R144: speculative parent response-listener native thread priority demotion; generation/foreground queue-pump admission fence and liveness continuation. Keep R-52/R-65/R-82/R-87/R-99 prefetch, cache, latest-wins and no-scheduler guardrails.
- R145: release cache logging and large-QImage last references **after** unlocking, with accounting/protection unchanged.
- R146 operator-directed timing: ordinary dual transition display separation now **400 ms** (was 800 ms), with duration compensation using the same constant; **first-image stagger remains 200 ms**. This is a preference change, not a performance-root-cause fix.

## Acceptance/closure

- [x] Operator reports both displays smooth after full Windows restart, with widgets enabled in R145.
- [x] Recovered R144/R145 log review: cache hit/consumption, prefetch resumption and no final shared-memory leak; handles plateau; no R145 native or Qt errors.
- [x] Source-level cache lock boundary and parent speculative listener admission improvements retained.
- [ ] **No automated overnight assurance** from these short captures. Keep existing independent R-97 lifetime/dormancy validation, without reopening the recovered P0 investigation.
- [ ] Root cause remains unknown. If observed again, compare the same binary pre-/post-restart and collect OS presentation evidence *before* rebooting.
