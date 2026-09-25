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

## Is The Absolute Level Normal?

About 700 MB of warm USS is expected for Qt Quick with 1–2 high-resolution displays, a 10-image decoded cache
(~200 MB), the Visualizer and the Python runtime. The warm private commit of ~1.9 GB is high because ~1.2 GB of it
is committed but not resident, and that gap is what grows.

## Regression Coverage

- `tests/test_qtquick_native_texture_wrapper_retention.py`: 40 uploads through the production node on a real
  threaded-GL window leave ≤1 wrapper, and the latest image is still shown.
- `tools/memory_slope_report.py`: warm-plateau slopes and settled replacement steps from existing logs.
