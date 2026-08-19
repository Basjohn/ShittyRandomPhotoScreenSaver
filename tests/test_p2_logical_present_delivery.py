"""A published logical frame must actually reach the compositor.

The logical runtime landed correctly but nothing presented its output, so the
visualizer never appeared at all. The installed log is unambiguous:

    [LOGICAL] Runtime started (generation=1 interval_ms=11.11)
    [LOGICAL] Runtime stopped (generation=1 steps=1082 ... failures=0 joined=True)
    [STARTUP] Reveal watchdog expired while still pending
              (mode=bubble waiting_frame=True ...)

1082 logical steps ran, zero frames were pushed, and the reveal never completed.

The cause was a seam, not the cadence: `logical_tick()` asked for presentation
through `getattr(widget, "_request_logical_present", None)`, and that widget
method had been removed when the plumbing moved into this module. The lookup
silently returned None, so the mailbox filled and was never drained.

These bars pin the delivery path end to end, so a publication that nobody
presents fails loudly instead of producing a blank visualizer.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer import tick_pipeline


class _UiThreadManager:
    """Runs UI callbacks inline, like the GUI thread would."""

    def __init__(self):
        self.calls: list[tuple] = []

    def run_on_ui_thread(self, func, *args, **kwargs):
        self.calls.append((func, args))
        func(*args, **kwargs)


class _Widget:
    def __init__(self, manager):
        from widgets.spotify_visualizer.logical_runtime import LatestStateMailbox

        self._thread_manager = manager
        self._logical_mailbox = LatestStateMailbox()
        self._logical_present_pending = False
        self._runtime_generation = 4
        self._activation_id = 2
        self.presented: list[dict] = []


@pytest.fixture
def rig(monkeypatch):
    manager = _UiThreadManager()
    widget = _Widget(manager)

    def _present(target):
        target.presented.append({"ok": True})
        return True

    monkeypatch.setattr(tick_pipeline, "present_tick", _present)
    return widget, manager


class TestPresentIsRequested:
    def test_a_publication_requests_a_present(self, rig):
        widget, manager = rig

        tick_pipeline.request_logical_present(widget)

        assert manager.calls, (
            "a published logical frame never asked the GUI to present it - "
            "this is the blank-visualizer defect"
        )

    def test_the_request_reaches_presentation(self, rig):
        widget, _manager = rig

        tick_pipeline.request_logical_present(widget)

        assert widget.presented, "the present request did not reach present_tick"

    def test_the_publish_path_requests_a_present(self):
        """The exact seam that broke: publish must call the module function.

        A `getattr` on a widget attribute that no longer exists fails silently,
        so the call is pinned directly.
        """
        import inspect

        # Publication moved into `_publish_logical_state()`, which every
        # logical-tick exit path goes through.
        source = inspect.getsource(tick_pipeline._publish_logical_state)
        assert "request_logical_present(widget)" in source, (
            "the publish path no longer requests presentation of what it publishes"
        )
        assert 'getattr(widget, "_request_logical_present"' not in source, (
            "presentation is being requested through a silently-optional lookup"
        )

    def test_no_widget_side_present_hook_is_required(self):
        """The widget carries no `_request_logical_present`; nothing may assume it."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

        assert not hasattr(SpotifyVisualizerWidget, "_request_logical_present")


class TestPresentIsSinglePending:
    def test_a_second_request_while_pending_is_coalesced(self, rig):
        widget, manager = rig
        widget._logical_present_pending = True

        tick_pipeline.request_logical_present(widget)

        assert manager.calls == [], (
            "logical steps queued one GUI callback each instead of coalescing"
        )

    def test_the_pending_flag_clears_after_presenting(self, rig):
        widget, _manager = rig

        tick_pipeline.present_logical_frame(widget)

        assert widget._logical_present_pending is False

    def test_a_stalled_gui_cannot_build_a_backlog(self, rig):
        """Many logical steps, at most one outstanding present."""
        widget, manager = rig
        widget._logical_present_pending = True

        for _ in range(50):
            tick_pipeline.request_logical_present(widget)

        assert len(manager.calls) == 0

        widget._logical_present_pending = False
        tick_pipeline.request_logical_present(widget)
        assert len(manager.calls) == 1

    def test_a_failing_dispatch_does_not_wedge_the_pending_flag(self):
        class _Broken:
            def run_on_ui_thread(self, func, *args, **kwargs):
                raise RuntimeError("no ui thread")

        widget = _Widget(_Broken())

        tick_pipeline.request_logical_present(widget)

        assert widget._logical_present_pending is False, (
            "one failed dispatch would have blocked presentation forever"
        )

    def test_no_thread_manager_is_safe(self):
        widget = _Widget(None)
        widget._thread_manager = None

        tick_pipeline.request_logical_present(widget)  # must not raise
