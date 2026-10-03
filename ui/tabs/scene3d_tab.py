"""The 3D Settings tab: how much detail every 3D transition and 3D Visualizer draws with.

Three pills over one ``scene3d`` settings section, each level storing only its own choice:
**General** (the tier for everything 3D; Auto picks by the GPU), **3D Transitions** and
**3D Visualizers** (a family tier, or Use General), and under 3D Visualizers one row per 3D mode
(its own tier, or Auto to follow the family). ``core/settings/scene3d_quality.py`` is the one
resolver; every "Now:" label shows what it resolves to, so the inheritance is visible.
A 3D transition's own Anti-aliasing, Bloom and Motion Blur stay on its Transitions page.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.logging.logger import get_logger
from core.settings.defaults import get_default_setting
from core.settings.scene3d_quality import (
    SCENE3D_ENTRY_CHOICES,
    SCENE3D_FAMILY_CHOICES,
    SCENE3D_GENERAL_CHOICES,
    SCENE3D_SECTION,
    read_scene3d_section,
    resolve_scene3d_tier,
    scene3d_auto_tier,
    scene3d_entry_key,
)
from core.settings.settings_manager import SettingsManager
from ui.flow_layout import FlowContainer
from ui.tabs import shared_styles
from ui.tabs.shared_styles import add_aligned_row as shared_add_aligned_row, style_group_box
from ui.widgets import StyledComboBox

logger = get_logger(__name__)

PAGES = (("general", "General"), ("transitions", "3D Transitions"), ("visualizers", "3D Visualizers"))
_FAMILY_LABELS = {"General": "Use General"}
_TIERS_TIP = (
    "High: smooth edges (multisampling), shadows, every effect and the densest geometry.\n"
    "Balanced: lighter multisampling and fewer particles; effects stay on.\n"
    "Performance: no multisampling, shadows or optional effects; lighter geometry.\n"
    "KAK: the bare minimum: no optional effect, every density at its lowest."
)


def scene3d_visualizer_entries() -> tuple[tuple[str, str], ...]:
    """(mode id, display name) of each 3D Visualizer mode with its own tier, from the canonical
    ``scene3d`` section (the defaults own which entries exist)."""
    from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS, get_visualizer_mode_descriptor

    canonical = get_default_setting(SCENE3D_SECTION, missing=None) or {}
    return tuple((mode, get_visualizer_mode_descriptor(mode).display_name) for mode in VISUALIZER_MODE_IDS
                 if scene3d_entry_key(mode) in canonical)


class Scene3DTab(QWidget):
    """General / 3D Transitions / 3D Visualizers detail tiers."""

    scene3d_changed = Signal()
    _LABEL_WIDTH = 160

    def __init__(self, settings: SettingsManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._loading = True
        self._combos: dict[str, StyledComboBox] = {}       # scene3d key -> combo
        self._now_labels: dict[str, QLabel] = {}            # scene3d key -> its "Now:" label
        self._pages: dict[str, QWidget] = {}
        self._setup_ui()
        self._load_settings()
        self._loading = False

    # ---- construction -------------------------------------------------------------------

    def _setup_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(shared_styles.SCROLL_AREA_STYLE)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        title = QLabel("3D Settings")
        shared_styles.apply_shared_label_style(title, "PAGE_TITLE_STYLE")
        layout.addWidget(title)
        intro = QLabel("How much detail 3D transitions and 3D Visualizers draw with, for this computer.")
        intro.setWordWrap(True)
        shared_styles.apply_shared_label_style(intro, "ACCESSIBILITY_DESC_STYLE")
        layout.addWidget(intro)

        nav = FlowContainer(h_spacing=8, v_spacing=8)
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons: dict[str, QPushButton] = {}
        for key, label in PAGES:
            button = QPushButton(label)
            button.setCheckable(True)
            shared_styles.bind_shared_styles(button, "TRANSITION_NAV_PILL_STYLE", base_style="")
            button.clicked.connect(lambda _checked=False, k=key: self.show_page(k))
            self._nav_group.addButton(button)
            self._nav_buttons[key] = button
            nav.addWidget(button)
        layout.addWidget(nav)

        self._pages["general"] = self._page(layout, "3D Detail", (
            ("detail", "3D Detail:", SCENE3D_GENERAL_CHOICES,
             "The detail for everything 3D, unless 3D Transitions, 3D Visualizers or one mode "
             "sets its own. Auto picks by the graphics card in use.\n\n" + _TIERS_TIP),
        ))
        self._pages["transitions"] = self._page(layout, "3D Transitions", (
            ("transitions_detail", "3D Detail:", SCENE3D_FAMILY_CHOICES,
             "The detail for 3D transitions. Use General follows the General page. A transition's "
             "own Anti-aliasing, Bloom and Motion Blur (on its page under Transitions) set to Auto "
             "follow this.\n\n" + _TIERS_TIP),
        ))
        rows = [("visualizers_detail", "3D Detail:", SCENE3D_FAMILY_CHOICES,
                 "The detail for 3D Visualizers. Use General follows the General page; each mode "
                 "below can set its own.\n\n" + _TIERS_TIP)]
        rows.extend((scene3d_entry_key(mode), f"{name}:", SCENE3D_ENTRY_CHOICES,
                     f"The detail {name} draws with. Auto follows 3D Visualizers above.")
                    for mode, name in scene3d_visualizer_entries())
        self._pages["visualizers"] = self._page(layout, "3D Visualizers", tuple(rows))

        layout.addStretch()
        scroll.setWidget(content)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)
        shared_styles.bind_shared_styles(self, "COMBOBOX_STYLE")
        self.show_page("general")

    def _page(self, layout: QVBoxLayout, title: str, rows) -> QWidget:
        group = QGroupBox(title)
        style_group_box(group)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(0, 12, 0, 0)
        group_layout.setSpacing(8)
        for key, label, choices, tip in rows:
            row, _label = shared_add_aligned_row(group_layout, label, label_width=self._LABEL_WIDTH)
            combo = StyledComboBox(size_variant="compact")
            for choice in choices:
                combo.addItem(_FAMILY_LABELS.get(choice, choice), choice)
            combo.setToolTip(tip)
            combo.currentIndexChanged.connect(lambda _index, k=key: self._on_changed(k))
            row.addWidget(combo)
            now = QLabel("")
            now.setToolTip("What this resolves to right now.")
            row.addWidget(now)
            row.addStretch()
            self._combos[key] = combo
            self._now_labels[key] = now
        layout.addWidget(group)
        return group

    # ---- navigation ---------------------------------------------------------------------

    def show_page(self, key: str) -> None:
        if key not in self._pages:
            raise KeyError(f"unknown 3D Settings page: {key!r}")
        for page_key, page in self._pages.items():
            page.setVisible(page_key == key)
        button = self._nav_buttons[key]
        if not button.isChecked():
            button.setChecked(True)

    # ---- settings -----------------------------------------------------------------------

    def load_from_settings(self) -> None:
        self._loading = True
        try:
            self._load_settings()
        finally:
            self._loading = False

    def _section(self) -> dict:
        return read_scene3d_section(self._settings.get)

    def _load_settings(self) -> None:
        section = self._section()
        for key, combo in self._combos.items():
            index = combo.findData(section.get(key))
            if index < 0:
                index = combo.findData(get_default_setting(f"{SCENE3D_SECTION}.{key}", missing=None))
            combo.blockSignals(True)
            combo.setCurrentIndex(max(0, index))
            combo.blockSignals(False)
        self._refresh_now()

    def _on_changed(self, key: str) -> None:
        if self._loading:
            return
        value = self._combos[key].currentData()
        self._settings.set(f"{SCENE3D_SECTION}.{key}", value)
        logger.debug("[SCENE3D_TAB] %s = %s", key, value)
        self._refresh_now()
        self.scene3d_changed.emit()

    def _refresh_now(self) -> None:
        from rendering.quick.bootstrap import last_validated_gpu

        gpu = last_validated_gpu()
        section = self._section()
        for key, label in self._now_labels.items():
            if key == "detail":
                tier = scene3d_auto_tier(gpu) if section.get(key) == "Auto" else section.get(key)
                note = "" if section.get(key) != "Auto" or gpu else " (until the graphics card is known)"
                label.setText(f"Now: {tier}{note}")
            elif key == "transitions_detail":
                label.setText(f"Now: {resolve_scene3d_tier(section, 'transitions', gpu=gpu)}")
            elif key == "visualizers_detail":
                label.setText(f"Now: {resolve_scene3d_tier(section, 'visualizers', gpu=gpu)}")
            else:
                entry = key[: -len("_detail")]
                label.setText(f"Now: {resolve_scene3d_tier(section, 'visualizers', entry, gpu=gpu)}")


__all__ = ["PAGES", "Scene3DTab", "scene3d_visualizer_entries"]
