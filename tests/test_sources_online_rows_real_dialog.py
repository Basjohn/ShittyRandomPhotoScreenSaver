"""Sources' online list on the real SettingsDialog: one row per active Just Make It Work pool and per custom feed,
each with the status its stored health says (valid, failing, untried), read with no network at all.

Pool ids, labels and the row prefix come from their canonical owners; stored health is written by the test through
the real feed store at the coordinator's own record names. DNS and sockets are stubbed to fail loudly.
"""
from __future__ import annotations

import socket
import time

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from core.animation import AnimationManager
from core.feeds.cache import FeedCacheStore
from core.feeds.models import FeedCacheRecord, FeedHealth
from core.feeds.normalization import endpoint_fingerprint
from core.settings.settings_manager import SettingsManager
from sources.rss import source_health
from sources.rss.pools import WALLPAPER_POOLS, WallpaperPoolSelection, pool_endpoint_source_ids, write_pool_selection
from ui.settings_dialog import SettingsDialog
from ui.tabs import online_source_rows as rows

pytestmark = pytest.mark.qt

FEEDS = ("https://valid.invalid/feed.xml", "https://broken.invalid/feed.xml")


@pytest.fixture
def no_network(monkeypatch):
    touched = []

    def refuse(*args, **_kwargs):
        touched.append(args[:1])
        raise OSError("network is stubbed out in this test")

    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", lambda self, *a: refuse(*a))
    yield touched
    assert touched == [], f"Settings touched the network: {touched}"


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    root = tmp_path / "rss_cache"
    monkeypatch.setattr(source_health, "_default_cache_dir", lambda: root)
    return root


def _pools():
    """Three active pools: two single-endpoint ones and the multi-subject one (derived, not named)."""
    single = [pool for pool in WALLPAPER_POOLS if len(pool_endpoint_source_ids(pool.pool_id)) == 1]
    multi = [pool for pool in WALLPAPER_POOLS if len(pool_endpoint_source_ids(pool.pool_id)) > 1]
    return single[0], single[1], multi[0]


def _store(cache_dir, source_id, health):
    store = FeedCacheStore(source_health.feed_store_dir(cache_dir))
    store.write(source_health.source_cache_key(source_id),
                FeedCacheRecord(source_id=source_id, endpoint_fingerprint=endpoint_fingerprint(source_id), health=health))


def _valid(at):
    return FeedHealth(last_checked_at=at, last_success_at=at)


def _failing(at, reason):
    return FeedHealth(last_checked_at=at, last_success_at=at - 3600, consecutive_failures=2, last_failure=reason)


@pytest.fixture
def manager(tmp_path):
    QApplication.instance() or QApplication([])
    manager = SettingsManager(application="sources_online_rows", storage_base_dir=tmp_path)
    manager.set("sources.folders", [str(tmp_path)])
    yield manager
    assert manager.flush(timeout=5.0)


def _sources_tab(manager):
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    dialog._switch_tab(dialog._tab_index_for_key("sources"), animate=False)
    return dialog, dialog._get_tab_instance("sources")


def _close(dialog):
    dialog.close()
    QCoreApplication.processEvents()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _by_key(tab):
    return {item.data(rows.KEY_ROLE): item for kind in (rows.POOL, rows.FEED)
            for item in rows.rows_of_kind(tab.rss_list, kind)}


def test_active_pools_and_custom_feeds_are_rows_with_their_stored_status(manager, cache_dir, no_network):
    valid_pool, failing_pool, multi_pool = _pools()
    now = time.time()
    _store(cache_dir, source_health.pool_source_id(valid_pool.pool_id), _valid(now))
    _store(cache_dir, source_health.pool_source_id(failing_pool.pool_id), _failing(now, "HTTP 503"))
    _store(cache_dir, source_health.custom_feed_source_id(FEEDS[0]), _valid(now))
    _store(cache_dir, source_health.custom_feed_source_id(FEEDS[1]), _failing(now, "not a feed"))
    selected = (multi_pool.pool_id, failing_pool.pool_id, valid_pool.pool_id)
    write_pool_selection(manager, WallpaperPoolSelection(True, selected, "latest"))
    manager.set("sources.rss_feeds", list(FEEDS))
    dialog, tab = _sources_tab(manager)
    try:
        pool_rows = rows.rows_of_kind(tab.rss_list, rows.POOL)
        expected = [pool for pool in WALLPAPER_POOLS if pool.pool_id in selected]
        assert [item.data(rows.KEY_ROLE) for item in pool_rows] == [pool.pool_id for pool in expected]
        assert [item.text() for item in pool_rows] == [rows.POOL_ROW_PREFIX + pool.label for pool in expected]
        assert [item.data(rows.KEY_ROLE) for item in rows.rows_of_kind(tab.rss_list, rows.FEED)] == list(FEEDS)
        # Pool rows are managed by the chooser: never selectable here.
        assert all(not item.flags() & Qt.ItemFlag.ItemIsSelectable for item in pool_rows)
        status = {key: item.data(rows.STATUS_ROLE) for key, item in _by_key(tab).items()}
        assert status == {valid_pool.pool_id: source_health.VALID, failing_pool.pool_id: source_health.FAILING,
                          multi_pool.pool_id: source_health.UNTRIED,
                          FEEDS[0]: source_health.VALID, FEEDS[1]: source_health.FAILING}
        # The tooltip says why: the stored failure reason.
        assert "HTTP 503" in _by_key(tab)[failing_pool.pool_id].toolTip()
        assert "not a feed" in _by_key(tab)[FEEDS[1]].toolTip()
        # The summary stays.
        assert str(len(selected)) in tab.pool_status_label.text()

        # A multi-endpoint pool reads its most recently checked endpoint; the tab's refresh edge picks it up.
        first, second = pool_endpoint_source_ids(multi_pool.pool_id)[:2]
        _store(cache_dir, source_health.pool_source_id(first), _valid(now - 60))
        _store(cache_dir, source_health.pool_source_id(second), _failing(now, "HTTP 429"))
        assert _by_key(tab)[multi_pool.pool_id].data(rows.STATUS_ROLE) == source_health.UNTRIED
        tab._load_settings()
        assert _by_key(tab)[multi_pool.pool_id].data(rows.STATUS_ROLE) == source_health.FAILING

        # Remove Selected never removes a pool row.
        tab.rss_list.setCurrentItem(rows.rows_of_kind(tab.rss_list, rows.POOL)[0])
        tab._remove_rss()
        assert [i.data(rows.KEY_ROLE) for i in rows.rows_of_kind(tab.rss_list, rows.POOL)] == [p.pool_id for p in expected]
        assert manager.get("sources.rss_feeds") == list(FEEDS)
    finally:
        _close(dialog)


def _mark_colours(list_widget, item):
    """The distinct colours painted inside an item's mark box (the list rendered off-screen with grab())."""
    image = list_widget.viewport().grab().toImage()   # renders off-screen; never shown
    scale = image.devicePixelRatio()                  # device pixels (150 % displays)
    box = rows.OnlineSourceRowDelegate.mark_rect(list_widget.visualItemRect(item))
    colours = set()
    for x in range(int(box.left() * scale), int((box.right() + 1) * scale)):
        for y in range(int(box.top() * scale), int((box.bottom() + 1) * scale)):
            colour = image.pixelColor(x, y)
            colours.add((colour.red(), colour.green(), colour.blue()))
    return colours


def _has(colours, token):
    from ui.settings_theme_runtime import get_active_settings_theme
    target = QColor(*get_active_settings_theme().color(token).as_tuple())
    return any(abs(r - target.red()) + abs(g - target.green()) + abs(b - target.blue()) < 24 for r, g, b in colours)


def test_marks_are_painted_in_the_status_theme_roles(manager, cache_dir, no_network):
    now = time.time()
    _store(cache_dir, source_health.custom_feed_source_id(FEEDS[0]), _valid(now))
    _store(cache_dir, source_health.custom_feed_source_id(FEEDS[1]), _failing(now, "timeout"))
    write_pool_selection(manager, WallpaperPoolSelection(False, (), "latest"))
    manager.set("sources.rss_feeds", list(FEEDS))
    dialog, tab = _sources_tab(manager)
    try:
        tab.rss_list.resize(640, 200)
        valid, failing = rows.rows_of_kind(tab.rss_list, rows.FEED)
        assert _has(_mark_colours(tab.rss_list, valid), rows.MARK_TOKENS[source_health.VALID])
        assert not _has(_mark_colours(tab.rss_list, valid), rows.MARK_TOKENS[source_health.FAILING])
        assert _has(_mark_colours(tab.rss_list, failing), rows.MARK_TOKENS[source_health.FAILING])
    finally:
        _close(dialog)


def test_no_pools_and_no_feeds_is_one_empty_state_row(manager, cache_dir, no_network):
    write_pool_selection(manager, WallpaperPoolSelection(False, (), "latest"))
    manager.set("sources.rss_feeds", [])
    dialog, tab = _sources_tab(manager)
    try:
        assert tab.rss_list.count() == 1
        assert tab.rss_list.item(0).data(rows.KIND_ROLE) == rows.EMPTY
        assert not rows.rows_of_kind(tab.rss_list, rows.POOL) and not rows.rows_of_kind(tab.rss_list, rows.FEED)
    finally:
        _close(dialog)


def test_the_coordinator_names_its_records_as_settings_reads_them(tmp_path, no_network):
    """One naming owner: the coordinator's FeedSource for a custom URL and for a pool endpoint uses the record
    names and store directory the Settings health read uses (constructing a source fetches nothing)."""
    from sources.rss.coordinator import RSSCoordinator
    from sources.rss.pools import pool_endpoint

    pool = _pools()[2]
    selection = WallpaperPoolSelection(True, (pool.pool_id,), "latest")
    coordinator = RSSCoordinator(feed_urls=[FEEDS[0]], cache_dir=tmp_path / "rss", pool_selection=selection)
    custom = coordinator._source(coordinator.feed_urls[0])
    endpoint = pool_endpoint(pool.pool_id, "latest")
    pooled = coordinator._source(endpoint.url, pool_endpoint=endpoint)
    assert custom.spec.cache_key == source_health.source_cache_key(source_health.custom_feed_source_id(FEEDS[0]))
    assert pooled.spec.cache_key == source_health.source_cache_key(source_health.pool_source_id(endpoint.source_id))
    assert endpoint.source_id in pool_endpoint_source_ids(pool.pool_id)
    assert coordinator._feed_store.root == source_health.feed_store_dir(tmp_path / "rss")
