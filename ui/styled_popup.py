"""
Styled popup notifications for SRPSS.

Provides dark glass themed popup dialogs that match the application's visual style.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QWidget,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

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
