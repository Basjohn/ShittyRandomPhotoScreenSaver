"""Application-level capability activation authority (Phase E).

Activation is separate from a widget instance's ``enabled`` flag and from a
transition's random-pool membership. These tests pin the read/write semantics
and, critically, that the canonical defaults keep every capability activated so
current behaviour is unchanged until H0 sets final Quick-era defaults.
"""
from __future__ import annotations

import pytest

from core.settings import capability_activation as ca
from core.settings.defaults import get_default_settings
from rendering.transition_registry import get_transition_setting_names
from rendering.widget_descriptors import get_widget_family_descriptors


# --- Defaults preserve current behaviour -----------------------------------


def test_canonical_default_activates_visualizers():
    widgets = get_default_settings()["widgets"]
    assert ca.is_widget_family_activated(widgets, "visualizers") is True


# --- Visualizers -> Media dependency ---------------------------------------


def test_visualizers_and_media_both_on_is_valid():
    cfg = {"family_activation": {"media": True, "visualizers": True}}
    assert ca.normalize_widget_capability_state(cfg) is False
    assert ca.is_widget_family_activated(cfg, "visualizers") is True


def test_visualizers_off_media_on_is_valid():
    cfg = {"family_activation": {"media": True, "visualizers": False}}
    assert ca.normalize_widget_capability_state(cfg) is False


def test_media_off_forces_visualizers_off():
    cfg = {"family_activation": {"media": False, "visualizers": True}}
    changed = ca.normalize_widget_capability_state(cfg)
    assert changed is True
    assert ca.is_widget_family_activated(cfg, "visualizers") is False
    # Media is NOT implicitly reactivated.
    assert ca.is_widget_family_activated(cfg, "media") is False


def test_media_off_visualizers_off_is_valid():
    cfg = {"family_activation": {"media": False, "visualizers": False}}
    assert ca.normalize_widget_capability_state(cfg) is False


def test_dependency_helpers():
    on = {"family_activation": {"media": True, "visualizers": True}}
    off = {"family_activation": {"media": False, "visualizers": True}}
    assert ca.is_widget_family_dependency_satisfied(on, "visualizers") is True
    assert ca.is_widget_family_dependency_satisfied(off, "visualizers") is False
    assert ca.is_widget_family_effective(off, "visualizers") is False


def test_canonical_defaults_activate_every_family():
    widgets = get_default_settings()["widgets"]
    for family in get_widget_family_descriptors():
        # A family omitted from the explicit activation defaults must still read
        # as activated via the True fallback.
        assert ca.is_widget_family_activated(widgets, family.family_id) is True


def test_canonical_defaults_activate_every_transition():
    transitions = get_default_settings()["transitions"]
    for name in get_transition_setting_names():
        assert ca.is_transition_activated(transitions, name) is True


def test_default_family_activation_keys_are_explicit_for_stable_families():
    activation = get_default_settings()["widgets"]["family_activation"]
    for family_id in ("clocks", "weather", "media", "reddit", "gmail", "steam"):
        assert activation[family_id] is True


# --- Missing state means activated -----------------------------------------


def test_missing_state_reads_as_activated():
    assert ca.is_widget_family_activated({}, "clocks") is True
    assert ca.is_widget_family_activated(None, "clocks") is True
    assert ca.is_transition_activated({}, "Burn") is True
    assert ca.is_transition_activated(None, "Burn") is True


def test_unknown_capability_reads_as_activated():
    assert ca.is_widget_family_activated({}, "does_not_exist") is True
    assert ca.is_transition_activated({}, "Not A Transition") is True


# --- Explicit deactivation --------------------------------------------------


def test_family_deactivation_round_trips():
    widgets: dict = {}
    ca.set_widget_family_activated(widgets, "clocks", False)
    assert ca.is_widget_family_activated(widgets, "clocks") is False
    ca.set_widget_family_activated(widgets, "clocks", True)
    assert ca.is_widget_family_activated(widgets, "clocks") is True


def test_setting_unknown_family_is_a_noop():
    widgets: dict = {}
    ca.set_widget_family_activated(widgets, "not_a_family", False)
    assert ca.WIDGET_FAMILY_ACTIVATION_KEY not in widgets


def test_transition_deactivation_round_trips_and_accepts_aliases():
    transitions: dict = {}
    ca.set_transition_activated(transitions, "Ripple", False)
    assert ca.is_transition_activated(transitions, "Ripple") is False
    # Legacy alias resolves to the same canonical capability.
    assert ca.is_transition_activated(transitions, "Rain Drops") is False
    # Stable id resolves too.
    assert ca.is_transition_activated(transitions, "ripple") is False


def test_is_widget_activated_maps_through_family():
    widgets: dict = {}
    ca.set_widget_family_activated(widgets, "reddit", False)
    assert ca.is_widget_activated(widgets, "reddit") is False
    assert ca.is_widget_activated(widgets, "reddit2") is False
    # Visualizer has no owning family -> never gated by family activation.
    assert ca.is_widget_activated(widgets, "spotify_visualizer") is True


# --- Effective random pool = activated ∩ pool-member ------------------------


def test_effective_pool_intersects_activation_and_membership():
    transitions = {
        "pool": {"Ripple": True, "Burn": True, "Wipe": False},
        "activation": {"Burn": False},
    }
    pool = ca.get_effective_random_pool(transitions)
    assert "Ripple" in pool
    assert "Burn" not in pool  # pool member but deactivated
    assert "Wipe" not in pool  # activated but not a pool member


def test_deactivation_preserves_pool_preference_for_later_reactivation():
    transitions = {"pool": {"Burn": True}, "activation": {"Burn": False}}
    assert "Burn" not in ca.get_effective_random_pool(transitions)
    # Preference survived; reactivation restores it to the effective pool.
    ca.set_transition_activated(transitions, "Burn", True)
    assert "Burn" in ca.get_effective_random_pool(transitions)


def test_random_mode_effective_requires_nonempty_pool():
    # Random on, but effective pool empty (only member is deactivated).
    empty = {
        "random_always": True,
        "pool": {"Burn": True},
        "activation": {"Burn": False},
    }
    assert ca.is_random_mode_effective(empty) is False

    ok = {"random_always": True, "pool": {"Ripple": True}}
    assert ca.is_random_mode_effective(ok) is True

    off = {"random_always": False, "pool": {"Ripple": True}}
    assert ca.is_random_mode_effective(off) is False


def test_default_settings_random_mode_is_effective():
    # Sanity: the shipped defaults do not silently produce an empty pool.
    transitions = get_default_settings()["transitions"]
    if transitions.get("random_always"):
        assert ca.is_random_mode_effective(transitions) is True


# --- Deterministic activated fallback / manual resolution ------------------


def test_activated_manual_request_remains_itself():
    assert ca.resolve_manual_transition_selection({}, "Burn") == "Burn"
    # Stable id / legacy alias canonicalize but stay the requested capability.
    assert ca.resolve_manual_transition_selection({}, "burn") == "Burn"


def test_deactivated_manual_request_resolves_to_activated_fallback():
    transitions = {"activation": {"Burn": False}}
    resolved = ca.resolve_manual_transition_selection(transitions, "Burn")
    assert resolved != "Burn"
    assert ca.is_transition_activated(transitions, resolved) is True
    # Crossfade activated by default -> it is the deterministic fallback.
    assert resolved == "Crossfade"


def test_default_activated_transition_prefers_crossfade():
    assert ca.get_default_activated_transition({}) == "Crossfade"


def test_default_activated_transition_when_crossfade_deactivated():
    # Crossfade deactivated -> the first other activated transition (canonical
    # registry order) is chosen; never a deactivated one.
    transitions = {"activation": {"Crossfade": False}}
    resolved = ca.get_default_activated_transition(transitions)
    assert resolved != "Crossfade"
    assert ca.is_transition_activated(transitions, resolved) is True
    assert resolved in ca.get_activated_transition_names(transitions)


# --- ensure_recovery_transition_activated ----------------------------------


def test_ensure_recovery_reactivates_crossfade_when_deactivated():
    transitions = {"activation": {t: False for t in get_transition_setting_names()}}
    assert ca.ensure_recovery_transition_activated(transitions) is True
    assert ca.is_transition_activated(transitions, "Crossfade") is True


def test_ensure_recovery_is_noop_when_crossfade_already_activated():
    transitions: dict = {}
    assert ca.ensure_recovery_transition_activated(transitions) is False


# --- normalize_transition_capability_state (the one authority) -------------


def test_normalize_is_noop_on_default_settings():
    transitions = get_default_settings()["transitions"]
    before = dict(transitions)
    changed = ca.normalize_transition_capability_state(transitions)
    assert changed is False
    assert transitions == before


def test_normalize_repairs_zero_activated_state():
    # All-false activation -> reactivate the recovery transition (Crossfade).
    transitions = {"activation": {t: False for t in get_transition_setting_names()}}
    changed = ca.normalize_transition_capability_state(transitions)
    assert changed is True
    assert ca.is_transition_activated(transitions, "Crossfade") is True
    assert ca.get_activated_transition_names(transitions) == ("Crossfade",)


def test_normalize_disables_random_on_empty_effective_pool_and_preserves_pool():
    # Random on, but the only pooled transition is deactivated -> empty effective
    # pool. Normalization turns Random off, persists a deterministic activated
    # manual selection, and leaves saved pool membership untouched.
    transitions = {
        "random_always": True,
        "pool": {"Burn": True},
        "activation": {"Burn": False},
        "type": "Burn",
    }
    changed = ca.normalize_transition_capability_state(transitions)
    assert changed is True
    assert transitions["random_always"] is False
    assert ca.is_transition_activated(transitions, transitions["type"]) is True
    # Saved pool preference preserved (never erased) for later reactivation.
    assert transitions["pool"] == {"Burn": True}


def test_normalize_converts_legacy_type_random_to_single_authority():
    # E2.6: legacy type="Random" must not act as a second random authority.
    transitions = {
        "type": "Random",
        "random_always": False,
        "pool": {name: True for name in get_transition_setting_names()},
    }
    changed = ca.normalize_transition_capability_state(transitions)
    assert changed is True
    assert transitions["random_always"] is True
    assert transitions["type"] != "Random"
    assert ca.is_transition_activated(transitions, transitions["type"]) is True


def test_normalize_type_random_with_empty_pool_disables_random():
    # type="Random" turns random on, but an empty effective pool then turns it
    # back off with a concrete manual selection (invariants compose).
    transitions = {
        "type": "Random",
        "random_always": False,
        "pool": {"Burn": True},
        "activation": {"Burn": False},
    }
    changed = ca.normalize_transition_capability_state(transitions)
    assert changed is True
    assert transitions["random_always"] is False
    assert transitions["type"] not in ("Random", "Burn")
    assert ca.is_transition_activated(transitions, transitions["type"]) is True


def test_normalize_leaves_random_on_with_nonempty_effective_pool():
    transitions = {
        "random_always": True,
        "pool": {"Ripple": True, "Burn": True},
        "activation": {"Burn": False},
    }
    changed = ca.normalize_transition_capability_state(transitions)
    assert changed is False
    assert transitions["random_always"] is True
