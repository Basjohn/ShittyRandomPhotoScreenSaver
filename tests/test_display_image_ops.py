from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QRect

from rendering import display_image_ops


def test_prewarm_spotify_visualizer_overlay_primes_shader_cache_before_overlay(monkeypatch):
    calls: list[object] = []

    class _FakeVisualizer:
        _vis_mode_str = "bubble"

        def geometry(self) -> QRect:
            return QRect(10, 20, 320, 160)

    class _FakeOverlay:
        def __init__(self) -> None:
            self._vis_mode = "spectrum"

        def prewarm_context(self, geom: QRect) -> None:
            calls.append(
                ("overlay", self._vis_mode, geom.x(), geom.y(), geom.width(), geom.height())
            )

    monkeypatch.setattr(
        "widgets.spotify_visualizer.shaders.preload_fragment_shaders",
        lambda: calls.append("shaders") or {"spectrum": "frag"},
    )
    monkeypatch.setattr(
        display_image_ops,
        "_ensure_spotify_bars_overlay",
        lambda widget: _FakeOverlay(),
    )

    widget = SimpleNamespace(spotify_visualizer_widget=_FakeVisualizer())

    assert display_image_ops.prewarm_spotify_visualizer_overlay(widget) is True
    assert calls == [
        "shaders",
        ("overlay", "bubble", 10, 20, 320, 160),
    ]


def test_ensure_spotify_bars_overlay_seeds_ctor_mode_from_visualizer(monkeypatch):
    calls: list[object] = []

    class _FakeVisualizer:
        _vis_mode_str = "devcurve"

    class _FakeWidget:
        spotify_visualizer_widget = _FakeVisualizer()
        _spotify_bars_overlay = None
        _resource_manager = None

    class _FakeOverlay:
        def __init__(self, parent, initial_mode=None) -> None:
            calls.append(("ctor", initial_mode))

        def setObjectName(self, name: str) -> None:
            calls.append(("name", name))

        def clear_overlay_buffer(self) -> None:
            return None

    monkeypatch.setattr(display_image_ops, "SpotifyBarsGLOverlay", _FakeOverlay)

    widget = _FakeWidget()
    overlay = display_image_ops._ensure_spotify_bars_overlay(widget)

    assert overlay is not None
    assert calls[0] == ("ctor", "devcurve")
