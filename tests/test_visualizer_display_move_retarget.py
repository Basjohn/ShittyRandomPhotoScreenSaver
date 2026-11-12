"""A Visualizer display move retargets the live owner; it never rebuilds the runtime (Current_Plan 1C.2).

Operator, 11 Nov: "we do not want teardowns and rebuilds unless absolutely needed. They are a last resort." Before
1C.2 every full-display glyph move rebuilt the whole runtime generation: the chrome-less move bound no scene to its
CUSTOM session, so its own Save refused the live promotion and requested ``save_corrupt_retained_runtime``.

The rig is the real ``QuickDisplayVisualizerOwner`` (Spectrum, an in-process replay engine, a test clock), the real
``QuickCustomLayoutOwner`` and the real takeover coordinator, across two real Quick display units that are never
shown. Each unit's screen is a stand-in so the two have distinct identities side by side; their sizes are test-owned.
Publications are driven at the owner's own edge (a logical tick, then ``sync_present``), never by a timer.
"""
from __future__ import annotations

from dataclasses import replace as _replace
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect

from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
from tests.test_qtquick_custom_layout_owner import (
    _LiveCommitEngine, _Settings, _clock_unit, _clock_widgets, _configure_visualizer,
)
from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer.expanded_display_coordinator import (
    ExpandedDisplayCoordinator, ExpandedDisplayServices, display_key,
)
from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

SHADOW = {"background_color": (0, 0, 0, 0), "border_color": (255, 255, 255, 255), "border_width": 4.,
          "corner_radius": 6., "content_inset": 14., "shadow_enabled": False, "shadow_color": (0, 0, 0, 0),
          "shadow_blur": 0., "shadow_offset": (0., 0.), "shadow_spread": 0., "shadow_extensions": (0., 0., 0., 0.)}


def _screen(name, rect):
    return SimpleNamespace(geometry=lambda r=QRect(rect): QRect(r), name=lambda: name, serialNumber=lambda: name,
                           manufacturer=lambda: "", model=lambda: "", devicePixelRatio=lambda: 1.0)


class _Window:
    def __init__(self, real, screen):
        self._real, self._screen = real, screen

    def screen(self):
        return self._screen

    def __getattr__(self, name):
        return getattr(self._real, name)


class _Runtime:
    """The real runtime, seen through a stand-in screen (its identity and geometry on the virtual desktop)."""

    def __init__(self, real, screen, rect):
        self._real = real
        self.window = _Window(real.window, screen)
        self.display_identity = _replace(real.display_identity, screen_key=screen.name(),
                                         geometry=(rect.x(), rect.y(), rect.width(), rect.height()))

    def __getattr__(self, name):
        return getattr(self._real, name)


class _Unit:
    def __init__(self, real, screen, rect):
        self._real = real
        self.runtime = _Runtime(real.runtime, screen, rect)

    def __getattr__(self, name):
        return getattr(self._real, name)


class _Rig:
    def __init__(self, qt_app, target_rect: QRect):
        widgets = _clock_widgets()
        widgets["clock"]["enabled"] = False
        widgets["spotify_visualizer"] = {"enabled": True, "mode": "spectrum", "monitor": "1"}
        self.qt_app = qt_app
        real0, self.factory = _clock_unit(qt_app, widgets, generation=1202, screen_index=0)
        real1, _ = _clock_unit(qt_app, widgets, generation=1202, screen_index=1, factory=self.factory)
        self.reals = (real0, real1)
        rects = (QRect(0, 0, 1280, 720), QRect(target_rect))
        self.units = tuple(_Unit(real, _screen(f"retarget-{index}", rect), rect)
                           for index, (real, rect) in enumerate(zip(self.reals, rects)))
        self.clock = [0.0]
        self.owner = QuickDisplayVisualizerOwner(
            self.units[0].runtime, initial_mode="spectrum", bar_count=24,
            engine_factory=lambda _count: _LiveCommitEngine(), card_shadow_kwargs=SHADOW,
            transition_clock=lambda: self.clock[0])
        self.units[0].attach_visualizer_owner(self.owner)
        self.current = {"unit": self.units[0]}
        self.reloads: list[str] = []
        self.settings = _Settings(widgets)
        self.layout = QuickCustomLayoutOwner(
            settings_manager=self.settings, participants_provider=lambda: self.units,
            visualizer_provider=lambda: (self.owner, self.current["unit"]), reload_request=self.reloads.append,
            visualizer_unit_transfer=self._transfer, live_config_commit=lambda _widgets: None)
        _configure_visualizer(self.owner, playing=True)
        self.owner.set_authored_outer_origin(100., 100.)
        self.owner.bind(engine_generation=3, activation_id=5)
        self.owner._apply_resolved_presentation(self.owner._resolve_current_presentation())
        self.owner.start(interval_s=10.)
        state = self.owner.controller.logical_tick_state
        state._mode_teardown_block_until_ready = False
        state._mode_transition_ready = True
        state._waiting_for_fresh_engine_frame = False
        state._display_bars_source_generation = 3
        state._display_bars_source_activation = 5

    refuse_transfer = False

    def _transfer(self, target) -> bool:
        """``VisualizerHostBinding.transfer``'s owner edge (``refuse_transfer``: the host binding refuses)."""
        if self.refuse_transfer:
            return False
        source = self.current["unit"]
        self.owner.set_presentation_runtime(target.runtime)
        source.detach_visualizer_owner(self.owner)
        target.attach_visualizer_owner(self.owner)
        self.current["unit"] = target
        return True

    def publish(self, seconds: float = 1.0 / 60.0) -> bool:
        """One publication at the owner's edge, the test clock ``seconds`` later."""
        self.clock[0] += seconds
        assert tick_pipeline.logical_tick(self.owner.controller.logical_tick_state) is not None
        return self.owner.sync_present()

    def identity(self) -> dict:
        controller = self.owner.controller
        return {"owner": id(self.owner), "controller": id(controller),
                "logical_runtime": id(controller.logical_runtime), "engine": id(controller.engine),
                "render_identity": self.owner.render_identity}

    def revision(self) -> int:
        return int(self.owner.controller.render_bridge._last_revision)

    def close(self) -> None:
        self.layout.retire()
        for real in self.reals:
            real.retire()
        self.factory.deleteLater()
        self.qt_app.processEvents()


@pytest.fixture
def quiet_ticks(monkeypatch):
    monkeypatch.setattr(tick_pipeline, "consume_engine_bars", lambda _o, _n: (True, True))
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda _o, _n: None)


@pytest.mark.parametrize("target_rect", [QRect(1280, 0, 1280, 720), QRect(1280, 0, 1920, 1080)],
                         ids=["same-size", "larger"])
def test_the_glyph_move_keeps_the_live_owner_both_ways_and_rebuilds_nothing(qt_app, quiet_ticks, target_rect):
    """Negative control (checked 12 Nov on the pre-fix move): every move requested ``save_corrupt_retained_runtime``
    and the target kept the source's rect."""
    rig = _Rig(qt_app, target_rect)
    try:
        assert rig.publish(2.0)                 # past the first-appearance fade: the card is fully shown
        before, revision = rig.identity(), rig.revision()
        assert rig.layout.move_visualizer_to_display(rig.units[1]) is True
        assert rig.reloads == [] and rig.current["unit"] is rig.units[1]
        assert rig.identity() == before
        assert rig.owner.presentation_runtime is rig.units[1].runtime
        assert rig.settings.widgets["spotify_visualizer"]["monitor"] == "2"
        # The target shows the rect the move projected (relative position, same shape), not the source's.
        projected = rig.units[1].runtime.scene_controller.visualizer_item.presentation.outer_rect
        assert projected[2:] == (420.0, 280.0)
        expected_x = round((100 + 210) / 1280 * target_rect.width() - 210)
        assert abs(projected[0] - expected_x) <= 1.0
        assert rig.publish() and rig.revision() > revision
        # And back.
        revision = rig.revision()
        assert rig.layout.move_visualizer_to_display(rig.units[0]) is True
        assert rig.reloads == [] and rig.current["unit"] is rig.units[0] and rig.identity() == before
        assert rig.publish() and rig.revision() > revision
    finally:
        rig.close()


def test_the_display_move_is_edits_hop_and_save_without_edit_chrome(qt_app, quiet_ticks):
    """Plan 1B.12 on the real owner and its real live commit (formerly a stubbed commit in
    ``test_qtquick_custom_layout_owner``, which hid the refusal): the move is Edit's hop + Save (the scene
    coordinator's retained transfer, the commit, the live promotion) with the scenes bound only as a direct gesture
    binds them, never Edit's chrome. Negative control: on the pre-fix move this Save requested a runtime reload."""
    rig = _Rig(qt_app, QRect(1280, 0, 1280, 720))
    try:
        assert rig.publish(2.0)
        bound: list[str] = []
        for unit in rig.units:
            scene = unit.runtime.scene_controller
            for name in ("bind_custom_layout_session", "bind_direct_custom_layout_session"):
                method = getattr(scene, name)

                def spy(*args, _method=method, _name=name, **kwargs):
                    bound.append(_name)
                    return _method(*args, **kwargs)
                setattr(scene, name, spy)
        assert rig.layout.move_visualizer_to_display(rig.units[1]) is True
        assert rig.current["unit"] is rig.units[1] and rig.reloads == []
        assert bound == ["bind_direct_custom_layout_session"] * 2           # no Edit chrome anywhere
        assert not rig.layout.is_active and not rig.layout.is_editing
        assert all(unit.runtime.scene_controller._custom_layout_session is None for unit in rig.units)
        assert rig.settings.widgets["spotify_visualizer"]["monitor"] == "2"  # committed where Edit's Save commits it
        local = rig.units[1].runtime.scene_controller.visualizer_item.presentation.outer_rect
        assert 0.0 <= local[0] and local[0] + local[2] <= 1280.0            # on the target display, inside it
        # Already there, or another session open: refused, nothing changes.
        assert rig.layout.move_visualizer_to_display(rig.units[1]) is False
        assert rig.layout.start() is True
        assert rig.layout.move_visualizer_to_display(rig.units[0]) is False
        assert rig.current["unit"] is rig.units[1]
        rig.layout.cancel()
    finally:
        rig.close()


def test_a_refused_display_move_leaves_the_source_exactly_and_writes_nothing(qt_app, quiet_ticks):
    from copy import deepcopy

    rig = _Rig(qt_app, QRect(1280, 0, 1280, 720))
    try:
        assert rig.publish(2.0)
        before = deepcopy(rig.settings.widgets)
        identity = rig.identity()
        rig.refuse_transfer = True
        assert rig.layout.move_visualizer_to_display(rig.units[1]) is False
        assert rig.current["unit"] is rig.units[0] and rig.identity() == identity
        source_item = rig.units[0].runtime.scene_controller.visualizer_item
        assert source_item.render_identity == identity["render_identity"]   # the retained scene came back
        assert rig.settings.widgets == before and rig.reloads == []
        assert not rig.layout.is_active
    finally:
        rig.close()


def test_a_move_whose_save_ends_in_a_runtime_reload_is_not_a_move(qt_app, quiet_ticks, monkeypatch):
    """A Save that asks for a runtime reload rebuilds; it does not move. Negative control (pre-fix): True."""
    from rendering.quick.lifecycle_errors import RetainedRuntimeIncoherenceError

    rig = _Rig(qt_app, QRect(1280, 0, 1280, 720))
    try:
        assert rig.publish(2.0)                 # past the first-appearance fade: the card is fully shown

        def refuse(**_kwargs):
            raise RetainedRuntimeIncoherenceError("a classified retained-runtime defect (test-owned)")
        monkeypatch.setattr(rig.owner, "commit_live_custom_layout", refuse)
        assert rig.layout.move_visualizer_to_display(rig.units[1]) is False
        assert rig.reloads == ["save_corrupt_retained_runtime"]
    finally:
        rig.close()


@pytest.fixture
def worker_run(monkeypatch):
    """The engine worker's own rules for a test (as ``test_visualizer_owner_engine_worker``): no device, a fresh run."""
    from core.visualizer_engine.engine_worker import EngineSession
    from widgets.spotify_visualizer import engine_worker_link

    def _device(_config=None):
        raise AssertionError("a test opened an audio device")

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", _device)
    monkeypatch.setattr(EngineSession, "LIVE_EDGE_TIMEOUT_S", 10.0)
    engine_worker_link.reset_run_state_for_testing()
    yield
    engine_worker_link.reset_run_state_for_testing()


@pytest.mark.qt
def test_on_the_engine_worker_a_move_keeps_the_session_both_ways(qt_app, worker_run):
    """The product's default path: the owner on the engine worker (an in-process stand-in for the supervisor, so the
    order is deterministic). A display move in each direction, through the owner's own fade-through and the retained
    scene transfer, keeps the worker link, its session mapping, the owner, its controller and render identity, and
    the session keeps publishing with rising revisions. (The pre-1C.2 owner had no such move: the glyph's move ended
    in a runtime reload, a new owner on a new session; the in-process tests above prove that reload is gone.)"""
    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor, _pump
    from tools.visualizer_replay import owner_worker_gate as gate
    from tools.visualizer_replay.live_engine_gate import paced_pcm
    from widgets.spotify_visualizer import engine_worker_link

    pcm = paced_pcm(3.0)
    stand_in = _InProcessSupervisor()
    clock = [0.0]
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=stand_in, cadence="thread", clock=clock)
    runtimes: list = []
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
            home = owner.presentation_runtime
            factory = QuickSceneFactory()
            away = QuickDisplayRuntime(screen_index=1, runtime_generation=gate.GENERATION, screen=qt_app.primaryScreen(),
                                       scene_factory=factory,
                                       window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False))
            runtimes.append((away, factory))
            link = owner._worker
            assert link is not None
            before = (id(owner), id(owner.controller), owner.render_identity, link, link.mapping_name)

            def run(target):
                done: list = []

                def hop() -> bool:
                    owner.presentation_runtime.scene_controller.transfer_visualizer_to(target.scene_controller)
                    return owner.set_presentation_runtime(target)
                assert owner.move_display(target, end_expanded=False, hop=hop, on_complete=done.append)
                for step in range(400):
                    clock[0] += 0.02
                    _pump(rig, 0.02)
                    if done:
                        break
                assert done == [True] and owner.presentation_runtime is target

            for target in (away, home):
                revision = int(owner.controller.render_bridge._last_revision)
                run(target)
                assert (id(owner), id(owner.controller), owner.render_identity, owner._worker,
                        owner._worker.mapping_name) == before
                for _ in range(10):
                    clock[0] += 0.02
                    _pump(rig, 0.02)
                assert int(owner.controller.render_bridge._last_revision) > revision
    finally:
        rig.close()
        for runtime, factory in runtimes:
            runtime.close_runtime()
            factory.deleteLater()
        stand_in.close()


def _coordinator(rig: _Rig, covers: list, writes: list) -> ExpandedDisplayCoordinator:
    requested = {"value": False}

    def persist(value: bool) -> None:
        requested["value"] = bool(value)
        writes.append(bool(value))

    coordinator = ExpandedDisplayCoordinator(ExpandedDisplayServices(
        admitted_owner=lambda: rig.owner, admitted_unit=lambda: rig.current["unit"],
        requested=lambda: requested["value"], persist_requested=persist,
        mode_capable=lambda _mode: True, edit_active=lambda: rig.layout.is_active,
        publish_glyph=lambda _unit, _available, _expanded: None,
        cover_widgets=lambda unit, covered, fade_s: covers.append((display_key(unit), bool(covered))),
        move_to_display=lambda key: rig.layout.move_visualizer_to_display(
            next(unit for unit in rig.units if display_key(unit) == key)),
        display_unit=lambda key: next((unit for unit in rig.units if display_key(unit) == key), None)))
    coordinator.generation_ready()
    return coordinator


def _record_commits(rig: _Rig) -> list:
    """Every record each display's scene is given: (display index, scene_fade, display-wide?)."""
    seen: list = []
    for index, unit in enumerate(rig.units):
        scene = unit.runtime.scene_controller
        apply = scene.apply_visualizer_presentation

        def recording(presentation, *, active=True, _apply=apply, _index=index):
            seen.append((_index, round(float(presentation.scene_fade), 4),
                         presentation.outer_rect[2] > 1000.0))
            return _apply(presentation, active=active)
        scene.apply_visualizer_presentation = recording
    return seen


@pytest.mark.parametrize("start_expanded", [False, True], ids=["from-ordinary", "from-expanded"])
def test_a_diagonal_is_one_fade_through_that_ends_expanded_on_the_target(qt_app, quiet_ticks, start_expanded):
    """The move is one fade-through across the displays: out where it is, the move at zero opacity, in display-wide
    on the target. The ordinary card is never shown on either display in between, nothing is rebuilt, and a move
    from an ordinary card ends expanded with the intent persisted (it used to end ordinary: the reload the move
    requested replaced the generation before the enter could commit)."""
    from core.expanded_visualizer_takeover import Phase

    rig = _Rig(qt_app, QRect(1280, 0, 1920, 1080))
    covers: list = []
    writes: list = []
    try:
        assert rig.publish(2.0)                 # past the first-appearance fade: the card is fully shown
        coordinator = _coordinator(rig, covers, writes)
        source, target = rig.units
        if start_expanded:
            assert coordinator.glyph_pressed(source, True)
            for _ in range(240):
                rig.publish()
                if coordinator.phase is Phase.EXPANDED:
                    break
            assert coordinator.phase is Phase.EXPANDED and writes == [True]
        before = rig.identity()
        commits = _record_commits(rig)
        assert coordinator.expand_on_display(source, target)
        assert coordinator.phase is Phase.TRANSFER_PENDING
        for _ in range(600):
            rig.publish()
            if coordinator.phase is not Phase.TRANSFER_PENDING:
                break
        assert coordinator.phase is Phase.EXPANDED, coordinator.phase
        assert rig.reloads == [] and rig.identity() == before and rig.current["unit"] is target
        assert rig.owner.expanded_display and writes == [True]
        # The source: only fading out (display-wide when it started so), then once at zero on its ordinary card
        # (the record the move commits), never visible again.
        on_source = [(fade, wide) for index, fade, wide in commits if index == 0]
        on_target = [(fade, wide) for index, fade, wide in commits if index == 1]
        visible_source = [fade for fade, _wide in on_source if fade > 0.0]
        assert visible_source == sorted(visible_source, reverse=True)
        assert all(wide is start_expanded for fade, wide in on_source if fade > 0.0)
        # The target: from zero up to full, display-wide whenever anything of it shows.
        visible_target = [fade for fade, wide in on_target if fade > 0.0]
        assert visible_target and visible_target == sorted(visible_target) and visible_target[-1] == 1.0
        assert all(wide for fade, wide in on_target if fade > 0.0)
        # Widgets: the source's come back (if they were covered) and the target's leave with the arrival.
        assert covers[-1] == (display_key(target), True)
    finally:
        rig.close()
