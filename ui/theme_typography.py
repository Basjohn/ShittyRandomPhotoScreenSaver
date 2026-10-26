"""Light-palette font presentation, preserving original fonts for dark palettes."""
from __future__ import annotations

import re
import weakref
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Property, Slot
from PySide6.QtGui import QFont, QFontDatabase, QFontInfo

from ui.font_registration import READABILITY_JOST_FAMILY, ensure_custom_fonts, ensure_readability_fonts
from ui.theme_semantics import settings_theme_is_light

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

_WEIGHT_AXIS = QFont.Tag("wght")
_WEIGHT_INCREMENT = 50
_SETTINGS_FONTS = weakref.WeakKeyDictionary()
_TOOLTIP_FONT = None


def settings_typography_qss(qss: str, theme) -> str:
    """Select Jost's private variable face only for a light Settings palette."""
    if not settings_theme_is_light(theme):
        return qss
    ensure_readability_fonts()
    def families(match):
        values = match.group(2).split(",")
        return match.group(1) + ",".join(
            re.sub("(?i)jost", READABILITY_JOST_FAMILY, value)
            if value.strip().strip("\"'").casefold() == "jost" else value
            for value in values)
    return re.sub(r"(?i)(font-family\s*:)([^;{}]+)", families, qss)


def light_palette_font(source: QFont) -> QFont:
    """Copy the complete font and add a small, real weight increment.

    Qt's Windows face matcher rounds an intermediate requested weight to a
    named instance. An explicit variable axis is needed for intermediate ink.
    Static families use their smallest available stronger face instead.
    """
    ensure_custom_fonts()
    result = QFont(source)
    baseline = QFont(source)
    families = source.families()
    if any(family.casefold() in {"jost", READABILITY_JOST_FAMILY.casefold()} for family in families):
        ensure_readability_fonts()
        baseline.setFamilies(["Jost" if family.casefold() == READABILITY_JOST_FAMILY.casefold() else family
                              for family in families])
        result.setFamilies([READABILITY_JOST_FAMILY if family.casefold() == "jost" else family
                            for family in families])
        # Measure the accepted static face, not a different variable named face.
        baseline.unsetVariableAxis(_WEIGHT_AXIS)
        base_weight = source.variableAxisValue(_WEIGHT_AXIS) if source.isVariableAxisSet(_WEIGHT_AXIS) else QFontInfo(baseline).weight()
        result.setVariableAxis(_WEIGHT_AXIS, min(900, base_weight + _WEIGHT_INCREMENT))
        return result
    info = QFontInfo(source)
    axis = next((axis for axis in info.variableAxes() if axis.tag() == _WEIGHT_AXIS), None)
    if axis is not None:
        base_weight = source.variableAxisValue(_WEIGHT_AXIS) if source.isVariableAxisSet(_WEIGHT_AXIS) else info.weight()
        result.setVariableAxis(_WEIGHT_AXIS, min(axis.maximumValue(), base_weight + _WEIGHT_INCREMENT))
    else:
        weights = {QFontDatabase.weight(info.family(), style) for style in QFontDatabase.styles(info.family())}
        stronger = [weight for weight in weights if weight > info.weight()]
        if stronger:
            result.setWeight(QFont.Weight(min(stronger)))
    return result


def apply_settings_typography(root: QWidget, theme) -> None:
    """Run within existing Settings style/lazy-construction passes; no watcher."""
    from PySide6.QtWidgets import QWidget

    light = settings_theme_is_light(theme)
    if not light and not _SETTINGS_FONTS:
        return
    for widget in (root, *root.findChildren(QWidget)):
        if widget.property("settingsShadowInternal"):
            continue
        current = widget.font()
        previous = _SETTINGS_FONTS.get(widget)
        if previous is None and current.isVariableAxisSet(_WEIGHT_AXIS):
            ancestor = widget.parentWidget()
            while ancestor is not None:
                inherited = _SETTINGS_FONTS.get(ancestor)
                if inherited is not None and current.variableAxisValue(_WEIGHT_AXIS) == inherited[1].variableAxisValue(_WEIGHT_AXIS):
                    if inherited[0].isVariableAxisSet(_WEIGHT_AXIS):
                        current.setVariableAxis(_WEIGHT_AXIS, inherited[0].variableAxisValue(_WEIGHT_AXIS))
                    else:
                        current.unsetVariableAxis(_WEIGHT_AXIS)
                    break
                ancestor = ancestor.parentWidget()
        if previous is not None:
            original, applied = previous
            if light and current == applied:
                continue
            if current == applied:
                current = QFont(original)
            elif current.isVariableAxisSet(_WEIGHT_AXIS) and current.variableAxisValue(_WEIGHT_AXIS) == applied.variableAxisValue(_WEIGHT_AXIS):
                # QSS can replace the family/weight while retaining the axis
                # installed by this adapter. Remove only our own axis value.
                if original.isVariableAxisSet(_WEIGHT_AXIS):
                    current.setVariableAxis(_WEIGHT_AXIS, original.variableAxisValue(_WEIGHT_AXIS))
                else:
                    current.unsetVariableAxis(_WEIGHT_AXIS)
        if light:
            adjusted = light_palette_font(current)
            _SETTINGS_FONTS[widget] = (QFont(current), QFont(adjusted))
        else:
            adjusted = current
            _SETTINGS_FONTS.pop(widget, None)
        if adjusted != widget.font():
            widget.setFont(adjusted)


def apply_settings_tooltip_typography(theme) -> None:
    """Keep Qt's shared tooltip font in the same reversible presentation policy."""
    from PySide6.QtWidgets import QToolTip

    global _TOOLTIP_FONT
    current = QToolTip.font()
    light = settings_theme_is_light(theme)
    if _TOOLTIP_FONT is not None:
        original, applied = _TOOLTIP_FONT
        if current == applied:
            if light:
                return
            current = QFont(original)
    if light:
        adjusted = light_palette_font(current)
        _TOOLTIP_FONT = (QFont(current), QFont(adjusted))
    else:
        adjusted = current
        _TOOLTIP_FONT = None
    if adjusted != QToolTip.font():
        QToolTip.setFont(adjusted)


class WidgetThemeTypography(QObject):
    """Generation-scoped immutable light-palette input to shared Quick text.

    Runtime Settings admission destroys the old DisplayManager/factory before
    opening the dialog, then creates a new factory after the dialog's own
    destruction barrier. Theme selection therefore cannot leave this input
    stale in a surviving production generation; no live theme observer belongs
    in the text renderer.
    """
    def __init__(self, light: bool, parent=None):
        super().__init__(parent)
        self._light = bool(light)
        if self._light:
            ensure_readability_fonts()

    @Property(bool, constant=True)
    def light(self):
        return self._light

    @Slot(QFont, result=QFont)
    def adjustedFont(self, font):
        return light_palette_font(font) if self._light else QFont(font)
