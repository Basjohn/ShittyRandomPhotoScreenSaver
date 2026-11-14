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


# ------------------------------------------------------------------- the route itself (audit 14 Nov, M4, M1, H1)

class _Composite:
    def __init__(self, log: list) -> None:
        self.log = log
        self.destroyed = False

    def set(self, **config):
        self.log.append(("set", config))

    def place(self, geometry, origin, **config):
        self.log.append(("place", geometry.item_config(origin), config))

    def destroy(self):
        self.destroyed = True
        self.log.append(("destroy", None))
        return True

    def window_pixels(self):
        return (2560, 1440)                    # Qt's own framebuffer of the 1707x960 window at 150 % (L1)


class _Spectrum:
    """A stand-in NativeSpectrum: records what the route hands the native item."""

    def __init__(self, log: list, *, fail_bind: int = 0, fail_program: int = 0, fail_settings: int = 0,
                 fail_unbind: int = 0) -> None:
        self.log = log
        self.composite = _Composite(log)
        self.fail_bind = fail_bind
        self.fail_program = fail_program
        self.fail_settings = fail_settings
        self.fail_unbind = fail_unbind

    def program(self, pack):
        self.log.append(("program", bool(pack)))
        if self.fail_program:
            self.fail_program -= 1
            raise FileNotFoundError("no pack")

    def bind(self, name, *, expect=None):
        self.log.append(("bind", name))
        if self.fail_bind:
            self.fail_bind -= 1
            raise ValueError("the reader refused the mapping")

    def settings(self, values):
        self.log.append(("settings", (values,)))
        if self.fail_settings:
            self.fail_settings -= 1
            raise ValueError("a settings value the core refuses")

    def unbind(self):
        self.log.append(("unbind", ()))
        if self.fail_unbind:
            self.fail_unbind -= 1
            raise BufferError("cannot close exported pointers exist")

    def __getattr__(self, name):
        if name in ("present_raw", "update", "drop_retained_frame"):
            return lambda *args: self.log.append((name, args))
        raise AttributeError(name)


class _Core:
    def __init__(self, **failures) -> None:
        self.log: list = []
        self.made: list = []
        self.failures = failures

    def spectrum(self, _host):
        spectrum = _Spectrum(self.log, **self.failures)
        self.made.append(spectrum)
        return spectrum


class _Bridge:
    def __init__(self) -> None:
        self.snapshots: list = []

    def admit_at_sync(self):
        pass

    def take_for_render(self, **_kwargs):
        return self.snapshots.pop(0) if self.snapshots else None


def _route_presentation(window_size, dpr, **overrides):
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from tests._visualizer_presentation import resolve_presentation

    kwargs = dict(policy=get_visualizer_presentation_policy("spectrum"), display_size=window_size,
                  viewport_extent=(820.0, 210.0), outer_origin=(803.0, 517.0), dpr=dpr)
    kwargs.update(overrides)
    return resolve_presentation(**kwargs)


@pytest.fixture
def route_world(monkeypatch):
    """A route on a stand-in core in a 2560x1440 window at 150 % (logical 1707x960: the H1 case), with the frame
    record and the settings arithmetic stubbed (both have their own parity tests)."""
    from core.visualizer_engine import spectrum_native_schema
    from rendering.native import program_values
    from rendering.quick.visualizer.implementations import spectrum as implementation
    from rendering.quick.visualizer.native_route import NativeVisualizerRoute

    window = SimpleNamespace(width=lambda: 1707, height=lambda: 960)
    host = SimpleNamespace(window=lambda: window)
    monkeypatch.setattr(spectrum_native_schema, "encode", lambda logical: b"record %d" % logical.value)
    monkeypatch.setattr(program_values, "mode_fragment_pack", lambda _mode: b"pack")
    monkeypatch.setattr(implementation, "spectrum_settings_values",
                        lambda logical, presentation, **card: {"u_test": float(card["item_size"][0])})
    names: list = []
    from core.visualizer_engine import packet_abi

    create = packet_abi.create_frame_mapping

    def recording_create(**kwargs):
        memory = create(**kwargs)
        names.append(memory.name)
        return memory

    monkeypatch.setattr(packet_abi, "create_frame_mapping", recording_create)
    routes: list = []

    def make(**failures):
        core = _Core(**failures)
        route = NativeVisualizerRoute(core, host)
        routes.append(route)
        return route, core

    world = SimpleNamespace(make=make, names=names, presentation=_route_presentation((1707.0, 960.0), 1.5))
    yield world
    for route in routes:
        route.close()


def _snapshot(presentation, value: int):
    logical = SimpleNamespace(value=value, logical_timestamp=float(value), present_frame=True)
    return SimpleNamespace(logical=logical, presentation=presentation)


def _sync(route, bridge, identity, presentation):
    return route.sync(bridge=bridge, identity=identity, presentation=presentation, authority=True)


def _mapping_opens(name: str) -> bool:
    from multiprocessing.shared_memory import SharedMemory

    try:
        memory = SharedMemory(name=name)
    except FileNotFoundError:
        return False
    memory.close()
    return True


def test_the_route_publishes_new_snapshots_and_sends_an_unchanged_card_once(route_world):
    route, core = route_world.make()
    bridge = _Bridge()
    identity = _identity("spectrum")
    presentation = route_world.presentation
    bridge.snapshots = [_snapshot(presentation, 1)]
    assert _sync(route, bridge, identity, presentation) is True and not route.failed
    # H1 through the route: placed on the window's own ratio (2560 / 1707 across), the card's map whole pixels.
    place = next(entry for entry in core.log if entry[0] == "place")
    assert place[1]["pixel_ratio"] == [2560 / 1707, 1440 / 960]
    # A new activation's first frame shows at once: its fade-in is the card's own content fade (the Python renderer's,
    # so rule (a) holds from the first frame); a composite fade on top would fade it twice.
    assert place[2] == {"visible": True, "fade_ms": 0}
    card = next(entry[1][0] for entry in core.log if entry[0] == "present_raw")
    assert all(value == round(value) for value in card["window_from_target"])
    # No new snapshot: nothing published, nothing sent.
    before = list(core.log)
    assert _sync(route, bridge, identity, presentation) is False and core.log == before and route.published == 1
    # A new snapshot under the same card: published, the card and settings not sent again.
    bridge.snapshots = [_snapshot(presentation, 2)]
    assert _sync(route, bridge, identity, presentation) is True and route.published == 2
    sent = [entry[0] for entry in core.log[len(before):]]
    assert sent == ["update"]
    # Control: another card (a re-placed record) is sent again.
    moved = _route_presentation((1707.0, 960.0), 1.5, outer_origin=(601.0, 333.0))
    bridge.snapshots = [_snapshot(moved, 3)]
    mark = len(core.log)
    assert _sync(route, bridge, identity, moved) is True
    assert {"place", "present_raw", "update"} <= {entry[0] for entry in core.log[mark:]}


def test_unbind_closes_and_unlinks_the_mapping_and_close_destroys_the_composite(route_world):
    route, core = route_world.make()
    bridge = _Bridge()
    bridge.snapshots = [_snapshot(route_world.presentation, 1)]
    _sync(route, bridge, _identity("spectrum"), route_world.presentation)
    name = route_world.names[-1]
    assert _mapping_opens(name)                                   # control: open while bound
    route.unbind()
    assert not _mapping_opens(name) and ("unbind", ()) in core.log
    assert not core.made[0].composite.destroyed                   # control: an unbind keeps the native item
    route.close()
    assert core.made[0].composite.destroyed


def test_a_failed_bind_fails_closed_with_no_mapping_left(route_world):
    # M1: the core's bind refuses the stream. The route never raises, leaves no mapping, hides, and does not try again
    # at every update while nothing changed; another identity tries again.
    route, core = route_world.make(fail_bind=2)
    bridge = _Bridge()
    identity = _identity("spectrum")
    bridge.snapshots = [_snapshot(route_world.presentation, 1)]
    assert _sync(route, bridge, identity, route_world.presentation) is False
    assert route.failed and route.failures == 1 and route_world.names
    assert not any(_mapping_opens(name) for name in route_world.names)
    binds = sum(1 for entry in core.log if entry[0] == "bind")
    for _ in range(3):
        assert _sync(route, bridge, identity, route_world.presentation) is False
    assert sum(1 for entry in core.log if entry[0] == "bind") == binds and route.failures == 1
    # Another identity is a changed input: tried again (and refused again, still no mapping left).
    other = SimpleNamespace(mode_id="spectrum", runtime_generation=1, engine_generation=1, activation_id=2)
    assert _sync(route, bridge, other, route_world.presentation) is False
    assert sum(1 for entry in core.log if entry[0] == "bind") == binds + 1
    assert not any(_mapping_opens(name) for name in route_world.names)
    # Control: the bind accepted at the next identity draws.
    third = SimpleNamespace(mode_id="spectrum", runtime_generation=1, engine_generation=1, activation_id=3)
    bridge.snapshots = [_snapshot(route_world.presentation, 2)]
    assert _sync(route, bridge, third, route_world.presentation) is True and not route.failed
    assert _mapping_opens(route_world.names[-1])


def test_a_program_that_did_not_load_is_loaded_again(route_world):
    # M1: the pack failed to load (a frozen build without it): no mapping is made, and the next bind loads it again
    # instead of drawing with no program.
    route, core = route_world.make(fail_program=1)
    bridge = _Bridge()
    bridge.snapshots = [_snapshot(route_world.presentation, 1)]
    assert _sync(route, bridge, _identity("spectrum"), route_world.presentation) is False and route.failed
    assert route_world.names == []                                # the program first: no mapping was made
    other = SimpleNamespace(mode_id="spectrum", runtime_generation=1, engine_generation=1, activation_id=2)
    bridge.snapshots = [_snapshot(route_world.presentation, 2)]
    assert _sync(route, bridge, other, route_world.presentation) is True
    assert [entry for entry in core.log if entry[0] == "program"] == [("program", True), ("program", True)]
    assert len(core.made) == 1                                    # one native item, its program retried


def test_a_window_that_is_gone_fails_closed(route_world, monkeypatch):
    # H1/M1: no exception reaches the item's update, whatever the window says.
    route, core = route_world.make()
    route._content_host = SimpleNamespace(window=lambda: None)
    bridge = _Bridge()
    bridge.snapshots = [_snapshot(route_world.presentation, 1)]
    assert _sync(route, bridge, _identity("spectrum"), route_world.presentation) is False
    assert route.failed and route.published == 0


def test_a_refused_frame_fades_the_card_out_and_the_next_new_snapshot_draws_again(route_world, monkeypatch):
    # Audit N29 M1: a frame's own failure (here its settings, refused once) is not latched for the activation: the card
    # fades out (never set invisible at once) and the next new snapshot, with its own settings, draws again.
    from rendering.quick.visualizer.implementations import spectrum as implementation
    from rendering.quick.visualizer.native_route import FAILURE_FADE_MS

    route, core = route_world.make()
    bridge = _Bridge()
    identity = _identity("spectrum")
    presentation = route_world.presentation
    bridge.snapshots = [_snapshot(presentation, 1)]
    assert _sync(route, bridge, identity, presentation) is True                 # placed and shown
    monkeypatch.setattr(implementation, "spectrum_settings_values",
                        lambda logical, presentation, **card: {"u_test": float(logical.value)})
    core.made[0].fail_settings = 1
    bridge.snapshots = [_snapshot(presentation, 2)]
    assert _sync(route, bridge, identity, presentation) is False and route.failed and route.failures == 1
    hide = [entry for entry in core.log if entry[0] == "set" and entry[1].get("visible") is False]
    assert hide and all(entry[1].get("fade_ms") == FAILURE_FADE_MS for entry in hide)
    bridge.snapshots = [_snapshot(presentation, 3)]
    assert _sync(route, bridge, identity, presentation) is True and not route.failed
    shown = [entry for entry in core.log if entry[0] == "place"]
    assert len(shown) == 2 and shown[-1][2] == {"visible": True, "fade_ms": FAILURE_FADE_MS}   # faded in again
    # Control: a setup failure (a refused bind) with the same inputs is not tried at the next snapshot.
    latched, latched_core = route_world.make(fail_bind=1)
    bridge.snapshots = [_snapshot(presentation, 4)]
    assert _sync(latched, bridge, identity, presentation) is False and latched.failed
    binds = sum(1 for entry in latched_core.log if entry[0] == "bind")
    bridge.snapshots = [_snapshot(presentation, 5)]
    assert _sync(latched, bridge, identity, presentation) is False
    assert sum(1 for entry in latched_core.log if entry[0] == "bind") == binds


def test_the_routes_teardown_branches_never_raise_and_a_missing_window_logs_at_debug(route_world, caplog):
    # Audit N29 L2: unbind (here a mapping whose close raises) and the hide run guarded; a window that is not there yet
    # is an ordinary startup state, logged at debug, never an error.
    import logging

    route, core = route_world.make(fail_unbind=1)
    bridge = _Bridge()
    bridge.snapshots = [_snapshot(route_world.presentation, 1)]
    assert _sync(route, bridge, _identity("spectrum"), route_world.presentation) is True
    assert route.sync(bridge=bridge, identity=None, presentation=route_world.presentation, authority=True) is False
    waiting, _core = route_world.make()
    waiting._content_host = SimpleNamespace(window=lambda: None)
    with caplog.at_level(logging.DEBUG, logger="rendering.quick.visualizer.native_route"):
        assert _sync(waiting, bridge, _identity("spectrum"), route_world.presentation) is False
    native = [record for record in caplog.records if "native route" in record.getMessage().lower()]
    assert native and all(record.levelno == logging.DEBUG for record in native)


def test_the_parity_tools_route_takes_the_routes_own_card_call(route_world):
    # rule (a)'s route (owner_render_parity) overrides card(); the route calls it with the window's metrics. When the
    # two disagreed, every parity run's native item failed closed and drew nothing (found 14 Nov, N2.9 round 2).
    from tools.visualizer_replay.owner_render_parity import _ParityRoute

    probe, core = route_world.make()
    mirror = SimpleNamespace(python_mappings=[((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0)], mapping_compared=0,
                             mapping_identical=0)
    route = _ParityRoute.make(core, probe._content_host, mirror)
    try:
        bridge = _Bridge()
        bridge.snapshots = [_snapshot(route_world.presentation, 1)]
        assert _sync(route, bridge, _identity("spectrum"), route_world.presentation) is True and not route.failed
        assert mirror.mapping_compared == 1
    finally:
        route.close()


def test_the_routes_fade_is_the_visualizers_activation_fade():
    from rendering.quick.visualizer.native_route import FAILURE_FADE_MS
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner

    assert FAILURE_FADE_MS == round(owner._ACTIVATION_SCENE_FADE_DURATION_S * 1000.0)


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
