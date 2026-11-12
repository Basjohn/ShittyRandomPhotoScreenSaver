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

    def move_display(self, runtime, *, end_expanded, hop, on_fade_out=None, on_fade_in=None, on_complete=None):
        """One display move as one fade-through (1C.2): recorded as ("move", end_expanded); ``finish`` runs it."""
        if self.is_retired:
            return False
        self.calls.append(("move", bool(end_expanded)))
        self.pending = ("move", runtime, bool(end_expanded), hop, on_fade_out, on_fade_in, on_complete)
        return True

    def finish(self) -> None:
        if self.pending[0] == "move":
            _kind, _runtime, end_expanded, hop, on_fade_out, on_fade_in, on_complete = self.pending
            self.pending = None
            source = self.expanded_display
            if on_fade_out is not None:
                on_fade_out()
            moved = bool(hop())                         # at zero opacity, on the ordinary card
            self.expanded_display = end_expanded if moved else source
            if on_fade_in is not None:
                on_fade_in(moved)
            if on_complete is not None:
                on_complete(moved)
            return
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


# ------------------------------------------------- plan 1B.12: one full-display glyph per target display


class _TwoDisplays(_Host):
    """Two displays; the move service is the CUSTOM hop + Save stand-in (it moves ``unit`` when it accepts)."""

    def __init__(self, *, accept: bool = True) -> None:
        self.accept = accept
        self.moves: list[str] = []
        super().__init__()
        self.units = (self.unit, _unit(1, "second"))
        services = self.coordinator._services
        from dataclasses import replace
        self.coordinator._services = replace(services, move_to_display=self._move, display_unit=lambda key: next(
            (unit for unit in self.units if display_key(unit) == key), None))

    def _move(self, display: str) -> bool:
        self.moves.append(display)
        # The takeover's own transfer is running while the move reaches the host binding.
        assert self.coordinator.transfer_in_flight
        if not self.accept:
            return False
        self.unit = next(unit for unit in self.units if display_key(unit) == display)
        return True


def test_a_display_glyph_on_the_cards_own_display_is_its_plain_expand_and_collapse():
    host = _TwoDisplays()
    host.coordinator.generation_ready()
    assert host.coordinator.expand_on_display(host.unit, host.units[0])
    host.owner.finish()
    assert host.coordinator.phase is Phase.EXPANDED and host.moves == [] and host.writes == [True]
    assert host.coordinator.expand_on_display(host.unit, host.units[0])        # the same glyph collapses there
    host.owner.finish()
    assert host.coordinator.phase is Phase.ORDINARY and host.writes == [True, False]


def test_a_display_glyph_for_the_other_display_moves_then_expands_there_as_one_user_action():
    """1C.2: one fade-through across the displays ends display-wide on the target: no ordinary card in between and
    no second enter; the commit persists the intent as the glyph's own enter does."""
    host = _TwoDisplays()
    host.coordinator.generation_ready()
    source, target = host.units
    assert host.coordinator.expand_on_display(source, target)
    assert host.coordinator.phase is Phase.TRANSFER_PENDING and host.owner.calls == [("move", True)]
    assert host.moves == []                                               # nothing moves before the fade's midpoint
    host.owner.finish()
    assert host.moves == [display_key(target)] and host.unit is target
    assert host.covers[-1] == (display_key(target), True, HALF)            # its widgets leave with the arrival
    assert host.coordinator.phase is Phase.EXPANDED and host.writes == [True]   # persisted as the glyph's own
    assert host.owner.calls == [("move", True)]                            # one transaction, never a second enter
    assert host.glyphs[-1] == (display_key(target), True, True)


def test_a_refused_move_stays_collapsed_on_the_source():
    host = _TwoDisplays(accept=False)
    host.coordinator.generation_ready()
    source, target = host.units
    host.coordinator.expand_on_display(source, target)
    host.owner.finish()
    assert host.moves == [display_key(target)] and host.unit is source
    assert host.coordinator.phase is Phase.ORDINARY and host.owner.calls == [("move", True)] and host.writes == []
    assert not host.owner.expanded_display and host.covers == []           # it faded back in where it was
    assert host.glyphs[-1] == (display_key(source), True, False)


@pytest.mark.parametrize("accept", [True, False])
def test_the_other_displays_glyph_moves_an_expanded_view_expanded(accept):
    """While expanded the card's own display glyph collapses; the other moves the view there expanded, as one
    fade-through (1C.2): it fades out display-wide on the source (its widgets fade back), moves at zero opacity, and
    fades in display-wide on the target (its widgets fade out). A refused move fades it back in display-wide on the
    source, so the rollback finds it exactly as it was; the intent is never written by the move."""
    host = _TwoDisplays(accept=accept)
    host.coordinator.generation_ready()
    source, target = host.units
    assert host.press(True)
    host.owner.finish()
    assert host.coordinator.expand_on_display(source, target)
    assert host.coordinator.phase is Phase.TRANSFER_PENDING and host.owner.calls[-1] == ("move", True)
    assert host.glyphs[-1][1] is False                                  # withdrawn while it moves
    host.owner.finish()
    landed = target if accept else source
    assert host.unit is landed
    assert host.covers[-2:] == [(display_key(source), False, HALF), (display_key(landed), True, HALF)]
    assert [call for call in host.owner.calls if call[0] != "move"] == [(True, True)]   # only the first enter
    assert host.coordinator.phase is Phase.EXPANDED and host.owner.expanded_display
    assert host.writes == [True]
    assert host.glyphs[-1] == (display_key(landed), True, True)


def test_a_display_glyph_is_refused_under_edit_and_from_a_display_without_the_card():
    host = _TwoDisplays()
    host.coordinator.generation_ready()
    source, target = host.units
    assert not host.coordinator.expand_on_display(target, source)         # the press must come from the card
    host.edit = True
    host.coordinator.edit_entered()
    assert not host.coordinator.expand_on_display(source, target)
    assert host.moves == [] and host.owner.calls == []


# ------------------------------------- plan 1B.12, relative form: the glyphs follow the displays' arrangement


LEFT, HERE, RIGHT = -1, 0, 1


def _row_rects(count: int, *, size=(1920, 1080)) -> list[tuple[int, int, int, int]]:
    """``count`` displays edge to edge, left to right (test-owned geometry)."""
    return [(index * size[0], 0, size[0], size[1]) for index in range(count)]


def _arranged(rects, *, on: int, accept: bool = True, mode: str = CAPABLE, requested: bool = False,
              indices=None):
    """The manager harness on displays placed at ``rects`` (the Visualizer on ``rects[on]``), with the production
    takeover wiring (the coordinator's glyph publication and display move go through the manager's own methods).
    Screen indices run against the arrangement by default (right to left), so nothing can lean on the index."""
    manager, owner, _published = _manager(mode, requested=requested)
    indices = list(indices) if indices is not None else list(reversed(range(len(rects))))
    units = [_placed(index, rect) for index, rect in zip(indices, rects)]
    manager.displays = units
    manager._quick_visualizer_unit = units[on]
    moves: list[object] = []

    def move(target) -> bool:
        moves.append(target)
        if accept:
            manager._quick_visualizer_unit = target
        return accept
    manager._quick_custom_layout_owner = SimpleNamespace(is_active=False, move_visualizer_to_display=move)
    manager._refresh_all_quick_context_menus = lambda: None
    manager.settings_manager = SimpleNamespace(set=lambda key, value: None, save=lambda: None,
                                               get=lambda key, default=None: None)   # the snapshot keeps the intent
    manager._expanded_display_ready()
    return manager, owner, units, moves


class _ArrangedScene:
    """A display's scene as the takeover publishes to it: the glyph (offered, expanded) and its side glyphs."""

    def __init__(self) -> None:
        self.glyph = (False, False)
        self.sides = (False, False)

    def set_visualizer_expand_glyph(self, available, expanded, *, sides=(False, False)):
        self.glyph = (bool(available), bool(expanded))
        self.sides = (bool(sides[0]), bool(sides[1]))

    @property
    def visualizer_expand_glyph(self):
        return self.glyph

    def set_ordinary_widgets_covered(self, covered, *, fade_s):
        pass

    def set_visualizer_expanded_overlay_config(self, config):
        pass

    def announce_visualizer_preset(self, name, *, reveal):
        pass

    def set_visualizer_overlay_media_model(self, model):
        pass


def _placed(index: int, rect):
    identity = SimpleNamespace(screen_key=f"monitor-{index}", geometry=tuple(rect))
    return SimpleNamespace(screen_index=index, is_retired=False, runtime=SimpleNamespace(
        display_identity=identity, scene_controller=_ArrangedScene(), runtime_generation=1,
        input_controller=SimpleNamespace(input_state=SimpleNamespace(admission_open=True, context_menu_active=False))))


def _offered(unit) -> tuple[bool, bool, bool]:
    """(up-left, this display, up-right) as the unit's scene shows them."""
    available, _expanded = unit.runtime.scene_controller.glyph
    left, right = unit.runtime.scene_controller.sides
    return (available and left, available, available and right)


@pytest.mark.parametrize("count", [1, 2, 3])
def test_the_row_offers_a_side_glyph_only_where_a_display_lies(count):
    """One display: the Up arrow alone. A row: the left end offers right only, the right end left only, a middle
    display both. Screen indices run against the arrangement (right to left)."""
    rects = _row_rects(count)
    for on in range(count):
        manager, _owner, units, _moves = _arranged(rects, on=on)
        assert _offered(units[on]) == (on > 0, True, on < count - 1), on


@pytest.mark.parametrize("offset", [0, 400])
def test_a_vertical_arrangement_offers_no_side_glyph(offset):
    rects = [(offset, -1080, 1920, 1080), (0, 0, 2560, 1440)]
    for on in range(2):
        _manager_, _owner, units, _moves = _arranged(rects, on=on)
        assert _offered(units[on]) == (False, True, False)


def test_an_offset_arrangement_follows_the_documented_rule():
    """A display beside the Visualizer's but offset down (sharing part of its height) is its right neighbour; one
    wholly below and to the left (corner only) is still its left neighbour, since nothing else is on that side."""
    rects = [(0, 0, 2560, 1440), (2560, 700, 1920, 1080), (-1920, 1440, 1920, 1080)]
    _manager_, _owner, units, _moves = _arranged(rects, on=0)
    assert _offered(units[0]) == (True, True, True)


@pytest.mark.parametrize("on,side", [(0, RIGHT), (1, LEFT), (1, RIGHT), (2, LEFT)])
def test_a_side_press_moves_to_that_neighbour_and_expands_there(on, side):
    """Three in a row: each offered side glyph is full display on the display placed on that side (resolved at the
    press, through the owner's "expand on display N"), one user action: one fade-through that moves at its midpoint
    and arrives display-wide (1C.2)."""
    manager, owner, units, moves = _arranged(_row_rects(3), on=on)
    target = units[on + side]
    assert manager._route_quick_visualizer_expand_to_side(units[on], side)
    assert owner.calls == [("move", True)] and moves == []
    owner.finish()
    assert moves == [target] and manager._quick_visualizer_unit is target
    coordinator = manager._expanded_display_coordinator
    assert coordinator.phase is Phase.EXPANDED and manager._expanded_display_requested() is True
    # The row on the new display shows that display's own neighbours, its glyph the collapse.
    assert target.runtime.scene_controller.glyph == (True, True)
    assert _offered(target) == (on + side > 0, True, on + side < 2)
    assert units[on].runtime.scene_controller.glyph == (False, False)          # withdrawn where it left


@pytest.mark.parametrize("on,side", [(0, LEFT), (2, RIGHT)])
def test_a_press_toward_no_display_is_refused(on, side):
    manager, owner, units, moves = _arranged(_row_rects(3), on=on)
    assert not manager._route_quick_visualizer_expand_to_side(units[on], side)
    assert moves == [] and owner.calls == []


def test_a_side_press_from_another_display_or_under_a_menu_is_refused():
    manager, owner, units, moves = _arranged(_row_rects(2), on=0)
    assert not manager._route_quick_visualizer_expand_to_side(units[1], LEFT)    # not the card's display
    units[0].runtime.input_controller.input_state.context_menu_active = True
    assert not manager._route_quick_visualizer_expand_to_side(units[0], RIGHT)   # a menu is open
    units[0].runtime.input_controller.input_state.context_menu_active = False
    assert not manager._route_quick_visualizer_expand_to_side(units[0], 0)       # not a side
    assert moves == [] and owner.calls == []


def _expanded_on_the_middle(**kwargs):
    manager, owner, units, moves = _arranged(_row_rects(3), on=1, **kwargs)
    assert manager._route_quick_visualizer_expand_glyph(units[1], True)
    owner.finish()
    assert manager._expanded_display_coordinator.phase is Phase.EXPANDED
    return manager, owner, units, moves


def test_expanded_on_the_middle_display_offers_the_collapse_and_both_moves():
    _manager_, _owner, units, _moves = _expanded_on_the_middle()
    scene = units[1].runtime.scene_controller
    assert scene.glyph == (True, True)                     # this display's glyph is the collapse (the Down arrow)
    assert scene.sides == (True, True)                     # and both diagonals move the view


@pytest.mark.parametrize("side", [LEFT, RIGHT])
@pytest.mark.parametrize("accept", [True, False])
def test_a_diagonal_moves_the_expanded_view_to_that_neighbour(side, accept):
    """While expanded a diagonal is the expanded-to-expanded move, one fade-through (1C.2): out display-wide on the
    source, the move at zero opacity, in display-wide on the neighbour; a refused move fades back in on the source.
    The intent is never written by the move."""
    manager, owner, units, moves = _expanded_on_the_middle(accept=accept)
    writes = manager._expanded_display_requested()
    assert manager._route_quick_visualizer_expand_to_side(units[1], side)
    assert owner.calls[-1] == ("move", True)               # never a collapse on the source first
    owner.finish()
    landed = units[1 + side] if accept else units[1]
    assert moves == [units[1 + side]] and manager._quick_visualizer_unit is landed
    assert owner.calls[-1] == ("move", True) and owner.expanded_display
    assert manager._expanded_display_coordinator.phase is Phase.EXPANDED
    assert manager._expanded_display_requested() is writes
    assert landed.runtime.scene_controller.glyph == (True, True)


@pytest.mark.parametrize("on_view_display", [True, False])
def test_the_edit_holds_refuse_a_side_move(on_view_display):
    """Fullscreen Edit (Edit on the view's display) and an Edit beside the view (another display): the glyphs are
    withdrawn and a stale side press moves nothing; the view stays expanded where it is."""
    manager, owner, units, moves = _expanded_on_the_middle()
    coordinator = manager._expanded_display_coordinator
    manager._quick_custom_layout_owner.is_active = True
    coordinator.edit_entered(on_view_display=on_view_display)
    assert units[1].runtime.scene_controller.glyph[0] is False
    calls = list(owner.calls)
    for side in (LEFT, RIGHT):
        assert not manager._route_quick_visualizer_expand_to_side(units[1], side)
    assert moves == [] and owner.calls == calls and coordinator.phase is Phase.EXPANDED
    assert manager._quick_visualizer_unit is units[1]


def test_v_still_expands_on_the_current_display():
    manager, owner, units, moves = _arranged(_row_rects(3), on=1)
    from engine.display_manager import DisplayManager

    toggle = DisplayManager._toggle_quick_visualizer_expansion_from_key.__get__(manager)
    assert toggle(units[1])
    owner.finish()
    assert moves == [] and manager._quick_visualizer_unit is units[1]
    assert manager._expanded_display_coordinator.phase is Phase.EXPANDED


def test_a_display_added_or_removed_changes_which_side_glyphs_show():
    """The display set is read at each publication: a display added to the left offers the up-left glyph from the
    next admission (a topology change replaces the generation), and a display removed withdraws its side."""
    rects = _row_rects(2)
    manager, _owner, units, _moves = _arranged(rects, on=0)
    card = units[0]
    assert _offered(card) == (False, True, True)
    manager.displays = [_placed(7, (-1920, 0, 1920, 1080)), *units]          # one more, to the left
    manager._expanded_display_ready()
    assert _offered(card) == (True, True, True)
    manager.displays = [manager.displays[0], card]                            # the right-hand display went
    manager._expanded_display_ready()
    assert _offered(card) == (True, True, False)


def test_only_the_takeovers_own_transfer_passes_the_layout_wait():
    """The display seam refuses a move while the view is display-wide (an Edit hop), except the takeover's own
    transfer, which is not reported back to it (it is already the reducer's transaction)."""
    from engine import display_manager as dm

    moved, reported = [], []
    coordinator = SimpleNamespace(blocks_ordinary_layout=True, transfer_in_flight=False,
                                  display_transferred=lambda: reported.append(1))
    manager = SimpleNamespace(_expanded_display_coordinator=coordinator, _publish_expanded_overlays=lambda: None)
    binding = SimpleNamespace(transfer=lambda target: moved.append(target) or True)
    seam = dm.DisplayManager._transfer_quick_visualizer_unit.__get__(manager)
    original = dm._visualizer_host_binding
    dm._visualizer_host_binding = lambda _manager: binding
    try:
        with pytest.raises(RuntimeError):
            seam("target")
        assert moved == []
        coordinator.transfer_in_flight = True
        assert seam("target") and moved == ["target"] and reported == []
        coordinator.blocks_ordinary_layout, coordinator.transfer_in_flight = False, False
        assert seam("other") and reported == [1]                         # an ordinary Edit hop is reported
    finally:
        dm._visualizer_host_binding = original


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
                    "_publish_expanded_overlays", "_publish_expanded_overlay_media",
                    # Plan 1B.12: the glyph publication asks which sides have a display; a side press resolves
                    # there; the takeover's move and the glyph's own routes.
                    "_expand_glyph_neighbours", "_expand_glyph_sides", "_route_quick_visualizer_expand_to_side",
                    "_move_quick_visualizer_to_display", "_quick_unit_for_display",
                    "_route_quick_visualizer_expand_glyph",
                    "_toggle_quick_visualizer_expansion_from_key")


def _manager(mode: str, *, requested: bool):
    """The display manager's Expanded Visualizer methods on a plain host (the QObject needs a whole runtime)."""
    from engine.display_manager import DisplayManager

    members = {name: getattr(DisplayManager, name) for name in _MANAGER_METHODS}
    # The live units are the plain host's displays (the production filter is a type check on the Quick unit).
    members["_live_quick_units"] = lambda self: tuple(unit for unit in self.displays if not unit.is_retired)
    host_type = type("_ManagerHost", (), members)
    manager = host_type()
    owner = _Owner(mode)
    unit = _unit()
    published = []
    overlays = []
    unit.runtime.scene_controller = SimpleNamespace(
        set_visualizer_expand_glyph=lambda available, expanded, sides=(False, False): published.append(
            (available, expanded)),
        set_ordinary_widgets_covered=lambda covered, *, fade_s: published.append(("covered", covered, fade_s)),
        set_visualizer_expanded_overlay_config=lambda config: overlays.append(("config", dict(config))),
        announce_visualizer_preset=lambda name, *, reveal: overlays.append(("preset", name, reveal)),
        set_visualizer_overlay_media_model=lambda model: overlays.append(("media", model)))
    section = {"mode": mode, "expanded_display_requested": requested}
    manager.__dict__.update(
        _retired=False, _expanded_display_coordinator=None, _quick_visualizer_owner=owner,
        _quick_visualizer_unit=unit, settings_manager=None, displays=[unit],
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

    def set_visualizer_expand_glyph(self, available, expanded, *, sides=(False, False)):
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
