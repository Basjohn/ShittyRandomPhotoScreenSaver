"""Settings GUI theme selection surface.

The tab consumes an already-resolved process catalogue. It deliberately owns no
frozen-build/install-path policy: startup/build authority supplies a themes
directory before Settings construction.

Internal navigation:
- Setting Themes: landing page and live .srtheme selection.
- Widget Themes: intentionally empty future surface.
"""
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (QButtonGroup, QGroupBox, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget)
from core.logging.logger import get_logger
from core.settings.settings_manager import SettingsManager
from ui.flow_layout import FlowContainer
from ui.settings_theme_catalog import (SettingsThemeCatalog, activate_catalog_theme,
    get_current_settings_theme_catalog, persist_settings_theme_selection,
    resolve_persisted_settings_theme)
from ui.settings_theme_runtime import get_active_settings_theme, set_active_settings_theme
from ui.tabs import shared_styles
from ui.tabs.shared_styles import style_group_box

logger = get_logger(__name__)
_SETTING_THEMES_PAGE = 0
_WIDGET_THEMES_PAGE = 1

class ThemesTab(QWidget):
    """Settings theme catalogue with reserved future Widget Themes surface."""
    def __init__(self, settings: SettingsManager, parent: Optional[QWidget]=None, *,
                 catalog: SettingsThemeCatalog|None=None):
        super().__init__(parent)
        self._settings=settings
        self._catalog=catalog or get_current_settings_theme_catalog()
        self._loading_selection=False
        self._setup_ui()
        self._populate_settings_themes()

    def _setup_ui(self):
        scroll=QScrollArea(self); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(shared_styles.SCROLL_AREA_STYLE)
        content=QWidget(); layout=QVBoxLayout(content)
        layout.setContentsMargins(24,24,24,24); layout.setSpacing(16)
        title=QLabel("Themes")
        shared_styles.apply_shared_label_style(title,"PAGE_TITLE_STYLE")
        layout.addWidget(title)
        nav=FlowContainer(h_spacing=8,v_spacing=8)
        self._nav_group=QButtonGroup(self); self._nav_group.setExclusive(True)
        self.setting_themes_pill=self._make_nav_pill("Setting Themes",_SETTING_THEMES_PAGE)
        self.widget_themes_pill=self._make_nav_pill("Widget Themes",_WIDGET_THEMES_PAGE)
        nav.addWidget(self.setting_themes_pill); nav.addWidget(self.widget_themes_pill)
        layout.addWidget(nav)
        self._page_stack=QStackedWidget()
        self._page_stack.addWidget(self._build_setting_themes_page())
        self._page_stack.addWidget(self._build_widget_themes_page())
        layout.addWidget(self._page_stack,1)
        self.setting_themes_pill.setChecked(True)
        self._page_stack.setCurrentIndex(_SETTING_THEMES_PAGE)
        scroll.setWidget(content)
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.addWidget(scroll)

    def _make_nav_pill(self,text,page_index):
        button=QPushButton(text); button.setCheckable(True)
        # Keep both authored labels comfortably inside their pills.
        button.setMinimumWidth(220)
        shared_styles.bind_shared_styles(button,"NAV_PILL_STYLE",base_style="")
        self._nav_group.addButton(button,page_index)
        button.clicked.connect(lambda _checked=False,index=page_index:self._select_page(index))
        return button

    def _select_page(self,page_index):
        if page_index in (_SETTING_THEMES_PAGE,_WIDGET_THEMES_PAGE):
            self._page_stack.setCurrentIndex(page_index)

    def _build_setting_themes_page(self):
        page=QWidget(); page_layout=QVBoxLayout(page)
        page_layout.setContentsMargins(0,0,0,0); page_layout.setSpacing(16)
        group=QGroupBox("Available Settings Themes"); style_group_box(group)
        group_layout=QVBoxLayout(group); group_layout.setContentsMargins(18,16,18,18); group_layout.setSpacing(10)
        intro=QLabel("Choose the appearance used by the Settings window. A valid selection applies immediately.")
        intro.setWordWrap(True); shared_styles.apply_shared_label_style(intro,"INFO_LABEL_STYLE"); group_layout.addWidget(intro)
        self.theme_list=QListWidget(); self.theme_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        # Root Settings QSS still owns semantic list colours; only typography
        # is enlarged here for catalogue readability.
        self.theme_list.setStyleSheet("QListWidget { font-size: 12pt; }")
        self.theme_list.setMinimumHeight(240); group_layout.addWidget(self.theme_list)
        self.theme_status=QLabel(""); self.theme_status.setWordWrap(True)
        shared_styles.apply_shared_label_style(self.theme_status,"INFO_LABEL_STYLE"); group_layout.addWidget(self.theme_status)
        page_layout.addWidget(group); page_layout.addStretch(); return page

    def _build_widget_themes_page(self):
        # Intentionally empty. Widget families already own mature custom-colour systems.
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(0,0,0,0); layout.addStretch(); return page

    def _populate_settings_themes(self):
        self._loading_selection=True
        try:
            self.theme_list.clear()
            for entry in self._catalog.entries:
                item=QListWidgetItem(entry.name); item.setData(Qt.ItemDataRole.UserRole,entry.theme_id)
                if entry.is_builtin:
                    item.setToolTip("Built-in fallback. This appearance does not depend on any theme file.")
                elif entry.source_path is not None:
                    item.setToolTip(entry.source_path.name)
                self.theme_list.addItem(item)
            resolution=resolve_persisted_settings_theme(self._settings,self._catalog)
            self._select_theme_id(resolution.entry.theme_id)
            messages=[]
            if resolution.error: messages.append(resolution.error)
            if self._catalog.issues:
                count=len(self._catalog.issues)
                messages.append(f"{count} invalid theme file{' was' if count==1 else 's were'} ignored.")
                self.theme_status.setToolTip("\n".join(f"{i.source_path.name}: {i.error}" for i in self._catalog.issues))
            else: self.theme_status.setToolTip("")
            if not messages: messages.append("Default Dark is always available as a built-in fallback.")
            self.theme_status.setText(" ".join(messages))
        finally:
            self._loading_selection=False
        self.theme_list.currentItemChanged.connect(self._on_theme_selection_changed)

    def _select_theme_id(self,theme_id):
        for row in range(self.theme_list.count()):
            item=self.theme_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole)==theme_id:
                self.theme_list.setCurrentRow(row); return
        if self.theme_list.count(): self.theme_list.setCurrentRow(0)

    def _on_theme_selection_changed(self,current,previous):
        if self._loading_selection or current is None: return
        theme_id=current.data(Qt.ItemDataRole.UserRole)
        entry=self._catalog.entry_by_id(str(theme_id))
        if entry is None:
            self._restore_previous_item(previous); return
        previous_theme=get_active_settings_theme()
        try:
            activate_catalog_theme(entry)
            persist_settings_theme_selection(self._settings,self._catalog,entry.theme_id)
        except Exception as exc:
            logger.warning("Settings theme selection failed for %s: %s",entry.theme_id,exc,exc_info=True)
            try: set_active_settings_theme(previous_theme)
            except Exception: logger.debug("Failed to restore previous Settings theme",exc_info=True)
            self._restore_previous_item(previous)
            self.theme_status.setText(f"Could not apply {entry.name!r}; the previous theme remains active.")
            return
        self.theme_status.setText(f"Using {entry.name}. Default Dark remains the built-in fallback.")

    def _restore_previous_item(self,previous):
        blocker=QSignalBlocker(self.theme_list)
        try:
            if previous is not None: self.theme_list.setCurrentItem(previous)
            else:
                resolution=resolve_persisted_settings_theme(self._settings,self._catalog)
                self._select_theme_id(resolution.entry.theme_id)
        finally: del blocker
