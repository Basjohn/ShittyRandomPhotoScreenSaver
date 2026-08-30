# R-63 — Display-1 Black Flash from Fullscreen-Flip PresentMode Transitions

Date: 2026-08-31
Status: Solved (recurring/activation flash); minor startup-only flash carried to J

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
