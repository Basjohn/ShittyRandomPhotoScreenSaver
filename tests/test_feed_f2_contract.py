from __future__ import annotations

from pathlib import Path

from core.settings.default_contract import require_canonical_default
from core.settings.widget_family_catalog import get_widget_family_descriptor
from rendering.widget_descriptors import (
    get_widget_runtime_descriptor,
    get_widget_settings_section_descriptor,
)

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_feeds_family_is_bounded_and_dormant_by_default():
    from core.feeds.config import FEED_WIDGET_IDS

    family = get_widget_family_descriptor("feeds")
    assert family is not None
    assert family.member_widget_ids == FEED_WIDGET_IDS == (
        "feeds_custom_1",
        "feeds_custom_2",
        "feeds_custom_3",
        "feeds_custom_4",
        "feeds_news_world",
        "feeds_news_us",
        "feeds_news_politics",
        "feeds_news_gaming",
        "feeds_news_tech",
    )
    assert require_canonical_default("widgets.family_activation.feeds") is False
    for widget_id in FEED_WIDGET_IDS:
        assert require_canonical_default(f"widgets.{widget_id}.enabled") is False


def test_every_feed_card_runs_the_same_runtime_descriptor():
    from dataclasses import replace

    from core.feeds.config import FEED_WIDGET_IDS

    first = get_widget_runtime_descriptor("feeds_custom_1")
    assert first is not None
    assert first.settings_section_id == "feeds"
    assert first.service_backed is True
    assert first.supports_layout_edit_mode is True
    assert first.content_extent_axes == ("horizontal", "vertical")
    assert first.content_extent_minimum_size == (320, 180)
    for widget_id in FEED_WIDGET_IDS:
        descriptor = get_widget_runtime_descriptor(widget_id)
        assert descriptor is not None
        # Identical apart from identity: no slot- or category-specific runtime
        # behaviour; CUSTOM and NEWS share edit, geometry and service contracts.
        assert replace(
            descriptor,
            widget_id="feeds_custom_1",
            attr_name="feeds_custom_1_widget",
            settings_prefixes=("widgets.feeds_custom_1",),
        ) == first


def test_feeds_settings_section_is_lazy_descriptor_owned_for_every_feed_card():
    from core.feeds.config import FEED_WIDGET_IDS

    descriptor = get_widget_settings_section_descriptor("feeds")
    assert descriptor is not None
    assert descriptor.builder_module == "ui.tabs.widgets_tab_feeds"
    assert descriptor.persisted_widget_keys == FEED_WIDGET_IDS


def test_feed_subtitle_toggle_has_canonical_default_for_every_custom_slot():
    for index in range(1, 5):
        assert require_canonical_default(
            f"widgets.feeds_custom_{index}.show_subtitle"
        ) is True
    settings = _text("ui/tabs/widgets_tab_feeds.py")
    assert 'QCheckBox("Show Feed Subtitle")' in settings
    assert '"show_subtitle": bool(_control(tab, widget_id, "show_subtitle").isChecked())' in settings


def test_settings_feed_probe_is_explicit_and_never_bound_to_url_typing():
    source = _text("ui/tabs/widgets_tab_feeds.py")
    assert "test_button.clicked.connect(lambda _checked=False, n=slot: _test_feed(tab, n))" in source
    assert "url.textChanged.connect" not in source
    assert "url.editingFinished.connect(tab._save_settings)" in source
    assert "probe_feed_url(url)" in source
    assert "Shiboken.isValid(owner)" in source


def test_feed_qml_never_loads_remote_images_or_owns_network_cadence():
    qml = _text("rendering/quick/qml/FeedPresentation.qml")
    assert "Timer {" not in qml
    assert "XMLHttpRequest" not in qml
    assert "NetworkAccess" not in qml
    assert 'source: parent.visible ? feedImageSource : ""' in qml  # F3: local URI only.


def test_feed_external_action_is_http_only_until_f4():
    source = _text("rendering/quick/widgets/feeds.py")
    assert 'scheme in {"http", "https"}' in source
    action = _text("core/widget_product_actions.py")
    assert "Magnet and managed torrent" in action


def test_f3_exposes_image_control_with_persisted_settings_and_local_only_rendering():
    settings = _text("ui/tabs/widgets_tab_feeds.py")
    assert '"show_images": bool(_control(tab, widget_id, "show_images").isChecked())' in settings
    assert '_control(tab, widget_id, "show_images").setChecked(tab._config_bool(' in settings
    assert '"show_subtitle": bool(_control(tab, widget_id, "show_subtitle").isChecked())' in settings
    assert '_control(tab, widget_id, "show_subtitle").setChecked(tab._config_bool(' in settings
    qml = _text("rendering/quick/qml/FeedPresentation.qml")
    assert 'source: parent.visible ? feedImageSource : ""' in qml


def test_legacy_rss_background_log_redacts_feed_query_tokens():
    source = _text("engine/engine_rss.py")
    assert "redacted_url_for_log(feed_url)" in source
    assert "feed_url[:60]" not in source


def test_feed_presentation_capacity_never_clips_configured_rows_or_steals_edit_wheel():
    qml = _text("rendering/quick/qml/FeedPresentation.qml")
    assert "readonly property int listCapacity" in qml
    assert "readonly property int gridColumns" in qml
    assert "readonly property int overflowCount" in qml
    assert '" MORE"' in qml
    assert "ListView" not in qml
    assert "GridView" not in qml
    assert "WheelHandler" not in qml


def test_feed_settings_describes_item_count_as_a_maximum():
    settings = _text("ui/tabs/widgets_tab_feeds.py")
    assert '"Max Items:"' in settings


def test_feed_custom_xy_resize_projects_content_extent_and_reflows_without_io():
    source = _text("rendering/quick/widgets/feeds.py")
    qml = _text("rendering/quick/qml/FeedPresentation.qml")
    assert "def set_content_extent(" in source
    assert "def apply_custom_layout_size_payload(" in source
    assert "set_custom_layout_size_payload_handler(model.apply_custom_layout_size_payload)" in source
    assert "self._content_extent" in source
    assert "preferredContentWidth: feedModel.preferredWidth" in qml
    assert "preferredContentHeight: feedModel.preferredHeight" in qml
    assert "readonly property int gridColumns" in qml
    assert "readonly property int gridRowCapacity" in qml
    for forbidden in ("Timer {", "XMLHttpRequest", "NetworkAccess"):
        assert forbidden not in qml
