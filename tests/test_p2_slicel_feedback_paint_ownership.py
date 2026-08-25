"""Gate 7C - animated feedback must not repaint unrelated F4 progress pixels.

`Docs/P2_Behavioral_Gates.md` Gate 7C, `Current_Plan.md` Slice L.

Media core pixels are now retained Quick-owned. The temporary QWidget painter
contains only the F4 controls and progress paths, and its feedback-only branch
must still avoid repainting progress for every animation frame.

These bars use a real `MediaWidget` and real Qt paint events (`repaint`) and
count which sub-painters the real pipeline actually invokes - not monkeypatched
`update()` names.
"""

from __future__ import annotations

import time

import pytest
from widgets.media import feedback, painting
from widgets.media_widget import MediaWidget


@pytest.fixture
def shown_widget(qt_app, qtbot):
    widget = MediaWidget()
    widget.resize(600, 320)
    widget._show_controls = True
    widget._playback_progress_enabled = True
    widget._playback_progress_visible = True
    widget._invalidate_controls_layout()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    yield widget
    widget.hide()
    widget.deleteLater()


def _instrument(monkeypatch):
    counts = {"progress": 0, "row": 0}

    def _wrap(name, original):
        def _counted(widget, painter):
            counts[name] += 1
            return original(widget, painter)
        return _counted

    monkeypatch.setattr(painting, "paint_playback_progress", _wrap("progress", painting.paint_playback_progress))
    monkeypatch.setattr(painting, "paint_controls_row", _wrap("row", painting.paint_controls_row))
    return counts


def _activate_feedback(widget):
    widget._controls_feedback = {"play": (time.monotonic(), "evt_test")}
    widget._active_feedback_events = {"play": "evt_test"}
    widget._controls_feedback_progress = {"play": 1.0}
    dirty = feedback._feedback_dirty_rect(widget)
    assert dirty is not None and not dirty.isNull()
    return dirty


_FRAMES = 10


class TestFeedbackRepaintSkipsUnrelatedProgress:
    def test_feedback_frames_do_not_run_progress_painter(
        self, shown_widget, monkeypatch
    ):
        counts = _instrument(monkeypatch)
        dirty = _activate_feedback(shown_widget)

        for frame in range(_FRAMES):
            # A real animated feedback progression across frames.
            shown_widget._controls_feedback_progress["play"] = 1.0 - frame / _FRAMES
            shown_widget.repaint(dirty)

        assert counts["row"] >= _FRAMES, (
            "the controls row did not repaint per feedback frame - the feedback "
            "is not animating (or the paint event never fired)"
        )
        assert counts["progress"] == 0

    def test_a_full_repaint_still_runs_progress_and_controls(
        self, shown_widget, monkeypatch
    ):
        """The fast path must be selective, not a global disable of subpainters."""
        counts = _instrument(monkeypatch)
        # Feedback inactive: an ordinary full repaint.
        shown_widget._controls_feedback = {}
        shown_widget.repaint()

        assert counts["progress"] >= 1
        assert counts["row"] >= 1

    def test_forcing_the_old_path_fails_the_bound(self, shown_widget, monkeypatch):
        """Negative control: without the feedback-only branch, every feedback
        frame runs the full pipeline - the installed frame-count-scale defect."""
        counts = _instrument(monkeypatch)
        monkeypatch.setattr(painting, "_is_feedback_only_repaint", lambda w, e: False)
        dirty = _activate_feedback(shown_widget)

        for _ in range(_FRAMES):
            shown_widget.repaint(dirty)

        assert counts["progress"] >= _FRAMES, (
            "the negative control did not reproduce the full-pipeline-per-frame "
            "behavior, so the gate proves nothing"
        )


class TestFeedbackRemainsVisible:
    def test_the_controls_row_carries_the_feedback_every_frame(
        self, shown_widget, monkeypatch
    ):
        counts = _instrument(monkeypatch)
        dirty = _activate_feedback(shown_widget)

        # The row must repaint on every feedback frame so the glow animates; that
        # is the whole point of keeping paint_controls_row in the fast path.
        for _ in range(_FRAMES):
            shown_widget.repaint(dirty)

        assert counts["row"] >= _FRAMES
