"""Final transition admission fencing against activation (Phase E, doc 07 §2.3/§5.6).

These cross the real engine random/cycle preparation seam and prove that a
transition deactivated (or made hardware-invalid) *after* a choice was prepared
can never instantiate merely because it was resolved earlier or because a
candidate list became empty. A deactivated Crossfade last-resort must never run;
an empty effective Random pool is resolved by explicit canonical normalization,
not a renderer bypass. The render-time final-admission fail-closed seam moved off
the retired ``TransitionFactory`` to the Quick request resolver — its stale-choice
rejection (deactivated / hardware-invalid / out-of-pool) is now proven by
``test_qtquick_transition_request_resolution`` — so only the still-live engine
random-prep and C-key cycle seams remain here.

They are inert while every transition is activated (the shipped default).
"""
from __future__ import annotations

from types import SimpleNamespace

from core.settings.capability_activation import (
    is_transition_activated,
)
from rendering.transition_registry import (
    get_transition_setting_names,
)


# --- Engine random preparation seam ----------------------------------------


class _FakeSettingsManager:
    def __init__(self, *, transitions: dict, hw_accel: bool = True) -> None:
        self._transitions = transitions
        self._display = {"hw_accel": hw_accel}

    def get(self, key, default=None):
        if key == "transitions":
            return self._transitions
        if key == "display.hw_accel":
            return self._display.get("hw_accel", default)
        if isinstance(key, str) and key.startswith("transitions."):
            node = self._transitions
            for part in key.split(".")[1:]:
                if not isinstance(node, dict) or part not in node:
                    return default
                node = node[part]
            return node
        return default

    def set(self, key, value):
        if key == "transitions":
            self._transitions = value
            return
        if isinstance(key, str) and key.startswith("transitions."):
            node = self._transitions
            parts = key.split(".")[1:]
            for part in parts[:-1]:
                nxt = node.get(part)
                if not isinstance(nxt, dict):
                    nxt = {}
                    node[part] = nxt
                node = nxt
            node[parts[-1]] = value

    def save(self):
        return


def test_engine_disables_random_when_effective_pool_empties():
    from engine.screensaver_engine import ScreensaverEngine

    pool = {name: False for name in get_transition_setting_names()}
    pool["Burn"] = True
    transitions = {
        "type": "Random",
        "random_always": True,
        "pool": pool,
        "activation": {"Burn": False},  # the only pooled member is deactivated
    }
    settings = _FakeSettingsManager(transitions=transitions, hw_accel=True)
    engine = type("EngineStub", (), {"settings_manager": settings})()

    ScreensaverEngine._prepare_random_transition_if_needed(engine)

    # Random turned off (empty effective pool) and no random_choice prepared.
    assert settings.get("transitions.random_always") is False
    assert settings.get("transitions.random_choice") is None
    # A deterministic activated manual selection was persisted.
    manual = settings.get("transitions.type")
    assert is_transition_activated(transitions, manual)


def test_engine_zero_activated_state_repairs_and_selects_activated():
    from engine.screensaver_engine import ScreensaverEngine

    transitions = {
        "type": "Random",
        "random_always": True,
        "pool": {name: True for name in get_transition_setting_names()},
        "activation": {name: False for name in get_transition_setting_names()},
    }
    settings = _FakeSettingsManager(transitions=transitions, hw_accel=True)
    engine = type("EngineStub", (), {"settings_manager": settings})()

    ScreensaverEngine._prepare_random_transition_if_needed(engine)

    # Zero-activated repaired: Crossfade reactivated in canonical state.
    assert is_transition_activated(transitions, "Crossfade")


# --- C-key cycle seam ------------------------------------------------------


def test_cycle_never_selects_deactivated_crossfade():
    from engine import engine_handlers

    # Only Ripple activated; Crossfade deactivated. Cycling must land on an
    # activated transition, never the deactivated Crossfade.
    activation = {name: False for name in get_transition_setting_names()}
    activation["Ripple"] = True
    transitions = {
        "type": "Slide",
        "random_always": False,
        "pool": {name: True for name in get_transition_setting_names()},
        "activation": activation,
    }
    settings = _FakeSettingsManager(transitions=transitions, hw_accel=True)
    engine = SimpleNamespace(
        settings_manager=settings,
        _transition_types=list(get_transition_setting_names()),
        _current_transition_index=0,
    )

    engine_handlers.on_cycle_transition(engine)

    chosen = settings.get("transitions.type")
    assert chosen != "Crossfade"
    assert is_transition_activated(transitions, chosen)
    assert chosen == "Ripple"


def test_cycle_recovery_reactivates_crossfade_when_no_hw_candidate():
    from engine import engine_handlers

    # Only Burn (hw-required) activated, every hw-safe transition (incl.
    # Crossfade) deactivated, hardware off. Cycling has no activated hw-available
    # candidate, so it must perform the explicit canonical recovery repair
    # (reactivate + persist Crossfade) rather than select a deactivated Crossfade.
    activation = {name: False for name in get_transition_setting_names()}
    activation["Burn"] = True
    transitions = {
        "type": "Slide",
        "random_always": False,
        "pool": {name: True for name in get_transition_setting_names()},
        "activation": activation,
    }
    settings = _FakeSettingsManager(transitions=transitions, hw_accel=False)
    engine = SimpleNamespace(
        settings_manager=settings,
        _transition_types=list(get_transition_setting_names()),
        _current_transition_index=0,
    )

    engine_handlers.on_cycle_transition(engine)

    chosen = settings.get("transitions.type")
    assert chosen == "Crossfade"
    assert is_transition_activated(transitions, "Crossfade") is True
