"""Expanded Visualizer M2: the takeover coordinator beside the host binding (plan 01 §0.3, §D, §0.5).

The coordinator feeds events to the pure reducer and performs its actions through the owner's display-wide route,
one narrow intent write, the canonical mode path and the glyph. These bars drive it with a recording stand-in owner
(the route's own behaviour is covered with the production owner in ``test_visualizer_expansion_geometry.py``) and
check the operator's rule end to end: full display is only ever the user's request, so a mode switch never
re-expands (7 Nov). The display manager's lazy wiring is checked at the end: an incapable Visualizer without a saved
intent creates no coordinator.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.expanded_visualizer_takeover import Phase
from widgets.spotify_visualizer.expanded_display_coordinator import (
    ExpandedDisplayCoordinator,
    ExpandedDisplayServices,
    display_key,
)

def _registry_capability() -> tuple[frozenset[str], tuple[str, ...]]:
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors

    descriptors = tuple(iter_all_visualizer_mode_descriptors())
    return (frozenset(d.mode_id for d in descriptors if d.supports_expanded_display),
            tuple(d.mode_id for d in descriptors if not d.supports_expanded_display))


#: Membership is the registry's capability flag; the labels below are just members of each side.
CAPABLE_SET, _INCAPABLE = _registry_capability()
CAPABLE = "extruded_bubble"
CAPABLE_2D = sorted(CAPABLE_SET - {CAPABLE})[0]
INCAPABLE, INCAPABLE_2 = _INCAPABLE[0], _INCAPABLE[-1]
assert CAPABLE in CAPABLE_SET and len(_INCAPABLE) >= 2


class _Engine:
    def __init__(self) -> None:
        self.activation = 1

    def get_activation_id(self) -> int:
        return self.activation


HALF = 0.25   # the stand-in owner's fade half (the production owner reports its own)


class _Owner:
    """Records route calls; an animated change completes when the test says so (the publication edge)."""

    expanded_display_fade_half_s = HALF

    def __init__(self, mode: str) -> None:
        self.controller = SimpleNamespace(mode_id=mode, engine=_Engine())
        self.is_retired = False
        self.expanded_display = False
        self.calls: list[tuple[bool, bool]] = []
        self.pending = None

    @property
    def expanded_display_transition_active(self) -> bool:
        return self.pending is not None

    def set_expanded_display(self, expanded, *, animate=False, on_complete=None):
        if self.is_retired:
            return False
        self.calls.append((bool(expanded), bool(animate)))
        self.pending = None
        if animate:
            self.pending = (bool(expanded), on_complete)
        else:
            self.expanded_display = bool(expanded)
            if on_complete is not None:
                on_complete()
        return True

    def finish(self) -> None:
        expanded, on_complete = self.pending
        self.pending = None
        self.expanded_display = expanded
        if on_complete is not None:
            on_complete()

    def activate(self, mode: str) -> None:
        self.controller.mode_id = mode
        self.controller.engine.activation += 1


def _unit(index: int = 0, key: str = "lg-tv"):
    identity = SimpleNamespace(screen_key=key, geometry=(0, 0, 2560, 1440))
    return SimpleNamespace(screen_index=index, is_retired=False, runtime=SimpleNamespace(display_identity=identity))


class _Host:
    def __init__(self, mode: str = CAPABLE, *, requested: bool = False) -> None:
        self.owner = _Owner(mode)
        self.unit = _unit()
        self.requested = requested
        self.writes: list[bool] = []
        self.edit = False
        self.glyphs: list[tuple[str, bool, bool]] = []
        self.covers: list[tuple[str, bool, float]] = []
        self.fullscreen_edit_ends = 0
        self.coordinator = ExpandedDisplayCoordinator(ExpandedDisplayServices(
            admitted_owner=lambda: self.owner,
            admitted_unit=lambda: self.unit,
            requested=lambda: self.requested,
            persist_requested=self._persist,
            mode_capable=lambda mode: mode in CAPABLE_SET,
            edit_active=lambda: self.edit,
            publish_glyph=lambda unit, available, expanded: self.glyphs.append(
                (display_key(unit), bool(available), bool(expanded))),
            cover_widgets=lambda unit, covered, fade_s: self.covers.append(
                (display_key(unit), bool(covered), float(fade_s))),
            end_fullscreen_edit=self._end_fullscreen_edit,
        ))

    def _end_fullscreen_edit(self) -> None:
        self.fullscreen_edit_ends += 1
        self.edit = False
        self.coordinator.edit_exited(saved=False)

    def _persist(self, value: bool) -> None:
        self.requested = bool(value)
        self.writes.append(bool(value))

    @property
    def glyph(self) -> tuple[bool, bool]:
        return self.glyphs[-1][1:]

    def press(self, expand: bool, unit=None) -> bool:
        return self.coordinator.glyph_pressed(unit or self.unit, expand)

    def request_mode(self, mode: str, *, accept: bool = True) -> tuple[bool, list[str]]:
        forwarded: list[str] = []

        def forward() -> bool:
            forwarded.append(mode)
            return accept
        return self.coordinator.mode_requested(mode, forward), forwarded

    def request_cycle(self, order: tuple[str, ...]) -> tuple[bool, list[str]]:
        requested: list[str] = []

        def request(mode: str) -> bool:
            requested.append(mode)
            return True
        return self.coordinator.mode_cycle_requested(order, request), requested

    def complete_mode(self, mode: str) -> None:
        self.owner.activate(mode)
        self.coordinator.mode_activated()


def _expanded_by_user() -> _Host:
    host = _Host()
    host.coordinator.generation_ready()
    assert host.press(True)
    host.owner.finish()
    assert host.coordinator.phase is Phase.EXPANDED and host.writes == [True]
    return host


def test_readiness_restores_a_saved_intent_before_reveal_without_writing_it():
    host = _Host(requested=True)
    host.coordinator.generation_ready()
    assert host.owner.calls == [(True, False)]               # unanimated: no ordinary-card flash, no double fade
    assert host.coordinator.phase is Phase.EXPANDED and host.writes == []
    assert host.glyph == (True, True)                        # the glyph offers the collapse


def test_readiness_on_an_incapable_mode_clears_a_saved_intent():
    host = _Host(INCAPABLE, requested=True)
    host.coordinator.generation_ready()
    assert host.writes == [False] and host.owner.calls == []
    assert host.glyph == (False, False)


def test_the_users_expand_persists_only_when_it_commits_and_collapse_writes_off_at_once():
    host = _Host()
    host.coordinator.generation_ready()
    assert host.glyph == (True, False)
    assert host.press(True)
    assert host.owner.calls == [(True, True)] and host.writes == []    # the fade is running: nothing persisted
    host.owner.finish()
    assert host.writes == [True] and host.glyph == (True, True)
    assert host.press(False)
    assert host.writes == [True, False] and host.owner.calls[-1] == (False, True)
    host.owner.finish()
    assert host.coordinator.phase is Phase.ORDINARY and host.glyph == (True, False)


def test_a_mode_switch_never_re_expands_operator_7_nov():
    """Expanded EB -> an incapable mode -> back to a capable mode: the second capable activation starts ordinary."""
    host = _expanded_by_user()
    accepted, forwarded = host.request_mode(INCAPABLE)
    assert accepted and forwarded == []                       # held until the collapse commits
    assert host.owner.calls[-1] == (False, True)
    host.owner.finish()
    assert forwarded == [INCAPABLE]                           # then the canonical request
    host.complete_mode(INCAPABLE)
    assert host.writes == [True, False]                       # the incapable mode cleared the intent
    assert host.glyph == (False, False)
    calls = len(host.owner.calls)
    accepted, forwarded = host.request_mode(CAPABLE)
    assert accepted and forwarded == [CAPABLE]
    host.complete_mode(CAPABLE)
    assert host.coordinator.phase is Phase.ORDINARY
    assert len(host.owner.calls) == calls                     # nothing re-expanded
    assert host.glyph == (True, False)


def test_a_rejected_incapable_target_re_expands_the_unchanged_capable_mode():
    host = _expanded_by_user()
    accepted, forwarded = host.request_mode(INCAPABLE, accept=False)
    assert accepted
    host.owner.finish()                                       # collapse committed -> forward -> refused
    assert forwarded == [INCAPABLE]
    assert host.owner.calls[-1] == (True, True)               # rollback: re-expand the capable mode
    host.owner.finish()
    assert host.coordinator.phase is Phase.EXPANDED and host.writes == [True]


def test_capable_to_capable_keeps_the_takeover():
    host = _expanded_by_user()
    accepted, forwarded = host.request_mode(CAPABLE)          # the same capable mode family, e.g. a preset path
    assert accepted and forwarded == [CAPABLE]
    host.complete_mode(CAPABLE)
    assert host.coordinator.phase is Phase.EXPANDED and host.owner.expanded_display


@pytest.mark.parametrize("order,target", [
    ((INCAPABLE, INCAPABLE_2, CAPABLE_2D, CAPABLE), CAPABLE_2D),       # skips the incapable ones
    ((INCAPABLE_2, CAPABLE), CAPABLE),                                 # wraps round: an earlier capable mode
])
def test_a_double_click_while_expanded_goes_to_the_next_capable_mode_and_stays_expanded(order, target):
    host = _expanded_by_user()
    accepted, requested = host.request_cycle(order)
    assert accepted and requested == [target]
    calls = len(host.owner.calls)
    host.complete_mode(target)
    assert host.coordinator.phase is Phase.EXPANDED and len(host.owner.calls) == calls   # never collapsed
    assert host.writes == [True]


def test_a_double_click_while_expanded_with_no_other_capable_mode_stays_put():
    host = _expanded_by_user()
    accepted, requested = host.request_cycle((INCAPABLE, INCAPABLE_2))
    assert not accepted and requested == []
    assert host.coordinator.phase is Phase.EXPANDED and host.owner.expanded_display


def test_an_explicit_incapable_selection_while_expanded_still_collapses():
    host = _expanded_by_user()
    accepted, forwarded = host.request_mode(INCAPABLE)                 # Settings / context menu
    assert accepted and forwarded == [] and host.owner.calls[-1] == (False, True)


def test_a_double_click_on_an_ordinary_card_takes_the_next_enabled_mode():
    host = _Host()
    host.coordinator.generation_ready()
    accepted, requested = host.request_cycle((INCAPABLE, CAPABLE_2D))
    assert accepted and requested == [INCAPABLE]


def test_a_mode_request_during_a_transition_is_refused_without_change():
    host = _Host()
    host.coordinator.generation_ready()
    host.press(True)                                          # entering
    accepted, forwarded = host.request_mode(INCAPABLE)
    assert not accepted and forwarded == []


def test_edit_on_an_expanded_view_is_fullscreen_edit_without_a_collapse_transaction():
    """M3c (operator, 8 Nov; supersedes "entering Edit collapses"): Edit on the expanded view keeps it expanded."""
    host = _expanded_by_user()
    calls, covers = list(host.owner.calls), list(host.covers)
    host.edit = True
    host.coordinator.edit_entered()
    assert host.owner.calls == calls                          # no collapse transaction reached the owner
    assert host.covers == covers                              # the ordinary widgets stay covered
    assert host.coordinator.phase is Phase.EXPANDED and host.coordinator.fullscreen_edit
    assert host.glyph == (False, True)                        # the glyph is withdrawn under Edit, as in every Edit
    # A stale collapse press goes through the session's resolution, which keeps the draft and Edit.
    assert not host.press(False)
    assert host.owner.calls == calls and host.writes == [True] and host.coordinator.fullscreen_edit
    host.edit = False
    host.coordinator.edit_exited(saved=True)
    assert host.owner.calls == calls and host.writes == [True]
    assert host.coordinator.phase is Phase.EXPANDED and not host.coordinator.fullscreen_edit
    assert host.glyph == (True, True)


def test_an_ordinary_edit_begun_while_entering_collapses_at_once_at_the_commit_and_restores_after():
    host = _Host()
    host.coordinator.generation_ready()
    assert host.press(True)                                   # entering (the fade runs)
    host.edit = True
    host.coordinator.edit_entered()
    assert not host.coordinator.fullscreen_edit
    host.owner.finish()                                       # the enter commits, then collapses for Edit at once
    assert host.owner.calls[-1] == (False, False) and host.coordinator.phase is Phase.ORDINARY
    host.edit = False
    host.coordinator.edit_exited(saved=True)
    assert host.owner.calls[-1] == (True, True)
    host.owner.finish()
    assert host.coordinator.phase is Phase.EXPANDED and host.writes == [True]


def test_an_incapable_activation_under_fullscreen_edit_ends_the_session_first():
    host = _expanded_by_user()
    host.edit = True
    host.coordinator.edit_entered()
    host.complete_mode(INCAPABLE)                             # unreachable by request; the reducer stays total
    assert host.fullscreen_edit_ends == 1 and not host.coordinator.fullscreen_edit
    assert host.owner.calls[-1] == (False, True)


def test_an_incapable_request_under_fullscreen_edit_is_refused_without_change():
    host = _expanded_by_user()
    host.edit = True
    host.coordinator.edit_entered()
    calls = list(host.owner.calls)
    accepted, forwarded = host.request_mode(INCAPABLE)
    assert not accepted and forwarded == [] and host.owner.calls == calls
    assert host.coordinator.phase is Phase.EXPANDED and host.coordinator.fullscreen_edit


def test_a_direct_layout_gesture_fails_the_preflight():
    host = _Host()
    host.coordinator.generation_ready()
    host.edit = True                                          # an Alt drag (no Edit event): the preflight refuses
    host.press(True)
    assert host.owner.calls == [] and host.writes == [] and host.coordinator.phase is Phase.ORDINARY


def test_owner_retirement_withdraws_the_glyph_and_fences_late_completions():
    host = _Host()
    host.coordinator.generation_ready()
    host.press(True)
    late = host.owner.pending
    host.coordinator.owner_retired("reload")
    assert host.glyph == (False, False) and host.coordinator.phase is Phase.RETIRING
    late[1]()                                                 # the old owner's completion arrives late
    assert host.writes == [] and host.coordinator.phase is Phase.RETIRING
    assert not host.press(False)
    # The replacement owner re-evaluates once (no intent was ever written).
    host.owner = _Owner(CAPABLE)
    host.coordinator.generation_ready()
    assert host.coordinator.phase is Phase.ORDINARY and host.owner.calls == []


def test_presses_are_fenced_to_the_owning_display_and_follow_a_transfer():
    host = _Host()
    host.coordinator.generation_ready()
    other = _unit(1, "second")
    assert not host.press(True, unit=other) and host.owner.calls == []
    host.unit = other                                         # the CUSTOM transaction moved it (ordinary)
    host.coordinator.display_transferred()
    assert host.glyphs[-2][1:] == (False, False)              # withdrawn from the old display
    assert host.glyphs[-1] == (display_key(other), True, False)
    assert host.press(True, unit=other) and host.owner.calls == [(True, True)]


# ------------------------------------------------------------- M3: the expanded display's ordinary widgets


def test_the_widgets_fade_out_with_the_enter_and_back_in_with_the_collapse():
    """Operator, 7 Nov night: the widgets underneath must really be hidden (a double border showed at the top
    left). They leave as the enter runs (D1.6) with the card's own fade half, and return as the collapse begins
    (D2.2); nothing else covers or uncovers them."""
    host = _Host()
    host.coordinator.generation_ready()
    key = display_key(host.unit)
    assert host.covers == []
    assert host.press(True)
    assert host.covers == [(key, True, HALF)]
    host.owner.finish()
    assert host.covers == [(key, True, HALF)]
    assert host.press(False)
    assert host.covers == [(key, True, HALF), (key, False, HALF)]
    host.owner.finish()
    assert len(host.covers) == 2


def test_a_restore_before_reveal_snaps_the_cover_and_fullscreen_edit_keeps_it():
    host = _Host(requested=True)
    host.coordinator.generation_ready()
    key = display_key(host.unit)
    assert host.covers == [(key, True, 0.0)]                  # never shown before reveal: no fade, no flash
    host.edit = True
    host.coordinator.edit_entered()                           # Fullscreen Edit: the widgets stay covered
    host.edit = False
    host.coordinator.edit_exited(saved=False)
    assert host.covers == [(key, True, 0.0)]


def test_an_ordinary_edits_collapse_snaps_the_cover():
    host = _Host()
    host.coordinator.generation_ready()
    key = display_key(host.unit)
    host.press(True)
    host.edit = True
    host.coordinator.edit_entered()                           # begun while entering: an ordinary Edit
    host.owner.finish()
    assert host.covers[-1] == (key, False, 0.0)               # it edits the ordinary layout at once
    host.edit = False
    host.coordinator.edit_exited(saved=False)
    assert host.covers[-1] == (key, True, HALF)               # the intent re-applies, with the fade


def test_an_incapable_mode_collapse_a_failed_enter_and_a_retirement_bring_the_widgets_back():
    host = _expanded_by_user()
    key = display_key(host.unit)
    host.request_mode(INCAPABLE)
    assert host.covers[-1] == (key, False, HALF)

    refused = _Host()
    refused.coordinator.generation_ready()
    refused.owner.set_expanded_display = lambda *args, **kwargs: False    # the owner cannot draw it
    refused.press(True)
    assert refused.covers == [(key, True, HALF), (key, False, HALF)]
    assert refused.coordinator.phase is Phase.ORDINARY

    retired = _expanded_by_user()
    retired.owner = None                                      # the admission ended (reload, Visualizer off)
    retired.coordinator.owner_retired("reload")
    assert retired.covers[-1] == (key, False, HALF)           # with the fade the owner had
    retired.coordinator.retire()
    assert retired.covers[-1] == (key, False, HALF) and len(retired.covers) == 2


def test_twenty_cycles_balance_the_cover_on_the_owning_display_only():
    host = _Host()
    host.coordinator.generation_ready()
    key = display_key(host.unit)
    for _ in range(20):
        assert host.press(True)
        host.owner.finish()
        assert host.press(False)
        host.owner.finish()
    assert host.covers == [(key, True, HALF), (key, False, HALF)] * 20
    assert host.writes == [True, False] * 20 and host.coordinator.phase is Phase.ORDINARY


def test_after_retire_nothing_is_called():
    host = _expanded_by_user()
    host.coordinator.retire()
    calls, writes = list(host.owner.calls), list(host.writes)
    host.coordinator.generation_ready()
    host.press(False)
    host.coordinator.mode_activated()
    assert host.owner.calls[: len(calls)] == calls and host.writes == writes


# ----------------------------------------------------------------------------- display manager: lazy, dormant


_MANAGER_METHODS = ("_expanded_display", "_visualizer_section", "_expanded_display_mode_capable",
                    "_cycle_quick_visualizer_mode",
                    "_expanded_display_requested", "_persist_expanded_display_requested",
                    "_quick_custom_layout_session_active", "_expanded_display_ready",
                    "_expanded_display_blocks_layout",
                    # M3b: the coordinator's creation publishes the full-display overlays' inputs to the scene.
                    "_publish_expanded_overlays", "_publish_expanded_overlay_media")


def _manager(mode: str, *, requested: bool):
    """The display manager's Expanded Visualizer methods on a plain host (the QObject needs a whole runtime)."""
    from engine.display_manager import DisplayManager

    host_type = type("_ManagerHost", (), {name: getattr(DisplayManager, name) for name in _MANAGER_METHODS})
    manager = host_type()
    owner = _Owner(mode)
    unit = _unit()
    published = []
    overlays = []
    unit.runtime.scene_controller = SimpleNamespace(
        set_visualizer_expand_glyph=lambda available, expanded: published.append((available, expanded)),
        set_ordinary_widgets_covered=lambda covered, *, fade_s: published.append(("covered", covered, fade_s)),
        set_visualizer_expanded_overlay_config=lambda config: overlays.append(("config", dict(config))),
        announce_visualizer_preset=lambda name, *, reveal: overlays.append(("preset", name, reveal)),
        set_visualizer_overlay_media_model=lambda model: overlays.append(("media", model)))
    section = {"mode": mode, "expanded_display_requested": requested}
    manager.__dict__.update(
        _retired=False, _expanded_display_coordinator=None, _quick_visualizer_owner=owner,
        _quick_visualizer_unit=unit, settings_manager=None,
        _widgets_config_snapshot={"spotify_visualizer": section},
        _quick_custom_layout_owner=SimpleNamespace(is_active=False),
        _quick_visualizer_media_model=None,
    )
    manager.overlay_publications = overlays
    return manager, owner, published


def test_an_incapable_visualizer_without_intent_creates_no_coordinator():
    manager, owner, published = _manager(INCAPABLE, requested=False)
    manager._expanded_display_ready()
    assert manager._expanded_display_coordinator is None and published == [] and owner.calls == []
    assert manager._expanded_display_blocks_layout() is False
    # M3b: nor any full-display overlay input (they exist only where a takeover can draw them).
    assert manager.overlay_publications == []


@pytest.mark.parametrize("mode,requested,calls,glyph", [
    (CAPABLE, False, [], (True, False)),
    (CAPABLE, True, [(True, False)], (True, True)),
])
def test_a_capable_visualizer_gets_one_coordinator_at_admission(mode, requested, calls, glyph):
    manager, owner, published = _manager(mode, requested=requested)
    manager._expanded_display_ready()
    coordinator = manager._expanded_display_coordinator
    assert coordinator is not None and owner.calls == calls and published[-1] == glyph
    # The manager's own cover service reaches the owning scene: a restored expansion hides its widgets at once.
    assert [entry for entry in published if entry[0] == "covered"] == (
        [("covered", True, 0.0)] if requested else [])
    # M3b: the overlays' inputs reach the owning scene before the restore, the preset's name without a reveal.
    kinds = [entry[0] for entry in manager.overlay_publications]
    assert kinds == ["config", "preset", "media"]
    assert manager.overlay_publications[1][2] is False
    manager._expanded_display_ready()                         # a re-admission reuses the one coordinator
    assert manager._expanded_display_coordinator is coordinator
    assert manager._expanded_display_blocks_layout() is (requested is True)
    # ...and republishes them (a re-admitted owner may sit on another unit).
    assert [entry[0] for entry in manager.overlay_publications] == kinds * 2


def test_the_display_managers_double_click_cycles_through_the_takeover(monkeypatch):
    """The manager's cycle while expanded: Oscilloscope after Extruded Bubble's incapable neighbours, kept expanded;
    on main the plain next enabled mode (Waveform Ribbon, Voxel Sphere...) was requested and an expanded view would
    have collapsed for it."""
    from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS, build_visualizer_mode_activation

    manager, owner, _published = _manager(CAPABLE, requested=True)
    owner.controller.settings_model = SimpleNamespace(
        mode_activation=build_visualizer_mode_activation(VISUALIZER_MODE_IDS))
    manager._expanded_display_ready()
    assert manager._expanded_display_coordinator.phase is Phase.EXPANDED
    requested = []
    manager._request_quick_visualizer_mode = lambda target, **kw: requested.append((target, kw)) or True
    manager._cycle_quick_visualizer_mode()
    capable = CAPABLE_SET
    assert len(requested) == 1
    target, kwargs = requested[0]
    assert target in capable - {CAPABLE} and kwargs == {"_through_takeover": False}
    assert owner.calls == [(True, False)]                     # only the restore: the cycle never collapsed


# ------------------------------------------------------------------------------- the V key: the glyph's own press


class _GlyphScene(SimpleNamespace):
    """The scene's retained glyph projection, as the real scene controller keeps it."""

    glyph = (False, False)

    def set_visualizer_expand_glyph(self, available, expanded):
        self.glyph = (bool(available), bool(expanded))

    @property
    def visualizer_expand_glyph(self):
        return self.glyph


def _v_key_manager(mode: str):
    """The manager harness with the V route, the glyph's route and the generation gate, admitted input on the
    Visualizer's display, and a scene that retains the published glyph."""
    from engine.display_manager import DisplayManager

    manager, owner, _published = _manager(mode, requested=False)
    for name in ("_route_quick_visualizer_input", "_route_quick_visualizer_expand_glyph",
                 "_toggle_quick_visualizer_expansion_from_key"):
        setattr(manager, name, getattr(DisplayManager, name).__get__(manager))
    unit = manager._quick_visualizer_unit
    stub = vars(unit.runtime.scene_controller)
    unit.runtime.scene_controller = _GlyphScene(**{k: v for k, v in stub.items()
                                                   if k != "set_visualizer_expand_glyph"})
    unit.runtime.runtime_generation = 1
    unit.runtime.input_controller = SimpleNamespace(
        input_state=SimpleNamespace(admission_open=True, context_menu_active=False))
    manager._runtime_generation = 1
    manager.intent_writes = []
    manager.settings_manager = SimpleNamespace(
        set=lambda key, value: manager.intent_writes.append((key, value)), save=lambda: None,
        get=lambda key, default=None: None)                         # sections fall back to the snapshot
    manager._expanded_display_ready()
    return manager, owner, unit


def _spy_glyph_presses(manager) -> list[tuple[object, bool]]:
    presses: list[tuple[object, bool]] = []
    coordinator = manager._expanded_display_coordinator
    real = coordinator.glyph_pressed
    coordinator.glyph_pressed = lambda unit, expand: presses.append((unit, bool(expand))) or real(unit, expand)
    return presses


def _press_v(manager, source) -> None:
    """What the runtime's V signal reaches in the manager: the generation/admission gate, then the V route."""
    manager._route_quick_visualizer_input(source, manager._toggle_quick_visualizer_expansion_from_key, source)


def test_v_presses_the_glyph_entry_in_the_glyphs_direction_and_a_second_v_collapses():
    manager, owner, unit = _v_key_manager(CAPABLE)
    presses = _spy_glyph_presses(manager)
    coordinator = manager._expanded_display_coordinator
    assert unit.runtime.scene_controller.visualizer_expand_glyph == (True, False)
    _press_v(manager, unit)
    assert presses == [(unit, True)] and owner.calls == [(True, True)]
    owner.finish()
    assert coordinator.phase is Phase.EXPANDED
    intent_key = "widgets.spotify_visualizer.expanded_display_requested"
    assert manager.intent_writes == [(intent_key, True)]         # the glyph's persisted intent, once
    assert manager._expanded_display_requested() is True
    assert unit.runtime.scene_controller.visualizer_expand_glyph == (True, True)
    _press_v(manager, unit)                                       # the second V: the collapse the glyph offers
    assert presses == [(unit, True), (unit, False)]
    assert owner.calls[-1] == (False, True)
    owner.finish()
    assert coordinator.phase is Phase.ORDINARY and manager._expanded_display_requested() is False
    assert manager.intent_writes == [(intent_key, True), (intent_key, False)]


def test_v_and_the_glyph_reach_the_same_entry_with_the_same_outcome():
    """Control: the glyph's own route on an identical manager records exactly what V records."""
    by_v, owner_v, unit_v = _v_key_manager(CAPABLE)
    by_glyph, owner_g, unit_g = _v_key_manager(CAPABLE)
    v_presses, glyph_presses = _spy_glyph_presses(by_v), _spy_glyph_presses(by_glyph)
    _press_v(by_v, unit_v)
    by_glyph._route_quick_visualizer_expand_glyph(unit_g, True)
    assert [expand for _unit, expand in v_presses] == [expand for _unit, expand in glyph_presses] == [True]
    assert owner_v.calls == owner_g.calls == [(True, True)]


def test_v_is_refused_under_the_context_menu_closed_input_and_edit():
    manager, owner, unit = _v_key_manager(CAPABLE)
    presses = _spy_glyph_presses(manager)
    coordinator = manager._expanded_display_coordinator
    state = unit.runtime.input_controller.input_state
    state.context_menu_active = True
    _press_v(manager, unit)
    state.context_menu_active = False
    state.admission_open = False
    _press_v(manager, unit)
    state.admission_open = True
    unit.runtime.runtime_generation = 0                           # a stale generation's key
    _press_v(manager, unit)
    unit.runtime.runtime_generation = 1
    assert presses == [] and owner.calls == []
    # Edit withdraws the glyph, so V's press is refused exactly as an unoffered glyph's would be.
    manager._quick_custom_layout_owner = SimpleNamespace(is_active=True)
    coordinator.edit_entered()
    _press_v(manager, unit)
    assert owner.calls == [] and coordinator.phase is Phase.ORDINARY
    assert manager._route_quick_visualizer_expand_glyph(unit, True) is False
    # Negative control: the same V once Edit has gone expands.
    manager._quick_custom_layout_owner = SimpleNamespace(is_active=False)
    coordinator.edit_exited(saved=False)
    _press_v(manager, unit)
    assert owner.calls == [(True, True)]


def test_the_runtimes_v_signal_reaches_the_v_route_through_the_generation_gate():
    import inspect

    from engine.display_manager import DisplayManager

    source = "".join(inspect.getsource(DisplayManager._connect_quick_runtime).split())
    wiring = source.split("runtime.visualizer_expand_toggle_requested.connect(", 1)[1].split(".connect(", 1)[0]
    assert "self._route_quick_visualizer_input(" in wiring
    assert "self._toggle_quick_visualizer_expansion_from_key" in wiring
    # ...and the V route ends in the glyph's own route, never a second takeover entry.
    route = inspect.getsource(DisplayManager._toggle_quick_visualizer_expansion_from_key)
    assert "self._route_quick_visualizer_expand_glyph(" in route and "glyph_pressed" not in route


def test_v_on_an_incapable_mode_does_what_an_unoffered_glyph_does():
    manager, owner, unit = _v_key_manager(INCAPABLE)
    assert manager._expanded_display_coordinator is None
    assert manager._toggle_quick_visualizer_expansion_from_key(unit) is False
    assert manager._route_quick_visualizer_expand_glyph(unit, True) is False   # the glyph's own answer
    assert owner.calls == []
