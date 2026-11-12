"""Phase B gates for the standalone Quick display-window owner."""

from __future__ import annotations

import math

import ast
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtQuick import QQuickWindow

from rendering.quick.state import (
    QuickDisplayBindingLoss,
    QuickWindowPolicy,
    QuickWindowRole,
    capture_display_identity,
)
from rendering.quick.window import QuickDisplayWindow


ROOT = Path(__file__).resolve().parents[1]


class _FakeScreen:
    def geometry(self) -> QRect:
        return QRect(-1920, 0, 1920, 1080)

    def availableGeometry(self) -> QRect:
        return QRect(-1920, 0, 1920, 1040)

    def name(self) -> str:
        return "DISPLAY2"

    def manufacturer(self) -> str:
        return "Fixture"

    def model(self) -> str:
        return "Panel"

    def serialNumber(self) -> str:
        return "ABC123"

    def devicePixelRatio(self) -> float:
        return 1.5

    def refreshRate(self) -> float:
        return 143.999


def test_display_identity_is_immutable_primitive_state_and_preserves_generation_zero():
    identity = capture_display_identity(
        screen_index=1,
        runtime_generation=0,
        screen=_FakeScreen(),  # type: ignore[arg-type]
    )

    assert identity.screen_index == 1
    assert identity.runtime_generation == 0
    assert identity.geometry == (-1920, 0, 1920, 1080)
    assert identity.available_geometry == (-1920, 0, 1920, 1040)
    assert identity.device_pixel_ratio == 1.5
    assert identity.refresh_rate_hz == 143.999
    assert identity.screen_key.startswith("serial:ABC123|")


def test_binding_loss_is_immutable_primitive_generation_state():
    loss = QuickDisplayBindingLoss(
        screen_index=1,
        runtime_generation=0,
        expected_screen_key="serial:expected",
        observed_screen_key="serial:fallback",
        observed_screen_name="DISPLAY1",
    )

    assert loss.as_dict() == {
        "screen_index": 1,
        "runtime_generation": 0,
        "expected_screen_key": "serial:expected",
        "observed_screen_key": "serial:fallback",
        "observed_screen_name": "DISPLAY1",
    }


def test_fullscreen_compat_geometry_overscans_without_losing_coverage():
    # Windows promotes an exact-cover borderless window to a hardware
    # fullscreen-flip presentation; PresentMon proved the composition<->flip
    # PresentMode transitions present the Display-1 black flash. A 1px overscan
    # disqualifies exact-cover promotion (stable composed present) while preserving
    # full visible coverage. The refined R-63 geometry no longer overscans all four
    # edges (that perturbed mixed-DPR shared seams): with no virtual-desktop
    # rectangle supplied it uses the narrowest safe top-only overscan.
    screen = QRect(2560, 0, 2560, 1440)
    compat = QuickDisplayWindow._fullscreen_compat_geometry(screen)

    # Non-exact-cover so Windows will not promote it to fullscreen flip...
    assert compat != screen
    # ...but it still fully covers every visible pixel of the screen.
    assert compat.contains(screen)
    assert compat == QRect(2560, -1, 2560, 1441)
    # The source screen rect the caller passed is not mutated.
    assert screen == QRect(2560, 0, 2560, 1440)


def test_native_compat_window_overscans_one_exterior_edge_in_device_pixels():
    # R-63 mixed-DPR follow-up: Qt sizes windows in whole logical pixels, so the
    # 150% 2560x1440 display's logical overscan came out 2561 device pixels wide
    # and overdrew the neighbouring display by a column.
    from rendering.quick.device_geometry import compat_native_rect

    logical_width = 1707  # Qt's screen geometry for 2560 px at 150%
    assert round(logical_width * 1.5 + 0.1) == 2561  # the old native width
    virtual = (0, 0, 6400, 2160)
    left_display = compat_native_rect((0, 0, 2560, 1440), virtual, 1.5)
    right_display = compat_native_rect((2560, 0, 6400, 2160), virtual, 1.5)
    assert left_display[2:] == (2560, 1440)  # shared right edge now exact
    assert left_display[1] == -3
    # 2560 px at 150% is 1706.67 logical: the left edge is exterior too, so it takes 2 device px (1708 logical) and
    # the width is whole as well (R-192 remainder); the shared edge is untouched.
    assert left_display[0] == -2
    # 3 device px at 150% is 2 logical: the window's height is a whole number of logical pixels, so Qt Quick maps the
    # scene 1:1 (2 device px gave 1441 logical over 2162 device, a 1.00023 vertical stretch: every horizontal edge
    # on the display blended, the 1C.4 D1 run of 12 Nov 2026).
    assert right_display == (2560, -3, 6400, 2160)


def _layouts():
    """Device-pixel monitor layouts: rows, stacks, negative origins, portrait, grids."""
    sizes = [(1280, 720), (1366, 768), (1920, 1080), (2560, 1080), (2560, 1440),
             (3440, 1440), (3840, 2160), (5120, 1440), (1080, 1920), (1440, 2560)]
    for aw, ah in sizes:
        for bw, bh in sizes:
            for align in ("top", "bottom", "centre"):
                dy = {"top": 0, "bottom": ah - bh, "centre": (ah - bh) // 2}[align]
                yield f"row {aw}x{ah}|{bw}x{bh} {align}", [(0, 0, aw, ah), (aw, dy, aw + bw, dy + bh)]
                yield f"left {aw}x{ah}|{bw}x{bh} {align}", [(0, 0, aw, ah), (-bw, dy, 0, dy + bh)]
            yield f"stack {aw}x{ah}/{bw}x{bh}", [(0, 0, aw, ah), (0, ah, bw, ah + bh)]
            yield f"above {aw}x{ah}/{bw}x{bh}", [(0, 0, aw, ah), (0, -bh, bw, 0)]
    yield "three in a row", [(0, 0, 1920, 1080), (1920, 0, 5760, 2160), (5760, 0, 7680, 1080)]
    yield "2x2 grid", [(0, 0, 1920, 1080), (1920, 0, 3840, 1080), (0, 1080, 1920, 2160), (1920, 1080, 3840, 2160)]
    yield "3x3 grid", [(x * 1920, y * 1080, (x + 1) * 1920, (y + 1) * 1080) for x in range(3) for y in range(3)]


def test_native_compat_window_is_durable_across_layouts_resolutions_and_dprs():
    """R-63 and R-192 invariants for every layout x DPR, from real device rects only (nothing hard-coded).

    Never exact cover, overscan only outward and at most one edge per axis; each axis that has an exterior edge is a
    whole number of logical pixels (Qt Quick maps logical size to surface size, so a non-whole axis is a stretched
    scene, R-192). An axis with no exterior edge (a monitor enclosed on that axis, such as the middle of three in a
    row horizontally) cannot be overscanned without overdrawing a neighbour, so it keeps the stretch when its extent
    is not whole; a monitor enclosed on all sides takes R-63's accepted top fallback.
    """
    from rendering.quick.device_geometry import (
        compat_native_rect, is_whole_logical, survives_logical_rounding, visible_rect_in_window,
    )

    checked = 0
    second_axis_cases = 0
    for name, monitors in _layouts():
        virtual = (min(m[0] for m in monitors), min(m[1] for m in monitors),
                   max(m[2] for m in monitors), max(m[3] for m in monitors))
        for dpr in (1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0):
            for monitor in monitors:
                case = (name, dpr, monitor)
                rect = compat_native_rect(monitor, virtual, dpr)
                changed = [i for i in range(4) if rect[i] != monitor[i]]
                assert 1 <= len(changed) <= 2, case  # never exact cover
                assert len({i % 2 for i in changed}) == len(changed), case  # at most one edge per axis
                for edge in changed:
                    amount = abs(rect[edge] - monitor[edge])
                    assert 1 <= amount <= 4 * math.ceil(dpr), case
                    assert (rect[edge] < monitor[edge]) if edge < 2 else (rect[edge] > monitor[edge]), case
                    extent = (rect[3] - rect[1]) if edge in (1, 3) else (rect[2] - rect[0])
                    assert survives_logical_rounding(extent, dpr), case
                exterior_x = monitor[0] <= virtual[0] or monitor[2] >= virtual[2]
                exterior_y = monitor[1] <= virtual[1] or monitor[3] >= virtual[3]
                if len(changed) == 2:
                    second_axis_cases += 1
                # R-192: every axis that has an exterior edge is whole, so Qt Quick draws it 1:1.
                if exterior_x:
                    assert is_whole_logical(rect[2] - rect[0], dpr), case
                if exterior_y:
                    assert is_whole_logical(rect[3] - rect[1], dpr), case
                if not (exterior_x or exterior_y):
                    continue  # enclosed on all sides: the accepted top fallback (R-63)
                for edge in changed:
                    # Overscan only ever goes past the virtual desktop's boundary: never on a shared edge.
                    on_virtual_edge = (monitor[edge] <= virtual[edge]) if edge < 2 else (monitor[edge] >= virtual[edge])
                    assert on_virtual_edge, case
                for other in monitors:
                    if other != monitor:  # never overdraws a neighbouring display
                        assert not (rect[0] < other[2] and other[0] < rect[2]
                                    and rect[1] < other[3] and other[1] < rect[3]), (case, other)
                # The scene lands exactly on the monitor's pixels.
                x, y, width, height = visible_rect_in_window(rect, virtual, dpr)
                device = tuple(round(value * dpr, 6) for value in (x, y, width, height))
                assert device == (monitor[0] - rect[0], monitor[1] - rect[1],
                                  monitor[2] - monitor[0], monitor[3] - monitor[1]), case
                checked += 1
    assert checked > 10000
    assert second_axis_cases > 0  # the sweep reaches monitors that need both axes overscanned


def test_native_compat_window_overscans_both_axes_when_neither_is_whole_logical():
    # R-192 remainder: 1366 x 768 at 125 % is 1092.8 x 614.4 logical. A top overscan alone left the width at 1366
    # device pixels for 1093 logical (a 0.9998 horizontal stretch: every vertical edge blended); the left edge is
    # exterior too, so it gets its own overscan and both axes are whole.
    from rendering.quick.device_geometry import compat_native_rect, is_whole_logical, visible_rect_in_window

    virtual = (0, 0, 1366 + 1920, 1080)
    rect = compat_native_rect((0, 0, 1366, 768), virtual, 1.25)
    assert rect[2:] == (1366, 768)  # the shared right edge and the bottom stay exactly the monitor's
    assert rect[0] < 0 and rect[1] < 0
    assert is_whole_logical(rect[2] - rect[0], 1.25) and is_whole_logical(rect[3] - rect[1], 1.25)
    x, y, width, height = visible_rect_in_window(rect, virtual, 1.25)
    assert tuple(round(v * 1.25, 6) for v in (x, y, width, height)) == (-rect[0], -rect[1], 1366, 768)


def test_scene_lands_on_the_monitor_pixels_inside_the_overscanned_window():
    from rendering.quick.device_geometry import visible_rect_in_window

    virtual = (0, 0, 6400, 2160)
    x, y, width, height = visible_rect_in_window((0, -2, 2560, 1440), virtual, 1.5)
    assert (x * 1.5, y * 1.5, width * 1.5, height * 1.5) == (0.0, 2.0, 2560.0, 1440.0)
    x, y, width, height = visible_rect_in_window((2560, -2, 6400, 2160), virtual, 1.5)
    assert (x * 1.5, y * 1.5, width * 1.5, height * 1.5) == (0.0, 2.0, 3840.0, 2160.0)
    # A window resized on the desktop keeps all of its visible area (the scene
    # follows it); only the off-desktop overscan strip is excluded.
    x, y, width, height = visible_rect_in_window((0, -2, 2681, 1507), virtual, 1.5)
    assert (x * 1.5, y * 1.5, width * 1.5, height * 1.5) == (0.0, 2.0, 2681.0, 1507.0)


def test_window_policy_keeps_native_roles_explicit():
    standard = QuickWindowPolicy().flags()
    secondary = QuickWindowPolicy(accepts_focus=False).flags()
    tool = QuickWindowPolicy(
        role=QuickWindowRole.MEDIA_CENTER_TOOL,
        always_on_top=False,
    ).flags()

    assert standard & Qt.WindowType.FramelessWindowHint
    assert standard & Qt.WindowType.SplashScreen
    assert standard & Qt.WindowType.WindowStaysOnTopHint
    assert secondary & Qt.WindowType.WindowDoesNotAcceptFocus
    assert tool & Qt.WindowType.Tool
    assert not tool & Qt.WindowType.WindowStaysOnTopHint


def test_quick_display_window_is_a_narrow_standalone_qwindow_owner():
    assert issubclass(QuickDisplayWindow, QQuickWindow)
    source_path = ROOT / "rendering" / "quick" / "window.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    methods = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert {
        "show_on_screen",
        "queue_hide",
        "queue_close",
        "refresh_display_identity",
        "revalidate_bound_screen_geometry",
        "describe_window_state",
    } <= methods
    assert "setPersistentGraphics(False)" in source
    assert "setPersistentSceneGraph(False)" in source
    assert "self.sceneGraphInitialized.connect(" in source
    assert "self._validate_scene_graph_opengl" in source
    assert "Qt.ConnectionType.DirectConnection" in source
    assert source.index("self.setScreen(screen)") < source.index(
        'self._queue_meta_call("show")'
    )
    assert "self._bind_screen(screen, apply_geometry=False)" in source
    screen_changed = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_on_window_screen_changed"
    )
    screen_changed_source = ast.unparse(screen_changed)
    assert "_bind_screen" not in screen_changed_source
    assert "binding_lost.emit" in screen_changed_source
    assert 'queue_hide()' in screen_changed_source
    assert source.index("self._apply_screen_geometry(screen)") < source.index(
        'self._queue_meta_call("show")'
    )
    for forbidden in (
        "QWidget",
        "QQuickWidget",
        "DisplayWidget",
        "WidgetManager",
        "GLCompositorWidget",
        "SettingsManager",
    ):
        assert forbidden not in source
