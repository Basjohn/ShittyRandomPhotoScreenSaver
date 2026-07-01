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
