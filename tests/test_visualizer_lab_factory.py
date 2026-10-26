"""Construction injection keeps canonical admission and host lifetime ownership."""
from types import SimpleNamespace

import pytest

from rendering.quick.visualizer.implementation_registry import resolve_quick_visualizer_renderer
from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
from tests.test_qtquick_visualizer_mode_retirement import _install_host_render_stubs, _render_mode


def test_factory_is_only_consulted_for_canonical_cache_misses(monkeypatch):
    calls, releases = [], []
    def factory(mode):
        calls.append(mode)
        return SimpleNamespace(mode_id=mode, has_resources=False, render=lambda _frame: None,
                               release_resources=lambda: releases.append(mode))
    host = QuickVisualizerRenderHost(renderer_factory=factory)
    _install_host_render_stubs(monkeypatch, host, {})
    from rendering.quick.visualizer import render_host
    monkeypatch.setattr(render_host, "resolve_quick_visualizer_renderer", resolve_quick_visualizer_renderer)
    assert _render_mode(host, "bubble") == "bubble"
    _render_mode(host, "bubble")
    assert calls == ["bubble"]
    _render_mode(host, "spectrum")
    assert calls == ["bubble", "spectrum"] and releases == ["bubble"]
    host.release_resources()
    assert releases == ["bubble", "spectrum"]
    with pytest.raises(ValueError, match="unknown canonical"):
        resolve_quick_visualizer_renderer("invented", renderer_factory=factory)
    assert calls == ["bubble", "spectrum"]


@pytest.mark.parametrize("identity, render, error", [("spectrum", lambda _: None, RuntimeError), ("bubble", None, TypeError)])
def test_invalid_factory_products_are_rejected_and_retired(identity, render, error):
    retired = []
    product = SimpleNamespace(mode_id=identity, render=render, release_resources=lambda: retired.append(True))
    with pytest.raises(error):
        resolve_quick_visualizer_renderer("bubble", renderer_factory=lambda _mode: product)
    assert retired == [True]
