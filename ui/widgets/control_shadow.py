"""Shared drop shadow helper for input-style controls."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple, Type

from PySide6.QtCore import QObject, QPointF, QEvent, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QGraphicsDropShadowEffect,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QComboBox,
)


@dataclass(slots=True)
class ShadowConfig:
    blur_radius: float = 26.0
    offset: QPointF = field(default_factory=lambda: QPointF(4.5, 7.5))
    color: QColor = field(default_factory=lambda: QColor(0, 0, 0, 210))
    disabled_alpha_scale: float = 0.4


class _ControlShadowHelper(QObject):
    """Owns the QGraphicsDropShadowEffect attached to a widget."""

    def __init__(self, widget: QWidget, config: ShadowConfig) -> None:
        super().__init__(widget)
        self._widget = widget
        self._config = config
        self._effect = QGraphicsDropShadowEffect(widget)
        self._widget.installEventFilter(self)
        self._apply()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if watched is self._widget:
            etype = event.type()
            if etype in (QEvent.Type.EnabledChange, QEvent.Type.StyleChange, QEvent.Type.UpdateRequest):
                self._apply()
            elif etype == QEvent.Type.Destroy:
                self._widget.removeEventFilter(self)
        return super().eventFilter(watched, event)

    def _apply(self) -> None:
        blur = max(0.0, float(self._config.blur_radius))
        offset = self._config.offset
        color = QColor(self._config.color)
        if not self._widget.isEnabled():
            color.setAlpha(int(color.alpha() * self._config.disabled_alpha_scale))
        self._effect.setBlurRadius(blur)
        self._effect.setOffset(offset)
        self._effect.setColor(color)
        self._widget.setGraphicsEffect(self._effect)


def attach_control_shadow(widget: QWidget, config: Optional[ShadowConfig] = None) -> None:
    """Attach a crisp drop shadow to the given widget and keep it updated."""

    existing = getattr(widget, "_control_shadow_helper", None)
    if isinstance(existing, _ControlShadowHelper):
        return

    cfg = config or ShadowConfig()
    helper = _ControlShadowHelper(widget, cfg)
    setattr(widget, "_control_shadow_helper", helper)


_DEFAULT_TARGET_TYPES: Tuple[Type[QWidget], ...] = (
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QComboBox,
)


def apply_shadows_to_inputs(
    root: Optional[QWidget],
    *,
    include_types: Sequence[Type[QWidget]] | None = None,
) -> None:
    """Apply control shadows to all matching children under ``root``."""

    if root is None:
        return

    target_types: list[Type[QWidget]] = list(_DEFAULT_TARGET_TYPES)
    if include_types:
        for cls in include_types:
            if cls not in target_types:
                target_types.append(cls)

    for cls in target_types:
        for widget in root.findChildren(cls):
            if isinstance(widget, QLineEdit) and isinstance(widget.parent(), (QSpinBox, QDoubleSpinBox)):
                continue
            _ensure_styled_background(widget)
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                editor = widget.findChild(QLineEdit)
                if editor is not None:
                    _ensure_styled_background(editor)
            attach_control_shadow(widget)


def _ensure_styled_background(widget: QWidget) -> None:
    if not widget.testAttribute(Qt.WidgetAttribute.WA_StyledBackground):
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


__all__ = ["ShadowConfig", "attach_control_shadow", "apply_shadows_to_inputs"]
