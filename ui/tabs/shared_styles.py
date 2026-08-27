"""Shared QSS styles and widgets for settings dialog tabs.

Centralises repeated styling blocks and common widgets so individual tabs
don't duplicate them.
"""
import re
import weakref
from typing import Callable

try:
    import shiboken6

    Shiboken = shiboken6.Shiboken
except Exception:  # pragma: no cover - PySide test/import fallback
    Shiboken = None  # type: ignore[assignment]

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QSlider,
    QToolButton,
    QSizePolicy,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QStyle,
    QStyleOptionSlider,
)

from ui.settings_theme_runtime import (
    get_active_settings_theme,
    subscribe_settings_theme,
)
from ui.settings_theme_spec import SettingsThemeSpec

# Ensure UI resources (e.g., circle checkbox SVGs) are registered even when
# shared_styles is imported before ui/__init__.py. Safe no-op if already loaded.
try:  # pragma: no cover - defensive import
    from ui.resources import assets_rc  # noqa: F401
except Exception:  # pragma: no cover - fallback when resources unavailable
    assets_rc = None  # type: ignore


_JOST_FONT_PATHS = (
    ":/ui/assets/fonts/Jost-Regular.ttf",
    ":/ui/assets/fonts/Jost-SemiBold.ttf",
    ":/ui/assets/fonts/Jost-Bold.ttf",
)
_INTER_FONT_PATHS = (
    ":/ui/assets/fonts/Inter-VariableFont_opsz,wght.ttf",
    ":/ui/assets/fonts/Inter-Italic-VariableFont_opsz,wght.ttf",
)
_FONTS_REGISTERED = False

_LIVE_GROUP_BOXES: weakref.WeakSet = weakref.WeakSet()
_LIVE_RECOMMENDED_SLIDERS: weakref.WeakSet = weakref.WeakSet()
_LIVE_STYLED_LABELS: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_LIVE_STYLE_BUNDLES: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


_SETTINGS_THEME = get_active_settings_theme()

_THEME_QSS_TOKEN_RE = re.compile(
    r"@@(?P<mode>hex|rgba|rgba255|gradient):(?P<token>[a-zA-Z0-9_.-]+)@@"
)


def _theme_qcolor(
    token: str,
    theme: SettingsThemeSpec | None = None,
) -> QColor:
    """Return one semantic theme colour as QColor for custom painters."""

    resolved_theme = theme or _SETTINGS_THEME
    value = resolved_theme.color(token)
    return QColor(*value.as_tuple())


def _theme_hex(token: str) -> str:
    """Render an opaque semantic colour in the same QSS form used historically."""

    value = _SETTINGS_THEME.color(token)
    if value.a != 255:
        raise ValueError(f"Theme colour {token!r} is not opaque")
    return f"#{value.r:02x}{value.g:02x}{value.b:02x}"


def _unit_alpha_text(alpha: int) -> str:
    """Preserve familiar QSS alpha spellings without losing arbitrary 8-bit values."""

    # Existing shared_styles.py commonly used compact unit alpha values such as
    # 0.95, 0.45 and 0.6. Prefer that spelling when it round-trips to the exact
    # 8-bit alpha; otherwise retain precision for future user-authored themes.
    unit = alpha / 255.0
    compact = round(unit, 2)
    if int(compact * 255.0 + 0.5) == alpha:
        text = f"{compact:.2f}".rstrip("0").rstrip(".")
        return text if "." in text else f"{text}.0"
    return f"{unit:.6f}".rstrip("0").rstrip(".")


def _theme_rgba(token: str) -> str:
    """Render a semantic colour using the normalized-alpha QSS form."""

    value = _SETTINGS_THEME.color(token)
    return (
        f"rgba({value.r}, {value.g}, {value.b}, "
        f"{_unit_alpha_text(value.a)})"
    )


def _theme_rgba255(token: str) -> str:
    """Render a semantic colour using Qt's integer-alpha QSS form."""

    value = _SETTINGS_THEME.color(token)
    return f"rgba({value.r}, {value.g}, {value.b}, {value.a})"


def _theme_gradient(token: str) -> str:
    """Render only gradient stops; direction and geometry remain component-owned."""

    parts: list[str] = []
    for stop in _SETTINGS_THEME.gradient(token).stops:
        position = f"{stop.position:g}"
        color = stop.color
        if color.a == 255:
            rendered = f"#{color.r:02x}{color.g:02x}{color.b:02x}"
        else:
            rendered = (
                f"rgba({color.r}, {color.g}, {color.b}, "
                f"{_unit_alpha_text(color.a)})"
            )
        parts.append(f"stop:{position} {rendered}")
    return ",\n        ".join(parts)


def _theme_qss(template: str) -> str:
    """Resolve semantic colour placeholders while leaving QSS structure untouched."""

    def replace(match: re.Match[str]) -> str:
        mode = match.group("mode")
        token = match.group("token")
        if mode == "hex":
            return _theme_hex(token)
        if mode == "rgba":
            return _theme_rgba(token)
        if mode == "rgba255":
            return _theme_rgba255(token)
        if mode == "gradient":
            return _theme_gradient(token)
        raise AssertionError(f"Unhandled theme QSS mode: {mode}")

    resolved = _THEME_QSS_TOKEN_RE.sub(replace, template)
    if "@@" in resolved:
        raise ValueError("Unresolved Settings theme QSS placeholder")
    return resolved


def _ensure_fonts_registered() -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    if QApplication.instance() is None:
        return
    for path in _JOST_FONT_PATHS:
        QFontDatabase.addApplicationFont(path)
    for path in _INTER_FONT_PATHS:
        QFontDatabase.addApplicationFont(path)
    _FONTS_REGISTERED = True


def ensure_custom_fonts() -> None:
    _ensure_fonts_registered()


FORM_LABEL_HEIGHT = 34
SWATCH_LABEL_HEIGHT = 34
LABEL_WIDTH = 140

_last_moved_slider: weakref.ref | None = None


def _is_live_qobject(obj) -> bool:
    """Return whether a PySide wrapper still owns a live C++ QObject."""

    if obj is None:
        return False
    if Shiboken is None:
        return True
    try:
        return bool(Shiboken.isValid(obj))
    except RuntimeError:
        return False


def _build_form_label_style() -> str:
    return (
        "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
        "font-weight: 600;"
        "font-size: 14px;"
        "letter-spacing: 0.4px;"
        f"color: {_theme_hex('text.primary')};"
        f"min-height: {FORM_LABEL_HEIGHT}px;"
        "line-height: 34px;"
        "padding-top: 0px;"
        "padding-bottom: 1px;"
        "margin-top: -1px;"
        "margin-bottom: 0px;"
        "qproperty-alignment: AlignVCenter;"
    )


FORM_LABEL_STYLE = _build_form_label_style()

def _build_form_row_label_style() -> str:
    return (
        "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
        "font-weight: 500;"
        "font-size: 14px;"
        "letter-spacing: 0.35px;"
        f"color: {_theme_hex('text.primary')};"
        f"min-height: {FORM_LABEL_HEIGHT}px;"
        "line-height: 34px;"
        "padding-top: 0px;"
        "padding-bottom: 1px;"
        "margin-top: -1px;"
        "margin-bottom: 0px;"
        "qproperty-alignment: AlignVCenter;"
    )


FORM_ROW_LABEL_STYLE = _build_form_row_label_style()

def _build_form_label_style_disabled() -> str:
    return (
        "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
        "font-weight: 600;"
        "font-size: 14px;"
        "letter-spacing: 0.35px;"
        f"color: {_theme_hex('text.disabled')};"
        f"min-height: {FORM_LABEL_HEIGHT}px;"
        "line-height: 34px;"
        "padding-top: 0px;"
        "padding-bottom: 1px;"
        "margin-top: -1px;"
        "margin-bottom: 0px;"
        "qproperty-alignment: AlignVCenter;"
    )


FORM_LABEL_STYLE_DISABLED = _build_form_label_style_disabled()

def _build_form_row_label_style_disabled() -> str:
    return (
        "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
        "font-weight: 500;"
        "font-size: 14px;"
        "letter-spacing: 0.35px;"
        f"color: {_theme_hex('text.disabled')};"
        f"min-height: {FORM_LABEL_HEIGHT}px;"
        "line-height: 34px;"
        "padding-top: 0px;"
        "padding-bottom: 1px;"
        "margin-top: -1px;"
        "margin-bottom: 0px;"
        "qproperty-alignment: AlignVCenter;"
    )


FORM_ROW_LABEL_STYLE_DISABLED = _build_form_row_label_style_disabled()


_SHARED_LABEL_STYLE_ROLES = (
    "FORM_LABEL_STYLE",
    "FORM_ROW_LABEL_STYLE",
    "FORM_LABEL_STYLE_DISABLED",
    "FORM_ROW_LABEL_STYLE_DISABLED",
    "PAGE_TITLE_STYLE",
    "SECTION_HEADING_STYLE",
    "SECTION_HEADING_STYLE_DISABLED",
    "SWATCH_LABEL_STYLE",
    "INFO_LABEL_STYLE",
    "ADV_HELPER_LABEL_STYLE",
    "INFO_LABEL_STYLE_DISABLED",
    "ACCESSIBILITY_TITLE_STYLE",
    "ACCESSIBILITY_DESC_STYLE",
    "ACCESSIBILITY_SECTION_DESC_STYLE",
)


def _shared_label_style_role(style_sheet: str) -> str | None:
    """Identify a current shared label style when the mapping is unambiguous."""

    matches = [
        name
        for name in _SHARED_LABEL_STYLE_ROLES
        if globals().get(name) == style_sheet
    ]
    return matches[0] if len(matches) == 1 else None


def _remember_live_label(label: QLabel, role: str | None) -> None:
    """Track only labels whose full style is owned by shared_styles.py."""

    if role is None:
        _LIVE_STYLED_LABELS.pop(label, None)
        return
    _LIVE_STYLED_LABELS[label] = role


def apply_shared_label_style(label: QLabel, role: str) -> None:
    """Apply and live-bind one shared label style without changing geometry."""

    style_sheet = globals().get(role)
    if not isinstance(style_sheet, str) or role not in _SHARED_LABEL_STYLE_ROLES:
        raise KeyError(f"Unknown shared label style role: {role!r}")
    label.setStyleSheet(style_sheet)
    _remember_live_label(label, role)


def _render_shared_style_bundle(
    base_style: str,
    style_roles: tuple[str, ...],
    trailing_style: str = "",
) -> str:
    """Compose current shared roles between stable local prefix/suffix QSS."""

    parts = [base_style]
    for role in style_roles:
        style_sheet = globals().get(role)
        if not isinstance(style_sheet, str):
            raise KeyError(f"Unknown shared style role: {role!r}")
        parts.append(style_sheet)
    parts.append(trailing_style)
    return "".join(parts)


def bind_shared_styles(
    widget: QWidget,
    *style_roles: str,
    base_style: str | None = None,
    trailing_style: str = "",
) -> None:
    """Apply shared style roles and keep the same widget bundle live.

    ``base_style`` defaults to the widget's stylesheet before the first shared
    bundle is attached. ``trailing_style`` is reapplied after the live shared
    roles so deliberate local overrides keep their historical precedence.
    Rebinding the same widget reuses the original base and cannot accumulate
    duplicate QSS.
    """

    if not style_roles:
        raise ValueError("At least one shared style role is required")
    existing = _LIVE_STYLE_BUNDLES.get(widget)
    if base_style is None:
        resolved_base = existing[0] if existing is not None else widget.styleSheet()
    else:
        resolved_base = str(base_style)
    roles = tuple(style_roles)
    resolved_trailing = str(trailing_style)
    rendered = _render_shared_style_bundle(
        resolved_base,
        roles,
        resolved_trailing,
    )
    _LIVE_STYLE_BUNDLES[widget] = (
        resolved_base,
        roles,
        resolved_trailing,
    )
    widget.setStyleSheet(rendered)


def apply_section_heading_style(
    label: QLabel,
    *,
    disabled: bool = False,
    style: str | None = None,
    height: int | None = None,
    lock_height: bool = True,
) -> None:
    """Normalize section heading labels so they align with adjacent controls."""

    ensure_custom_fonts()
    if style is None:
        style_role = (
            "FORM_LABEL_STYLE_DISABLED" if disabled else "FORM_LABEL_STYLE"
        )
        style_sheet = globals()[style_role]
    else:
        style_sheet = style
        style_role = _shared_label_style_role(style_sheet)
    label.setStyleSheet(style_sheet)
    _remember_live_label(label, style_role)
    target_height = height if height is not None else FORM_LABEL_HEIGHT
    if lock_height:
        label.setFixedHeight(target_height)
        label.setWordWrap(False)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    else:
        label.setMinimumHeight(target_height)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)


def create_section_label(
    text: str,
    width: int | None = None,
    *,
    disabled: bool = False,
    style: str | None = None,
    height: int | None = None,
    lock_height: bool = True,
) -> QLabel:
    label = QLabel(text)
    if width is not None:
        label.setFixedWidth(width)
    apply_section_heading_style(
        label,
        disabled=disabled,
        style=style,
        height=height,
        lock_height=lock_height,
    )
    return label


def add_section_label(
    layout,
    text: str,
    width: int | None = None,
    *,
    disabled: bool = False,
    style: str | None = None,
    height: int | None = None,
    wrap: bool = True,
) -> QLabel:
    if style is None:
        style = FORM_ROW_LABEL_STYLE_DISABLED if disabled else FORM_ROW_LABEL_STYLE
    label = create_section_label(
        text,
        width,
        disabled=disabled,
        style=style,
        height=height,
        lock_height=not wrap,
    )
    layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignVCenter)
    return label


def add_swatch_label(
    layout,
    text: str,
    width: int | None = None,
) -> QLabel:
    return add_section_label(
        layout,
        text,
        width,
        style=SWATCH_LABEL_STYLE,
        height=SWATCH_LABEL_HEIGHT,
        wrap=False,
    )


def add_aligned_row_widget(
    parent_layout: QVBoxLayout,
    label_text: str,
    *,
    label_width: int | None = LABEL_WIDTH,
    wrap: bool = True,
    margins: tuple[int, int, int, int] = (0, 8, 0, 8),
    spacing: int = 12,
    content_margins: tuple[int, int, int, int] = (0, 0, 0, 0),
    content_spacing: int = 12,
) -> tuple[QWidget, QHBoxLayout, QLabel]:
    """Add a form row widget with shared spacing + wrap-aware label."""

    row_widget = QWidget()
    row_layout = QHBoxLayout(row_widget)
    row_layout.setContentsMargins(*margins)
    row_layout.setSpacing(spacing)
    label = add_section_label(row_layout, label_text, label_width, wrap=wrap)
    content_layout = QHBoxLayout()
    content_layout.setContentsMargins(*content_margins)
    content_layout.setSpacing(content_spacing)
    row_layout.addLayout(content_layout, 1)
    parent_layout.addWidget(row_widget)
    return row_widget, content_layout, label


def add_aligned_row(
    parent_layout: QVBoxLayout,
    label_text: str,
    *,
    label_width: int | None = LABEL_WIDTH,
    wrap: bool = True,
    margins: tuple[int, int, int, int] = (0, 8, 0, 8),
    spacing: int = 12,
    content_margins: tuple[int, int, int, int] = (0, 0, 0, 0),
    content_spacing: int = 12,
) -> tuple[QHBoxLayout, QLabel]:
    """Convenience wrapper returning just the content row + label."""

    _, content_layout, label = add_aligned_row_widget(
        parent_layout,
        label_text,
        label_width=label_width,
        wrap=wrap,
        margins=margins,
        spacing=spacing,
        content_margins=content_margins,
        content_spacing=content_spacing,
    )
    return content_layout, label


def create_inline_label(
    text: str,
    *,
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft
    | Qt.AlignmentFlag.AlignVCenter,
    minimum_width: int | None = None,
) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(FORM_ROW_LABEL_STYLE)
    _remember_live_label(label, "FORM_ROW_LABEL_STYLE")
    if minimum_width is not None:
        label.setMinimumWidth(minimum_width)
    label.setAlignment(alignment)
    return label


class NoWheelSlider(QSlider):
    """Slider that ignores mouse wheel events to prevent accidental changes.

    Also tracks the most-recently-moved slider via a module-level weakref
    so the QSS ``QSlider[lastMoved="true"]`` selector highlights its handle.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setProperty("lastMoved", False)
        self.sliderPressed.connect(self._mark_last_moved)
        self.valueChanged.connect(self._mark_last_moved)
        self.destroyed.connect(self._clear_last_moved_ref)

    def _clear_last_moved_ref(self, *_args) -> None:
        global _last_moved_slider
        if _last_moved_slider is not None and _last_moved_slider() is self:
            _last_moved_slider = None

    @staticmethod
    def _set_last_moved_state(slider: "NoWheelSlider", value: bool) -> None:
        if not _is_live_qobject(slider):
            return
        slider.setProperty("lastMoved", value)
        slider.style().unpolish(slider)
        slider.style().polish(slider)

    def _mark_last_moved(self, *_args) -> None:
        global _last_moved_slider
        if not _is_live_qobject(self):
            _last_moved_slider = None
            return
        prev = _last_moved_slider() if _last_moved_slider is not None else None
        if prev is self:
            return
        if prev is not None and _is_live_qobject(prev):
            self._set_last_moved_state(prev, False)
        elif prev is not None:
            _last_moved_slider = None
        self._set_last_moved_state(self, True)
        _last_moved_slider = weakref.ref(self)

    def wheelEvent(self, event):  # type: ignore[override]
        event.ignore()


class RecommendedMarkSlider(NoWheelSlider):
    """Slider with a subtle recommended-position marker painted on the groove."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._recommended_value: int | None = None
        self._recommended_color_uses_theme = True
        self._recommended_color = _theme_qcolor("slider.recommended_mark")
        _LIVE_RECOMMENDED_SLIDERS.add(self)

    def set_recommended_value(self, value: int | None) -> None:
        target = None if value is None else int(value)
        if self._recommended_value == target:
            return
        self._recommended_value = target
        self.update()

    def recommended_value(self) -> int | None:
        return self._recommended_value

    def set_recommended_color(self, color: QColor) -> None:
        next_color = QColor(color)
        self._recommended_color_uses_theme = False
        if next_color == self._recommended_color:
            return
        self._recommended_color = next_color
        self.update()

    def _refresh_theme_marker(self, theme: SettingsThemeSpec) -> None:
        if not self._recommended_color_uses_theme:
            return
        next_color = _theme_qcolor("slider.recommended_mark", theme)
        if next_color == self._recommended_color:
            return
        self._recommended_color = next_color
        self.update()

    def paintEvent(self, event):  # type: ignore[override]
        super().paintEvent(event)
        if self._recommended_value is None:
            return
        if self.orientation() != Qt.Orientation.Horizontal:
            return
        minimum = int(self.minimum())
        maximum = int(self.maximum())
        if maximum <= minimum:
            return

        option = QStyleOptionSlider()
        self.initStyleOption(option)
        groove = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderGroove,
            self,
        )
        handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderHandle,
            self,
        )
        if groove.isNull() or handle.isNull():
            return

        span = max(1, groove.width() - handle.width())
        ratio = (self._recommended_value - minimum) / float(maximum - minimum)
        ratio = max(0.0, min(1.0, ratio))
        center_x = groove.left() + handle.width() * 0.5 + span * ratio
        groove_mid_y = groove.center().y()
        marker_height = max(5.0, groove.height() + 8.0)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(self._recommended_color)
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(
            int(round(center_x)),
            int(round(groove_mid_y - marker_height * 0.5)),
            int(round(center_x)),
            int(round(groove_mid_y + marker_height * 0.5)),
        )
        painter.end()

def _build_spinbox_style() -> str:
    return _theme_qss("""
    /* Rounded inputs with opaque borders + circular stepper controls */
    QSpinBox, QDoubleSpinBox, QLineEdit, QAbstractSpinBox {
        min-height: 34px;
        padding: 4px 48px 4px 16px;
        margin-bottom: 0px;
        color: @@hex:control.input.text@@;
        font-family: 'Jost';
        font-weight: 600;
        background-color: @@hex:control.input.surface@@;
        border: 2px solid @@hex:control.input.border@@;
        border-radius: 18px;
    }
    
    QSpinBox > QLineEdit,
    QDoubleSpinBox > QLineEdit,
    QAbstractSpinBox > QLineEdit {
        background-color: @@hex:control.input.surface@@;
        border: none;
        padding: 0px;
        margin: 0px;
    }
    
    QLineEdit {
        padding-right: 16px;
    }
    
    QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover, QAbstractSpinBox:hover {
        border-color: @@hex:control.input.border@@;
    }
    
    QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QAbstractSpinBox:focus {
        border-color: @@hex:control.input.border@@;
    }
    
    QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled, QAbstractSpinBox:disabled {
        color: @@rgba:control.input.disabled_text@@;
        border-color: @@hex:control.input.disabled_border@@;
        background-color: @@hex:control.input.surface@@;
    }
    
    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {
        subcontrol-origin: border;
        subcontrol-position: right;
        width: 10px;
        height: 10px;
        margin: 4px 14px 4px 0px;
        padding: 0px;
        border: none;
        border-radius: 5px;
        background-color: @@hex:control.stepper.surface@@;
    }
    
    QSpinBox::up-button, QDoubleSpinBox::up-button {
        subcontrol-position: top right;
        margin-top: 7.5px;
        margin-bottom: -3.5px;
    }
    
    QSpinBox::down-button, QDoubleSpinBox::down-button {
        subcontrol-position: bottom right;
        margin-top: -3.5px;
        margin-bottom: 7.5px;
    }
    
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
        background-color: @@hex:control.stepper.hover_surface@@;
    }
    
    QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
    QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
        background-color: @@hex:control.stepper.pressed_surface@@;
    }
    
    QSpinBox::up-button:disabled, QDoubleSpinBox::up-button:disabled,
    QSpinBox::down-button:disabled, QDoubleSpinBox::down-button:disabled {
        background-color: @@hex:control.stepper.disabled_surface@@;
    }
    
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
        width: 0px;
        height: 0px;
        border: none;
    }
    """)


SPINBOX_STYLE = _build_spinbox_style()

CIRCLE_CHECKBOX_STYLE = """
/* Circular indicator prototype (feature flag via `circleIndicator` dynamic property). */
QCheckBox[circleIndicator='true'] {
    spacing: 10px;
    padding: 4px 16px 4px 6px;
    min-height: 34px;
}

QCheckBox[circleIndicator='true'][tightSpacing='true'] {
    spacing: 6px;
    padding: 4px 12px 4px 0px;
    min-height: 34px;
}

QCheckBox[circleIndicator='true']::indicator {
    width: 22px;
    height: 22px;
    border-radius: 11px;
    margin: 6px 12px 6px 0px;
    border: none;
    background: transparent;
    image: none;
}

QCheckBox[circleIndicator='true'][tightSpacing='true']::indicator {
    margin: 5px 9px 5px 0px;
}

QCheckBox[circleIndicator='true']::indicator:unchecked {
    image: url(:/ui/assets/circle_checkbox_unchecked.svg);
}

QCheckBox[circleIndicator='true']::indicator:unchecked:hover {
    image: url(:/ui/assets/circle_checkbox_unchecked_hover.svg);
}

QCheckBox[circleIndicator='true']::indicator:checked {
    image: url(:/ui/assets/circle_checkbox_checked.svg);
}

QCheckBox[circleIndicator='true']::indicator:checked:hover {
    image: url(:/ui/assets/circle_checkbox_checked_hover.svg);
}

QCheckBox[circleIndicator='true']::indicator:disabled {
    image: url(:/ui/assets/circle_checkbox_unchecked.svg);
}

QCheckBox[circleIndicator='true']::indicator:disabled:checked {
    image: url(:/ui/assets/circle_checkbox_checked.svg);
}
"""


def _build_combobox_style() -> str:
    return _theme_qss("""
    /* StyledComboBox base skin */
    QComboBox[customCombo='true'] {
        min-height: 34px;
        padding: 4px 56px 4px 18px;
        margin-top: 1px;
        margin-bottom: 10px;
        font-family: 'Jost';
        font-weight: 700;
        font-size: 14px;
        letter-spacing: 0.4px;
        color: @@hex:control.input.text@@;
        border: 2px solid @@hex:control.input.border@@;
        border-radius: 18px;
        background-color: @@hex:control.input.surface@@;
    }
    
    QComboBox[customCombo='true']:hover {
        background-color: @@hex:control.input.hover_surface@@;
    }
    
    QComboBox[customCombo='true']:focus,
    QComboBox[customCombo='true']:on {
        background-color: @@hex:control.input.focus_surface@@;
        border-color: @@hex:control.input.border@@;
        outline: none;
    }
    
    QComboBox[customCombo='true']:disabled {
        color: @@rgba:control.input.disabled_text@@;
        border-color: @@hex:control.input.disabled_border@@;
        background-color: @@hex:control.input.surface@@;
    }
    
    QComboBox[customCombo='true']::drop-down,
    QComboBox[customCombo='true']::down-arrow {
        width: 0px;
        border: none;
        background: transparent;
        image: none;
        margin: 0px;
        padding: 0px;
    }
    
    QComboBox[customCombo='true'][comboSize='regular'] {
        min-width: 188px;
        min-height: 38px;
        padding: 4px 60px 4px 18px;
        border-radius: 20px;
        margin-top: 1px;
        margin-bottom: 10px;
    }
    
    QComboBox[customCombo='true'][comboSize='compact'] {
        min-width: 164px;
        min-height: 34px;
        padding: 3px 52px 3px 16px;
        border-radius: 17px;
        font-size: 13px;
        margin-top: 2px;
        margin-bottom: 12px;
    }
    
    QComboBox[customCombo='true'][comboSize='mini'] {
        min-width: 136px;
        min-height: 32px;
        padding: 2px 46px 2px 14px;
        border-radius: 16px;
        font-size: 12px;
        margin-top: 2px;
        margin-bottom: 12px;
    }
    
    QComboBox[customCombo='true'][comboSize='hero'] {
        min-width: 198px;
        max-width: 306px;
        min-height: 38px;
        padding: 3px 54px 5px 20px;
        border-radius: 20px;
        font-size: 14px;
        margin-top: 1px;
        margin-bottom: 10px;
    }
    """)


COMBOBOX_STYLE = _build_combobox_style()

def _build_combobox_popup_view_style() -> str:
    return _theme_qss("""
    QListView[customComboPopup='true'],
    QListWidget[customComboPopup='true'] {
        background-color: @@rgba:combo.popup.surface@@;
        border: 2px solid @@hex:combo.popup.border@@;
        border-radius: 14px;
        padding: 8px 8px 12px 8px;
        outline: none;
        selection-background-color: @@rgba:combo.popup.selection_surface@@;
        selection-color: @@hex:combo.popup.selection_text@@;
        color: @@hex:combo.popup.text@@;
        font-family: 'Jost';
        font-weight: 600;
        font-size: 14px;
        letter-spacing: 0.4px;
    }
    
    QListView[customComboPopup='true']::item,
    QListWidget[customComboPopup='true']::item {
        padding: 4px 6px;
        min-height: 22px;
        margin: 0px 2px;
        border-radius: 8px;
        background: transparent;
    }
    """)


COMBOBOX_POPUP_VIEW_STYLE = _build_combobox_popup_view_style()

def _build_tooltip_style() -> str:
    return _theme_qss("""
    QToolTip {
        background-color: @@hex:tooltip.surface@@;
        color: @@hex:tooltip.text@@;
        border: 1px solid @@hex:tooltip.border@@;
        padding: 6px;
        font-size: 12px;
    }
    """)


TOOLTIP_STYLE = _build_tooltip_style()

def _build_page_title_style() -> str:
    return (
        "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
        "font-weight: 700;"
        "font-size: 18px;"
        "letter-spacing: 0.5px;"
        f"color: {_theme_hex('text.primary')};"
    )


PAGE_TITLE_STYLE = _build_page_title_style()

def _build_section_heading_style() -> str:
    return (
        "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
        "font-weight: 800;"
        "font-size: 15px;"
        "letter-spacing: 0.6px;"
        f"color: {_theme_hex('text.primary')};"
        f"min-height: {FORM_LABEL_HEIGHT + 6}px;"
        "line-height: 36px;"
        "padding-top: 0px;"
        "padding-bottom: 2px;"
        "margin-top: -6px;"
        "margin-bottom: 12px;"
        "qproperty-alignment: AlignVCenter;"
    )


SECTION_HEADING_STYLE = _build_section_heading_style()

def _build_section_heading_style_disabled() -> str:
    return (
        "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
        "font-weight: 800;"
        "font-size: 15px;"
        "letter-spacing: 0.6px;"
        f"color: {_theme_hex('text.disabled')};"
        f"min-height: {FORM_LABEL_HEIGHT + 6}px;"
        "line-height: 36px;"
        "padding-top: 0px;"
        "padding-bottom: 2px;"
        "margin-top: -6px;"
        "margin-bottom: 12px;"
        "qproperty-alignment: AlignVCenter;"
    )


SECTION_HEADING_STYLE_DISABLED = _build_section_heading_style_disabled()

def _build_swatch_label_style() -> str:
    return (
        "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
        "font-weight: 500;"
        "font-size: 13px;"
        "letter-spacing: 0.4px;"
        f"color: {_theme_hex('text.primary')};"
        f"min-height: {SWATCH_LABEL_HEIGHT}px;"
        "line-height: 34px;"
        "padding-top: 0px;"
        "padding-bottom: 0px;"
        "margin-top: 0px;"
        "margin-bottom: 0px;"
        "qproperty-alignment: AlignVCenter;"
    )


SWATCH_LABEL_STYLE = _build_swatch_label_style()

def _build_subsection_divider_style() -> str:
    return (
        f"background-color: {_theme_rgba255('panel.subsection.surface')};"
        f"border: 2px solid {_theme_hex('panel.border')};"
        "border-radius: 19px;"
    )


SUBSECTION_DIVIDER_STYLE = _build_subsection_divider_style()


def style_group_box(box) -> None:
    """Apply the subsection border + title style to a QGroupBox."""

    _LIVE_GROUP_BOXES.add(box)
    box.setStyleSheet(
        (
            f"QGroupBox {{{SUBSECTION_DIVIDER_STYLE}}}"
            "QGroupBox::title {"
            "  subcontrol-origin: margin;"
            "  subcontrol-position: top left;"
            "  padding: 2px 10px;"
            "  margin-top: 5px;"
            f"  color: {_theme_hex('text.primary')};"
            "  font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
            "  font-weight: 800;"
            "  font-size: 16px;"
            "  letter-spacing: 0.6px;"
            "}"
        )
    )

NAV_TAB_FONT_STYLE = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 600;"
    "font-size: 13px;"
    "letter-spacing: 0.4px;"
)

NAV_TAB_FONT_STYLE_ACTIVE = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 700;"
    "font-size: 13px;"
    "letter-spacing: 0.5px;"
)


def _build_nav_pill_style() -> str:
    """Theme-aware checkable pill used for Settings sub-navigation."""

    return (
        "QPushButton {"
        f" {NAV_TAB_FONT_STYLE}"
        f" background-color: {_theme_rgba255('control.button.surface')};"
        f" color: {_theme_hex('control.button.text')};"
        f" border: 1px solid {_theme_hex('control.button.border')};"
        " border-radius: 8px;"
        " padding: 6px 18px;"
        " min-width: 70px;"
        " }"
        "QPushButton:hover {"
        f" background-color: {_theme_rgba255('control.button.hover_surface')};"
        f" border: 1px solid {_theme_hex('control.button.border')};"
        " }"
        "QPushButton:checked {"
        f" {NAV_TAB_FONT_STYLE_ACTIVE}"
        f" background-color: {_theme_rgba255('control.button.hover_surface')};"
        f" color: {_theme_hex('control.button.text')};"
        f" border: 1px solid {_theme_hex('control.button.border')};"
        " }"
    )


NAV_PILL_STYLE = _build_nav_pill_style()


STATUS_LABEL_STYLE = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 600;"
    "font-size: 11px;"
    "letter-spacing: 0.3px;"
)

def _build_info_label_style() -> str:
    return (
        f"color: {_theme_hex('text.secondary')};"
        "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
        "font-weight: 500;"
        "font-size: 11px;"
        "letter-spacing: 0.3px;"
    )


INFO_LABEL_STYLE = _build_info_label_style()

def _build_adv_helper_label_style() -> str:
    return (
        f"color: {_theme_rgba('text.helper')};"
        "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
        "font-weight: 500;"
        "font-size: 11px;"
        "letter-spacing: 0.3px;"
    )


ADV_HELPER_LABEL_STYLE = _build_adv_helper_label_style()

def _build_info_label_style_disabled() -> str:
    return (
        f"color: {_theme_hex('text.helper_disabled')};"
        "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
        "font-weight: 500;"
        "font-size: 11px;"
        "letter-spacing: 0.3px;"
    )


INFO_LABEL_STYLE_DISABLED = _build_info_label_style_disabled()

def _build_slider_style() -> str:
    return _theme_qss("""
    /* Dark glass indented slider with pill-shaped notch handle */
    QSlider {
        min-height: 34px;
        margin: 2px 0px 0px 0px;
    }
    
    QSlider::groove:horizontal {
        height: 4px;
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            @@gradient:slider.groove.surface@@);
        border: 1px solid @@rgba:slider.groove.border@@;
        border-top-color: @@rgba:slider.groove.top_border@@;
        border-bottom-color: @@rgba:slider.groove.bottom_border@@;
        border-radius: 2px;
        margin: 0px 0;
    }
    
    QSlider::sub-page:horizontal {
        height: 4px;
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            @@gradient:slider.fill.surface@@);
        border: 1px solid @@rgba:slider.fill.border@@;
        border-top-color: @@rgba:slider.fill.top_border@@;
        border-bottom-color: @@rgba:slider.fill.bottom_border@@;
        border-radius: 2px;
    }
    
    QSlider::handle:horizontal {
        width: 16px;
        height: 10px;
        margin: -4px 0;
        border-radius: 5px;
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            @@gradient:slider.handle.surface@@);
        border: 1px solid @@hex:slider.handle.border@@;
        
    }
    
    QSlider::handle:horizontal:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            @@gradient:slider.handle.hover_surface@@);
        border: 1px solid @@hex:slider.handle.hover_border@@;
        
    }
    
    QSlider::handle:horizontal:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            @@gradient:slider.handle.pressed_surface@@);
        border: 1px solid @@hex:slider.handle.pressed_border@@;
    }
    
    QSlider::handle:horizontal:disabled {
        background: @@hex:slider.handle.disabled_surface@@;
    }
    
    QSlider#presetModeSlider {
        margin: 3px 0 0 0;
    }
    
    QSlider#presetModeSlider::groove:horizontal {
        margin: 1px 0 0 0;
    }
    
    QSlider::add-page:horizontal {
        background: transparent;
    }
    
    NoWheelSlider#sourcesRatioSlider {
        min-height: 22px;
        margin: 0px;
    }
    
    NoWheelSlider#sourcesRatioSlider::handle:horizontal {
        margin-top: -2px;
        margin-bottom: -2px;
    }
    
    /* Active indicator on the most-recently-moved slider handle */
    QSlider[lastMoved="true"]::handle:horizontal {
        width: 12px;
        height: 6px;
        margin: -4px 0;
        border-radius: 5px;
        border: 1.5px solid @@hex:slider.handle.active_border@@;
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            @@gradient:slider.handle.active_surface@@);
    }
    """)


SLIDER_STYLE = _build_slider_style()


def _build_accessibility_title_style() -> str:
    return (
        "font-size: 18px; font-weight: bold; "
        f"color: {_theme_hex('text.primary')};"
    )


ACCESSIBILITY_TITLE_STYLE = _build_accessibility_title_style()


def _build_accessibility_desc_style() -> str:
    return (
        f"color: {_theme_hex('text.secondary')};"
        " font-size: 11px; margin-bottom: 10px;"
    )


ACCESSIBILITY_DESC_STYLE = _build_accessibility_desc_style()


def _build_accessibility_section_desc_style() -> str:
    return (
        f"color: {_theme_hex('text.tertiary')};"
        " font-size: 10px; margin-top: 5px;"
    )


ACCESSIBILITY_SECTION_DESC_STYLE = _build_accessibility_section_desc_style()


_THEME_STYLE_BUILDERS = {
    "FORM_LABEL_STYLE": _build_form_label_style,
    "FORM_ROW_LABEL_STYLE": _build_form_row_label_style,
    "FORM_LABEL_STYLE_DISABLED": _build_form_label_style_disabled,
    "FORM_ROW_LABEL_STYLE_DISABLED": _build_form_row_label_style_disabled,
    "SPINBOX_STYLE": _build_spinbox_style,
    "COMBOBOX_STYLE": _build_combobox_style,
    "COMBOBOX_POPUP_VIEW_STYLE": _build_combobox_popup_view_style,
    "TOOLTIP_STYLE": _build_tooltip_style,
    "PAGE_TITLE_STYLE": _build_page_title_style,
    "SECTION_HEADING_STYLE": _build_section_heading_style,
    "SECTION_HEADING_STYLE_DISABLED": _build_section_heading_style_disabled,
    "SWATCH_LABEL_STYLE": _build_swatch_label_style,
    "SUBSECTION_DIVIDER_STYLE": _build_subsection_divider_style,
    "INFO_LABEL_STYLE": _build_info_label_style,
    "ADV_HELPER_LABEL_STYLE": _build_adv_helper_label_style,
    "INFO_LABEL_STYLE_DISABLED": _build_info_label_style_disabled,
    "NAV_PILL_STYLE": _build_nav_pill_style,
    "SLIDER_STYLE": _build_slider_style,
    "ACCESSIBILITY_TITLE_STYLE": _build_accessibility_title_style,
    "ACCESSIBILITY_DESC_STYLE": _build_accessibility_desc_style,
    "ACCESSIBILITY_SECTION_DESC_STYLE": _build_accessibility_section_desc_style,
}


def _install_theme_styles(theme: SettingsThemeSpec) -> None:
    """Rebuild shared style vocabulary from one resolved active ThemeSpec."""

    global _SETTINGS_THEME
    _SETTINGS_THEME = theme
    namespace = globals()
    for name, builder in _THEME_STYLE_BUILDERS.items():
        namespace[name] = builder()


def _refresh_live_shared_widgets(theme: SettingsThemeSpec) -> None:
    """Refresh widget families whose styling is owned directly in this module."""

    _install_theme_styles(theme)

    for label, role in tuple(_LIVE_STYLED_LABELS.items()):
        if _is_live_qobject(label):
            style_sheet = globals().get(role)
            if isinstance(style_sheet, str):
                label.setStyleSheet(style_sheet)

    for widget, binding in tuple(_LIVE_STYLE_BUNDLES.items()):
        if _is_live_qobject(widget):
            base_style, style_roles, trailing_style = binding
            widget.setStyleSheet(
                _render_shared_style_bundle(
                    base_style,
                    style_roles,
                    trailing_style,
                )
            )

    for box in tuple(_LIVE_GROUP_BOXES):
        if _is_live_qobject(box):
            style_group_box(box)

    for slider in tuple(_LIVE_RECOMMENDED_SLIDERS):
        if _is_live_qobject(slider):
            slider._refresh_theme_marker(theme)


# Future tab/component migration should consume current module attributes or
# shared apply helpers rather than importing rendered style strings by value.
# Existing by-value consumers are deliberately migrated in focused checkpoints
# instead of being patched through module-global or application-wide scans.
_THEME_UNSUBSCRIBE = subscribe_settings_theme(_refresh_live_shared_widgets)


SCROLL_AREA_STYLE = """
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
"""

# Sources-specific field styling
RSS_INPUT_STYLE = (
    "QLineEdit#rssFeedInput {"
    " border: 1px solid rgba(70,70,70,0.6);"
    " border-radius: 6px;"
    " padding: 8px 10px;"
    " background-color: #282828;"
    " box-shadow: 0px 2px 8px rgba(0, 0, 0, 0.45);"
    " }"
    "QLineEdit#rssFeedInput:focus {"
    " border-color: rgba(200,200,200,0.85);"
    " }"
)

def build_bucket_toggle(
    host_layout: QVBoxLayout,
    title: str,
    expanded: bool = False,
    on_toggle: Callable[[bool], None] | None = None,
    defer_initial_visibility: bool = False,
) -> tuple[QToolButton, QWidget, QVBoxLayout]:
    """Create a collapsible bucket toggle with arrow indicator.

    Matches the established visualizer bucket design: a QToolButton with
    a Down/Right arrow and text beside the icon.  Returns
    ``(toggle_button, body_widget, body_layout)``.
    """
    toggle = QToolButton()
    toggle.setText(title)
    toggle.setCheckable(True)
    toggle.setChecked(expanded)
    toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
    toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    toggle.setAutoRaise(True)

    toggle_row = QHBoxLayout()
    toggle_row.addWidget(toggle)
    toggle_row.addStretch()
    host_layout.addLayout(toggle_row)

    body = QWidget()
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(12, 0, 0, 8)
    body_layout.setSpacing(4)
    if not defer_initial_visibility:
        body.setVisible(expanded)
    host_layout.addWidget(body)

    def _apply_state(checked: bool) -> None:
        toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        if body.isHidden() == bool(checked):
            body.setVisible(checked)
        if on_toggle is not None:
            on_toggle(checked)

    toggle.toggled.connect(_apply_state)
    return toggle, body, body_layout
