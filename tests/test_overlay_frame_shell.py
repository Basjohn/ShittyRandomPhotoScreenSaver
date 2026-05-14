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
    overlay = SimpleNamespace(_enabled=False, _fade=1.0)

    assert frame_shell.resolve_frame_fade(overlay, logger) is None


def test_resolve_frame_fade_returns_none_for_invalid_or_nonpositive_values():
    logger = _CaptureLogger()
    bad_overlay = SimpleNamespace(_enabled=True, _fade=object())
    zero_overlay = SimpleNamespace(_enabled=True, _fade=0.0)

    assert frame_shell.resolve_frame_fade(bad_overlay, logger) is None
    assert frame_shell.resolve_frame_fade(zero_overlay, logger) is None
    assert logger.messages


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
