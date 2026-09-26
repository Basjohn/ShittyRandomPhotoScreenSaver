"""Lazy Settings selection surfaces, backed by canonical admission and theme owners."""
from __future__ import annotations

from copy import deepcopy
from PySide6.QtCore import QSignalBlocker, Signal, Qt
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from core.settings.capability_activation import (
    is_transition_activated, is_widget_family_effective,
    normalize_transition_capability_state, normalize_widget_capability_state,
    set_transition_activated, set_widget_family_activated,
)
from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors, resolve_admissible_enabled_modes
from core.settings.widget_family_catalog import get_widget_family_descriptors
from rendering.transition_registry import iter_transition_descriptors
from ui.onboarding.common import Page, ImagePanel, action, asset_path, checkbox, CheckList, text_label
from ui.onboarding.state import current_setup_summary, saved_account_states
from ui.settings_theme_catalog import get_current_settings_theme_catalog, read_persisted_theme_id
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
    if family.family_id == "clocks":
        return "Clock " + (member.removeprefix("clock") or "1")
    if family.family_id == "feeds":
        from core.feeds.news import NEWS_CATEGORIES
        for category in NEWS_CATEGORIES:
            if member == category.widget_id:
                return category.label
        return "Custom feed " + member.rsplit("_", 1)[-1]
    if member == "steam_progress":
        return "Games You Follow"
    return member.replace("_", " ").title()


class ThemePage(Page):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.body.addWidget(text_label("Make yourself at home", heading=True))
        self.body.addWidget(text_label("Choose a Settings theme to apply it immediately. Widget colours follow only when Keep Synced is on."))
        self.list = QListWidget(); self.list.setMinimumHeight(250)
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
        preview = ImagePanel(asset_path(f"onboarding/widget_{family.family_id}.png"))
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
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.body.addWidget(text_label("Bring your music to life", heading=True))
        self.body.addWidget(text_label("Choose which Visualizer modes are available. Detailed tuning and presets remain in full Settings."))
        self.enabled = _check("Enable Visualizer", False, self._enable)
        self.body.addWidget(self.enabled)
        self.rows = CheckList(); self.body.addWidget(self.rows, 1)
        self.status = text_label(""); self.body.addWidget(self.status)
        self.rows.itemChanged.connect(self._toggle)
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
        with QSignalBlocker(self.rows):
            self.rows.clear()
            for mode in self._offered_modes:
                item = QListWidgetItem(mode.display_name); item.setData(Qt.ItemDataRole.UserRole, mode.mode_id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if mode.mode_id in active else Qt.CheckState.Unchecked)
                self.rows.addItem(item)
        self.rows.setEnabled(effective)

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
    "block_spins": "The whole picture turns over in 3D. At the halfway point you see its thin edge.", "burn": "A burning edge consumes the old image.",
    "crumble": "The old image breaks apart and falls away.", "diffuse": "The old image scatters into the new image.",
    "exploding_tiles": "Tiles burst outward to uncover the next image.", "glass_shatter": "The picture fractures into glass shards.",
    "ink_bloom": "Organic ink shapes spread across the picture.", "melt_drip": "The image melts into falling drips.",
    "particle": "Particles carry the image into the next scene.", "pixel_accretion": "Small pieces assemble the new picture.",
    "ripple": "Water-like ripples blend the two pictures.",
}


class TransitionsPage(Page):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.body.addWidget(text_label("How should your wallpapers change?", heading=True))
        self.body.addWidget(text_label("Select transitions to include in the available effects and random pool. Each preview shows 25%, 50% and 75% of the change."))
        self.rows = CheckList(); self.rows.setMinimumHeight(130); self.rows.setMaximumHeight(200)
        self.body.addWidget(self.rows)
        self.preview = ImagePanel(asset_path("onboarding/transition_crossfade.png"))
        self.preview.setMinimumHeight(180)
        self.body.addWidget(self.preview, 1)
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
        self._show(self.rows.currentItem(), None)
        self.status.setText("Random selection is on." if cfg["random_always"] else "Your current manual transition choice is kept when available.")

    def _show(self, item, previous):
        if item is None: return
        key = item.data(Qt.ItemDataRole.UserRole+1)
        self.preview.set_source(asset_path(f"onboarding/transition_{key}.png"))
        self.description.setText(item.text() + " — " + TRANSITION_COPY[key])

    def _toggle(self, item):
        cfg = self.settings.get("transitions")
        enabled = item.checkState() == Qt.CheckState.Checked
        name = item.data(Qt.ItemDataRole.UserRole)
        set_transition_activated(cfg, name, enabled)
        cfg["pool"][name] = enabled
        normalize_transition_capability_state(cfg)
        self.settings.set("transitions", cfg)
        self.refresh()


class ReadyPage(Page):
    arrangeRequested = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.body.addWidget(text_label("You're ready", heading=True))
        self.body.addWidget(text_label("Your choices are saved. Optional accounts can be connected later in Settings."))
        self.summary = text_label(""); self.body.addWidget(self.summary)
        self.body.addWidget(action("Back to Arrange", self.arrangeRequested.emit, secondary=True))
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
        self.summary.setText("\n\n".join(lines))
