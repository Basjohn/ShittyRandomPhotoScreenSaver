"""N2.5 box 7: the Visualizer's native route (``rendering.quick.visualizer.native_route``, D10 point 4).

On Vulkan the Visualizer item never makes a Python render node; each of its update requests is the route's GUI-thread
take. These tests hold the item's side of that seam with a recording route (no native module): the backend decides
whether a route is attached at all, a native mode's update is the route's sync (never Qt's), another mode's activation
draws through the item's own node again (the mixed window) and retires the route's stream, and the preparation and
retained-snapshot queries answer for the route. The route's own drawing is proved on the module by
``tools/visualizer_replay/owner_render_parity.py --native`` (its hidden production scene attaches this route).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest


class _RecordingRoute:
    def __init__(self) -> None:
        self.calls: list = []
        self.identity = None

    def sync(self, **kwargs):
        self.calls.append(("sync", kwargs["identity"]))
        self.identity = kwargs["identity"]
        return True

    def unbind(self):
        self.calls.append(("unbind", None))
        self.identity = None

    def drop(self):
        self.calls.append(("drop", None))

    def retained_snapshot(self, identity):
        return ("retained", identity)

    def close(self):
        self.calls.append(("close", None))


def _identity(mode_id: str):
    return SimpleNamespace(mode_id=mode_id, runtime_generation=1, engine_generation=1, activation_id=1)


@pytest.mark.parametrize("backend,wanted", (("vulkan", True), ("opengl", False)))
def test_the_route_is_the_vulkan_backends_only(backend, wanted):
    from rendering.quick.visualizer import native_route

    assert native_route.native_route_wanted(backend) is wanted
    attached: list = []
    item = SimpleNamespace(attach_native_route=attached.append)
    if not wanted:
        assert native_route.attach_native_route(item, object(), backend) is None and attached == []


def test_a_mode_without_a_native_renderer_is_refused_before_anything_is_created():
    from rendering.quick.visualizer.native_route import NativeVisualizerRoute

    class _NoCore:
        def spectrum(self, _host):
            raise AssertionError("nothing is created for a mode the route does not draw")

    route = NativeVisualizerRoute(_NoCore(), object())
    with pytest.raises(ValueError, match="never offered"):
        route.bind(_identity("bubble"))


def _offered_on_vulkan() -> frozenset[str]:
    from core.settings import visualizer_mode_registry as modes

    return frozenset(d.mode_id for d in modes.iter_all_visualizer_mode_descriptors()
                     if "vulkan" in d.renderer_backends)


def test_vulkan_offers_exactly_the_modes_the_route_draws(monkeypatch):
    # D10: a mode is offered on Vulkan (its renderer_backends) only once the route draws it, and the route draws only
    # an offered mode: one answer, read from both owners, never a list here.
    import dataclasses

    from core.settings import visualizer_mode_registry as modes
    from rendering.quick.visualizer.native_route import NATIVE_MODE_IDS

    assert NATIVE_MODE_IDS and _offered_on_vulkan() == NATIVE_MODE_IDS
    # Control: a descriptor claiming Vulkan for a mode the route does not draw is caught.
    claimed = next(d.mode_id for d in modes.iter_all_visualizer_mode_descriptors() if d.mode_id not in NATIVE_MODE_IDS)
    monkeypatch.setattr(modes, "_ALL_DESCRIPTORS", tuple(
        dataclasses.replace(d, renderer_backends=("opengl", "vulkan")) if d.mode_id == claimed else d
        for d in modes._ALL_DESCRIPTORS))
    assert _offered_on_vulkan() != NATIVE_MODE_IDS


@pytest.mark.qt
def test_a_native_modes_update_is_the_routes_take_and_another_mode_draws_through_the_item(qt_app, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from rendering.quick.visualizer.item import VisualizerRenderItem

    qt_updates: list = []
    monkeypatch.setattr(QQuickItem, "update", lambda self: qt_updates.append(self))
    item = VisualizerRenderItem()
    route = _RecordingRoute()
    item.attach_native_route(route)
    has_contents = lambda: bool(item.flags() & QQuickItem.Flag.ItemHasContents)   # noqa: E731
    assert not has_contents()

    spectrum = _identity("spectrum")
    item._identity = spectrum
    item.update()
    assert route.calls == [("sync", spectrum)] and qt_updates == []         # the route's take, never a Qt sync
    assert item.updatePaintNode(None, None) is None                         # never a Python render node
    assert item.renderer_prepared("spectrum", 1) is True
    item._presentation = object()
    assert item.retained_snapshot(spectrum) == ("retained", spectrum)
    item._drop_retained = True
    item.update()
    assert route.calls[-2:] == [("drop", None), ("sync", spectrum)] and not item._drop_retained

    # The mixed window: another mode's activation draws through the item's own node; the native stream retires.
    route.calls.clear()
    item._identity = _identity("bubble")
    item.update()
    assert route.calls == [("unbind", None)] and qt_updates == [item] and has_contents()

    item.close_native_route()
    assert route.calls[-1] == ("close", None)


@pytest.mark.qt
def test_control_an_item_without_a_route_takes_qts_sync(qt_app, monkeypatch):
    # Negative control: the same update with no route attached is Qt's own request (the Python node's sync).
    from PySide6.QtQuick import QQuickItem

    from rendering.quick.visualizer.item import VisualizerRenderItem

    qt_updates: list = []
    monkeypatch.setattr(QQuickItem, "update", lambda self: qt_updates.append(self))
    item = VisualizerRenderItem()
    item._identity = _identity("spectrum")
    item.update()
    assert qt_updates == [item] and bool(item.flags() & QQuickItem.Flag.ItemHasContents)
