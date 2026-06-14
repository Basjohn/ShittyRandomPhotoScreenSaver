from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSize

from rendering.gl_compositor_pkg import overlays


class _Profiler:
    def __init__(self, metrics):
        self._metrics = metrics

    def get_metrics(self, name):
        return self._metrics.get(name)


class _OverlayWidget:
    def __init__(self):
        self._slide = None
        self._wipe = SimpleNamespace(progress=0.25)
        self._blockspin = None
        self._warp = None
        self._raindrops = None
        self._blockflip = None
        self._diffuse = None
        self._blinds = None
        self._crumble = None
        self._particle = None
        self._profiler = _Profiler({"wipe": (60.0, 14.0, 18.0, None)})
        self._debug_overlay_cache_key = None
        self._debug_overlay_cache_image = None
        self._size = QSize(320, 200)

    def size(self):
        return QSize(self._size)


@pytest.mark.qt_no_exception_capture
def test_render_debug_overlay_image_reuses_cached_image(monkeypatch, qt_app):
    widget = _OverlayWidget()
    monkeypatch.setattr(overlays, "is_perf_metrics_enabled", lambda: True)

    first = overlays.render_debug_overlay_image(widget)
    second = overlays.render_debug_overlay_image(widget)

    assert first is not None
    assert second is first


@pytest.mark.qt_no_exception_capture
def test_render_debug_overlay_image_invalidates_cache_when_payload_changes(monkeypatch, qt_app):
    widget = _OverlayWidget()
    monkeypatch.setattr(overlays, "is_perf_metrics_enabled", lambda: True)

    first = overlays.render_debug_overlay_image(widget)
    widget._wipe.progress = 0.55
    second = overlays.render_debug_overlay_image(widget)

    assert first is not None
    assert second is not None
    assert second is not first
