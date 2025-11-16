"""Startup integration tests to guard against black init flash.

These tests exercise DisplayWidget startup in both software and OpenGL
modes, with clock and weather widgets enabled, and assert that the base
black fallback paint path is never used for the first image.

The goal is to catch regressions where the base widget would briefly
paint a black frame (e.g. during GL overlay prewarm or widget setup)
instead of a seeded pixmap.
"""

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from rendering.display_widget import DisplayWidget
from rendering.display_modes import DisplayMode


class DummySettings:
    """Minimal settings shim for tests.

    Supports direct keys and simple dotted access into nested dicts so we can
    provide a small in-memory settings tree without touching on-disk config.
    """

    def __init__(self, data=None):
        self._data = data or {}

    def get(self, key, default=None):
        if key in self._data:
            return self._data[key]
        if "." in key:
            cur = self._data
            for part in key.split("."):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    return default
            return cur
        return default


@pytest.fixture
def qapp():
    """Ensure a QApplication exists for these tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def _run_startup_case(qtbot, hw_accel: bool) -> None:
    """Helper that runs a single startup scenario and asserts invariants."""

    widgets_cfg = {
        "clock": {
            "enabled": True,
            "position": "Top Right",
            "font_size": 48,
            "show_seconds": True,
            "show_timezone": True,
            "timezone": "Africa/Johannesburg",
            "monitor": "ALL",
        },
        "weather": {
            "enabled": True,
            "location": "Testville",
            "position": "Top Left",
            "font_size": 24,
            "show_background": True,
            "bg_opacity": 0.9,
            "color": [255, 255, 255, 230],
            "monitor": "ALL",
        },
    }

    settings = DummySettings(
        {
            "display.hw_accel": hw_accel,
            "display.pan_and_scan": False,
            "widgets": widgets_cfg,
        }
    )

    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings,
    )
    qtbot.addWidget(widget)
    widget.resize(800, 600)

    # Drive real startup path (including GL prewarm when enabled).
    widget.show_on_screen()

    # Allow time for prewarm + widget setup to complete.
    qtbot.wait(600)

    # Seed first image manually, similar to engine behaviour.
    pm = QPixmap(800, 600)
    pm.fill(Qt.GlobalColor.red)
    widget.set_image(pm, "startup_test.jpg")

    # Give the event loop a moment to process the initial paint.
    qtbot.wait(150)

    # Invariants:
    # - Base widget should never have needed to fall back to a pure black
    #   paint (no pixmap) during this flow.
    assert (
        getattr(widget, "_base_fallback_paint_logged", False) is False
    ), "Base fallback paint path was triggered during startup"

    # - Overlay telemetry should be available as a diagnostic dict.
    counts = widget.get_overlay_stage_counts()
    assert isinstance(counts, dict)

    widget.close()


@pytest.mark.qt_no_exception_capture
def test_startup_no_base_black_fallback_software(qapp, qtbot):
    """Software mode startup should not trigger base black fallback paint."""

    _run_startup_case(qtbot, hw_accel=False)


@pytest.mark.qt_no_exception_capture
def test_startup_no_base_black_fallback_opengl(qapp, qtbot):
    """OpenGL mode startup should also not trigger base black fallback paint."""

    _run_startup_case(qtbot, hw_accel=True)
