"""All four CUSTOM Feed slots share one admission, presentation and runtime path."""
from __future__ import annotations

import pytest

from core.feeds.config import CUSTOM_FEED_WIDGET_IDS
from rendering.quick.widgets.family_binder import FeedFamilyAdapter


def _slot(name: str, url: str = "https://example.test/feed.xml", *, enabled: bool = True) -> dict:
    return {"enabled": enabled, "name": name, "feed_url": url}


def test_every_enabled_configured_custom_slot_is_admitted_in_slot_order():
    adapter = FeedFamilyAdapter()
    widgets = {
        "feeds_custom_1": _slot("Alpha"),
        "feeds_custom_2": _slot("Beta", enabled=False),
        "feeds_custom_3": _slot("Gamma", url=""),  # enabled but unconfigured: no dead card
        "feeds_custom_4": _slot("Delta"),
    }
    assert adapter.enabled_instance_ids(widgets) == ("feeds_custom_1", "feeds_custom_4")
    all_on = {widget_id: _slot(f"Feed {index}") for index, widget_id in enumerate(CUSTOM_FEED_WIDGET_IDS, 1)}
    assert adapter.enabled_instance_ids(all_on) == CUSTOM_FEED_WIDGET_IDS


def test_monogram_ordinal_is_zero_for_unique_initials():
    from rendering.quick.widgets.feeds import _monogram_ordinal

    widgets = {
        "feeds_custom_1": _slot("Nyaa"),
        "feeds_custom_2": _slot("Ars Technica"),
        "feeds_custom_3": _slot("GitHub"),
    }
    for widget_id in ("feeds_custom_1", "feeds_custom_2", "feeds_custom_3"):
        assert _monogram_ordinal(widgets, widget_id) == 0


def test_monogram_ordinal_ranks_same_initial_slots_by_slot_order():
    from rendering.quick.widgets.feeds import _monogram_ordinal

    widgets = {
        "feeds_custom_1": _slot("Nyaa"),
        "feeds_custom_2": _slot("Hacker News"),
        "feeds_custom_3": _slot("news digest"),  # initial is case-insensitive
        "feeds_custom_4": _slot("Nintendo"),
    }
    assert _monogram_ordinal(widgets, "feeds_custom_1") == 1
    assert _monogram_ordinal(widgets, "feeds_custom_2") == 0
    assert _monogram_ordinal(widgets, "feeds_custom_3") == 2
    assert _monogram_ordinal(widgets, "feeds_custom_4") == 3


def test_disabled_or_unconfigured_slots_never_cause_a_collision_ordinal():
    from rendering.quick.widgets.feeds import _monogram_ordinal

    widgets = {
        "feeds_custom_1": _slot("Nyaa"),
        "feeds_custom_2": _slot("News", enabled=False),
        "feeds_custom_3": _slot("Nightly", url=""),
    }
    assert _monogram_ordinal(widgets, "feeds_custom_1") == 0


def test_monogram_ordinal_uses_the_one_cached_vector_path(qapp):
    from rendering.quick.widgets.feeds import _vector_monogram_data_uri

    color = (255, 255, 255, 230)
    plain = _vector_monogram_data_uri("N", color)
    first = _vector_monogram_data_uri("N", color, 1)
    second = _vector_monogram_data_uri("N", color, 2)
    assert all(uri.startswith("data:image/png;base64,") for uri in (plain, first, second))
    assert len({plain, first, second}) == 3
    # Cached per (glyph, colour, ordinal): repeated calls do not re-rasterize.
    assert _vector_monogram_data_uri("N", color, 2) is second


@pytest.mark.parametrize("widget_id", CUSTOM_FEED_WIDGET_IDS)
def test_every_slot_has_a_runtime_service_spec(widget_id):
    from rendering.widget_runtime_services import _RUNTIME_SERVICE_SPECS

    assert _RUNTIME_SERVICE_SPECS[widget_id] is _RUNTIME_SERVICE_SPECS["feeds_custom_1"]


def test_later_slots_inherit_the_custom_1_header_theme_roles():
    from ui.widget_visual_roles import WIDGET_VISUAL_ROLE_PARENTS

    for widget_id in CUSTOM_FEED_WIDGET_IDS[1:]:
        for role in ("fill", "border", "text"):
            assert WIDGET_VISUAL_ROLE_PARENTS[f"{widget_id}.header.{role}"] == f"feeds_custom_1.header.{role}"


def test_settings_feeds_section_builds_and_round_trips_all_four_slots(qt_app, settings_manager):
    from rendering.widget_descriptors import (
        apply_widget_section_save_results,
        collect_widget_section_save_results,
    )
    from ui.tabs.widgets_tab import WidgetsTab
    from ui.tabs.widgets_tab_feeds import feed_slot_attr, load_feeds_settings, save_feeds_settings

    # Feeds is a deactivated family by default; its page is only built once active.
    settings_manager.set("widgets.family_activation.feeds", True)
    tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "feeds"})
    try:
        for slot in (1, 2, 3, 4):
            assert getattr(tab, feed_slot_attr(slot, "enabled")).text() == f"Enable Custom {slot}"
            container = getattr(tab, f"_feeds_custom{slot}_controls_container")
            getattr(tab, feed_slot_attr(slot, "enabled")).setChecked(False)
            assert container.isHidden() is True
            getattr(tab, feed_slot_attr(slot, "enabled")).setChecked(True)
            assert container.isHidden() is False

        widgets = {
            "feeds_custom_1": {"enabled": True, "name": "One", "feed_url": "https://a.example/rss"},
            "feeds_custom_2": {"enabled": True, "name": "Two", "feed_url": "https://b.example/rss",
                               "view_mode": "grid", "item_limit": 9},
            "feeds_custom_3": {"enabled": False, "name": "Three", "feed_url": ""},
            "feeds_custom_4": {"enabled": True, "name": "Four", "feed_url": "https://a.example/rss",
                               "refresh_minutes": 45},
        }
        load_feeds_settings(tab, widgets)
        payloads = save_feeds_settings(tab)
        # One payload per Feed card (CUSTOM slots, then NEWS categories).
        from core.feeds.config import FEED_WIDGET_IDS
        assert len(payloads) == len(FEED_WIDGET_IDS)
        by_id = dict(zip(FEED_WIDGET_IDS[:4], payloads))
        assert by_id["feeds_custom_2"]["view_mode"] == "grid"
        assert by_id["feeds_custom_2"]["item_limit"] == 9
        assert by_id["feeds_custom_3"]["enabled"] is False
        assert by_id["feeds_custom_4"]["refresh_minutes"] == 45
        assert [by_id[key]["name"] for key in by_id] == ["One", "Two", "Three", "Four"]

        # The descriptor layer accepts the tuple shape and writes every slot.
        results = collect_widget_section_save_results(tab, {})
        config: dict = {}
        apply_widget_section_save_results(config, results)
        for key in by_id:
            assert config[key]["name"] == by_id[key]["name"]
    finally:
        tab.deleteLater()
