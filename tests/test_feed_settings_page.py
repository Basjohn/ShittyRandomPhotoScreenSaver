"""The Feeds Settings page: News/Custom buckets, closed by default, one open per level."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.feeds.news import NEWS_CATEGORIES

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def feeds_tab(qt_app, settings_manager):
    from ui.tabs.widgets_tab import WidgetsTab

    settings_manager.set("widgets.family_activation.feeds", True)
    tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "feeds"})
    try:
        yield tab
    finally:
        tab.deleteLater()


def _toggles(tab):
    from PySide6.QtWidgets import QToolButton

    root = tab._feeds_container
    return [button for button in root.findChildren(QToolButton) if button.isCheckable()]


def _toggle(tab, title, within=None):
    matches = [
        button for button in _toggles(tab)
        if button.text() == title and (within is None or within.isAncestorOf(button))
    ]
    assert len(matches) == 1, (title, len(matches))
    return matches[0]


def _body(toggle):
    """The bucket body follows its toggle row in the host layout."""
    host = toggle.parentWidget().layout()
    for index in range(host.count()):
        item = host.itemAt(index)
        if item.layout() is not None and item.layout().indexOf(toggle) >= 0:
            return host.itemAt(index + 1).widget()
    raise AssertionError(toggle.text())


def test_page_is_news_then_custom_with_nested_card_buckets(feeds_tab):
    tab = feeds_tab
    news = _toggle(tab, "News")
    custom = _toggle(tab, "Custom")
    news_body, custom_body = _body(news), _body(custom)
    # Top level: exactly the two group buckets.
    top = [b for b in _toggles(tab) if not news_body.isAncestorOf(b) and not custom_body.isAncestorOf(b)]
    assert [b.text() for b in top] == ["News", "Custom"]

    for category in NEWS_CATEGORIES:
        card = _toggle(tab, category.label, news_body)
        body = _body(card)
        enable = getattr(tab, f"{category.widget_id}_enabled")
        assert body.isAncestorOf(enable) and enable.text() == f"Enable {category.label}"
        leaves = [b.text() for b in _toggles(tab) if body.isAncestorOf(b)]
        assert leaves == ["Sources", "Content", "Layout", "Appearance"]
    for slot in (1, 2, 3, 4):
        card = _toggle(tab, f"Custom {slot}", custom_body)
        leaves = [b.text() for b in _toggles(tab) if _body(card).isAncestorOf(b)]
        assert leaves == ["Source", "Content", "Layout", "Appearance"]

    # Every bucket starts closed.
    assert not any(button.isChecked() for button in _toggles(tab))


def test_one_bucket_is_open_per_level_and_parents_stay_open(feeds_tab):
    tab = feeds_tab
    news, custom = _toggle(tab, "News"), _toggle(tab, "Custom")
    news_body = _body(news)
    world = _toggle(tab, "World News", news_body)
    us = _toggle(tab, "US News", news_body)
    world_body = _body(world)
    sources = _toggle(tab, "Sources", world_body)
    content = _toggle(tab, "Content", world_body)

    news.click()
    world.click()
    sources.click()
    assert news.isChecked() and world.isChecked() and sources.isChecked()
    content.click()  # a sibling leaf closes Sources, never its card or group
    assert content.isChecked() and not sources.isChecked()
    assert world.isChecked() and news.isChecked()
    us.click()  # a sibling card closes World News, never the News group
    assert us.isChecked() and not world.isChecked() and news.isChecked()
    custom.click()
    assert custom.isChecked() and not news.isChecked()

    stored = {key for key, value in tab._widget_bucket_state.items() if value and key.startswith("feeds:")}
    # One remembered bucket per scope: the group, each card's last leaf.
    assert stored == {"feeds:custom", "feeds:news_us", "feeds:news_world_content"}


def test_one_refresh_control_for_the_whole_family(feeds_tab):
    from PySide6.QtWidgets import QSpinBox

    minutes = [box for box in feeds_tab._feeds_container.findChildren(QSpinBox) if box.suffix() == " min"]
    assert minutes == [feeds_tab.feeds_refresh_minutes]


def test_page_carries_no_explanatory_fluff():
    source = (ROOT / "ui" / "tabs" / "widgets_tab_feeds.py").read_text(encoding="utf-8")
    for retired in (
        "Not tested in this Settings session",
        "Runtime is cache-first",
        "SRPSS does not rank",
        "One publisher failing keeps",
        "Layout & Typography",
        "Content & Refresh",
    ):
        assert retired not in source, retired
