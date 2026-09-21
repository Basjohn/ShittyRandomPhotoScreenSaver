"""Pending-removal admission and Settings affordances for Tendril Reveal."""

from __future__ import annotations

from copy import deepcopy
import json
import subprocess
import sys

from core.settings import capability_activation as capabilities
from rendering.quick.transitions.implementation_registry import (
    canonical_enabled_transition_ids,
    resolve_quick_transition_renderer,
)
from rendering.quick.transitions.request_resolution import resolve_quick_transition_spec
from rendering.transition_registry import (
    is_transition_available,
    transition_unavailability_reason,
)
from ui.tabs.transitions_tab import TransitionsTab


def test_tendril_descriptor_quarantine_excludes_saved_activation_and_random_admission(
    settings_manager,
) -> None:
    transitions = deepcopy(settings_manager.get("transitions", {}))
    transitions["activation"]["Tendril Reveal"] = True
    transitions["pool"]["Tendril Reveal"] = True
    transitions["type"] = "Tendril Reveal"
    transitions["random_always"] = True
    transitions["random_choice"] = "Tendril Reveal"
    settings_manager.set("transitions", transitions)

    assert not is_transition_available("Tendril Reveal")
    assert "Pending removal" in transition_unavailability_reason("Tendril Reveal")
    assert not capabilities.is_transition_activated(transitions, "Tendril Reveal")
    assert resolve_quick_transition_spec(settings_manager) is None
    assert "tendril_reveal" not in canonical_enabled_transition_ids(("Tendril Reveal",))
    assert resolve_quick_transition_renderer(
        "tendril_reveal", enabled_transition_ids=frozenset({"tendril_reveal"})
    ) is None

    transitions["random_always"] = False
    settings_manager.set("transitions", transitions)
    assert resolve_quick_transition_spec(settings_manager).transition_id != "tendril_reveal"


def test_quarantined_tendril_cannot_trigger_its_lazy_renderer_import() -> None:
    probe = """
import json
import sys
from rendering.quick.transitions.implementation_registry import resolve_quick_transition_renderer
result = resolve_quick_transition_renderer('tendril_reveal', enabled_transition_ids=frozenset({'tendril_reveal'}))
print(json.dumps({'resolved': result is not None, 'imported': 'rendering.quick.transitions.implementations.tendril_reveal' in sys.modules}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, check=True, text=True
    )
    assert json.loads(completed.stdout) == {"resolved": False, "imported": False}


def test_tendril_is_visible_but_inert_in_setup_and_selection(qapp, settings_manager, qtbot) -> None:
    transitions = deepcopy(settings_manager.get("transitions", {}))
    transitions["activation"]["Tendril Reveal"] = True
    transitions["pool"]["Tendril Reveal"] = True
    settings_manager.set("transitions", transitions)
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)

    activation = tab._activation_checkboxes["Tendril Reveal"]
    pool = tab._pool_checkboxes["Tendril Reveal"]
    pill = tab._nav_buttons["Tendril Reveal"]
    assert not activation.isEnabled()
    assert not pool.isEnabled()
    assert not pill.isHidden() and not pill.isEnabled()
    assert "Pending removal" in pill.toolTip()
    assert tab._admit_nav_key("Tendril Reveal") == "__setup__"
    assert not hasattr(tab, "tendril_reveal_group")
