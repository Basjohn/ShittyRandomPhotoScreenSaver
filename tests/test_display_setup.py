from __future__ import annotations

from collections.abc import Iterable
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect

from rendering import display_setup
from rendering.display_widget import DisplayWidget
from engine.screensaver_engine import ScreensaverEngine


class _Validity:
    def __init__(self, invalid: Iterable[object]) -> None:
        self.invalid_ids = {id(obj) for obj in invalid}

    def isValid(self, obj) -> bool:  # noqa: N802 - mirrors shiboken API
        return id(obj) not in self.invalid_ids


class _Widget:
    screen_index = 0

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._screen = None
        self._device_pixel_ratio = 1.0

    def _set_device_pixel_ratio(self, value) -> float:
        self._device_pixel_ratio = float(value)
        self.calls.append(f"dpr:{self._device_pixel_ratio}")
        return self._device_pixel_ratio

    def setGeometry(self, _geom) -> None:  # noqa: N802 - Qt-style API
        self.calls.append("setGeometry")

    def _configure_refresh_rate_sync(self) -> None:
        self.calls.append("refresh")

    def _ensure_render_surface(self) -> None:
        self.calls.append("surface")

    def _ensure_overlay_stack(self, *, stage: str) -> None:
        self.calls.append(f"stack:{stage}")

    def _reuse_persistent_gl_overlays(self) -> None:
        self.calls.append("reuse")

    def _ensure_gl_compositor(self) -> None:
        self.calls.append("compositor")


def test_handle_screen_change_ignores_deleted_display_widget(monkeypatch):
    widget = _Widget()
    screen = SimpleNamespace()
    monkeypatch.setattr(display_setup, "Shiboken", _Validity([widget]))

    display_setup.handle_screen_change(widget, screen)

    assert widget.calls == []
    assert widget._screen is None


def test_handle_screen_change_ignores_deleted_screen(monkeypatch):
    widget = _Widget()
    screen = SimpleNamespace()
    monkeypatch.setattr(display_setup, "Shiboken", _Validity([screen]))

    display_setup.handle_screen_change(widget, screen)

    assert widget.calls == []
    assert widget._screen is None


def test_handle_screen_change_syncs_dpr_without_relying_on_resize_event():
    widget = _Widget()
    screen = SimpleNamespace(
        devicePixelRatio=lambda: 1.5,
        geometry=lambda: QRect(0, 0, 1920, 1080),
    )

    display_setup.handle_screen_change(widget, screen)

    assert widget._device_pixel_ratio == 1.5
    assert widget.calls[0] == "dpr:1.5"
    assert "setGeometry" in widget.calls


def test_display_runtime_resume_reopens_nested_admission_before_display_gate():
    events: list[str] = []

    class _Controller:
        def resume_after_quiesce(self):
            events.append("controller")

    class _Compositor:
        def resume_after_quiesce(self):
            events.append("compositor")

    widget = SimpleNamespace(
        screen_index=0,
        _render_pipeline_permanent_shutdown=False,
        _render_pipeline_quiesced=True,
        _transition_admission_open=False,
        _render_lifecycle_generation=7,
        _pending_activation_refresh=True,
        _transition_work_pending=True,
        _transition_controller=_Controller(),
        _gl_compositor=_Compositor(),
    )

    assert DisplayWidget.resume_after_runtime_pause(widget) is True
    assert events == ["controller", "compositor"]
    assert widget._render_pipeline_quiesced is False
    assert widget._transition_admission_open is True
    assert widget._render_lifecycle_generation == 8


def test_display_runtime_resume_rolls_controller_back_on_compositor_failure():
    events: list[str] = []

    class _Controller:
        def resume_after_quiesce(self):
            events.append("controller_resume")

        def begin_quiesce(self, *, reason, snap_to_new):
            events.append(("controller_rollback", reason, snap_to_new))

    class _Compositor:
        def resume_after_quiesce(self):
            raise RuntimeError("resume failed")

    widget = SimpleNamespace(
        screen_index=0,
        _render_pipeline_permanent_shutdown=False,
        _render_pipeline_quiesced=True,
        _transition_admission_open=False,
        _render_lifecycle_generation=7,
        _pending_activation_refresh=True,
        _transition_work_pending=True,
        _transition_controller=_Controller(),
        _gl_compositor=_Compositor(),
    )

    with pytest.raises(RuntimeError, match="resume failed"):
        DisplayWidget.resume_after_runtime_pause(widget)

    assert events == [
        "controller_resume",
        ("controller_rollback", "display_resume_rollback", False),
    ]
    assert widget._render_pipeline_quiesced is True
    assert widget._transition_admission_open is False


def test_engine_start_reopens_reused_displays_before_first_image():
    events: list[str] = []

    class _DisplayManager:
        def resume_all_after_runtime_pause(self):
            events.append("resume_displays")
            return True

    class _Signal:
        def emit(self, *args):
            events.append(("emit", args))

    class _Engine:
        _instance_running = False

        def __init__(self):
            self._running = False
            self._instance_lock = threading.RLock()
            self._rotation_timer = None
            self.display_manager = _DisplayManager()
            self.started = _Signal()
            self.error_occurred = _Signal()

        def _transition_state(self, state, expected_from=None):
            del expected_from
            events.append(("state", state))
            return True

        def _show_next_image(self):
            events.append("show_next_image")
            return True

        def _schedule_startup_first_image_retry(self):
            raise AssertionError("first image should succeed")

    engine = _Engine()

    assert ScreensaverEngine.start(engine) is True
    assert events.index("resume_displays") < events.index("show_next_image")
