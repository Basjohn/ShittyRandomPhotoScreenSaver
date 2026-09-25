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
