# R-97 — Overnight Main-Process Private Commit Growth

Date: 2026-09-25  
Status: AWAITING VALIDATION — root cause found and fixed 2026-09-26 (thread churn × GL-driver per-thread state); awaiting an unattended physical run

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure

Main-process private commit grew from 1137 MB to 2527 MB over the ~5.6 h single-display overnight run of
2026-09-25, and passed 2.9 GB after the morning monitor rebuilds (R-96).

`tools/memory_slope_report.py` on the existing `--usage`/`--life` logs, warm plateau (after 20 min), per process:

| Process | Span | Private commit | USS | RSS | Handles | Image cache | VRAM dedicated | VRAM shared |
|---|---|---|---|---|---|---|---|---|
| 2026-09-22 08:01 | 6.1 h | +125.2 MB/h | +32.4 MB/h | +32.0 MB/h | +25.4/h | −0.8 MB/h | +1.3 MB/h | 0.0 |
| 2026-09-25 02:17 | 5.3 h | +127.3 MB/h | +33.6 MB/h | +33.5 MB/h | +18.3/h | −0.3 MB/h | +0.4 MB/h | 0.0 |

The step at a 1 → 2 display rebuild was +373 MB (09-22) and +387 MB (09-25) of private commit, of which +137 to
+152 MB was dedicated VRAM.

## What The Evidence Rules Out

- **Bounded caches.** The decoded image cache (`cpu_cache_bytes`, ~190–220 MB over 10 images) is flat across both
  plateaus. Prefetch stays bounded (R-82).
- **GPU texture churn.** Dedicated and shared VRAM are flat, so replaced wallpaper textures are released.
- **The rebuild step as retention.** The measured steps add a second display, with its own windows, scene graphs,
  QML roots and swap chain, which the VRAM share shows. Retention across rebuilds needs repeated equivalent
  rebuilds that settle to the same display count (R-84 method).
- **Python-level growth.** On the Linux/Xvfb soak (real app, one 1440p display, 5 s rotation) private memory
  plateaued at ~870–950 MB. The interpreter's allocated blocks rose by ~30 per rotation. 300 FEEDS
  refresh-plus-artwork cycles stayed bounded. Per-rebuild growth on Linux was glibc free-list retention (arena
  free 588 → 1001 MB) with live allocations bounded, which is a Linux allocator property.

## What Was Retained And Fixed

PySide parents every `QQuickWindow.createTextureFromImage()` result to the window's Python wrapper. The retained
background's `QSGImageNode` owns and deletes the C++ texture, so every upload left one dangling `QSGTexture` wrapper
alive for the window's lifetime. The probe counted 40 wrappers for 40 images, and ≤1 after the fix
(`_release_owned_texture_wrapper`). Each wrapper is small, so this fix alone cannot account for +125 MB/h.

## Original Hypotheses (Superseded By The Root Cause Below)

Private commit grows about four times faster than USS. The ~93 MB/h difference is memory that is committed but no
longer resident: written once, never touched again, and trimmed from the working set. That is the signature of
retention, or of allocator/driver commit that is never reused. It did not reproduce on Linux. The leading
candidates are the Windows-only paths the Linux soak does not run:
- Gmail IMAP refresh, whose cadence matches the handle slope at ~+1.5 handles per refresh;
- WASAPI/PyAudio visualizer capture;
- the WinRT media session;
- PDH system stats;
- the OpenGL driver's user-mode allocations.

Attribution belongs on Windows: one `--usage --life --handle-attribution` run, then one-family-off A/B runs, read
with `tools/memory_slope_report.py`. The Gmail per-connection TLS change (R-98) alters that path; judge it
from the new run, not from this evidence.

## Update: The Fixed Part Of The Commit Gap (R-99)

The flat, never-touched commit is largely numpy's OpenBLAS thread pool: ~23 threads × a committed buffer each on the 24-CPU machine, which is ≈ 700 MB in the main process and again in the ImageWorker (816 MB private against 155 MB resident all night). It is now one thread (`core/native_threads.py`). That explains the fixed gap, not the slope. The slope stays open here.

## Root Cause (2026-09-26): Thread Churn × NVIDIA Per-Thread State

**Category.** `tools/win_memory_map.py` maps of the real saver, running invisibly (opacity 0, click-through) on the
operator's machine with the displays asleep, put the whole slope in one 1 GB read/write `VirtualAlloc` reservation.
Its commit grew +55.6 MB in 25 min (~133 MB/h), only ~25% resident. Its content is the NVIDIA OpenGL driver's own
heap: 218,000 pointers into `nvoglv64.dll` and driver assembly shader text. Write-combined driver memory, the heap,
large heap blocks and CPython arenas were flat or cache-bounded.

**Owner.** Diffing that heap over four idle minutes showed one ~72 KB driver object added about every 3 s. Each
holds a table of ~125 slots pointing at one static driver stub (a per-thread GL dispatch table in its "no current
context" state) and a per-thread RNG state. A Qt Quick window alone stayed flat (+5.6 MB/h) until a short-lived
Python thread was added every 50 ms; then it grew 34 MB per 30 s, ~57 KB per thread. The driver keeps per-thread
state for every thread a GL process ever creates and, at least with the displays off, never returns it.

SRPSS created threads continuously (external census of the running saver, 4 min):

| Source | New threads | Lifetime | Driver commit |
|---|---|---|---|
| `ProcessSupervisor` heartbeat: a new `threading.Timer` per 3 s tick | 20.2/min | 2.8 s | ≈ 86 MB/h |
| Qt's private image pool (`QGuiApplicationPrivate::qtGuiThreadPool`, ≤ 8 threads, 30 s idle expiry) recreated by every 40 s wallpaper | 10.0/min | 37.7 s | ≈ 43 MB/h |

That is ≈ 130 MB/h against the observed 125–142 MB/h, and 86 MB/h against the 88 MB/h of an idle saver (no
widgets, no rotation, no rendering). The earlier Screensaver-vs-MC and pixel-shift correlations were confounded by
attended versus unattended runs; the same invisible saver grew at +144 MB/h with pixel shift on and off.

**Fix.**
- The supervisor heartbeat is one persistent daemon thread (`srpss-worker-heartbeat`) that waits on an event
  between checks. Interval, checks, restarts and non-blocking shutdown are unchanged.
- `core/native_threads.retain_qt_gui_pool_threads()` (called once after `QApplication`) sets the private image
  pool's idle expiry to "never" through Qt's exported accessor, the same export-by-handle pattern as the PR-04
  texture bridge. The pool keeps its own maximum of 8, so this is a bounded one-time cost. If the export is ever
  missing it changes nothing and logs a warning.

**Measured after the fix** (same invisible full-activity run, 10 min): 0 new Python threads, 0 new Qt threads,
6 Windows thread-pool workers (0.6/min, ~200 s each). Driver heap +4 MB/h and converging (was ~140 MB/h). Private
commit shows no slope over the run.

**Rule.** A GL process must not create threads per tick, per image or per request. Periodic work runs on a
persistent thread or an existing lane (see `Docs/Guardrails.md`).

**Remaining.** The Windows thread-pool workers (≈ 2–3 MB/h at the observed rate) come from system components
(COM/WinRT/audio) and are not SRPSS threads. `bounded_dns` used to start one short-lived thread per network
lookup (a few dozen an hour, more once NEWS multiplied feed sources); since 2026-09-26 it resolves on at most
eight persistent resolver threads, started only as concurrent lookups first need them. Census of the invisible
saver with two NEWS cards and Custom 1 at a 5-minute refresh (7 min, one full refresh of six publishers): 4
Windows thread-pool workers (0.6/min, unchanged) and 2 Python threads that never exited (the resolver pool
reaching its peak concurrency); no SRPSS thread was created and destroyed.

## Is The Absolute Level Normal?

About 700 MB of warm USS is expected for Qt Quick with 1–2 high-resolution displays, a 10-image decoded cache
(~200 MB), the Visualizer and the Python runtime. The warm private commit of ~1.9 GB is high because ~1.2 GB of it
is committed but not resident, and that gap is what grows.

## Regression Coverage

- `tests/test_process_supervisor.py::TestHeartbeatThreadLifetime`: heartbeat checks run on one persistent thread,
  only that thread is ever started, and shutdown stops it.
- `tests/test_native_thread_pools.py::test_qt_image_pool_keeps_its_threads_instead_of_recreating_them`: with a short
  expiry Qt's image pool recreates threads between images; with the production setting the same threads are reused.
- `tests/test_feed_dns_stall.py::test_lookups_reuse_persistent_resolvers_instead_of_a_thread_each`: forty lookups
  create no thread; the deadline, cancellation, cap and exit-fence tests in the same file are unchanged.
- `tests/test_qtquick_native_texture_wrapper_retention.py`: 40 uploads through the production node on a real
  threaded-GL window leave ≤1 wrapper, and the latest image is still shown.
- `tools/memory_slope_report.py`: warm-plateau slopes and settled replacement steps from existing logs.
