"""Settings GUI theme selection surface.

The tab consumes an already-resolved process catalogue. It deliberately owns no
frozen-build/install-path policy: startup/build authority supplies a themes
directory before Settings construction.

Internal navigation:
- Setting Themes: landing page and live .srtheme selection.
- Widget Themes: linked or independent runtime Widget Theme selection.
"""
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import QSignalBlocker, QSize, Qt
from PySide6.QtWidgets import (QButtonGroup, QGroupBox, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget)
from core.logging.logger import get_logger
from core.settings.settings_manager import SettingsManager
from ui.flow_layout import FlowContainer
from ui.settings_theme_catalog import (SettingsThemeCatalog, activate_catalog_theme,
    get_current_settings_theme_catalog, persist_settings_theme_selection,
    read_persisted_theme_id, resolve_persisted_settings_theme)
from ui.settings_theme_runtime import get_active_settings_theme, set_active_settings_theme
from ui.widget_theme_catalog import get_current_widget_theme_catalog
from ui.widget_theme_runtime import CUSTOM_WIDGET_THEME_ID, WidgetThemeState
from ui.widget_theme_selection import (
    activate_widget_theme_state,
    persist_widget_theme_state,
    read_widget_theme_state,
    resolve_widget_theme_state,
    synced_widget_theme_id_for_settings,
)
from ui.tabs import shared_styles
from ui.tabs.shared_styles import style_group_box

logger = get_logger(__name__)
_SETTING_THEMES_PAGE = 0
_WIDGET_THEMES_PAGE = 1


class _ThemePillButton(QPushButton):
    """Pill whose layout hint always includes the full authored label."""

    _MIN_WIDTH = 280
    _TEXT_PADDING = 112

    def sizeHint(self) -> QSize:  # noqa: N802
        hint = super().sizeHint()
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        return QSize(
            max(self._MIN_WIDTH, text_width + self._TEXT_PADDING),
            hint.height(),
        )

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()


class ThemesTab(QWidget):
    """Settings and runtime Widget theme catalogues with explicit linking."""
    def __init__(self, settings: SettingsManager, parent: Optional[QWidget]=None, *,
                 catalog: SettingsThemeCatalog|None=None):
        super().__init__(parent)
        self._settings=settings
        self._catalog=catalog or get_current_settings_theme_catalog()
        self._loading_selection=False
        self._setup_ui()
        self._populate_settings_themes()
        self._populate_widget_themes()

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
        button=_ThemePillButton(text); button.setCheckable(True)
        shared_styles.bind_shared_styles(button,"NAV_PILL_STYLE",base_style="")
        self._nav_group.addButton(button,page_index)
        button.clicked.connect(lambda _checked=False,index=page_index:self._select_page(index))
        return button

    def _select_page(self,page_index):
        if page_index in (_SETTING_THEMES_PAGE,_WIDGET_THEMES_PAGE):
            self._page_stack.setCurrentIndex(page_index)
            if page_index == _WIDGET_THEMES_PAGE:
                self._refresh_widget_theme_page_from_state()

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
        page=QWidget(); page_layout=QVBoxLayout(page)
        page_layout.setContentsMargins(0,0,0,0); page_layout.setSpacing(16)
        group=QGroupBox("Available Widget Themes"); style_group_box(group)
        group_layout=QVBoxLayout(group); group_layout.setContentsMargins(18,16,18,18); group_layout.setSpacing(10)
        intro=QLabel(
            "Choose the shared runtime widget palette. Card Surface and Card Border "
            "are edited once under Widgets → General → Appearance."
        )
        intro.setWordWrap(True); shared_styles.apply_shared_label_style(intro,"INFO_LABEL_STYLE"); group_layout.addWidget(intro)
        self.widget_keep_synced=QPushButton()
        self.widget_keep_synced.setCheckable(True)
        self.widget_keep_synced.setMinimumWidth(300)
        self.widget_keep_synced.setToolTip(
            "Linked: Settings Theme changes automatically select the explicitly paired Widget Theme. "
            "Independent: Widget Theme can be chosen separately."
        )
        shared_styles.bind_shared_styles(
            self.widget_keep_synced, "MODE_TOGGLE_BUTTON_STYLE", base_style=""
        )
        group_layout.addWidget(self.widget_keep_synced, 0, Qt.AlignmentFlag.AlignLeft)
        self.widget_theme_list=QListWidget(); self.widget_theme_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.widget_theme_list.setStyleSheet("QListWidget { font-size: 12pt; }")
        self.widget_theme_list.setMinimumHeight(240); group_layout.addWidget(self.widget_theme_list)
        self.widget_theme_status=QLabel(""); self.widget_theme_status.setWordWrap(True)
        shared_styles.apply_shared_label_style(self.widget_theme_status,"INFO_LABEL_STYLE"); group_layout.addWidget(self.widget_theme_status)
        page_layout.addWidget(group); page_layout.addStretch(); return page

    def _update_widget_link_button(self, checked: bool | None = None) -> None:
        if not hasattr(self, "widget_keep_synced"):
            return
        linked = self.widget_keep_synced.isChecked() if checked is None else bool(checked)
        self.widget_keep_synced.setText(
            "Linked to Settings Theme" if linked else "Independent Widget Theme"
        )

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
        self._resync_widget_theme_for_settings(entry.theme_id)

    def _populate_widget_themes(self):
        self._loading_widget_selection=True
        try:
            state=read_widget_theme_state(self._settings)
            catalog=get_current_widget_theme_catalog()
            self.widget_theme_list.clear()
            for entry in catalog.entries:
                item=QListWidgetItem(entry.name); item.setData(Qt.ItemDataRole.UserRole,entry.theme_id)
                if entry.is_builtin:
                    item.setToolTip("Built-in runtime fallback. No theme file is required.")
                elif entry.source_path is not None:
                    item.setToolTip(entry.source_path.name)
                self.widget_theme_list.addItem(item)
            if state.custom_payload is not None:
                custom=QListWidgetItem("Custom"); custom.setData(Qt.ItemDataRole.UserRole,CUSTOM_WIDGET_THEME_ID)
                custom.setToolTip("Settings-persisted user Widget Theme snapshot.")
                self.widget_theme_list.addItem(custom)
            self.widget_keep_synced.setChecked(state.keep_synced)
            self._update_widget_link_button(state.keep_synced)
            effective=activate_widget_theme_state(
                self._settings,
                state,
                settings_theme_id=read_persisted_theme_id(self._settings),
                persist=False,
            )
            self._select_widget_theme_id(effective.theme.theme_id if effective.is_custom else effective.theme.theme_id)
            issues=len(catalog.issues)
            suffix=f" {issues} invalid Widget theme file{' was' if issues==1 else 's were'} ignored." if issues else ""
            self.widget_theme_status.setText(f"Using {effective.theme.name}.{suffix}")
            if catalog.issues:
                self.widget_theme_status.setToolTip("\n".join(f"{issue.source_path.name}: {issue.error}" for issue in catalog.issues))
            else:
                self.widget_theme_status.setToolTip("")
        finally:
            self._loading_widget_selection=False
        self.widget_theme_list.currentItemChanged.connect(self._on_widget_theme_selection_changed)
        self.widget_keep_synced.toggled.connect(self._on_widget_keep_synced_changed)

    def _select_widget_theme_id(self,theme_id):
        for row in range(self.widget_theme_list.count()):
            item=self.widget_theme_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole)==theme_id:
                self.widget_theme_list.setCurrentRow(row); return
        if self.widget_theme_list.count(): self.widget_theme_list.setCurrentRow(0)

    def _refresh_widget_theme_page_from_state(self):
        """Refresh linked/Custom UI when this lazy page becomes visible.

        Card Surface edits live under Widgets -> General and can create Custom while
        this Themes tab already exists. Refreshing on page entry keeps both surfaces
        coherent without a polling owner or cross-tab mutation service.
        """

        if not hasattr(self, "widget_theme_list"):
            return
        state=read_widget_theme_state(self._settings)
        catalog=get_current_widget_theme_catalog()

        custom_row=-1
        for row in range(self.widget_theme_list.count()):
            item=self.widget_theme_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole)==CUSTOM_WIDGET_THEME_ID:
                custom_row=row
                break
        if state.custom_payload is not None and custom_row < 0:
            custom=QListWidgetItem("Custom")
            custom.setData(Qt.ItemDataRole.UserRole,CUSTOM_WIDGET_THEME_ID)
            custom.setToolTip("Settings-persisted user Widget Theme snapshot.")
            self.widget_theme_list.addItem(custom)
        elif state.custom_payload is None and custom_row >= 0:
            self.widget_theme_list.takeItem(custom_row)

        resolved=resolve_widget_theme_state(
            state,
            catalog=catalog,
            settings_theme_id=read_persisted_theme_id(self._settings),
        )
        self._loading_widget_selection=True
        try:
            blocker=QSignalBlocker(self.widget_keep_synced)
            self.widget_keep_synced.setChecked(state.keep_synced)
            self._update_widget_link_button(state.keep_synced)
            del blocker
            self._select_widget_theme_id(resolved.theme.theme_id)
        finally:
            self._loading_widget_selection=False

        issues=len(catalog.issues)
        suffix=f" {issues} invalid Widget theme file{' was' if issues==1 else 's were'} ignored." if issues else ""
        if state.keep_synced:
            self.widget_theme_status.setText(f"Linked to {resolved.theme.name}.{suffix}")
        else:
            self.widget_theme_status.setText(f"Using {resolved.theme.name} independently.{suffix}")

    def _on_widget_theme_selection_changed(self,current,previous):
        if getattr(self,"_loading_widget_selection",False) or current is None: return
        theme_id=str(current.data(Qt.ItemDataRole.UserRole) or "")
        catalog=get_current_widget_theme_catalog()
        state=read_widget_theme_state(self._settings)
        if theme_id != CUSTOM_WIDGET_THEME_ID and catalog.entry_by_id(theme_id) is None:
            self._select_widget_theme_id(state.selected_id); return
        if theme_id == CUSTOM_WIDGET_THEME_ID and state.custom_payload is None:
            self._select_widget_theme_id(state.selected_id); return
        # A deliberate independent Widget Theme choice necessarily breaks sync;
        # otherwise the linked Settings identity would immediately override it.
        next_state=WidgetThemeState(
            selected_id=theme_id,
            keep_synced=False,
            card_material_override=state.card_material_override,
            custom_payload=state.custom_payload,
        )
        blocker=QSignalBlocker(self.widget_keep_synced)
        self.widget_keep_synced.setChecked(False)
        self._update_widget_link_button(False)
        del blocker
        resolved=activate_widget_theme_state(
            self._settings,next_state,settings_theme_id=read_persisted_theme_id(self._settings)
        )
        self.widget_theme_status.setText(f"Using {resolved.theme.name} independently of the Settings Theme.")

    def _on_widget_keep_synced_changed(self,checked):
        if getattr(self,"_loading_widget_selection",False): return
        checked=bool(checked)
        self._update_widget_link_button(checked)
        state=read_widget_theme_state(self._settings)
        settings_theme_id=read_persisted_theme_id(self._settings)
        selected_id=state.selected_id
        catalog=get_current_widget_theme_catalog()
        linked=None
        if checked:
            linked=synced_widget_theme_id_for_settings(catalog,settings_theme_id)
            if linked is not None:
                # Link is a real identity relationship, not just a transient resolver
                # preference. Persist the paired id so unlinking later freezes the
                # currently visible Widget Theme instead of resurrecting stale state.
                selected_id=linked
        next_state=WidgetThemeState(
            selected_id=selected_id,
            keep_synced=checked,
            card_material_override=state.card_material_override,
            custom_payload=state.custom_payload,
        )
        resolved=activate_widget_theme_state(
            self._settings,next_state,settings_theme_id=settings_theme_id
        )
        self._loading_widget_selection=True
        try:
            self._select_widget_theme_id(resolved.theme.theme_id)
        finally:
            self._loading_widget_selection=False
        if checked:
            if linked is None:
                self.widget_theme_status.setText(
                    "Linked mode is on, but this Settings Theme has no paired Widget Theme; "
                    "the current Widget Theme remains in use."
                )
            else:
                self.widget_theme_status.setText(f"Synced to {resolved.theme.name}.")
        else:
            self.widget_theme_status.setText(
                f"Using {resolved.theme.name} independently of the Settings Theme."
            )

    def _resync_widget_theme_for_settings(self,settings_theme_id):
        if not hasattr(self,"widget_theme_list"): return
        state=read_widget_theme_state(self._settings)
        if not state.keep_synced: return
        catalog=get_current_widget_theme_catalog()
        linked_id=synced_widget_theme_id_for_settings(catalog,str(settings_theme_id))
        if linked_id is None:
            self.widget_theme_status.setText(
                "Linked mode is on, but this Settings Theme has no paired Widget Theme; "
                "the current Widget Theme remains in use."
            )
            return
        # Persist the effective linked identity as well as publishing it. This makes
        # unlinking a freeze operation: the currently visible Widget Theme remains
        # selected instead of snapping back to whichever independent id happened to
        # be stored before linking. Surface Style remains orthogonal.
        next_state=WidgetThemeState(
            selected_id=linked_id,
            keep_synced=True,
            card_material_override=state.card_material_override,
            custom_payload=state.custom_payload,
        )
        resolved=activate_widget_theme_state(
            self._settings,next_state,settings_theme_id=str(settings_theme_id),persist=True
        )
        self._loading_widget_selection=True
        try:
            self._select_widget_theme_id(resolved.theme.theme_id)
        finally:
            self._loading_widget_selection=False
        self.widget_theme_status.setText(f"Synced to {resolved.theme.name}.")

    def _restore_previous_item(self,previous):
        blocker=QSignalBlocker(self.theme_list)
        try:
            if previous is not None: self.theme_list.setCurrentItem(previous)
            else:
                resolution=resolve_persisted_settings_theme(self._settings,self._catalog)
                self._select_theme_id(resolution.entry.theme_id)
        finally: del blocker
