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


def test_feeds_family_catalog_and_defaults_are_authority_owned():
    from core.feeds.config import FEED_WIDGET_IDS

    family = get_widget_family_descriptor("feeds")
    assert family is not None
    assert family.member_widget_ids == FEED_WIDGET_IDS
    assert FEED_WIDGET_IDS and len(set(FEED_WIDGET_IDS)) == len(FEED_WIDGET_IDS)

    # Values are mutable product defaults. The durability contract here is that
    # they exist at the canonical authority with the expected schema, not that
    # today's authored booleans/minutes can never change.
    assert isinstance(require_canonical_default("widgets.family_activation.feeds"), bool)
    for widget_id in FEED_WIDGET_IDS:
        assert isinstance(require_canonical_default(f"widgets.{widget_id}.enabled"), bool)
        # One family cadence (widgets.feeds), never a per-card refresh period.
        assert "refresh_minutes" not in require_canonical_default(f"widgets.{widget_id}")
    family_defaults = require_canonical_default("widgets.feeds")
    assert set(family_defaults) == {"refresh_minutes"}
    assert isinstance(family_defaults["refresh_minutes"], int)
    assert family_defaults["refresh_minutes"] > 0


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
    assert descriptor.persisted_widget_keys == ("feeds",) + FEED_WIDGET_IDS


def test_feed_subtitle_toggle_has_canonical_boolean_default_for_every_custom_slot():
    from core.feeds.config import FEED_WIDGET_IDS

    for widget_id in (item for item in FEED_WIDGET_IDS if item.startswith("feeds_custom_")):
        assert isinstance(
            require_canonical_default(f"widgets.{widget_id}.show_subtitle"),
            bool,
        )
    settings = _text("ui/tabs/widgets_tab_feeds.py")
    assert 'QCheckBox("Show Feed Subtitle")' in settings
    assert '"show_subtitle": bool(_control(tab, widget_id, "show_subtitle").isChecked())' in settings


def test_settings_feed_probe_is_explicit_and_never_bound_to_url_typing():
    source = _text("ui/tabs/widgets_tab_feeds.py")
    assert "lambda _checked=False, n=slot: _test_feed(tab, n)" in source
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


def test_feed_external_actions_are_http_pages_and_validated_magnets_only():
    source = _text("rendering/quick/widgets/feeds.py")
    assert 'scheme in {"http", "https"}' in source
    assert "return _browser_action_url(value) or admitted_magnet_uri(value)" in source
    action = _text("core/widget_product_actions.py")
    assert "admitted_magnet_uri(normalized_url)" in action
    helper = _text("helpers/reddit_helper_worker.py")
    assert "admitted_magnet_uri(url)" in helper


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


def test_feed_article_refresh_fade_is_body_scoped_event_driven_and_timerless():
    source = _text("rendering/quick/widgets/feeds.py")
    qml = _text("rendering/quick/qml/FeedPresentation.qml")

    assert "contentTransitionRequested = Signal()" in source
    assert "def commitPendingContent(" in source
    assert "self.contentTransitionRequested.emit()" in source
    assert 'settled = bool(getattr(result, "presentation_settled", True))' in source
    assert "if not settled:" in source
    assert "self._content_transitions_armed = False" in source
    assert "if not self._content_transitions_armed:" in source
    assert "self._content_transitions_armed = True" in source
    assert "self._content_transition_requested" in source
    assert "function onContentTransitionRequested()" in qml
    assert "id: articleContentFade" in qml
    assert 'target: body' in qml
    assert 'script: feedRoot.feedModel.commitPendingContent()' in qml
    assert 'property: "fadeOpacity"' not in qml[qml.index("id: articleContentFade"):qml.index("Item {", qml.index("id: articleContentFade") + 1)]
    # Feed content transitions are intentionally unmistakable and gentle, not
    # a sub-quarter-second flicker. Both values are shared by CUSTOM and NEWS
    # because the whole FEEDS family uses this one presentation component.
    assert "readonly property int contentFadeOutDuration: 900" in qml
    assert "readonly property int contentFadeInDuration: 1200" in qml
    assert "duration: feedRoot.contentFadeOutDuration" in qml
    assert "duration: feedRoot.contentFadeInDuration" in qml
    assert qml.count("easing.type: Easing.InOutSine") >= 2
    # Artwork hydration is a retained two-buffer fade as well.  A late local
    # artwork URI must never make the image snap into a fully opaque raw Image.
    assert qml.count("ArtworkFadeImage {") >= 2
    assert qml.count("fadeOutDuration: feedRoot.contentFadeOutDuration") >= 2
    assert qml.count("fadeInDuration: feedRoot.contentFadeInDuration") >= 2
    assert "Timer {" not in qml
    assert "Thread(" not in source
