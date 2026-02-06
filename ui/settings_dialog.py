"""
Settings Dialog for screensaver configuration.

Features gorgeous UI with:
- Custom title bar (no native window border)
- Drop shadow effect
- Resizable window
"""
from typing import Dict, Optional, Any
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
    QLabel, QStackedWidget, QGraphicsDropShadowEffect, QSizeGrip,
    QFileDialog, QMenu, QScrollArea,
)
from PySide6.QtCore import Qt, QPoint, Signal, QUrl, QTimer
from PySide6.QtGui import QFont, QColor, QDesktopServices, QPainter, QPen, QGuiApplication

from core.logging.logger import get_logger
from core.settings.settings_manager import SettingsManager
from core.animation import AnimationManager
from ui.tabs import SourcesTab, TransitionsTab, WidgetsTab, DisplayTab, AccessibilityTab, PresetsTab
from ui.styled_popup import StyledPopup

logger = get_logger(__name__)


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
        title_font = QFont("Segoe UI", 11, QFont.Weight.Bold)
        self.title_label.setFont(title_font)
        # Subtle drop shadow so the title reads crisply against bright
        # backgrounds without overwhelming the frame shadow.
        title_shadow = QGraphicsDropShadowEffect(self)
        title_shadow.setBlurRadius(8)
        title_shadow.setOffset(0, 1)
        title_shadow.setColor(QColor(0, 0, 0, 140))
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


class TabButton(QPushButton):
    """Custom tab button with icon and text."""
    
    def __init__(self, text: str, icon_text: str = "", parent: Optional[QWidget] = None):
        """
        Initialize tab button.
        
        Args:
            text: Button text
            icon_text: Icon text (emoji or symbol)
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setText(f"{icon_text} {text}" if icon_text else text)
        self.setCheckable(True)
        self.setObjectName("tabButton")
        self.setMinimumHeight(50)
        
        font = QFont("Segoe UI", 10)
        self.setFont(font)


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
        color = QColor(255, 255, 255, 200)
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


class NoSourcesPopup(QDialog):
    """Popup shown when user tries to close settings without any image sources configured.
    
    Offers two choices:
    - "Just Make It Work" - adds curated RSS feeds as default sources
    - "Ehhhh" - closes the application (no sources = can't run)
    """
    
    # Signal emitted when user chooses to add default sources
    add_defaults_requested = Signal()
    # Signal emitted when user chooses to exit
    exit_requested = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        
        card = QWidget(self)
        card.setObjectName("noSourcesPopupCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        
        # Title bar
        title_bar = CustomTitleBar(card)
        title_bar.title_label.setText("No Image Sources")
        title_bar.minimize_btn.hide()
        title_bar.maximize_btn.hide()
        title_bar.close_btn.hide()  # No close button - must choose an option
        card_layout.addWidget(title_bar)
        
        # Body
        body = QWidget(card)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 20, 24, 24)
        body_layout.setSpacing(16)
        
        # Warning message
        message = QLabel(
            "You haven't configured any image sources!\n\n"
            "The screensaver needs at least one folder or RSS feed to display images.\n\n"
            "What would you like to do?"
        )
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        message.setStyleSheet("color: #ffffff; font-size: 14px;")
        body_layout.addWidget(message)
        
        # Buttons
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(12)
        
        # "Just Make It Work" button - adds curated feeds
        make_it_work_btn = QPushButton("Just Make It Work")
        make_it_work_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        make_it_work_btn.clicked.connect(self._on_make_it_work)
        buttons_row.addWidget(make_it_work_btn)
        
        # "Ehhhh" button - exits application
        exit_btn = QPushButton("Ehhhh")
        exit_btn.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
        exit_btn.clicked.connect(self._on_exit)
        buttons_row.addWidget(exit_btn)
        
        body_layout.addLayout(buttons_row)
        card_layout.addWidget(body)
        
        # Shadow effect
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 200))
        card.setGraphicsEffect(shadow)
        
        card.setStyleSheet(
            "QWidget#noSourcesPopupCard {"
            "background-color: rgba(20, 20, 20, 245);"
            "border-radius: 12px;"
            "border: 1px solid rgba(255, 255, 255, 30);"
            "}"
        )
        
        outer_layout.addWidget(card)
        self.setFixedWidth(420)
        self.adjustSize()
    
    def _on_make_it_work(self) -> None:
        """User chose to add default sources."""
        self.add_defaults_requested.emit()
        self.accept()
    
    def _on_exit(self) -> None:
        """User chose to exit the application."""
        self.exit_requested.emit()
        self.reject()
    
    def showEvent(self, event) -> None:
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            try:
                geom = parent.rect()
                self.move(
                    parent.mapToGlobal(geom.center()) - self.rect().center()
                )
            except Exception as e:
                logger.debug("[SETTINGS] Exception suppressed: %s", e)


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

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        shadow.setColor(QColor(0, 0, 0, 180))
        card.setGraphicsEffect(shadow)

        card.setStyleSheet(
            "QWidget#resetDefaultsDialogCard {"
            "background-color: rgba(16, 16, 16, 230);"
            "border-radius: 10px;"
            "}"
        )

        outer_layout.addWidget(card)
        self.adjustSize()

        # Auto-dismiss after a short delay so this behaves like a toast.
        QTimer.singleShot(2000, self.accept)

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
        self.close()

    def reject(self) -> None:
        """Treat rejection the same as acceptance for this toast."""
        self.close()


class SettingsDialog(QDialog):
    """
    Main settings dialog with gorgeous UI.
    
    Features:
    - Custom title bar (frameless)
    - Drop shadow
    - Resizable
    - Animated tab switching
    - Dark theme
    - 4 tabs: Sources, Transitions, Widgets, About
    """
    
    def __init__(self, settings_manager: SettingsManager,
                 animation_manager: AnimationManager,
                 parent: Optional[QWidget] = None):
        """
        Initialize settings dialog.
        
        Args:
            settings_manager: Settings manager instance
            animation_manager: Animation manager for UI animations
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._settings = settings_manager
        self._animations = animation_manager
        self._is_maximized = False
        self._drag_pos = QPoint()
        self._dragging = False
        self._tab_scroll_cache: Dict[str, int] = {}
        self._suppress_scroll_capture: bool = False
        self._tab_keys = [
            "sources",
            "display",
            "transitions",
            "widgets",
            "accessibility",
            "presets",
            "about",
        ]
        self._tab_state_cache: Dict[str, Dict[str, Any]] = {}
        stored_scroll = self._settings.get('ui.last_tab_scroll', {})
        if isinstance(stored_scroll, dict):
            for key, value in stored_scroll.items():
                try:
                    self._tab_scroll_cache[str(key)] = int(value)
                except Exception:
                    logger.debug("Invalid stored scroll position for %s: %r", key, value)
        self._tab_scroll_widgets: Dict[int, Optional[QScrollArea]] = {}
        stored_states = self._settings.get('ui.tab_state', {})
        if isinstance(stored_states, dict):
            for key, value in stored_states.items():
                if isinstance(value, dict):
                    try:
                        self._tab_state_cache[str(key)] = dict(value)
                    except Exception:
                        logger.debug("Invalid stored tab state for %s", key)
        
        self._setup_window()
        self._load_theme()
        self._setup_ui()
        self._connect_signals()
        self._restore_geometry()
        self._restore_last_tab_selection()
        
        logger.info("Settings dialog created")
    
    def _setup_window(self) -> None:
        """Setup window properties."""
        # Frameless window with custom title bar
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowSystemMenuHint
        )
        
        # Enable transparency for drop shadow
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
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
        
        # Drop shadow effect (no global windowOpacity so controls stay fully opaque)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.setGraphicsEffect(shadow)
    
    def _load_theme(self) -> None:
        """Delegates to ui.settings_theme."""
        from ui.settings_theme import load_theme
        load_theme(self)

    def _setup_ui(self) -> None:
        """Setup dialog UI."""
        # Main container (for rounded corners and shadow)
        container = QWidget()
        container.setObjectName("dialogContainer")
        
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Custom title bar
        self.title_bar = CustomTitleBar(self)
        main_layout.addWidget(self.title_bar)
        
        # Content area
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(10, 10, 10, 10)
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
        # Presets icon: sliders/controls symbol for configuration presets
        self.presets_tab_btn = TabButton("Presets", "🎚")
        # Use a circled information glyph for About so the icon's
        # bounding box and spacing match the other emoji-style icons.
        self.about_tab_btn = TabButton("About", "ⓘ")
        
        self.tab_buttons = [
            self.sources_tab_btn,
            self.display_tab_btn,
            self.transitions_tab_btn,
            self.widgets_tab_btn,
            self.accessibility_tab_btn,
            self.presets_tab_btn,
            self.about_tab_btn
        ]
        
        sidebar_layout.addWidget(self.sources_tab_btn)
        sidebar_layout.addWidget(self.display_tab_btn)
        sidebar_layout.addWidget(self.transitions_tab_btn)
        sidebar_layout.addWidget(self.widgets_tab_btn)
        sidebar_layout.addWidget(self.accessibility_tab_btn)
        sidebar_layout.addWidget(self.presets_tab_btn)
        sidebar_layout.addWidget(self.about_tab_btn)
        sidebar_layout.addStretch()
        
        # Right content area with stacked widget
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentArea")
        
        # Create actual tabs
        self.sources_tab = SourcesTab(self._settings)
        self.display_tab = DisplayTab(self._settings)
        self.transitions_tab = TransitionsTab(self._settings)
        self.widgets_tab = WidgetsTab(self._settings)
        self.accessibility_tab = AccessibilityTab(self._settings)
        self.presets_tab = PresetsTab(self._settings)
        self.about_tab = self._create_about_tab()
        
        self.content_stack.addWidget(self.sources_tab)
        self.content_stack.addWidget(self.display_tab)
        self.content_stack.addWidget(self.transitions_tab)
        self.content_stack.addWidget(self.widgets_tab)
        self.content_stack.addWidget(self.accessibility_tab)
        self.content_stack.addWidget(self.presets_tab)
        self.content_stack.addWidget(self.about_tab)
        self._register_tab_scroll_area(0, self.sources_tab)
        self._register_tab_scroll_area(1, self.display_tab)
        self._register_tab_scroll_area(2, self.transitions_tab)
        self._register_tab_scroll_area(3, self.widgets_tab)
        self._register_tab_scroll_area(4, self.accessibility_tab)
        self._register_tab_scroll_area(5, self.presets_tab)
        self._register_tab_scroll_area(6, self.about_tab)
        
        content_layout.addWidget(sidebar)
        content_layout.addWidget(self.content_stack, 1)
        
        main_layout.addLayout(content_layout)
        
        # Size grip for resizing
        self.size_grip = CornerSizeGrip(container)
        self.size_grip.setFixedSize(20, 20)
        
        # Set main layout
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.addWidget(container)
        
        # Default selection
        self.sources_tab_btn.setChecked(True)
        self.content_stack.setCurrentIndex(0)
    
    
    def _create_about_tab(self) -> QWidget:
        """Create about tab. Delegates to ui.settings_about_tab."""
        from ui.settings_about_tab import build_about_tab
        return build_about_tab(self)

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
        self.sources_tab_btn.clicked.connect(lambda: self._switch_tab(0))
        self.display_tab_btn.clicked.connect(lambda: self._switch_tab(1))
        self.transitions_tab_btn.clicked.connect(lambda: self._switch_tab(2))
        self.widgets_tab_btn.clicked.connect(lambda: self._switch_tab(3))
        self.accessibility_tab_btn.clicked.connect(lambda: self._switch_tab(4))
        self.presets_tab_btn.clicked.connect(lambda: self._switch_tab(5))
        self.about_tab_btn.clicked.connect(lambda: self._switch_tab(6))
        
        # Connect preset changes to refresh all tabs
        self.presets_tab.settings_reloaded.connect(self._reload_all_tab_settings)
    
    def _switch_tab(self, index: int, animate: bool = True) -> None:
        """
        Switch to tab with animation.
        
        Args:
            index: Tab index
        """
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
            if index == 6:  # About tab is now at index 6 (presets is at 5)
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
            # Fade out old widget
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
            logger.debug("Failed to restore view state for tab %s", key, exc_info=True)

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
        scrollbar = scroll.verticalScrollBar()
        try:
            self._suppress_scroll_capture = True
            scrollbar.setValue(value)
        except Exception:
            logger.debug("Failed to restore scroll for tab %s", key, exc_info=True)
        finally:
            self._suppress_scroll_capture = False

    def _save_last_tab(self, index: int) -> None:
        if index < 0:
            return
        try:
            self._settings.set('ui.last_tab_index', int(index))
            self._settings.save()
        except Exception:
            logger.debug("Failed to persist last tab index", exc_info=True)

    def _restore_last_tab_selection(self) -> None:
        stored = self._settings.get('ui.last_tab_index', 0)
        try:
            index = int(stored)
        except Exception:
            logger.debug("[SETTINGS] Exception suppressed")
            index = 0
        if index < 0 or index >= len(self.tab_buttons):
            index = 0
        self._suppress_scroll_capture = True
        try:
            self._switch_tab(index, animate=False)
        finally:
            self._suppress_scroll_capture = False

    def closeEvent(self, event):
        # Check if user has configured any image sources
        if not self._has_image_sources():
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
        
        super().closeEvent(event)
    
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
        """Show popup when user tries to close without configuring sources."""
        popup = NoSourcesPopup(self)
        popup.add_defaults_requested.connect(self._on_add_default_sources)
        popup.exit_requested.connect(self._on_exit_without_sources)
        popup.exec()
    
    def _reload_all_tab_settings(self) -> None:
        """Reload settings in all tabs after preset change."""
        # Reload settings in each tab by calling their load/refresh methods
        tabs_to_reload = [
            (0, self.sources_tab),
            (1, self.display_tab),
            (2, self.transitions_tab),
            (3, self.widgets_tab),
            (4, self.accessibility_tab),
        ]
        
        for idx, tab in tabs_to_reload:
            # Check if tab has a refresh/reload method
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
        
        logger.debug("[SETTINGS] Reloaded all tab settings after preset change")
    
    def _on_add_default_sources(self) -> None:
        """Add curated RSS feeds as default sources."""
        try:
            # Use the same curated feeds as the sources tab
            curated_feeds = [
                "https://www.bing.com/HPImageArchive.aspx?format=rss&idx=0&n=8&mkt=en-US",
                "https://www.nasa.gov/feeds/iotd-feed",
                "https://www.reddit.com/r/EarthPorn/top/.json?t=day&limit=25",
                "https://www.reddit.com/r/SpacePorn/top/.json?t=day&limit=25",
                "https://www.reddit.com/r/CityPorn/top/.json?t=day&limit=25",
                "https://www.reddit.com/r/ArchitecturePorn/top/.json?t=day&limit=25",
                "https://www.reddit.com/r/WaterPorn/top/.json?t=day&limit=25",
                "https://www.reddit.com/r/WQHD_Wallpaper/top/.json?t=day&limit=25",
                "https://www.reddit.com/r/4kwallpaper/top/.json?t=day&limit=25",
                "https://www.reddit.com/r/AbandonedPorn/top/.json?t=day&limit=25",
            ]
            
            self._settings.set('sources.rss_feeds', curated_feeds)
            self._settings.save()
            
            # Reload sources tab if it exists
            if hasattr(self, 'sources_tab'):
                self.sources_tab._load_settings()
            
            logger.info("Added %d curated RSS feeds as default sources", len(curated_feeds))
            
            # Now close the dialog
            self.close()
        except Exception:
            logger.exception("Failed to add default sources")
    
    def _on_exit_without_sources(self) -> None:
        """User chose to exit the application without sources."""
        import sys
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
                if hasattr(self, "sources_tab"):
                    self.sources_tab._load_settings()  # type: ignore[attr-defined]
                if hasattr(self, "display_tab"):
                    self.display_tab._load_settings()  # type: ignore[attr-defined]
                if hasattr(self, "transitions_tab"):
                    self.transitions_tab._load_settings()  # type: ignore[attr-defined]
                if hasattr(self, "widgets_tab"):
                    self.widgets_tab._load_settings()  # type: ignore[attr-defined]
            except Exception:
                logger.debug("Failed to reload settings tabs after reset_to_defaults", exc_info=True)

            try:
                notice = getattr(self, "reset_notice_label", None)
                if notice is not None:
                    notice.setVisible(True)
                    QTimer.singleShot(2000, lambda: notice.setVisible(False))
            except Exception:
                logger.debug("Failed to show reset notice label", exc_info=True)
        except Exception as exc:
            logger.exception("Failed to reset settings to defaults: %s", exc)
            StyledPopup.show_error(
                self,
                "Error",
                "Failed to reset settings to defaults.\nSee log for details.",
            )
    
    def _show_more_options_menu(self) -> None:
        """Show the more options context menu."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(25, 25, 30, 240);
                border: 1px solid rgba(80, 80, 90, 180);
                border-radius: 6px;
                padding: 4px 2px;
            }
            QMenu::item {
                background-color: transparent;
                color: rgba(220, 220, 225, 230);
                padding: 6px 16px;
                margin: 1px 3px;
                border-radius: 3px;
                font-size: 11px;
            }
            QMenu::item:selected {
                background-color: rgba(60, 60, 75, 200);
            }
            QMenu::separator {
                height: 1px;
                background-color: rgba(80, 80, 90, 120);
                margin: 3px 8px;
            }
        """)
        
        # Open logs folder
        logs_action = menu.addAction("📁  Open Logs Folder")
        logs_action.triggered.connect(self._open_logs_folder)
        
        # Open settings folder
        settings_action = menu.addAction("⚙  Open Settings Folder")
        settings_action.triggered.connect(self._open_settings_folder)
        
        menu.addSeparator()
        
        # GitHub link
        github_action = menu.addAction("🔗  GitHub Repository")
        github_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/Basjohn/ShittyRandomPhotoScreenSaver")))
        
        # Show menu below the button
        btn = self.more_options_btn
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
    
    def _open_logs_folder(self) -> None:
        """Open the logs folder in file explorer."""
        try:
            logs_path = Path.cwd() / "logs"
            if not logs_path.exists():
                logs_path.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs_path)))
        except Exception:
            logger.debug("Failed to open logs folder", exc_info=True)
    
    def _open_settings_folder(self) -> None:
        """Open the settings folder in file explorer."""
        try:
            # Get the actual JSON settings path from SettingsManager
            settings_path = Path(self._settings._settings.fileName()).parent
            if not settings_path.exists():
                # Fallback to current directory
                settings_path = Path.cwd()
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

            # Apply imported settings to Custom preset
            try:
                from core.settings.presets import apply_preset
                # Switch to custom preset and save imported settings as custom backup
                self._settings.set("preset", "custom")
                apply_preset(self._settings, "custom")
                logger.info("[SETTINGS] Imported settings applied to Custom preset")
            except Exception:
                logger.debug("Failed to apply imported settings to Custom preset", exc_info=True)

            # Reload all tabs so the UI reflects the imported configuration
            # immediately.
            try:
                self._reload_all_tab_settings()
                # Also refresh presets tab to show Custom is selected
                if hasattr(self, "presets_tab"):
                    self.presets_tab.refresh()
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
        """Toggle window maximize state."""
        if self._is_maximized:
            self.showNormal()
            self._is_maximized = False
        else:
            self.showMaximized()
            self._is_maximized = True
    
    def resizeEvent(self, event):
        """Handle resize event to position size grip and save geometry."""
        super().resizeEvent(event)
        
        # Position size grip in bottom-right corner
        if hasattr(self, 'size_grip'):
            try:
                parent = self.size_grip.parent() or self
                pw = parent.width()
                ph = parent.height()
                self.size_grip.move(
                    pw - self.size_grip.width(),
                    ph - self.size_grip.height(),
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
                ResourceManager().register_qt(
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
        super().showEvent(event)
        try:
            self._update_about_header_images()
        except Exception as e:
            logger.debug("[SETTINGS] Exception suppressed: %s", e)
    
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
                ResourceManager().register_qt(
                    self._move_timer,
                    resource_type=ResourceType.TIMER,
                    description="Settings dialog move debounce timer",
                    group="qt",
                )
            except Exception:
                pass
        self._move_timer.start(500)  # Save 500ms after move stops
    
    def mousePressEvent(self, event):
        """Handle mouse press for window dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Don't interfere with size grip
            size_grip_rect = self.size_grip.geometry() if hasattr(self, 'size_grip') else None
            if size_grip_rect and size_grip_rect.contains(event.pos()):
                super().mousePressEvent(event)
                return
            
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
            self._dragging = False
            event.accept()
    
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
