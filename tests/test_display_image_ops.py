from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QRect

from rendering import display_image_ops


def test_prewarm_spotify_visualizer_overlay_primes_shader_cache_before_overlay(monkeypatch):
    calls: list[object] = []

    class _FakeVisualizer:
        def geometry(self) -> QRect:
            return QRect(10, 20, 320, 160)

    class _FakeOverlay:
        def prewarm_context(self, geom: QRect) -> None:
            calls.append(("overlay", geom.x(), geom.y(), geom.width(), geom.height()))

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
        ("overlay", 10, 20, 320, 160),
    ]
