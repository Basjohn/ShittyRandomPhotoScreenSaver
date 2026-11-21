"""1C.9: Sources' lists wear the Themes list's style, through the real SettingsDialog (never shown).

One list style owner (``shared_styles.SETTINGS_LIST_STYLE``) gives the Themes catalogue and Sources' Folders and online
lists their typography and row geometry; the online rows' delegate draws with that font and sets none; a pool row is
a tag, an arrow and the name in their theme roles (never a slanted string); a feed URL elides in the middle short of
its mark; the size grip is three solid strokes. Expectations come from the owners (tokens, roles, the list's own
font), never from pinned wording, sizes or colours. No network: sockets and DNS are stubbed to fail loudly.
"""
from __future__ import annotations

import inspect
import re
import socket
import time

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QApplication

from core.animation import AnimationManager
from core.feeds.cache import FeedCacheStore
from core.feeds.models import FeedCacheRecord, FeedHealth
from core.feeds.normalization import endpoint_fingerprint
from core.settings.settings_manager import SettingsManager
from sources.rss import source_health
from sources.rss.pools import WALLPAPER_POOLS, WallpaperPoolSelection, write_pool_selection
from ui.settings_dialog import SettingsDialog
from ui.settings_theme_runtime import get_active_settings_theme
from ui.tabs import online_source_rows as rows
from ui.tabs import shared_styles

pytestmark = pytest.mark.qt

LONG_FEED = "https://long.invalid/" + "/".join(f"segment{number}" for number in range(60)) + "/tail-end.xml"
FEEDS = ("https://valid.invalid/feed.xml", LONG_FEED)


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
def dialog(tmp_path, monkeypatch, no_network):
    QApplication.instance() or QApplication([])
    cache = tmp_path / "rss_cache"
    monkeypatch.setattr(source_health, "_default_cache_dir", lambda: cache)
    store = FeedCacheStore(source_health.feed_store_dir(cache))
    source_id = source_health.custom_feed_source_id(FEEDS[0])
    store.write(source_health.source_cache_key(source_id),
                FeedCacheRecord(source_id=source_id, endpoint_fingerprint=endpoint_fingerprint(source_id),
                                health=FeedHealth(last_checked_at=time.time(), last_success_at=time.time())))
    manager = SettingsManager(application="settings_list_style", storage_base_dir=tmp_path / "profile")
    manager.set("sources.folders", [str(tmp_path)])
    write_pool_selection(manager, WallpaperPoolSelection(True, (WALLPAPER_POOLS[0].pool_id,), "latest"))
    manager.set("sources.rss_feeds", list(FEEDS))
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    try:
        yield dialog
    finally:
        dialog.close()
        QCoreApplication.processEvents()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QCoreApplication.processEvents()
        assert manager.flush(timeout=5.0)


def _tab(dialog, key):
    dialog._switch_tab(dialog._tab_index_for_key(key), animate=False)
    QCoreApplication.processEvents()
    return dialog._get_tab_instance(key)


def _font_signature(font: QFont):
    return (tuple(font.families()), font.pointSizeF(), font.pixelSize(), font.weight(), font.italic())


def _row_heights(view):
    return {view.visualItemRect(view.item(row)).height() for row in range(view.count())}


def test_sources_lists_and_the_themes_list_share_one_list_style(dialog):
    sources = _tab(dialog, "sources")
    themes = _tab(dialog, "themes")
    lists = (sources.rss_list, sources.folder_list, themes.theme_list, themes.widget_theme_list)
    for view in lists:
        # Bound to the one shared owner (live across theme changes), nothing else.
        assert shared_styles._LIVE_STYLE_BUNDLES[view][1] == ("SETTINGS_LIST_STYLE",), view
    reference = _font_signature(themes.theme_list.font())
    assert all(_font_signature(view.font()) == reference for view in lists)
    assert _row_heights(sources.rss_list) == _row_heights(themes.theme_list) == {
        max(_row_heights(themes.theme_list))}


def test_the_online_rows_delegate_sets_no_font_and_fakes_no_face(dialog, monkeypatch):
    source = inspect.getsource(rows)
    assert not re.search(r"\bQFont\(|setItalic|setBold|setWeight|setPointSize|setPixelSize|setFamil|setStyle\(",
                         source)
    sources = _tab(dialog, "sources")
    view = sources.rss_list
    view.resize(900, 300)
    fonts = []
    original = QPainter.setFont

    def spy(painter, font):
        fonts.append(QFont(font))
        return original(painter, font)

    monkeypatch.setattr(QPainter, "setFont", spy)
    view.viewport().grab()
    assert fonts, "the pool row paints its parts with the list's font"
    assert all(_font_signature(font) == _font_signature(view.font()) for font in fonts)


def test_a_pool_row_is_its_tag_arrow_and_name_in_their_theme_roles(dialog, monkeypatch):
    sources = _tab(dialog, "sources")
    view = sources.rss_list
    view.resize(900, 300)
    (pool_item,) = rows.rows_of_kind(view, rows.POOL)
    drawn = []
    original = QPainter.drawText

    def spy(painter, *args):
        texts = [arg for arg in args if isinstance(arg, str)]
        if texts:
            drawn.append((texts[0], painter.pen().color().rgba()))
        return original(painter, *args)

    monkeypatch.setattr(QPainter, "drawText", spy)
    view.viewport().grab()
    theme = get_active_settings_theme()

    def rgba(token):
        return QColor(*theme.color(token).as_tuple()).rgba()

    expected = [(rows.POOL_TAG, rgba(rows.TAG_TOKEN)), (rows.POOL_ARROW, rgba(rows.ARROW_TOKEN)),
                (pool_item.data(rows.NAME_ROLE), rgba(rows.NAME_TOKEN))]
    assert drawn[:3] == expected
    assert pool_item.data(rows.NAME_ROLE) == WALLPAPER_POOLS[0].label
    assert rows.POOL_TAG == rows.POOL_TAG.upper()


def test_a_long_feed_url_elides_in_the_middle_and_stops_short_of_its_mark(dialog, monkeypatch):
    sources = _tab(dialog, "sources")
    view = sources.rss_list
    view.resize(520, 300)
    QCoreApplication.processEvents()
    modes = []
    original = QFontMetrics.elidedText

    def spy(metrics, text, mode, width, *args):
        modes.append((text, mode, width))
        return original(metrics, text, mode, width, *args)

    monkeypatch.setattr(QFontMetrics, "elidedText", spy)
    image = view.viewport().grab().toImage()
    assert (LONG_FEED, Qt.TextElideMode.ElideMiddle) in {(text, mode) for text, mode, _ in modes}
    assert view.horizontalScrollBar().maximum() == 0
    # No ink in the gap between the text area and the mark (the row's own fill only).
    (item,) = [item for item in rows.rows_of_kind(view, rows.FEED) if item.data(rows.KEY_ROLE) == LONG_FEED]
    rect = view.visualItemRect(item)
    mark = rows.OnlineSourceRowDelegate.mark_rect(rect, view.font())
    scale = image.devicePixelRatio()
    gap_left = int((mark.left() - rows.OnlineSourceRowDelegate.GAP + 2) * scale)
    gap_right = int((mark.left() - 2) * scale)
    background = image.pixelColor(gap_right, int((rect.top() + 2) * scale))
    for x in range(gap_left, gap_right):
        for y in range(int((rect.top() + 4) * scale), int((rect.bottom() - 4) * scale)):
            colour = image.pixelColor(x, y)
            assert abs(colour.red() - background.red()) + abs(colour.green() - background.green()) \
                + abs(colour.blue() - background.blue()) < 12, (x, y)


def test_four_settings_grips_are_invisible_with_native_resize_hit_targets(dialog):
    grips = dialog.corner_size_grips
    assert set(grips) == {"top_left", "top_right", "bottom_left", "bottom_right"}
    assert dialog.size_grip is grips["bottom_right"]
    assert all(not grip.isHidden() for grip in grips.values())
    # The old three diagonal strokes are deliberately removed. The native
    # QSizeGrip remains the resize event owner; decorative paint is empty.
    from ui.settings_dialog import CornerSizeGrip
    import inspect
    assert 'painter.drawLine' not in inspect.getsource(CornerSizeGrip.paintEvent)
    assert len({grip.objectName() for grip in grips.values()}) == 4


def _bar_colours(view):
    """The handle colour a list's own stylesheet gives its vertical scrollbar, or None when it styles none."""
    match = re.search(r"QScrollBar::handle:vertical:hover[^{]*\{[^}]*background:\s*([^;]+);", view.styleSheet())
    return match.group(1).strip() if match else None


def test_the_content_lists_and_the_filter_popup_scrollbars_are_the_themes_not_the_platforms(dialog):
    """1B.11 / 1C.9: a list's bar is the shared style's themed bar (the platform's native bar ignores the theme)."""
    from ui.widgets.theme_filter import ThemedCompleterPopup
    sources = _tab(dialog, "sources")
    themes = _tab(dialog, "themes")
    popup = ThemedCompleterPopup()
    owners = (sources.rss_list, sources.folder_list, themes.theme_list, themes.widget_theme_list, popup)
    from ui.settings_theme_qss import render_qss_color
    accent = render_qss_color(get_active_settings_theme().color("control.list.selected_accent"))
    for view in owners:
        assert accent in (_bar_colours(view) or ""), view
        assert "QScrollBar:vertical" in view.styleSheet(), view
