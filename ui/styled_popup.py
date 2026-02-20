"""
Styled popup notifications for SRPSS.

Provides dark glass themed popup dialogs that match the application's visual style.
"""
from typing import Optional, Sequence, Tuple
from PySide6.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QWidget,
    QGraphicsDropShadowEffect, QColorDialog, QFrame,
)
from PySide6.QtCore import Qt, QTimer, QPoint, Signal
from PySide6.QtGui import QColor, QPalette

from core.logging.logger import get_logger

logger = get_logger(__name__)


ButtonDef = Tuple[str, str]


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
        buttons: Optional[Sequence[ButtonDef]] = None,
        default_button_index: int = 0,
    ):
        super().__init__(parent)
        
        self._title = title
        self._message = message
        self._icon_type = icon_type
        self._auto_close_ms = auto_close_ms
        self._buttons: list[ButtonDef] = list(buttons) if buttons else [("OK", "ok")]
        self._default_button_index = min(
            max(default_button_index, 0), len(self._buttons) - 1
        )
        self._result_value: Optional[str] = None
        
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
            QTimer.singleShot(auto_close_ms, self._auto_accept)
    
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
            "question": "?",
        }
        icon_colors = {
            "info": "rgba(100, 180, 255, 255)",
            "warning": "rgba(255, 200, 80, 255)",
            "error": "rgba(255, 100, 100, 255)",
            "success": "rgba(100, 220, 140, 255)",
            "question": "rgba(180, 180, 255, 255)",
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
        
        for index, (label, value) in enumerate(self._buttons):
            button = QPushButton(label)
            button.setFixedHeight(28)
            button.setMinimumWidth(90)
            button.setStyleSheet("""
                QPushButton {
                    background-color: rgba(60, 60, 70, 200);
                    border: 1px solid rgba(100, 100, 110, 180);
                    border-radius: 4px;
                    color: rgba(240, 240, 245, 230);
                    font-size: 12px;
                    padding: 4px 16px;
                }
                QPushButton:hover {
                    background-color: rgba(80, 80, 95, 220);
                }
                QPushButton:pressed {
                    background-color: rgba(50, 50, 60, 220);
                }
            """)
            button.clicked.connect(lambda _=False, val=value: self._on_button(val))
            if index == self._default_button_index:
                button.setDefault(True)
            btn_layout.addWidget(button)
        
        btn_layout.addStretch()
        container_layout.addLayout(btn_layout)
        
        # Set minimum size
        self.setMinimumWidth(280)
        self.adjustSize()
    
    def _on_button(self, value: str) -> None:
        self._result_value = value
        self.accept()
    
    def _auto_accept(self) -> None:
        if self._result_value is None and self._buttons:
            self._result_value = self._buttons[self._default_button_index][1]
        self.accept()
    
    @property
    def result_value(self) -> Optional[str]:
        return self._result_value
    
    @staticmethod
    def show_info(
        parent: Optional[QWidget],
        title: str,
        message: str,
        auto_close_ms: int = 0,
        button_text: str = "OK",
    ) -> None:
        """Show an info popup."""
        popup = StyledPopup(
            parent,
            title,
            message,
            "info",
            auto_close_ms,
            buttons=[(button_text, "ok")],
        )
        popup.exec()
    
    @staticmethod
    def show_success(
        parent: Optional[QWidget],
        title: str,
        message: str,
        auto_close_ms: int = 0,
        button_text: str = "OK",
    ) -> None:
        """Show a success popup."""
        popup = StyledPopup(
            parent,
            title,
            message,
            "success",
            auto_close_ms,
            buttons=[(button_text, "ok")],
        )
        popup.exec()
    
    @staticmethod
    def show_warning(
        parent: Optional[QWidget],
        title: str,
        message: str,
        auto_close_ms: int = 0,
        button_text: str = "OK",
    ) -> None:
        """Show a warning popup."""
        popup = StyledPopup(
            parent,
            title,
            message,
            "warning",
            auto_close_ms,
            buttons=[(button_text, "ok")],
        )
        popup.exec()
    
    @staticmethod
    def show_error(
        parent: Optional[QWidget],
        title: str,
        message: str,
        auto_close_ms: int = 0,
        button_text: str = "OK",
    ) -> None:
        """Show an error popup."""
        popup = StyledPopup(
            parent,
            title,
            message,
            "error",
            auto_close_ms,
            buttons=[(button_text, "ok")],
        )
        popup.exec()
    
    @staticmethod
    def question(
        parent: Optional[QWidget],
        title: str,
        message: str,
        yes_text: str = "Yes",
        no_text: str = "No",
        default_to_yes: bool = True,
    ) -> bool:
        """Show a confirmation popup and return True for yes."""
        popup = StyledPopup(
            parent,
            title,
            message,
            "question",
            auto_close_ms=0,
            buttons=[(yes_text, "yes"), (no_text, "no")],
            default_button_index=0 if default_to_yes else 1,
        )
        result = popup.exec()
        return (
            result == QDialog.DialogCode.Accepted and popup.result_value == "yes"
        )


class _ColorPickerDialog(QDialog):
    """Frameless wrapper that embeds a styled QColorDialog."""

    def __init__(
        self,
        initial: QColor,
        parent: Optional[QWidget],
        title: str,
        show_alpha: bool,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("subsettingsDialog")
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self._drag_pos = QPoint()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_frame = QFrame(self)
        title_frame.setObjectName("titleFrame")
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(12, 8, 12, 8)
        title_layout.setSpacing(8)

        title_label = QLabel(title, title_frame)
        title_label.setObjectName("titleLabel")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        close_label = QLabel("×", title_frame)
        close_label.setObjectName("closeButton")
        close_label.setCursor(Qt.CursorShape.PointingHandCursor)
        close_label.mousePressEvent = lambda event: self.reject()  # type: ignore[assignment]
        title_layout.addWidget(close_label)

        title_frame.mousePressEvent = self._on_title_mouse_press  # type: ignore[assignment]
        title_frame.mouseMoveEvent = self._on_title_mouse_move  # type: ignore[assignment]

        layout.addWidget(title_frame)

        content_frame = QFrame(self)
        content_frame.setObjectName("settingsContentFrame")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(12)
        layout.addWidget(content_frame)

        self._color_dialog = QColorDialog(initial, content_frame)
        self._color_dialog.setObjectName("styledColorDialog")
        self._color_dialog.setOptions(
            self._color_dialog.options()
            | QColorDialog.ColorDialogOption.DontUseNativeDialog
        )
        if show_alpha:
            self._color_dialog.setOptions(
                self._color_dialog.options()
                | QColorDialog.ColorDialogOption.ShowAlphaChannel
            )
        self._color_dialog.setWindowFlags(Qt.WindowType.Widget)
        StyledColorPicker._apply_dark_palette(self._color_dialog)

        self._color_dialog.accepted.connect(self.accept)
        self._color_dialog.rejected.connect(self.reject)

        content_layout.addWidget(self._color_dialog)

    def selected_color(self) -> QColor:
        return self._color_dialog.currentColor()

    def _on_title_mouse_press(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def _on_title_mouse_move(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()


class ColorSwatchButton(QPushButton):
    """Burn-style colour chip with white border + drop shadow."""

    color_changed = Signal(QColor)

    _MIN_WIDTH = 78
    _MIN_HEIGHT = 26

    def __init__(
        self,
        color: Optional[QColor] = None,
        parent: Optional[QWidget] = None,
        title: str = "Choose Color",
        show_alpha: bool = True,
    ) -> None:
        super().__init__(parent)
        self._color: QColor = QColor(color) if color is not None else QColor(255, 255, 255, 255)
        self._title = title
        self._show_alpha = show_alpha
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMinimumSize(self._MIN_WIDTH, self._MIN_HEIGHT)
        self.setMaximumHeight(self._MIN_HEIGHT + 6)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 110))
        self.setGraphicsEffect(shadow)

        self._update_style()
        self.clicked.connect(self._open_picker)

    def color(self) -> QColor:
        return QColor(self._color)

    def set_color(self, color: Optional[QColor]) -> None:
        if color is None:
            return
        self._color = QColor(color)
        self._update_style()

    def _rgba(self, color: QColor) -> str:
        return f"rgba({color.red()},{color.green()},{color.blue()},{color.alpha()})"

    def _blend(self, color: QColor, target: QColor, strength: float) -> QColor:
        strength = max(0.0, min(1.0, strength))
        r = round(color.red() + (target.red() - color.red()) * strength)
        g = round(color.green() + (target.green() - color.green()) * strength)
        b = round(color.blue() + (target.blue() - color.blue()) * strength)
        a = color.alpha()
        return QColor(r, g, b, a)

    def _update_style(self) -> None:
        base = QColor(self._color)
        hover = self._blend(base, QColor(255, 255, 255, base.alpha()), 0.12)
        pressed = self._blend(base, QColor(0, 0, 0, base.alpha()), 0.12)
        self.setStyleSheet(
            f"""
            ColorSwatchButton {{
                background-color: {self._rgba(base)};
                border: 1px solid rgba(255, 255, 255, 0.95);
                border-radius: 6px;
                min-width: {self._MIN_WIDTH}px;
                min-height: {self._MIN_HEIGHT}px;
                padding: 0;
            }}
            ColorSwatchButton::hover {{
                background-color: {self._rgba(hover)};
                border-color: rgba(255, 255, 255, 1.0);
            }}
            ColorSwatchButton::pressed {{
                background-color: {self._rgba(pressed)};
                border-color: rgba(255, 255, 255, 0.75);
            }}
            """
        )

    def _open_picker(self) -> None:
        new_color = StyledColorPicker.get_color(
            self._color, self.parentWidget(), self._title, self._show_alpha
        )
        if new_color is not None:
            self._color = new_color
            self._update_style()
            self.color_changed.emit(new_color)


class StyledColorPicker:
    """Centralized styled color picker utility.
    
    Provides a consistent dark-themed color picker dialog that matches
    the application's visual style. Wraps QColorDialog with custom styling.
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
        dialog = _ColorPickerDialog(initial, parent, title, show_alpha)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_color()
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

    @staticmethod
    def _apply_dark_palette(dialog: QColorDialog) -> None:
        palette = dialog.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 35))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 225))
        palette.setColor(QPalette.ColorRole.Base, QColor(45, 45, 50))
        palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 225))
        palette.setColor(QPalette.ColorRole.Button, QColor(55, 55, 65))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 225))
        dialog.setPalette(palette)


