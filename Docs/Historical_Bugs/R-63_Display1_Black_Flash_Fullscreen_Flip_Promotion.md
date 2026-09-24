# R-63 — Display-1 Black Flash from Fullscreen-Flip PresentMode Transitions

Date: 2026-08-31
Status: Solved / H accepted — recurring black/stale flash eliminated; bounded mixed-DPR 1px shared-edge overshoot accepted residual

## Symptom

On the Qt Quick production presenter, one physical display (operator's LG 4K
60 Hz TV, the non-primary output) showed recurring full-black flashes and brief
"old wallpaper" (stale-frame) resurfacing on activation/click and context-menu
opens. The other display (MSI 2560x1440, primary) never flashed. A single-window
MC A/B proved the defect follows the LG output even when it is the only SRPSS
window — so it was never a two-window/activation-between-windows interaction.

## Root Cause (measured, not inferred)

PresentMon (ETW) capture correlated against a DXGI Desktop-Duplication
black/stale-frame detector, both timestamped in QPC:

```text
non-flashing launches:  100% PresentMode = "Composed: Copy with GPU GDI"
flashing launch:        same window also spent presents in "Hardware: Legacy Flip"
                        (AllowsTearing=1); black/stale events cluster in the +/-250 ms
                        windows that contain BOTH modes -> at the mode transitions
```

Windows non-deterministically **promotes an exact-cover borderless top-level
window to a hardware fullscreen-flip presentation**. The composition <->
`Hardware: Legacy Flip` **PresentMode transitions** are what present the
black/stale frames. Stable composition is fine; the promotion/demotion is the
defect. This is the same class SRPSS's historical `_FULLSCREEN_COMPAT_WORKAROUND`
(geometry.height -= 1, borderless) was created to prevent.

The retained Quick scene, image identity, scene-graph state and frame swaps stay
healthy throughout (`[QUICK_SURFACE]` telemetry) — the flash is below Qt, in
native presentation.

## Failed Approaches (physically disproven — do not retry)

```text
persistent scene graph/graphics (setPersistent*(True))  no change; SG never invalidated mid-flash
event-driven surface-refresh redraw on activation/menu   no improvement; removed
deferred first-show (gate show on first image)           made startup WORSE (image->black->image); removed
VSync ON (swapInterval=1) alone                          no reliable reduction
drop SplashScreen role                                   non-deterministic (0 vs 15 same code)
WS_EX_NOACTIVATE / focus / DWM-transition-disable        PROHIBITED (feature loss)
```

## Fix

`QuickDisplayWindow._fullscreen_compat_geometry` applies a 1px coverage-preserving
overscan (`x-1, y-1, w+2, h+2`) so the window is never exact-cover and Windows
does not promote it to fullscreen flip. PresentMon then shows a stable
`Composed: Copy with GPU GDI` present mode with no transitions.

```text
height-1  (diagnostic): 3/3 launches black=0, stable composed   (loses a visible row -> not shipped)
overscan  (shipped):    3/3 launches black=0, stable composed, full visible coverage
```

Overscan preserves full visible coverage and centering — only an off-screen 1px
ring is clipped. The display's own geometry/identity is untouched, so image
target size and CUSTOM widget geometry are unaffected. Regression:
`tests/test_qtquick_window.py::test_fullscreen_compat_geometry_overscans_without_losing_coverage`.

## Diagnostic Method (reusable for future presentation issues)

Ephemeral, outside the repo (nothing added to production):

```text
PresentMon capture-all (unelevated OK): PresentMon.exe --timed N --qpc_time --output_file f.csv
  -> per-present PresentMode, AllowsTearing, TimeInQPC; SwapChainAddress is 0x0 without elevation
dxcam (DXGI Desktop Duplication) near-black/stale detector, timestamped via QueryPerformanceCounter
correlate: for each black/stale frame, inspect PresentMode within +/-250 ms; did it transition?
drive activation with Win32 SetForegroundWindow (no cursor motion -> mouse-move exit never fires)
run >=3 launches per condition: launch-to-launch presentation behavior is variable
```

See `Docs/Qt_QML_Observability.md` and `Current_Plan.md` "Interleaved black-flash".


## 2026-09-01 Mixed-DPR Shared-Edge Follow-Up

After the anti-fullscreen-flip geometry was refined away from all-edge overscan, an intermittent one-pixel seam appeared on Display 1. One-shot native Win32 geometry telemetry proved the mechanism rather than guessing from logical Qt rectangles:

```text
Display 0 monitor device rect width = 2560
Display 0 Quick window device width = 2561
Display 1 begins at device x = 2560
```

The intended exterior/top logical overscan on the operator's 1.5-DPR display rounds into one extra device pixel on the shared right edge. This is a mixed-DPR logical->native rounding consequence, not a return of the fullscreen-flip failure.

The H acceptance priority is now explicit:

```text
recurring black/stale flash = 0        mandatory
bounded shared-edge overshoot <= 1px  acceptable residual
```

Do **not** remove overscan, force exact-cover geometry, or hard-code this monitor's `2560x1440`, `1.5` DPR, coordinate, display index or neighbour relationship merely to erase the pixel. Any optional J refinement must derive native/device-space coverage from the actual monitor rectangles/DPR and remain correct for different resolutions, origins/orderings and common mixed DPR combinations. A harmless bounded overshoot is preferable to re-admitting exact-cover fullscreen promotion.

## 2026-09-24 Device-Exact Window And Scene (J Refinement)

The accepted <=1px shared-edge residual is removed the way this record required: native geometry is derived in
device pixels from the real monitor/virtual-desktop rectangles and DPR, with nothing hard-coded.

- `rendering/quick/device_geometry.py` `compat_native_rect`: the monitor plus overscan on one exterior edge only
  (top, bottom, left, right; an interior display falls back to top), using the smallest overscan (>=1 px) whose
  extent survives Qt's whole-logical-pixel rounding (otherwise Qt's idea of the surface height differs from the
  real one and the scene shifts a row). Never exact cover; never past the monitor on any other edge.
- `QuickDisplayWindow._apply_native_compat_geometry` re-sets the native rectangle with `SetWindowPos` after show and
  after every Qt geometry application, but only while the window still has the logical geometry its own R-63
  placement produced: a window placed by anything else (test harness, tool role) is left alone. The logical
  `_fullscreen_compat_geometry` still applies first (pre-show, and as the fallback when Win32 rectangles fail).
- The window publishes its on-desktop rectangle (`scene_rect`, `visible_rect_in_window`, re-derived on every
  window geometry change) and the scene root is laid out on it. The overscan strip lies off the virtual desktop,
  so for the display window this is exactly its monitor. The wallpaper (processed at monitor size) had been drawn
  across the whole overscanned window with linear filtering: on the 4K display 2160 rows over 2161.5 device rows,
  cropping two rows, blending neighbouring rows by up to 50% and dropping one; the startup desktop capture and
  widgets were shifted the same way. They now map 1:1 to monitor pixels. A monitor enclosed on all four sides
  keeps the accepted top fallback and today's fill-the-window scene.
- Operator layout after the change: Display 0 `(0,-2,2560,1442)` (was 2561 wide, overdrawing Display 1),
  Display 1 `(2560,-2,3840,2162)`.
- Bars: `tests/test_qtquick_window.py` sweeps 803 layouts (rows both sides, top/bottom/centre aligned, stacks,
  negative origins, portrait, three-wide, 2x2 and 3x3 grids; ten resolutions) at DPR 1.0-3.0: never exact cover, one
  outward edge, no neighbour overdrawn, Qt-rounding-safe extent, scene exactly on the monitor's pixels. The
  render-node smoke and runtime suites keep harness-placed windows untouched.

**Accepted 2026-09-24 (operator physical run, 15:10-15:14):** every generation logged Display 0
`window_device=(0,-2,2560,1442)` / Display 1 `(2560,-2,3840,2162)` with `right=0`, no bleed into the
neighbouring display, no black/stale flash, crisp wallpapers; Glass held 158-165 fps on the 165 Hz display.
