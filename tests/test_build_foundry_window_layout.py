"""UI geometry contracts for the stdlib/Tk Build Foundry.

What matters is that every job's checkbox and every action control can be seen and clicked, and that the window fits
the monitor's work area: never a fixed pixel height (the native build targets grew the window to fit their rows, and
the old 696 px limit only went stale). A change that adds a Build Runner control runs this file.

The window is real (mapped through the product's own show path, native frame styles included) but never shows a
pixel: ``keep_tk_off_screen`` holds it transparent, and its work area is the real monitor's work area moved past the
virtual screen, so the Foundry places itself off every monitor at the size it would have on it.
"""

import ctypes
import sys
import tkinter as tk
from ctypes import wintypes

import pytest

from tests._invisible_windows import keep_tk_off_screen
from tools import build_runner

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="the Foundry's work area and frame are Windows'")

_FOOTER_ACTIONS = (
    "_select_all_button", "_select_none_button", "_emergency_stop_button", "_start_button", "_auto_close_checkbox",
)


def _virtual_screen_right() -> int:
    metrics = ctypes.windll.user32.GetSystemMetrics
    return int(metrics(76) + metrics(78))  # SM_XVIRTUALSCREEN + SM_CXVIRTUALSCREEN


def _outer_rect(app) -> tuple[int, int, int, int]:
    """The whole visible window, native frame included (Tk reports only the client area); DWM's extended frame
    bounds, which leave out Windows' invisible resize borders, else the window rectangle."""
    hwnd = wintypes.HWND(app._native_toplevel_hwnd())
    rect = wintypes.RECT()
    if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)) != 0:
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))   # 9 = DWMWA_EXTENDED_FRAME_BOUNDS
        return rect.left, rect.top, rect.right, rect.bottom
    # DWM reports physical pixels; Tk (and the work area) use this process's own (possibly DPI-virtualised) ones.
    corners = [wintypes.POINT(rect.left, rect.top), wintypes.POINT(rect.right, rect.bottom)]
    for corner in corners:
        ctypes.windll.user32.PhysicalToLogicalPointForPerMonitorDPI(hwnd, ctypes.byref(corner))
    return corners[0].x, corners[0].y, corners[1].x, corners[1].y


def _rect(widget) -> tuple[int, int, int, int]:
    x, y = widget.winfo_rootx(), widget.winfo_rooty()
    return x, y, x + widget.winfo_width(), y + widget.winfo_height()


def _hit(widget, x: int, y: int):
    """The widget a click at screen (x, y) lands on, by Tk's own geometry: the topmost mapped child containing the
    point, recursively. A child reaches only as far as its parent's rectangle (a canvas clips its embedded frame)."""
    for child in reversed(widget.winfo_children()):   # stacking order, lowest first
        if isinstance(child, tk.Toplevel) or not child.winfo_ismapped():
            continue
        left, top, right, bottom = _rect(child)
        if left <= x < right and top <= y < bottom:
            return _hit(child, x, y)
    return widget


def _unreachable(app, root, work_area) -> list[str]:
    """Every job checkbox and action control not wholly inside the client area and clickable, and a window that
    leaves the work area. Empty when the Foundry is usable."""
    problems = []
    left, top, right, bottom = _outer_rect(app)
    if not (work_area[0] <= left and work_area[1] <= top and right <= work_area[2] and bottom <= work_area[3]):
        problems.append(f"window {(left, top, right, bottom)} outside work area {work_area}")
    client = _rect(root)
    controls = [(f"job {key}", widgets.checkbox) for key, widgets in app._job_widgets.items()]
    controls += [(name, getattr(app, name)) for name in _FOOTER_ACTIONS]
    for name, control in controls:
        if not control.winfo_ismapped():
            problems.append(f"{name} not mapped")
            continue
        x0, y0, x1, y1 = _rect(control)
        if not (client[0] <= x0 and client[1] <= y0 and x1 <= client[2] and y1 <= client[3]):
            problems.append(f"{name} {(x0, y0, x1, y1)} outside client area {client}")
            continue
        points = ((x0 + x1) // 2, (y0 + y1) // 2), (x0, y0), (x1 - 1, y0), (x0, y1 - 1), (x1 - 1, y1 - 1)
        for x, y in points:
            hit = _hit(root, x, y)
            if not str(hit).startswith(str(control)):
                problems.append(f"{name}: a click at {(x, y)} lands on {hit}")
                break
    return problems


@pytest.fixture
def open_foundry(monkeypatch):
    """Open the Foundry off screen; ``work_area`` maps the real (on-screen) work area to the one it should use."""
    monkeypatch.setattr(
        build_runner, "helper_build_status",
        lambda *_a, **_k: build_runner.HelperBuildStatus(False, "Stable", "fixture", 0),
    )
    monkeypatch.setattr(build_runner, "run_preflight", lambda *_a, **_k: build_runner.PreflightResult())
    real_work_area = build_runner.BuildRunnerApp._work_area
    roots = []

    def open_(work_area=lambda real: real):
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("Tk display unavailable")
        roots.append(root)
        keep_tk_off_screen(root)
        cached = {}
        shift = _virtual_screen_right() + 4000

        def off_screen_work_area(app):
            if "area" not in cached:            # the monitor the window opens on, then moved past every monitor
                l, t, r, b = work_area(real_work_area(app))
                cached["area"] = (l + shift, t, r + shift, b)
            return cached["area"]

        monkeypatch.setattr(build_runner.BuildRunnerApp, "_work_area", off_screen_work_area)
        app = build_runner.BuildRunnerApp(root, initial_mode="github")
        root.update()
        root.after(400, root.quit)               # the delayed native-style refresh and the preflight result
        root.mainloop()
        root.update()
        assert app._initial_show_complete and root.state() == "normal"
        assert _outer_rect(app)[0] > _virtual_screen_right(), "the test window must sit past every monitor"
        return root, app, cached["area"]

    yield open_
    for root in roots:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_every_job_and_action_is_inside_the_window_and_clickable(open_foundry):
    root, app, work_area = open_foundry()
    assert app._job_widgets
    assert _unreachable(app, root, work_area) == []

    # A long live status must never consume the action buttons' row.
    app._footer_status.configure(text="Building on GitHub; " * 16)
    root.update()
    assert _unreachable(app, root, work_area) == []


def _open_short(open_foundry):
    """The Foundry on a work area two thirds as tall as the window its jobs need: the rows must scroll."""
    root, app, _area = open_foundry()
    left, top, right, bottom = _outer_rect(app)
    root.destroy()
    return open_foundry(lambda real: (real[0], real[1], real[2], real[1] + (bottom - top) * 2 // 3))


def test_a_short_work_area_scrolls_the_jobs_and_keeps_the_actions(open_foundry):
    root, app, work_area = _open_short(open_foundry)
    assert app._body_content.winfo_reqheight() > app._body_canvas.winfo_height()
    canvas_bottom = app._body_canvas.winfo_rooty() + app._body_canvas.winfo_height()
    assert canvas_bottom <= app._footer.winfo_rooty()
    problems = [problem for problem in _unreachable(app, root, work_area) if not problem.startswith("window ")]
    # Jobs below the viewport are reached by scrolling; every action control stays inside and clickable.
    assert problems and all(problem.startswith("job ") for problem in problems), problems

    # User resizing does not require reconstructing job/status widgets.
    jobs = dict(app._job_widgets)
    root.geometry(f"{root.winfo_width()}x{root.winfo_height() - 40}")
    root.update()
    assert app._job_widgets == jobs
    assert not [problem for problem in _unreachable(app, root, work_area)
                if not problem.startswith(("job ", "window "))]


@pytest.mark.xfail(strict=True, reason=(
    "tools/build_runner.py _fit_initial_window clamps Tk's client height to the work area, but the native frame "
    "(and the caption removal, which grows the client) is not counted: on a work area shorter than its content the "
    "window's bottom passes the work area's by about a caption height. Reported to the lead (1D.10)."))
def test_a_short_work_area_keeps_the_whole_window_inside_it(open_foundry):
    root, app, work_area = _open_short(open_foundry)
    assert not [problem for problem in _unreachable(app, root, work_area) if problem.startswith("window ")]


# ---------------------------------------------------------------------------------------------------- negative controls
def test_a_smaller_window_is_caught(open_foundry):
    root, app, work_area = open_foundry()
    assert _unreachable(app, root, work_area) == []
    # Shrink the window just past the last job row: the canvas viewport now cuts it off.
    last = list(app._job_widgets.values())[-1].checkbox
    canvas_bottom = app._body_canvas.winfo_rooty() + app._body_canvas.winfo_height()
    clip = canvas_bottom - (last.winfo_rooty() + last.winfo_height()) + last.winfo_height() // 2
    root.geometry(f"{root.winfo_width()}x{root.winfo_height() - clip}")
    root.update()
    problems = _unreachable(app, root, work_area)
    assert any(problem.startswith(f"job {key}") for key in app._job_widgets for problem in problems), problems


def test_a_window_past_the_work_area_is_caught(open_foundry):
    root, app, work_area = open_foundry()
    assert _unreachable(app, root, work_area) == []
    # The same window against a work area that ends a few pixels above its bottom edge.
    shorter = (*work_area[:3], _outer_rect(app)[3] - 4)
    assert [problem for problem in _unreachable(app, root, shorter) if problem.startswith("window ")]
