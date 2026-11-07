"""AC-18: each mode's audio-analysis (technical) controls are ordinary entries of its spec.

One declaration (``core/settings/visualizer_mode_settings.audio_analysis_entries``) gives Settings' value cache, the
Studio and the settings model one admission, and the preset guard sees every technical key. The out-of-range values
here are test-owned and derived from the canonical defaults (never a pinned range), so the same test runs on the
code before the fold, where the three surfaces disagreed. Settings is the real SettingsDialog, never shown, with
``StyledPopup.exec`` patched.
"""
from __future__ import annotations

from copy import deepcopy

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from core.animation import AnimationManager
from core.settings.capability_activation import set_widget_family_activated
from core.settings.default_contract import require_canonical_default
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import (
    build_visualizer_mode_activation, get_owned_mode_setting_keys, get_visualizer_mode_descriptor,
    iter_visualizer_mode_descriptors,
)
from core.settings.visualizer_presets import get_custom_preset_index, preset_artwork_keys
from core.settings.visualizer_settings_contract import SPECIAL_PER_MODE_KEYS

pytestmark = pytest.mark.qt

MODES = tuple(d.mode_id for d in iter_visualizer_mode_descriptors() if d.technical_controls)


def _technical_keys(mode):
    """Every technical key the mode owns: the registry's suffix map plus its transient mix keys."""
    keys = list(get_owned_mode_setting_keys(mode, "technical").values())
    keys += [key for owner, _suffix, key, _coerce in SPECIAL_PER_MODE_KEYS if owner == mode]
    return keys


def _offered(mode, suffix):
    return suffix in get_owned_mode_setting_keys(mode, "technical") and \
        suffix not in get_visualizer_mode_descriptor(mode).technical_hidden_suffixes


@pytest.mark.parametrize("mode", MODES)
def test_every_technical_key_is_a_control_of_its_mode_spec(mode):
    from core.settings.visualizer_mode_settings import require_mode_settings
    spec = require_mode_settings(mode)
    for key in _technical_keys(mode):
        assert spec.control(key).key == key


@pytest.mark.parametrize("mode", MODES)
def test_the_preset_guard_and_repair_fill_cover_every_technical_key(mode):
    missing = set(_technical_keys(mode)) - set(preset_artwork_keys(mode))
    assert not missing, f"{mode}: the curated-preset guard cannot see {sorted(missing)}"


# ------------------------------------------------------------------------- one admission, three surfaces
def _wild(mode):
    """Test-owned values a stored profile or imported SST could hold: far above any bar count, a floor a tenth of
    the canonical one, a gain far above unity. Derived from the canonical defaults only."""
    default = lambda suffix: require_canonical_default(f"widgets.spotify_visualizer.{mode}_{suffix}")  # noqa: E731
    wanted = {"bar_count": int(default("bar_count")) * 20,
              "manual_floor": float(default("manual_floor")) / 10.0,
              "input_gain": float(default("input_gain")) * 7.0}
    return {f"{mode}_{suffix}": value for suffix, value in wanted.items() if _offered(mode, suffix)}


@pytest.fixture
def manager(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.styled_popup import StyledPopup
    monkeypatch.setattr(StyledPopup, "exec", lambda popup: setattr(popup, "_result_value", None))
    manager = SettingsManager(application="audio_analysis_fold", storage_base_dir=tmp_path)
    widgets = manager.get("widgets", {})
    widgets["spotify_visualizer"] = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    for family in ("media", "visualizers"):
        set_widget_family_activated(widgets, family, True)
    manager.set("widgets", widgets)
    manager.set("sources.folders", [str(tmp_path)])
    yield manager
    assert manager.flush(timeout=5.0)


def _settings_cache(manager, mode, wild):
    """What the real Settings dialog's mode body holds for a profile storing ``wild`` (Custom preset)."""
    from core.settings.visualizer_mode_settings import mode_settings
    from ui.settings_dialog import SettingsDialog
    widgets = manager.get("widgets", {})
    section = dict(widgets["spotify_visualizer"])
    section.update({"enabled": True, "visualizers_enabled": True, "mode": mode,
                    "mode_activation": build_visualizer_mode_activation([mode]),
                    f"preset_{mode}": get_custom_preset_index(mode), **wild})
    widgets["spotify_visualizer"] = section
    manager.set("widgets", widgets)
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    try:
        dialog._switch_tab(dialog._tab_index_for_key("visualizers"), animate=False)
        tab = dialog.visualizers_tab
        tab._select_mode_page(mode)
        QCoreApplication.processEvents()
        prefix = mode_settings(mode).prefix if mode_settings(mode) is not None else mode
        cache = getattr(tab, f"_{prefix}_lazy_values")
        return {key: cache[key] for key in wild}
    finally:
        dialog.close()
        QCoreApplication.processEvents()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QCoreApplication.processEvents()


@pytest.mark.parametrize("mode", [m for m in MODES if _wild(m)])
def test_settings_the_studio_and_the_model_admit_a_technical_value_identically(manager, mode):
    from core.settings.models import SpotifyVisualizerSettings
    from ui.studio.registry import create_adapter
    wild = _wild(mode)
    model = SpotifyVisualizerSettings.from_mapping({"mode": mode, **wild}, apply_preset_overlay=False)
    schema = create_adapter(mode).schema()
    for key, value in wild.items():
        default = require_canonical_default(f"widgets.spotify_visualizer.{key}")
        studio = schema.admit(key, value, default)
        assert getattr(model, key) == studio, f"{key}: the model holds {getattr(model, key)!r}, the Studio {studio!r}"
    settings = _settings_cache(manager, mode, wild)
    for key in wild:
        assert settings[key] == getattr(model, key), \
            f"{key}: Settings holds {settings[key]!r}, the model {getattr(model, key)!r}"
