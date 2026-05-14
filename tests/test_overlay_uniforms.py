from __future__ import annotations

from types import SimpleNamespace

import widgets.spotify_visualizer.overlay_uniforms as overlay_uniforms


class _CaptureGL:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def glUniform2f(self, loc, a, b) -> None:
        self.calls.append(("glUniform2f", loc, a, b))

    def glUniform1f(self, loc, value) -> None:
        self.calls.append(("glUniform1f", loc, value))

    def glUniform1i(self, loc, value) -> None:
        self.calls.append(("glUniform1i", loc, value))


class _CaptureLogger:
    def __init__(self) -> None:
        self.info_messages: list[str] = []
        self.warning_messages: list[str] = []

    def info(self, msg, *args, **kwargs) -> None:
        self.info_messages.append(msg % args if args else str(msg))

    def warning(self, msg, *args, **kwargs) -> None:
        self.warning_messages.append(msg % args if args else str(msg))


def _make_overlay(**overrides):
    base = dict(
        _accumulated_time=10.0,
        _border_width_px=2.0,
        _rainbow_enabled=True,
        _rainbow_per_bar=True,
        _spectrum_rainbow_border=True,
        _rainbow_speed=1.5,
        _rainbow_logged_mode=None,
        _get_dpr=lambda: 1.5,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_upload_common_uniforms_sets_shared_and_global_rainbow_uniforms():
    gl = _CaptureGL()
    logger = _CaptureLogger()
    overlay = _make_overlay()
    uniforms = {
        "u_resolution": 1,
        "u_dpr": 2,
        "u_fade": 3,
        "u_time": 4,
        "u_border_width": 5,
        "u_rainbow_per_bar": 6,
        "u_rainbow_border": 7,
        "u_rainbow_hue_offset": 8,
    }

    overlay_uniforms.upload_common_uniforms(gl, uniforms, overlay, "bubble", 640, 360, 1.2, logger)

    assert ("glUniform2f", 1, 640.0, 360.0) in gl.calls
    assert ("glUniform1f", 2, 1.5) in gl.calls
    assert ("glUniform1f", 3, 1.0) in gl.calls
    assert ("glUniform1f", 4, 10.0) in gl.calls
    assert ("glUniform1f", 5, 2.0) in gl.calls
    assert ("glUniform1i", 6, 1) in gl.calls
    assert ("glUniform1i", 7, 1) in gl.calls

    hue_call = next(call for call in gl.calls if call[:2] == ("glUniform1f", 8))
    assert 0.0 < hue_call[2] < 1.0
    assert overlay._rainbow_logged_mode == "bubble"
    assert len(logger.info_messages) == 1
    assert "Rainbow ACTIVE" in logger.info_messages[0]


def test_upload_common_uniforms_uses_per_bar_cycle_when_global_rainbow_disabled_for_spectrum():
    gl = _CaptureGL()
    logger = _CaptureLogger()
    overlay = _make_overlay(
        _rainbow_enabled=False,
        _rainbow_per_bar=True,
        _spectrum_rainbow_border=False,
        _rainbow_logged_mode="spectrum",
    )
    uniforms = {"u_rainbow_hue_offset": 8, "u_rainbow_per_bar": 6, "u_rainbow_border": 7}

    overlay_uniforms.upload_common_uniforms(gl, uniforms, overlay, "spectrum", 640, 360, 0.4, logger)

    hue_call = next(call for call in gl.calls if call[:2] == ("glUniform1f", 8))
    assert 0.0 < hue_call[2] < 1.0
    assert overlay._rainbow_logged_mode is None
    assert ("glUniform1i", 6, 1) in gl.calls
    assert ("glUniform1i", 7, 0) in gl.calls
    assert not logger.info_messages
    assert not logger.warning_messages


def test_upload_common_uniforms_warns_when_global_rainbow_uniform_missing():
    gl = _CaptureGL()
    logger = _CaptureLogger()
    overlay = _make_overlay(_rainbow_enabled=True)

    overlay_uniforms.upload_common_uniforms(gl, {}, overlay, "devcurve", 640, 360, 0.5, logger)

    assert len(logger.warning_messages) == 1
    assert "Rainbow BROKEN" in logger.warning_messages[0]
