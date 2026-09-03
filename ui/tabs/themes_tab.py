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
from time import perf_counter_ns
from PySide6.QtCore import QLineF, QSignalBlocker, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
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
    synced_settings_theme_id_for_widget,
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


def _theme_link_icon(locked: bool) -> QIcon:
    """Create a small antialiased vector-style lock/unlock icon.

    The icon is drawn from geometry at a few target resolutions rather than
    depending on a platform icon theme or another resource file. Its colour
    follows the active Settings semantic mode-button text role.
    """

    rgba = get_active_settings_theme().color("control.mode.text")
    color = QColor(rgba.r, rgba.g, rgba.b, rgba.a)
    icon = QIcon()
    for size in (16, 20, 24, 32):
        scale = float(size) / 18.0
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pen = QPen(color, max(1.2, 1.55 * scale))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        fill = QColor(color)
        fill.setAlpha(max(24, min(92, int(color.alpha() * 0.28))))
        painter.setBrush(fill)
        body = QRectF(4.2 * scale, 8.0 * scale, 9.6 * scale, 7.0 * scale)
        painter.drawRoundedRect(body, 1.7 * scale, 1.7 * scale)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        shackle = QPainterPath()
        if locked:
            shackle.moveTo(6.2 * scale, 8.0 * scale)
            shackle.lineTo(6.2 * scale, 6.5 * scale)
            shackle.cubicTo(
                6.2 * scale, 2.9 * scale,
                11.8 * scale, 2.9 * scale,
                11.8 * scale, 6.5 * scale,
            )
            shackle.lineTo(11.8 * scale, 8.0 * scale)
        else:
            shackle.moveTo(6.6 * scale, 8.0 * scale)
            shackle.lineTo(6.6 * scale, 6.6 * scale)
            shackle.cubicTo(
                6.6 * scale, 3.2 * scale,
                11.8 * scale, 3.2 * scale,
                11.8 * scale, 6.3 * scale,
            )
            shackle.lineTo(13.4 * scale, 6.3 * scale)
        painter.drawPath(shackle)

        painter.drawEllipse(QRectF(8.15 * scale, 10.1 * scale, 1.7 * scale, 1.7 * scale))
        painter.drawLine(QLineF(9.0 * scale, 11.8 * scale, 9.0 * scale, 13.0 * scale))
        painter.end()
        icon.addPixmap(pixmap)
    return icon


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

    def _make_link_button(self) -> QPushButton:
        button=QPushButton()
        button.setCheckable(True)
        # Relationship affordance: deliberately ~20% smaller than the former
        # 300px general mode toggle while remaining comfortably clickable.
        button.setMinimumWidth(240)
        button.setIconSize(QSize(16,16))
        shared_styles.bind_shared_styles(
            button,"THEME_LINK_BUTTON_STYLE",base_style=""
        )
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
        self.settings_keep_synced=self._make_link_button()
        group_layout.addWidget(self.settings_keep_synced,0,Qt.AlignmentFlag.AlignLeft)
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
        self.widget_keep_synced=self._make_link_button()
        group_layout.addWidget(self.widget_keep_synced,0,Qt.AlignmentFlag.AlignLeft)
        self.widget_theme_list=QListWidget(); self.widget_theme_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.widget_theme_list.setStyleSheet("QListWidget { font-size: 12pt; }")
        self.widget_theme_list.setMinimumHeight(240); group_layout.addWidget(self.widget_theme_list)
        self.widget_theme_status=QLabel(""); self.widget_theme_status.setWordWrap(True)
        shared_styles.apply_shared_label_style(self.widget_theme_status,"INFO_LABEL_STYLE"); group_layout.addWidget(self.widget_theme_status)
        page_layout.addWidget(group); page_layout.addStretch(); return page

    def _sync_link_buttons(self, checked: bool) -> None:
        """Publish one shared link state to both theme pages without recursion."""

        linked=bool(checked)
        text="Linked" if linked else "Independent"
        tooltip=(
            "Linked: choosing either a Settings Theme or a Widget Theme changes "
            "the other selector to its explicit matching pair."
            if linked
            else
            "Independent: Settings Themes and Widget Themes can be selected separately."
        )
        icon=_theme_link_icon(linked)
        for name in ("settings_keep_synced","widget_keep_synced"):
            button=getattr(self,name,None)
            if button is None:
                continue
            blocker=QSignalBlocker(button)
            button.setChecked(linked)
            button.setText(text)
            button.setIcon(icon)
            button.setToolTip(tooltip)
            del blocker

    def _update_widget_link_button(self, checked: bool | None = None) -> None:
        """Compatibility wrapper for the former Widget-only link control."""

        if checked is None:
            state=read_widget_theme_state(self._settings)
            checked=state.keep_synced
        self._sync_link_buttons(bool(checked))

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
        selection_started_ns=perf_counter_ns()
        theme_id=current.data(Qt.ItemDataRole.UserRole)
        entry=self._catalog.entry_by_id(str(theme_id))
        if entry is None:
            self._restore_previous_item(previous); return

        state=read_widget_theme_state(self._settings)
        linked_widget_id=None
        if state.keep_synced:
            linked_widget_id=synced_widget_theme_id_for_settings(
                get_current_widget_theme_catalog(),entry.theme_id
            )
            if linked_widget_id is None:
                self._restore_previous_item(previous)
                self.theme_status.setText(
                    "This Settings Theme has no matching Widget Theme. "
                    "Switch to Independent before selecting it."
                )
                return

        previous_theme=get_active_settings_theme()
        previous_settings_id=read_persisted_theme_id(self._settings)
        try:
            activate_catalog_theme(entry)
            persist_settings_theme_selection(self._settings,self._catalog,entry.theme_id)
            if state.keep_synced:
                self._resync_widget_theme_for_settings(entry.theme_id)
        except Exception as exc:
            logger.warning("Settings theme selection failed for %s: %s",entry.theme_id,exc,exc_info=True)
            try:
                set_active_settings_theme(previous_theme)
                previous_entry=self._catalog.entry_by_id(previous_settings_id)
                if previous_entry is not None:
                    persist_settings_theme_selection(
                        self._settings,self._catalog,previous_entry.theme_id
                    )
                if state.keep_synced:
                    activate_widget_theme_state(
                        self._settings,state,settings_theme_id=previous_settings_id,persist=True
                    )
            except Exception:
                logger.debug("Failed to restore previous linked theme pair",exc_info=True)
            self._restore_previous_item(previous)
            self.theme_status.setText(f"Could not apply {entry.name!r}; the previous theme remains active.")
            return

        # Rebuild the compact vector icon in the newly active Settings palette.
        self._sync_link_buttons(state.keep_synced)
        if state.keep_synced:
            widget_entry=get_current_widget_theme_catalog().entry_by_id(str(linked_widget_id))
            widget_name=widget_entry.name if widget_entry is not None else "matching Widget Theme"
            self.theme_status.setText(f"Using {entry.name}, linked to {widget_name}.")
        else:
            self.theme_status.setText(
                f"Using {entry.name} independently of the Widget Theme. "
                "Default Dark remains the built-in fallback."
            )
        logger.info(
            "[PERF][THEME_SELECT] source=settings theme=%s linked=%s total=%.2fms",
            entry.name,
            state.keep_synced,
            (perf_counter_ns()-selection_started_ns)/1_000_000.0,
        )

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
            self._sync_link_buttons(state.keep_synced)
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
        self.settings_keep_synced.toggled.connect(self._on_widget_keep_synced_changed)
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
            self._sync_link_buttons(state.keep_synced)
            self._select_widget_theme_id(resolved.theme.theme_id)
        finally:
            self._loading_widget_selection=False

        issues=len(catalog.issues)
        suffix=f" {issues} invalid Widget theme file{' was' if issues==1 else 's were'} ignored." if issues else ""
        if state.keep_synced:
            self.widget_theme_status.setText(f"Linked to {resolved.theme.name}.{suffix}")
        else:
            self.widget_theme_status.setText(f"Using {resolved.theme.name} independently.{suffix}")

    def _restore_widget_selection(self, previous, fallback_id: str) -> None:
        blocker=QSignalBlocker(self.widget_theme_list)
        try:
            if previous is not None:
                self.widget_theme_list.setCurrentItem(previous)
            else:
                self._select_widget_theme_id(fallback_id)
        finally:
            del blocker

    def _on_widget_theme_selection_changed(self,current,previous):
        if getattr(self,"_loading_widget_selection",False) or current is None: return
        selection_started_ns=perf_counter_ns()
        theme_id=str(current.data(Qt.ItemDataRole.UserRole) or "")
        catalog=get_current_widget_theme_catalog()
        state=read_widget_theme_state(self._settings)
        if theme_id != CUSTOM_WIDGET_THEME_ID and catalog.entry_by_id(theme_id) is None:
            self._restore_widget_selection(previous,state.selected_id); return
        if theme_id == CUSTOM_WIDGET_THEME_ID and state.custom_payload is None:
            self._restore_widget_selection(previous,state.selected_id); return

        if state.keep_synced:
            # Locked means bidirectional identity, not "Settings wins". A Widget
            # selection selects its explicitly linked Settings counterpart too.
            # Custom has no Settings identity, so it requires unlocking first.
            settings_theme_id=synced_settings_theme_id_for_widget(catalog,theme_id)
            settings_entry=(
                self._catalog.entry_by_id(settings_theme_id)
                if settings_theme_id is not None else None
            )
            if settings_entry is None:
                self._restore_widget_selection(previous,state.selected_id)
                self.widget_theme_status.setText(
                    "This Widget Theme has no available matching Settings Theme. "
                    "Switch to Independent before selecting it."
                )
                return

            previous_settings_id=read_persisted_theme_id(self._settings)
            previous_settings_theme=get_active_settings_theme()
            try:
                activate_catalog_theme(settings_entry)
                persist_settings_theme_selection(
                    self._settings,self._catalog,settings_entry.theme_id
                )
                next_state=WidgetThemeState(
                    selected_id=theme_id,
                    keep_synced=True,
                    custom_payload=state.custom_payload,
                )
                resolved=activate_widget_theme_state(
                    self._settings,next_state,settings_theme_id=settings_entry.theme_id,persist=True
                )
            except Exception as exc:
                logger.warning(
                    "Linked Widget theme selection failed for %s: %s",
                    theme_id,exc,exc_info=True,
                )
                try:
                    set_active_settings_theme(previous_settings_theme)
                    previous_entry=self._catalog.entry_by_id(previous_settings_id)
                    if previous_entry is not None:
                        persist_settings_theme_selection(
                            self._settings,self._catalog,previous_entry.theme_id
                        )
                    activate_widget_theme_state(
                        self._settings,state,settings_theme_id=previous_settings_id,persist=True
                    )
                except Exception:
                    logger.debug("Failed to roll back linked theme pair",exc_info=True)
                self._restore_widget_selection(previous,state.selected_id)
                self.widget_theme_status.setText(
                    "Could not apply the linked theme pair; the previous pair remains active."
                )
                return

            self._loading_selection=True
            try:
                blocker=QSignalBlocker(self.theme_list)
                self._select_theme_id(settings_entry.theme_id)
                del blocker
            finally:
                self._loading_selection=False
            self._sync_link_buttons(True)
            self.theme_status.setText(
                f"Using {settings_entry.name}, linked to {resolved.theme.name}."
            )
            self.widget_theme_status.setText(
                f"Using {resolved.theme.name}, linked to {settings_entry.name}."
            )
            logger.info(
                "[PERF][THEME_SELECT] source=widget theme=%s linked=True total=%.2fms",
                resolved.theme.name,
                (perf_counter_ns()-selection_started_ns)/1_000_000.0,
            )
            return

        # Independent mode changes only the Widget Theme and preserves the link
        # state as explicitly unlocked.
        next_state=WidgetThemeState(
            selected_id=theme_id,
            keep_synced=False,
            custom_payload=state.custom_payload,
        )
        resolved=activate_widget_theme_state(
            self._settings,next_state,settings_theme_id=read_persisted_theme_id(self._settings)
        )
        self._sync_link_buttons(False)
        self.widget_theme_status.setText(
            f"Using {resolved.theme.name} independently of the Settings Theme."
        )
        logger.info(
            "[PERF][THEME_SELECT] source=widget theme=%s linked=False total=%.2fms",
            resolved.theme.name,
            (perf_counter_ns()-selection_started_ns)/1_000_000.0,
        )

    def _on_widget_keep_synced_changed(self,checked):
        if getattr(self,"_loading_widget_selection",False): return
        checked=bool(checked)
        state=read_widget_theme_state(self._settings)
        settings_theme_id=read_persisted_theme_id(self._settings)
        selected_id=state.selected_id
        catalog=get_current_widget_theme_catalog()
        linked=None
        if checked:
            linked=synced_widget_theme_id_for_settings(catalog,settings_theme_id)
            if linked is None:
                # A locked relationship must always describe a real pair. Keep the
                # current independent state rather than publishing a fake link.
                self._sync_link_buttons(False)
                self.widget_theme_status.setText(
                    "This Settings Theme has no matching Widget Theme. "
                    "The themes remain Independent."
                )
                self.theme_status.setText(
                    "No matching Widget Theme is available; linking was not enabled."
                )
                return
            selected_id=linked
        next_state=WidgetThemeState(
            selected_id=selected_id,
            keep_synced=checked,
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
        self._sync_link_buttons(checked)
        settings_entry=self._catalog.entry_by_id(settings_theme_id)
        settings_name=settings_entry.name if settings_entry is not None else "Settings Theme"
        if checked:
            self.widget_theme_status.setText(
                f"Using {resolved.theme.name}, linked to {settings_name}."
            )
            self.theme_status.setText(
                f"Using {settings_name}, linked to {resolved.theme.name}."
            )
        else:
            self.widget_theme_status.setText(
                f"Using {resolved.theme.name} independently of the Settings Theme."
            )
            self.theme_status.setText(
                f"Using {settings_name} independently of the Widget Theme."
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
        # be stored before linking.
        next_state=WidgetThemeState(
            selected_id=linked_id,
            keep_synced=True,
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
        self._sync_link_buttons(True)
        settings_entry=self._catalog.entry_by_id(str(settings_theme_id))
        settings_name=settings_entry.name if settings_entry is not None else "Settings Theme"
        self.widget_theme_status.setText(
            f"Using {resolved.theme.name}, linked to {settings_name}."
        )

    def _restore_previous_item(self,previous):
        blocker=QSignalBlocker(self.theme_list)
        try:
            if previous is not None: self.theme_list.setCurrentItem(previous)
            else:
                resolution=resolve_persisted_settings_theme(self._settings,self._catalog)
                self._select_theme_id(resolution.entry.theme_id)
        finally: del blocker
