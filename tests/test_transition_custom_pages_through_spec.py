"""AC-20: the Particle, Blinds and Burn pages take their ranges from the transition spec, and the resolver admits
through it.

* A canonical default runs as authored (Particle's radius default used to be raised by a hidden resolver floor).
* For every numeric field of the three pages, the Settings control's range equals the range the request resolver
  admits, probed from the resolver itself with test-owned out-of-range values (no range is pinned here).
* Saving the Particle page keeps the fields it never shows as stored (a stored ``overlap`` that is not the canonical
  default survives a hydrate and save).

Settings is the real SettingsDialog, never shown, with ``StyledPopup.exec`` patched.
"""
from __future__ import annotations

import random

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from core.animation import AnimationManager
from core.settings.default_contract import require_canonical_default
from core.settings.settings_manager import SettingsManager

pytestmark = pytest.mark.qt

_HUGE = 1.0e6


def _resolved(name, section, field, value):
    from rendering.quick.transitions import parameter_resolution as resolution
    resolver = {"particle": resolution._resolve_particle, "burn": resolution._resolve_burn,
                "blinds": resolution._resolve_blinds}[name]
    # A fixed Particle mode: Random would draw the swirl order itself.
    config = {"mode": "Swirl", field: value} if name == "particle" else {field: value}
    return resolver({name: config}, random.Random(7)).parameter_dict()[section]


def test_particles_canonical_radius_runs_as_authored():
    from rendering.quick.transitions.parameter_resolution import _resolve_particle
    resolved = _resolve_particle({}, random.Random(7)).parameter_dict()["particle_radius"]
    assert resolved == float(require_canonical_default("transitions.particle.particle_radius"))


@pytest.fixture
def transitions_tab(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.settings_dialog import SettingsDialog
    from ui.styled_popup import StyledPopup
    monkeypatch.setattr(StyledPopup, "exec", lambda popup: setattr(popup, "_result_value", None))
    manager = SettingsManager(application="transition_custom_pages", storage_base_dir=tmp_path)
    manager.set("sources.folders", [str(tmp_path)])
    activation = dict(manager.get("transitions.activation") or {})
    activation.update({"Particle": True, "Blinds": True, "Burn": True})
    manager.set("transitions.activation", activation)
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    tab = dialog._get_tab_instance("transitions")
    for name in ("Particle", "Blinds", "Burn"):
        tab._ensure_transition_page(name)
    yield manager, tab
    dialog.close()
    QCoreApplication.processEvents()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()
    assert manager.flush(timeout=5.0)


def test_every_custom_page_number_offers_exactly_the_range_the_resolver_admits(transitions_tab):
    _manager, tab = transitions_tab
    # (page, field, Settings widget, widget units per stored unit)
    numbers = [
        ("particle", "particle_radius", tab.particle_radius_spin, 1),
        ("particle", "gloss_size", tab.particle_gloss_spin, 1),
        ("particle", "swirl_turns", tab.particle_swirl_turns_spin, 1),
        ("particle", "light_direction", tab.particle_light_combo, 1),
        ("particle", "swirl_order", tab.particle_swirl_order_combo, 1),
        ("burn", "jaggedness", tab.burn_jaggedness_slider, 100),
        ("burn", "glow_intensity", tab.burn_glow_intensity_slider, 100),
        ("burn", "char_width", tab.burn_char_width_slider, 100),
        ("burn", "smoke_density", tab.burn_smoke_density_slider, 100),
        ("burn", "ash_density", tab.burn_ash_density_slider, 100),
    ]
    for page, field, widget, scale in numbers:
        if hasattr(widget, "count"):            # an index list: its positions are the range
            offered = (0, widget.count() - 1)
        else:
            offered = (widget.minimum() / scale, widget.maximum() / scale)
        admitted = (_resolved(page, field, field, -_HUGE), _resolved(page, field, field, _HUGE))
        assert offered == pytest.approx(admitted), f"{page}.{field}: Settings offers {offered}, resolver admits {admitted}"
    # Blinds' Edge Softness: the slider's ends are exactly where the resolver's feather stops changing.
    slider = tab.blinds_feather_slider
    feather = lambda value: _resolved("blinds", "feather", "feather", value)  # noqa: E731
    assert feather(slider.minimum()) == feather(-_HUGE)
    assert feather(slider.maximum()) == feather(_HUGE) > feather(slider.maximum() - 1)


def test_saving_the_particle_page_keeps_the_fields_it_never_shows(transitions_tab):
    manager, tab = transitions_tab
    canonical = require_canonical_default("transitions.particle")
    stored = dict(manager.get("transitions.particle") or canonical)
    stored["overlap"] = float(canonical["overlap"]) / 2.0        # test-owned: anything but the canonical value
    stored["swirl_strength"] = float(canonical["swirl_strength"]) / 2.0
    manager.set("transitions.particle", stored)
    tab.load_from_settings()
    tab._save_settings()
    tab.flush_pending_changes() if hasattr(tab, "flush_pending_changes") else None
    saved = manager.get("transitions.particle")
    assert saved["overlap"] == pytest.approx(stored["overlap"])
    assert saved["swirl_strength"] == pytest.approx(stored["swirl_strength"])
