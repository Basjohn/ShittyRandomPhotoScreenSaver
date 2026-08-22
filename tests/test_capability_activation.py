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


def test_canonical_defaults_activate_every_family():
    widgets = get_default_settings()["widgets"]
    for family in get_widget_family_descriptors():
        # imgur is dev-only and omitted from defaults; it must still read as
        # activated via the True fallback.
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
