from __future__ import annotations

from collections.abc import Iterable
from types import SimpleNamespace

from rendering import display_setup


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


def test_setup_pixel_shift_propagates_runtime_generation_and_uses_weak_defer_owner(
    monkeypatch,
):
    captured: dict[str, object] = {}

    class _Settings:
        def get(self, key, default=None):
            values = {
                "accessibility.pixel_shift.enabled": False,
                "accessibility.pixel_shift.rate": 1,
            }
            return values.get(key, default)

    class _Manager:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.defer_check = None

        def set_thread_manager(self, value):
            captured["thread_manager_set"] = value

        def set_defer_check(self, value):
            self.defer_check = value

        def set_shifts_per_minute(self, value):
            captured["rate"] = value

        def register_widget(self, _widget):
            raise AssertionError("fixture has no overlay children")

        def set_enabled(self, value):
            captured["enabled"] = value

    monkeypatch.setattr(display_setup, "PixelShiftManager", _Manager)
    thread_manager = object()
    class _PixelWidget:
        pass

    widget = _PixelWidget()
    widget.settings_manager = _Settings()
    widget._pixel_shift_manager = None
    widget._resource_manager = object()
    widget._thread_manager = thread_manager
    widget._runtime_generation = 44
    widget.has_running_transition = lambda: True
    widget.clock_widget = None
    widget.clock2_widget = None
    widget.clock3_widget = None
    widget.weather_widget = None
    widget.media_widget = None
    widget.reddit_widget = None
    widget.reddit2_widget = None

    display_setup.setup_pixel_shift(widget)

    assert captured["runtime_generation"] == 44
    assert captured["thread_manager"] is thread_manager
    assert captured["thread_manager_set"] is thread_manager
    assert captured["enabled"] is False
    assert widget._pixel_shift_manager.defer_check() is True
    assert (
        widget._pixel_shift_manager.defer_check._srpss_runtime_generation
        == 44
    )
