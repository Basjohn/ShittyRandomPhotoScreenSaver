"""Focused Settings-only admission tests for Guided Setup selection pages."""

from __future__ import annotations

from copy import deepcopy

import pytest
from PySide6.QtCore import Qt

from core.settings.capability_activation import is_widget_family_effective
from ui.onboarding import state
from ui.onboarding.selection_pages import (
    ReadyPage,
    ThemePage,
    TransitionsPage,
    VisualizerPage,
    WidgetsPage,
)


class _Settings:
    def __init__(self) -> None:
        from core.settings.defaults import get_default_settings
        self.values = deepcopy(get_default_settings())
        self.writes: list[str] = []

    def get(self, key: str, default=None):
        value = self.values
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return deepcopy(default)
            value = value[part]
        return deepcopy(value)

    def set(self, key: str, value) -> None:
        self.writes.append(key)
        target = self.values
        parts = key.split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = deepcopy(value)


@pytest.fixture
def settings() -> _Settings:
    return _Settings()


def test_selection_page_hydration_is_read_only(qapp, settings) -> None:
    """Opening the wizard must not normalize or select on the user's behalf."""

    pages = [ThemePage(settings), WidgetsPage(settings), VisualizerPage(settings), TransitionsPage(settings)]
    try:
        for page in pages:
            page.refresh()
        assert settings.writes == []
    finally:
        for page in pages:
            page.deleteLater()


def test_widget_member_aliases_write_media_and_obey_family_dependencies(qapp, settings) -> None:
    page = WidgetsPage(settings)
    try:
        page._member("spotify_volume", False)
        widgets = settings.get("widgets")
        assert widgets["media"]["spotify_volume_enabled"] is False
        assert "spotify_volume" not in widgets
        assert settings.writes == ["widgets"]

        settings.writes.clear()
        page._member("mute_button", True)
        widgets = settings.get("widgets")
        assert widgets["media"]["mute_button_enabled"] is True
        assert widgets["family_activation"]["media"] is True
        assert settings.writes == ["widgets"]

        # Visualizers cannot promote their Media prerequisite implicitly.
        widgets["family_activation"]["media"] = False
        widgets["family_activation"]["visualizers"] = False
        settings.values["widgets"] = widgets
        page._member("spotify_visualizer", True)
        widgets = settings.get("widgets")
        assert widgets["spotify_visualizer"]["enabled"] is True
        assert is_widget_family_effective(widgets, "visualizers") is False

        widgets["family_activation"]["media"] = True
        settings.values["widgets"] = widgets
        page._member("spotify_visualizer", True)
        assert is_widget_family_effective(settings.get("widgets"), "visualizers") is True
    finally:
        page.deleteLater()


def test_current_summary_counts_effective_families_and_media_aliases(settings, monkeypatch) -> None:
    monkeypatch.setattr(state, "saved_account_states", lambda _settings: {"steam": False, "gmail": False})
    widgets = settings.values["widgets"]
    for family in widgets["family_activation"]:
        widgets["family_activation"][family] = False
    widgets["family_activation"]["media"] = True
    widgets["media"]["enabled"] = False
    widgets["media"]["spotify_volume_enabled"] = True
    widgets["media"]["mute_button_enabled"] = True

    summary = state.current_setup_summary(settings)
    assert summary["families"] == 1

    widgets["spotify_visualizer"]["enabled"] = True
    widgets["family_activation"]["visualizers"] = True
    widgets["family_activation"]["media"] = False
    # Visualizer is configured but its Media family prerequisite is disabled.
    assert state.current_setup_summary(settings)["visualizer_modes"] == ()


def test_visualizer_selection_offers_standard_sphere_and_can_enable_it(qapp, settings) -> None:
    widgets = settings.values["widgets"]
    widgets["family_activation"]["media"] = True
    widgets["family_activation"]["visualizers"] = True
    widgets["spotify_visualizer"]["enabled"] = False
    widgets["spotify_visualizer"]["mode_activation"]["sphere"] = False
    page = VisualizerPage(settings)
    try:
        page.refresh()
        offered = {
            page.rows.item(index).data(Qt.ItemDataRole.UserRole): page.rows.item(index)
            for index in range(page.rows.count())
        }
        assert "sphere" in offered
        assert offered["sphere"].text() == "Voxel Sphere"
        assert offered["sphere"].checkState() == Qt.CheckState.Unchecked
        assert settings.writes == []

        page._enable(True)
        offered["sphere"].setCheckState(Qt.CheckState.Checked)
        modes = settings.get("widgets.spotify_visualizer.mode_activation")
        assert settings.get("widgets.spotify_visualizer.enabled") is True
        assert modes["sphere"] is True
    finally:
        page.deleteLater()


def test_transition_toggle_updates_activation_pool_and_random_semantics(qapp, settings) -> None:
    transitions = settings.values["transitions"]
    transitions["type"] = "Random"
    transitions["random_always"] = False
    page = TransitionsPage(settings)
    try:
        page.refresh()
        crossfade = next(
            page.rows.item(index)
            for index in range(page.rows.count())
            if page.rows.item(index).data(Qt.ItemDataRole.UserRole) == "Crossfade"
        )
        crossfade.setCheckState(Qt.CheckState.Checked)
        cfg = settings.get("transitions")
        assert cfg["activation"]["Crossfade"] is True
        assert cfg["pool"]["Crossfade"] is True
        assert cfg["random_always"] is True
        assert cfg["type"] != "Random"
    finally:
        page.deleteLater()


def test_ready_page_accounts_are_optional_and_do_not_block(qapp, settings, monkeypatch) -> None:
    monkeypatch.setattr(state, "saved_account_states", lambda _settings: {"steam": False, "gmail": False})
    page = ReadyPage(settings)
    try:
        page.refresh()
        assert page.can_continue() is True
        assert "Steam: Needs Setup" in page.summary.text()
        assert "Gmail: Needs Setup" in page.summary.text()
    finally:
        page.deleteLater()


def test_transition_strip_is_ninety_percent_wide_and_undistorted(qapp) -> None:
    from ui.onboarding.selection_pages import TransitionStrip, _transition_manifest

    strip = TransitionStrip()
    try:
        strip.set_transition("crossfade")
        row = _transition_manifest()["crossfade"]
        assert row["path"].endswith(".png") and len(row["progress"]) == 3
        count, frame_width, frame_height = strip._layout(1000)
        assert count == 3
        assert frame_width * 3 + strip.GAP * 2 == 900  # 90% of the width
        assert abs(frame_width / frame_height - 16 / 9) < 1e-9
        assert strip.heightForWidth(1000) == round(frame_height)
        strip.resize(1000, strip.heightForWidth(1000))
        image = strip.grab().toImage()
        background = image.pixelColor(2, 2)
        assert image.pixelColor(40, 60) == background  # the 5% side margin stays clear
        assert image.pixelColor(200, 100) != background  # the first frame is painted
    finally:
        strip.deleteLater()


def test_widget_previews_never_upscale_past_native_pixels(qapp) -> None:
    from ui.onboarding.common import ImagePanel, asset_path

    panel = ImagePanel(asset_path("onboarding/widget_system_audio_osd.png"), upscale=False)
    try:
        source = panel._source.size()
        panel.resize(source.width() * 3, source.height() * 3)
        panel._rescale()
        shown = panel.pixmap()
        assert shown.width() <= source.width() and shown.height() <= source.height()
    finally:
        panel.deleteLater()


def test_visualizer_page_is_a_narrow_list_with_the_selected_modes_preview(qapp, settings) -> None:
    page = VisualizerPage(settings)
    try:
        page.refresh()
        assert page.rows.maximumWidth() <= 360
        for row in range(page.rows.count()):  # narrow, yet no mode name is cut off
            check = page.rows.itemWidget(page.rows.item(row))
            assert check.sizeHint().width() <= page.rows.maximumWidth() - 2 * page.rows.frameWidth()
        assert page.preview is not None
        for row in range(page.rows.count()):
            page.rows.setCurrentRow(row)
            mode_id = page.rows.item(row).data(Qt.ItemDataRole.UserRole)
            assert page.preview_title.text() == page.rows.item(row).text()
            assert not page.preview._source.isNull(), mode_id
        assert settings.writes == []
    finally:
        page.deleteLater()


def test_ready_page_summarises_the_real_context_menu(qapp, settings, monkeypatch) -> None:
    from rendering.quick.context_menu import build_quick_context_menu_entries
    from ui.onboarding.selection_pages import CONTEXT_MENU_SUMMARY
    monkeypatch.setattr(state, "saved_account_states", lambda _settings: {"steam": False, "gmail": False})
    entries = build_quick_context_menu_entries(
        transition_names=("Crossfade",), current_transition="Crossfade", random_enabled=False,
        random_selectable=True, visualizer_modes=(("bubble", "Bubble"),), current_visualizer="bubble",
        visualizer_available=True, dimming_enabled=False, interaction_mode_enabled=False,
        interaction_mode_locked=False, edit_mode_active=False)
    menu = " ".join(child.label for entry in entries for child in (entry, *entry.children))
    for name, _detail in CONTEXT_MENU_SUMMARY:
        for part in name.split(" / "):
            assert part.split()[0] in menu, part  # every summarised entry exists in the menu
    page = ReadyPage(settings)
    try:
        page.refresh()
        assert page.summary.text()  # the Ready summary is filled from the draft
    finally:
        page.deleteLater()
