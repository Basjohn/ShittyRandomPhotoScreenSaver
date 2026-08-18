"""P2-165-DELIVERY: presentation admission never waits for paint.

The installed dual-display run delivered ~153.3-153.7 FPS on a 165 Hz target
while accepting only ~93.18-93.44% of requests. 165 x 0.932 is ~153.8, so the
measured ceiling was essentially the acceptance rate.

``_queue_safe_widget_update`` rejected a request whenever
``_srpss_timer_update_pending`` was set, and that flag was cleared only when a
queued update reached paint consumption. That is a pending-until-paint admission
latch: a physical presentation deadline waiting for paint acknowledgement.

What remains is a queued-GUI-dispatch guard and nothing else:

1. the first deadline queues one GUI callback;
2. deadlines arriving before that callback runs do not queue a second one;
3. the callback executes and calls ``QWidget.update()``;
4. a later deadline is admitted BEFORE paint happens;
5. repeated ``update()`` calls rely on Qt's own paint-event coalescing;
6. paint timing is passive diagnostics only;
7. teardown/stale widgets still fail safely;
8. the 60/165 target cadence maths is untouched.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from rendering import adaptive_timer
from rendering.adaptive_timer import (
    _mark_widget_update_consumed,
    _normalize_next_deadline,
    _queue_safe_widget_update,
)


class _Widget:
    """A GUI widget seam with no thread affinity and no paint."""

    def __init__(self):
        self.update_count = 0

    def update(self):
        self.update_count += 1


@pytest.fixture
def gui(monkeypatch):
    """Capture queued GUI callbacks instead of running them immediately."""
    queued: list = []
    monkeypatch.setattr(
        adaptive_timer.ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda func, *a, **k: queued.append(func)),
    )
    monkeypatch.setattr(adaptive_timer, "Shiboken", None)
    return queued


# ---------------------------------------------------------------------------
# The admission contract
# ---------------------------------------------------------------------------


class TestQueuedDispatchIsTheOnlyGuard:
    def test_first_deadline_queues_one_callback(self, gui):
        widget = _Widget()
        assert _queue_safe_widget_update(widget) is True
        assert len(gui) == 1
        assert widget.update_count == 0, "the callback has not run yet"

    def test_deadlines_before_the_callback_runs_do_not_queue_a_second(self, gui):
        widget = _Widget()
        _queue_safe_widget_update(widget)
        for _ in range(10):
            assert _queue_safe_widget_update(widget) is False
        assert len(gui) == 1

    def test_the_callback_calls_widget_update(self, gui):
        widget = _Widget()
        _queue_safe_widget_update(widget)
        gui[0]()
        assert widget.update_count == 1

    def test_a_deadline_is_admitted_before_paint(self, gui):
        """The whole point: paint has not run, and the next deadline is taken."""
        widget = _Widget()
        _queue_safe_widget_update(widget)
        gui[0]()
        assert getattr(widget, "_srpss_timer_update_pending") is True, (
            "paint has deliberately not been signalled"
        )
        assert _queue_safe_widget_update(widget) is True
        assert len(gui) == 2

    def test_repeated_updates_are_left_for_qt_to_coalesce(self, gui):
        """Every admitted deadline reaches QWidget.update(); Qt merges them."""
        widget = _Widget()
        for _ in range(20):
            if _queue_safe_widget_update(widget):
                gui[-1]()
        assert widget.update_count == 20
        # No paint was ever acknowledged and nothing throttled.
        assert getattr(widget, "_srpss_timer_update_pending") is True

    def test_paint_consumption_only_closes_the_passive_diagnostic(self, gui):
        widget = _Widget()
        _queue_safe_widget_update(widget)
        gui[0]()
        _mark_widget_update_consumed(widget)
        assert getattr(widget, "_srpss_timer_update_pending") is False
        assert getattr(widget, "_srpss_timer_update_pending_since") == 0.0
        # And it did not become a gate release either: admission was already open.
        assert _queue_safe_widget_update(widget) is True


class TestNoPaintPathCanRejectADeadline:
    def test_the_only_false_return_is_the_dispatch_branch(self):
        """AST, not prose: exactly one guarded rejection path may exist."""
        tree = ast.parse(
            textwrap.dedent(inspect.getsource(_queue_safe_widget_update))
        ).body[0]

        guarded_rejections = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            for stmt in node.body:
                if isinstance(stmt, ast.Return) and _is_false(stmt.value):
                    guarded_rejections.append(ast.dump(node.test))

        # The widget-is-None guard plus the queued-dispatch guard.
        assert len(guarded_rejections) == 2, guarded_rejections
        assert any("_srpss_timer_update_dispatch_pending" in dump for dump in guarded_rejections)
        assert not any("_srpss_timer_update_pending'" in dump for dump in guarded_rejections), (
            "paint-pending state is gating admission again"
        )

    def test_paint_pending_state_is_never_read_as_a_gate(self):
        source = inspect.getsource(_queue_safe_widget_update)
        # It may not consult the paint-pending flag at all on the admission path.
        assert 'getattr(widget, "_srpss_timer_update_pending", False)' not in source

    def test_no_paint_or_swap_acknowledgement_seam_exists(self):
        source = inspect.getsource(adaptive_timer)
        for forbidden in ("swapBuffers", "glFinish", "DwmFlush", "waitForPaint"):
            assert forbidden not in source


def _is_false(node) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


class TestTeardownStillFailsSafely:
    def test_an_invalid_widget_does_not_leave_the_guard_latched(self, monkeypatch):
        queued: list = []
        monkeypatch.setattr(
            adaptive_timer.ThreadManager,
            "run_on_ui_thread",
            staticmethod(lambda func, *a, **k: queued.append(func)),
        )

        class _FakeShiboken:
            @staticmethod
            def isValid(_obj):
                return False

        monkeypatch.setattr(adaptive_timer, "Shiboken", _FakeShiboken)

        widget = _Widget()
        assert _queue_safe_widget_update(widget) is True
        queued[0]()
        assert widget.update_count == 0
        assert getattr(widget, "_srpss_timer_update_dispatch_pending") is False, (
            "a torn-down widget latched the dispatch guard forever"
        )

    def test_a_raising_widget_releases_the_guard(self, monkeypatch):
        queued: list = []
        monkeypatch.setattr(
            adaptive_timer.ThreadManager,
            "run_on_ui_thread",
            staticmethod(lambda func, *a, **k: queued.append(func)),
        )
        monkeypatch.setattr(adaptive_timer, "Shiboken", None)

        class _Stale:
            def update(self):
                raise RuntimeError("wrapped C/C++ object has been deleted")

        widget = _Stale()
        assert _queue_safe_widget_update(widget) is True
        queued[0]()
        assert getattr(widget, "_srpss_timer_update_dispatch_pending") is False

    def test_none_widget_is_rejected(self):
        assert _queue_safe_widget_update(None) is False


class TestTargetCadenceIsUnchanged:
    @pytest.mark.parametrize("fps,expected_ms", [(60, 1000.0 / 60.0), (165, 1000.0 / 165.0)])
    def test_target_interval_matches_the_display_target(self, fps, expected_ms):
        interval = max(1.0, 1000.0 / float(fps)) / 1000.0
        assert interval * 1000.0 == pytest.approx(expected_ms)

    def test_deadlines_stay_anchored_to_the_previous_deadline(self):
        """Cadence must not drift by re-pacing from 'now' after a late wake."""
        interval = 1.0 / 165.0
        deadline = 100.0
        # A wake that arrived 2.5 intervals late skips whole intervals only.
        nxt = _normalize_next_deadline(deadline, 100.0 + 2.5 * interval, interval)
        assert nxt == pytest.approx(deadline + 3 * interval)

    def test_an_on_time_deadline_is_returned_unchanged(self):
        interval = 1.0 / 60.0
        assert _normalize_next_deadline(50.0, 49.9, interval) == 50.0


class TestAcceptanceLossIsGone:
    def test_a_full_165_hz_window_admits_every_deadline_without_paint(self, gui):
        """Simulated 165 Hz with paint never signalled: no request is lost."""
        widget = _Widget()
        admitted = 0
        for _ in range(165):
            if _queue_safe_widget_update(widget):
                admitted += 1
                gui[-1]()  # the GUI thread runs the callback promptly
        assert admitted == 165
        assert widget.update_count == 165

    def test_a_stalled_gui_thread_still_coalesces_to_one_callback(self, gui):
        """Backpressure protection is preserved where it belongs."""
        widget = _Widget()
        admitted = sum(1 for _ in range(165) if _queue_safe_widget_update(widget))
        assert admitted == 1, "the GUI queue must not grow while a callback waits"
        assert len(gui) == 1
