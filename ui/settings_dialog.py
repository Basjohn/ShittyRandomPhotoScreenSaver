"""
Settings Dialog for screensaver configuration.

Features gorgeous UI with:
- Custom title bar (no native window border)
- Drop shadow effect
- Resizable window
- Animated tab switching
- Dark theme
- Modern, polished design
"""
from typing import Optional
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
    QLabel, QStackedWidget, QGraphicsDropShadowEffect, QSizeGrip
)
from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui import QIcon, QFont, QColor, QPalette

from core.logging.logger import get_logger
from core.settings.settings_manager import SettingsManager
from core.animation import AnimationManager
from ui.tabs import SourcesTab, TransitionsTab, WidgetsTab

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
        self.title_label = QLabel("Screensaver Settings")
        self.title_label.setObjectName("titleBarLabel")
        title_font = QFont("Segoe UI", 11, QFont.Weight.Bold)
        self.title_label.setFont(title_font)
        
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
        
        self._setup_window()
        self._load_theme()
        self._setup_ui()
        self._connect_signals()
        
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
        
        # Size
        self.setMinimumSize(900, 600)
        self.resize(1000, 700)
        
        # Drop shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.setGraphicsEffect(shadow)
    
    def _load_theme(self) -> None:
        """Load dark theme stylesheet."""
        try:
            theme_path = Path(__file__).parent.parent / "themes" / "dark.qss"
            if theme_path.exists():
                with open(theme_path, 'r', encoding='utf-8') as f:
                    stylesheet = f.read()
                    
                    # Add custom styles for settings dialog
                    custom_styles = """
                    /* Settings Dialog Custom Styles */
                    QDialog {
                        background-color: #2b2b2b;
                        border-radius: 10px;
                    }
                    
                    #customTitleBar {
                        background-color: #1e1e1e;
                        border-top-left-radius: 10px;
                        border-top-right-radius: 10px;
                    }
                    
                    #titleBarLabel {
                        color: #ffffff;
                        padding-left: 10px;
                    }
                    
                    #titleBarButton {
                        background-color: transparent;
                        color: #ffffff;
                        border: none;
                        font-size: 16px;
                        font-weight: bold;
                    }
                    
                    #titleBarButton:hover {
                        background-color: #3e3e3e;
                        border-radius: 4px;
                    }
                    
                    #titleBarCloseButton {
                        background-color: transparent;
                        color: #ffffff;
                        border: none;
                        font-size: 18px;
                        font-weight: bold;
                    }
                    
                    #titleBarCloseButton:hover {
                        background-color: #e81123;
                        border-radius: 4px;
                    }
                    
                    #tabButton {
                        background-color: #2b2b2b;
                        color: #cccccc;
                        border: none;
                        text-align: left;
                        padding: 10px 20px;
                        margin: 2px;
                        border-radius: 6px;
                    }
                    
                    #tabButton:hover {
                        background-color: #3e3e3e;
                        color: #ffffff;
                    }
                    
                    #tabButton:checked {
                        background-color: #0078d4;
                        color: #ffffff;
                        font-weight: bold;
                    }
                    
                    #contentArea {
                        background-color: #1e1e1e;
                        border-radius: 8px;
                        padding: 20px;
                    }
                    """
                    
                    self.setStyleSheet(stylesheet + custom_styles)
                    logger.debug("Theme loaded successfully")
            else:
                logger.warning(f"[FALLBACK] Theme file not found: {theme_path}")
        except Exception as e:
            logger.exception(f"Failed to load theme: {e}")
    
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
        self.transitions_tab_btn = TabButton("Transitions", "✨")
        self.widgets_tab_btn = TabButton("Widgets", "🕐")
        self.about_tab_btn = TabButton("About", "ℹ")
        
        self.tab_buttons = [
            self.sources_tab_btn,
            self.transitions_tab_btn,
            self.widgets_tab_btn,
            self.about_tab_btn
        ]
        
        sidebar_layout.addWidget(self.sources_tab_btn)
        sidebar_layout.addWidget(self.transitions_tab_btn)
        sidebar_layout.addWidget(self.widgets_tab_btn)
        sidebar_layout.addWidget(self.about_tab_btn)
        sidebar_layout.addStretch()
        
        # Right content area with stacked widget
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentArea")
        
        # Create actual tabs
        self.sources_tab = SourcesTab(self._settings)
        self.transitions_tab = TransitionsTab(self._settings)
        self.widgets_tab = WidgetsTab(self._settings)
        self.about_tab = self._create_about_tab()
        
        self.content_stack.addWidget(self.sources_tab)
        self.content_stack.addWidget(self.transitions_tab)
        self.content_stack.addWidget(self.widgets_tab)
        self.content_stack.addWidget(self.about_tab)
        
        content_layout.addWidget(sidebar)
        content_layout.addWidget(self.content_stack, 1)
        
        main_layout.addLayout(content_layout)
        
        # Size grip for resizing
        self.size_grip = QSizeGrip(container)
        self.size_grip.setFixedSize(20, 20)
        
        # Set main layout
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.addWidget(container)
        
        # Default selection
        self.sources_tab_btn.setChecked(True)
        self.content_stack.setCurrentIndex(0)
    
    
    def _create_about_tab(self) -> QWidget:
        """Create about tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("About")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)
        
        # About info
        about_text = QLabel(
            "<h2>Shitty Random Photo Screensaver</h2>"
            "<p>Version 1.0.0</p>"
            "<p>A feature-rich photo screensaver with transitions, widgets, and more!</p>"
            "<br>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>4 Professional transitions (Crossfade, Slide, Diffuse, Block Flip)</li>"
            "<li>Pan & Scan (Ken Burns effect)</li>"
            "<li>Clock and Weather widgets</li>"
            "<li>Multiple image sources (Folders, RSS feeds)</li>"
            "<li>Multi-monitor support</li>"
            "<li>21 Easing curves for smooth animations</li>"
            "</ul>"
            "<br>"
            "<p><b>Hotkeys While Running:</b></p>"
            "<ul>"
            "<li><b>Z</b> - Go back to previous image</li>"
            "<li><b>X</b> - Go forward to next image</li>"
            "<li><b>C</b> - Cycle through transition modes</li>"
            "<li><b>S</b> - Stop screensaver and open Settings</li>"
            "<li><b>ESC/Click/Any Key</b> - Exit screensaver</li>"
            "</ul>"
        )
        about_text.setWordWrap(True)
        about_text.setStyleSheet("color: #cccccc; padding: 20px;")
        about_text.setOpenExternalLinks(True)
        layout.addWidget(about_text)
        layout.addStretch()
        
        return widget
    
    def _connect_signals(self) -> None:
        """Connect signals to slots."""
        # Title bar
        self.title_bar.close_clicked.connect(self.close)
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self._toggle_maximize)
        
        # Tab buttons
        self.sources_tab_btn.clicked.connect(lambda: self._switch_tab(0))
        self.transitions_tab_btn.clicked.connect(lambda: self._switch_tab(1))
        self.widgets_tab_btn.clicked.connect(lambda: self._switch_tab(2))
        self.about_tab_btn.clicked.connect(lambda: self._switch_tab(3))
    
    def _switch_tab(self, index: int) -> None:
        """
        Switch to tab with animation.
        
        Args:
            index: Tab index
        """
        # Uncheck all buttons
        for btn in self.tab_buttons:
            btn.setChecked(False)
        
        # Check selected button
        self.tab_buttons[index].setChecked(True)
        
        # Get widgets
        old_widget = self.content_stack.currentWidget()
        
        # Create simple fade animation using AnimationManager
        def fade_out_complete():
            # Switch to new widget
            self.content_stack.setCurrentIndex(index)
            new_widget = self.content_stack.currentWidget()
            
            # Fade in new widget
            self._animations.animate_property(
                target=new_widget,
                property_name='windowOpacity',
                start_value=0.0,
                end_value=1.0,
                duration=0.15
            )
            self._animations.start()
        
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
        
        logger.debug(f"Switched to tab {index}")
    
    def _toggle_maximize(self) -> None:
        """Toggle window maximize state."""
        if self._is_maximized:
            self.showNormal()
            self._is_maximized = False
        else:
            self.showMaximized()
            self._is_maximized = True
    
    def resizeEvent(self, event):
        """Handle resize event to position size grip."""
        super().resizeEvent(event)
        
        # Position size grip in bottom-right corner
        if hasattr(self, 'size_grip'):
            self.size_grip.move(
                self.width() - self.size_grip.width() - 10,
                self.height() - self.size_grip.height() - 10
            )
