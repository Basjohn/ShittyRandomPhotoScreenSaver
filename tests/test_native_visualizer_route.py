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
        from rendering.native.composite import ContentStatus

        self.log = log
        self.destroyed = False
        self.pixels: tuple | None = (2560, 1440)   # Qt's own framebuffer of the 1707x960 window at 150 % (L1)
        self.status = ContentStatus(draws=0, failures=0, refused_run=0, failing=False)

    def set(self, **config):
        self.log.append(("set", config))

    def place(self, geometry, origin, **config):
        self.log.append(("place", geometry.item_config(origin), config))

    def destroy(self):
        self.destroyed = True
        self.log.append(("destroy", None))
        return True

    def window_pixels(self):
        return self.pixels                     # None: the native item has not synchronised with the window (M3)

    def update(self):
        self.log.append(("composite_update", ()))

    def content_status(self):
        return self.status                     # read at every sync: never logged


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

    size = {"width": 1707, "height": 960}
    window = SimpleNamespace(width=lambda: size["width"], height=lambda: size["height"],
                             afterSynchronizing=_Signal("afterSynchronizing"), afterRendering=_Signal("afterRendering"))
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

    world = SimpleNamespace(make=make, names=names, presentation=_route_presentation((1707.0, 960.0), 1.5),
                            window=window, size=size)
    yield world
    for route in routes:
        route.close()


class _Signal:
    """A stand-in window signal: the route's edge connects a queued receiver; ``emit`` delivers it (the GUI thread's
    queued call)."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.slots: list = []
        self.connections = 0

    def connect(self, slot, _type=None):
        self.slots.append(slot)
        self.connections += 1

    def disconnect(self, slot):
        self.slots.remove(slot)

    def emit(self):
        for slot in list(self.slots):
            slot()


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
    # Audit N29 L2: the unbind (here the native item's own unbind raising) runs guarded, and the route's mapping is
    # still closed and unlinked; a window that is not there yet is an ordinary startup state, logged at debug.
    import logging

    route, core = route_world.make(fail_unbind=1)
    bridge = _Bridge()
    bridge.snapshots = [_snapshot(route_world.presentation, 1)]
    assert _sync(route, bridge, _identity("spectrum"), route_world.presentation) is True
    name = route_world.names[-1]
    assert _mapping_opens(name)                                   # control: open while bound
    assert route.sync(bridge=bridge, identity=None, presentation=route_world.presentation, authority=True) is False
    assert ("unbind", ()) in core.log and not _mapping_opens(name) and route.identity is None
    # Control: unguarded, the same raising unbind reaches the caller (the guard is what keeps the update alive).
    raising, _raising_core = route_world.make(fail_unbind=1)
    bridge.snapshots = [_snapshot(route_world.presentation, 2)]
    assert _sync(raising, bridge, _identity("spectrum"), route_world.presentation) is True
    with pytest.raises(BufferError):
        raising.unbind()
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


# ------------------------------------------------------------------- N2.9 round 2's audit (M1 to M5, L3, L5)

def _places(core) -> list:
    return [entry for entry in core.log if entry[0] == "place"]


def _hides(core) -> list:
    return [entry for entry in core.log if entry[0] == "set" and entry[1].get("visible") is False]


def _wired(route, bridge, identity, presentation_of):
    """The item's update as the route's request (``VisualizerRenderItem.attach_native_route``)."""
    calls: list = []

    def update():
        calls.append(1)
        _sync(route, bridge, identity, presentation_of())

    # (getattr: the same test runs against the pre-fix route as its negative control, which has no request at all)
    getattr(route, "set_update_request", lambda request: None)(update)
    return calls


def test_a_failed_take_is_a_frame_failure_tried_again_at_the_next_update(route_world):
    # M1: the take raising once (a rebase refusal, a bridge error at an engine handover) fades the card out, and the next
    # update takes again and fades it back in. Before, the take was the setup's stage: latched, nothing taken again.
    from rendering.quick.visualizer.native_route import FAILURE_FADE_MS

    route, core = route_world.make()
    identity = _identity("spectrum")
    presentation = route_world.presentation

    class _RaisingOnce(_Bridge):
        raises = 0
        takes = 0

        def take_for_render(self, **kwargs):
            self.takes += 1
            if self.raises:
                self.raises -= 1
                raise RuntimeError("a presentation rebase refused")
            return super().take_for_render(**kwargs)

    bridge = _RaisingOnce()
    bridge.snapshots = [_snapshot(presentation, 1)]
    assert _sync(route, bridge, identity, presentation) is True
    bridge.raises = 1
    bridge.snapshots = [_snapshot(presentation, 2)]
    assert _sync(route, bridge, identity, presentation) is False and route.failed
    assert _hides(core) and _hides(core)[-1][1]["fade_ms"] == FAILURE_FADE_MS
    takes = bridge.takes
    published = [_sync(route, bridge, identity, presentation) for _ in range(1)]
    assert bridge.takes == takes + 1 and published == [True] and not route.failed
    assert _places(core)[-1][2] == {"visible": True, "fade_ms": FAILURE_FADE_MS}      # faded back in


def test_a_card_never_shown_fades_in_when_its_first_frame_comes_late(route_world):
    # M2: a setup failure before the first placement (a refused bind), retried at a changed input: the first frame is
    # late, so it fades in (it popped in at full opacity before).
    from rendering.quick.visualizer.native_route import FAILURE_FADE_MS

    route, core = route_world.make(fail_bind=1)
    bridge = _Bridge()
    identity = _identity("spectrum")
    bridge.snapshots = [_snapshot(route_world.presentation, 1)]
    assert _sync(route, bridge, identity, route_world.presentation) is False and route.failed
    moved = _route_presentation((1707.0, 960.0), 1.5, outer_origin=(804.0, 517.0))      # one pixel right: retried
    bridge.snapshots = [_snapshot(moved, 2)]
    assert _sync(route, bridge, identity, moved) is True and not route.failed
    assert [entry[2] for entry in _places(core)] == [{"visible": True, "fade_ms": FAILURE_FADE_MS}]
    # Control: an activation whose first frame is on time shows at once (its fade-in is the card's content fade).
    on_time, on_time_core = route_world.make()
    bridge.snapshots = [_snapshot(route_world.presentation, 3)]
    assert _sync(on_time, bridge, _identity("spectrum"), route_world.presentation) is True
    assert [entry[2] for entry in _places(on_time_core)] == [{"visible": True, "fade_ms": 0}]


def test_an_update_waiting_for_the_framebuffer_is_redone_at_the_windows_synchronisation(route_world):
    # M3 case 1: the native item has not read its window's framebuffer yet (before the window's first frame). The
    # update is not dropped: the route asks for the item's synchronisation and the window's afterSynchronizing re-runs
    # the update, which draws the frame the bridge holds with no new revision. Not a failure; nothing hidden.
    route, core = route_world.make()
    bridge = _Bridge()
    identity = _identity("spectrum")
    presentation = route_world.presentation
    calls = _wired(route, bridge, identity, lambda: presentation)
    route._window_metrics(presentation)             # the native item made (the route's prepare at attach)
    composite = core.made[0].composite
    composite.pixels = None
    bridge.snapshots = [_snapshot(presentation, 1)]
    assert _sync(route, bridge, identity, presentation) is False
    assert not route.failed and route.published == 0 and route.waits == 1 and _hides(core) == []
    signal = route_world.window.afterSynchronizing
    assert signal.slots and ("composite_update", ()) in core.log
    composite.pixels = (2560, 1440)                 # the item's sync read the framebuffer
    signal.emit()
    assert calls == [1] and route.published == 1 and signal.slots == []           # drawn; the edge fired once
    assert _places(core)                                                            # shown (it fades in: late)


def test_a_resize_is_carded_again_at_rest_once_the_item_has_read_the_new_framebuffer(route_world):
    # M3 case 2: the window resized while nothing new is published. The card stays shown (no fade-out for a resize);
    # once the native item's synchronisation read the new framebuffer, the retained frame is carded and placed for it.
    route, core = route_world.make()
    bridge = _Bridge()
    identity = _identity("spectrum")
    current = {"presentation": route_world.presentation}
    calls = _wired(route, bridge, identity, lambda: current["presentation"])
    bridge.snapshots = [_snapshot(current["presentation"], 1)]
    assert _sync(route, bridge, identity, current["presentation"]) is True
    first_card = next(entry[1][0] for entry in core.log if entry[0] == "present_raw")
    composite = core.made[0].composite
    route_world.size.update(width=1280, height=720)
    current["presentation"] = _route_presentation((1280.0, 720.0), 1.5, outer_origin=(201.0, 300.0))
    composite.pixels = None                          # stale: the item has not synchronised since the resize
    mark = len(core.log)
    assert _sync(route, bridge, identity, current["presentation"]) is False
    assert not route.failed and _hides(core) == []
    composite.pixels = (1920, 1080)
    route_world.window.afterSynchronizing.emit()
    assert calls == [1] and route.published == 1                                      # no new revision published
    cards = [entry[1][0] for entry in core.log[mark:] if entry[0] == "present_raw"]
    assert cards and cards[-1]["item_from_window"] != first_card["item_from_window"]   # the new window's map
    assert any(entry[0] == "place" for entry in core.log[mark:])


def test_the_cores_failed_build_fades_the_card_out_once_and_back_in_when_it_draws(route_world, caplog):
    # M4: the core's content failed (its first build, a program that does not build): the route reads the item's status
    # at its sync, fades the card out (logged once) and keeps publishing; once the core draws again it fades back in.
    import logging

    from rendering.native.composite import ContentStatus
    from rendering.quick.visualizer.native_route import FAILURE_FADE_MS

    route, core = route_world.make()
    bridge = _Bridge()
    identity = _identity("spectrum")
    presentation = route_world.presentation
    bridge.snapshots = [_snapshot(presentation, 1)]
    assert _sync(route, bridge, identity, presentation) is True
    composite = core.made[0].composite
    composite.status = ContentStatus(draws=0, failures=1, refused_run=0, failing=True)
    with caplog.at_level(logging.ERROR, logger="rendering.quick.visualizer.native_route"):
        for value in (2, 3, 4):
            bridge.snapshots = [_snapshot(presentation, value)]
            assert _sync(route, bridge, identity, presentation) is True             # still published for the core
    assert route.failed and route.published == 4
    assert len([r for r in caplog.records if "build failed" in r.getMessage()]) == 1
    assert len(_hides(core)) == 1 and _hides(core)[0][1]["fade_ms"] == FAILURE_FADE_MS
    composite.status = ContentStatus(draws=1, failures=1, refused_run=0, failing=False)
    bridge.snapshots = [_snapshot(presentation, 5)]
    assert _sync(route, bridge, identity, presentation) is True and not route.failed
    assert _places(core)[-1][2] == {"visible": True, "fade_ms": FAILURE_FADE_MS}


def test_the_cores_verdict_is_read_after_the_frame_renders_with_no_new_frame(route_world):
    # M4 with a paused source: the card is placed, the core's build of it fails at the next frame, and nothing new is
    # published. The window's afterRendering (armed when the route sent the core something to build) re-runs the
    # update, which reads the failure and fades the card out.
    from rendering.native.composite import ContentStatus

    route, core = route_world.make()
    bridge = _Bridge()
    identity = _identity("spectrum")
    presentation = route_world.presentation
    calls = _wired(route, bridge, identity, lambda: presentation)
    bridge.snapshots = [_snapshot(presentation, 1)]
    assert _sync(route, bridge, identity, presentation) is True
    signal = route_world.window.afterRendering
    assert len(signal.slots) == 1
    core.made[0].composite.status = ContentStatus(draws=0, failures=1, refused_run=0, failing=True)
    signal.emit()
    assert calls == [1] and route.failed and len(_hides(core)) == 1 and signal.slots == []
    # Control: an update at rest with no edge fired reads nothing and sends nothing.
    before = list(core.log)
    healthy, healthy_core = route_world.make()
    bridge.snapshots = [_snapshot(presentation, 2)]
    assert _sync(healthy, bridge, identity, presentation) is True
    mark = len(healthy_core.log)
    assert _sync(healthy, bridge, identity, presentation) is False and healthy_core.log[mark:] == []
    assert core.log == before


def test_a_lasting_run_of_refused_frames_fades_the_card_out(route_world):
    # M5: a frame the core refuses keeps the last drawn one; a run of them past REFUSED_RUN_FADE (a value that stays
    # non-finite) fades the card out instead of freezing it, and the next drawn frame fades it back in.
    from rendering.native.composite import ContentStatus
    from rendering.quick.visualizer import native_route
    from rendering.quick.visualizer.native_route import FAILURE_FADE_MS

    REFUSED_RUN_FADE = getattr(native_route, "REFUSED_RUN_FADE", 30)   # (the pre-fix route, the control, has none)

    route, core = route_world.make()
    bridge = _Bridge()
    identity = _identity("spectrum")
    presentation = route_world.presentation
    bridge.snapshots = [_snapshot(presentation, 1)]
    assert _sync(route, bridge, identity, presentation) is True
    composite = core.made[0].composite
    composite.status = ContentStatus(draws=1, failures=0, refused_run=REFUSED_RUN_FADE - 1, failing=False)
    bridge.snapshots = [_snapshot(presentation, 2)]
    assert _sync(route, bridge, identity, presentation) is True and not route.failed and _hides(core) == []
    composite.status = ContentStatus(draws=1, failures=0, refused_run=REFUSED_RUN_FADE, failing=False)
    bridge.snapshots = [_snapshot(presentation, 3)]
    assert _sync(route, bridge, identity, presentation) is True and route.failed
    assert len(_hides(core)) == 1 and _hides(core)[0][1]["fade_ms"] == FAILURE_FADE_MS
    composite.status = ContentStatus(draws=2, failures=0, refused_run=0, failing=False)
    bridge.snapshots = [_snapshot(presentation, 4)]
    assert _sync(route, bridge, identity, presentation) is True and not route.failed
    assert _places(core)[-1][2] == {"visible": True, "fade_ms": FAILURE_FADE_MS}


def test_an_unbind_fades_the_card_out_even_when_the_native_unbind_raises(route_world):
    # L3: the fade is its own step, before the stream retires (the core keeps the last frame for it); a raising native
    # unbind still leaves the card fading out, never shown with its last frame.
    from rendering.quick.visualizer.native_route import FAILURE_FADE_MS

    route, core = route_world.make(fail_unbind=1)
    bridge = _Bridge()
    bridge.snapshots = [_snapshot(route_world.presentation, 1)]
    assert _sync(route, bridge, _identity("spectrum"), route_world.presentation) is True
    route.sync(bridge=bridge, identity=None, presentation=route_world.presentation, authority=True)
    hides = [index for index, entry in enumerate(core.log) if entry[0] == "set" and entry[1].get("visible") is False]
    unbinds = [index for index, entry in enumerate(core.log) if entry[0] == "unbind"]
    assert hides and unbinds and hides[0] < unbinds[0]
    assert core.log[hides[0]][1]["fade_ms"] == FAILURE_FADE_MS


def test_a_card_hidden_with_its_presentation_returns_without_a_second_fade(route_world):
    # L5: the owner hid the Visualizer (no presentation) and fades it back in itself; the native item's return adds no
    # fade of its own on top (before, it faded twice).
    route, core = route_world.make()
    bridge = _Bridge()
    identity = _identity("spectrum")
    presentation = route_world.presentation
    bridge.snapshots = [_snapshot(presentation, 1)]
    assert _sync(route, bridge, identity, presentation) is True
    assert route.sync(bridge=bridge, identity=identity, presentation=None, authority=True) is False
    assert len(_hides(core)) == 1
    bridge.snapshots = [_snapshot(presentation, 2)]
    assert _sync(route, bridge, identity, presentation) is True
    assert [entry[2] for entry in _places(core)] == [{"visible": True, "fade_ms": 0}] * 2


@pytest.mark.qt
def test_the_item_hands_the_route_its_update(qt_app):
    from rendering.quick.visualizer.item import VisualizerRenderItem

    handed: list = []
    route = _RecordingRoute()
    route.set_update_request = handed.append
    item = VisualizerRenderItem()
    item.attach_native_route(route)
    assert handed == [item.update]


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
