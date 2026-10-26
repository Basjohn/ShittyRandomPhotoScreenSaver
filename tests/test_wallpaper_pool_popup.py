"""Real selector controls, isolated Settings, and the wizard draft boundary."""
from dataclasses import replace

import pytest

from sources.rss.pools import read_pool_selection, write_pool_selection, WallpaperPoolSelection


@pytest.fixture
def settings(tmp_path):
    from core.settings.settings_manager import SettingsManager
    store = SettingsManager(organization="SC4Tests", application="PoolPopup", storage_base_dir=tmp_path)
    write_pool_selection(store, WallpaperPoolSelection(False, ("wallhaven.nature",), "latest"))
    return store


def test_selection_roundtrip_preserves_custom_urls_folders_and_profile_reset(qt_app, settings, tmp_path):
    from core.settings.models import SourceSettings
    from core.sources.readiness import has_image_sources
    custom = ["https://custom.invalid/authored?private=kept"]
    settings.set("sources.rss_feeds", custom)
    settings.set("sources.folders", ["X:/wallpapers"])
    selection = WallpaperPoolSelection(True, ("nasa.space", "konachan.safe"), "popular")
    write_pool_selection(settings, selection)
    assert read_pool_selection(settings) == selection
    assert SourceSettings.from_settings(settings).wallpaper_pools == selection.to_dict()
    settings.save()
    from core.settings.settings_manager import SettingsManager
    reopened = SettingsManager(organization="SC4Tests", application="PoolPopup", storage_base_dir=tmp_path)
    assert read_pool_selection(reopened) == selection
    from core.settings.json_store import JsonSettingsStore
    from types import SimpleNamespace
    independent_disk_store = JsonSettingsStore(storage_path=settings.get_storage_path(), profile="PoolPopup")
    assert read_pool_selection(SimpleNamespace(get=independent_disk_store.value)) == selection
    settings.reset_to_defaults()
    assert read_pool_selection(settings) == selection
    assert settings.get("sources.rss_feeds") == custom
    assert has_image_sources(settings)


@pytest.mark.parametrize("nested", [False, True])
def test_sst_import_export_and_natural_nested_pool_shape(qt_app, settings, tmp_path, nested):
    import json
    selection = WallpaperPoolSelection(True, ("nasa.space",), "month")
    write_pool_selection(settings, selection)
    sst = tmp_path / "pool.sst"
    assert settings.export_to_sst(str(sst))
    if nested:
        data = json.loads(sst.read_text(encoding="utf8"))
        sources = data["snapshot"]["sources"]
        for key in selection.to_dict():
            sources.pop(f"wallpaper_pools.{key}")
        sources["wallpaper_pools"] = selection.to_dict()
        sst.write_text(json.dumps(data), encoding="utf8")
    write_pool_selection(settings, replace(selection, enabled=False, selected=()))
    assert settings.import_from_sst(str(sst), merge=False)
    assert read_pool_selection(settings) == selection


@pytest.mark.parametrize("accepted", [False, True])
def test_shared_popup_cancel_or_apply_is_staged_and_draft_discard_keeps_store(qt_app, settings, monkeypatch, accepted):
    import ui.wallpaper_pool_popup as module
    from ui.onboarding.draft import SettingsDraft
    custom = ["https://authored.invalid/rss"]
    settings.set("sources.rss_feeds", custom)
    before = read_pool_selection(settings)
    draft = SettingsDraft(settings)
    def interact(popup):
        popup.checkboxes["nasa.space"].setChecked(True)
        popup.order.setCurrentIndex(popup.order.findData("year"))
        popup._result_value = "apply" if accepted else "cancel"
    monkeypatch.setattr(module.WallpaperPoolPopup, "exec", interact)
    assert module.choose_wallpaper_pools(None, draft) is accepted
    assert read_pool_selection(settings) == before
    assert settings.get("sources.rss_feeds") == custom
    if accepted:
        assert read_pool_selection(draft).discovery_order == "year"
        assert "nasa.space" in read_pool_selection(draft).selected
        draft.commit()
        assert read_pool_selection(settings) == read_pool_selection(draft)
    else:
        assert not draft.pending


def test_guided_toggle_changes_pool_admission_without_replacing_custom_feeds(qt_app, settings):
    from ui.onboarding.basic_pages import SourcesPage
    custom = ["https://authored.invalid/rss"]
    settings.set("sources.rss_feeds", custom)
    page = SourcesPage(settings)
    try:
        page.feeds_enabled.setChecked(True)
        page.feeds_enabled.setChecked(False)
        assert settings.get("sources.rss_feeds") == custom
        assert page.can_continue()
    finally:
        page.deleteLater()
        qt_app.processEvents()


def test_settings_pool_only_configuration_enables_ratio_and_readiness(qt_app, settings):
    from ui.tabs.sources_tab import SourcesTab
    from core.sources.readiness import has_image_sources
    settings.set("sources.folders", ["X:/wallpapers"])
    write_pool_selection(settings, WallpaperPoolSelection(True, ("nasa.space",), "latest"))
    tab = SourcesTab(settings)
    try:
        assert tab.ratio_slider.isEnabled()
        assert tab.rss_list.count() == 0
        assert has_image_sources(settings)
        assert "Pools:" in tab.pool_status_label.text()
    finally:
        tab.deleteLater()
        qt_app.processEvents()


def test_selector_uses_shared_circle_controls_and_keeps_choices_across_navigation(qt_app, settings):
    from PySide6.QtWidgets import QScrollArea
    from ui.wallpaper_pool_popup import WallpaperPoolPopup

    before = read_pool_selection(settings)
    popup = WallpaperPoolPopup(None, before)
    try:
        from sources.rss.pools import WALLPAPER_POOLS
        assert set(popup.checkboxes) == {pool.pool_id for pool in WALLPAPER_POOLS}
        assert all(check.property("circleIndicator") is True and check.toolTip()
                   for check in popup.checkboxes.values())
        assert popup.order.toolTip()
        assert all(button.toolTip() for button in popup._navigation.buttons())
        assert "&&" in popup.checkboxes["wallhaven.nature"].text(), "Qt mnemonics must not swallow the visible ampersand"
        for page, key in ((1, "nasa.space"), (2, "konachan.safe"), (0, "wallhaven.nature")):
            popup._navigation.button(page).click()
            check = popup.checkboxes[key]
            assert popup.pages.currentWidget().isAncestorOf(check)
            check.setChecked(True)
        assert {"nasa.space", "konachan.safe", "wallhaven.nature"} <= set(popup.selection().selected)
        assert read_pool_selection(settings) == before, "navigation and checks remain a local draft"
        assert popup._message == "", "provider explanations belong in tooltips"
        assert not popup.findChild(QScrollArea).viewport().autoFillBackground(), "the list must not expose a foreign dark palette"
    finally:
        popup.deleteLater()
        qt_app.processEvents()


def test_startup_migrates_exact_legacy_urls_once_preserving_custom_variants(qt_app, settings, tmp_path):
    from core.settings.settings_manager import SettingsManager
    from sources.rss.constants import LEGACY_CURATED_RSS_FEEDS
    legacy = list(LEGACY_CURATED_RSS_FEEDS.values())
    custom = ["https://custom.invalid/rss", legacy[0] + "?authored=1"]
    settings.set("sources.rss_feeds", [custom[0], *legacy, custom[1]])
    for key in ("enabled", "selected", "discovery_order"):
        settings._settings.remove(f"sources.wallpaper_pools.{key}")
    settings.save()
    reopened = SettingsManager(organization="SC4Tests", application="PoolPopup", storage_base_dir=tmp_path)
    selection = read_pool_selection(reopened)
    assert selection.enabled and {"nasa.space", "bing.daily"} <= set(selection.selected)
    assert reopened.get("sources.rss_feeds") == custom
    # Once the new policy exists, an explicitly authored old URL remains custom.
    reopened.set("sources.rss_feeds", [legacy[0]])
    reopened.save()
    again = SettingsManager(organization="SC4Tests", application="PoolPopup", storage_base_dir=tmp_path)
    assert again.get("sources.rss_feeds") == [legacy[0]]
    assert read_pool_selection(again) == selection


def test_sst_legacy_mixed_sources_preview_and_import_share_migration(qt_app, settings, tmp_path):
    import json
    from sources.rss.constants import LEGACY_CURATED_RSS_FEEDS
    legacy = LEGACY_CURATED_RSS_FEEDS["NASA JPL Photojournal"]
    custom = "https://custom.invalid/feed"
    sst = tmp_path / "old.sst"
    sst.write_text(json.dumps({"snapshot": {"sources": {"rss_feeds": [legacy, custom]}}}), encoding="utf8")
    before = read_pool_selection(settings)
    preview = settings.preview_import_from_sst(str(sst))
    assert read_pool_selection(settings) == before
    assert settings.import_from_sst(str(sst))
    assert read_pool_selection(settings) == WallpaperPoolSelection(True, ("nasa.space",), before.discovery_order)
    assert settings.get("sources.rss_feeds") == [custom]
