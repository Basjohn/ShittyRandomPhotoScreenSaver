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
    QAbstractScrollArea,
    QAbstractSpinBox,
    QComboBox,
    QGraphicsDropShadowEffect,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollBar,
    QToolButton,
    QWidget,
)

from ui.settings_theme_runtime import (
    get_active_settings_theme,
    subscribe_settings_theme,
)
from ui.settings_theme_spec import SettingsThemeSpec


def _active_input_style():
    """Return the currently active semantic input shadow."""

    return get_active_settings_theme().shadow("input.spin_combo")


@dataclass(slots=True)
class ShadowConfig:
    """One bounded renderer-facing widget-shadow style.

    Default construction remains compatible with provisional input shadows,
    but those defaults are resolved from the active theme at construction time
    rather than being frozen when this module is imported.
    """

    blur_radius: float = field(
        default_factory=lambda: _active_input_style().blur_radius
    )
    offset: QPointF = field(
        default_factory=lambda: QPointF(
            _active_input_style().offset_x,
            _active_input_style().offset_y,
        )
    )
    color: QColor = field(
        default_factory=lambda: QColor(*_active_input_style().color.as_tuple())
    )
    disabled_alpha_scale: float = field(
        default_factory=lambda: _active_input_style().disabled_alpha_scale
    )


def _theme_shadow_config(
    token: str,
    theme: SettingsThemeSpec | None = None,
) -> ShadowConfig:
    """Adapt one semantic theme shadow into the existing QWidget renderer type."""

    resolved_theme = theme or get_active_settings_theme()
    style = resolved_theme.shadow(token)
    return ShadowConfig(
        blur_radius=style.blur_radius,
        offset=QPointF(style.offset_x, style.offset_y),
        color=QColor(*style.color.as_tuple()),
        disabled_alpha_scale=style.disabled_alpha_scale,
    )


# These names remain stable renderer vocabulary for the rest of this module.
# Their values are replaced atomically whenever the active ThemeSpec changes.
SPIN_COMBO_SHADOW: ShadowConfig
LINE_EDIT_SHADOW: ShadowConfig
PILL_BUTTON_SHADOW: ShadowConfig
NAV_TAB_SHADOW: ShadowConfig
BUCKET_CLOSED_SHADOW: ShadowConfig
BUCKET_OPEN_SHADOW: ShadowConfig
SECTION_TEXT_SHADOW: ShadowConfig
NAV_ICON_SHADOW: ShadowConfig
PAGE_TEXT_SHADOW: ShadowConfig
TITLE_TEXT_SHADOW: ShadowConfig
SHELL_PANEL_SHADOW: ShadowConfig
SCROLLBAR_SHADOW: ShadowConfig
GROUP_FRAME_SHADOW: ShadowConfig
RATIO_FRAME_SHADOW: ShadowConfig


def _install_theme_shadow_configs(theme: SettingsThemeSpec) -> None:
    """Replace renderer-facing shadow configs from one resolved ThemeSpec."""

    global SPIN_COMBO_SHADOW
    global LINE_EDIT_SHADOW
    global PILL_BUTTON_SHADOW
    global NAV_TAB_SHADOW
    global BUCKET_CLOSED_SHADOW
    global BUCKET_OPEN_SHADOW
    global SECTION_TEXT_SHADOW
    global NAV_ICON_SHADOW
    global PAGE_TEXT_SHADOW
    global TITLE_TEXT_SHADOW
    global SHELL_PANEL_SHADOW
    global SCROLLBAR_SHADOW
    global GROUP_FRAME_SHADOW
    global RATIO_FRAME_SHADOW

    SPIN_COMBO_SHADOW = _theme_shadow_config("input.spin_combo", theme)

    # Entry boxes deliberately share the same crisp input cast as combo/spin
    # shells. There is no separate blurred line-edit visual authority anymore.
    LINE_EDIT_SHADOW = SPIN_COMBO_SHADOW

    PILL_BUTTON_SHADOW = _theme_shadow_config("button.pill", theme)

    # Main left-nav tabs are translucent; the renderer still uses the proven
    # outside-only body cast rather than an alpha-following graphics effect.
    NAV_TAB_SHADOW = _theme_shadow_config("navigation.tab", theme)

    BUCKET_CLOSED_SHADOW = _theme_shadow_config("bucket.closed", theme)
    BUCKET_OPEN_SHADOW = _theme_shadow_config("bucket.open", theme)
    SECTION_TEXT_SHADOW = _theme_shadow_config("text.section", theme)
    NAV_ICON_SHADOW = SECTION_TEXT_SHADOW
    PAGE_TEXT_SHADOW = _theme_shadow_config("text.page", theme)
    TITLE_TEXT_SHADOW = _theme_shadow_config("text.title", theme)
    SHELL_PANEL_SHADOW = _theme_shadow_config("shell.panel", theme)
    SCROLLBAR_SHADOW = _theme_shadow_config("scrollbar", theme)
    GROUP_FRAME_SHADOW = _theme_shadow_config("panel.group", theme)

    # ratioFrame intentionally reuses the semantic panel-group cast.
    RATIO_FRAME_SHADOW = GROUP_FRAME_SHADOW


_install_theme_shadow_configs(get_active_settings_theme())


# Settings roots that have actually used this renderer. Weak references keep
# the runtime theme authority from extending any dialog/widget lifetime.
_THEMED_ROOT_REFS: list[weakref.ReferenceType[QWidget]] = []


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

    def reconfigure(
        self,
        config: ShadowConfig,
        *,
        radius: float,
        insets: tuple[float, float, float, float],
        group_box_frame: bool,
    ) -> None:
        """Apply new semantic values without changing the render mechanism."""

        self.config = config
        self.radius = float(radius)
        self.insets = tuple(float(value) for value in insets)
        self.group_box_frame = bool(group_box_frame)
        self._sync()

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


def _layout_containing_widget(layout, widget: QWidget):
    """Return the nested layout that directly contains ``widget``, if any."""

    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is None:
            continue
        if item.widget() is widget:
            return layout
        child_layout = item.layout()
        if child_layout is not None:
            found = _layout_containing_widget(child_layout, widget)
            if found is not None:
                return found
    return None


def _reserve_parent_layout_shadow_clearance(widget: QWidget, config: ShadowConfig) -> None:
    """Reserve right/bottom room when a cast would otherwise be clipped by layout bounds."""

    required_right = int(math.ceil(max(0.0, float(config.offset.x())))) + 2
    required_bottom = int(math.ceil(max(0.0, float(config.offset.y())))) + 2
    child: QWidget = widget
    parent = widget.parentWidget()
    while parent is not None:
        layout = parent.layout()
        target_layout = (
            _layout_containing_widget(layout, child)
            if layout is not None
            else None
        )
        if target_layout is not None:
            margins = target_layout.contentsMargins()
            next_right = max(margins.right(), required_right)
            next_bottom = max(margins.bottom(), required_bottom)
            if next_right != margins.right() or next_bottom != margins.bottom():
                target_layout.setContentsMargins(
                    margins.left(),
                    margins.top(),
                    next_right,
                    next_bottom,
                )
                parent.updateGeometry()
            return
        child = parent
        parent = parent.parentWidget()


def _find_scroll_area(scrollbar: QScrollBar) -> QAbstractScrollArea | None:
    """Return the QAbstractScrollArea that owns an internal scrollbar."""

    parent = scrollbar.parentWidget()
    while parent is not None:
        if isinstance(parent, QAbstractScrollArea):
            return parent
        parent = parent.parentWidget()
    return None


class _ScrollBarShadowStripHelper(QObject):
    """Keep only the exposed right/bottom pieces of a scrollbar hard cast.

    The real scrollbar remains untouched. Unlike a filled rectangle behind a
    transparent QScrollBar, these strips never exist underneath the scrollbar
    body, so the shadow cannot bleed through its transparent track.
    """

    _CORNER_RADIUS = 1

    def __init__(self, owner: QScrollBar, config: ShadowConfig) -> None:
        super().__init__(owner)
        self.owner = owner
        self.config = config
        self.scroll_area: QAbstractScrollArea | None = None
        self.right_shadow: QWidget | None = None
        self.bottom_shadow: QWidget | None = None

        owner.installEventFilter(self)
        self._bind_scroll_area()
        self._sync()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        etype = event.type()

        if watched is self.owner:
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
                if etype == QEvent.Type.ParentChange:
                    self._bind_scroll_area()
                self._sync()
            elif etype == QEvent.Type.Destroy:
                self._dispose_shadows()

        elif watched is self.scroll_area:
            if etype in (
                QEvent.Type.Move,
                QEvent.Type.Resize,
                QEvent.Type.Show,
                QEvent.Type.Hide,
                QEvent.Type.LayoutRequest,
            ):
                self._sync()
            elif etype == QEvent.Type.Destroy:
                self.scroll_area = None
                self._dispose_shadows()

        return super().eventFilter(watched, event)

    def reconfigure(self, config: ShadowConfig) -> None:
        self.config = config
        self._reserve_clearance()
        self._sync()

    def _bind_scroll_area(self) -> None:
        next_area = _find_scroll_area(self.owner)
        if next_area is self.scroll_area:
            return

        if self.scroll_area is not None:
            self.scroll_area.removeEventFilter(self)

        self.scroll_area = next_area
        if self.scroll_area is not None:
            self.scroll_area.installEventFilter(self)

        self._dispose_shadows()
        self._reserve_clearance()

    def _reserve_clearance(self) -> None:
        if self.scroll_area is not None:
            _reserve_parent_layout_shadow_clearance(
                self.scroll_area,
                self.config,
            )

    def _make_strip(self, page: QWidget) -> QWidget:
        strip = QWidget(page)
        strip.setProperty("settingsShadowInternal", True)
        strip.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        strip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return strip

    def _ensure_shadows(self) -> tuple[QWidget | None, QWidget | None]:
        area = self.scroll_area
        if area is None:
            return None, None

        page = area.parentWidget()
        if page is None:
            return None, None

        if self.right_shadow is None:
            self.right_shadow = self._make_strip(page)
        elif self.right_shadow.parentWidget() is not page:
            self.right_shadow.setParent(page)

        if self.bottom_shadow is None:
            self.bottom_shadow = self._make_strip(page)
        elif self.bottom_shadow.parentWidget() is not page:
            self.bottom_shadow.setParent(page)

        return self.right_shadow, self.bottom_shadow

    def _apply_shadow_style(self, strip: QWidget) -> None:
        color = QColor(self.config.color)
        if not self.owner.isEnabled():
            color.setAlpha(
                int(color.alpha() * self.config.disabled_alpha_scale)
            )

        strip.setStyleSheet(
            "background-color: "
            f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});"
            " border: none;"
            f" border-radius: {self._CORNER_RADIUS}px;"
        )

    def _sync(self) -> None:
        area = self.scroll_area
        right_shadow, bottom_shadow = self._ensure_shadows()
        if area is None or right_shadow is None or bottom_shadow is None:
            return

        page = area.parentWidget()
        if page is None:
            right_shadow.hide()
            bottom_shadow.hide()
            return

        top_left = self.owner.mapTo(page, self.owner.rect().topLeft())
        dx = max(0, int(round(float(self.config.offset.x()))))
        dy = max(0, int(round(float(self.config.offset.y()))))
        width = self.owner.width()
        height = self.owner.height()

        # Hard-cast geometry = translated source rectangle minus the original.
        # Draw only those exposed pieces; absolutely nothing sits beneath the
        # transparent scrollbar body.
        right_shadow.setGeometry(
            top_left.x() + width,
            top_left.y() + dy,
            dx,
            height,
        )
        bottom_shadow.setGeometry(
            top_left.x() + dx,
            top_left.y() + height,
            width,
            dy,
        )

        self._apply_shadow_style(right_shadow)
        self._apply_shadow_style(bottom_shadow)

        right_shadow.stackUnder(area)
        bottom_shadow.stackUnder(area)

        visible = (
            area.isVisible()
            and self.owner.isVisible()
            and width > 0
            and height > 0
            and dx > 0
            and dy > 0
        )
        right_shadow.setVisible(visible)
        bottom_shadow.setVisible(visible)

    def _dispose_shadows(self) -> None:
        for strip in (self.right_shadow, self.bottom_shadow):
            if strip is not None:
                strip.deleteLater()
        self.right_shadow = None
        self.bottom_shadow = None


def attach_scrollbar_shadow_strip(
    scrollbar: QScrollBar,
    config: ShadowConfig = SCROLLBAR_SHADOW,
) -> bool:
    """Attach a cohesive full-scrollbar shadow using exposed sibling strips."""

    if _find_scroll_area(scrollbar) is None:
        return False

    # Retire checkpoint-11's whole-widget graphics effect and its helper so an
    # old event filter cannot reattach it later.
    old_helper = getattr(scrollbar, "_control_shadow_helper", None)
    if isinstance(old_helper, _ControlShadowHelper):
        scrollbar.removeEventFilter(old_helper)
        if scrollbar.graphicsEffect() is not None:
            scrollbar.setGraphicsEffect(None)
        old_helper.deleteLater()
        setattr(scrollbar, "_control_shadow_helper", None)

    existing = getattr(
        scrollbar,
        "_settings_scrollbar_shadow_strip_helper",
        None,
    )
    if isinstance(existing, _ScrollBarShadowStripHelper):
        existing.reconfigure(config)
        return True

    helper = _ScrollBarShadowStripHelper(scrollbar, config)
    setattr(
        scrollbar,
        "_settings_scrollbar_shadow_strip_helper",
        helper,
    )
    return True


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
        existing.reconfigure(
            config,
            radius=radius,
            insets=insets,
            group_box_frame=group_box_frame,
        )
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


def _heading_shadow_config(label: QLabel) -> ShadowConfig | None:
    text = (label.text() or "").strip()
    if not text:
        return None
    # This helper paints plain text. Leave rich/HTML labels to their existing
    # presentation rather than risking literal markup in the shadow backing.
    if "<" in text and ">" in text:
        return None

    if label.objectName() == "titleBarLabel":
        # Typography/geometry are established synchronously by SettingsDialog.
        # This renderer owns only the shadow and must never move the title.
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

    if widget.property("settingsNavIcon"):
        # Widget construction owns icon geometry. This module owns only the
        # semantic shadow attachment/rendering.
        attach_control_shadow(
            widget,
            NAV_ICON_SHADOW,
            replace_existing=True,
        )
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
            # shadow. Keep only the proven outside-only body cast here.
            #
            # TabButton owns icon/text layout only. Its child text and icon are
            # discovered by this centralized pass and receive their shadows here.
            if widget.graphicsEffect() is not None:
                widget.setGraphicsEffect(None)
            attach_cast_shadow(
                widget,
                NAV_TAB_SHADOW,
                radius=6.0,
                insets=(3.0, 3.0, 5.0, 5.0),
            )
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
        if not attach_scrollbar_shadow_strip(widget, SCROLLBAR_SHADOW):
            # Conservative fallback for a standalone QScrollBar. Settings tab
            # scrollbars all use the sibling-strip path.
            attach_control_shadow(
                widget,
                SCROLLBAR_SHADOW,
                replace_existing=True,
            )

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
            reserve_layout=True,
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


def _register_shadow_root(root: QWidget) -> None:
    """Remember the owning Settings window without extending its lifetime."""

    try:
        window = root.window()
    except RuntimeError:
        return
    candidate = window if isinstance(window, QWidget) else root

    live_refs: list[weakref.ReferenceType[QWidget]] = []
    found = False
    for ref in _THEMED_ROOT_REFS:
        existing = ref()
        if existing is None:
            continue
        live_refs.append(ref)
        if existing is candidate:
            found = True

    if not found:
        try:
            live_refs.append(weakref.ref(candidate))
        except TypeError:
            return

    _THEMED_ROOT_REFS[:] = live_refs


def _iter_shadow_roots() -> tuple[QWidget, ...]:
    """Return live registered roots while pruning dead weak references."""

    roots: list[QWidget] = []
    live_refs: list[weakref.ReferenceType[QWidget]] = []
    seen: set[int] = set()

    for ref in _THEMED_ROOT_REFS:
        root = ref()
        if root is None:
            continue
        live_refs.append(ref)
        identity = id(root)
        if identity not in seen:
            roots.append(root)
            seen.add(identity)

    _THEMED_ROOT_REFS[:] = live_refs
    return tuple(roots)


def apply_shadows_to_existing(
    root: Optional[QWidget],
    *,
    include_types: Sequence[Type[QWidget]] | None = None,
) -> None:
    """Synchronously apply Settings shadows to the widgets that exist now.

    This performs no delayed work and installs no watcher.  It is the correct
    path for the fully assembled Settings shell before first paint, and is also
    suitable for a future live-theme refresh of existing widgets.
    """

    if root is None:
        return

    _register_shadow_root(root)

    target_types_list: list[Type[QWidget]] = list(_DEFAULT_TARGET_TYPES)
    if include_types:
        for cls in include_types:
            if cls not in target_types_list:
                target_types_list.append(cls)
    _style_scope(root, tuple(target_types_list))


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

    apply_shadows_to_existing(root, include_types=include_types)

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


def _refresh_registered_shadows(theme: SettingsThemeSpec) -> None:
    """Reconfigure every existing Settings shadow for a live theme change."""

    _install_theme_shadow_configs(theme)
    for root in _iter_shadow_roots():
        try:
            apply_shadows_to_existing(root)
        except RuntimeError:
            # A QWidget may have been deleted at C++ level just before its
            # Python weakref disappears. Dead roots are harmless on refresh.
            continue


# Stable module-level subscription. The runtime authority calls this
# synchronously and will invoke it again with the previous ThemeSpec if another
# renderer fails and the overall theme transaction rolls back.
_THEME_UNSUBSCRIBE = subscribe_settings_theme(_refresh_registered_shadows)


__all__ = [
    "ShadowConfig",
    "SPIN_COMBO_SHADOW",
    "LINE_EDIT_SHADOW",
    "PILL_BUTTON_SHADOW",
    "NAV_TAB_SHADOW",
    "BUCKET_CLOSED_SHADOW",
    "BUCKET_OPEN_SHADOW",
    "SECTION_TEXT_SHADOW",
    "NAV_ICON_SHADOW",
    "PAGE_TEXT_SHADOW",
    "TITLE_TEXT_SHADOW",
    "SHELL_PANEL_SHADOW",
    "SCROLLBAR_SHADOW",
    "GROUP_FRAME_SHADOW",
    "attach_control_shadow",
    "attach_text_shadow",
    "attach_cast_shadow",
    "attach_scrollbar_shadow_strip",
    "apply_shadows_to_existing",
    "apply_shadows_to_inputs",
]
