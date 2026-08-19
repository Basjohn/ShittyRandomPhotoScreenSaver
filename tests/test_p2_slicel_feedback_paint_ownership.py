"""Gate 7C - animated feedback must not run the full parent paint pipeline.

`Docs/P2_Behavioral_Gates.md` Gate 7C, `Current_Plan.md` Slice L.

Slice H changed the feedback repaint request from a full-card `update()` to
`update(controls_row_rect)`, but `MediaWidget.paintEvent` still dispatched the
whole artwork/header/metadata/logo/progress sequence (merely clipped by Qt), so
the second installed run still measured frame-count-scale `media.paint`
execution during rapid Pause/Play. Slice L makes `paint_contents` take a
feedback-only branch that paints only the cached background frame and the
controls row when the damage is confined to that band.

These bars use a real `MediaWidget` and real Qt paint events (`repaint`) and
count which sub-painters the real pipeline actually invokes - not monkeypatched
`update()` names.
"""

from __future__ import annotations

import time

import pytest
from PySide6.QtGui import QColor, QPixmap

from widgets.media import feedback, painting
from widgets.media_widget import MediaWidget


@pytest.fixture
def shown_widget(qt_app, qtbot):
    widget = MediaWidget()
    widget.resize(600, 320)
    widget._show_controls = True
    widget._invalidate_controls_layout()
    # A real artwork pixmap so paint_artwork has genuine work to skip.
    pm = QPixmap(120, 120)
    pm.fill(QColor(80, 120, 200))
    widget._artwork_pixmap = pm
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    yield widget
    widget.hide()
    widget.deleteLater()


def _instrument(monkeypatch):
    counts = {"artwork": 0, "header": 0, "metadata": 0, "logo": 0, "progress": 0, "row": 0}

    def _wrap(name, original):
        def _counted(widget, painter):
            counts[name] += 1
            return original(widget, painter)
        return _counted

    monkeypatch.setattr(painting, "paint_artwork", _wrap("artwork", painting.paint_artwork))
    monkeypatch.setattr(painting, "paint_header_frame", _wrap("header", painting.paint_header_frame))
    monkeypatch.setattr(painting, "paint_metadata_text", _wrap("metadata", painting.paint_metadata_text))
    monkeypatch.setattr(painting, "paint_header_logo", _wrap("logo", painting.paint_header_logo))
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


class TestFeedbackRepaintSkipsExpensiveSubpainters:
    def test_feedback_frames_do_not_run_artwork_header_or_metadata(
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
        assert counts["artwork"] == 0, "artwork ran on feedback frames"
        assert counts["header"] == 0, "header frame ran on feedback frames"
        assert counts["metadata"] == 0, "metadata text ran on feedback frames"
        assert counts["logo"] == 0 and counts["progress"] == 0

    def test_a_full_repaint_still_runs_the_whole_pipeline(
        self, shown_widget, monkeypatch
    ):
        """The fast path must be selective, not a global disable of subpainters."""
        counts = _instrument(monkeypatch)
        # Feedback inactive: an ordinary full repaint.
        shown_widget._controls_feedback = {}
        shown_widget.repaint()

        assert counts["artwork"] >= 1, "the ordinary paint path stopped drawing artwork"
        assert counts["row"] >= 1

    def test_forcing_the_old_path_fails_the_bound(self, shown_widget, monkeypatch):
        """Negative control: without the feedback-only branch, every feedback
        frame runs the full pipeline - the installed frame-count-scale defect."""
        counts = _instrument(monkeypatch)
        monkeypatch.setattr(painting, "_is_feedback_only_repaint", lambda w, e: False)
        dirty = _activate_feedback(shown_widget)

        for _ in range(_FRAMES):
            shown_widget.repaint(dirty)

        assert counts["artwork"] >= _FRAMES, (
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
