"""Phase B gates for the standalone Quick display-window owner."""

from __future__ import annotations

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
        "describe_window_state",
    } <= methods
    assert "setPersistentGraphics(False)" in source
    assert "setPersistentSceneGraph(False)" in source
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
