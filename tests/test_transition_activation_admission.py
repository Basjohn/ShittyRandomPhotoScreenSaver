"""Final transition admission fencing against activation (Phase E, doc 07 §2.3/§5.6).

These cross the real selection seams — the transition factory and the engine
random/cycle preparation — and prove that a transition deactivated (or made
hardware-invalid) *after* a choice was prepared can never instantiate merely
because it was resolved earlier or because a candidate list became empty. A
deactivated Crossfade last-resort must never run; an empty effective Random pool
is resolved by explicit canonical normalization, not a renderer bypass.

They are inert while every transition is activated (the shipped default).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.settings.capability_activation import (
    is_transition_activated,
)
from rendering.transition_registry import (
    get_transition_setting_names,
    is_transition_available_for_hw,
)


# --- Factory admission seam ------------------------------------------------


class _StubFactorySettings:
    """Minimal SettingsManager stand-in for exercising factory selection."""

    def __init__(self, transitions: dict, *, hw: bool = True) -> None:
        self._transitions = transitions
        self._hw = hw
        self.save_calls = 0

    def get(self, key, default=None):
        if key == "transitions":
            return self._transitions
        if key == "display.hw_accel":
            return self._hw
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

    def save(self):
        self.save_calls += 1


def _factory_selected_type(monkeypatch, transitions: dict, *, hw: bool = True):
    from rendering.transition_factory import TransitionFactory

    captured: dict = {}

    def _fake_create_by_type(self, ttype, settings, duration_ms, easing):
        captured["type"] = ttype
        return SimpleNamespace(set_resource_manager=lambda rm: None)

    monkeypatch.setattr(TransitionFactory, "_create_by_type", _fake_create_by_type)
    settings = _StubFactorySettings(transitions, hw=hw)
    factory = TransitionFactory(settings)
    result = factory.create_transition()
    assert result is not None
    return captured.get("type"), settings


def test_factory_rejects_stale_deactivated_random_choice(monkeypatch):
    # A random choice (Burn) was prepared, then Burn was deactivated. The factory
    # must NOT instantiate Burn merely because it was pre-resolved.
    transitions = {
        "random_always": True,
        "pool": {"Ripple": True, "Burn": True},
        "activation": {"Burn": False},
        "random_choice": "Burn",
    }
    chosen, settings = _factory_selected_type(monkeypatch, transitions)
    assert chosen != "Burn"
    assert is_transition_activated(settings.get("transitions"), chosen)


def test_factory_rejects_hardware_invalid_stale_random_choice(monkeypatch):
    # Burn requires hardware acceleration; the pre-resolved choice is now invalid
    # because hardware is off. The factory re-resolves to an hw-safe transition.
    transitions = {
        "random_always": True,
        "pool": {name: True for name in get_transition_setting_names()},
        "random_choice": "Burn",
    }
    chosen, _settings = _factory_selected_type(monkeypatch, transitions, hw=False)
    assert chosen != "Burn"
    assert is_transition_available_for_hw(chosen, False)


def test_factory_manual_selection_of_deactivated_transition_falls_back(monkeypatch):
    transitions = {
        "random_always": False,
        "type": "Burn",
        "activation": {"Burn": False},
    }
    chosen, settings = _factory_selected_type(monkeypatch, transitions)
    assert chosen != "Burn"
    assert is_transition_activated(settings.get("transitions"), chosen)


def test_factory_fails_closed_when_no_hw_candidate(monkeypatch):
    # No-activated-hw-candidate state: only an hw-REQUIRED transition (Burn) is
    # activated+pooled while hardware is off, so the effective pool
    # (activated ∩ saved pool ∩ hardware) is empty. Random must FAIL CLOSED — the
    # factory instantiates nothing rather than broadening beyond the saved pool
    # (E2 §10). It must never run an out-of-pool transition.
    from rendering.transition_factory import TransitionFactory

    calls: list[str] = []

    def _fake_create_by_type(self, ttype, settings, duration_ms, easing):
        calls.append(ttype)
        return SimpleNamespace(set_resource_manager=lambda rm: None)

    monkeypatch.setattr(TransitionFactory, "_create_by_type", _fake_create_by_type)

    activation = {name: False for name in get_transition_setting_names()}
    activation["Burn"] = True  # hw-required, unavailable with hw off
    transitions = {
        "random_always": True,
        "pool": {name: (name == "Burn") for name in get_transition_setting_names()},
        "activation": activation,
    }
    settings = _StubFactorySettings(transitions, hw=False)
    factory = TransitionFactory(settings)

    result = factory.create_transition()

    assert result is None
    assert calls == []  # nothing instantiated; no out-of-pool substitution


def test_factory_fails_closed_when_pick_random_raises(monkeypatch):
    # Correction 1: _pick_random_transition no longer has a silent Crossfade
    # fallback. If it fails while Crossfade is deactivated, the failure must
    # propagate to create_transition (which returns None) — nothing is
    # instantiated, and certainly not a deactivated Crossfade.
    from rendering.transition_factory import TransitionFactory

    calls: list[str] = []

    def _fake_create_by_type(self, ttype, settings, duration_ms, easing):
        calls.append(ttype)
        return SimpleNamespace(set_resource_manager=lambda rm: None)

    def _boom(self, settings):
        raise RuntimeError("forced pick failure")

    monkeypatch.setattr(TransitionFactory, "_create_by_type", _fake_create_by_type)
    monkeypatch.setattr(TransitionFactory, "_pick_random_transition", _boom)

    transitions = {
        "random_always": True,
        "pool": {name: True for name in get_transition_setting_names()},
        "activation": {"Crossfade": False},
    }
    settings = _StubFactorySettings(transitions, hw=True)
    factory = TransitionFactory(settings)

    result = factory.create_transition()

    assert result is None
    assert calls == []  # nothing instantiated, no Crossfade bypass


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
