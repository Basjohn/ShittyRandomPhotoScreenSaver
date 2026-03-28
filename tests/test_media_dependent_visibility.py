from __future__ import annotations

from widgets.media.dependent_visibility import (
    resolve_anchor_visibility,
    sync_anchor_dependent_visibility,
)


class _DummyAnchor:
    def __init__(self, visible: bool) -> None:
        self._visible = visible

    def isVisible(self) -> bool:
        return self._visible


class _DummyWidget:
    def __init__(self) -> None:
        self.hidden = 0
        self.shown = 0
        self.raised = 0

    def hide(self) -> None:
        self.hidden += 1

    def show(self) -> None:
        self.shown += 1

    def raise_(self) -> None:
        self.raised += 1


def test_resolve_anchor_visibility_can_defer_missing_anchor() -> None:
    assert resolve_anchor_visibility(None, missing_anchor_visible=None) is None


def test_sync_anchor_dependent_visibility_hides_when_disabled() -> None:
    widget = _DummyWidget()

    visible = sync_anchor_dependent_visibility(
        widget,
        anchor=_DummyAnchor(True),
        enabled=False,
        has_faded_in=False,
        start_fade_in=lambda: None,
    )

    assert visible is False
    assert widget.hidden == 1


def test_sync_anchor_dependent_visibility_defers_when_anchor_missing() -> None:
    widget = _DummyWidget()
    fade_calls: list[str] = []

    visible = sync_anchor_dependent_visibility(
        widget,
        anchor=None,
        enabled=True,
        has_faded_in=False,
        start_fade_in=lambda: fade_calls.append("fade"),
        missing_anchor_visible=None,
    )

    assert visible is False
    assert widget.hidden == 0
    assert fade_calls == []


def test_sync_anchor_dependent_visibility_hides_when_anchor_hidden() -> None:
    widget = _DummyWidget()

    visible = sync_anchor_dependent_visibility(
        widget,
        anchor=_DummyAnchor(False),
        enabled=True,
        has_faded_in=False,
        start_fade_in=lambda: None,
    )

    assert visible is False
    assert widget.hidden == 1


def test_sync_anchor_dependent_visibility_starts_fade_for_first_show() -> None:
    widget = _DummyWidget()
    fade_calls: list[str] = []
    refresh_calls: list[str] = []

    visible = sync_anchor_dependent_visibility(
        widget,
        anchor=_DummyAnchor(True),
        enabled=True,
        has_faded_in=False,
        start_fade_in=lambda: fade_calls.append("fade"),
        refresh_visible=lambda: refresh_calls.append("refresh"),
    )

    assert visible is True
    assert fade_calls == ["fade"]
    assert refresh_calls == ["refresh"]
    assert widget.shown == 0


def test_sync_anchor_dependent_visibility_refreshes_visible_widget() -> None:
    widget = _DummyWidget()
    refresh_calls: list[str] = []

    visible = sync_anchor_dependent_visibility(
        widget,
        anchor=_DummyAnchor(True),
        enabled=True,
        has_faded_in=True,
        start_fade_in=lambda: None,
        refresh_visible=lambda: refresh_calls.append("refresh"),
    )

    assert visible is True
    assert widget.shown == 1
    assert widget.raised == 1
    assert refresh_calls == ["refresh"]
