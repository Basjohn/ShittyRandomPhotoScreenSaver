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
    assert title_case("click a display to switch it on or off.") == "Click a Display to Switch It on or Off."
    assert title_case("Added https://example.org/feed.rss") == "Added https://example.org/feed.rss"
    assert title_case("C:/Pictures and you@gmail.com") == "C:/Pictures and you@gmail.com"
    assert title_case("RSS feeds, 10 px") == "RSS Feeds, 10 px"
    assert title_case("right-click, play/pause, e.g. r/cats") == "Right-Click, Play/Pause, e.g. r/cats"
    assert title_case("(shift for more)") == "(Shift for More)"


def test_popups_carry_settings_theme_semantics(qapp) -> None:
    """A popup is its own window: it must bring the Settings theme with it."""
    from PySide6.QtWidgets import QCheckBox
    from ui.styled_popup import StyledPopup
    from ui.widgets.continuous_border import PopupSurface
    from ui.widgets.outlined_button import OutlinedButton

    check = QCheckBox("Display Settings")
    popup = StyledPopup(None, "Import Settings", "Choose.", buttons=[("Import", "import"), ("Cancel", "cancel")],
                        content=check)
    try:
        assert popup.styleSheet() == _build_settings_root_stylesheet(get_active_settings_theme())
        assert isinstance(popup.findChild(PopupSurface), PopupSurface)  # seam-free panel body
        buttons = popup.findChildren(OutlinedButton)
        assert [b.text() for b in buttons] == ["Import", "Cancel"]
        # Ordinary Settings button semantics throughout; the default answers Enter
        # but is never painted as a permanently emphasized (stuck-hover) pill.
        assert {b._role for b in buttons} == {"secondary"}
        assert buttons[0].isDefault() and not buttons[1].isDefault()
        assert check.isVisibleTo(popup) or check.parent() is not None
    finally:
        popup.deleteLater()


def test_circle_indicators_contrast_with_the_themes_checkbox_text(qapp, tmp_path, monkeypatch) -> None:
    """Light themes (dark text) get dark rings; light-text themes keep the shipped white SVGs."""
    import core.settings.storage_paths as paths
    from ui.settings_theme_catalog import build_settings_theme_catalog, activate_catalog_theme
    from ui.tabs import shared_styles
    monkeypatch.setattr(paths, "get_cache_dir", lambda profile=None: tmp_path)
    catalog = build_settings_theme_catalog("themes")
    before = get_active_settings_theme()
    try:
        activate_catalog_theme(next(e for e in catalog.entries if e.name.startswith("Polished Chrome")))
        style = shared_styles.CIRCLE_CHECKBOX_STYLE
        assert ":/srpss/ui/icons/circle_checkbox_" not in style
        text = get_active_settings_theme().color("control.checkbox.text")
        colour = f"#{text.r:02x}{text.g:02x}{text.b:02x}"
        written = sorted(tmp_path.glob("settings_indicators/*.svg"))
        assert len(written) == 4 and all(colour in path.read_text(encoding="utf-8") for path in written)
        activate_catalog_theme(next(e for e in catalog.entries if e.name == "Default Dark"))
        assert shared_styles.CIRCLE_CHECKBOX_STYLE.count(":/srpss/ui/icons/circle_checkbox_") == 6
    finally:
        from ui.settings_theme_runtime import set_active_settings_theme
        set_active_settings_theme(before)
