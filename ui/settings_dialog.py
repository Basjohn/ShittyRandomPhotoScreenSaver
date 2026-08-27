"""
Settings Dialog for screensaver configuration.

Features gorgeous UI with:
- Custom title bar (no native window border)
- Drop shadow effect
- Resizable window
"""
import sys
import time
import os
import weakref
from typing import Dict, Optional, Any
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
    QLabel, QStackedWidget, QGraphicsDropShadowEffect, QSizeGrip,
    QFileDialog, QMenu, QScrollArea, QStyle, QStyleOptionButton,
    QStylePainter,
)
from PySide6.QtCore import Qt, QPoint, QRect, QRectF, Signal, QUrl, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QGuiApplication, QPainterPath, QDesktopServices

from core.logging.logger import get_log_dir, get_logger, is_perf_metrics_enabled
from core.build_profile import is_diagnostic_build
from core.mc import is_mc_build
from core.settings.settings_manager import SettingsManager
from core.threading.manager import ThreadManager
from core.settings.visualizer_preset_transfer import (
    export_visualizer_presets_zip,
    import_visualizer_preset_json_files,
    import_visualizer_presets_archive,
    import_visualizer_presets_folder,
)
from core.animation import AnimationManager
from ui.tabs import SourcesTab, TransitionsTab, WidgetsTab, DisplayTab, AccessibilityTab, ThemesTab
from ui.styled_popup import StyledPopup
from ui.tabs import shared_styles
from ui.widgets.control_shadow import (
    apply_shadows_to_existing,
    apply_shadows_to_inputs,
)
from ui.settings_dialog_cache import get_settings_dialog_cache
from ui.settings_theme_runtime import (
    get_active_settings_theme,
    subscribe_settings_theme,
)
from ui.settings_theme_spec import SettingsThemeSpec

logger = get_logger(__name__)


def _record_diagnostic_stage(stage: str, **fields: object) -> None:
    """Record native Settings presentation boundaries only for diagnostics."""

    if not is_diagnostic_build():
        return
    from core.logging.crash_capture import record_diagnostic_stage

    record_diagnostic_stage(stage, **fields)

_SETTINGS_THEME = get_active_settings_theme()
_LIVE_SETTINGS_DIALOGS: weakref.WeakSet = weakref.WeakSet()


def _theme_qcolor(
    token: str,
    theme: SettingsThemeSpec | None = None,
) -> QColor:
    """Convert one semantic Settings theme colour into Qt's QColor."""

    resolved_theme = theme or _SETTINGS_THEME
    value = resolved_theme.color(token)
    return QColor(*value.as_tuple())


def _theme_opaque_qcolor(
    token: str,
    theme: SettingsThemeSpec | None = None,
) -> QColor:
    """Use a theme surface's RGB as an opaque renderer camouflage colour."""

    resolved_theme = theme or _SETTINGS_THEME
    value = resolved_theme.color(token)
    return QColor(value.r, value.g, value.b, 255)


# Fragile forged-edge geometry remains renderer-owned by design.  The forged
# backing/corner camouflage is not independently themeable: it follows the
# shell surface immediately inside the native edge, forced opaque so the fake
# rounded corner continues to hide the rectangular acrylic HWND underneath.
SETTINGS_OUTER_CORNER_RADIUS = 6.5
SETTINGS_OUTER_BORDER_WIDTH = 4.0
SETTINGS_OUTER_BORDER_BACKING_WIDTH = 6.0
SETTINGS_OUTER_BORDER_COLOR = _theme_qcolor("chrome.outer_border")
SETTINGS_FORGED_EDGE_COLOR = _theme_opaque_qcolor("window.titlebar.surface")
SETTINGS_OUTER_BORDER_BACKING_COLOR = SETTINGS_FORGED_EDGE_COLOR
SETTINGS_CORNER_COVER_COLOR = SETTINGS_FORGED_EDGE_COLOR


def _install_settings_dialog_theme(theme: SettingsThemeSpec) -> None:
    """Install live shell colours without altering forged-edge geometry."""

    global _SETTINGS_THEME
    global SETTINGS_OUTER_BORDER_COLOR
    global SETTINGS_FORGED_EDGE_COLOR
    global SETTINGS_OUTER_BORDER_BACKING_COLOR
    global SETTINGS_CORNER_COVER_COLOR

    _SETTINGS_THEME = theme
    SETTINGS_OUTER_BORDER_COLOR = _theme_qcolor("chrome.outer_border", theme)
    forged_edge = _theme_opaque_qcolor("window.titlebar.surface", theme)
    SETTINGS_FORGED_EDGE_COLOR = forged_edge
    SETTINGS_OUTER_BORDER_BACKING_COLOR = forged_edge
    SETTINGS_CORNER_COVER_COLOR = forged_edge


class CustomTitleBar(QWidget):
    """Custom title bar for frameless window."""
    
    # Signals
    close_clicked = Signal()
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize custom title bar.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._drag_pos = QPoint()
        self._setup_ui()
        
    def _setup_ui(self) -> None:
        """Setup title bar UI."""
        self.setFixedHeight(40)
        self.setObjectName("customTitleBar")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)
        
        # Title
        self.title_label = QLabel("SRPSS SETTINGS")
        self.title_label.setObjectName("titleBarLabel")
        title_font = QFont("Jost", 15)
        title_font.setFamilies(["Jost", "Segoe UI", "Arial", "Sans Serif"])
        title_font.setWeight(QFont.Weight.Bold)
        self.title_label.setFont(title_font)
        # Subtle drop shadow so the title reads crisply against bright
        # backgrounds without overwhelming the frame shadow.
        title_shadow = QGraphicsDropShadowEffect(self)
        title_shadow.setBlurRadius(8)
        title_shadow.setOffset(0, 1)
        title_shadow.setColor(QColor(100, 100, 100, 70))
        self.title_label.setGraphicsEffect(title_shadow)
        
        # Buttons
        self.minimize_btn = QPushButton("−")
        self.minimize_btn.setObjectName("titleBarButton")
        self.minimize_btn.setFixedSize(40, 30)
        self.minimize_btn.clicked.connect(self.minimize_clicked.emit)
        
        self.maximize_btn = QPushButton("□")
        self.maximize_btn.setObjectName("titleBarButton")
        self.maximize_btn.setFixedSize(40, 30)
        self.maximize_btn.clicked.connect(self.maximize_clicked.emit)
        
        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("titleBarCloseButton")
        self.close_btn.setFixedSize(40, 30)
        self.close_btn.clicked.connect(self.close_clicked.emit)
        
        # Layout
        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.minimize_btn)
        layout.addWidget(self.maximize_btn)
        layout.addWidget(self.close_btn)
    
    def mousePressEvent(self, event):
        """Handle mouse press for window dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for window dragging."""
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
    
    def mouseDoubleClickEvent(self, event):
        """Toggle maximize on double-click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_clicked.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


class TabButton(QPushButton):
    """Navigation tab with separately rendered icon and text content.

    The QPushButton continues to own interaction/state and keeps its full text
    value for tests/accessibility. Painting the icon and label as dedicated
    child widgets avoids Windows colour-emoji clipping and lets the existing
    crisp QLabel shadow renderer handle the text without duplicating the icon.
    """

    _ICON_PIXEL_SIZE = 17  # Previously inherited the 15px tab QSS: +2px.
    _ICON_BOX_SIZE = 26
    _ICON_HOST_SIZE = 30  # Breathing room for the glyph + renderer-owned shadow.
    _TEXT_POINT_SIZE = 12.25  # 15px at 96 DPI is 11.25pt: requested +1pt.
    _MINIMUM_HEIGHT = 52  # Previous minimum was 50px: requested +2px.

    def __init__(
        self,
        text: str,
        icon_text: str = "",
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize tab button.

        Args:
            text: Button text.
            icon_text: Icon text (emoji or symbol).
            parent: Parent widget.
        """
        super().__init__(parent)

        # Preserve the historical public button text even though the native
        # label is suppressed in paintEvent in favour of unclipped children.
        self._tab_label_text = text
        self._tab_icon_text = icon_text
        self.setText(f"{icon_text} {text}" if icon_text else text)
        self.setAccessibleName(text)
        self.setCheckable(True)
        self.setObjectName("tabButton")
        self.setMinimumHeight(self._MINIMUM_HEIGHT)

        # The parent button's QSS still owns its translucent body/border. Child
        # content is positioned to match the existing 20px left padding plus
        # the tab's 3px left margin.
        content_layout = QHBoxLayout(self)
        content_layout.setContentsMargins(23, 0, 20, 0)
        content_layout.setSpacing(6)

        if icon_text:
            self._tab_icon_host = QWidget(self)
            self._tab_icon_host.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                True,
            )
            self._tab_icon_host.setFixedSize(
                self._ICON_HOST_SIZE,
                self._ICON_HOST_SIZE,
            )

            self._tab_icon_label = QLabel(icon_text, self._tab_icon_host)
            # Construction owns the icon; control_shadow.py owns its shadow.
            self._tab_icon_label.setProperty("settingsNavIcon", True)
            self._tab_icon_label.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                True,
            )
            self._tab_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tab_icon_label.setGeometry(
                0,
                0,
                self._ICON_BOX_SIZE,
                self._ICON_BOX_SIZE,
            )
            icon_font = QFont("Segoe UI Emoji")
            icon_font.setFamilies(
                [
                    "Segoe UI Emoji",
                    "Noto Color Emoji",
                    "Apple Color Emoji",
                    "Segoe UI Symbol",
                ]
            )
            icon_font.setPixelSize(self._ICON_PIXEL_SIZE)
            self._tab_icon_label.setFont(icon_font)
            self._tab_icon_label.setStyleSheet(
                "background: transparent; border: none; padding: 0px; margin: 0px;"
            )

            content_layout.addWidget(
                self._tab_icon_host,
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )

        self._tab_text_label = QLabel(text, self)
        self._tab_text_label.setObjectName("tabButtonText")
        self._tab_text_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self._tab_text_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        text_font = QFont("Jost")
        text_font.setFamilies(["Jost", "Segoe UI", "Arial", "Sans Serif"])
        text_font.setPointSizeF(self._TEXT_POINT_SIZE)
        text_font.setWeight(QFont.Weight.DemiBold)
        self._tab_text_label.setFont(text_font)
        content_layout.addWidget(
            self._tab_text_label,
            1,
            Qt.AlignmentFlag.AlignVCenter,
        )

        self.toggled.connect(self._sync_content_style)
        self._sync_content_style()

    def _sync_content_style(self, *_args) -> None:
        if self.isChecked():
            token = "navigation.tab.selected_text"
            weight = QFont.Weight.Bold
        elif self.underMouse():
            token = "navigation.tab.hover_text"
            weight = QFont.Weight.DemiBold
        else:
            token = "navigation.tab.text"
            weight = QFont.Weight.DemiBold

        color = _SETTINGS_THEME.color(token)
        self._tab_text_label.setStyleSheet(
            "background: transparent; border: none; padding: 0px; margin: 0px;"
            f" color: rgba({color.r}, {color.g}, {color.b}, {color.a});"
        )
        font = self._tab_text_label.font()
        font.setWeight(weight)
        self._tab_text_label.setFont(font)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        super().enterEvent(event)
        self._sync_content_style()

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        super().leaveEvent(event)
        self._sync_content_style()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        """Paint only the native/QSS button chrome; children paint the content."""
        del event
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.text = ""
        painter = QStylePainter(self)
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)


class CornerSizeGrip(QSizeGrip):
    """Custom size grip with a subtle white dotted diagonal indicator."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("cornerSizeGrip")
        # Slightly larger footprint so the diagonal cut reads clearly.
        self.setFixedSize(24, 24)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        color = _theme_qcolor("chrome.size_grip")
        pen = QPen(color)
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(pen)

        w = self.width()
        h = self.height()

        # Three short diagonal strokes that read as a "cut" into the
        # corner rather than a tiny triangle of pixels.
        margin = 3
        for offset in (0, 5, 10):
            x1 = w - margin - offset
            y1 = h - margin
            x2 = w - margin
            y2 = h - margin - offset
            if x1 >= 0 and y2 >= 0:
                painter.drawLine(x1, y1, x2, y2)


class ResetDefaultsDialog(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        card = QWidget(self)
        card.setObjectName("resetDefaultsDialogCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        title_bar = CustomTitleBar(card)
        title_bar.title_label.setText("Reset To Defaults")
        title_bar.minimize_btn.hide()
        title_bar.maximize_btn.hide()
        title_bar.close_clicked.connect(self.reject)
        card_layout.addWidget(title_bar)

        body = QWidget(card)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 20, 24, 20)
        body_layout.setSpacing(16)

        # Simple confirmation text shown after settings have already been
        # reverted to their canonical defaults.
        message = QLabel("Settings reverted to defaults!")
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        body_layout.addWidget(message)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        buttons_row.addWidget(ok_btn)
        body_layout.addLayout(buttons_row)

        card_layout.addWidget(body)

        theme = get_active_settings_theme()
        popup_shadow = theme.shadow("popup.dialog")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(popup_shadow.blur_radius)
        shadow.setOffset(popup_shadow.offset_x, popup_shadow.offset_y)
        shadow.setColor(QColor(*popup_shadow.color.as_tuple()))
        card.setGraphicsEffect(shadow)

        popup_surface = theme.color("popup.container.surface")
        popup_border = theme.color("popup.container.border")
        card.setStyleSheet(
            "QWidget#resetDefaultsDialogCard {"
            f"background-color: rgba({popup_surface.r}, {popup_surface.g}, "
            f"{popup_surface.b}, {popup_surface.a});"
            f"border: 1px solid rgba({popup_border.r}, {popup_border.g}, "
            f"{popup_border.b}, {popup_border.a});"
            "border-radius: 10px;"
            "}"
        )

        outer_layout.addWidget(card)
        self.adjustSize()

        # Own the auto-dismiss timer so an early close cannot leave a late
        # callback targeting an already-closing toast.
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self.accept)
        self._auto_close_timer.start(2000)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            try:
                # Center the toast within the parent dialog's client rect so
                # it always appears above the content without creating a
                # separate native window.
                geom = parent.rect()
                self.move(geom.center() - self.rect().center())
                self.raise_()
            except Exception as e:
                logger.debug("[SETTINGS] Exception suppressed: %s", e)

    def accept(self) -> None:
        """Close the toast when acknowledged or after timeout."""
        timer = getattr(self, "_auto_close_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()
        self.close()

    def reject(self) -> None:
        """Treat rejection the same as acceptance for this toast."""
        self.accept()


class SettingsDialog(QDialog):
    """
    Main settings dialog with gorgeous UI.
    
    Features:
    - Custom title bar (frameless)
    - Drop shadow
    - Resizable
    - Animated tab switching
    - Dark theme
    - Sidebar tabs including Themes between Accessibility and About
    """
    
    def __init__(self, settings_manager: SettingsManager,
                 animation_manager: AnimationManager,
                 parent: Optional[QWidget] = None,
                 *,
                 runtime_generation: object | None = None,
                 themes_directory: str | os.PathLike[str] | None = None):
        """
        Initialize settings dialog.
        
        Args:
            settings_manager: Settings manager instance
            animation_manager: Animation manager for UI animations
            parent: Parent widget
            themes_directory: Optional caller-resolved packaged themes directory.
                When omitted, the temporary path seam uses its build-replace
                stub and then the repository-local themes/ fallback.
        """
        # Resolve the final persisted selection before this QWidget or any
        # Settings child exists. There is no intermediate Default Dark
        # activation before a valid custom theme, so this cannot create a
        # Default->custom first-paint flash.
        try:
            from ui.settings_theme_catalog import activate_persisted_settings_theme
            from ui.settings_theme_paths import resolve_settings_themes_directory

            resolved_themes_directory = resolve_settings_themes_directory(
                themes_directory
            )
            activate_persisted_settings_theme(
                settings_manager,
                resolved_themes_directory,
            )
        except Exception:
            # Runtime activation is transactional; cold startup already owns
            # compiled Default Dark, so disk themes can never leave Settings
            # without a valid style.
            logger.warning(
                "Failed to resolve persisted Settings theme before UI construction",
                exc_info=True,
            )

        super().__init__(parent)

        self._runtime_generation = runtime_generation
        self._settings = settings_manager
        self._animations = animation_manager
        self._is_maximized = False
        self._drag_pos = QPoint()
        self._dragging = False
        self._tab_scroll_cache: Dict[str, int] = {}
        self._tab_widgets: Dict[str, QWidget] = {}
        self._tab_builders: Dict[str, Any] = {}
        self._built_tab_indices: set[int] = set()
        self._styled_tabs: set[int] = set()
        self._background_build_scheduled = False
        self._background_tab_queue: list[int] = []
        self._background_hydration_started = False
        self._background_hydration_delay_ms = 1500
        self._background_hydration_step_delay_ms = 150
        self._closing = False
        self._backdrop_applied = False
        cache = get_settings_dialog_cache()
        stored_scroll = self._settings.get('ui.last_tab_scroll', {})
        if isinstance(stored_scroll, dict):
            for key, value in stored_scroll.items():
                try:
                    self._tab_scroll_cache[str(key)] = int(value)
                except (TypeError, ValueError):
                    pass
        self._suppress_scroll_capture: bool = False
        self._tab_keys = ["sources", "display", "transitions", "widgets", "accessibility", "themes", "about"]
        self._force_initial_sources_tab = os.getenv(
            "SRPSS_SETTINGS_FORCE_INITIAL_TAB_SOURCES", "0"
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._skip_widgets_hydration = os.getenv(
            "SRPSS_SETTINGS_SKIP_WIDGETS_HYDRATION", "0"
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._tab_state_cache: Dict[str, Dict[str, Any]] = {}
        self._tab_scroll_widgets: Dict[int, Optional[QScrollArea]] = {}
        self._tab_button_by_key: Dict[str, TabButton] = {}
        stored_states = self._settings.get('ui.tab_state', {})
        if isinstance(stored_states, dict):
            for key, value in stored_states.items():
                if isinstance(value, dict):
                    try:
                        self._tab_state_cache[str(key)] = dict(value)
                    except Exception:
                        logger.debug("Invalid stored tab state for %s", key)
        self._normal_geometry = None

        self._shadow_diagnostics_enabled = is_perf_metrics_enabled()

        shared_styles.ensure_custom_fonts()
        self._apply_application_font()

        self._setup_window()
        self._load_theme()
        self._determine_initial_tab()
        _ui_start = time.perf_counter()
        self._setup_ui()
        self._log_perf_event("SettingsDialog._setup_ui", _ui_start)
        self._apply_circle_checkbox_style()
        self._connect_signals()
        self._restore_geometry()
        self._restore_last_tab_selection()

        # Register only after the complete Settings hierarchy exists. Runtime
        # theme callbacks hold weak references and cannot extend dialog life.
        _LIVE_SETTINGS_DIALOGS.add(self)

        logger.info("Settings dialog created")

    def _log_perf_event(self, label: str, start_time: float) -> None:
        if not is_perf_metrics_enabled():
            return
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info("[PERF][SETTINGS] %s in %.1f ms", label, elapsed_ms)

    def _read_persisted_tab_index(self) -> int:
        """Resolve stable tab key first, then migrate the pre-Themes index."""
        stored_key = self._settings.get('ui.last_tab_key', None)
        if isinstance(stored_key, str) and stored_key in self._tab_keys:
            return self._tab_keys.index(stored_key)
        legacy_keys = ("sources", "display", "transitions", "widgets", "accessibility", "about")
        stored = self._settings.get('ui.last_tab_index', 0)
        try: legacy_index = int(stored)
        except Exception: legacy_index = 0
        if legacy_index < 0 or legacy_index >= len(legacy_keys): legacy_index = 0
        return self._tab_keys.index(legacy_keys[legacy_index])

    def _determine_initial_tab(self) -> None:
        index = self._read_persisted_tab_index()
        # Diagnostic toggle for U-04 isolation:
        # force a lightweight initial tab so we can compare startup behavior.
        if self._force_initial_sources_tab:
            index = 0
        if index < 0 or index >= len(self._tab_keys):
            index = 0
        self._initial_tab_index = index
    
    def _setup_window(self) -> None:
        """Setup window properties."""
        # Frameless dialog — Dialog type avoids creating a premature taskbar
        # entry during construction (Window type does), which prevents the
        # ghost-frame / taskbar flash on Windows.  All custom chrome (title
        # bar, resize grip, drag, acrylic) is independent of native flags.
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        
        # Enable transparency for drop shadow
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Prevent accidental early activation from producing ghost frames.
        # Cleared in showEvent so exec() can properly activate the window.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        
        # Minimum size tuned to the reference layout so that all tabs
        # (especially About/Widgets) render without clipping. The width
        # is intentionally generous so the About header artwork and
        # blurb/buttons fit side-by-side without crowding. The height is
        # slightly taller than the original 610px baseline so the About
        # card and hotkeys section have comfortable breathing room even
        # immediately after a Reset To Defaults.
        self.setMinimumSize(1280, 700)
        
        # Check if we have saved geometry first; if not, create the dialog at
        # the designed minimum size so layout matches the reference exactly.
        saved_geometry = self._settings.get('ui.dialog_geometry', {})
        
        if saved_geometry and 'width' in saved_geometry and 'height' in saved_geometry:
            # Use saved geometry (will be applied in _restore_geometry()).
            pass
        else:
            self.resize(self.minimumWidth(), self.minimumHeight())
            logger.debug(
                "No saved geometry - defaulting to minimum size: %sx%s",
                self.minimumWidth(),
                self.minimumHeight(),
            )
        
        # Improve text antialiasing (smoother rendering without changing fonts)
        font = self.font()
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        font.setStyleStrategy(
            QFont.StyleStrategy.PreferAntialias
            | QFont.StyleStrategy.PreferQuality
        )
        self.setFont(font)

    def _load_theme(self) -> None:
        """Delegates to ui.settings_theme."""
        from ui.settings_theme import load_theme
        load_theme(self)

    def _apply_native_backdrop_theme(
        self,
        theme: SettingsThemeSpec,
        *,
        record_diagnostics: bool = False,
    ) -> bool:
        """Apply one theme's native backdrop through the Windows adapter."""

        self._backdrop_applied = True
        try:
            if record_diagnostics:
                _record_diagnostic_stage("settings_show_event_before_winid")
            hwnd = int(self.winId())
            backdrop = theme.backdrop
            if record_diagnostics:
                _record_diagnostic_stage(
                    "settings_show_event_before_backdrop",
                    hwnd=hwnd,
                    mode=backdrop.mode,
                )

            tint = backdrop.tint
            if backdrop.mode == "acrylic":
                from core.windows.dwm_blur import enable_acrylic_blur

                native_enabled = enable_acrylic_blur(
                    hwnd,
                    tint_r=tint.r,
                    tint_g=tint.g,
                    tint_b=tint.b,
                    tint_alpha=tint.a,
                )
            elif backdrop.mode == "glass":
                from core.windows.dwm_blur import enable_glass_blur

                native_enabled = enable_glass_blur(
                    hwnd,
                    tint_r=tint.r,
                    tint_g=tint.g,
                    tint_b=tint.b,
                    tint_alpha=tint.a,
                )
            elif backdrop.mode == "off":
                from core.windows.dwm_blur import disable_blur

                disable_blur(hwnd)
                native_enabled = False
            else:
                raise ValueError(
                    f"Unsupported Settings native backdrop mode: {backdrop.mode!r}"
                )

            if record_diagnostics:
                _record_diagnostic_stage(
                    "settings_show_event_after_backdrop",
                    mode=backdrop.mode,
                    enabled=native_enabled,
                )
            return bool(native_enabled)
        except Exception:
            logger.debug("Native Settings backdrop not available", exc_info=True)
            if record_diagnostics:
                _record_diagnostic_stage("settings_show_event_backdrop_exception")
            return False

    def _refresh_live_shell_theme(self, theme: SettingsThemeSpec) -> None:
        """Refresh shell-owned visuals on an already-built Settings dialog."""

        for button in getattr(self, "tab_buttons", ()):
            sync_content = getattr(button, "_sync_content_style", None)
            if callable(sync_content):
                sync_content()

        size_grip = getattr(self, "size_grip", None)
        if size_grip is not None:
            size_grip.update()

        # paintEvent consumes the live forged-edge globals installed above.
        self.update()

        # Hidden dialogs use the latest ThemeSpec when shown. Visible dialogs
        # update native acrylic immediately through the exact same DWM path.
        if self.isVisible():
            self._apply_native_backdrop_theme(theme)
        else:
            self._backdrop_applied = False

    def _setup_ui(self) -> None:
        """Setup dialog UI."""
        # Main container (for rounded corners and shadow)
        container = QWidget()
        container.setObjectName("dialogContainer")
        self._dialog_container = container
        
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Custom title bar
        self.title_bar = CustomTitleBar(self)
        # CustomTitleBar is also used by small popup dialogs and still carries
        # their legacy local title shadow. The main Settings title is centrally
        # shadow-managed, so remove that inherited effect before first paint.
        self.title_bar.title_label.setGraphicsEffect(None)

        # Establish the approved main-title geometry before the window can ever
        # paint.  Shadow discovery must not mutate typography/layout later.
        title_font = self.title_bar.title_label.font()
        title_font.setPointSizeF(19.0)
        self.title_bar.title_label.setFont(title_font)
        self.title_bar.setFixedHeight(52)

        # The content row puts the sidebar frame at +10px. The title QLabel
        # already owns 10px of left QSS padding, so remove only this main
        # title bar's extra 10px layout inset. Popup title bars are unaffected.
        title_layout = self.title_bar.layout()
        if title_layout is not None:
            margins = title_layout.contentsMargins()
            title_layout.setContentsMargins(
                0,
                margins.top(),
                margins.right(),
                margins.bottom(),
            )
        main_layout.addWidget(self.title_bar)
        
        # Content area
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(10, 10, 10, 9)
        content_layout.setSpacing(10)
        
        # Left sidebar with tabs
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(5)
        
        # Tab buttons
        self.sources_tab_btn = TabButton("Sources", "📁")
        self.display_tab_btn = TabButton("Display", "🖥")
        self.transitions_tab_btn = TabButton("Transitions", "✨")
        self.widgets_tab_btn = TabButton("Widgets", "🕐")
        # Accessibility icon: wheelchair symbol for universal accessibility
        self.accessibility_tab_btn = TabButton("Accessibility", "♿")
        self.themes_tab_btn = TabButton("Themes", "🎨")
        self.about_tab_btn = TabButton("About", "ℹ️")

        self._tab_button_by_key = {
            "sources": self.sources_tab_btn,
            "display": self.display_tab_btn,
            "transitions": self.transitions_tab_btn,
            "widgets": self.widgets_tab_btn,
            "accessibility": self.accessibility_tab_btn,
            "themes": self.themes_tab_btn,
            "about": self.about_tab_btn,
        }
        self.tab_buttons = [self._tab_button_by_key[key] for key in self._tab_keys]
        
        for btn in self.tab_buttons:
            sidebar_layout.addWidget(btn)
        sidebar_layout.addStretch()
        
        # Right content area with stacked widget
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentArea")
        
        # Create actual tabs lazily
        cache = get_settings_dialog_cache()
        self._tab_builders = {
            # Build tabs with the stacked-widget as parent immediately so
            # constructors never run as transient top-level windows.
            "sources": lambda: SourcesTab(self._settings, parent=self.content_stack),
            "display": lambda: DisplayTab(self._settings, parent=self.content_stack),
            "transitions": lambda: TransitionsTab(self._settings, parent=self.content_stack),
            "widgets": lambda: WidgetsTab(
                self._settings,
                parent=self.content_stack,
                widget_defaults=cache.widget_defaults,
                lazy_sections=True,
                initial_view_state=dict(
                    self._tab_state_cache.get("widgets", {}).get("view_state", {})
                ) if isinstance(self._tab_state_cache.get("widgets", {}).get("view_state", {}), dict) else None,
            ),
            "accessibility": lambda: AccessibilityTab(self._settings, parent=self.content_stack),
            "themes": lambda: ThemesTab(self._settings, parent=self.content_stack),
            "about": self._create_about_tab,
        }
        for key in self._tab_keys:
            placeholder = QWidget()
            placeholder.setObjectName(f"{key}_placeholder")
            self.content_stack.addWidget(placeholder)
            self._tab_widgets[key] = placeholder

        self._ensure_tab_built(self._initial_tab_index)
        self._hydrate_remaining_tabs_async()

        content_layout.addWidget(sidebar)
        content_layout.addWidget(self.content_stack, 1)

        main_layout.addLayout(content_layout)

        # Bottom margin placeholder (separator line painted in paintEvent)
        bottom_spacer = QWidget()
        bottom_spacer.setFixedHeight(9)
        main_layout.addWidget(bottom_spacer)

        # Size grip for resizing
        self.size_grip = CornerSizeGrip(container)
        self.size_grip.setFixedSize(20, 20)
        
        # Set main layout
        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.addWidget(container)
        
        self.tab_buttons[self._initial_tab_index].setChecked(True)
        self.content_stack.setCurrentIndex(self._initial_tab_index)

        # The initial tab was constructed before the finished dialog hierarchy
        # existed, so its tab-scoped pass cannot reliably reach shell siblings.
        # Apply the fully assembled existing tree synchronously now: title,
        # sidebar, nav content, scrollbars and current-tab controls are shadowed
        # before the first visible frame. Lazy children still use their normal
        # watcher when they are actually created later.
        apply_shadows_to_existing(self)



    def _create_about_tab(self) -> QWidget:
        """Create about tab. Delegates to ui.settings_about_tab."""
        from ui.settings_about_tab import build_about_tab
        return build_about_tab(self)

    def __getattr__(self, name: str):
        if name.endswith("_tab"):
            key = name[:-4]
            if key in getattr(self, "_tab_keys", []):
                tab = self._get_tab_instance(key)
                if key == "widgets" and tab is not None:
                    ensure_media = getattr(tab, "ensure_programmatic_media_sections_built", None)
                    if callable(ensure_media):
                        ensure_media()
                if tab is not None:
                    return tab
        raise AttributeError(f"{type(self).__name__!s} object has no attribute {name!r}")

    def _get_tab_instance(self, key: str) -> Optional[QWidget]:
        index = self._tab_index_for_key(key)
        if index < 0:
            return None
        self._ensure_tab_built(index)
        return getattr(self, f"{key}_tab", None)

    def _tab_index_for_key(self, key: str) -> int:
        try:
            return self._tab_keys.index(key)
        except ValueError:
            return -1

    def _ensure_tab_built(self, index: int) -> None:
        if index in self._built_tab_indices:
            return
        if index < 0 or index >= len(self._tab_keys):
            return
        key = self._tab_key_for_index(index)
        widget = self._build_tab_by_key(key, index)
        self._built_tab_indices.add(index)
        self._style_tab_widget(widget)

    def _build_tab_by_key(self, key: str, index: int) -> QWidget:
        builder = self._tab_builders.get(key)
        if builder is None:
            return self._tab_widgets.get(key)

        build_start = time.perf_counter()
        widget = builder()

        placeholder = self.content_stack.widget(index)
        if placeholder is not None:
            self.content_stack.removeWidget(placeholder)
            placeholder.deleteLater()
        self.content_stack.insertWidget(index, widget)
        self._register_tab_scroll_area(index, widget)
        setattr(self, f"{key}_tab", widget)

        # Disable opaque auto-fill on scroll area viewports so the acrylic
        # blur-behind can show through semi-transparent backgrounds.
        for scroll in widget.findChildren(QScrollArea):
            scroll.viewport().setAutoFillBackground(False)

        # Restore view state + scroll as soon as the tab exists so subsections pick up saved positions.
        self._restore_tab_view_state(index, widget)
        self._restore_scroll_for_tab(index, widget)

        if is_perf_metrics_enabled():
            elapsed_ms = (time.perf_counter() - build_start) * 1000.0
            logger.info(
                "[PERF][SETTINGS] Tab '%s' built in %.1f ms",
                key,
                elapsed_ms,
            )

        return widget

    def _hydrate_remaining_tabs_async(self) -> None:
        # Widgets is intentionally excluded from background hydration.
        # Its constructor is large enough that hidden/off-screen builds can
        # stall the visible shell and confuse persisted subtab/bucket state
        # restoration. Build it only when explicitly selected or restored
        # as the active top-level tab.
        remaining = [
            i
            for i in range(len(self._tab_keys))
            if i not in self._built_tab_indices
            and self._tab_key_for_index(i) != "widgets"
        ]
        if not remaining:
            return
        self._background_tab_queue.extend(remaining)
        if self.isVisible():
            self._start_background_tab_hydration()

    def _start_background_tab_hydration(self) -> None:
        if self._closing or self._background_hydration_started or not self._background_tab_queue:
            return
        self._background_hydration_started = True
        hydration_start = time.perf_counter()

        def _run():
            if self._closing:
                return
            self._log_perf_event("SettingsDialog.background_hydration_delay", hydration_start)
            self._schedule_next_background_build()

        self._schedule_runtime_single_shot(
            self._background_hydration_delay_ms,
            _run,
        )

    def _schedule_next_background_build(self) -> None:
        if self._closing or self._background_build_scheduled or not self._background_tab_queue:
            return
        self._background_build_scheduled = True

        def _run():
            self._background_build_scheduled = False
            if self._closing:
                self._background_tab_queue.clear()
                return
            if not self._background_tab_queue:
                return
            index = self._background_tab_queue.pop(0)
            self._ensure_tab_built(index)
            self._schedule_next_background_build()

        self._schedule_runtime_single_shot(
            self._background_hydration_step_delay_ms,
            _run,
        )

    def _schedule_runtime_single_shot(
        self,
        delay_ms: int,
        callback,
    ) -> None:
        """Track dialog-owned delayed work through the runtime scheduler."""

        # Python bound-method objects do not allow arbitrary attributes.  Wrap
        # every callback in a plain function so lifecycle ownership metadata is
        # attached consistently for both bound methods and local closures.
        def _run_callback():
            callback()

        _run_callback._srpss_timer_owner = self
        _run_callback._srpss_runtime_generation = self._runtime_generation
        ThreadManager.single_shot(delay_ms, _run_callback)

    def _style_tab_widget(self, widget: Optional[QWidget]) -> None:
        if widget is None:
            return
        idx = self.content_stack.indexOf(widget)
        if idx < 0 or idx in self._styled_tabs:
            return
        try:
            apply_shadows_to_inputs(widget)
        except Exception:
            logger.debug("Failed to apply tab control shadows", exc_info=True)
            return
        self._styled_tabs.add(idx)

    def _update_about_header_images(self) -> None:
        """Scale About header images responsively. Delegates to ui.settings_about_tab."""
        from ui.settings_about_tab import update_about_header_images
        update_about_header_images(self)
    
    def _connect_signals(self) -> None:
        """Connect signals to slots."""
        # Title bar
        self.title_bar.close_clicked.connect(self.close)
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self._toggle_maximize)
        
        # Tab buttons (indices match content_stack order)
        for key in self._tab_keys:
            btn = self._tab_button_by_key.get(key)
            if btn is None:
                continue
            index = self._tab_index_for_key(key)
            btn.clicked.connect(lambda _checked=False, idx=index: self._switch_tab(idx))
        

    def _switch_tab(self, index: int, animate: bool = True) -> None:
        """
        Switch to tab with animation.
        
        Args:
            index: Tab index
        """
        self._ensure_tab_built(index)
        previous_index = self.content_stack.currentIndex()
        if previous_index >= 0:
            if not self._suppress_scroll_capture:
                self._remember_scroll_for_tab(previous_index)
            self._capture_tab_view_state(previous_index)
        if index < 0 or index >= len(self.tab_buttons):
            return
        # Uncheck all buttons
        for btn in self.tab_buttons:
            btn.setChecked(False)
        
        # Check selected button
        self.tab_buttons[index].setChecked(True)
        
        # Get widgets
        old_widget = self.content_stack.currentWidget()
        def _after_switch():
            current_widget = self.content_stack.currentWidget()
            about_idx = self._tab_index_for_key("about")
            if index == about_idx:
                try:
                    self._about_last_card_width = 0
                except Exception:
                    logger.debug("[SETTINGS] Exception suppressed")
                try:
                    self._update_about_header_images()
                except Exception:
                    logger.debug("[SETTINGS] Exception suppressed")
            self._restore_tab_view_state(index, current_widget)
            self._restore_scroll_for_tab(index, current_widget)
            self._style_tab_widget(current_widget)
            self._save_last_tab(index)
            logger.debug(f"Switched to tab {index}")
        if animate and old_widget is not None:
            def fade_out_complete():
                self.content_stack.setCurrentIndex(index)
                # Fade in new widget
                new_widget = self.content_stack.currentWidget()
                self._animations.animate_property(
                    target=new_widget,
                    property_name='windowOpacity',
                    start_value=0.0,
                    end_value=1.0,
                    duration=0.15
                )
                self._animations.start()
                _after_switch()

            self._animations.animate_property(
                target=old_widget,
                property_name='windowOpacity',
                start_value=1.0,
                end_value=0.0,
                duration=0.15,
                on_complete=fade_out_complete
            )
            self._animations.start()
        else:
            self.content_stack.setCurrentIndex(index)
            _after_switch()

    def _apply_application_font(self) -> None:
        font = QFont("Jost", 11)
        font.setFamilies(["Jost", "Segoe UI", "Arial", "Sans Serif"])
        font.setWeight(QFont.Weight.Normal)
        QGuiApplication.setFont(font)

    def _apply_tab_button_font(self) -> None:
        font = QFont("Jost", 10)
        font.setFamilies(["Jost", "Segoe UI", "Arial", "Sans Serif"])
        font.setWeight(QFont.Weight.DemiBold)
        for button in self.tab_buttons:
            button.setFont(font)

    def _apply_circle_checkbox_style(self) -> None:
        try:
            self.setStyleSheet(self.styleSheet() + shared_styles.CIRCLE_CHECKBOX_STYLE)
        except Exception:
            logger.debug("Failed to append circle checkbox stylesheet", exc_info=True)

    def _register_tab_scroll_area(self, index: int, tab_widget: QWidget) -> None:
        """Associate a scroll area with a tab for persistence."""
        if index < 0:
            return
        scroll: Optional[QScrollArea]
        if isinstance(tab_widget, QScrollArea):
            scroll = tab_widget
        else:
            scroll = tab_widget.findChild(QScrollArea)
        self._tab_scroll_widgets[index] = scroll

    def _capture_tab_view_state(self, index: int) -> None:
        if index < 0:
            return
        widget = self.content_stack.widget(index)
        if widget is None:
            return
        getter = getattr(widget, "get_view_state", None)
        if not callable(getter):
            return
        try:
            view_state = getter()
        except Exception:
            logger.debug("Failed to capture view state for tab %s", index, exc_info=True)
            return
        key = self._tab_key_for_index(index)
        if view_state in (None, {}):
            entry = dict(self._tab_state_cache.get(key, {}))
            if 'view_state' in entry:
                entry.pop('view_state')
            if entry:
                self._tab_state_cache[key] = entry
            elif key in self._tab_state_cache:
                self._tab_state_cache.pop(key, None)
            self._save_tab_state_cache()
            return
        entry = dict(self._tab_state_cache.get(key, {}))
        entry['view_state'] = view_state
        self._tab_state_cache[key] = entry
        self._save_tab_state_cache()

    def _restore_tab_view_state(self, index: int, widget: Optional[QWidget]) -> None:
        if widget is None or index < 0:
            return
        key = self._tab_key_for_index(index)
        entry = self._tab_state_cache.get(key, {})
        view_state = entry.get('view_state')
        if not view_state:
            return
        restorer = getattr(widget, "restore_view_state", None)
        if not callable(restorer):
            return
        try:
            restorer(view_state)
        except Exception:
            logger.debug("Failed to restore tab view state for tab %s", key, exc_info=True)

    def _save_tab_state_cache(self) -> None:
        try:
            self._settings.set('ui.tab_state', dict(self._tab_state_cache))
            self._settings.save()
        except Exception:
            logger.debug("Failed to persist tab state cache", exc_info=True)

    def _tab_key_for_index(self, index: int) -> str:
        if 0 <= index < len(self._tab_keys):
            return self._tab_keys[index]
        return f"tab_{index}"

    def _remember_scroll_for_tab(self, index: int) -> None:
        scroll = self._tab_scroll_widgets.get(index)
        if scroll is None:
            return
        try:
            value = scroll.verticalScrollBar().value()
        except Exception:
            logger.debug("[SETTINGS] Exception suppressed")
            return
        key = self._tab_key_for_index(index)
        self._tab_scroll_cache[key] = value
        try:
            self._settings.set('ui.last_tab_scroll', dict(self._tab_scroll_cache))
            self._settings.save()
        except Exception:
            logger.debug("Failed to persist tab scroll positions", exc_info=True)

    def _restore_scroll_for_tab(self, index: int, widget: Optional[QWidget]) -> None:
        if index < 0:
            return
        if self._tab_scroll_widgets.get(index) is None and widget is not None:
            self._register_tab_scroll_area(index, widget)
        scroll = self._tab_scroll_widgets.get(index)
        if scroll is None:
            return
        key = self._tab_key_for_index(index)
        value = self._tab_scroll_cache.get(key, 0)
        if value <= 0:
            return
        scrollbar = scroll.verticalScrollBar()

        def _apply_scroll() -> None:
            try:
                self._suppress_scroll_capture = True
                scrollbar.setValue(value)
            except Exception:
                logger.debug("Failed to restore scroll for tab %s", key, exc_info=True)
            finally:
                self._suppress_scroll_capture = False

        self._schedule_runtime_single_shot(0, _apply_scroll)

    def _save_last_tab(self, index: int) -> None:
        if index < 0 or index >= len(self._tab_keys):
            return
        try:
            self._settings.set('ui.last_tab_key', self._tab_keys[index])
            self._settings.set('ui.last_tab_index', int(index))
            self._settings.save()
        except Exception:
            logger.debug("Failed to persist last Settings tab", exc_info=True)

    def _restore_last_tab_selection(self) -> None:
        if self._force_initial_sources_tab:
            return
        index = self._read_persisted_tab_index()
        if index < 0 or index >= len(self.tab_buttons):
            index = 0
        self._suppress_scroll_capture = True
        try:
            self._switch_tab(index, animate=False)
        finally:
            self._suppress_scroll_capture = False

    def closeEvent(self, event):
        self._closing = True
        self._background_tab_queue.clear()
        self._background_build_scheduled = False
        # Check if user has configured any image sources
        if not self._has_image_sources():
            if not self.isVisible():
                event.accept()
                return
            self._closing = False
            event.ignore()
            self._show_no_sources_popup()
            return
        
        try:
            current_index = self.content_stack.currentIndex()
            if current_index >= 0:
                self._capture_tab_view_state(current_index)
                if not self._suppress_scroll_capture:
                    self._remember_scroll_for_tab(current_index)
        except Exception:
            logger.debug("Failed to capture tab state on close", exc_info=True)
        
        # Save window geometry for next session
        try:
            self._save_geometry()
        except Exception:
            logger.debug("Failed to save dialog geometry on close", exc_info=True)

        # Settings completion is an explicit durability boundary.  Routine
        # control changes only enqueue persistence; one bounded close flush
        # prevents the standalone config process or a runtime rebuild from
        # observing an acknowledged Settings session that never reached disk.
        try:
            flush = getattr(self._settings, "flush", None)
            if callable(flush) and not flush(timeout=2.0):
                logger.warning(
                    "[SETTINGS_PERSIST] Settings close durability flush timed out"
                )
        except Exception:
            logger.exception("[SETTINGS_PERSIST] Settings close flush failed")
        
        # Disable native backdrop
        try:
            from core.windows.dwm_blur import disable_blur
            disable_blur(int(self.winId()))
        except Exception:
            pass
        super().closeEvent(event)

    def _schedule_shell_shadow_refresh(self) -> None:
        return

    def _refresh_shell_shadow_cache(self) -> None:
        return
    
    def _has_image_sources(self) -> bool:
        """Check if user has configured at least one image source (folder or RSS feed)."""
        try:
            folders = self._settings.get('sources.folders', [])
            rss_feeds = self._settings.get('sources.rss_feeds', [])
            return bool(folders) or bool(rss_feeds)
        except Exception:
            logger.debug("[SETTINGS] Exception suppressed")
            return False
    
    def _show_no_sources_popup(self) -> None:
        """Use the central themed popup when no image source is configured."""
        popup = StyledPopup(
            self,
            "No Image Sources",
            "You haven't configured any image sources!<br><br>"
            "The screensaver needs at least one folder or RSS feed to display "
            "images.<br><br>What would you like to do?",
            icon_type="warning",
            buttons=[
                ("Just Make It Work", "defaults"),
                ("Ehhhh", "exit"),
            ],
            default_button_index=0,
        )
        popup.exec()
        if popup.result_value == "defaults":
            self._on_add_default_sources()
        elif popup.result_value == "exit":
            self._on_exit_without_sources()
    
    def _reload_all_tab_settings(self) -> None:
        """Reload settings in all tabs after preset change."""
        tab_attrs = [
            (0, "sources_tab"),
            (1, "display_tab"),
            (2, "transitions_tab"),
            (3, "widgets_tab"),
            (4, "accessibility_tab"),
        ]

        for idx, attr in tab_attrs:
            tab = getattr(self, attr, None)
            if tab is None:
                continue
            if hasattr(tab, 'load_from_settings'):
                try:
                    tab.load_from_settings()
                except Exception as e:
                    logger.debug("[SETTINGS] Failed to reload tab %d: %s", idx, e)
            elif hasattr(tab, 'refresh'):
                try:
                    tab.refresh()
                except Exception as e:
                    logger.debug("[SETTINGS] Failed to refresh tab %d: %s", idx, e)

        logger.debug("[SETTINGS] Reloaded tab settings after preset change")
    
    def _on_add_default_sources(self) -> None:
        """Add curated RSS feeds as default sources."""
        try:
            # Use the same curated feed contract as the Sources tab.
            from sources.rss.constants import DEFAULT_RSS_FEEDS
            curated_feeds = list(DEFAULT_RSS_FEEDS.values())
            
            self._settings.set('sources.rss_feeds', curated_feeds)
            self._settings.save()
            
            # Reload sources tab if it exists
            tab = self._get_tab_instance('sources')
            if tab and hasattr(tab, '_load_settings'):
                tab._load_settings()
            
            logger.info("Added %d curated RSS feeds as default sources", len(curated_feeds))
            
            # Now close the dialog
            self.close()
        except Exception:
            logger.exception("Failed to add default sources")
    
    def _on_exit_without_sources(self) -> None:
        """User chose to exit the application without sources."""
        logger.info("User chose to exit without configuring sources")
        sys.exit(0)

    def _on_reset_to_defaults_clicked(self) -> None:
        """Reset all application settings back to defaults and show a styled notice."""
        try:
            self._settings.reset_to_defaults()

            # Reload all tabs so the UI reflects the new canonical defaults
            # immediately, avoiding a confusing mismatch between on-disk
            # configuration and visible controls.
            try:
                for key in ("sources", "display", "transitions", "widgets"):
                    tab = self._get_tab_instance(key)
                    if tab and hasattr(tab, '_load_settings'):
                        tab._load_settings()
            except Exception:
                logger.debug("Failed to reload settings tabs after reset_to_defaults", exc_info=True)

            try:
                notice = getattr(self, "reset_notice_label", None)
                if notice is not None:
                    notice.setText("Settings reverted to defaults!")
                    notice.setVisible(True)

                    def _hide_notice() -> None:
                        notice.setVisible(False)

                    self._schedule_runtime_single_shot(2000, _hide_notice)
            except Exception:
                logger.debug("Failed to show reset notice label", exc_info=True)
        except Exception as exc:
            logger.exception("Failed to reset settings to defaults: %s", exc)
            StyledPopup.show_error(
                self,
                "Error",
                "Failed to reset settings to defaults.\nSee log for details.",
            )

    def _on_export_visualizers_clicked(self) -> None:
        """Export the active curated visualizer presets to a zip archive."""
        try:
            try:
                base_dir = Path.home() / "Documents"
            except Exception as e:
                logger.debug("[SETTINGS] Exception suppressed: %s", e)
                base_dir = Path.cwd()
            if not base_dir.exists():
                base_dir = Path.cwd()

            default_path = str(base_dir / "SRPSS_Visualizer_Presets.zip")
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Visualizer Presets",
                default_path,
                "Visualizer Preset Archive (*.zip);;All Files (*)",
            )
            if not file_path:
                return

            path = Path(file_path)
            if path.suffix.lower() != ".zip":
                path = path.with_suffix(".zip")

            result = export_visualizer_presets_zip(path)
            StyledPopup.show_success(
                self,
                "Export Complete",
                f"Exported {result.files} visualizer preset file(s) to:\n{path.name}",
            )
        except Exception as exc:
            logger.exception("Failed to export visualizer presets: %s", exc)
            StyledPopup.show_error(
                self,
                "Export Failed",
                "Failed to export visualizer presets.\nSee log for details.",
            )

    def _show_import_visualizers_menu(self) -> None:
        """Show visualizer import choices for archives/files or whole folders."""
        menu = QMenu(self)
        menu.setStyleSheet(self._more_options_menu_stylesheet())

        files_action = menu.addAction("Import Zip Or JSON Files...")
        files_action.triggered.connect(self._on_import_visualizer_files_clicked)

        folder_action = menu.addAction("Import Presets Folder...")
        folder_action.triggered.connect(self._on_import_visualizer_folder_clicked)

        btn = self.import_visualizers_btn
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _on_import_visualizer_files_clicked(self) -> None:
        """Import a visualizer preset zip archive or loose JSON preset files."""
        try:
            try:
                base_dir = Path.home() / "Documents"
            except Exception as e:
                logger.debug("[SETTINGS] Exception suppressed: %s", e)
                base_dir = Path.cwd()
            if not base_dir.exists():
                base_dir = Path.cwd()

            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Import Visualizer Presets",
                str(base_dir),
                "Visualizer Presets (*.zip *.json);;All Files (*)",
            )
            if not file_paths:
                return

            paths = [Path(p) for p in file_paths]
            zip_paths = [p for p in paths if p.suffix.lower() == ".zip"]
            json_paths = [p for p in paths if p.suffix.lower() == ".json"]

            if len(zip_paths) == 1 and len(paths) == 1:
                result = import_visualizer_presets_archive(zip_paths[0])
            elif json_paths and len(json_paths) == len(paths):
                result = import_visualizer_preset_json_files(json_paths)
            else:
                StyledPopup.show_error(
                    self,
                    "Import Failed",
                    "Select one .zip archive or one or more .json preset files.",
                )
                return

            self._refresh_visualizer_import_state()
            StyledPopup.show_success(
                self,
                "Import Complete",
                f"Imported {result.files} visualizer preset file(s).",
            )
        except Exception as exc:
            logger.exception("Failed to import visualizer presets: %s", exc)
            StyledPopup.show_error(
                self,
                "Import Failed",
                "Failed to import visualizer presets.\nSee log for details.",
            )

    def _on_import_visualizer_folder_clicked(self) -> None:
        """Import a whole visualizer preset folder as the active curated tree."""
        try:
            try:
                base_dir = Path.home() / "Documents"
            except Exception as e:
                logger.debug("[SETTINGS] Exception suppressed: %s", e)
                base_dir = Path.cwd()
            if not base_dir.exists():
                base_dir = Path.cwd()

            folder_path = QFileDialog.getExistingDirectory(
                self,
                "Import Visualizer Presets Folder",
                str(base_dir),
            )
            if not folder_path:
                return

            result = import_visualizer_presets_folder(folder_path)
            self._refresh_visualizer_import_state()
            StyledPopup.show_success(
                self,
                "Import Complete",
                f"Imported {result.files} visualizer preset file(s).",
            )
        except Exception as exc:
            logger.exception("Failed to import visualizer preset folder: %s", exc)
            StyledPopup.show_error(
                self,
                "Import Failed",
                "Failed to import the visualizer preset folder.\nSee log for details.",
            )

    def _refresh_visualizer_import_state(self) -> None:
        try:
            tab = self._get_tab_instance('widgets')
            if tab and hasattr(tab, '_load_settings'):
                tab._load_settings()
        except Exception:
            logger.debug("Failed to reload widgets tab after visualizer import", exc_info=True)

        try:
            notice = getattr(self, "reset_notice_label", None)
            if notice is not None:
                notice.setText("Visualizer presets imported!")
                notice.setVisible(True)

                def _hide_notice() -> None:
                    notice.setVisible(False)

                self._schedule_runtime_single_shot(2000, _hide_notice)
        except Exception:
            logger.debug("Failed to show visualizer import notice label", exc_info=True)
    
    def _show_more_options_menu(self) -> None:
        """Show the more options context menu."""
        menu = QMenu(self)
        menu.setStyleSheet(self._more_options_menu_stylesheet())
        
        # Open logs folder
        logs_action = menu.addAction("Open Logs Folder")
        logs_action.triggered.connect(self._open_logs_folder)
        
        # Open settings folder
        settings_action = menu.addAction("Open Settings Folder")
        settings_action.triggered.connect(self._open_settings_folder)
        
        menu.addSeparator()
        
        # GitHub link
        github_action = menu.addAction("GitHub Repository")
        github_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/Basjohn/ShittyRandomPhotoScreenSaver")))
        
        # Show menu below the button
        btn = self.more_options_btn
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    @staticmethod
    def _more_options_menu_stylesheet() -> str:
        """Use the same semantic context-menu palette as app menus."""
        def rgba(token: str) -> str:
            value = _SETTINGS_THEME.color(token)
            return f"rgba({value.r}, {value.g}, {value.b}, {value.a})"

        return f"""
            QMenu {{
                background-color: {rgba('context.menu.surface')};
                border: 1px solid {rgba('context.menu.border')};
                border-radius: 6px;
                padding: 4px 2px;
            }}
            QMenu::item {{
                background-color: transparent;
                color: {rgba('context.menu.text')};
                padding: 6px 16px;
                margin: 1px 3px;
                border-radius: 3px;
                font-size: 11px;
            }}
            QMenu::item:selected {{
                background-color: {rgba('context.menu.selected_surface')};
            }}
            QMenu::item:disabled {{
                color: {rgba('context.menu.disabled_text')};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {rgba('context.menu.separator')};
                margin: 3px 8px;
            }}
        """
    
    def _open_logs_folder(self) -> None:
        """Open the logs folder in file explorer."""
        try:
            logs_path = get_log_dir()
            if not logs_path.exists():
                logs_path.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs_path)))
        except Exception:
            logger.debug("Failed to open logs folder", exc_info=True)
    
    def _open_settings_folder(self) -> None:
        """Open the settings folder in file explorer."""
        try:
            settings_path = self._settings.get_settings_dir()
            if not settings_path.exists():
                settings_path.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(settings_path)))
        except Exception:
            logger.debug("Failed to open settings folder", exc_info=True)

    def _on_export_settings_clicked(self) -> None:
        """Export the current settings profile to an SST snapshot file."""

        try:
            # Prefer the user's Documents folder as a sensible default
            # location for human-edited snapshots; fall back to CWD.
            try:
                base_dir = Path.home() / "Documents"
            except Exception as e:
                logger.debug("[SETTINGS] Exception suppressed: %s", e)
                base_dir = Path.cwd()

            if not base_dir.exists():
                base_dir = Path.cwd()

            profile = "Screensaver"
            try:
                if hasattr(self._settings, "get_application_name"):
                    profile = self._settings.get_application_name()
            except Exception as e:
                logger.debug("[SETTINGS] Exception suppressed: %s", e)
                profile = "Screensaver"
            safe_profile = str(profile).replace(" ", "_") if profile is not None else "Screensaver"
            default_path = str(base_dir / f"SRPSS_Settings_{safe_profile}.sst")
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Settings Snapshot",
                default_path,
                "Settings Snapshot (*.sst *.json);;All Files (*)",
            )

            if not file_path:
                return

            ok = False
            try:
                ok = bool(self._settings.export_to_sst(file_path))
            except Exception:
                logger.exception("Export to SST failed")
                ok = False

            if not ok:
                StyledPopup.show_error(
                    self,
                    "Export Failed",
                    "Failed to export settings snapshot.\nSee log for details.",
                )
            else:
                StyledPopup.show_success(
                    self,
                    "Export Complete",
                    f"Settings exported to:\n{Path(file_path).name}",
                )
        except Exception as exc:
            logger.exception("Unexpected error during settings export: %s", exc)
            StyledPopup.show_error(
                self,
                "Export Failed",
                "Failed to export settings snapshot.\nSee log for details.",
            )

    def _on_import_settings_clicked(self) -> None:
        """Import settings from an SST snapshot and refresh all tabs."""

        try:
            try:
                base_dir = Path.home() / "Documents"
            except Exception as e:
                logger.debug("[SETTINGS] Exception suppressed: %s", e)
                base_dir = Path.cwd()

            if not base_dir.exists():
                base_dir = Path.cwd()

            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Import Settings Snapshot",
                str(base_dir),
                "Settings Snapshot (*.sst *.json);;All Files (*)",
            )

            if not file_path:
                return

            ok = False
            try:
                ok = bool(self._settings.import_from_sst(file_path, merge=True))
            except Exception:
                logger.exception("Import from SST failed")
                ok = False

            if not ok:
                StyledPopup.show_error(
                    self,
                    "Import Failed",
                    "Failed to import settings snapshot.\nSee log for details.",
                )
                return

            # Reload all tabs so the UI reflects the imported configuration
            # immediately.
            try:
                self._reload_all_tab_settings()
            except Exception:
                logger.debug("Failed to reload settings tabs after SST import", exc_info=True)

            StyledPopup.show_success(
                self,
                "Import Complete",
                f"Settings imported from:\n{Path(file_path).name}",
            )
        except Exception as exc:
            logger.exception("Unexpected error during settings import: %s", exc)
            StyledPopup.show_error(
                self,
                "Import Failed",
                "Failed to import settings snapshot.\nSee log for details.",
            )
    
    def _toggle_maximize(self) -> None:
        """Toggle window maximize state manually."""
        if self._is_maximized:
            self._restore_from_maximize()
        else:
            self._apply_maximized_geometry()

    def _screen_available_rect(self) -> QRect:
        screen = QGuiApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return screen.geometry() if screen is not None else self.geometry()

    def _apply_maximized_geometry(self) -> None:
        self._normal_geometry = self.geometry()
        self._is_maximized = True
        available = self._screen_available_rect()
        # Reduce by a pixel to avoid overlapping taskbar bounds on some DPIs
        available.adjust(0, 0, -1, -1)
        self.setGeometry(available)
        self._update_shell_chrome()

    def _restore_from_maximize(self) -> None:
        target = self._normal_geometry
        self._is_maximized = False
        if target is not None:
            self.setGeometry(target)
        self._normal_geometry = self.geometry()
        self._update_shell_chrome()

    def _update_shell_chrome(self) -> None:
        """Adjust layout margins and shadow visibility for current state."""
        if hasattr(self, "_outer_layout"):
            self._outer_layout.setContentsMargins(0, 0, 0, 0)
        if hasattr(self, "size_grip"):
            self.size_grip.setVisible(not self._is_maximized)
    
    def resizeEvent(self, event):
        """Handle resize event to position size grip and save geometry."""
        super().resizeEvent(event)


        # Position size grip in bottom-right corner
        if hasattr(self, 'size_grip'):
            try:
                parent = self.size_grip.parent() or self
                pw = parent.width()
                ph = parent.height()
                grip_inset = 0 if self._is_maximized else int((SETTINGS_OUTER_BORDER_BACKING_WIDTH * 0.5) + 1)
                self.size_grip.move(
                    pw - self.size_grip.width() - grip_inset,
                    ph - self.size_grip.height() - grip_inset,
                )
            except Exception as e:
                logger.debug("[SETTINGS] Exception suppressed: %s", e)
        
        # Save geometry on resize (debounced to avoid excessive saves)
        if hasattr(self, '_resize_timer'):
            self._resize_timer.stop()
        else:
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._save_geometry)
            try:
                from core.resources.manager import ResourceManager
                from core.resources.types import ResourceType
                ResourceManager.get_or_create_app_shared().register_qt(
                    self._resize_timer,
                    resource_type=ResourceType.TIMER,
                    description="Settings dialog resize debounce timer",
                    group="qt",
                )
            except Exception:
                pass
        self._resize_timer.start(500)  # Save 500ms after resize stops
        
        # Keep About header images scaled appropriately for the current
        # dialog width, but guard in case the About tab has not been
        # constructed yet.
        try:
            self._update_about_header_images()
        except Exception as e:
            logger.debug("[SETTINGS] Exception suppressed: %s", e)
    
    def showEvent(self, event):
        show_start = time.perf_counter()
        _record_diagnostic_stage("settings_show_event_begin")
        super().showEvent(event)
        _record_diagnostic_stage("settings_show_event_after_super")
        # Clear the construction-time activation guard so the window can
        # receive focus normally now that it has visible content.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        _record_diagnostic_stage("settings_show_event_activation_enabled")
        self._start_background_tab_hydration()
        # Apply the theme-requested Windows native backdrop on first show.
        # Enabled themes pass their exact tint/strength into the existing DWM
        # renderer; disabled themes use the real disable path rather than an
        # explicit backdrop mode rather than an alpha-zero Acrylic workaround.
        if not self._backdrop_applied:
            blur_start = time.perf_counter()
            self._apply_native_backdrop_theme(
                _SETTINGS_THEME,
                record_diagnostics=True,
            )
            self._log_perf_event("SettingsDialog.showEvent.blur", blur_start)
        # Reset cached width so images rescale on every show
        try:
            self._about_last_card_width = 0
        except Exception:
            pass
        # Defer image scaling until after Qt processes layout geometry
        try:
            self._schedule_runtime_single_shot(
                0,
                self._update_about_header_images,
            )
        except Exception as e:
            logger.debug("[SETTINGS] Exception suppressed: %s", e)
        self._log_perf_event("SettingsDialog.showEvent.total", show_start)
        _record_diagnostic_stage("settings_show_event_complete")
    
    def moveEvent(self, event):
        """Handle move event to save geometry."""
        super().moveEvent(event)
        # Save geometry on move (debounced to avoid excessive saves)
        if hasattr(self, '_move_timer'):
            self._move_timer.stop()
        else:
            self._move_timer = QTimer(self)
            self._move_timer.setSingleShot(True)
            self._move_timer.timeout.connect(self._save_geometry)
            try:
                from core.resources.manager import ResourceManager
                from core.resources.types import ResourceType
                ResourceManager.get_or_create_app_shared().register_qt(
                    self._move_timer,
                    resource_type=ResourceType.TIMER,
                    description="Settings dialog move debounce timer",
                    group="qt",
                )
            except Exception:
                pass
        self._move_timer.start(500)  # Save 500ms after move stops
    
    def paintEvent(self, event):
        """Paint a white border at the dialog edge."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        outer_rect = QRectF(self.rect())
        border_rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if not self._is_maximized:
            self._paint_outer_corner_caps(painter, outer_rect, border_rect)
            backing_pen = QPen(
                SETTINGS_OUTER_BORDER_BACKING_COLOR,
                SETTINGS_OUTER_BORDER_BACKING_WIDTH,
            )
            backing_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(backing_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                border_rect,
                SETTINGS_OUTER_CORNER_RADIUS,
                SETTINGS_OUTER_CORNER_RADIUS,
            )

        border_pen = QPen(SETTINGS_OUTER_BORDER_COLOR, SETTINGS_OUTER_BORDER_WIDTH)
        border_pen.setJoinStyle(
            Qt.PenJoinStyle.MiterJoin if self._is_maximized else Qt.PenJoinStyle.RoundJoin
        )
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self._is_maximized:
            painter.drawRect(border_rect)
        else:
            painter.drawRoundedRect(
                border_rect,
                SETTINGS_OUTER_CORNER_RADIUS,
                SETTINGS_OUTER_CORNER_RADIUS,
            )

        painter.end()

    def _paint_outer_corner_caps(
        self,
        painter: QPainter,
        outer_rect: QRectF,
        border_rect: QRectF,
    ) -> None:
        """Forge rounded corner fills without altering the real acrylic window edge."""
        dpr = max(1.0, float(self.devicePixelRatioF()))
        cover_overlap = max(
            1.75,
            ((SETTINGS_OUTER_BORDER_BACKING_WIDTH - SETTINGS_OUTER_BORDER_WIDTH) * 0.5)
            + (1.25 / dpr),
        )
        cover_radius = (
            SETTINGS_OUTER_CORNER_RADIUS
            + (SETTINGS_OUTER_BORDER_BACKING_WIDTH * 0.25)
            + cover_overlap
        )
        outer_path = QPainterPath()
        outer_path.addRect(outer_rect)
        rounded_path = QPainterPath()
        rounded_path.addRoundedRect(
            border_rect.adjusted(
                -cover_overlap,
                -cover_overlap,
                cover_overlap,
                cover_overlap,
            ),
            cover_radius,
            cover_radius,
        )
        cover_path = outer_path.subtracted(rounded_path)

        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(SETTINGS_CORNER_COVER_COLOR)
        painter.drawPath(cover_path)
        painter.restore()

    def keyPressEvent(self, event):
        """Intercept Enter/Return so it closes the dialog instead of minimizing."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.close()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press for window dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Don't interfere with size grip
            size_grip_rect = self.size_grip.geometry() if hasattr(self, 'size_grip') else None
            if size_grip_rect and size_grip_rect.contains(event.pos()):
                super().mousePressEvent(event)
                return
            
            if self._is_maximized:
                cursor_ratio = 0.5
                if self.width() > 0:
                    cursor_ratio = max(0.05, min(0.95, event.position().x() / self.width()))
                self._restore_from_maximize()
                # Position window so cursor stays over same relative spot
                new_x = int(event.globalPosition().x() - self.width() * cursor_ratio)
                new_y = int(event.globalPosition().y() - self.title_bar.height() // 2)
                self.move(new_x, new_y)
                self._normal_geometry = self.geometry()
            
            # Otherwise, dragging
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for window dragging."""
        if self._dragging and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release to stop dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._dragging
            self._dragging = False
            event.accept()
            if was_dragging and not self._is_maximized:
                screen = QGuiApplication.screenAt(event.globalPosition().toPoint())
                if screen is None:
                    screen = QGuiApplication.primaryScreen()
                if screen is not None:
                    top_threshold = screen.availableGeometry().top() + 5
                    if event.globalPosition().toPoint().y() <= top_threshold:
                        self._apply_maximized_geometry()
    
    def _save_geometry(self):
        """Save window geometry to settings."""
        if not self._is_maximized:
            self._settings.set('ui.dialog_geometry', {
                'x': self.x(),
                'y': self.y(),
                'width': self.width(),
                'height': self.height()
            })
            self._settings.save()
    
    def _restore_geometry(self):
        """Restore window geometry from settings."""
        geometry = self._settings.get('ui.dialog_geometry', {})
        if geometry:
            x_saved = int(geometry.get('x', 100))
            y_saved = int(geometry.get('y', 100))
            w_saved = int(geometry.get('width', 1000))
            h_saved = int(geometry.get('height', 700))

            # Find which screen the saved position belongs to
            target_screen = QGuiApplication.screenAt(QPoint(x_saved, y_saved))
            
            # Fallback to primary if off-screen or monitor unplugged
            if target_screen is None:
                target_screen = QGuiApplication.primaryScreen()

            if target_screen is not None:
                available = target_screen.availableGeometry()

                # Clamp size to available screen area (minus taskbars)
                width = max(self.minimumWidth(), min(w_saved, available.width()))
                height = max(self.minimumHeight(), min(h_saved, available.height()))

                # Clamp position to be within the target screen
                # Ensure x is within [left, right - width]
                x = max(available.left(), min(x_saved, available.right() - width))
                # Ensure y is within [top, bottom - height]
                y = max(available.top(), min(y_saved, available.bottom() - height))

                self.resize(width, height)
                self.move(x, y)
                logger.debug(
                    "Restored dialog geometry: x=%s, y=%s, w=%s, h=%s (Screen: %s)",
                    x, y, width, height, target_screen.name()
                )
            else:
                # Last resort fallback
                self.move(x_saved, y_saved)
                self.resize(w_saved, h_saved)
                logger.debug("Restored dialog geometry (no screen info): %s", geometry)

def _refresh_live_settings_dialogs(theme: SettingsThemeSpec) -> None:
    """Refresh all live Settings shells after the active ThemeSpec changes."""

    _install_settings_dialog_theme(theme)
    for dialog in tuple(_LIVE_SETTINGS_DIALOGS):
        try:
            dialog._refresh_live_shell_theme(theme)
        except RuntimeError:
            # Qt can delete the C++ object just before its Python weakref clears.
            continue


# settings_theme.py owns root QSS; control_shadow.py owns shadow refreshes.
_THEME_UNSUBSCRIBE = subscribe_settings_theme(_refresh_live_settings_dialogs)

