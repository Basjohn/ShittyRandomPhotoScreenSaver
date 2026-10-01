"""Lazy Settings selection surfaces, backed by canonical admission and theme owners."""
from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache

from PySide6.QtCore import QRectF, QSignalBlocker, QSize, QSizeF, Signal, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QListWidget, QListWidgetItem, QSizePolicy, QVBoxLayout, QWidget

from ui.widgets.continuous_border import OutlinedListWidget
from core.settings.capability_activation import (
    is_transition_activated, is_widget_family_effective,
    normalize_transition_capability_state, normalize_widget_capability_state,
    set_transition_activated, set_widget_family_activated,
)
from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors, resolve_admissible_enabled_modes
from core.settings.widget_family_catalog import get_widget_family_descriptors, get_widget_member_label
from rendering.transition_registry import iter_transition_descriptors
from ui.onboarding.common import Page, ImagePanel, action, asset_bytes, asset_path, checkbox, CheckList, text_label, font_with_point_delta
from ui.onboarding.state import current_setup_summary, saved_account_states
from ui.settings_theme_catalog import get_current_settings_theme_catalog, read_persisted_theme_id
from ui.widgets.dpr_pixmap import scale_pixmap_for_dpr
from ui.settings_theme_selection import apply_settings_theme_selection
from ui.widget_theme_selection import read_widget_theme_state


def _check(text, checked, callback):
    check = checkbox(text)
    check.setChecked(checked)
    check.toggled.connect(callback)
    return check


def _member_setting(widget_id):
    if widget_id in {"spotify_volume", "mute_button"}:
        return "media", f"{widget_id}_enabled"
    return widget_id, "enabled"


def _member_label(member, family):
    if len(family.member_widget_ids) == 1:
        return family.label
    return get_widget_member_label(member)


class ThemePage(Page):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.body.addWidget(text_label("Make yourself at home", heading=True))
        self.body.addWidget(text_label("Choose a Settings theme to apply it immediately. Widget colours follow only when Keep Synced is on."))
        self.list = OutlinedListWidget(); self.list.setMinimumHeight(250)
        self.body.addWidget(self.list, 1)
        self.status = text_label(""); self.body.addWidget(self.status)
        self.list.currentItemChanged.connect(self._select)

    def refresh(self):
        catalog = get_current_settings_theme_catalog()
        with QSignalBlocker(self.list):
            self.list.clear()
            for entry in catalog.entries:
                item = QListWidgetItem(entry.name)
                item.setData(Qt.ItemDataRole.UserRole, entry.theme_id)
                self.list.addItem(item)
                if entry.theme_id == read_persisted_theme_id(self.settings):
                    self.list.setCurrentItem(item)
        self.status.setText("Keep Synced is on: Widget Theme follows." if read_widget_theme_state(self.settings).keep_synced else "Widget Theme is independent and will stay as you chose it.")

    def _select(self, item, previous):
        if item is None: return
        try:
            entry = apply_settings_theme_selection(self.settings, get_current_settings_theme_catalog(), item.data(Qt.ItemDataRole.UserRole))
        except Exception:
            with QSignalBlocker(self.list): self.list.setCurrentItem(previous)
            self.status.setText("This theme could not be applied. Your previous theme is still selected.")
            return
        self.status.setText(f"Using {entry.name}. " + ("Widget Theme follows." if read_widget_theme_state(self.settings).keep_synced else "Your independent Widget Theme is kept."))


class WidgetsPage(Page):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.body.addWidget(text_label("Widgets are what make the experience special, and messy.\nPick the ones you might actually give a shit about.", heading=True))
        row = QHBoxLayout(); row.setSpacing(20)
        self.rows = CheckList(); self.rows.setMinimumWidth(180); self.rows.setMaximumWidth(260)
        row.addWidget(self.rows, 1)
        self.panel = QWidget(); self.panel_layout = QVBoxLayout(self.panel); self.panel_layout.setContentsMargins(0,0,0,0)
        row.addWidget(self.panel, 3); self.body.addLayout(row, 1)
        self.rows.currentItemChanged.connect(self._show)
        self.rows.itemChanged.connect(self._toggle)

    def refresh(self):
        selected = self.rows.currentItem().data(Qt.ItemDataRole.UserRole) if self.rows.currentItem() else None
        widgets = self.settings.get("widgets")
        with QSignalBlocker(self.rows):
            self.rows.clear()
            for family in get_widget_family_descriptors():
                item = QListWidgetItem(family.label)
                item.setData(Qt.ItemDataRole.UserRole, family.family_id)
                item.setData(Qt.ItemDataRole.UserRole+1, family)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if is_widget_family_effective(widgets, family.family_id) else Qt.CheckState.Unchecked)
                self.rows.addItem(item)
                dependencies_ready = all(is_widget_family_effective(widgets, required) for required in family.required_family_ids)
                self.rows.itemWidget(item).setEnabled(dependencies_ready)
                if not dependencies_ready:
                    self.rows.itemWidget(item).setToolTip("Activate " + ", ".join(family.required_family_ids) + " first.")
                if selected == family.family_id: self.rows.setCurrentItem(item)
            if self.rows.currentRow() < 0: self.rows.setCurrentRow(0)
        self._show(self.rows.currentItem(), None)

    def _show(self, item, previous):
        if item is None: return
        while self.panel_layout.count():
            child = self.panel_layout.takeAt(0).widget()
            if child is not None:
                child.hide(); child.deleteLater()
        family = item.data(Qt.ItemDataRole.UserRole+1)
        self.panel_layout.addWidget(text_label(family.label, heading=True))
        self.panel_layout.addWidget(text_label(family.description))
        preview = ImagePanel(asset_path(f"onboarding/widget_{family.family_id}.png"), upscale=False)
        preview.setMinimumHeight(170); preview.setMaximumHeight(260)
        self.panel_layout.addWidget(preview, 1)
        widgets = self.settings.get("widgets")
        requirement = "READY"
        if family.required_family_ids and not is_widget_family_effective(widgets, family.family_id):
            requirement = "REQUIRES " + ", ".join(family.required_family_ids).upper()
        elif family.family_id in {"steam", "gmail"}:
            if not saved_account_states(self.settings)[family.family_id]: requirement = f"NEEDS {family.family_id.upper()}"
        elif family.family_id == "weather" and not widgets["weather"]["location"]:
            requirement = "NEEDS LOCATION"
        elif family.family_id == "feeds" and not any(widgets.get(member, {}).get("enabled") for member in family.member_widget_ids):
            requirement = "NEEDS NEWS CATEGORY OR CUSTOM FEED SETUP"
        self.panel_layout.addWidget(text_label(requirement))
        for member in family.member_widget_ids:
            # Custom feed authoring stays in full Settings; existing selections are visible here.
            if family.family_id == "feeds" and member.startswith("feeds_custom"):
                continue
            section, key = _member_setting(member)
            checked = bool(widgets.get(section, {}).get(key))
            control = _check(_member_label(member, family), checked, lambda value, wid=member: self._member(wid, value))
            self.panel_layout.addWidget(control)
        if family.family_id == "feeds":
            self.panel_layout.addWidget(text_label("Custom feed cards are configured in Widgets → Feeds → Custom."))
        self.panel_layout.addStretch()

    def _toggle(self, item):
        widgets = self.settings.get("widgets")
        family_id = item.data(Qt.ItemDataRole.UserRole)
        set_widget_family_activated(widgets, family_id, item.checkState() == Qt.CheckState.Checked)
        normalize_widget_capability_state(widgets)
        self.settings.set("widgets", widgets)
        self.refresh()

    def _member(self, widget_id, enabled):
        widgets = self.settings.get("widgets")
        section, key = _member_setting(widget_id)
        widgets[section][key] = enabled
        family = next(f for f in get_widget_family_descriptors() if widget_id in f.member_widget_ids)
        if enabled:
            set_widget_family_activated(widgets, family.family_id, True)
            if family.family_id == "steam": widgets["steam"]["enabled"] = True
        normalize_widget_capability_state(widgets)
        self.settings.set("widgets", widgets)
        self.refresh()


class VisualizerPage(Page):
    """A narrow mode list with the selected mode's real preview beside it."""

    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.body.addWidget(text_label("Bring your music to life", heading=True))
        self.body.addWidget(text_label("Choose which Visualizer modes are available. Select a mode to see it. Detailed tuning and presets remain in full Settings."))
        self.enabled = _check("Enable Visualizer", False, self._enable)
        self.body.addWidget(self.enabled)
        row = QHBoxLayout(); row.setSpacing(20)
        self.rows = CheckList(); self.rows.setMinimumHeight(290)
        row.addWidget(self.rows, 0, Qt.AlignmentFlag.AlignTop)
        preview_column = QVBoxLayout(); preview_column.setContentsMargins(0, 0, 0, 0)
        self.preview_title = text_label("", heading=True)
        preview_column.addWidget(self.preview_title)
        self.preview = None
        self._preview_holder = preview_column
        preview_column.addStretch()
        row.addLayout(preview_column, 1)
        self.body.addLayout(row, 1)
        self.status = text_label(""); self.body.addWidget(self.status)
        self.rows.itemChanged.connect(self._toggle)
        self.rows.currentItemChanged.connect(self._show)
        self._offered_modes = None

    def refresh(self):
        widgets = self.settings.get("widgets"); section = widgets["spotify_visualizer"]
        active = set(resolve_admissible_enabled_modes(section["mode_activation"]))
        if self._offered_modes is None:
            # Experimental Sphere can be retained/disabled here only if already admitted.
            self._offered_modes = [d for d in iter_visualizer_mode_descriptors() if d.mode_id != "sphere" or d.mode_id in active]
        with QSignalBlocker(self.enabled): self.enabled.setChecked(bool(section["enabled"]))
        effective = is_widget_family_effective(widgets, "visualizers")
        self.enabled.setEnabled(effective)
        self.status.setText("Choose at least one mode." if effective else "Enable Media and Visualizers in the Widgets step to use the Visualizer.")
        selected = self.rows.currentRow()
        with QSignalBlocker(self.rows):
            self.rows.clear()
            for mode in self._offered_modes:
                item = QListWidgetItem(mode.display_name); item.setData(Qt.ItemDataRole.UserRole, mode.mode_id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if mode.mode_id in active else Qt.CheckState.Unchecked)
                self.rows.addItem(item)
                # Previews stay browsable even while the Visualizer family is off.
                self.rows.itemWidget(item).setEnabled(effective)
            self.rows.setCurrentRow(max(0, min(selected, self.rows.count() - 1)))
        # Narrow, but never truncating a mode name: fit the longest row.
        widest = max((self.rows.itemWidget(self.rows.item(i)).sizeHint().width() for i in range(self.rows.count())), default=200)
        self.rows.setFixedWidth(min(360, max(220, widest + 2 * self.rows.frameWidth() + 44)))
        self._show(self.rows.currentItem(), None)

    def _show(self, item, _previous):
        if item is None:
            return
        mode_id = item.data(Qt.ItemDataRole.UserRole)
        self.preview_title.setText(item.text())
        path = asset_path(f"onboarding/visualizer_{mode_id}.png")
        if self.preview is None:
            self.preview = ImagePanel(path, upscale=False)
            self.preview.setMinimumHeight(220); self.preview.setMaximumHeight(300)
            self._preview_holder.insertWidget(1, self.preview)
        else:
            self.preview.set_source(path)

    def _enable(self, enabled):
        self.settings.set("widgets.spotify_visualizer.enabled", enabled)

    def _toggle(self, item):
        section = self.settings.get("widgets.spotify_visualizer")
        activation = dict(section["mode_activation"])
        activation[item.data(Qt.ItemDataRole.UserRole)] = item.checkState() == Qt.CheckState.Checked
        if not any(activation.values()):
            with QSignalBlocker(self.rows): item.setCheckState(Qt.CheckState.Checked)
            self.status.setText("Keep at least one Visualizer mode selected."); return
        self.settings.set("widgets.spotify_visualizer.mode_activation", activation)


TRANSITION_COPY = {
    "crossfade": "One image gently fades into the next.", "slide": "The next image slides into view.",
    "wipe": "A moving edge reveals the next image.", "warp_dissolve": "A swirling distortion blends the images.",
    "blinds": "Strips open to reveal the next image.", "block_flip": "Bands flip over to reveal the next image.",
    "block_spins": "The whole picture turns over in 3D.", "burn": "A burning edge consumes the old image.",
    "crumble": "The old image breaks apart and falls away.", "diffuse": "The old image scatters into the new image.",
    "exploding_tiles": "Tiles burst outward to uncover the next image.", "glass_shatter": "The picture fractures into glass shards.",
    "ink_bloom": "Organic ink shapes spread across the picture.", "melt_drip": "The image melts into falling drips.",
    "particle": "Particles carry the image into the next scene.", "pixel_accretion": "Small pieces assemble the new picture.",
    "ripple": "Water-like ripples blend the two pictures.",
}


@lru_cache(maxsize=1)
def _transition_manifest() -> dict[str, dict]:
    rows = json.loads(asset_bytes("onboarding/manifest.json").decode("utf-8"))["transitions"]
    return {row["transition_id"]: row for row in rows}


class TransitionStrip(QWidget):
    """Three moments of one transition, with painted gaps and live-text labels.

    The strip image carries only pixels; progress labels are drawn here so
    they stay crisp at any DPR.  It uses 90% of the available width, centred,
    and never distorts the 16:9 frames.
    """

    GAP = 10
    WIDTH_SHARE = 0.9

    def __init__(self, parent=None):
        super().__init__(parent)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.transition_id = None
        self._source = QPixmap()
        self._progress = ()
        self._frames = []
        self._frames_key = None

    def set_transition(self, transition_id):
        row = _transition_manifest()[transition_id]
        source = QPixmap(str(asset_path("onboarding/" + row["path"])))
        if source.isNull():
            raise FileNotFoundError(f"Guided Setup transition preview missing or unreadable: {row['path']}")
        self.transition_id = transition_id
        self._source = source
        self._progress = tuple(row["progress"])
        self._frames_key = None
        self.updateGeometry()
        self.update()

    def _layout(self, width):
        count = max(1, len(self._progress) or 3)
        strip = width * self.WIDTH_SHARE
        frame_width = max(1.0, (strip - self.GAP * (count - 1)) / count)
        return count, frame_width, frame_width * 9 / 16

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return round(self._layout(width)[2])

    def sizeHint(self):
        return QSize(640, self.heightForWidth(640))

    def minimumSizeHint(self):
        return QSize(240, self.heightForWidth(240))

    def _scaled_frames(self, frame_width, frame_height):
        key = (round(frame_width), round(frame_height), self.devicePixelRatioF(), self._source.cacheKey())
        if key != self._frames_key:
            count = max(1, len(self._progress))
            source_width = self._source.width() // count
            self._frames = [
                scale_pixmap_for_dpr(self._source.copy(index * source_width, 0, source_width, self._source.height()),
                                     frame_width, frame_height, key[2])
                for index in range(count)
            ]
            self._frames_key = key
        return self._frames

    def paintEvent(self, _event):
        if self._source.isNull():
            return
        count, frame_width, frame_height = self._layout(self.width())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        left = (self.width() - (frame_width * count + self.GAP * (count - 1))) / 2
        top = max(0.0, (self.height() - frame_height) / 2)
        font = font_with_point_delta(self, 0.5)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        for index, frame in enumerate(self._scaled_frames(frame_width, frame_height)):
            target = QRectF(left + index * (frame_width + self.GAP), top, frame_width, frame_height)
            clip = QPainterPath()
            clip.addRoundedRect(target, 8.0, 8.0)
            painter.save()
            painter.setClipPath(clip)
            logical = QSizeF(frame.width(), frame.height()) / frame.devicePixelRatio()
            painter.drawPixmap(QRectF(target.center().x() - logical.width() / 2,
                                      target.center().y() - logical.height() / 2,
                                      logical.width(), logical.height()), frame, QRectF(frame.rect()))
            painter.restore()
            if index < len(self._progress):
                text = f"{round(self._progress[index] * 100)}%"
                badge = QRectF(target.left() + 8, target.top() + 8,
                               metrics.horizontalAdvance(text) + 16, metrics.height() + 6)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(0, 0, 0, 165))
                painter.drawRoundedRect(badge, badge.height() / 2, badge.height() / 2)
                painter.setPen(QColor(245, 247, 250))
                painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)


def _prominent_scrollbar_style() -> str:
    """A scrollbar people notice: always shown, wider, accent-coloured handle."""
    from ui.settings_theme_runtime import get_active_settings_theme
    theme = get_active_settings_theme()

    def rgba(token, alpha):
        red, green, blue = theme.color(token).as_tuple()[:3]
        return f"rgba({red}, {green}, {blue}, {alpha})"

    return (
        "QScrollBar:vertical { width: 18px; margin: 2px 2px 2px 4px; border-radius: 8px;"
        f" border: 1.5px solid {rgba('control.button.border', 200)};"
        f" background: {rgba('control.button.surface', 190)}; }}"
        " QScrollBar::handle:vertical { min-height: 40px; margin: 1px; border-radius: 6px;"
        f" background: {rgba('control.list.selected_accent', 235)}; }}"
        f" QScrollBar::handle:vertical:hover {{ background: {rgba('control.list.selected_accent', 255)}; }}"
        " QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
        " QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }"
    )


class TransitionsPage(Page):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.body.addWidget(text_label("How should your wallpapers change?", heading=True))
        self.body.addWidget(text_label("Select transitions to include in the available effects and random pool. Each preview shows three moments of the change."))
        self.rows = CheckList(); self.rows.setMinimumHeight(190); self.rows.setMaximumHeight(270)
        self.rows.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.body.addWidget(self.rows)
        self.more = text_label("")
        self.body.addWidget(self.more)
        self.preview = TransitionStrip()
        self.body.addWidget(self.preview)
        self.description = text_label(""); self.body.addWidget(self.description)
        self.status = text_label(""); self.body.addWidget(self.status)
        self.rows.itemChanged.connect(self._toggle)
        self.rows.currentItemChanged.connect(self._show)

    def refresh(self):
        selected = self.rows.currentRow()
        cfg = self.settings.get("transitions")
        with QSignalBlocker(self.rows):
            self.rows.clear()
            for descriptor in iter_transition_descriptors():
                if not descriptor.available: continue
                item = QListWidgetItem(descriptor.setting_name)
                item.setData(Qt.ItemDataRole.UserRole, descriptor.setting_name)
                item.setData(Qt.ItemDataRole.UserRole+1, descriptor.stable_id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if is_transition_activated(cfg, descriptor.setting_name) else Qt.CheckState.Unchecked)
                self.rows.addItem(item)
            self.rows.setCurrentRow(max(0, min(selected, self.rows.count()-1)))
        self.rows.verticalScrollBar().setStyleSheet(_prominent_scrollbar_style())
        self.more.setText(f"{self.rows.count()} transitions: scroll the list to see them all.")
        self._show(self.rows.currentItem(), None)
        self.status.setText("Random selection is on." if cfg["random_always"] else "Your current manual transition choice is kept when available.")

    def _show(self, item, previous):
        if item is None: return
        key = item.data(Qt.ItemDataRole.UserRole+1)
        self.preview.set_transition(key)
        copy = TRANSITION_COPY.get(key)
        self.description.setText(item.text() + (" — " + copy if copy else ""))

    def _toggle(self, item):
        cfg = self.settings.get("transitions")
        enabled = item.checkState() == Qt.CheckState.Checked
        name = item.data(Qt.ItemDataRole.UserRole)
        set_transition_activated(cfg, name, enabled)
        cfg["pool"][name] = enabled
        normalize_transition_capability_state(cfg)
        self.settings.set("transitions", cfg)
        self.refresh()


# The saver's right-click menu (rendering/quick/context_menu.py) and its keys
# (rendering/runtime_input.py), in the order people reach for them.
CONTEXT_MENU_SUMMARY = (
    ("Images", "Previous or next image, or save the one on screen to your collection."),
    ("Change Transition", "Pick one effect or Random."),
    ("Change Visualizer", "Switch the music Visualizer mode."),
    ("Edit Widget Layout", "Drag widgets anywhere, then Save Widget Layout."),
    ("Background Dimming", "Darken the picture behind your widgets."),
    ("Interaction Mode", "Keep widgets clickable without holding Ctrl."),
    ("Settings / Exit Screensaver", "Everything else, or leave."),
)
KEY_SUMMARY = (
    ("Z / X", "Previous / next image"),
    ("C", "Cycle transition"),
    ("S", "Open Settings"),
    ("Space  ·  ← / →", "Play/pause  ·  previous/next track"),
    ("↑ / ↓  ·  PgUp / PgDn", "Media volume  ·  system volume"),
    ("1–9, 0  ·  Shift + number", "Load / save a layout slot"),
    ("Esc / Q", "Exit"),
)


def _controls_summary() -> QWidget:
    from PySide6.QtWidgets import QFrame, QGridLayout
    box = QWidget()
    layout = QVBoxLayout(box); layout.setContentsMargins(0, 8, 0, 0); layout.setSpacing(10)
    line = QFrame(); line.setObjectName("controlsSeparator"); line.setFixedHeight(2)
    from ui.settings_theme_runtime import get_active_settings_theme
    red, green, blue, alpha = get_active_settings_theme().color("panel.border").as_tuple()
    line.setStyleSheet(f"QFrame#controlsSeparator {{ background: rgba({red}, {green}, {blue}, {alpha}); border: none; }}")
    layout.addWidget(line)
    layout.addWidget(text_label("Controls", heading=True))
    layout.addWidget(text_label("Right-click the screensaver for its menu (hold Ctrl first when Interaction is off). It is the quickest way to change anything while it runs."))
    columns = QHBoxLayout(); columns.setSpacing(28)
    for title, rows in (("RIGHT-CLICK MENU", CONTEXT_MENU_SUMMARY), ("KEYS", KEY_SUMMARY)):
        column = QVBoxLayout(); column.setSpacing(6)
        column.addWidget(text_label(title))
        grid = QGridLayout(); grid.setHorizontalSpacing(14); grid.setVerticalSpacing(4)
        for row, (name, detail) in enumerate(rows):
            name_label = text_label(name)
            name_label.setWordWrap(False)  # shortcut names stay on one line
            font = name_label.font(); font.setBold(True); name_label.setFont(font)
            grid.addWidget(name_label, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(text_label(detail), row, 1, Qt.AlignmentFlag.AlignTop)
        grid.setColumnStretch(1, 1)
        column.addLayout(grid); column.addStretch()
        columns.addLayout(column, 1)
    layout.addLayout(columns)
    return box


# A capture of the saver's own right-click menu from the immutable onboarding QRC, shown at its
# true logical size: 2x source pixels, so it stays sharp at any display scale.
_EDIT_MENU_CAPTURE = "onboarding/context_menu_edit.png"
_EDIT_MENU_SIZE = QSize(344, 108)


def _edit_layout_hint() -> QWidget:
    """The menu rows around Edit Widget Layout, highlighted as hovering shows it."""
    box = QWidget()
    layout = QVBoxLayout(box); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(4)
    menu = ImagePanel(asset_path(_EDIT_MENU_CAPTURE))
    menu.setFixedSize(_EDIT_MENU_SIZE)
    menu.setAlignment(Qt.AlignmentFlag.AlignCenter)
    menu.setToolTip("Right-click the screensaver, then Edit Widget Layout.")
    layout.addWidget(menu)
    caption = text_label("Move and resize widgets right on the screensaver.")
    caption.setFixedWidth(_EDIT_MENU_SIZE.width())
    caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(caption)
    return box


class ReadyPage(Page):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.body.addWidget(text_label("You're almost done", heading=True))
        self.body.addWidget(text_label("Nothing is saved yet. Finish saves your settings; Finish & Run also starts the screensaver with them. Optional accounts can be connected later in Settings."))
        self.summary = text_label("")
        summary_row = QHBoxLayout(); summary_row.setSpacing(24)
        summary_row.addWidget(self.summary, 1, Qt.AlignmentFlag.AlignTop)
        summary_row.addWidget(_edit_layout_hint(), 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.body.addLayout(summary_row)
        self.controls = _controls_summary()
        self.body.addWidget(self.controls)
        self.body.addStretch()

    def refresh(self):
        state = current_setup_summary(self.settings)
        displays = "All displays" if state["displays"] == "ALL" else ", ".join(map(str, state["displays"]))
        accounts = state["accounts"]
        def count(value, noun):
            return f"{value} {noun}" + ("" if value == 1 else "s")
        from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
        modes = ", ".join(get_visualizer_mode_descriptor(mode).display_name for mode in state["visualizer_modes"])
        lines = [f"Displays: {displays}", f"Sources: {count(state['folders'], 'folder')} · {count(state['feeds'], 'wallpaper feed')}",
                 "Interaction: " + ("Always on" if state["interaction"] else "Hold Ctrl when needed"),
                 f"Widget families selected: {state['families']}",
                 "Steam: " + ("Saved connection" if accounts['steam'] else "Needs setup"),
                 "Gmail: " + ("Saved connection" if accounts['gmail'] else "Needs setup"),
                 "Visualizer: " + (modes or "Off"),
                 f"Transitions: {state['transitions']}"]
        self.summary.setText("\n".join(lines))
