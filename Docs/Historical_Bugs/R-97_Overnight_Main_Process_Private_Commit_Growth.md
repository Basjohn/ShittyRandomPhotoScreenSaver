# R-97 — Overnight Main-Process Private Commit Growth

Date: 2026-09-25  
Status: PARTIAL / AWAITING LOGS — one Windows retention was fixed; the Windows steady slope is not yet attributed

## Classification

- [ ] COMPLETELY FUCKED
- [x] PARTIAL
- [ ] AWAITING VALIDATION
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

## Open: The Windows Steady Slope

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

## Attribution 2026-09-26 (native maps plus seven-run comparison)

`tools/win_memory_map.py` maps of `main_mc.py` (one 4K display) put the growing private commit in one category:
NVIDIA OpenGL (`nvoglv64.dll`) write-combined memory (`PAGE_READWRITE | PAGE_WRITECOMBINE`), 420 → 444 → 479 MB over
55 min with ~27 MB resident. The other `VirtualAlloc`, heap, large heap blocks, CPython arenas and stacks were flat
or cache-bounded. The chunks are surface-sized: 32,640 KiB is exactly 3840 × 2176 × 4, i.e. the 3840 × 2162 R-63
window or a 3840 × 2160 texture with rows padded to 2176. In that MC setup the pool is bounded: a relaunch sat at
476–484 MB for a full hour. So in MC, driver write-combined memory is bounded rather than growing. Most of the
"committed but not resident" gap is this driver pool.

Across every run with `--usage` logs of at least 1 h (plateau generation state from the teardown records):

| Run | Plateau | Pixel shift | Unattended (window active, displays off) | Result |
|---|---|---|---|---|
| 09-12 05:44 diagnostic | 3.3 h | no record | yes | +142 MB/h |
| 09-14 03:53 diagnostic | 9.9 h | off | yes | +0.1 MB/h |
| 09-22 08:01 diagnostic | 6.1 h | on | yes | +125 MB/h |
| 09-23 09:07 MC | 1.2 h | off | no | flat |
| 09-25 02:17 diagnostic | 5.3 h | on | yes | +127 MB/h |
| 09-25 13:00 source | 3.0 h | on | yes | +135 MB/h |
| 09-26 00:46 MC | 1.0 h | on (rate 2) | no | flat |

Slope appears only with pixel shift on and the saver unattended. The two cannot be separated with existing data:
the saver window being active and the displays being off always coincide. Also established from the logs:
- growth is time-continuous (+0.3 MB per 15 s sample), not a step at each shift;
- phase-locked per rotation cycle it is the same for every transition type;
- scene/swap rates are identical sloped and flat (~91 swaps/s, 11 ms spacing);
- the swap interval was 0 in every run;
- the 09-12 slope predates the runtime audit. "New" matches pixel shift having been off in most recent testing.

Audited without a finding: the pixel-shift controller and publish path (a property write only on change, once per
shift), the `pixelShiftLayer` Translate and its only consumer (Edit-only mapping), the native cursor controller
(cached cursors; shift publishes return early) and the Visualizer clip host (one static VBO). No production change
was made. The remaining discriminator is one attended Screensaver-profile run with pixel shift on and display sleep
disabled: slope then means the focused-window path, flat means the displays-off path.

## Is The Absolute Level Normal?

About 700 MB of warm USS is expected for Qt Quick with 1–2 high-resolution displays, a 10-image decoded cache
(~200 MB), the Visualizer and the Python runtime. The warm private commit of ~1.9 GB is high because ~1.2 GB of it
is committed but not resident, and that gap is what grows.

## Regression Coverage

- `tests/test_qtquick_native_texture_wrapper_retention.py`: 40 uploads through the production node on a real
  threaded-GL window leave ≤1 wrapper, and the latest image is still shown.
- `tools/memory_slope_report.py`: warm-plateau slopes and settled replacement steps from existing logs.
