"""Guided Setup's sources page and Settings' Sources tab list the same online sources, with the same state.

Both run inside the real SettingsDialog (never shown). Pools are derived from the canonical pool owner, stored
health is written through the real feed store, and DNS/sockets are stubbed to fail loudly. The wizard edits a
draft: a pool turned on there shows and counts in the wizard at once, and reaches the store only at Finish.
"""
from __future__ import annotations

import socket
import time

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from core.animation import AnimationManager
from core.feeds.cache import FeedCacheStore
from core.feeds.models import FeedCacheRecord, FeedHealth
from core.feeds.normalization import endpoint_fingerprint
from core.settings.settings_manager import SettingsManager
from sources.rss import source_health
from sources.rss.pools import (WALLPAPER_POOLS, WallpaperPoolSelection, online_source_count, read_pool_selection,
                               write_pool_selection)
from ui.settings_dialog import SettingsDialog
from ui.tabs import online_source_rows as rows

pytestmark = pytest.mark.qt

FEED = "https://valid.invalid/feed.xml"


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


@pytest.fixture
def manager(tmp_path):
    QApplication.instance() or QApplication([])
    manager = SettingsManager(application="guided_online_sources", storage_base_dir=tmp_path)
    manager.set("sources.folders", [str(tmp_path)])
    yield manager
    assert manager.flush(timeout=5.0)


def _store_valid(cache_dir, pool_id):
    at = time.time()
    store = FeedCacheStore(source_health.feed_store_dir(cache_dir))
    source_id = source_health.pool_source_id(pool_id)
    store.write(source_health.source_cache_key(source_id),
                FeedCacheRecord(source_id=source_id, endpoint_fingerprint=endpoint_fingerprint(source_id),
                                health=FeedHealth(last_checked_at=at, last_success_at=at)))


def _rows(list_widget):
    """What a list shows: every row's kind, key, text and status, in order."""
    return [(item.data(rows.KIND_ROLE), item.data(rows.KEY_ROLE), item.text(), item.data(rows.STATUS_ROLE))
            for item in (list_widget.item(row) for row in range(list_widget.count()))]


def _open(manager):
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    dialog._switch_tab(dialog._tab_index_for_key("sources"), animate=False)
    tab = dialog._get_tab_instance("sources")
    dialog.run_guided_setup()
    panel = dialog._guided_setup_panel
    panel.show_page("sources")
    return dialog, tab, panel, panel.pages["sources"][0]


def _close(dialog):
    if dialog._guided_setup_panel is not None:
        dialog._guided_setup_panel.close_setup(False)  # drop the draft: no Keep/Discard prompt at close
    dialog.close()
    QCoreApplication.processEvents()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_pools_turned_on_in_settings_are_listed_in_guided_setup_as_in_sources(manager, cache_dir, no_network):
    first, second = WALLPAPER_POOLS[0], WALLPAPER_POOLS[-1]
    _store_valid(cache_dir, first.pool_id)
    write_pool_selection(manager, WallpaperPoolSelection(True, (second.pool_id, first.pool_id), "latest"))
    manager.set("sources.rss_feeds", [FEED])
    dialog, tab, _panel, page = _open(manager)
    try:
        shown = _rows(page.feeds)
        assert [key for kind, key, _text, _status in shown if kind == rows.POOL] == [first.pool_id, second.pool_id]
        assert shown == _rows(tab.rss_list)  # same rows, same text, same valid/untried state
        assert type(page.feeds.itemDelegate()) is type(tab.rss_list.itemDelegate())  # the Settings look
        assert page.feeds_toggle.text() == tab.feeds_toggle.text()  # and the same count
    finally:
        _close(dialog)


def test_a_pool_turned_on_in_guided_setup_shows_at_once_and_reaches_settings_at_finish(manager, cache_dir, no_network):
    pool = WALLPAPER_POOLS[0]
    write_pool_selection(manager, WallpaperPoolSelection(False, (pool.pool_id,), "latest"))
    manager.set("sources.rss_feeds", [])
    dialog, tab, panel, page = _open(manager)
    try:
        assert not rows.rows_of_kind(page.feeds, rows.POOL)
        page.feeds_enabled.setChecked(True)
        assert [item.data(rows.KEY_ROLE) for item in rows.rows_of_kind(page.feeds, rows.POOL)] == [pool.pool_id]
        assert str(online_source_count(panel.settings)) in page.feeds_toggle.text()
        # The draft rule: nothing is saved before Finish.
        assert not read_pool_selection(manager).enabled
        panel.finish()
        QCoreApplication.processEvents()
        assert read_pool_selection(manager).enabled
        assert _rows(tab.rss_list)[0][:2] == (rows.POOL, pool.pool_id)
    finally:
        _close(dialog)


def test_remove_selected_in_guided_setup_removes_a_custom_feed_and_never_a_pool(manager, cache_dir, no_network):
    pool = WALLPAPER_POOLS[0]
    write_pool_selection(manager, WallpaperPoolSelection(True, (pool.pool_id,), "latest"))
    manager.set("sources.rss_feeds", [FEED])
    dialog, _tab, panel, page = _open(manager)
    try:
        page.feeds.setCurrentItem(rows.rows_of_kind(page.feeds, rows.POOL)[0])
        page.remove_custom_feed()
        assert panel.settings.get("sources.rss_feeds") == [FEED]
        page.feeds.setCurrentItem(rows.rows_of_kind(page.feeds, rows.FEED)[0])
        page.remove_custom_feed()
        assert panel.settings.get("sources.rss_feeds") == []
        assert manager.get("sources.rss_feeds") == [FEED]  # the draft, until Finish
        assert [item.data(rows.KEY_ROLE) for item in rows.rows_of_kind(page.feeds, rows.POOL)] == [pool.pool_id]
    finally:
        _close(dialog)
