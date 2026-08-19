"""The visualizer slow-tick diagnostic must never throw.

The >50 ms slow-tick breakdown in `tick_pipeline.logical_tick` referenced
`is_transition_active` after transition state was removed from the logical step,
so the installed run hit `NameError: name 'is_transition_active' is not defined`.
The logical runtime caught it and continued, turning the defect into a silent
timing hole instead of a crash. This bar forces the slow path and proves it
cannot raise.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QWidget

from widgets.spotify_visualizer import tick_pipeline


@pytest.fixture
def widget(qt_app, qtbot):
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    parent = QWidget()
    qtbot.addWidget(parent)
    w = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    qtbot.addWidget(w)
    w._enabled = True
    w._engine = None
    w._waiting_for_fresh_engine_frame = False
    w._waiting_for_fresh_frame = False
    yield w
    w.cleanup()


def test_the_slow_tick_breakdown_path_does_not_throw(widget, monkeypatch):
    monkeypatch.setattr(tick_pipeline, "is_perf_metrics_enabled", lambda: True)

    # Every time.time() call jumps 50 ms, so _tick_elapsed exceeds the 50 ms
    # slow-tick threshold and the breakdown log branch runs.
    clock = {"t": 1000.0}

    def _advancing():
        clock["t"] += 0.05
        return clock["t"]

    monkeypatch.setattr(tick_pipeline.time, "time", _advancing)

    # Must not raise (NameError or anything else) and must still publish.
    payload = tick_pipeline.logical_tick(widget)
    assert payload is not None
    assert widget._logical_mailbox.revision >= 1


def test_the_slow_tick_log_references_no_transition_state(widget):
    import ast
    import inspect

    source = inspect.getsource(tick_pipeline.logical_tick)
    tree = ast.parse(source)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "is_transition_active" not in names, (
        "the slow-tick diagnostic again references transition state that the "
        "logical step no longer computes"
    )
