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
    QLabel, QStackedWidget, QGraphicsDropShadowEffect, QSizeGrip,
    QMessageBox, QSizePolicy,
)
from PySide6.QtCore import Qt, QPoint, Signal, QUrl
from PySide6.QtGui import QFont, QColor, QPixmap, QDesktopServices, QPainter, QPen

from core.logging.logger import get_logger
from core.settings.settings_manager import SettingsManager
from core.animation import AnimationManager
from ui.tabs import SourcesTab, TransitionsTab, WidgetsTab, DisplayTab

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
        
        self._setup_window()
        self._load_theme()
        self._setup_ui()
        self._connect_signals()
        self._restore_geometry()
        
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
        
        # Minimum size (kept modest so the dialog remains usable on
        # 1080p displays while still providing enough room for the
        # richer tabs like Sources and About).
        self.setMinimumSize(800, 500)
        
        # Check if we have saved geometry first
        saved_geometry = self._settings.get('ui.dialog_geometry', {})
        
        if saved_geometry and 'width' in saved_geometry and 'height' in saved_geometry:
            # Use saved geometry (will be applied in _restore_geometry())
            pass
        else:
            # No saved geometry - default to 60% of primary screen
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            if screen:
                geometry = screen.geometry()
                default_width = int(geometry.width() * 0.6)
                default_height = int(geometry.height() * 0.6)
            else:
                default_width = 1000
                default_height = 700
            
            self.resize(default_width, default_height)
            logger.debug(f"No saved geometry - defaulting to 60% of screen: {default_width}x{default_height}")
        
        # Drop shadow effect (no global windowOpacity so controls stay fully opaque)
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
                        background-color: transparent;
                        border: 3px solid #ffffff;
                        border-radius: 12px;
                    }
                    
                    #dialogContainer {
                        background-color: #2B2B2B;
                        border: 2px solid #5a5a5a;
                        border-radius: 10px;
                    }
                    
                    #customTitleBar {
                        background-color: #1E1E1E;
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
                        background-color: rgba(62, 62, 62, 0.8);
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
                        background-color: rgba(232, 17, 35, 0.8);
                        border-radius: 4px;
                    }
                    
                    #sidebar {
                        background-color: #232323;
                        border-radius: 8px;
                    }
                    
                    #tabButton {
                        background-color: #2B2B2B;
                        color: #cccccc;
                        border: none;
                        text-align: left;
                        padding: 10px 20px;
                        margin: 2px;
                        border-radius: 6px;
                    }
                    
                    #tabButton:hover {
                        background-color: #3E3E3E;
                        color: #ffffff;
                    }
                    
                    #tabButton:checked {
                        background-color: #0078D4;
                        color: #ffffff;
                        font-weight: bold;
                    }
                    
                    #contentArea {
                        background-color: #1E1E1E;
                        border-radius: 8px;
                        padding: 20px;
                    }
                    
                    /* Input fields and controls - dark theme, no bright white */
                    QLineEdit {
                        background-color: rgba(45, 45, 45, 0.8);
                        color: #ffffff;
                        border: 1px solid rgba(90, 90, 90, 0.8);
                        border-radius: 4px;
                        padding: 6px;
                    }
                    
                    QLineEdit:focus {
                        border: 1px solid rgba(0, 120, 212, 0.8);
                    }
                    
                    QComboBox {
                        background-color: rgba(45, 45, 45, 0.8);
                        color: #ffffff;
                        border: 1px solid rgba(90, 90, 90, 0.8);
                        border-radius: 4px;
                        padding: 6px;
                    }
                    
                    QComboBox:hover {
                        border: 1px solid rgba(0, 120, 212, 0.8);
                    }
                    
                    QComboBox::drop-down {
                        border: none;
                        background-color: rgba(62, 62, 62, 0.8);
                        border-radius: 2px;
                    }
                    
                    QComboBox QAbstractItemView {
                        background-color: rgba(45, 45, 45, 0.95);
                        color: #ffffff;
                        border: 1px solid rgba(90, 90, 90, 0.8);
                        selection-background-color: rgba(0, 120, 212, 0.8);
                    }
                    
                    QSpinBox {
                        background-color: rgba(45, 45, 45, 0.8);
                        color: #ffffff;
                        border: 1px solid rgba(90, 90, 90, 0.8);
                        border-radius: 4px;
                        padding: 4px;
                    }
                    
                    QSpinBox:focus {
                        border: 1px solid rgba(0, 120, 212, 0.8);
                    }
                    
                    QListWidget {
                        background-color: rgba(35, 35, 35, 0.8);
                        color: #ffffff;
                        border: 1px solid rgba(90, 90, 90, 0.8);
                        border-radius: 4px;
                    }
                    
                    QListWidget::item:selected {
                        background-color: rgba(70, 70, 70, 0.8);
                        border-left: 3px solid rgba(120, 120, 120, 0.9);
                    }
                    
                    QListWidget::item:hover {
                        background-color: rgba(62, 62, 62, 0.8);
                    }
                    
                    QPushButton {
                        background-color: rgba(60, 60, 60, 0.8);
                        color: #ffffff;
                        border: 1px solid rgba(90, 90, 90, 0.8);
                        border-radius: 4px;
                        padding: 8px 16px;
                    }
                    
                    QPushButton:hover {
                        background-color: rgba(75, 75, 75, 0.8);
                        border: 1px solid rgba(110, 110, 110, 0.8);
                    }
                    
                    QPushButton:pressed {
                        background-color: rgba(50, 50, 50, 0.8);
                        border: 1px solid rgba(70, 70, 70, 0.8);
                    }
                    
                    QGroupBox {
                        background-color: rgba(40, 40, 40, 0.8);
                        border: 1px solid rgba(90, 90, 90, 0.8);
                        border-radius: 6px;
                        margin-top: 15px;
                        margin-bottom: 10px;
                        padding: 15px 10px 10px 10px;
                        color: #ffffff;
                    }
                    
                    QGroupBox::title {
                        subcontrol-origin: margin;
                        subcontrol-position: top left;
                        padding: 2px 8px;
                        margin-top: 5px;
                        color: #ffffff;
                    }
                    
                    QCheckBox {
                        color: #ffffff;
                        spacing: 8px;
                    }
                    
                    QCheckBox::indicator {
                        width: 18px;
                        height: 18px;
                        background-color: rgba(45, 45, 45, 0.8);
                        border: 1px solid rgba(90, 90, 90, 0.8);
                        border-radius: 3px;
                    }
                    
                    QCheckBox::indicator:checked {
                        background-color: rgba(0, 120, 212, 0.8);
                        border: 1px solid rgba(0, 120, 212, 0.8);
                    }
                    
                    QLabel {
                        color: #ffffff;
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
        self.display_tab_btn = TabButton("Display", "🖥")
        self.transitions_tab_btn = TabButton("Transitions", "✨")
        self.widgets_tab_btn = TabButton("Widgets", "🕐")
        # Use a circled information glyph for About so the icon's
        # bounding box and spacing match the other emoji-style icons.
        self.about_tab_btn = TabButton("About", "ⓘ")
        
        self.tab_buttons = [
            self.sources_tab_btn,
            self.display_tab_btn,
            self.transitions_tab_btn,
            self.widgets_tab_btn,
            self.about_tab_btn
        ]
        
        sidebar_layout.addWidget(self.sources_tab_btn)
        sidebar_layout.addWidget(self.display_tab_btn)
        sidebar_layout.addWidget(self.transitions_tab_btn)
        sidebar_layout.addWidget(self.widgets_tab_btn)
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
        self.about_tab = self._create_about_tab()
        
        self.content_stack.addWidget(self.sources_tab)
        self.content_stack.addWidget(self.display_tab)
        self.content_stack.addWidget(self.transitions_tab)
        self.content_stack.addWidget(self.widgets_tab)
        self.content_stack.addWidget(self.about_tab)
        
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
        """Create about tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Main content card (matches ABOUTExample mockup)
        content_card = QWidget(widget)
        content_card.setObjectName("aboutContentCard")
        content_card.setStyleSheet(
            "#aboutContentCard {"
            "  background-color: #1f1f1f;"
            "  border-radius: 8px;"
            "}"
        )
        card_layout = QVBoxLayout(content_card)
        # Slightly tighter top margin and vertical spacing to reduce empty space
        card_layout.setContentsMargins(24, 12, 24, 24)
        card_layout.setSpacing(12)

        # Header with logo and Shoogle artwork, scaled down only
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        # Keep references so we can rescale responsively on resize without
        # repeatedly degrading the images.
        self._about_content_card = content_card
        self._about_header_layout = header_layout
        self._about_logo_label = None
        self._about_shoogle_label = None
        self._about_logo_source = None
        self._about_shoogle_source = None
        self._about_last_card_width: int = 0

        # Resolve images directory robustly (works both in dev and frozen builds)
        try:
            images_dir = (Path(__file__).resolve().parent.parent / "images").resolve()
            if not images_dir.exists():
                # Fallback: project launched from root, look for ./images
                alt_dir = (Path.cwd() / "images").resolve()
                if alt_dir.exists():
                    images_dir = alt_dir
            logger.debug("[ABOUT] Images directory resolved to %s (exists=%s)", images_dir, images_dir.exists())
        except Exception:
            images_dir = Path.cwd() / "images"

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._about_logo_label = logo_label
        try:
            logo_path = images_dir / "Logo.png"
            logo_pm = QPixmap(str(logo_path))
            logger.debug("[ABOUT] Loading logo pixmap from %s (exists=%s, null=%s)", logo_path, logo_path.exists(), logo_pm.isNull())
            if not logo_pm.isNull():
                # Store the original, unscaled pixmap; scaling is handled
                # centrally in _update_about_header_images().
                self._about_logo_source = logo_pm
        except Exception:
            logger.debug("[ABOUT] Failed to load Logo.png", exc_info=True)
        header_layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignTop)

        shoogle_label = QLabel()
        shoogle_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._about_shoogle_label = shoogle_label
        try:
            shoogle_path = images_dir / "Shoogle300W.png"
            shoogle_pm = QPixmap(str(shoogle_path))
            logger.debug("[ABOUT] Loading Shoogle pixmap from %s (exists=%s, null=%s)", shoogle_path, shoogle_path.exists(), shoogle_pm.isNull())
            if not shoogle_pm.isNull():
                # Store the original, unscaled pixmap for responsive
                # scaling based on the dialog width.
                self._about_shoogle_source = shoogle_pm
        except Exception:
            logger.debug("[ABOUT] Failed to load Shoogle300W.png", exc_info=True)
        header_layout.addWidget(shoogle_label, 0, Qt.AlignmentFlag.AlignTop)
        header_layout.addStretch()
        card_layout.addLayout(header_layout)

        # Blurb loaded from external text file when available
        blurb_label = QLabel()
        blurb_label.setWordWrap(True)
        # Left-align blurb so it lines up with the logo and buttons
        blurb_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        blurb_label.setStyleSheet("color: #dddddd; font-size: 12pt;")
        blurb_label.setTextFormat(Qt.TextFormat.RichText)

        default_blurb = (
            "Made for my own weird niche, shared freely for yours.<br>"
            "You can always donate to my dumbass though or buy my shitty literature."
        )
        blurb_text = default_blurb
        try:
            about_path = Path.home() / "Documents" / "AboutBlurb.txt"
            if about_path.exists():
                raw = about_path.read_text(encoding="utf-8").splitlines()
                blurb_lines: list[str] = []
                for line in raw:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    lower = stripped.lower()
                    # Skip URLs and instructions from the spec file
                    if lower.startswith("http://") or lower.startswith("https://"):
                        continue
                    if "centre-aligned" in lower or "center-aligned" in lower:
                        continue
                    if "then the following" in lower and "links" in lower:
                        continue
                    # Strip wrapping quotes if present
                    if (stripped.startswith('"') and stripped.endswith('"')) or (
                        stripped.startswith("'") and stripped.endswith("'")
                    ):
                        stripped = stripped[1:-1].strip()
                    if stripped:
                        blurb_lines.append(stripped)

                if blurb_lines:
                    blurb_text = "<br>".join(blurb_lines)
        except Exception:
            pass

        # Small stylistic tweak to italicize the "can" in the second sentence,
        # matching the ABOUTExample reference mockup.
        if "You can always" in blurb_text:
            blurb_text = blurb_text.replace("You can", "You <i>can</i>", 1)

        blurb_label.setText(blurb_text)
        card_layout.addWidget(blurb_label)

        # External links row (PayPal, Goodreads, Amazon, GitHub)
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(16)
        # Left-align buttons to share a vertical line with the logo and blurb
        buttons_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        def _make_link_button(text: str, url: str) -> QPushButton:
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.setStyleSheet(
                "QPushButton {"
                "  padding: 6px 18px;"
                "  font-weight: bold;"
                "  border-radius: 16px;"
                "  background-color: #2f2f2f;"
                "  color: #ffffff;"
                "  border: 1px solid #555555;"
                "}"
                "QPushButton:hover {"
                "  background-color: #3a3a3a;"
                "  border-color: #777777;"
                "}"
                "QPushButton:pressed {"
                "  background-color: #262626;"
                "}"
            )

            def _open() -> None:
                try:
                    QDesktopServices.openUrl(QUrl(url))
                except Exception:
                    pass

            btn.clicked.connect(_open)
            return btn

        buttons_row.addWidget(_make_link_button("PAYPAL", "https://www.paypal.com/donate/?business=UBZJY8KHKKLGC&no_recurring=0&item_name=Why+are+you+doing+this?+Are+you+drunk?+&currency_code=USD"))
        buttons_row.addWidget(_make_link_button("GOODREADS", "https://www.goodreads.com/book/show/25006763-usu"))
        buttons_row.addWidget(_make_link_button("AMAZON", "https://www.amazon.com/Usu-Jayde-Ver-Elst-ebook/dp/B00V8A5K7Y"))
        buttons_row.addWidget(_make_link_button("GITHUB", "https://github.com/Basjohn?tab=repositories"))
        card_layout.addLayout(buttons_row)

        # Hotkeys section beneath links (left-aligned, no bullet indent)
        hotkeys_label = QLabel(
            "<p><b>Hotkeys While Running:</b></p>"
            "<p>"
            "<b>Z</b>  - Go back to previous image<br>"
            "<b>X</b>  - Go forward to next image<br>"
            "<b>C</b>  - Cycle transition modes (Crossfade   Slide   Wipe   Diffuse   Block Flip)<br>"
            "<b>S</b>  - Stop screensaver and open Settings<br>"
            "<b>ESC</b> - Exit screensaver<br>"
            "<b>Ctrl (HOLD)</b> - Temporary interaction mode (widgets clickable without exiting)<br>"
            "<b>Mouse Click/Any Other Key</b> - Exit screensaver"
            "</p>"
        )
        hotkeys_label.setWordWrap(True)
        hotkeys_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        hotkeys_label.setStyleSheet("color: #cccccc; margin-top: 16px;")
        hotkeys_label.setOpenExternalLinks(False)
        card_layout.addWidget(hotkeys_label)

        # Attach card to main layout
        layout.addWidget(content_card)
        layout.addStretch()

        # Reset to Defaults button (bottom-left, small and unobtrusive)
        button_row = QHBoxLayout()
        self.reset_defaults_btn = QPushButton("Reset To Defaults")
        self.reset_defaults_btn.setObjectName("resetDefaultsButton")
        self.reset_defaults_btn.setFixedHeight(24)
        self.reset_defaults_btn.setStyleSheet("font-size: 11px; padding: 4px 10px;")
        self.reset_defaults_btn.clicked.connect(self._on_reset_to_defaults_clicked)
        button_row.addWidget(self.reset_defaults_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        return widget

    def _update_about_header_images(self) -> None:
        """Scale About header images responsively based on dialog width.

        The logo and fish artwork are always scaled down from their source
        resolution using smooth, high-DPI aware transforms and never
        upscaled beyond 100% size. When the settings dialog is narrow the
        images shrink together so they never clip or overlap.
        """

        card = getattr(self, "_about_content_card", None)
        header_layout = getattr(self, "_about_header_layout", None)
        logo_label = getattr(self, "_about_logo_label", None)
        shoogle_label = getattr(self, "_about_shoogle_label", None)
        logo_src = getattr(self, "_about_logo_source", None)
        shoogle_src = getattr(self, "_about_shoogle_source", None)

        if (
            card is None
            or header_layout is None
            or logo_label is None
            or shoogle_label is None
            or logo_src is None
            or logo_src.isNull()
            or shoogle_src is None
            or shoogle_src.isNull()
        ):
            return

        current_width = card.width()
        if current_width <= 0:
            return

        # Avoid aggressive rescaling on tiny drags by only recomputing when
        # the card width has changed meaningfully since the last update.
        last_width = getattr(self, "_about_last_card_width", 0)
        if last_width and abs(current_width - last_width) < 12:
            return
        self._about_last_card_width = current_width

        available = current_width - card.contentsMargins().left() - card.contentsMargins().right()
        if available <= 0:
            return

        spacing = header_layout.spacing()
        total_w = logo_src.width() + shoogle_src.width()
        if total_w <= 0 or available <= spacing + 10:
            scale = 1.0
        else:
            scale = (available - spacing) / float(total_w)
            # Allow a modest upscale so the header artwork can occupy the
            # available space on wide dialogs while still clamping to
            # reasonable bounds.
            scale = max(0.5, min(2.0, scale))

        try:
            dpr = float(self.devicePixelRatioF())
        except Exception:
            dpr = 1.0
        if dpr < 1.0:
            dpr = 1.0

        def _apply(src: QPixmap, label: QLabel, *, y_offset: int = 0) -> None:
            if src is None or src.isNull():
                return

            target_w = max(1, int(round(src.width() * scale * dpr)))
            target_h = max(1, int(round(src.height() * scale * dpr)))

            scaled = src.scaled(
                target_w,
                target_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            if dpr != 1.0:
                try:
                    scaled.setDevicePixelRatio(dpr)
                except Exception:
                    pass

            label.setPixmap(scaled)

            # Use logical (device-independent) size for the label so the
            # layout behaves consistently on high-DPI displays.
            logical_w = max(1, int(round(scaled.width() / dpr)))
            logical_h = max(1, int(round(scaled.height() / dpr)))
            label.setMinimumSize(logical_w, logical_h)
            label.setMaximumSize(logical_w, logical_h)
            label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

            if y_offset != 0:
                label.setContentsMargins(0, max(0, y_offset), 0, 0)
            else:
                label.setContentsMargins(0, 0, 0, 0)

        # Slight vertical nudge so the two images feel aligned by eye; the
        # Shoogle artwork rides a touch lower so we bias the logo down a
        # few extra pixels instead.
        _apply(logo_src, logo_label, y_offset=5)
        _apply(shoogle_src, shoogle_label, y_offset=0)
    
    def _connect_signals(self) -> None:
        """Connect signals to slots."""
        # Title bar
        self.title_bar.close_clicked.connect(self.close)
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self._toggle_maximize)
        
        # Tab buttons
        self.sources_tab_btn.clicked.connect(lambda: self._switch_tab(0))
        self.display_tab_btn.clicked.connect(lambda: self._switch_tab(1))
        self.transitions_tab_btn.clicked.connect(lambda: self._switch_tab(2))
        self.widgets_tab_btn.clicked.connect(lambda: self._switch_tab(3))
        self.about_tab_btn.clicked.connect(lambda: self._switch_tab(4))
    
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

            if index == 4:
                try:
                    self._about_last_card_width = 0
                except Exception:
                    pass
                try:
                    self._update_about_header_images()
                except Exception:
                    pass

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

    def _on_reset_to_defaults_clicked(self) -> None:
        """Reset all application settings back to defaults with confirmation."""

        reply = QMessageBox.question(
            self,
            "Reset To Defaults",
            (
                "This will reset all settings to their default values.\n\n"
                "You will need to close this dialog and restart the screensaver "
                "for all changes to fully apply.\n\nContinue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._settings.reset_to_defaults()
            QMessageBox.information(
                self,
                "Defaults Restored",
                (
                    "Settings have been reset to defaults.\n\n"
                    "Please close this dialog and restart the screensaver to "
                    "reload all settings."
                ),
            )
        except Exception as exc:
            logger.exception("Failed to reset settings to defaults: %s", exc)
            QMessageBox.warning(
                self,
                "Error",
                "Failed to reset settings to defaults. See log for details.",
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
            except Exception:
                pass
        
        # Save geometry on resize (debounced to avoid excessive saves)
        if hasattr(self, '_resize_timer'):
            self._resize_timer.stop()
        else:
            from PySide6.QtCore import QTimer
            self._resize_timer = QTimer()
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._save_geometry)
        self._resize_timer.start(500)  # Save 500ms after resize stops
        
        # Keep About header images scaled appropriately for the current
        # dialog width, but guard in case the About tab has not been
        # constructed yet.
        try:
            self._update_about_header_images()
        except Exception:
            pass
    
    def showEvent(self, event):
        super().showEvent(event)
        try:
            self._update_about_header_images()
        except Exception:
            pass
    
    def moveEvent(self, event):
        """Handle move event to save geometry."""
        super().moveEvent(event)
        # Save geometry on move (debounced to avoid excessive saves)
        if hasattr(self, '_move_timer'):
            self._move_timer.stop()
        else:
            from PySide6.QtCore import QTimer
            self._move_timer = QTimer()
            self._move_timer.setSingleShot(True)
            self._move_timer.timeout.connect(self._save_geometry)
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
            self.move(geometry.get('x', 100), geometry.get('y', 100))
            self.resize(geometry.get('width', 1000), geometry.get('height', 700))
            logger.debug(f"Restored dialog geometry: {geometry}")
