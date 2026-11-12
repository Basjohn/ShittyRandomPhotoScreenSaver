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

    def _transfer(self, target) -> bool:
        """``VisualizerHostBinding.transfer``'s owner edge."""
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
        assert rig.publish()
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


def test_a_move_whose_save_ends_in_a_runtime_reload_is_not_a_move(qt_app, quiet_ticks, monkeypatch):
    """A Save that asks for a runtime reload rebuilds; it does not move. Negative control (pre-fix): True."""
    from rendering.quick.custom_layout_contract import RetainedRuntimeIncoherenceError

    rig = _Rig(qt_app, QRect(1280, 0, 1280, 720))
    try:
        assert rig.publish()

        def refuse(**_kwargs):
            raise RetainedRuntimeIncoherenceError("a classified retained-runtime defect (test-owned)")
        monkeypatch.setattr(rig.owner, "commit_live_custom_layout", refuse)
        assert rig.layout.move_visualizer_to_display(rig.units[1]) is False
        assert rig.reloads == ["save_corrupt_retained_runtime"]
    finally:
        rig.close()


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
        assert rig.publish()
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
