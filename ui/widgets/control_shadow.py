"""Central Settings drop-shadow rendering for controls, text, buttons and frames.

Shadow *values* come from the semantic Settings theme.  This module continues
owning the proven QWidget rendering mechanisms and widget classification.
"""
from __future__ import annotations

import math
import re
import weakref
from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple, Type

from PySide6.QtCore import QObject, QPointF, QEvent, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QComboBox,
    QGraphicsDropShadowEffect,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollBar,
    QStyle,
    QStyleOptionButton,
    QToolButton,
    QWidget,
)

from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME


_SETTINGS_THEME = DEFAULT_DARK_SETTINGS_THEME
_DEFAULT_INPUT_STYLE = _SETTINGS_THEME.shadow("input.spin_combo")


@dataclass(slots=True)
class ShadowConfig:
    """One bounded renderer-facing widget-shadow style.

    The default remains the Settings input shadow for compatibility with custom
    controls that attach a provisional shadow during construction, but those
    values now come from the semantic theme rather than being repeated here.
    """

    blur_radius: float = _DEFAULT_INPUT_STYLE.blur_radius
    offset: QPointF = field(
        default_factory=lambda: QPointF(
            _DEFAULT_INPUT_STYLE.offset_x,
            _DEFAULT_INPUT_STYLE.offset_y,
        )
    )
    color: QColor = field(
        default_factory=lambda: QColor(*_DEFAULT_INPUT_STYLE.color.as_tuple())
    )
    disabled_alpha_scale: float = _DEFAULT_INPUT_STYLE.disabled_alpha_scale


def _theme_shadow_config(token: str) -> ShadowConfig:
    """Adapt one semantic theme shadow into the existing QWidget renderer type."""

    style = _SETTINGS_THEME.shadow(token)
    return ShadowConfig(
        blur_radius=style.blur_radius,
        offset=QPointF(style.offset_x, style.offset_y),
        color=QColor(*style.color.as_tuple()),
        disabled_alpha_scale=style.disabled_alpha_scale,
    )


# Settings control-shadow language.  Rendering remains local; visual policy is
# semantic theme data.
SPIN_COMBO_SHADOW = _theme_shadow_config("input.spin_combo")

# The old line-edit treatment was the remaining soft/blurred input shadow.  The
# Settings visual refresh now deliberately gives entry boxes the same crisp
# cast as combo/spin input shells.  The legacy ``input.line_edit`` theme token
# can be removed when settings_theme_spec.py next comes through migration.
LINE_EDIT_SHADOW = SPIN_COMBO_SHADOW

PILL_BUTTON_SHADOW = _theme_shadow_config("button.pill")

# Main left-nav tabs are translucent; a normal graphics effect shadows their
# border/text alpha and looks hollow.  Their body therefore remains a solid
# geometry backing, while their label content gets a separate shadow-only pass.
NAV_TAB_SHADOW = _theme_shadow_config("navigation.tab")
NAV_TAB_CONTENT_SHADOW = _theme_shadow_config("text.section")

BUCKET_CLOSED_SHADOW = _theme_shadow_config("bucket.closed")
BUCKET_OPEN_SHADOW = _theme_shadow_config("bucket.open")
SECTION_TEXT_SHADOW = _theme_shadow_config("text.section")
PAGE_TEXT_SHADOW = _theme_shadow_config("text.page")
TITLE_TEXT_SHADOW = _theme_shadow_config("text.title")
SHELL_PANEL_SHADOW = _theme_shadow_config("shell.panel")
SCROLLBAR_SHADOW = _theme_shadow_config("scrollbar")
GROUP_FRAME_SHADOW = _theme_shadow_config("panel.group")

# ``ratioFrame`` is a compact rounded panel rather than a control.  Until a
# dedicated semantic token is warranted, reuse the existing panel-group cast
# instead of inventing another local numeric shadow policy.
RATIO_FRAME_SHADOW = GROUP_FRAME_SHADOW


class _ControlShadowHelper(QObject):
    """Own the QGraphicsDropShadowEffect attached to one widget."""

    def __init__(
        self,
        widget: QWidget,
        config: ShadowConfig,
        *,
        checked_config: ShadowConfig | None = None,
    ) -> None:
        super().__init__(widget)
        self._widget = widget
        self._config = config
        self._checked_config = checked_config
        self._effect = QGraphicsDropShadowEffect(widget)
        self._toggled_connected = False
        self._widget.installEventFilter(self)
        self._ensure_toggle_connection()
        self._apply()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if watched is self._widget:
            etype = event.type()
            if etype in (
                QEvent.Type.EnabledChange,
                QEvent.Type.StyleChange,
                QEvent.Type.UpdateRequest,
            ):
                self._apply()
            elif etype == QEvent.Type.Destroy:
                self._widget.removeEventFilter(self)
        return super().eventFilter(watched, event)

    def reconfigure(
        self,
        config: ShadowConfig,
        *,
        checked_config: ShadowConfig | None = None,
    ) -> None:
        """Replace an early/provisional policy with the central Settings one."""

        self._config = config
        self._checked_config = checked_config
        self._ensure_toggle_connection()
        self._apply()

    def _ensure_toggle_connection(self) -> None:
        if (
            self._checked_config is not None
            and isinstance(self._widget, QAbstractButton)
            and not self._toggled_connected
        ):
            self._widget.toggled.connect(self._apply)
            self._toggled_connected = True

    def _active_config(self) -> ShadowConfig:
        if (
            self._checked_config is not None
            and isinstance(self._widget, QAbstractButton)
            and self._widget.isChecked()
        ):
            return self._checked_config
        return self._config

    def _apply(self, *_args) -> None:
        config = self._active_config()
        color = QColor(config.color)
        if not self._widget.isEnabled():
            color.setAlpha(int(color.alpha() * config.disabled_alpha_scale))
        self._effect.setBlurRadius(max(0.0, float(config.blur_radius)))
        self._effect.setOffset(config.offset)
        self._effect.setColor(color)
        self._widget.setGraphicsEffect(self._effect)


def attach_control_shadow(
    widget: QWidget,
    config: Optional[ShadowConfig] = None,
    *,
    checked_config: ShadowConfig | None = None,
    replace_existing: bool = False,
) -> None:
    """Attach one owned shadow, optionally replacing an early owned policy.

    Custom combo controls attach during construction. The Settings post-pass
    therefore needs ``replace_existing=True`` to normalize any early helper to
    the central spin/combo policy instead of preserving stale old defaults.
    """

    cfg = config or SPIN_COMBO_SHADOW
    existing = getattr(widget, "_control_shadow_helper", None)
    if isinstance(existing, _ControlShadowHelper):
        if replace_existing:
            existing.reconfigure(cfg, checked_config=checked_config)
        return

    helper = _ControlShadowHelper(widget, cfg, checked_config=checked_config)
    setattr(widget, "_control_shadow_helper", helper)


class _TextShadowOverlay(QWidget):
    """Paint one hard antialiased text shadow without rasterizing the source QLabel."""

    def __init__(self, helper: "_TextShadowHelper", parent: QWidget) -> None:
        super().__init__(parent)
        self._helper = helper
        self.setProperty("settingsShadowInternal", True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("background: transparent; border: none;")

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        helper = self._helper
        owner = helper.owner
        if owner is None or owner.isHidden() or not owner.text():
            return

        text_rect = QRectF(owner.contentsRect())
        margin = max(0, int(owner.margin()))
        if margin:
            text_rect.adjust(margin, margin, -margin, -margin)
        if owner.objectName() == "titleBarLabel":
            # settings_theme.py gives the title 10px left / 3px top padding.
            # QLabel's contentsRect does not reliably expose stylesheet padding.
            text_rect.adjust(10.0, 3.0, 0.0, 0.0)

        offset = helper.config.offset
        shadow_rect = QRectF(text_rect)
        shadow_rect.translate(offset)

        color = QColor(helper.config.color)
        if not owner.isEnabled():
            color.setAlpha(int(color.alpha() * helper.config.disabled_alpha_scale))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(owner.font())
        painter.setPen(color)
        flags = int(owner.alignment())
        if owner.wordWrap():
            flags |= int(Qt.TextFlag.TextWordWrap)
        painter.drawText(shadow_rect, flags, owner.text())
        painter.end()


class _TextShadowHelper(QObject):
    """Track a QLabel with a sibling-painted hard shadow and untouched source glyphs."""

    def __init__(self, owner: QLabel, config: ShadowConfig) -> None:
        super().__init__(owner)
        self.owner = owner
        self.config = config
        self.overlay: _TextShadowOverlay | None = None
        owner.installEventFilter(self)
        self._sync()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if watched is self.owner:
            etype = event.type()
            if etype in (
                QEvent.Type.Move,
                QEvent.Type.Resize,
                QEvent.Type.Show,
                QEvent.Type.Hide,
                QEvent.Type.EnabledChange,
                QEvent.Type.StyleChange,
                QEvent.Type.FontChange,
                QEvent.Type.PaletteChange,
                QEvent.Type.UpdateRequest,
            ):
                self._sync()
            elif etype == QEvent.Type.Destroy:
                if self.overlay is not None:
                    self.overlay.deleteLater()
                    self.overlay = None
        return super().eventFilter(watched, event)

    def reconfigure(self, config: ShadowConfig) -> None:
        self.config = config
        self._sync()

    def _ensure_overlay_parent(self) -> None:
        parent = self.owner.parentWidget()
        if parent is None:
            if self.overlay is not None:
                self.overlay.hide()
            return
        if self.overlay is None:
            self.overlay = _TextShadowOverlay(self, parent)
        elif self.overlay.parentWidget() is not parent:
            self.overlay.setParent(parent)

    def _sync(self) -> None:
        self._ensure_overlay_parent()
        overlay = self.overlay
        if overlay is None:
            return
        offset = self.config.offset
        pad_x = max(2, int(math.ceil(max(0.0, float(offset.x())))) + 2)
        pad_y = max(2, int(math.ceil(max(0.0, float(offset.y())))) + 2)
        geom = self.owner.geometry()
        overlay.setGeometry(geom.x(), geom.y(), geom.width() + pad_x, geom.height() + pad_y)
        overlay.setVisible(not self.owner.isHidden())
        overlay.stackUnder(self.owner)
        overlay.update()


def attach_text_shadow(
    label: QLabel,
    config: ShadowConfig,
    *,
    replace_existing: bool = True,
) -> None:
    """Attach a crisp sibling-painted text shadow while keeping source text native/crisp."""

    if replace_existing and label.graphicsEffect() is not None:
        # QLabel graphics effects rasterize the source glyphs and are the cause
        # of the jagged/soft text seen in the Settings screenshots.
        label.setGraphicsEffect(None)

    existing = getattr(label, "_settings_text_shadow_helper", None)
    if isinstance(existing, _TextShadowHelper):
        existing.reconfigure(config)
        return
    helper = _TextShadowHelper(label, config)
    setattr(label, "_settings_text_shadow_helper", helper)


class _ButtonContentShadowOverlay(QWidget):
    """Paint a hard shadow for tab text/emoji without shadowing the translucent body."""

    def __init__(self, helper: "_ButtonContentShadowHelper", owner: QPushButton) -> None:
        super().__init__(owner)
        self._helper = helper
        self.setProperty("settingsShadowInternal", True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("background: transparent; border: none;")
        self.setGeometry(owner.rect())
        self.show()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        helper = self._helper
        owner = helper.owner
        if owner is None or owner.isHidden() or not owner.text():
            return

        option = QStyleOptionButton()
        option.initFrom(owner)
        option.rect = owner.rect()
        option.text = owner.text()
        option.icon = owner.icon()
        option.iconSize = owner.iconSize()

        content_rect = owner.style().subElementRect(
            QStyle.SubElement.SE_PushButtonContents,
            option,
            owner,
        )
        shadow_rect = QRectF(content_rect)
        shadow_rect.translate(helper.config.offset)

        color = QColor(helper.config.color)
        if not owner.isEnabled():
            color.setAlpha(int(color.alpha() * helper.config.disabled_alpha_scale))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(owner.font())
        painter.setPen(color)
        painter.drawText(
            shadow_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            owner.text(),
        )
        painter.end()


class _ButtonContentShadowHelper(QObject):
    """Keep a tab-label shadow child synchronized with its QPushButton owner."""

    def __init__(self, owner: QPushButton, config: ShadowConfig) -> None:
        super().__init__(owner)
        self.owner = owner
        self.config = config
        self.overlay = _ButtonContentShadowOverlay(self, owner)
        owner.installEventFilter(self)
        owner.toggled.connect(self.overlay.update)
        self._sync()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if watched is self.owner:
            etype = event.type()
            if etype in (
                QEvent.Type.Resize,
                QEvent.Type.Show,
                QEvent.Type.Hide,
                QEvent.Type.EnabledChange,
                QEvent.Type.StyleChange,
                QEvent.Type.FontChange,
                QEvent.Type.PaletteChange,
                QEvent.Type.Enter,
                QEvent.Type.Leave,
                QEvent.Type.UpdateRequest,
            ):
                self._sync()
            elif etype == QEvent.Type.Destroy:
                self.overlay.deleteLater()
        return super().eventFilter(watched, event)

    def reconfigure(self, config: ShadowConfig) -> None:
        self.config = config
        self._sync()

    def _sync(self) -> None:
        self.overlay.setGeometry(self.owner.rect())
        self.overlay.setVisible(not self.owner.isHidden())
        self.overlay.raise_()
        self.overlay.update()


def attach_button_content_shadow(
    button: QPushButton,
    config: ShadowConfig,
) -> None:
    """Shadow only a button's text/emoji content, leaving its body renderer alone."""

    existing = getattr(button, "_settings_button_content_shadow_helper", None)
    if isinstance(existing, _ButtonContentShadowHelper):
        existing.reconfigure(config)
        return
    helper = _ButtonContentShadowHelper(button, config)
    setattr(button, "_settings_button_content_shadow_helper", helper)


class _CastShadowOverlay(QWidget):
    """Sibling overlay that paints only the exposed portion of a hard cast shadow."""

    def __init__(self, helper: "_CastShadowHelper", parent: QWidget) -> None:
        super().__init__(parent)
        self._helper = helper
        self.setProperty("settingsShadowInternal", True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; border: none;")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        helper = self._helper
        owner = helper.owner
        if owner is None or owner.isHidden():
            return

        base_rect = helper.base_rect()
        if base_rect.isEmpty() or base_rect.width() <= 0.0 or base_rect.height() <= 0.0:
            return

        config = helper.config
        shadow_rect = QRectF(base_rect)
        shadow_rect.translate(config.offset)

        base_path = QPainterPath()
        base_path.addRoundedRect(base_rect, helper.radius, helper.radius)
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(shadow_rect, helper.radius, helper.radius)
        cast_path = shadow_path.subtracted(base_path)

        color = QColor(config.color)
        if not owner.isEnabled():
            color.setAlpha(int(color.alpha() * config.disabled_alpha_scale))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillPath(cast_path, color)
        painter.end()


class _CastShadowHelper(QObject):
    """Track a widget with an independent outside-only hard shadow sibling."""

    def __init__(
        self,
        owner: QWidget,
        config: ShadowConfig,
        *,
        radius: float,
        insets: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
        group_box_frame: bool = False,
    ) -> None:
        super().__init__(owner)
        self.owner = owner
        self.config = config
        self.radius = float(radius)
        self.insets = tuple(float(value) for value in insets)
        self.group_box_frame = bool(group_box_frame)
        parent = owner.parentWidget()
        self.overlay: _CastShadowOverlay | None = None
        if parent is not None:
            self.overlay = _CastShadowOverlay(self, parent)
        owner.installEventFilter(self)
        self._sync()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if watched is self.owner:
            etype = event.type()
            if etype in (
                QEvent.Type.Move,
                QEvent.Type.Resize,
                QEvent.Type.Show,
                QEvent.Type.Hide,
                QEvent.Type.EnabledChange,
                QEvent.Type.StyleChange,
                QEvent.Type.ParentChange,
                QEvent.Type.ZOrderChange,
            ):
                self._sync()
            elif etype == QEvent.Type.Destroy:
                if self.overlay is not None:
                    self.overlay.deleteLater()
                    self.overlay = None
        return super().eventFilter(watched, event)

    def base_rect(self) -> QRectF:
        owner = self.owner
        if self.group_box_frame and isinstance(owner, QGroupBox):
            # The Settings theme uses a 20 px title margin and 12 px bottom
            # margin for the visible rounded frame. Paint the cast against that
            # frame rather than against the full QGroupBox allocation/title area.
            rect = QRectF(owner.rect())
            return rect.adjusted(0.0, 20.0, 0.0, -12.0)

        left, top, right, bottom = self.insets
        return QRectF(owner.rect()).adjusted(left, top, -right, -bottom)

    def _ensure_overlay_parent(self) -> None:
        parent = self.owner.parentWidget()
        if parent is None:
            if self.overlay is not None:
                self.overlay.hide()
            return
        if self.overlay is None:
            self.overlay = _CastShadowOverlay(self, parent)
        elif self.overlay.parentWidget() is not parent:
            self.overlay.setParent(parent)

    def _sync(self) -> None:
        self._ensure_overlay_parent()
        overlay = self.overlay
        if overlay is None:
            return

        offset = self.config.offset
        pad_x = max(2, int(math.ceil(max(0.0, float(offset.x())))) + 2)
        pad_y = max(2, int(math.ceil(max(0.0, float(offset.y())))) + 2)
        geom = self.owner.geometry()
        overlay.setGeometry(geom.x(), geom.y(), geom.width() + pad_x, geom.height() + pad_y)
        overlay.setVisible(not self.owner.isHidden())
        # Keep the cast behind the source even when a hidden/lazy widget is
        # shown and Qt rebuilds child z-order.
        overlay.stackUnder(self.owner)
        overlay.update()


def _reserve_parent_layout_shadow_clearance(widget: QWidget, config: ShadowConfig) -> None:
    """Reserve right/bottom room when a cast would otherwise be clipped by layout bounds."""

    required_right = int(math.ceil(max(0.0, float(config.offset.x())))) + 2
    required_bottom = int(math.ceil(max(0.0, float(config.offset.y())))) + 2
    child: QWidget = widget
    parent = widget.parentWidget()
    while parent is not None:
        layout = parent.layout()
        if layout is not None and layout.indexOf(child) >= 0:
            margins = layout.contentsMargins()
            next_right = max(margins.right(), required_right)
            next_bottom = max(margins.bottom(), required_bottom)
            if next_right != margins.right() or next_bottom != margins.bottom():
                layout.setContentsMargins(
                    margins.left(),
                    margins.top(),
                    next_right,
                    next_bottom,
                )
                parent.updateGeometry()
            return
        child = parent
        parent = parent.parentWidget()


def attach_cast_shadow(
    widget: QWidget,
    config: ShadowConfig,
    *,
    radius: float,
    insets: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    group_box_frame: bool = False,
    reserve_layout: bool = False,
) -> None:
    """Attach an independent solid cast shadow without affecting widget opacity."""

    existing = getattr(widget, "_settings_cast_shadow_helper", None)
    if isinstance(existing, _CastShadowHelper):
        if reserve_layout:
            _reserve_parent_layout_shadow_clearance(widget, config)
        return
    helper = _CastShadowHelper(
        widget,
        config,
        radius=radius,
        insets=insets,
        group_box_frame=group_box_frame,
    )
    setattr(widget, "_settings_cast_shadow_helper", helper)
    if reserve_layout:
        _reserve_parent_layout_shadow_clearance(widget, config)


_DEFAULT_TARGET_TYPES: Tuple[Type[QWidget], ...] = (
    QAbstractSpinBox,
    QLineEdit,
    QComboBox,
)


_FONT_SIZE_RE = re.compile(r"font-size\s*:\s*([0-9]+(?:\.[0-9]+)?)px", re.IGNORECASE)


def _input_shadow_config(widget: QWidget) -> ShadowConfig:
    if isinstance(widget, (QAbstractSpinBox, QComboBox, QLineEdit)):
        return SPIN_COMBO_SHADOW
    return SPIN_COMBO_SHADOW


def _is_bucket_toggle(button: QToolButton) -> bool:
    """Recognize the shared build_bucket_toggle() contract without tab coupling."""

    return bool(
        button.isCheckable()
        and button.autoRaise()
        and button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        and button.arrowType() in (Qt.ArrowType.RightArrow, Qt.ArrowType.DownArrow)
    )


def _label_font_size_px(label: QLabel) -> float:
    style = label.styleSheet() or ""
    match = _FONT_SIZE_RE.search(style)
    if match is not None:
        try:
            return float(match.group(1))
        except ValueError:
            pass

    font = label.font()
    pixel_size = font.pixelSize()
    if pixel_size > 0:
        return float(pixel_size)
    point_size = font.pointSizeF()
    if point_size > 0:
        return float(point_size) * (96.0 / 72.0)
    return 0.0


def _prepare_title_label(label: QLabel) -> None:
    """Apply the requested +2pt Settings title treatment exactly once."""

    if label.text().strip() != "SRPSS SETTINGS":
        return
    if label.property("settingsTitleShadowPrepared"):
        return

    font = label.font()
    point_size = font.pointSizeF()
    if point_size > 0:
        font.setPointSizeF(point_size + 2.0)
    else:
        pixel_size = font.pixelSize()
        if pixel_size > 0:
            font.setPixelSize(pixel_size + 3)
    label.setFont(font)
    label.setProperty("settingsTitleShadowPrepared", True)

    parent = label.parentWidget()
    if parent is not None and parent.objectName() == "customTitleBar":
        # The original title bar is fixed at 40px. Give the larger glyphs and
        # 5px cast enough vertical room instead of letting the parent clip it.
        parent.setFixedHeight(max(46, parent.height()))


def _heading_shadow_config(label: QLabel) -> ShadowConfig | None:
    text = (label.text() or "").strip()
    if not text:
        return None
    # This helper paints plain text. Leave rich/HTML labels to their existing
    # presentation rather than risking literal markup in the shadow backing.
    if "<" in text and ">" in text:
        return None

    if label.objectName() == "titleBarLabel":
        _prepare_title_label(label)
        return TITLE_TEXT_SHADOW

    size_px = _label_font_size_px(label)
    if size_px >= 17.0:
        return PAGE_TEXT_SHADOW
    if size_px >= 15.0:
        return SECTION_TEXT_SHADOW
    return None


def _reserve_flow_shadow_clearance(widget: QWidget, config: ShadowConfig) -> None:
    """Give a FlowContainer's last wrapped row room for an outside shadow."""

    try:
        from ui.flow_layout import FlowContainer
    except Exception:
        return

    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, FlowContainer):
            margins = parent.flow.contentsMargins()
            required_right = int(math.ceil(max(0.0, float(config.offset.x())))) + 1
            required_bottom = int(math.ceil(max(0.0, float(config.offset.y())))) + 1
            next_right = max(margins.right(), required_right)
            next_bottom = max(margins.bottom(), required_bottom)
            if next_right != margins.right() or next_bottom != margins.bottom():
                parent.flow.setContentsMargins(
                    margins.left(),
                    margins.top(),
                    next_right,
                    next_bottom,
                )
                parent.updateGeometry()
            return
        parent = parent.parentWidget()


def _is_shadow_internal(widget: QWidget) -> bool:
    return bool(widget.property("settingsShadowInternal"))


def _style_one_widget(
    widget: QWidget,
    target_types: tuple[Type[QWidget], ...],
) -> None:
    """Apply the current Settings shadow policy to one widget if applicable."""

    if _is_shadow_internal(widget):
        return

    if isinstance(widget, target_types):
        if isinstance(widget, QLineEdit) and isinstance(widget.parent(), QAbstractSpinBox):
            pass
        else:
            _ensure_styled_background(widget)
            if isinstance(widget, QAbstractSpinBox):
                editor = widget.findChild(QLineEdit)
                if editor is not None:
                    _ensure_styled_background(editor)
            attach_control_shadow(
                widget,
                _input_shadow_config(widget),
                replace_existing=True,
            )

    if isinstance(widget, QPushButton):
        if widget.property("shadowDirectionCell"):
            return
        if widget.objectName() in ("titleBarButton", "titleBarCloseButton"):
            return
        if widget.objectName() == "tabButton":
            # Never return to a whole-button graphics effect: the tab surface is
            # translucent and that treatment produces a hollow alpha-following
            # shadow. Keep the body cast and shadow only its text/emoji content.
            if widget.graphicsEffect() is not None:
                widget.setGraphicsEffect(None)
            attach_cast_shadow(
                widget,
                NAV_TAB_SHADOW,
                radius=6.0,
                insets=(3.0, 3.0, 5.0, 5.0),
            )
            attach_button_content_shadow(widget, NAV_TAB_CONTENT_SHADOW)
        else:
            attach_control_shadow(widget, PILL_BUTTON_SHADOW, replace_existing=True)
            _reserve_flow_shadow_clearance(widget, PILL_BUTTON_SHADOW)

    elif isinstance(widget, QToolButton) and _is_bucket_toggle(widget):
        attach_control_shadow(
            widget,
            BUCKET_CLOSED_SHADOW,
            checked_config=BUCKET_OPEN_SHADOW,
            replace_existing=True,
        )
        active = BUCKET_OPEN_SHADOW if widget.isChecked() else BUCKET_CLOSED_SHADOW
        _reserve_flow_shadow_clearance(widget, active)

    if isinstance(widget, QLabel):
        config = _heading_shadow_config(widget)
        if config is not None:
            # Do not use QGraphicsDropShadowEffect for labels: it rasterizes
            # the source glyphs and is what produced the jagged/soft text seen
            # in the previous screenshots.
            attach_text_shadow(widget, config, replace_existing=True)

    if isinstance(widget, QGroupBox):
        attach_cast_shadow(
            widget,
            GROUP_FRAME_SHADOW,
            radius=18.0,
            group_box_frame=True,
            reserve_layout=True,
        )

    if isinstance(widget, QScrollBar):
        # QScrollBar is a non-text surface, so a zero-blur graphics effect is
        # acceptable. Keep the offset small because Qt nests scrollbars in an
        # internal container that may clip large casts on some styles.
        attach_control_shadow(widget, SCROLLBAR_SHADOW, replace_existing=True)

    name = widget.objectName()
    if name in ("sidebar", "contentArea"):
        attach_cast_shadow(
            widget,
            SHELL_PANEL_SHADOW,
            radius=8.0,
        )
    elif name == "ratioFrame":
        attach_cast_shadow(
            widget,
            RATIO_FRAME_SHADOW,
            radius=8.0,
        )


def _style_scope(
    scope: QWidget,
    target_types: tuple[Type[QWidget], ...],
) -> None:
    _style_one_widget(scope, target_types)
    for widget in scope.findChildren(QWidget):
        _style_one_widget(widget, target_types)


class _SettingsShadowWatcher(QObject):
    """Style lazy Settings children when they are built after the initial scan."""

    def __init__(
        self,
        root: QWidget,
        target_types: tuple[Type[QWidget], ...],
    ) -> None:
        super().__init__(root)
        self._root_ref = weakref.ref(root)
        self._target_types = target_types
        self._install_tree(root)

    def reconfigure(self, target_types: tuple[Type[QWidget], ...]) -> None:
        self._target_types = target_types
        root = self._root_ref()
        if root is not None:
            self._install_tree(root)

    def _install_tree(self, widget: QWidget) -> None:
        if _is_shadow_internal(widget):
            return
        if not widget.property("settingsShadowWatcherInstalled"):
            widget.installEventFilter(self)
            widget.setProperty("settingsShadowWatcherInstalled", True)
        for child in widget.findChildren(
            QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly
        ):
            self._install_tree(child)

    def _defer_style(self, widget: QWidget) -> None:
        try:
            ref = weakref.ref(widget)
        except TypeError:
            return

        def _apply() -> None:
            target = ref()
            if target is None:
                return
            try:
                if _is_shadow_internal(target):
                    return
                self._install_tree(target)
                _style_scope(target, self._target_types)
            except RuntimeError:
                # C++ object may have been deleted before the queued polish.
                return

        QTimer.singleShot(0, _apply)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if isinstance(watched, QWidget):
            etype = event.type()
            if etype == QEvent.Type.ChildAdded:
                child = event.child() if hasattr(event, "child") else None
                if isinstance(child, QWidget) and not _is_shadow_internal(child):
                    self._install_tree(child)
                    self._defer_style(child)
            elif etype in (QEvent.Type.Show, QEvent.Type.Polish):
                if not _is_shadow_internal(watched):
                    self._defer_style(watched)
        return super().eventFilter(watched, event)


def apply_shadows_to_inputs(
    root: Optional[QWidget],
    *,
    include_types: Sequence[Type[QWidget]] | None = None,
) -> None:
    """Apply and maintain the centralized Settings shadow language.

    The historical function name remains because SettingsDialog already calls
    it after a tab is built. The installed watcher extends that policy to lazy
    section/page children created later.
    """

    if root is None:
        return

    target_types_list: list[Type[QWidget]] = list(_DEFAULT_TARGET_TYPES)
    if include_types:
        for cls in include_types:
            if cls not in target_types_list:
                target_types_list.append(cls)
    target_types = tuple(target_types_list)

    _style_scope(root, target_types)

    existing_watcher = getattr(root, "_settings_shadow_scope_watcher", None)
    if isinstance(existing_watcher, _SettingsShadowWatcher):
        existing_watcher.reconfigure(target_types)
    else:
        watcher = _SettingsShadowWatcher(root, target_types)
        setattr(root, "_settings_shadow_scope_watcher", watcher)

    window = root.window()
    if isinstance(window, QWidget) and window is not root:
        # Static shell surfaces (title, sidebar and right content frame) are
        # siblings of the tab root, so style them in the same idempotent pass.
        _style_scope(window, target_types)


def _ensure_styled_background(widget: QWidget) -> None:
    if not widget.testAttribute(Qt.WidgetAttribute.WA_StyledBackground):
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


__all__ = [
    "ShadowConfig",
    "SPIN_COMBO_SHADOW",
    "LINE_EDIT_SHADOW",
    "PILL_BUTTON_SHADOW",
    "NAV_TAB_SHADOW",
    "BUCKET_CLOSED_SHADOW",
    "BUCKET_OPEN_SHADOW",
    "SECTION_TEXT_SHADOW",
    "PAGE_TEXT_SHADOW",
    "TITLE_TEXT_SHADOW",
    "SHELL_PANEL_SHADOW",
    "SCROLLBAR_SHADOW",
    "GROUP_FRAME_SHADOW",
    "attach_control_shadow",
    "attach_text_shadow",
    "attach_cast_shadow",
    "apply_shadows_to_inputs",
]
