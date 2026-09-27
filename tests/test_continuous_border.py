"""Seam-free painted borders for buckets, lists and the content area (offscreen, never shown)."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ui.onboarding.common import title_case
from ui.settings_theme import _build_settings_root_stylesheet
from ui.settings_theme_runtime import get_active_settings_theme
from ui.widgets.continuous_border import BucketToggle, OutlinedListWidget, paint_content_frame


def _host():
    host = QWidget()
    host.setStyleSheet(_build_settings_root_stylesheet(get_active_settings_theme()))
    return host, QVBoxLayout(host)


def _edge_alphas(widget, y: int, start: int, stop: int) -> list[int]:
    image = widget.grab().toImage()
    return [image.pixelColor(x, y).alpha() for x in range(start, stop)]


def test_bucket_toggles_are_painted_and_the_large_variant_keeps_its_box(qapp) -> None:
    from ui.tabs.shared_styles import build_bucket_toggle

    host, layout = _host()
    try:
        normal, _, _ = build_bucket_toggle(layout, "Folders")
        large, _, _ = build_bucket_toggle(layout, "Folders", large=True)
        assert isinstance(normal, BucketToggle) and isinstance(large, BucketToggle)
        host.ensurePolished(); large.ensurePolished(); normal.ensurePolished()
        assert large.font().pixelSize() == 15 and normal.font().pixelSize() == 11
        assert large.iconSize().width() < normal.iconSize().width()  # smaller arrow
        previous, _, _ = build_bucket_toggle(layout, "Folders", large=True)
        previous.setStyleSheet("QToolButton { padding: 5px 12px; font-size: 14px; }")  # the old large metrics
        previous.setIconSize(previous.iconSize().__class__(15, 15))
        previous.ensurePolished()
        assert large.sizeHint().height() <= previous.sizeHint().height()  # same box as before
        large.resize(large.sizeHint())
        alphas = _edge_alphas(large, 0, 10, large.width() - 10)
        assert min(alphas) > 0 and max(alphas) - min(alphas) <= 12  # continuous top edge
    finally:
        host.deleteLater()


def test_outlined_list_frame_is_one_continuous_stroke(qapp) -> None:
    host, layout = _host()
    try:
        listing = OutlinedListWidget()
        layout.addWidget(listing)
        host.resize(300, 160)
        host.ensurePolished()
        listing.resize(280, 140)
        alphas = _edge_alphas(listing, 0, 14, 266)
        assert min(alphas) > 0 and max(alphas) - min(alphas) <= 12
    finally:
        host.deleteLater()


def test_veil_darkens_inside_the_border_only(qapp) -> None:
    from PySide6.QtGui import QImage

    class Veiled(QWidget):
        def paintEvent(self, _event):
            paint_content_frame(self, veil=True)

    widget = Veiled()
    widget.resize(200, 120)
    try:
        image = QImage(widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(0)
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QRegion
        widget.render(image, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)  # no window background
        light_text = get_active_settings_theme().color("panel.group.text").as_tuple()[0] > 127
        centre = image.pixelColor(100, 60)
        assert centre.alpha() > 0  # the veil is painted
        assert (centre.red() < 128) is light_text
        assert image.pixelColor(0, 0).alpha() == 0  # rounded corner: nothing outside the border
    finally:
        widget.deleteLater()


def test_title_case_rule_leaves_data_and_units_alone() -> None:
    assert title_case("click a display to switch it on or off.") == "Click A Display To Switch It On Or Off."
    assert title_case("Added https://example.org/feed.rss") == "Added https://example.org/feed.rss"
    assert title_case("C:/Pictures and you@gmail.com") == "C:/Pictures And you@gmail.com"
    assert title_case("RSS feeds, 10 px") == "RSS Feeds, 10 px"
    assert title_case("right-click, play/pause, e.g. r/cats") == "Right-Click, Play/Pause, e.g. r/cats"
    assert title_case("(shift for more)") == "(Shift For More)"
