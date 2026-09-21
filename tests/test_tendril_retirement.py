"""Permanent Tendril Reveal retirement and persisted-state sanitation gates."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from core.settings.capability_activation import normalize_transition_capability_state
from core.settings.defaults import get_default_settings
from rendering.quick.transitions.implementation_registry import (
    canonical_enabled_transition_ids,
    resolve_quick_transition_renderer,
)
from rendering.transition_registry import (
    get_transition_descriptor,
    get_transition_descriptor_for_runtime_identity,
    is_transition_available,
)

ROOT = Path(__file__).resolve().parents[1]


def test_tendril_has_no_product_registry_runtime_or_source_admission():
    assert get_transition_descriptor("Tendril Reveal") is None
    assert get_transition_descriptor_for_runtime_identity("tendril_reveal") is None
    assert not is_transition_available("Tendril Reveal")
    with pytest.raises(ValueError, match="unknown canonical transition"):
        canonical_enabled_transition_ids(("Tendril Reveal",))
    with pytest.raises(ValueError, match="unknown canonical transition"):
        resolve_quick_transition_renderer(
            "tendril_reveal", enabled_transition_ids=frozenset({"tendril_reveal"})
        )
    assert not (ROOT / "rendering/quick/transitions/implementations/tendril_reveal.py").exists()
    assert not (ROOT / "rendering/gl_programs/tendril_reveal_program.py").exists()


def test_defaults_have_no_tendril_capability_or_settings_section():
    transitions = get_default_settings()["transitions"]
    assert "Tendril Reveal" not in transitions["activation"]
    assert "Tendril Reveal" not in transitions["pool"]
    assert "Tendril Reveal" not in transitions["durations"]
    assert "tendril_reveal" not in transitions


def test_old_tendril_state_is_generically_pruned_by_canonical_normalization():
    transitions = deepcopy(get_default_settings()["transitions"]
    )
    transitions["activation"]["Tendril Reveal"] = True
    transitions["pool"]["Tendril Reveal"] = True
    transitions["durations"]["Tendril Reveal"] = 9999
    transitions["tendril_reveal"] = {"detail": 2.0}
    transitions["type"] = "Tendril Reveal"
    transitions["random_choice"] = "Tendril Reveal"
    transitions["last_random_choice"] = "Tendril Reveal"

    assert normalize_transition_capability_state(transitions) is True
    assert "Tendril Reveal" not in transitions["activation"]
    assert "Tendril Reveal" not in transitions["pool"]
    assert "Tendril Reveal" not in transitions["durations"]
    assert "tendril_reveal" not in transitions
    assert transitions["type"] != "Tendril Reveal"
    assert "random_choice" not in transitions
    assert "last_random_choice" not in transitions
