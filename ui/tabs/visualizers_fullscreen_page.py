"""Visualizers → Fullscreen Mode: the full-display overlays' options (plan 01 §G, M3b) and the display style (1D.2).

One page, placed first after Setup, for the overlays the Expanded Visualizer shows on the full display: the preset's
name and Now Playing (Artist, Song and Artwork), and how the expanded card meets the display's edges (Display Style,
built from its one spec declaration ``DISPLAY_STYLE_CONTROL``). Every value is ``widgets.spotify_visualizer.fullscreen_overlays``
(``core.settings.fullscreen_overlays``: one canonical owner, persisted with the Visualizer section, reset and imported
with it); this page holds no other state. Placement offsets and scales (Fullscreen Edit, M3c) have no control here:
they are kept as loaded and written back unchanged, except that a new Corner rebases the overlay's offset by the one
owner's rule (``rebase_offset_for_corner``).

Layout follows the Settings bucket pattern: one bucket per overlay plus Text, closed by default, one open at a time
(the Visualizer pages' remembered leaf), a one-sentence intro, details in tooltips.
"""
from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtCore import QSignalBlocker
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QCheckBox, QGroupBox, QLabel, QSpinBox, QVBoxLayout, QWidget

from core.settings.fullscreen_overlays import (
    CORNERS,
    DISPLAY_STYLE_CONTROL,
    DISPLAY_STYLE_KEY,
    FONT_SIZE_MAX,
    FONT_SIZE_MIN,
    normalize_fullscreen_overlays,
    rebase_offset_for_corner,
)
from ui.tabs import shared_styles
from ui.tabs.media.builder_scaffold import build_collapsible_bucket
from ui.tabs.shared_styles import add_aligned_row, style_group_box
from ui.widgets import StyledComboBox, StyledFontComboBox

if TYPE_CHECKING:
    from ui.tabs.visualizers_tab import VisualizersTab

#: The bucket scope of this page in ``ui.visualizer_bucket_states`` (``fullscreen:<bucket>``).
FULLSCREEN_BUCKET_SCOPE = "fullscreen"
#: The buckets this page builds, in order (their open state is ``fullscreen:<bucket>``).
FULLSCREEN_BUCKETS = ("display", "preset", "now_playing", "text")
_CORNER_LABELS = {
    "top_left": "Top Left",
    "top_right": "Top Right",
    "bottom_left": "Bottom Left",
    "bottom_right": "Bottom Right",
}


class FullscreenModePage(QWidget):
    """The Fullscreen Mode pill's page; ``changed`` is the tab's (coalesced) save."""

    def __init__(self, tab: "VisualizersTab", *, changed: Callable[[], None]) -> None:
        super().__init__()
        self.setObjectName("visualizers_fullscreen_page")
        self._changed = changed
        self._loading = False
        self._values: dict[str, Any] = normalize_fullscreen_overlays(None, tab._settings.get_application_name())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        group = QGroupBox("Fullscreen Mode")
        style_group_box(group)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(18, 18, 18, 18)
        group_layout.setSpacing(10)
        intro = QLabel("What the Visualizer shows over itself while it fills the display.")
        intro.setWordWrap(True)
        shared_styles.apply_shared_label_style(intro, "INFO_LABEL_STYLE")
        group_layout.addWidget(intro)

        # The expanded card's display style (1D.2): built from its one spec declaration (DISPLAY_STYLE_CONTROL).
        _host, display_layout = build_collapsible_bucket(
            tab, group_layout, mode_key=FULLSCREEN_BUCKET_SCOPE, bucket_key=FULLSCREEN_BUCKETS[0], title="Display",
            helper_text="How the Visualizer meets the edges of the display.")
        style_row = add_aligned_row(display_layout, f"{DISPLAY_STYLE_CONTROL.label}:")[0]
        self.display_style = StyledComboBox(size_variant="hero")
        self.display_style.setObjectName("fullscreen_display_style")
        for value, label in zip(DISPLAY_STYLE_CONTROL.choices, DISPLAY_STYLE_CONTROL.labels, strict=True):
            self.display_style.addItem(label, value)
        self.display_style.setToolTip(DISPLAY_STYLE_CONTROL.tooltip)
        self.display_style.currentIndexChanged.connect(
            lambda _index: self._set_value((DISPLAY_STYLE_KEY,), str(self.display_style.currentData())))
        style_row.addWidget(self.display_style)
        style_row.addStretch()

        _host, preset_layout = build_collapsible_bucket(
            tab, group_layout, mode_key=FULLSCREEN_BUCKET_SCOPE, bucket_key=FULLSCREEN_BUCKETS[1], title="Preset Name",
            helper_text="The preset's name, shown for a moment when the preset changes.")
        self.preset_corner = self._corner_row(preset_layout, "preset")
        self.preset_always_show = self._check(
            preset_layout, "Always Show", "preset", "always_show",
            "Keep the preset's name on screen; a new preset fades in its place.")
        self.preset_card = self._check(
            preset_layout, "Card", "preset", "card",
            "Show the name on a card with the theme's border and surface, like the widgets.")

        _host, now_playing_layout = build_collapsible_bucket(
            tab, group_layout, mode_key=FULLSCREEN_BUCKET_SCOPE, bucket_key=FULLSCREEN_BUCKETS[2], title="Now Playing",
            helper_text="Artist, song and artwork, shown for a moment when the track changes.")
        self.now_playing_corner = self._corner_row(now_playing_layout, "now_playing")
        self.now_playing_always_show = self._check(
            now_playing_layout, "Always Show", "now_playing", "always_show",
            "Keep the track on screen; a new track fades in its place.")
        self.now_playing_hover_reveal = self._check(
            now_playing_layout, "Show On Hover", "now_playing", "hover_reveal",
            "Once the track has faded, pointing at where it sits fades it back in; it fades again after the pointer "
            "leaves.")
        self.now_playing_media_controls = self._check(
            now_playing_layout, "Media Controls", "now_playing", "media_controls",
            "Previous, play/pause and next beside the track. They control the Media widget's player and need "
            "Interaction Mode (or Ctrl held), like every widget control.")
        controls_row = add_aligned_row(now_playing_layout, "Controls Style:")[0]
        self.now_playing_controls_style = StyledComboBox(size_variant="hero")
        self.now_playing_controls_style.addItem("Media Bar", "bar")
        self.now_playing_controls_style.addItem("Floating Glyphs", "floating")
        self.now_playing_controls_style.setToolTip("Use the Media card's bar or its transport glyphs without a surface.")
        self.now_playing_controls_style.setEnabled(self.now_playing_media_controls.isChecked())
        self.now_playing_media_controls.toggled.connect(self.now_playing_controls_style.setEnabled)
        self.now_playing_controls_style.currentIndexChanged.connect(
            lambda _index: self._set_value(("now_playing", "media_controls_style"),
                                          str(self.now_playing_controls_style.currentData())))
        controls_row.addWidget(self.now_playing_controls_style)
        controls_row.addStretch()
        self.now_playing_seek_bar = self._check(
            now_playing_layout, "Seek Bar", "now_playing", "seek_bar",
            "The Media widget's seek bar under the track, in its colours. Click it to seek; like Media Controls it "
            "needs Interaction Mode (or Ctrl held).")
        self.now_playing_card = self._check(
            now_playing_layout, "Card", "now_playing", "card",
            "Show the track on a card with the theme's border and surface, like the widgets. The artwork keeps "
            "the Media widget's artwork border either way.")

        _host, text_layout = build_collapsible_bucket(
            tab, group_layout, mode_key=FULLSCREEN_BUCKET_SCOPE, bucket_key=FULLSCREEN_BUCKETS[3], title="Text",
            helper_text="The font both overlays use.")
        font_row = add_aligned_row(text_layout, "Font:")[0]
        self.font_combo = StyledFontComboBox(size_variant="hero")
        self.font_combo.setMinimumWidth(220)
        self.font_combo.setToolTip("The overlays' font. Text is white, with a soft shadow over bright visuals.")
        self.font_combo.currentFontChanged.connect(self._on_font_changed)
        font_row.addWidget(self.font_combo)
        font_row.addStretch()
        size_row = add_aligned_row(text_layout, "Font Size:")[0]
        self.font_size = QSpinBox()
        self.font_size.setRange(FONT_SIZE_MIN, FONT_SIZE_MAX)
        self.font_size.setAccelerated(True)
        self.font_size.setSuffix(" px")
        self.font_size.setToolTip("The song and preset size; the artist line and the artwork follow it.")
        self.font_size.valueChanged.connect(lambda value: self._set_value(("font_size",), int(value)))
        size_row.addWidget(self.font_size)
        size_row.addStretch()

        layout.addWidget(group)
        layout.addStretch()
        self.load(self._values)

    # ------------------------------------------------------------------------------------------- controls

    def _corner_row(self, parent: QVBoxLayout, overlay: str) -> StyledComboBox:
        row = add_aligned_row(parent, "Corner:")[0]
        combo = StyledComboBox()
        combo.setObjectName(f"fullscreen_{overlay}_corner")
        for corner in CORNERS:
            combo.addItem(_CORNER_LABELS[corner], corner)
        combo.setMinimumWidth(150)
        combo.setToolTip("Which corner of the display it sits in. Two overlays in one corner stack, the newer "
                         "one nearer the edge.")
        combo.currentIndexChanged.connect(
            lambda _index, box=combo, name=overlay: self._set_corner(name, str(box.currentData())))
        row.addWidget(combo)
        row.addStretch()
        return combo

    def _check(self, parent: QVBoxLayout, label: str, overlay: str, key: str, tooltip: str) -> QCheckBox:
        check = QCheckBox(label)
        check.setObjectName(f"fullscreen_{overlay}_{key}")
        check.setProperty("circleIndicator", True)
        check.setToolTip(tooltip)
        check.toggled.connect(lambda checked, name=overlay, field=key: self._set_value((name, field), bool(checked)))
        parent.addWidget(check)
        return check

    def _on_font_changed(self, font: QFont) -> None:
        family = font.family().strip()
        if family:
            self._set_value(("font_family",), family)

    def _set_corner(self, overlay: str, corner: str) -> None:
        """A new anchor corner rebases the overlay's Fullscreen Edit offset (the one owner's rule): kept on each axis
        that still points into the display from the new corner, reset where it would push the overlay out."""

        if self._loading or self._values[overlay].get("corner") == corner:
            return
        self._values[overlay] = rebase_offset_for_corner(self._values[overlay], corner)
        self._changed()

    def _set_value(self, path: tuple[str, ...], value: Any) -> None:
        if self._loading:
            return
        target = self._values
        for key in path[:-1]:
            target = target[key]
        if target.get(path[-1]) == value:
            return
        target[path[-1]] = value
        self._changed()

    # ----------------------------------------------------------------------------------------- load / save

    def load(self, stored: Any) -> None:
        """Show ``stored`` (normalised through the one owner); signals stay silent."""

        self._values = normalize_fullscreen_overlays(stored)
        values = self._values
        self._loading = True
        try:
            for combo, overlay in ((self.preset_corner, "preset"), (self.now_playing_corner, "now_playing")):
                with QSignalBlocker(combo):
                    combo.setCurrentIndex(max(0, combo.findData(values[overlay]["corner"])))
            for check, overlay, key in (
                (self.preset_always_show, "preset", "always_show"),
                (self.preset_card, "preset", "card"),
                (self.now_playing_always_show, "now_playing", "always_show"),
                (self.now_playing_hover_reveal, "now_playing", "hover_reveal"),
                (self.now_playing_media_controls, "now_playing", "media_controls"),
                (self.now_playing_seek_bar, "now_playing", "seek_bar"),
                (self.now_playing_card, "now_playing", "card"),
            ):
                with QSignalBlocker(check):
                    check.setChecked(bool(values[overlay][key]))
            with QSignalBlocker(self.display_style):
                self.display_style.setCurrentIndex(max(0, self.display_style.findData(values[DISPLAY_STYLE_KEY])))
            with QSignalBlocker(self.font_combo):
                self.font_combo.setCurrentFont(QFont(str(values["font_family"])))
            with QSignalBlocker(self.now_playing_controls_style):
                self.now_playing_controls_style.setCurrentIndex(
                    self.now_playing_controls_style.findData(values["now_playing"]["media_controls_style"]))
            self.now_playing_controls_style.setEnabled(bool(values["now_playing"]["media_controls"]))
            with QSignalBlocker(self.font_size):
                self.font_size.setValue(int(values["font_size"]))
        finally:
            self._loading = False

    def values(self) -> dict[str, Any]:
        """The value to persist: the loaded one with this page's edits (placement kept as loaded)."""

        return deepcopy(self._values)


__all__ = ["FULLSCREEN_BUCKET_SCOPE", "FullscreenModePage"]
