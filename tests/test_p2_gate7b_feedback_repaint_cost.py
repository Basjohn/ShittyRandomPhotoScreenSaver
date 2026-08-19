"""Gate 7B - Pause/Play feedback must not repaint the whole media card per frame.

`Docs/P2_Behavioral_Gates.md` Gate 7B, Current_Plan Slice H.

The first installed run showed each completed Play control event issuing ~35-66
full MediaWidget paint requests over the 1.35s feedback fade, because every
feedback animation update called `widget._safe_update()` (a whole-card repaint
of a ~170400px card). That full-card stream is a bounded, edge-specific target
for the unchanged Pause/Play hitch.

The feedback only draws a small control glow on the transport controls row, so
it now issues a dirty-region `update(rect)` confined to that row. These bars
prove the feedback still repaints (it is not silently dropped or slowed) while
the number of whole-card repaints attributable to one feedback event stays a
small constant, not one-per-frame.
"""

from __future__ import annotations

import pytest

from widgets.media import feedback
from widgets.media_widget import MediaWidget


@pytest.fixture
def media_widget(qt_app):
    widget = MediaWidget()
    widget.resize(600, 320)
    widget._show_controls = True
    widget._invalidate_controls_layout()
    yield widget
    widget.deleteLater()


def _event_id(widget) -> str:
    return widget._active_feedback_events["play"]


class TestFeedbackRepaintsAreDirtyRegion:
    def test_the_dirty_rect_covers_every_control_button(self, media_widget):
        layout = media_widget._compute_controls_layout()
        assert layout is not None, "no controls layout to scope the repaint to"

        dirty = feedback._feedback_dirty_rect(media_widget)
        assert dirty is not None and not dirty.isNull()
        for key, rect in layout["button_rects"].items():
            assert dirty.contains(rect), (
                f"feedback dirty rect does not cover the {key} control, so its "
                f"glow would not repaint"
            )

    def test_the_dirty_rect_excludes_the_upper_card(self, media_widget):
        dirty = feedback._feedback_dirty_rect(media_widget)
        assert dirty is not None
        # The artwork/metadata/header band lives above the controls row; a
        # feedback repaint must not span the whole card.
        assert dirty.top() > media_widget.height() * 0.4, (
            "the feedback dirty rect reaches into the upper card - it is not "
            "confined to the controls row"
        )

    def test_request_feedback_paint_issues_a_region_update_not_full_card(
        self, media_widget, monkeypatch
    ):
        region_calls: list = []
        full_calls: list = []
        monkeypatch.setattr(
            feedback, "_safe_update_region",
            lambda w, rect: region_calls.append(rect),
        )
        monkeypatch.setattr(media_widget, "_safe_update", lambda: full_calls.append(1))

        # Register an event the way trigger does, without starting the real
        # animation manager.
        cls = type(media_widget)
        event_id = "play_test"
        media_widget._active_feedback_events["play"] = event_id
        cls._shared_feedback_events[event_id] = {
            "key": "play", "mode": "animated",
            "paint_requests": 0, "full_card_paint_requests": 0,
        }
        try:
            feedback._request_feedback_paint(media_widget, event_id)
        finally:
            cls._shared_feedback_events.pop(event_id, None)
            media_widget._active_feedback_events.pop("play", None)

        assert len(region_calls) == 1, "the feedback paint was not a region update"
        assert full_calls == [], "the feedback paint repainted the whole card"


class TestOneEventDoesNotRepaintTheCardPerFrame:
    def test_a_full_feedback_event_bounds_full_card_paints(
        self, media_widget, monkeypatch
    ):
        # Neutralise the real per-frame paint side effects; only the accounting
        # matters here.
        monkeypatch.setattr(feedback, "_safe_update_region", lambda w, rect: None)
        monkeypatch.setattr(media_widget, "_safe_update", lambda: None)
        # Force the animated (non-static) path regardless of transition state.
        monkeypatch.setattr(feedback, "_has_transition_work", lambda w: False)
        monkeypatch.setattr(feedback, "start_feedback_animation", lambda w, k: None)
        monkeypatch.setattr(feedback, "ensure_shared_feedback_timer", lambda cls: None)

        feedback.trigger_controls_feedback(media_widget, "play")
        event_id = _event_id(media_widget)

        # 40 animation frames, matching the ~1.35s / 60Hz fade the installed run
        # produced 35-66 full-card paints for.
        for _ in range(40):
            feedback._request_feedback_paint(media_widget, event_id)

        meta_before_finalize = dict(type(media_widget)._shared_feedback_events[event_id])
        feedback.finalize_feedback_key(media_widget, "play")

        total = int(meta_before_finalize["paint_requests"])
        full = int(meta_before_finalize["full_card_paint_requests"])

        assert total >= 41, (
            f"the feedback only issued {total} paints; it is not animating"
        )
        assert full == 0, (
            f"{full} of {total} feedback paints repainted the whole media card; "
            f"the per-frame full-card repaint stream is still present"
        )

    def test_completion_is_the_only_full_card_paint(self, media_widget, monkeypatch):
        monkeypatch.setattr(feedback, "_safe_update_region", lambda w, rect: None)
        monkeypatch.setattr(media_widget, "_safe_update", lambda: None)
        monkeypatch.setattr(feedback, "_has_transition_work", lambda w: False)
        monkeypatch.setattr(feedback, "start_feedback_animation", lambda w, k: None)
        monkeypatch.setattr(feedback, "ensure_shared_feedback_timer", lambda cls: None)

        feedback.trigger_controls_feedback(media_widget, "play")
        event_id = _event_id(media_widget)
        for _ in range(40):
            feedback._request_feedback_paint(media_widget, event_id)

        # finalize reads then pops the meta, so capture the running counter and
        # add the single completion paint it records.
        running = int(type(media_widget)._shared_feedback_events[event_id]["full_card_paint_requests"])
        feedback.finalize_feedback_key(media_widget, "play")

        # Only the completion repaint may be full-card: never one-per-frame.
        assert running + 1 <= 2, (
            "more than the start/end full-card paints were issued for one event"
        )
