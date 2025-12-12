"""
Styled popup notifications for SRPSS.

Provides dark glass themed popup dialogs that match the application's visual style.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QWidget,
    QGraphicsDropShadowEffect, QColorDialog,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPalette

from core.logging.logger import get_logger

logger = get_logger(__name__)


class StyledPopup(QDialog):
    """Dark glass themed popup notification.
    
    Features:
    - Frameless window with custom title bar
    - Semi-transparent dark background
    - Optional auto-close timer
    - Fade in/out animations
    """
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        title: str = "Notice",
        message: str = "",
        icon_type: str = "info",  # "info", "warning", "error", "success"
        auto_close_ms: int = 0,  # 0 = no auto-close
    ):
        super().__init__(parent)
        
        self._title = title
        self._message = message
        self._icon_type = icon_type
        self._auto_close_ms = auto_close_ms
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        
        self._setup_ui()
        
        # Auto-close timer
        if auto_close_ms > 0:
            QTimer.singleShot(auto_close_ms, self.accept)
    
    def _setup_ui(self) -> None:
        """Build the popup UI."""
        # Main container with styling
        container = QWidget(self)
        container.setObjectName("popupContainer")
        container.setStyleSheet("""
            #popupContainer {
                background-color: rgba(25, 25, 30, 235);
                border: 1px solid rgba(80, 80, 90, 180);
                border-radius: 10px;
            }
        """)
        
        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 4)
        container.setGraphicsEffect(shadow)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(16, 12, 16, 16)
        container_layout.setSpacing(12)
        
        # Title bar
        title_bar = QHBoxLayout()
        title_bar.setSpacing(8)
        
        # Icon based on type
        icon_map = {
            "info": "ℹ",
            "warning": "⚠",
            "error": "✕",
            "success": "✓",
        }
        icon_colors = {
            "info": "rgba(100, 180, 255, 255)",
            "warning": "rgba(255, 200, 80, 255)",
            "error": "rgba(255, 100, 100, 255)",
            "success": "rgba(100, 220, 140, 255)",
        }
        
        icon_label = QLabel(icon_map.get(self._icon_type, "ℹ"))
        icon_label.setStyleSheet(f"""
            font-size: 16px;
            color: {icon_colors.get(self._icon_type, icon_colors['info'])};
        """)
        title_bar.addWidget(icon_label)
        
        title_label = QLabel(self._title)
        title_label.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            color: rgba(240, 240, 245, 240);
        """)
        title_bar.addWidget(title_label)
        title_bar.addStretch()
        
        container_layout.addLayout(title_bar)
        
        # Message
        if self._message:
            msg_label = QLabel(self._message)
            msg_label.setWordWrap(True)
            msg_label.setStyleSheet("""
                font-size: 12px;
                color: rgba(200, 200, 210, 220);
                padding: 4px 0;
            """)
            container_layout.addWidget(msg_label)
        
        # OK button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        ok_btn = QPushButton("OK")
        ok_btn.setFixedSize(70, 28)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(60, 60, 70, 200);
                border: 1px solid rgba(100, 100, 110, 180);
                border-radius: 4px;
                color: rgba(240, 240, 245, 230);
                font-size: 12px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 95, 220);
            }
            QPushButton:pressed {
                background-color: rgba(50, 50, 60, 220);
            }
        """)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        
        container_layout.addLayout(btn_layout)
        
        # Set minimum size
        self.setMinimumWidth(280)
        self.adjustSize()
    
    @staticmethod
    def show_info(parent: Optional[QWidget], title: str, message: str, auto_close_ms: int = 0) -> None:
        """Show an info popup."""
        popup = StyledPopup(parent, title, message, "info", auto_close_ms)
        popup.exec()
    
    @staticmethod
    def show_success(parent: Optional[QWidget], title: str, message: str, auto_close_ms: int = 0) -> None:
        """Show a success popup."""
        popup = StyledPopup(parent, title, message, "success", auto_close_ms)
        popup.exec()
    
    @staticmethod
    def show_warning(parent: Optional[QWidget], title: str, message: str, auto_close_ms: int = 0) -> None:
        """Show a warning popup."""
        popup = StyledPopup(parent, title, message, "warning", auto_close_ms)
        popup.exec()
    
    @staticmethod
    def show_error(parent: Optional[QWidget], title: str, message: str, auto_close_ms: int = 0) -> None:
        """Show an error popup."""
        popup = StyledPopup(parent, title, message, "error", auto_close_ms)
        popup.exec()


class StyledColorPicker:
    """Centralized styled color picker utility.
    
    Provides a consistent dark-themed color picker dialog that matches
    the application's visual style. Wraps QColorDialog with custom styling.
    """
    
    # Dark theme stylesheet for QColorDialog
    _STYLESHEET = """
        QColorDialog {
            background-color: rgb(30, 30, 35);
            color: rgb(220, 220, 225);
        }
        QColorDialog QWidget {
            background-color: rgb(30, 30, 35);
            color: rgb(220, 220, 225);
        }
        QColorDialog QLabel {
            color: rgb(220, 220, 225);
        }
        QColorDialog QLineEdit {
            background-color: rgb(45, 45, 50);
            border: 1px solid rgb(70, 70, 80);
            border-radius: 4px;
            padding: 4px 8px;
            color: rgb(220, 220, 225);
        }
        QColorDialog QSpinBox {
            background-color: rgb(45, 45, 50);
            border: 1px solid rgb(70, 70, 80);
            border-radius: 4px;
            padding: 2px 6px;
            color: rgb(220, 220, 225);
        }
        QColorDialog QPushButton {
            background-color: rgb(55, 55, 65);
            border: 1px solid rgb(80, 80, 90);
            border-radius: 4px;
            padding: 6px 16px;
            color: rgb(220, 220, 225);
            min-width: 70px;
        }
        QColorDialog QPushButton:hover {
            background-color: rgb(70, 70, 80);
        }
        QColorDialog QPushButton:pressed {
            background-color: rgb(45, 45, 55);
        }
        QColorDialog QGroupBox {
            border: 1px solid rgb(60, 60, 70);
            border-radius: 6px;
            margin-top: 8px;
            padding-top: 8px;
            color: rgb(200, 200, 210);
        }
        QColorDialog QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
    """
    
    @staticmethod
    def get_color(
        initial: QColor,
        parent: Optional[QWidget] = None,
        title: str = "Choose Color",
        show_alpha: bool = True,
    ) -> Optional[QColor]:
        """Show a styled color picker dialog.
        
        Args:
            initial: Initial color to display
            parent: Parent widget
            title: Dialog title
            show_alpha: Whether to show alpha channel option
            
        Returns:
            Selected QColor if user clicked OK, None if cancelled
        """
        dialog = QColorDialog(initial, parent)
        dialog.setWindowTitle(title)
        dialog.setStyleSheet(StyledColorPicker._STYLESHEET)
        
        # Set options
        options = QColorDialog.ColorDialogOption(0)
        if show_alpha:
            options |= QColorDialog.ColorDialogOption.ShowAlphaChannel
        dialog.setOptions(options)
        
        # Apply dark palette
        palette = dialog.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 35))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 225))
        palette.setColor(QPalette.ColorRole.Base, QColor(45, 45, 50))
        palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 225))
        palette.setColor(QPalette.ColorRole.Button, QColor(55, 55, 65))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 225))
        dialog.setPalette(palette)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.currentColor()
        return None
    
    @staticmethod
    def choose_color(
        current_color: QColor,
        parent: Optional[QWidget] = None,
        title: str = "Choose Color",
    ) -> QColor:
        """Convenience method that returns current color if cancelled.
        
        Args:
            current_color: Current color (returned if cancelled)
            parent: Parent widget
            title: Dialog title
            
        Returns:
            Selected QColor if user clicked OK, current_color if cancelled
        """
        result = StyledColorPicker.get_color(current_color, parent, title)
        return result if result is not None else current_color
