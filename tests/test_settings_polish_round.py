"""Bucket arrow spacing, button semantics, popup glyphs and source-folder spelling.

Widgets are rendered with ``grab()`` and never shown on screen.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.sources.folder_paths import contains_folder, display_folder_path, same_folder, without_folder


def test_one_folder_is_one_folder_whatever_its_separators() -> None:
    forward, native = "C:/Users/Me/Wallpapers/", r"c:\Users\Me\Wallpapers"
    assert same_folder(forward, native)
    assert display_folder_path(forward) == r"C:\Users\Me\Wallpapers"
    assert contains_folder([native], forward)
    assert without_folder([forward, r"D:\Other"], native) == [r"D:\Other"]
    assert not same_folder("", "")


def test_wizard_sources_never_add_a_second_spelling(qt_app, monkeypatch) -> None:
    from ui.onboarding import basic_pages
    from ui.onboarding.draft import SettingsDraft

    class _Store(dict):
        def get(self, key, default=None):
            return super().get(key, default)

        def set(self, key, value):
            self[key] = value

        def save(self):
            pass

    store = _Store({"sources.folders": [r"C:\Users\Me\Pictures\SRPSS Collections"], "sources.rss_feeds": []})
    page = basic_pages.SourcesPage(SettingsDraft(store))
    try:
        monkeypatch.setattr(basic_pages.QFileDialog, "getExistingDirectory",
                            staticmethod(lambda *_a, **_k: "C:/Users/Me/Pictures/SRPSS Collections"))
        page.add_folder()
        monkeypatch.setattr(basic_pages.QFileDialog, "getExistingDirectory",
                            staticmethod(lambda *_a, **_k: "C:/Users/Me/Wallpapers"))
        page.add_folder()
        shown = [page.folders.item(row).text() for row in range(page.folders.count())]
        assert shown == [r"C:\Users\Me\Pictures\SRPSS Collections", r"C:\Users\Me\Wallpapers"]
        assert all("/" not in text for text in shown)
    finally:
        page.deleteLater()


def test_popups_show_no_neutral_glyph_and_no_stuck_emphasis(qt_app) -> None:
    from ui.styled_popup import StyledPopup
    from ui.widgets.outlined_button import OutlinedButton

    for kind in ("question", "info"):
        popup = StyledPopup(None, "Replace Layout Slot", "Replace it?", kind,
                            buttons=[("Replace", "yes"), ("Cancel", "no")])
        try:
            labels = [label.text() for label in popup.findChildren(QLabel)]
            assert "?" not in labels and "ℹ" not in labels
            roles = {button._role for button in popup.findChildren(OutlinedButton)}
            assert roles == {"secondary"}
        finally:
            popup.deleteLater()
    warning = StyledPopup(None, "Careful", "Something failed.", "warning")
    try:
        assert "⚠" in [label.text() for label in warning.findChildren(QLabel)]
    finally:
        warning.deleteLater()


def test_wizard_buttons_use_ordinary_settings_button_semantics(qt_app) -> None:
    from ui.onboarding.common import action

    button = action("Next", lambda: None)
    try:
        assert button._role == "secondary"
    finally:
        button.deleteLater()


def _ink_runs(image) -> list[tuple[int, int]]:
    ink = [any(image.pixelColor(x, y).lightness() > 150 for y in range(image.height()))
           for x in range(image.width() - 3)]  # ignore the border stroke
    runs, start = [], None
    for x, value in enumerate(ink + [False]):
        if value and start is None:
            start = x
        elif not value and start is not None:
            runs.append((start, x - 1))
            start = None
    return runs


@pytest.mark.parametrize("large", [False, True])
def test_bucket_arrow_keeps_clear_of_its_title_and_the_title_never_clips(qt_app, large) -> None:
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtWidgets import QToolButton

    from ui.settings_theme import _build_settings_root_stylesheet
    from ui.settings_theme_runtime import get_active_settings_theme
    from ui.tabs.shared_styles import build_bucket_toggle

    host = QWidget()
    host.setStyleSheet(_build_settings_root_stylesheet(get_active_settings_theme()))
    layout = QVBoxLayout(host)
    title = "Online Wallpaper Feeds · 4 ON"
    try:
        for expanded in (False, True):
            toggle, _body, _layout = build_bucket_toggle(layout, title, expanded, large=large)
            # Qt's native layout of the same header: the spacing it replaced.
            native = QToolButton(host)
            native.setText(title)
            native.setAutoRaise(True)
            native.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            native.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
            if large:
                native.setProperty("bucketSize", "large")
                native.setIconSize(QSize(11, 11))
            host.ensurePolished()
            for button in (toggle, native):
                button.resize(button.sizeHint())
            ours, theirs = _ink_runs(toggle.grab().toImage()), _ink_runs(native.grab().toImage())
            gap = ours[1][0] - ours[0][1]
            native_gap = theirs[1][0] - theirs[0][1]
            # Arrow size is unchanged (within one device pixel of antialiasing at
            # fractional scaling); the title moved 1 px (normal) / 2 px (large) away.
            assert abs((ours[0][1] - ours[0][0]) - (theirs[0][1] - theirs[0][0])) <= 1
            assert gap - native_gap >= (2 if large else 1), (gap, native_gap)
            image = toggle.grab().toImage()
            margin = (image.width() - 1 - ours[-1][1]) / image.devicePixelRatioF()
            assert margin >= 8  # the title ends well inside the border at any scale
    finally:
        host.deleteLater()
