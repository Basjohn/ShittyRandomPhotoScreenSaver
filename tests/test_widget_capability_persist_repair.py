"""Durable persisted Media->Visualizers dependency repair at load (E2 §3).

These exercise the real SettingsManager load/init normalization boundary (not
``normalize_widget_capability_state`` in isolation): an invalid persisted state
(``media=False`` with ``visualizers`` still activated, or its key missing) must be
canonically repaired AND persisted so a later Media reactivation cannot silently
re-enable Visualizers.
"""
from __future__ import annotations

import uuid

import pytest

from core.settings import SettingsManager


def _new_app() -> str:
    return f"CapRepairTest_{uuid.uuid4().hex}"


def _seed_then_reload(tmp_path, seed_family_activation: dict):
    """Seed an invalid widgets state, then construct a fresh manager on the same
    store so the real load-time normalization boundary runs. Returns the reloaded
    manager."""
    storage_base = tmp_path / "settings"
    app = _new_app()
    seeder = SettingsManager(organization="Test", application=app, storage_base_dir=storage_base)
    seeder.set("widgets", {"family_activation": dict(seed_family_activation)})
    seeder.save()
    # A second construction re-runs __init__ -> _normalize_persisted_widget_capability_state.
    reloaded = SettingsManager(organization="Test", application=app, storage_base_dir=storage_base)
    return reloaded


def _family_activation(manager) -> dict:
    widgets = manager.get("widgets", {}) or {}
    fa = widgets.get("family_activation", {})
    return fa if isinstance(fa, dict) else {}


def test_load_repairs_media_off_visualizers_on(tmp_path):
    # A: persisted media=False, visualizers=True -> repaired durably to False.
    mgr = _seed_then_reload(tmp_path, {"media": False, "visualizers": True})
    fa = _family_activation(mgr)
    assert fa.get("media") is False
    assert fa.get("visualizers") is False


def test_load_repairs_media_off_visualizers_key_missing(tmp_path):
    # B: migrated/missing visualizers key with media=False. Defaults merge fills
    # visualizers=True, then the dependency repair forces it False durably.
    mgr = _seed_then_reload(tmp_path, {"media": False})
    fa = _family_activation(mgr)
    assert fa.get("media") is False
    assert fa.get("visualizers") is False


def test_reactivating_media_does_not_reactivate_visualizers(tmp_path):
    # C: after the durable repair, an external Media reactivation must NOT auto
    # re-enable Visualizers.
    mgr = _seed_then_reload(tmp_path, {"media": False, "visualizers": True})
    assert _family_activation(mgr).get("visualizers") is False

    widgets = dict(mgr.get("widgets", {}) or {})
    fa = dict(widgets.get("family_activation", {}))
    fa["media"] = True  # external mutation reactivates Media only
    widgets["family_activation"] = fa
    mgr.set("widgets", widgets)

    after = _family_activation(mgr)
    assert after.get("media") is True
    assert after.get("visualizers") is False  # stays off until explicitly activated


def test_valid_state_is_not_disturbed(tmp_path):
    # Negative control: a fully-activated state is untouched by the repair.
    mgr = _seed_then_reload(tmp_path, {"media": True, "visualizers": True})
    fa = _family_activation(mgr)
    assert fa.get("media") is True
    assert fa.get("visualizers") is True
