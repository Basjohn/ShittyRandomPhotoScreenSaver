"""A-12 (in AC-01): a Studio-owned Visualizer mode's Settings body builds no hidden value-owner QWidgets.

Every mode is edited in its Studio. Its Settings body is the preset row (with OPEN STUDIO), the 3D Detail row where
the mode has one, and one sentence; the section-lazy cache ``_<prefix>_lazy_values`` is the only owner of the body's
values, technical (audio analysis) values included. Drives the real SettingsDialog, never shown, on a test-owned
profile with image sources configured. Values are derived from the canonical registries, never pinned.
"""
from __future__ import annotations

from copy import deepcopy

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QWidget

from core.animation import AnimationManager
from core.settings.capability_activation import set_widget_family_activated
from core.settings.default_contract import require_canonical_default
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import build_visualizer_mode_activation, iter_visualizer_mode_descriptors
from core.settings.visualizer_mode_settings import require_mode_settings
from core.settings.visualizer_presets import get_custom_preset_index

pytestmark = pytest.mark.qt

MODES = tuple(d.mode_id for d in iter_visualizer_mode_descriptors())


@pytest.fixture
def manager(tmp_path):
    QApplication.instance() or QApplication([])
    manager = SettingsManager(application="studio_owned_values", storage_base_dir=tmp_path)
    widgets = manager.get("widgets", {})
    widgets["spotify_visualizer"] = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    for family in ("media", "visualizers"):
        set_widget_family_activated(widgets, family, True)
    manager.set("widgets", widgets)
    manager.set("sources.folders", [str(tmp_path)])
    yield manager
    assert manager.flush(timeout=5.0)


def _use_mode(manager, mode):
    widgets = manager.get("widgets", {})
    section = dict(widgets["spotify_visualizer"])
    section.update({"enabled": True, "visualizers_enabled": True, "mode": mode,
                    "mode_activation": build_visualizer_mode_activation([mode]),
                    f"preset_{mode}": get_custom_preset_index(mode)})
    widgets["spotify_visualizer"] = section
    manager.set("widgets", widgets)


def _open_mode(manager, mode):
    from ui.settings_dialog import SettingsDialog
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    dialog._switch_tab(dialog._tab_index_for_key("visualizers"), animate=False)
    tab = dialog.visualizers_tab
    tab._select_mode_page(mode)
    QCoreApplication.processEvents()
    return dialog, tab


def _destroy(dialog):
    dialog.close()
    QCoreApplication.processEvents()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _technical_defs(mode):
    return {control.key: control for control in require_mode_settings(mode).technical_controls()}


def _other_value(control, value):
    """A legal value of the technical control other than ``value``."""
    from core.settings.visualizer_mode_settings import Choice, Toggle
    if isinstance(control, Toggle):
        return not bool(value)
    if isinstance(control, Choice):
        return next(option for option in control.choices if option != value)
    if control.integer:
        return int(control.low) if int(value) != int(control.low) else int(control.high)
    return float(control.low) if float(value) != float(control.low) else float(control.high)


@pytest.mark.parametrize("mode", MODES)
def test_studio_owned_body_builds_no_hidden_value_owners(manager, mode):
    from ui.widgets.continuous_border import BucketToggle
    _use_mode(manager, mode)
    dialog, tab = _open_mode(manager, mode)
    spec = require_mode_settings(mode)
    body = getattr(tab, f"_{spec.prefix}_settings_container")
    assert body.findChild(QWidget, f"{mode}_studio_owned_values") is None
    assert body.findChildren(BucketToggle) == []
    assert not hasattr(tab, "_per_mode_technical_controls")
    for suffix in ("normal", "advanced_host", "advanced"):
        assert not hasattr(tab, f"_{spec.prefix}_{suffix}"), suffix
    # The shared Bar Appearance / Rainbow rows are never placed into a mode body.
    for accessory in (tab._base_appearance_group, tab._rainbow_controls_container):
        assert not body.isAncestorOf(accessory)
        assert not accessory.isVisibleTo(tab)
    _destroy(dialog)


@pytest.mark.parametrize("mode", MODES)
def test_the_lazy_cache_round_trips_every_body_and_technical_value(manager, mode):
    from ui.tabs.media.spec_mode_builder import body_keys
    _use_mode(manager, mode)
    dialog, tab = _open_mode(manager, mode)
    cache = getattr(tab, f"_{require_mode_settings(mode).prefix}_lazy_values")
    technical = _technical_defs(mode)
    assert set(body_keys(mode)) | set(technical) <= set(cache)
    edited = {key: _other_value(defn, cache[key]) for key, defn in technical.items()}
    cache.update(edited)
    tab._save_settings_now()
    stored = manager.get("widgets")["spotify_visualizer"]
    for key, value in edited.items():
        assert stored[key] == pytest.approx(value), key
    held = deepcopy({key: cache[key] for key in (*body_keys(mode), *technical)})
    _destroy(dialog)

    dialog, tab = _open_mode(manager, mode)
    reopened = getattr(tab, f"_{require_mode_settings(mode).prefix}_lazy_values")
    for key, value in held.items():
        assert reopened[key] == value, key
    _destroy(dialog)
