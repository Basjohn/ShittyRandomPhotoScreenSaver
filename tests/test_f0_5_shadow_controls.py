"""F0.5 gates: canonical shadow cleanup + Widgets → General shadow controls.

Covers the retirement of the hidden ``shadowtuning.json`` authority's canonical
consequences (model/default cleanup and the retired ``offset`` pair), plus the
new Widgets → General shadow controls: darkness/blur/extra-offset canonical
round-trip, the 3x3 direction picker, and the mandatory save-preservation fix.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QCheckBox, QSpinBox, QVBoxLayout, QWidget

from core.settings.defaults import CANONICAL_DEFAULTS
from core.settings.models._core import ShadowSettings
from core.settings.settings_manager import SettingsManager
from core.settings.shadow_direction import ShadowDirection
from ui.tabs import widgets_tab_defaults as wtd


# --------------------------------------------------------------------------- #
# Sidecar retirement is complete                                              #
# --------------------------------------------------------------------------- #


def test_shadow_tuning_sidecar_module_is_gone() -> None:
    with pytest.raises(ModuleNotFoundError):
        __import__("core.settings.shadow_tuning")


def test_no_current_source_reads_the_retired_sidecar() -> None:
    root = Path(__file__).resolve().parents[1]
    for rel in (
        "widgets/base_overlay_widget.py",
        "widgets/shadow_utils.py",
        "rendering/quick/widgets/clock.py",
        "rendering/quick/widgets/weather.py",
        "widgets/spotify_visualizer/card_surface.py",
        "widgets/spotify_visualizer/renderers/spectrum.py",
        "core/settings/storage_paths.py",
    ):
        if not (root / rel).exists():
            # Retired QWidget-era files were deleted by the Quick cutover; a file
            # that no longer exists trivially cannot read the retired sidecar.
            continue
        source = (root / rel).read_text(encoding="utf-8")
        # No import of the retired sidecar and no exported-dict/alias dependency.
        assert "import" not in source or "core.settings.shadow_tuning" not in source, rel
        for banned in (
            "SHADOW_TUNING",
            "PAINTED_FRAME_SHADOW_TUNING",
            "load_shadow_tuning",
        ):
            assert banned not in source, f"{rel}: {banned}"


def test_no_production_copy_of_retired_profile_behavior_remains() -> None:
    root = Path(__file__).resolve().parents[1]
    retired_markers = {
        "widgets/base_overlay_widget.py": (
            "painted_frame_shadow",
            "uses_shared_painted_frame_shadow_cache",
        ),
        "rendering/widget_manager.py": (
            "painted_frame_shadow",
            "_prepare_overlay_frame_shadow_before_reveal",
        ),
        "widgets/shadow_utils.py": (
            "shadowtuning.json",
            "TEXT_SHADOW_",
            "TEXT_LARGE_SHADOW_",
            "HEADER_SHADOW_",
            "_resolve_text_shadow_params",
            "draw_text_rect_shadow_only",
            "draw_rich_text_shadow_only",
            "make_alpha_shadow_pixmap",
            "draw_pixmap_drop_shadow",
            "draw_rounded_rect_with_shadow",
        ),
        "rendering/quick/widgets/weather.py": (
            "shadowtuning.json",
            "_scaled_shadow_offsets",
            "_shadow_pixmap",
            "make_alpha_shadow_pixmap",
        ),
        "widgets/spotify_visualizer_widget.py": (
            "painted_frame_shadow",
            "card_paint",
        ),
        "widgets/spotify_visualizer/card_surface.py": (
            "painted_frame_shadow",
            "shadowtuning.json",
        ),
    }

    for rel, markers in retired_markers.items():
        if not (root / rel).exists():
            # Retired QWidget-era files were deleted by the Quick cutover; a file
            # that no longer exists cannot carry a copy of the retired behaviour.
            continue
        source = (root / rel).read_text(encoding="utf-8")
        for marker in markers:
            assert marker not in source, f"{rel}: {marker}"


# --------------------------------------------------------------------------- #
# ShadowSettings model + canonical defaults                                   #
# --------------------------------------------------------------------------- #


def test_shadow_settings_defaults_match_canonical() -> None:
    s = ShadowSettings()
    assert s.blur_radius == 18
    assert s.frame_opacity == pytest.approx(0.77)
    assert s.text_opacity == pytest.approx(0.33)
    assert s.direction == "SE"
    assert s.frame_extra_offset == 0
    assert s.text_extra_offset == 0
    assert not hasattr(s, "offset")


def test_shadow_settings_round_trip_has_extras_and_no_offset() -> None:
    payload = ShadowSettings().to_dict()
    assert payload["widgets.shadows.frame_extra_offset"] == 0
    assert payload["widgets.shadows.text_extra_offset"] == 0
    assert payload["widgets.shadows.direction"] == "SE"
    assert "widgets.shadows.offset" not in payload


def test_canonical_defaults_shadows_are_clean() -> None:
    shadows = CANONICAL_DEFAULTS["widgets"]["shadows"]
    assert shadows["direction"] == "SE"
    assert shadows["frame_extra_offset"] == 0
    assert shadows["text_extra_offset"] == 0
    assert "offset" not in shadows
    assert shadows["blur_radius"] == 18
    assert shadows["frame_opacity"] == pytest.approx(0.77)
    assert shadows["text_opacity"] == pytest.approx(0.33)


def test_retired_offset_pair_is_stripped_on_cleanup(tmp_path: Path) -> None:
    manager = SettingsManager(
        organization="TestOrg",
        application=f"TestApp_{uuid.uuid4().hex}",
        storage_base_dir=tmp_path / uuid.uuid4().hex,
    )
    manager.set("widgets", {"shadows": {"enabled": True, "offset": [4, 4]}})
    assert manager.get("widgets.shadows.offset") == [4, 4]

    removed = manager.cleanup_obsolete_settings()

    assert "widgets.shadows.offset" in removed
    assert manager.get("widgets.shadows.offset", "missing") == "missing"
    # Sibling shadow keys are preserved.
    assert manager.get("widgets.shadows.enabled") is True


# --------------------------------------------------------------------------- #
# Widgets → General controls                                                  #
# --------------------------------------------------------------------------- #


class _FakeSettings:
    def __init__(self, widgets: dict) -> None:
        self._widgets = widgets

    def get(self, key, default=None):
        if key == "widgets":
            return self._widgets
        return default


def _fake_general_tab(existing_shadows: dict) -> SimpleNamespace:
    tab = SimpleNamespace()
    tab._settings = _FakeSettings({"shadows": dict(existing_shadows)})
    tab._save_calls = 0
    tab._save_settings = lambda: setattr(tab, "_save_calls", tab._save_calls + 1)
    tab.widget_shadows_enabled = QCheckBox()
    tab.widget_text_shadows_enabled = QCheckBox()
    tab.widget_header_shadows_enabled = QCheckBox()
    tab.widget_stacking_enabled = QCheckBox()
    for name, value in (
        ("widget_shadow_darkness_spin", 77),
        ("widget_shadow_blur_spin", 18),
        ("widget_shadow_extra_offset_spin", 0),
        ("widget_text_shadow_darkness_spin", 33),
        ("widget_text_shadow_extra_offset_spin", 0),
    ):
        spin = QSpinBox()
        spin.setRange(0, 100)
        spin.setValue(value)
        setattr(tab, name, spin)
    tab._global_card_border_width = 3
    tab._widget_default = lambda *_a, **_k: 3
    tab._selected_shadow_direction = ShadowDirection.SE
    return tab


@pytest.mark.qt
def test_general_save_merges_and_preserves_canonical_and_future_keys(qt_app) -> None:
    tab = _fake_general_tab(
        {
            "enabled": True,
            "text_enabled": True,
            "header_enabled": True,
            "color": [0, 0, 0, 255],
            "direction": "NW",
            "frame_opacity": 0.77,
            "blur_radius": 18,
            "future_unknown_key": 7,
            "offset": [4, 4],
        }
    )
    # User edits: turn drop shadows off, set darkness 50%, extra offset 5, pick SE.
    tab.widget_shadows_enabled.setChecked(False)
    tab.widget_text_shadows_enabled.setChecked(True)
    tab.widget_header_shadows_enabled.setChecked(True)
    tab.widget_shadow_darkness_spin.setValue(50)
    tab.widget_shadow_extra_offset_spin.setValue(5)
    tab.widget_text_shadow_extra_offset_spin.setValue(2)
    tab._selected_shadow_direction = ShadowDirection.SE

    shadows_config, _global = wtd.save_defaults_settings(tab)

    # Edited keys land.
    assert shadows_config["enabled"] is False
    assert shadows_config["frame_opacity"] == pytest.approx(0.5)
    assert shadows_config["frame_extra_offset"] == 5
    assert shadows_config["text_extra_offset"] == 2
    assert shadows_config["direction"] == "SE"
    # Unedited canonical and unknown-future keys are preserved.
    assert shadows_config["color"] == [0, 0, 0, 255]
    assert shadows_config["future_unknown_key"] == 7
    # The retired magnitude pair is never re-persisted.
    assert "offset" not in shadows_config


@pytest.mark.qt
def test_direction_picker_has_eight_cells_inert_center_and_updates_selection(qt_app) -> None:
    tab = SimpleNamespace()
    tab._save_calls = 0
    tab._save_settings = lambda: setattr(tab, "_save_calls", tab._save_calls + 1)
    host = QWidget()
    layout = QVBoxLayout(host)
    try:
        wtd._build_shadow_direction_picker(tab, layout, ShadowDirection.SE)

        buttons = tab._shadow_direction_buttons
        assert set(buttons) == set(ShadowDirection)  # all eight, center is not a button
        assert len(buttons) == 8
        assert buttons[ShadowDirection.SE].isChecked() is True
        assert tab._selected_shadow_direction is ShadowDirection.SE

        # Selecting NW updates state, checks exactly one cell, and saves.
        wtd._on_shadow_direction_selected(tab, ShadowDirection.NW)
        assert tab._selected_shadow_direction is ShadowDirection.NW
        assert buttons[ShadowDirection.NW].isChecked() is True
        assert buttons[ShadowDirection.SE].isChecked() is False
        assert sum(1 for b in buttons.values() if b.isChecked()) == 1
        assert tab._save_calls == 1
    finally:
        host.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_direction_picker_malformed_stored_token_falls_back_to_se(qt_app) -> None:
    from core.settings.shadow_direction import resolve_shadow_direction

    tab = SimpleNamespace()
    tab._save_settings = lambda: None
    host = QWidget()
    layout = QVBoxLayout(host)
    try:
        wtd._build_shadow_direction_picker(
            tab, layout, resolve_shadow_direction("not-a-direction")
        )
        assert tab._selected_shadow_direction is ShadowDirection.SE
        assert tab._shadow_direction_buttons[ShadowDirection.SE].isChecked() is True
    finally:
        host.deleteLater()
        qt_app.processEvents()
