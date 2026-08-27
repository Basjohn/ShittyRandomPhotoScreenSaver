"""
Styled popup notifications for SRPSS.

Provides dark glass themed popup dialogs that match the application's visual style.
"""
from typing import Optional, Sequence, Tuple
from PySide6.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QWidget,
    QGraphicsDropShadowEffect, QColorDialog, QFrame,
)
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QColor, QPalette, QPainter, QPen, QBrush, QLinearGradient

from core.logging.logger import get_logger
from core.threading.manager import ThreadManager
from ui.settings_theme_runtime import get_active_settings_theme
from ui.settings_theme_spec import SettingsThemeSpec
from ui.widgets import control_shadow

logger = get_logger(__name__)


def _theme_qcolor(theme: SettingsThemeSpec, token: str) -> QColor:
    """Return one semantic popup/swatch colour as QColor."""

    value = theme.color(token)
    return QColor(*value.as_tuple())


def _theme_rgba255(theme: SettingsThemeSpec, token: str) -> str:
    """Return one semantic popup colour using Qt integer-alpha QSS."""

    value = theme.color(token)
    return f"rgba({value.r}, {value.g}, {value.b}, {value.a})"


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
            ThreadManager.single_shot(auto_close_ms, self._auto_accept)
    
    def _setup_ui(self) -> None:
        """Build the popup UI from the currently active Settings theme."""

        theme = get_active_settings_theme()

        # Main container with styling
        container = QWidget(self)
        container.setObjectName("popupContainer")
        container.setStyleSheet(
            f"""
            #popupContainer {{
                background-color: {_theme_rgba255(theme, 'popup.container.surface')};
                border: 1px solid {_theme_rgba255(theme, 'popup.container.border')};
                border-radius: 10px;
            }}
        """
        )

        # Existing popup-specific renderer; visual values are ThemeSpec-owned.
        popup_shadow = theme.shadow("popup.dialog")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(popup_shadow.blur_radius)
        shadow.setColor(QColor(*popup_shadow.color.as_tuple()))
        shadow.setOffset(popup_shadow.offset_x, popup_shadow.offset_y)
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
        icon_tokens = {
            "info": "popup.icon.info",
            "warning": "popup.icon.warning",
            "error": "popup.icon.error",
            "success": "popup.icon.success",
            "question": "popup.icon.question",
        }
        icon_token = icon_tokens.get(self._icon_type, "popup.icon.info")
        
        icon_label = QLabel(icon_map.get(self._icon_type, "ℹ"))
        icon_label.setStyleSheet(f"""
            font-size: 16px;
            color: {_theme_rgba255(theme, icon_token)};
        """)
        title_bar.addWidget(icon_label)
        
        title_label = QLabel(self._title)
        title_label.setStyleSheet(
            f"""
            font-size: 13px;
            font-weight: bold;
            color: {_theme_rgba255(theme, 'popup.title.text')};
        """
        )
        title_bar.addWidget(title_label)
        title_bar.addStretch()
        
        container_layout.addLayout(title_bar)
        
        # Message
        if self._message:
            msg_label = QLabel(self._message)
            msg_label.setTextFormat(Qt.TextFormat.RichText)
            msg_label.setWordWrap(True)
            msg_label.setStyleSheet(
                f"""
                font-size: 12px;
                color: {_theme_rgba255(theme, 'popup.message.text')};
                padding: 4px 0;
            """
            )
            container_layout.addWidget(msg_label)
        
        # OK button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        for index, (label, value) in enumerate(self._buttons):
            button = QPushButton(label)
            button.setFixedHeight(28)
            button.setMinimumWidth(90)
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {_theme_rgba255(theme, 'popup.button.surface')};
                    border: 1px solid {_theme_rgba255(theme, 'popup.button.border')};
                    border-radius: 4px;
                    color: {_theme_rgba255(theme, 'popup.button.text')};
                    font-size: 12px;
                    padding: 4px 16px;
                }}
                QPushButton:hover {{
                    background-color: {_theme_rgba255(theme, 'popup.button.hover_surface')};
                }}
                QPushButton:pressed {{
                    background-color: {_theme_rgba255(theme, 'popup.button.pressed_surface')};
                }}
            """
            )
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
        # The wrapper is frameless, so let its rounded child frames define the
        # visible outline instead of leaving an opaque rectangular backing.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
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
        picker_theme = get_active_settings_theme()
        picker_window = _theme_qcolor(picker_theme, "color_picker.window")
        picker_window_qss = _theme_rgba255(picker_theme, "color_picker.window")

        # Legacy dark.qss deliberately makes generic subsettings content
        # transparent. This picker owns its body, so override only this frame;
        # QColorDialog descendants remain palette/Qt-owned.
        content_frame.setStyleSheet(
            "QFrame#settingsContentFrame {"
            f" background-color: {picker_window_qss};"
            " border: none;"
            " border-bottom-left-radius: 10px;"
            " border-bottom-right-radius: 10px;"
            " margin: 0 2px 2px 2px;"
            " }"
        )
        content_palette = content_frame.palette()
        content_palette.setColor(QPalette.ColorRole.Window, picker_window)
        content_frame.setPalette(content_palette)
        content_frame.setAutoFillBackground(True)
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
    """Burn-style colour chip using the central semantic button cast."""

    color_changed = Signal(QColor)

    _MIN_WIDTH = 78
    _MIN_HEIGHT = 34

    def __init__(
        self,
        color: Optional[QColor] = None,
        parent: Optional[QWidget] = None,
        title: str = "Choose Color",
        show_alpha: bool = True,
        auto_picker: bool = True,
    ) -> None:
        super().__init__(parent)
        self._color: QColor = QColor(color) if color is not None else QColor(255, 255, 255, 255)
        self._title = title
        self._show_alpha = show_alpha
        self._auto_picker = auto_picker
        self._hovered = False
        self._pressed = False

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setMinimumSize(self._MIN_WIDTH, self._MIN_HEIGHT)
        self.setMaximumHeight(self._MIN_HEIGHT + 4)
        self.setStyleSheet("border: none; background: transparent; margin-bottom: 0px;")

        control_shadow.attach_control_shadow(
            self,
            control_shadow.PILL_BUTTON_SHADOW,
            replace_existing=True,
        )

        if self._auto_picker:
            self.clicked.connect(self._open_picker)

    def color(self) -> QColor:
        return QColor(self._color)

    def set_color(self, color: Optional[QColor]) -> None:
        if color is None:
            return
        self._color = QColor(color)
        self.update()

    # ----- state handling -------------------------------------------------
    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = False
            self.update()
        super().mouseReleaseEvent(event)

    # ----- painting -------------------------------------------------------
    def _current_fill(self) -> QColor:
        base = QColor(self._color)
        if not self.isEnabled():
            base.setAlpha(int(base.alpha() * 0.4))
            return base

        theme = get_active_settings_theme()
        if self._pressed:
            target = _theme_qcolor(theme, "swatch.pressed_mix")
            target.setAlpha(base.alpha())
            return self._blend(base, target, 0.18)
        if self._hovered:
            target = _theme_qcolor(theme, "swatch.hover_mix")
            target.setAlpha(base.alpha())
            return self._blend(base, target, 0.12)
        return base

    def _blend(self, color: QColor, target: QColor, strength: float) -> QColor:
        strength = max(0.0, min(1.0, strength))
        r = round(color.red() + (target.red() - color.red()) * strength)
        g = round(color.green() + (target.green() - color.green()) * strength)
        b = round(color.blue() + (target.blue() - color.blue()) * strength)
        a = color.alpha()
        return QColor(r, g, b, a)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        outer = self.rect().adjusted(2, 2, -2, -2)
        radius = 7

        fill = self._current_fill()
        painter.setBrush(QBrush(fill))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(outer, radius, radius)

        theme = get_active_settings_theme()

        # Inner accent for contrast (helps white colours stand out)
        inner = outer.adjusted(1, 1, -1, -1)
        gradient = QLinearGradient(inner.topLeft(), inner.bottomLeft())
        gradient.setColorAt(0, _theme_qcolor(theme, "swatch.inner_highlight"))
        gradient.setColorAt(1, _theme_qcolor(theme, "swatch.inner_shade"))
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(inner, radius - 1, radius - 1)

        # Border + inner stroke depending on luminance
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(_theme_qcolor(theme, "swatch.border"), 1))
        painter.drawRoundedRect(outer, radius, radius)

        lum = 0.299 * fill.red() + 0.587 * fill.green() + 0.114 * fill.blue()
        accent_token = "swatch.dark_accent" if lum > 180 else "swatch.light_accent"
        painter.setPen(QPen(_theme_qcolor(theme, accent_token), 1))
        painter.drawRoundedRect(inner.adjusted(1, 1, -1, -1), radius - 2, radius - 2)

        painter.end()

    # ----- picker ---------------------------------------------------------
    def _open_picker(self) -> None:
        new_color = StyledColorPicker.get_color(
            self._color, self.parentWidget(), self._title, self._show_alpha
        )
        if new_color is not None:
            self._color = new_color
            self.update()
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
        theme = get_active_settings_theme()
        palette = dialog.palette()
        palette.setColor(
            QPalette.ColorRole.Window,
            _theme_qcolor(theme, "color_picker.window"),
        )
        palette.setColor(
            QPalette.ColorRole.WindowText,
            _theme_qcolor(theme, "color_picker.window_text"),
        )
        palette.setColor(
            QPalette.ColorRole.Base,
            _theme_qcolor(theme, "color_picker.base"),
        )
        palette.setColor(
            QPalette.ColorRole.Text,
            _theme_qcolor(theme, "color_picker.text"),
        )
        palette.setColor(
            QPalette.ColorRole.Button,
            _theme_qcolor(theme, "color_picker.button"),
        )
        palette.setColor(
            QPalette.ColorRole.ButtonText,
            _theme_qcolor(theme, "color_picker.button_text"),
        )
        dialog.setPalette(palette)
        # Qt's non-native QColorDialog does not consistently paint its empty
        # body from QPalette.Window on Windows. Restrict this selector to the
        # dialog object itself so the actual colour wells/sliders remain Qt-owned.
        window = theme.color("color_picker.window")
        dialog.setStyleSheet(
            "QColorDialog#styledColorDialog {"
            f" background-color: rgba({window.r}, {window.g}, {window.b}, {window.a});"
            " }"
        )
        dialog.setAutoFillBackground(True)


