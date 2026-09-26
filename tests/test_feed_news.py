"""NEWS categories: vetted publisher feeds merged on the shared FEEDS path."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from core.feeds.config import FEED_WIDGET_IDS, feed_widget_config
from core.feeds.models import (
    FeedDocument,
    FeedHealth,
    FeedItem,
    FeedRefreshResult,
    FeedSnapshot,
)
from core.feeds.news import (
    NEWS_CATEGORIES,
    NEWS_PROVIDERS,
    NEWS_WIDGET_IDS,
    NewsFeedConfig,
    merge_news_results,
    news_providers_for,
)
from core.settings.default_contract import require_canonical_default
from widgets import feed_runtime
from widgets.feed_runtime import NewsRuntimeConfig, NewsRuntimeService

QML_ROOT = Path(__file__).resolve().parents[1] / "rendering" / "quick" / "qml"


def _item(item_id, published_at, url=None, *, title=None):
    return FeedItem(
        item_id,
        title or f"Story {item_id}",
        url if url is not None else f"https://news.example/{item_id}",
        published_at=published_at,
    )


def _result(*items, status="available", fetched_at=1000.0, artwork=(), failure="", title="Feed"):
    snapshot = FeedSnapshot(FeedDocument(title, "https://news.example/", "rss20", tuple(items)), fetched_at)
    return FeedRefreshResult(
        status, snapshot,
        FeedHealth(last_checked_at=fetched_at, last_success_at=fetched_at),
        failure=failure, local_artwork_by_item=tuple(artwork),
    )


def _failed(failure="FeedTransportError"):
    return FeedRefreshResult("unavailable", None, FeedHealth(consecutive_failures=1), failure=failure)


# --- catalog -----------------------------------------------------------------


def test_every_category_has_at_least_two_independent_publishers():
    for category in NEWS_CATEGORIES:
        providers = news_providers_for(category.widget_id)
        assert len(providers) >= 2, category.widget_id
        assert len({provider.display_name for provider in providers}) >= 2, category.widget_id


def test_provider_identity_is_stable_and_independent_of_the_endpoint():
    ids = [provider.provider_id for provider in NEWS_PROVIDERS]
    assert len(ids) == len(set(ids))
    for provider in NEWS_PROVIDERS:
        assert urlsplit(provider.url).scheme == "https"
        spec = provider.source_spec()
        assert spec.source_id == f"news:{provider.provider_id}"
        assert spec.cache_key == f"news_{provider.provider_id}"
        assert provider.url not in spec.cache_key
        # An official URL move keeps last-good state under the same ID.
        assert spec.allow_endpoint_migration is True


def test_news_defaults_select_every_catalog_publisher_and_stay_dormant():
    for widget_id in NEWS_WIDGET_IDS:
        assert require_canonical_default(f"widgets.{widget_id}.enabled") is False
        assert require_canonical_default(f"widgets.{widget_id}.providers") == [
            provider.provider_id for provider in news_providers_for(widget_id)
        ]


def test_news_widget_ids_follow_the_custom_slots_in_feed_order():
    assert FEED_WIDGET_IDS[4:] == NEWS_WIDGET_IDS == (
        "feeds_news_world", "feeds_news_us", "feeds_news_politics",
        "feeds_news_gaming", "feeds_news_tech",
    )


# --- config ------------------------------------------------------------------


def test_news_config_keeps_catalog_order_and_ignores_unknown_publishers():
    config = NewsFeedConfig.from_mapping(
        "feeds_news_world",
        {"enabled": "yes", "providers": ["npr_world", "abc_world", "nonsense", "cbs_world"]},
    )
    assert config.enabled is True
    assert config.name == "World News"
    assert [provider.provider_id for provider in config.providers] == ["cbs_world", "npr_world"]
    assert config.configured is True
    assert feed_widget_config("feeds_news_world", {}).providers == news_providers_for("feeds_news_world")


def test_news_config_without_publishers_is_unconfigured_and_malformed_input_repairs():
    assert NewsFeedConfig.from_mapping("feeds_news_us", {"providers": []}).configured is False
    repaired = NewsFeedConfig.from_mapping(
        "feeds_news_us",
        {"providers": "cbs_us", "view_mode": "carousel", "item_limit": 999, "refresh_minutes": 1},
    )
    assert repaired.providers == news_providers_for("feeds_news_us")
    assert repaired.view_mode == "list"
    assert repaired.item_limit == 40
    assert repaired.refresh_minutes == 5
    with pytest.raises(ValueError):
        NewsFeedConfig.from_mapping("feeds_custom_1", {})


# --- merge -------------------------------------------------------------------


def test_merge_is_newest_first_with_publisher_attribution_and_undated_last():
    cbs, bbc, npr = news_providers_for("feeds_news_world")
    merged = merge_news_results(
        (cbs, bbc, npr),
        {
            "cbs_world": _result(_item("a", 300), _item("b", None), _item("c", 100)),
            "bbc_world": _result(_item("x", 200), _item("y", None)),
        },
    )
    rows = [(item.item_id, item.author) for item in merged.snapshot.document.items]
    assert rows == [
        ("cbs_world:a", "CBS News"),
        ("bbc_world:x", "BBC News"),
        ("cbs_world:c", "CBS News"),
        ("cbs_world:b", "CBS News"),
        ("bbc_world:y", "BBC News"),
    ]
    assert merged.status == "available"
    assert merged.snapshot.document.title == "CBS News · BBC News"
    assert merged.snapshot.document.home_url == ""


def test_merge_dedups_exact_story_urls_only():
    cbs, bbc, _npr = news_providers_for("feeds_news_world")
    merged = merge_news_results(
        (cbs, bbc),
        {
            "cbs_world": _result(
                _item("a", 300, "https://Wire.Example/story#top"),
                _item("b", 250, "https://wire.example/story?page=2"),
            ),
            "bbc_world": _result(
                _item("x", 200, "https://wire.example/story"),
                # Same headline, different outlet URL: never inferred equivalent.
                _item("y", 150, "https://bbc.example/story", title="Story a"),
            ),
        },
    )
    assert [item.item_id for item in merged.snapshot.document.items] == [
        "cbs_world:a", "cbs_world:b", "bbc_world:y",
    ]


def test_merge_remaps_local_artwork_to_namespaced_ids_and_caps_items():
    cbs, bbc, _npr = news_providers_for("feeds_news_world")
    merged = merge_news_results(
        (cbs, bbc),
        {
            "cbs_world": _result(*(_item(str(i), 1000 - i) for i in range(30)),
                                 artwork=(("0", "file:///a.png"), ("29", "file:///z.png"))),
            "bbc_world": _result(*(_item(f"b{i}", 500 - i) for i in range(30)),
                                 artwork=(("b0", "file:///b.png"),)),
        },
        max_items=31,
    )
    items = merged.snapshot.document.items
    assert len(items) == 31
    assert dict(merged.local_artwork_by_item) == {
        "cbs_world:0": "file:///a.png",
        "cbs_world:29": "file:///z.png",
        "bbc_world:b0": "file:///b.png",
    }


def test_a_failed_publisher_never_blanks_the_healthy_ones():
    cbs, bbc, npr = news_providers_for("feeds_news_world")
    merged = merge_news_results(
        (cbs, bbc, npr),
        {"cbs_world": _failed(), "bbc_world": _result(_item("x", 200)), "npr_world": _failed()},
    )
    assert [item.item_id for item in merged.snapshot.document.items] == ["bbc_world:x"]
    assert merged.status == "available"
    stale = merge_news_results(
        (cbs, bbc),
        {"cbs_world": _result(_item("a", 1), status="stale_cache"),
         "bbc_world": _result(_item("x", 2), status="backoff_cache")},
    )
    assert stale.status == "stale_cache"
    nothing = merge_news_results((cbs, bbc), {"cbs_world": _failed("FeedEmptyError"), "bbc_world": _failed()})
    assert nothing.snapshot is None and nothing.status == "unavailable"
    assert nothing.failure == "FeedEmptyError"


# --- runtime -----------------------------------------------------------------


class _Manager:
    def __init__(self):
        self.submissions = 0

    def submit_io_task(self, work, *, callback, **_kwargs):
        self.submissions += 1
        try:
            callback(SimpleNamespace(success=True, result=work()))
        except Exception as exc:
            callback(SimpleNamespace(success=False, result=None, error=exc))


class _Source:
    def __init__(self, cached, fresh):
        self.cached = cached
        self.fresh = fresh
        self.refresh_calls = 0

    def load_cached(self):
        return self.cached

    def refresh(self, *, force=False):
        self.refresh_calls += 1
        return self.fresh


class _Consumer:
    def __init__(self, generation=5):
        self._runtime_generation = generation
        self.accepted = []

    def is_feed_consumer_alive(self):
        return True

    def on_feed_runtime_result(self, result, *, from_cache):
        self.accepted.append((result, from_cache))


def setup_function():
    feed_runtime.reset_shared_feed_runtime_for_tests()


def teardown_function():
    feed_runtime.reset_shared_feed_runtime_for_tests()


def _service(monkeypatch, sources, *, widget_id="feeds_news_world", values=None):
    def source_for(_owner, state):
        state.source = sources[state.spec.cache_key]
        return state.source

    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", source_for)
    config = NewsFeedConfig.from_mapping(widget_id, values or {"enabled": True})
    manager = _Manager()
    service = NewsRuntimeService(
        config=NewsRuntimeConfig.from_news(config), generation=5, manager=manager,
        ui_dispatch=lambda fn: fn(), schedule=lambda _delay, _cb: (lambda: None), task_priority=0,
    )
    consumer = _Consumer()
    service.attach_consumer(consumer)
    return service, consumer, manager


def test_news_service_runs_each_publisher_as_an_ordinary_lease_on_the_shared_owner(monkeypatch):
    no_cache = FeedRefreshResult("unavailable", None, FeedHealth(), failure="no_cache")
    sources = {
        "news_cbs_world": _Source(no_cache, _result(_item("a", 300))),
        "news_bbc_world": _Source(no_cache, _result(_item("x", 200))),
        "news_npr_world": _Source(no_cache, _failed()),
    }
    service, consumer, _manager = _service(monkeypatch, sources)
    assert service.start() is True
    assert service.is_running() is True
    assert feed_runtime.shared_feed_owner_count() == 1
    # Cache misses never publish a failed card; the first merge carries stories.
    assert consumer.accepted
    assert all(result.snapshot is not None for result, _cached in consumer.accepted)
    final, from_cache = consumer.accepted[-1]
    assert [item.item_id for item in final.snapshot.document.items] == ["cbs_world:a", "bbc_world:x"]
    assert from_cache is False
    assert all(source.refresh_calls == 1 for source in sources.values())

    service.retire()
    assert service.is_retired() is True
    assert feed_runtime.shared_feed_owner_count() == 0


def test_news_service_reports_unavailable_only_after_every_publisher_failed(monkeypatch):
    no_cache = FeedRefreshResult("unavailable", None, FeedHealth(), failure="no_cache")
    sources = {
        f"news_{pid}": _Source(no_cache, _failed()) for pid in ("cbs_us", "abc_us", "npr_us")
    }
    service, consumer, _manager = _service(monkeypatch, sources, widget_id="feeds_news_us")
    service.start()
    assert len(consumer.accepted) == 1
    result, from_cache = consumer.accepted[0]
    assert result.snapshot is None and result.status == "unavailable"
    assert from_cache is False
    service.retire()


def test_news_service_publishes_cached_stories_first_and_only_selected_publishers(monkeypatch):
    cached = _result(_item("old", 50), status="available")
    sources = {"news_bbc_world": _Source(cached, _result(_item("new", 60)))}
    service, consumer, manager = _service(
        monkeypatch, sources, values={"enabled": True, "providers": ["bbc_world"]})
    service.start()
    first, first_cached = consumer.accepted[0]
    assert [item.item_id for item in first.snapshot.document.items] == ["bbc_world:old"]
    assert first_cached is True
    assert manager.submissions >= 1
    service.retire()


def test_news_runtime_service_is_built_for_news_ids_only():
    from rendering.widget_runtime_services import _RUNTIME_SERVICE_SPECS, _build_feed_service

    for widget_id in NEWS_WIDGET_IDS:
        assert _RUNTIME_SERVICE_SPECS[widget_id] is _RUNTIME_SERVICE_SPECS["feeds_custom_1"]
    service = _build_feed_service("feeds_news_tech", {"feeds_news_tech": {"enabled": True}})
    assert isinstance(service, NewsRuntimeService)
    assert [p.provider_id for p in service.config.providers] == ["cbs_technology", "abc_technology", "ars_all"]
    service.retire()
    assert _build_feed_service("feeds_news_tech", {"feeds_news_tech": {"providers": []}}) is None


# --- admission and presentation ------------------------------------------------


def test_enabled_news_cards_are_admitted_after_the_custom_slots():
    from rendering.quick.widgets.family_binder import FeedFamilyAdapter

    widgets = {
        "feeds_custom_2": {"enabled": True, "feed_url": "https://example.test/rss"},
        "feeds_news_tech": {"enabled": True},
        "feeds_news_world": {"enabled": True, "providers": []},  # no publisher: no dead card
        "feeds_news_us": {"enabled": False},
    }
    assert FeedFamilyAdapter().enabled_instance_ids(widgets) == ("feeds_custom_2", "feeds_news_tech")


def test_monogram_ordinals_span_custom_and_news_cards():
    from rendering.quick.widgets.feeds import _monogram_ordinal

    widgets = {
        "feeds_custom_1": {"enabled": True, "name": "TechCrunch", "feed_url": "https://tc.example/feed"},
        "feeds_news_tech": {"enabled": True},
        "feeds_news_world": {"enabled": True},
    }
    assert _monogram_ordinal(widgets, "feeds_custom_1") == 1
    assert _monogram_ordinal(widgets, "feeds_news_tech") == 2
    assert _monogram_ordinal(widgets, "feeds_news_world") == 0


def _model(widget_id, values):
    from rendering.quick.widgets.feeds import (
        FeedPresentationConfig,
        FeedPresentationModel,
        FeedPresentationStyle,
    )

    config = FeedPresentationConfig.from_widgets_mapping({widget_id: values}, widget_id=widget_id)
    return FeedPresentationModel(
        config, FeedPresentationStyle.project(config, dict(require_canonical_default("widgets.shadows"))))


def test_only_news_cards_show_source_attribution(qt_app):
    news = _model("feeds_news_world", {"enabled": True})
    custom = _model("feeds_custom_1", {"enabled": True, "feed_url": "https://example.test/rss"})
    assert news.showSourceAttribution is True
    assert news.displayName == "World News"
    assert news.monogram == "W"
    assert custom.showSourceAttribution is False


def test_a_first_run_cache_miss_keeps_a_card_loading_instead_of_failed(qt_app):
    model = _model("feeds_custom_1", {"enabled": True, "feed_url": "https://example.test/rss"})
    model._active = True  # Test-only consumer admission; no runtime owner.
    assert model.viewState == "loading"
    model.on_feed_runtime_result(
        FeedRefreshResult("unavailable", None, FeedHealth(), failure="no_cache"), from_cache=True)
    assert model.viewState == "loading"
    model.on_feed_runtime_result(_failed(), from_cache=False)
    assert model.viewState == "error"


def test_news_rows_name_their_publisher_in_real_qml(qt_app):
    """Load FeedPresentation.qml without showing a window and read the row text."""
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickItem

    def texts(item: QQuickItem) -> list[str]:
        found = []
        value = item.property("text") if item.objectName() == "shadowedText" else None
        if isinstance(value, str) and value:
            found.append(value)
        for child in item.childItems():
            found.extend(texts(child))
        return found

    now = 1_900_000_000.0
    merged = merge_news_results(
        news_providers_for("feeds_news_world"),
        {"cbs_world": _result(_item("a", int(now) - 7200, title="Harbour reopens")),
         "bbc_world": _result(_item("x", int(now) - 60, title="Summit opens"))},
    )
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    for widget_id, values, expect_publisher in (
        ("feeds_news_world", {"enabled": True, "show_images": False}, True),
        ("feeds_custom_1", {"enabled": True, "feed_url": "https://example.test/rss", "show_images": False}, False),
    ):
        for view_mode in ("list", "grid", "compact"):
            model = _model(widget_id, dict(values, view_mode=view_mode))
            model._active = True
            model.on_feed_runtime_result(merged, from_cache=False)
            component = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_ROOT / "FeedPresentation.qml")))
            root = component.createWithInitialProperties({"feedModel": model})
            assert isinstance(root, QQuickItem), [error.toString() for error in component.errors()]
            root.setWidth(560.0)
            root.setHeight(420.0)
            qt_app.processEvents()
            shown = texts(root)
            # List and Grid delegates both exist; the hidden view keeps its rows.
            publishers = {text.split(" · ")[0] for text in shown
                          if text.startswith(("BBC NEWS · ", "CBS NEWS · "))}
            if expect_publisher:
                assert publishers == {"BBC NEWS", "CBS NEWS"}, (view_mode, shown)
            else:
                assert publishers == set(), (view_mode, shown)
            root.deleteLater()
            qt_app.processEvents()


def test_news_cards_inherit_the_custom_1_header_theme_roles():
    from ui.widget_visual_roles import WIDGET_VISUAL_ROLE_PARENTS

    for widget_id in NEWS_WIDGET_IDS:
        for role in ("fill", "border", "text"):
            assert WIDGET_VISUAL_ROLE_PARENTS[f"{widget_id}.header.{role}"] == f"feeds_custom_1.header.{role}"


# --- Settings ------------------------------------------------------------------


def test_settings_news_cards_round_trip_publisher_choices(qt_app, settings_manager):
    from rendering.widget_descriptors import (
        apply_widget_section_save_results,
        collect_widget_section_save_results,
    )
    from ui.tabs.widgets_tab import WidgetsTab
    from ui.tabs.widgets_tab_feeds import (
        feed_attr,
        load_feeds_settings,
        news_provider_attr,
        save_feeds_settings,
    )

    settings_manager.set("widgets.family_activation.feeds", True)
    tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "feeds"})
    try:
        for category in NEWS_CATEGORIES:
            checkbox = getattr(tab, feed_attr(category.widget_id, "enabled"))
            assert checkbox.text() == f"Enable {category.label}"
            container = getattr(tab, f"_{category.widget_id}_controls_container")
            checkbox.setChecked(True)
            assert container.isHidden() is False
            checkbox.setChecked(False)
            assert container.isHidden() is True

        load_feeds_settings(tab, {
            "feeds_news_world": {"enabled": True, "providers": ["bbc_world"], "view_mode": "grid"},
            "feeds_news_gaming": {"enabled": True, "item_limit": 20},
        })
        assert getattr(tab, news_provider_attr("feeds_news_world", "bbc_world")).isChecked()
        assert not getattr(tab, news_provider_attr("feeds_news_world", "cbs_world")).isChecked()
        getattr(tab, news_provider_attr("feeds_news_world", "npr_world")).setChecked(True)

        by_id = dict(zip(FEED_WIDGET_IDS, save_feeds_settings(tab)))
        assert by_id["feeds_news_world"]["providers"] == ["bbc_world", "npr_world"]
        assert by_id["feeds_news_world"]["view_mode"] == "grid"
        assert by_id["feeds_news_world"]["enabled"] is True
        assert "name" not in by_id["feeds_news_world"]
        assert by_id["feeds_news_gaming"]["item_limit"] == 20
        assert by_id["feeds_news_gaming"]["providers"] == ["ars_gaming", "pcgamer_all", "eurogamer_all"]
        assert by_id["feeds_news_us"]["enabled"] is False

        results = collect_widget_section_save_results(tab, {})
        config: dict = {}
        apply_widget_section_save_results(config, results)
        assert config["feeds_news_world"]["providers"] == ["bbc_world", "npr_world"]
        for widget_id in NEWS_WIDGET_IDS:
            for bucket in ("source", "content", "layout", "appearance"):
                key = f"{widget_id.removeprefix('feeds_')}_{bucket}"
                assert isinstance(tab.get_widget_bucket_state("feeds", key), bool)
    finally:
        tab.deleteLater()
