from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect

import widgets.spotify_visualizer.overlay_frame_shell as frame_shell


class _CaptureGL:
    GL_SCISSOR_TEST = 1
    GL_COLOR_BUFFER_BIT = 2

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def glDisable(self, value) -> None:
        self.calls.append(("glDisable", value))

    def glClearColor(self, a, b, c, d) -> None:
        self.calls.append(("glClearColor", a, b, c, d))

    def glClear(self, value) -> None:
        self.calls.append(("glClear", value))


class _CaptureLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def debug(self, msg, *args, **kwargs) -> None:
        self.messages.append(msg % args if args else str(msg))


def _spectrum_overlay(bars: list[float]) -> SimpleNamespace:
    updates: list[str] = []
    return SimpleNamespace(
        _enabled=True,
        _vis_mode="spectrum",
        _bars=list(bars),
        _bar_count=len(bars),
        _perf_set_state_total=1,
        _engine_generation=4,
        _activation_id=7,
        _last_reset_ts=0.0,
        _begin_painted_card_stencil_clip=lambda _rect: True,
        _end_painted_card_stencil_clip=lambda _active: None,
        _request_frame_update=lambda: updates.append("update"),
        _test_updates=updates,
    )


def test_clear_overlay_backbuffer_runs_standard_clear_sequence():
    gl = _CaptureGL()
    logger = _CaptureLogger()

    frame_shell.clear_overlay_backbuffer(gl, logger)

    assert gl.calls == [
        ("glDisable", gl.GL_SCISSOR_TEST),
        ("glClearColor", 0.0, 0.0, 0.0, 0.0),
        ("glClear", gl.GL_COLOR_BUFFER_BIT),
    ]
    assert not logger.messages


def test_resolve_frame_fade_returns_none_when_disabled():
    logger = _CaptureLogger()
    overlay = SimpleNamespace(
        _enabled=False,
        _fade=1.0,
        _spectrum_presentation_bars=[0.5],
    )

    assert frame_shell.resolve_frame_fade(overlay, logger) is None
    assert not hasattr(overlay, "_spectrum_presentation_bars")


def test_resolve_frame_fade_returns_none_for_invalid_or_nonpositive_values():
    logger = _CaptureLogger()
    bad_overlay = SimpleNamespace(_enabled=True, _fade=object())
    zero_overlay = SimpleNamespace(_enabled=True, _fade=0.0)

    assert frame_shell.resolve_frame_fade(bad_overlay, logger) is None
    assert frame_shell.resolve_frame_fade(zero_overlay, logger) is None
    assert logger.messages


def test_spectrum_first_presentation_frame_snaps_to_authoritative_source():
    overlay = _spectrum_overlay([0.2, 0.8])

    active = frame_shell.advance_spectrum_presentation(overlay, now_ts=1.0)

    assert active is False
    assert overlay._bars == [0.2, 0.8]
    assert overlay._spectrum_presentation_target_bars == [0.2, 0.8]


def test_spectrum_attack_is_immediate_while_decay_is_smoothed():
    overlay = _spectrum_overlay([0.2, 1.0])
    frame_shell.advance_spectrum_presentation(overlay, now_ts=1.0)

    overlay._bars = [0.9, 0.0]
    overlay._perf_set_state_total += 1
    active = frame_shell.advance_spectrum_presentation(overlay, now_ts=1.016)

    assert active is True
    assert overlay._bars[0] == pytest.approx(0.9)
    assert 0.0 < overlay._bars[1] < 1.0
    assert overlay._spectrum_presentation_target_bars == [0.9, 0.0]


def test_spectrum_generation_or_activation_change_snaps_without_stale_decay():
    overlay = _spectrum_overlay([1.0])
    frame_shell.advance_spectrum_presentation(overlay, now_ts=1.0)

    overlay._bars = [0.0]
    overlay._perf_set_state_total += 1
    overlay._engine_generation = 5
    overlay._activation_id = 8
    active = frame_shell.advance_spectrum_presentation(overlay, now_ts=1.016)

    assert active is False
    assert overlay._bars == [0.0]


def test_non_spectrum_mode_is_untouched():
    overlay = _spectrum_overlay([0.4, 0.7])
    overlay._vis_mode = "bubble"

    active = frame_shell.advance_spectrum_presentation(overlay, now_ts=1.0)

    assert active is False
    assert overlay._bars == [0.4, 0.7]
    assert not hasattr(overlay, "_spectrum_presentation_bars")


def test_render_overlay_frame_requests_only_local_decay_continuation():
    overlay = _spectrum_overlay([1.0])
    frame_shell.advance_spectrum_presentation(overlay, now_ts=1.0)
    overlay._bars = [0.0]
    overlay._perf_set_state_total += 1
    overlay._spectrum_presentation_last_ts = 1.0

    rendered: list[float] = []

    def _render(_rect, _fade):
        rendered.extend(overlay._bars)

    original_monotonic = frame_shell.time.monotonic
    frame_shell.time.monotonic = lambda: 1.016
    try:
        frame_shell.render_overlay_frame(
            overlay,
            QRect(0, 0, 320, 180),
            1.0,
            _render,
        )
    finally:
        frame_shell.time.monotonic = original_monotonic

    assert 0.0 < rendered[0] < 1.0
    assert overlay._test_updates == ["update"]


def test_render_overlay_frame_wraps_render_in_stencil_lifecycle():
    calls: list[tuple] = []

    def _begin(rect):
        calls.append(("begin", rect.width(), rect.height()))
        return True

    def _end(active):
        calls.append(("end", active))

    def _render(rect, fade):
        calls.append(("render", rect.width(), rect.height(), fade))

    overlay = SimpleNamespace(
        _begin_painted_card_stencil_clip=_begin,
        _end_painted_card_stencil_clip=_end,
    )
    rect = QRect(0, 0, 320, 180)

    frame_shell.render_overlay_frame(overlay, rect, 0.75, _render)

    assert calls == [
        ("begin", 320, 180),
        ("render", 320, 180, 0.75),
        ("end", True),
    ]


def test_render_overlay_frame_always_ends_stencil_after_render_error():
    calls: list[tuple] = []

    def _begin(rect):
        calls.append(("begin", rect.width(), rect.height()))
        return False

    def _end(active):
        calls.append(("end", active))

    def _render(rect, fade):
        calls.append(("render", rect.width(), rect.height(), fade))
        raise RuntimeError("boom")

    overlay = SimpleNamespace(
        _begin_painted_card_stencil_clip=_begin,
        _end_painted_card_stencil_clip=_end,
    )
    rect = QRect(0, 0, 320, 180)

    with pytest.raises(RuntimeError, match="boom"):
        frame_shell.render_overlay_frame(overlay, rect, 0.5, _render)

    assert calls == [
        ("begin", 320, 180),
        ("render", 320, 180, 0.5),
        ("end", False),
    ]
