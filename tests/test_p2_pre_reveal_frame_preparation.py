"""The reveal window must not be where every overlay builds its frame.

Current_Plan section 7 listed "reconstruction warmup that can be completed
before reveal rather than during live cadence" as candidate 2 and deliberately
left it unlanded, because the evidence then available named no concrete owner.

The 2026-08-19 / 4.7.2 acceptance named it. On the settings-close full restart
(`Settings dialog destroyed, performing full-style restart`), the fade
coordinator started 6 fades on screen 1 and 2 on screen 0 at 02:26:49, and the
same second recorded:

    overlay.frame_shadow.regen  weather 8.88  gmail 8.46  reddit2 12.08
                                reddit 16.25  media 6.45x3
                                achievement_pulse 7.99x2
                                abandonment_issues 8.62x2

`BaseOverlayWidget._commit_painted_frame_shadow_cache()` returns early unless
`isVisible()`, so during reconstruction those invalidations coalesce and
`showEvent` is the only builder - and the reveal starter is what calls `show()`.

`WidgetManager` requests the fade at the moment the overlay declares itself
ready, with geometry and style already final and the widget still hidden. These
bars hold that seam.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QWidget

from rendering.widget_manager import WidgetManager


# `_resolve_overlay_fade_widget` only accepts real QWidgets, so these stand-ins
# are real widgets carrying the frame-shadow seam and nothing else.


class _Overlay(QWidget):
    """The frame-shadow surface of a real overlay, with nothing else faked."""

    def __init__(self):
        super().__init__()
        self.prepare_calls = 0

    def _prepare_painted_frame_shadow_pixmap(self):
        self.prepare_calls += 1
        return object()


class _PlainOverlay(QWidget):
    """A reveal participant that does not use the shared painted frame."""


class _ExplodingOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.prepare_calls = 0

    def _prepare_painted_frame_shadow_pixmap(self):
        self.prepare_calls += 1
        raise RuntimeError("frame preparation blew up")


def _manager(overlay_name: str, widget) -> WidgetManager:
    manager = WidgetManager.__new__(WidgetManager)
    manager._widgets = {overlay_name: widget}
    manager._parent = None
    return manager


def _prepare(manager: WidgetManager, overlay_name: str) -> None:
    manager._prepare_overlay_frame_shadow_before_reveal(overlay_name)


class TestPreparationHappensBeforeReveal:
    def test_a_ready_overlay_is_prepared(self, qtbot):
        overlay = _Overlay()
        qtbot.addWidget(overlay)
        manager = _manager("gmail", overlay)

        _prepare(manager, "gmail")

        assert overlay.prepare_calls == 1, (
            "the overlay reached its reveal starter without a prepared frame"
        )

    def test_every_participant_is_prepared_independently(self, qtbot):
        """The installed burst was seven overlays in one reveal window."""
        overlays = {name: _Overlay() for name in (
            "weather", "gmail", "reddit", "reddit2", "media",
            "achievement_pulse", "abandonment_issues",
        )}
        for _o in overlays.values():
            qtbot.addWidget(_o)
        manager = WidgetManager.__new__(WidgetManager)
        manager._widgets = dict(overlays)
        manager._parent = None

        for name in overlays:
            _prepare(manager, name)

        assert all(o.prepare_calls == 1 for o in overlays.values())

    def test_the_widget_suffix_form_resolves(self, qtbot):
        overlay = _Overlay()
        qtbot.addWidget(overlay)
        manager = WidgetManager.__new__(WidgetManager)
        manager._widgets = {"gmail_widget": overlay}
        manager._parent = None

        _prepare(manager, "gmail")

        assert overlay.prepare_calls == 1

    def test_a_parent_owned_overlay_resolves(self, qtbot):
        overlay = _Overlay()
        qtbot.addWidget(overlay)
        manager = WidgetManager.__new__(WidgetManager)
        manager._widgets = {}
        manager._parent = SimpleNamespace(clock_widget=overlay)

        _prepare(manager, "clock")

        assert overlay.prepare_calls == 1


class TestPreparationIsSafe:
    def test_a_missing_overlay_is_not_an_error(self):
        manager = WidgetManager.__new__(WidgetManager)
        manager._widgets = {}
        manager._parent = None

        _prepare(manager, "absent")  # must not raise

    def test_an_overlay_without_the_seam_is_skipped(self, qtbot):
        """Not every reveal participant uses the shared painted frame."""
        plain = _PlainOverlay()
        qtbot.addWidget(plain)
        manager = _manager("clock", plain)

        _prepare(manager, "clock")  # must not raise

    def test_a_failing_preparation_never_blocks_the_reveal(self, qtbot):
        overlay = _ExplodingOverlay()
        qtbot.addWidget(overlay)
        manager = _manager("reddit", overlay)

        _prepare(manager, "reddit")

        assert overlay.prepare_calls == 1


class TestTheRevealPathCallsIt:
    def test_request_fade_prepares_before_registering(self):
        """Ordering is the whole point: prepare, then hand over the starter."""
        import inspect

        source = inspect.getsource(WidgetManager._request_overlay_fade) \
            if hasattr(WidgetManager, "_request_overlay_fade") else None
        if source is None:
            source = inspect.getsource(WidgetManager)

        prepare_at = source.find("_prepare_overlay_frame_shadow_before_reveal(overlay_name)")
        request_at = source.find("self._fade_coordinator.request_fade(overlay_name")

        assert prepare_at != -1, "the reveal path no longer prepares the frame"
        assert request_at != -1
        assert prepare_at < request_at, (
            "preparation must precede the fade request, not follow it"
        )
