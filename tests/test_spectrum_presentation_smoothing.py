from __future__ import annotations

import math
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor

from widgets.spotify_visualizer.spectrum_presentation_smoothing import (
    reset_widget_spectrum_presentation_smoothing,
    resolve_widget_spectrum_presentation,
)
from widgets.spotify_visualizer.tick_pipeline import push_gpu_frame


_TEMPORAL_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "visualizer_temporal"
    / "v1"
    / "spectrum_authoritative_smoothing.json"
)
_TEMPORAL_GOLDEN = (
    Path(__file__).parent
    / "goldens"
    / "visualizer_temporal"
    / "v1"
    / "spectrum_authoritative_smoothing.json"
)


def _state(**overrides):
    values = {
        "_vis_mode_str": "spectrum",
        "_spotify_playing": True,
        "_spectrum_visual_smoothing_enabled": True,
        "_spectrum_visual_smoothing": 0.5,
        "_display_bars_source_generation": 7,
        "_display_bars_source_activation": 3,
        "_bar_count": 1,
        "_spectrum_single_piece": True,
        "_spectrum_presentation_bars": [],
        "_spectrum_presentation_last_ts": 0.0,
        "_spectrum_presentation_identity": None,
        "_spectrum_presentation_pending": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_default_spectrum_smoothing_is_symmetric_and_sub_tick_bounded():
    widget = _state()

    first, first_changed = resolve_widget_spectrum_presentation(
        widget,
        [0.0],
        now_ts=1.0,
        first_frame=True,
    )
    rise, rise_changed = resolve_widget_spectrum_presentation(
        widget,
        [1.0],
        now_ts=1.01,
    )
    fall, fall_changed = resolve_widget_spectrum_presentation(
        widget,
        [0.0],
        now_ts=1.02,
    )

    expected_alpha = 1.0 - math.exp(-0.01 / 0.008)
    assert first == [0.0]
    assert first_changed is False
    assert rise_changed is True
    assert rise[0] == pytest.approx(expected_alpha)
    assert 0.70 < rise[0] < 0.72
    assert fall_changed is True
    assert fall[0] == pytest.approx(rise[0] * (1.0 - expected_alpha))
    assert 0.20 < fall[0] < 0.21
    assert widget._spectrum_presentation_pending is True


def test_spectrum_authoritative_tick_trace_matches_versioned_golden():
    fixture = json.loads(_TEMPORAL_FIXTURE.read_text(encoding="utf-8"))
    golden = json.loads(_TEMPORAL_GOLDEN.read_text(encoding="utf-8"))
    widget = _state(
        _spectrum_visual_smoothing_enabled=fixture["smoothing_enabled"],
        _spectrum_visual_smoothing=fixture["smoothing_strength"],
    )
    trace = []

    for tick in fixture["ticks"]:
        widget._display_bars_source_generation = int(tick["generation"])
        presented, presentation_changed = resolve_widget_spectrum_presentation(
            widget,
            [float(tick["source"])],
            now_ts=float(tick["timestamp"]),
            first_frame=bool(tick["first_frame"]),
        )
        trace.append(
            {
                "tick": int(tick["tick"]),
                "source": float(tick["source"]),
                "presented": round(float(presented[0]), 9),
                "presentation_changed": bool(presentation_changed),
                "settling": bool(widget._spectrum_presentation_pending),
            }
        )

    assert trace == golden["ticks"]
    assert trace[1]["presented"] >= golden["contract"][
        "minimum_default_first_tick_step"
    ]
    assert trace[1]["presented"] <= golden["contract"][
        "maximum_default_first_tick_step"
    ]
    assert trace[5]["presented"] == fixture["ticks"][5]["source"]
    assert trace[6]["presented"] == fixture["ticks"][6]["source"]
    assert golden["cadence"]["independent_timer_count"] == 0
    assert golden["cadence"]["paint_local_mutation_count"] == 0
    assert golden["cadence"]["overlay_self_update_requests"] == 0


def test_spectrum_smoothing_snaps_on_identity_stall_pause_and_disable():
    widget = _state()
    resolve_widget_spectrum_presentation(widget, [0.0], now_ts=1.0)
    resolve_widget_spectrum_presentation(widget, [1.0], now_ts=1.01)

    widget._display_bars_source_generation = 8
    generation_reset, _ = resolve_widget_spectrum_presentation(
        widget,
        [0.25],
        now_ts=1.02,
    )
    assert generation_reset == [0.25]

    stalled, _ = resolve_widget_spectrum_presentation(
        widget,
        [0.9],
        now_ts=1.12,
    )
    assert stalled == [0.9]

    widget._spotify_playing = False
    paused, _ = resolve_widget_spectrum_presentation(widget, [0.0], now_ts=1.13)
    assert paused == [0.0]
    assert widget._spectrum_presentation_bars == []

    widget._spotify_playing = True
    widget._spectrum_visual_smoothing_enabled = False
    disabled, _ = resolve_widget_spectrum_presentation(widget, [0.8], now_ts=1.14)
    assert disabled == [0.8]
    assert widget._spectrum_presentation_pending is False


def test_reset_discards_only_presentation_history():
    widget = _state(
        _display_bars=[0.6],
        _spectrum_presentation_bars=[0.4],
        _spectrum_presentation_last_ts=2.0,
        _spectrum_presentation_identity=(1,),
        _spectrum_presentation_pending=True,
    )

    reset_widget_spectrum_presentation_smoothing(widget)

    assert widget._display_bars == [0.6]
    assert widget._spectrum_presentation_bars == []
    assert widget._spectrum_presentation_identity is None
    assert widget._spectrum_presentation_pending is False


def test_gpu_push_settles_on_existing_tick_without_independent_cadence():
    pushes: list[list[float]] = []

    class _Parent:
        _spotify_bars_overlay = None

        def push_spotify_visualizer_frame(self, **kwargs):
            pushes.append(list(kwargs["bars"]))
            return True

    widget = _state(
        _display_bars=[0.0],
        _last_gpu_geom=None,
        _last_gpu_fade_sent=-1.0,
        _mode_transition_phase=0,
        _rainbow_enabled=False,
        _engine=None,
        _border_width=1,
        _bar_fill_color=QColor(1, 2, 3, 255),
        _bar_border_color=QColor(4, 5, 6, 255),
        _ghosting_enabled=False,
        _ghost_alpha=0.0,
        _ghost_decay_rate=0.4,
        _spectrum_border_radius=0.0,
        _has_pushed_first_frame=False,
        _spectrum_gpu_push_extras={},
    )
    widget._resolve_gpu_target_rect = lambda: QRect(0, 0, 100, 40)
    widget._get_gpu_fade_factor = lambda _now: 1.0
    widget._mode_transition_fade_factor = lambda _now: 1.0
    widget._dynamic_bar_segments = lambda: 18
    widget.update = lambda: None
    widget._on_first_frame_after_cold_start = lambda: None
    parent = _Parent()

    assert push_gpu_frame(widget, parent, 1.0, True, True) is True
    widget._display_bars = [1.0]
    assert push_gpu_frame(widget, parent, 1.01, True, False) is True
    second = pushes[-1][0]
    assert 0.70 < second < 0.72

    # Source is now unchanged, but the normal UI tick advances the bounded
    # presentation residual and publishes it through the same one push path.
    assert push_gpu_frame(widget, parent, 1.02, False, False) is True
    assert second < pushes[-1][0] < 1.0
    assert len(pushes) == 3
