"""F4-preservation tests for transport feedback during transitions."""

from __future__ import annotations

import logging
import weakref

from core.threading.manager import ThreadManager
from widgets.media import feedback
from widgets.media_widget import MediaWidget


def _set_transition_probe(monkeypatch, busy) -> None:
    monkeypatch.setattr(
        MediaWidget,
        "_has_transition_work_on_any_display",
        classmethod(lambda cls: bool(busy[0])),
    )


def test_transition_media_feedback_is_static_without_frame_animation(
    qt_app,
    monkeypatch,
) -> None:
    busy = [True]
    _set_transition_probe(monkeypatch, busy)
    widget = MediaWidget()
    animations = []
    updates = []
    timer_owners = []
    scheduled_clears = []
    monkeypatch.setattr(MediaWidget, "_shared_feedback_events", {})
    monkeypatch.setattr(
        feedback,
        "start_feedback_animation",
        lambda candidate, key: animations.append((candidate, key)),
    )
    monkeypatch.setattr(
        feedback,
        "ensure_shared_feedback_timer",
        lambda owner: timer_owners.append(owner),
    )
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(
            lambda delay_ms, callback, *_args, **_kwargs: scheduled_clears.append(
                (delay_ms, callback)
            )
        ),
    )
    widget._safe_update = lambda: updates.append("update")
    monkeypatch.setattr(
        feedback,
        "_safe_update_region",
        lambda candidate, rect: updates.append("update"),
    )

    try:
        feedback.trigger_controls_feedback(widget, "next", source="media_key")

        assert animations == []
        assert widget._controls_feedback_progress["next"] == 1.0
        assert updates == ["update"]
        assert timer_owners == []
        assert len(scheduled_clears) == 1
        assert scheduled_clears[0][0] == 1350
        assert widget._controls_feedback_anim_ids == {}
        assert widget._feedback_deadlines == {}

        scheduled_clears.pop()[1]()
        assert widget._controls_feedback == {}
        assert updates == ["update", "update"]
        animations.clear()
        updates.clear()
        timer_owners.clear()
        busy[0] = False

        feedback.trigger_controls_feedback(widget, "prev", source="media_key")

        assert animations == [(widget, "prev")]
        assert updates == ["update"]
        assert timer_owners == [MediaWidget]
        assert "prev" in widget._feedback_deadlines
    finally:
        feedback.finalize_feedback_key(widget, "next")
        feedback.finalize_feedback_key(widget, "prev")
        widget.cleanup()
        widget.close()


def test_transition_media_feedback_telemetry_reports_static_two_paint_lifecycle(
    qt_app,
    monkeypatch,
    caplog,
) -> None:
    _set_transition_probe(monkeypatch, [True])
    widget = MediaWidget()
    scheduled = []
    monkeypatch.setattr(MediaWidget, "_shared_feedback_events", {})
    monkeypatch.setattr(feedback, "is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(
            lambda delay_ms, callback, *_args, **_kwargs: scheduled.append(callback)
        ),
    )
    widget._safe_update = lambda: None

    try:
        with caplog.at_level(logging.INFO):
            feedback.trigger_controls_feedback(widget, "next", source="media_key")
            scheduled.pop()()

        messages = [
            record.getMessage()
            for record in caplog.records
            if "[PERF][MEDIA_FEEDBACK]" in record.getMessage()
            and "phase=ingress" not in record.getMessage()
        ]
        assert len(messages) == 2
        assert "phase=start" in messages[0]
        assert "transition_active=True" in messages[0]
        assert "mode=static" in messages[0]
        assert "paint_requests=1" in messages[0]
        assert "phase=complete" in messages[1]
        assert "paint_requests=2" in messages[1]
    finally:
        feedback.finalize_feedback_key(widget, "next")
        widget.cleanup()
        widget.close()


def test_static_feedback_remains_one_shot_owned_while_other_feedback_sweeps(
    qt_app,
    monkeypatch,
) -> None:
    busy = [False]
    clock = [100.0]
    _set_transition_probe(monkeypatch, busy)
    animated = MediaWidget()
    static = MediaWidget()
    scheduled = []
    monkeypatch.setattr(
        MediaWidget,
        "_instances",
        weakref.WeakSet([animated, static]),
    )
    monkeypatch.setattr(MediaWidget, "_shared_feedback_events", {})
    monkeypatch.setattr(MediaWidget, "_shared_feedback_timer", None)
    monkeypatch.setattr(feedback.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(feedback, "start_feedback_animation", lambda *_args: None)
    monkeypatch.setattr(feedback, "ensure_shared_feedback_timer", lambda _cls: None)
    monkeypatch.setattr(feedback.Shiboken, "isValid", lambda _widget: True)
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(
            lambda delay_ms, callback, *_args, **_kwargs: scheduled.append(callback)
        ),
    )
    animated._safe_update = lambda: None
    static._safe_update = lambda: None

    try:
        feedback.trigger_controls_feedback(animated, "play", source="media_key")
        busy[0] = True
        feedback.trigger_controls_feedback(static, "next", source="media_key")
        assert static._feedback_deadlines == {}

        clock[0] = 102.0
        feedback.on_shared_feedback_tick(MediaWidget)

        assert animated._controls_feedback == {}
        assert "next" in static._controls_feedback
        assert static._active_feedback_events.get("next") is not None

        scheduled.pop()()
        assert static._controls_feedback == {}
    finally:
        feedback.finalize_feedback_key(animated, "play")
        feedback.finalize_feedback_key(static, "next")
        animated.cleanup()
        static.cleanup()
        animated.close()
        static.close()
