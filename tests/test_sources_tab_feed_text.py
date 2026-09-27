"""The Sources tab describes wallpaper feeds as they currently work."""

from __future__ import annotations


def test_default_feed_action_names_the_canonical_defaults(qt_app, tmp_path) -> None:
    from core.settings.settings_manager import SettingsManager
    from sources.rss.constants import DEFAULT_RSS_FEEDS
    from ui.tabs.sources_tab import SourcesTab

    settings = SettingsManager(
        organization="TestOrg",
        application="SourcesTabFeedText",
        storage_base_dir=tmp_path,
    )
    tab = SourcesTab(settings)
    try:
        tip = tab.just_make_it_work_btn.toolTip()
        # Generated from the curated list, so it cannot name removed feeds.
        assert all(name in tip for name in DEFAULT_RSS_FEEDS)
        assert "Flickr" not in tip and "Wikimedia" not in tip
        assert tab.rss_ratio_label.text().endswith("% Feeds")
        tab.ratio_slider.setValue(70)
        assert tab.rss_ratio_label.text() == "30% Feeds"
    finally:
        tab.deleteLater()


def test_sources_are_two_closed_buckets_with_counts_and_the_ratio_below_both(qt_app, tmp_path) -> None:
    from core.settings.settings_manager import SettingsManager
    from ui.tabs.sources_tab import SourcesTab
    from ui.widgets.outlined_button import OutlinedButton

    settings = SettingsManager(organization="TestOrg", application="SourcesTabBuckets", storage_base_dir=tmp_path)
    settings.set("sources.folders", ["C:/Wallpapers", r"D:\More"])
    settings.set("sources.rss_feeds", ["https://example.test/feed.xml"])
    tab = SourcesTab(settings)
    try:
        assert not tab.folders_toggle.isChecked() and not tab.feeds_toggle.isChecked()
        assert tab.folders_toggle.text().endswith("2")
        assert tab.feeds_toggle.text().endswith("1 ON")
        # One accordion: opening one closes the other.
        tab.folders_toggle.setChecked(True)
        tab.feeds_toggle.setChecked(True)
        assert not tab.folders_toggle.isChecked()

        def y(widget):
            return widget.mapTo(tab, widget.rect().topLeft()).y()

        from tests._invisible_windows import keep_off_screen

        tab.resize(900, 900)
        keep_off_screen(tab).show()  # a real layout pass, never visible
        qt_app.processEvents()
        assert y(tab.folders_toggle) < y(tab.feeds_toggle) < y(tab.ratio_frame)
        # Painted, seam-free action buttons in the Sources look.
        assert isinstance(tab.add_folder_btn, OutlinedButton) and tab.add_folder_btn._role == "source"
        assert isinstance(tab.rss_save_dir_btn, OutlinedButton)
        # What the option does: every kept feed image is copied.
        assert "All" in tab.rss_save_to_disk.text() and "Disk" in tab.rss_save_to_disk.text()
    finally:
        tab.deleteLater()
