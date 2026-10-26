"""Real glyph-weight and exact dark round-trip checks, with fixture palettes."""
from dataclasses import replace

import pytest
from PySide6.QtGui import QFont, QFontInfo, QImage, QPainter, QColor
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.font_registration import ensure_custom_fonts, READABILITY_JOST_FAMILY
from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, Rgba
from ui.theme_typography import light_palette_font, apply_settings_typography, settings_typography_qss


def test_runtime_font_projection_import_does_not_load_qtwidgets():
    from pathlib import Path
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", "import sys; from ui.theme_typography import WidgetThemeTypography, light_palette_font; assert 'PySide6.QtWidgets' not in sys.modules"],
        cwd=root, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr


def _palette(light):
    colors = dict(DEFAULT_DARK_SETTINGS_THEME.colors)
    colors["text.primary"] = Rgba(20,25,30) if light else Rgba(240,245,250)
    colors["panel.group.surface"] = Rgba(240,245,250,110) if light else Rgba(20,25,30,110)
    return replace(DEFAULT_DARK_SETTINGS_THEME, colors=colors)


def _ink(font):
    image = QImage(500,90,QImage.Format.Format_RGBA8888)
    image.fill(0)
    painter = QPainter(image)
    painter.setFont(font)
    painter.setPen(QColor("black"))
    painter.drawText(2,60,"Readable Theme Controls")
    painter.end()
    return sum(bytes(image.constBits())[3::4]), bytes(image.constBits())


@pytest.mark.parametrize("weight", [400,600,700])
def test_light_jost_has_real_intermediate_ink_without_changing_the_source_font(qt_app, weight):
    ensure_custom_fonts()
    source = QFont("Jost",20)
    source.setWeight(QFont.Weight(weight))
    before = QFont(source)
    adjusted = light_palette_font(source)
    assert source == before
    assert adjusted.pointSizeF() == source.pointSizeF()
    assert adjusted.family() == READABILITY_JOST_FAMILY
    assert QFontInfo(adjusted).weight() == QFontInfo(source).weight()+50
    assert _ink(adjusted)[0] > _ink(source)[0]


def test_light_font_copy_retains_italic_features_and_spacing(qt_app):
    source = QFont("Jost",18)
    source.setItalic(True)
    source.setUnderline(True)
    source.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,1.25)
    source.setFeature(QFont.Tag("tnum"),1)
    adjusted = light_palette_font(source)
    assert adjusted.italic() and adjusted.underline()
    assert adjusted.pointSizeF() == source.pointSizeF()
    assert adjusted.letterSpacing() == source.letterSpacing()
    assert adjusted.featureValue(QFont.Tag("tnum")) == 1


def test_shared_qss_family_projection_is_idempotent_and_keeps_other_families(qt_app):
    source = "QLabel { font-family:'jost', 'Segoe UI'; }"
    projected = settings_typography_qss(source, _palette(True))
    assert READABILITY_JOST_FAMILY in projected
    assert "'Segoe UI'" in projected
    assert settings_typography_qss(projected, _palette(True)) == projected


def test_settings_font_policy_is_idempotent_and_restores_dark_pixels(qt_app):
    ensure_custom_fonts()
    root = QWidget()
    label = QLabel("Readable Theme Controls")
    QVBoxLayout(root).addWidget(label)
    base_qss = "QLabel { font-family:'Jost';font-weight:600;font-size:20px; }"
    root.setStyleSheet(base_qss)
    root.ensurePolished()
    label.ensurePolished()
    original = QFont(label.font())
    original_pixels = _ink(original)[1]
    try:
        root.setStyleSheet(settings_typography_qss(base_qss,_palette(True)))
        apply_settings_typography(root,_palette(True))
        first = QFont(label.font())
        assert QFontInfo(first).weight() == 650
        apply_settings_typography(root,_palette(True))
        assert label.font() == first
        root.setStyleSheet(settings_typography_qss(base_qss,_palette(False)))
        apply_settings_typography(root,_palette(False))
        assert _ink(label.font())[1] == original_pixels
        assert label.font() == original
        assert settings_typography_qss(base_qss,_palette(False)) == base_qss
    finally:
        root.deleteLater()
        qt_app.processEvents()


def test_nested_inherited_font_weights_do_not_accumulate_and_restore_dark(qt_app):
    root = QWidget()
    child = QWidget(root)
    label = QLabel("Nested",child)
    base_qss = "* { font-family:'Jost';font-weight:400;font-size:16px; }"
    root.setStyleSheet(base_qss)
    root.ensurePolished()
    child.ensurePolished()
    label.ensurePolished()
    original = QFont(label.font())
    try:
        root.setStyleSheet(settings_typography_qss(base_qss,_palette(True)))
        apply_settings_typography(root,_palette(True))
        assert QFontInfo(label.font()).weight() == 450
        root.setStyleSheet(base_qss)
        apply_settings_typography(root,_palette(False))
        assert label.font() == original
    finally:
        root.deleteLater()
        qt_app.processEvents()


def test_shared_quick_plain_text_keeps_the_complete_dark_font(qt_app):
    from pathlib import Path
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent,QQmlEngine
    root = Path(__file__).resolve().parents[1]/"rendering/quick/qml"
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(b'import QtQuick; Text { font.family: "Jost"; font.pixelSize: 14; font.weight: Font.DemiBold }',QUrl())
    ordinary = component.create()
    themed_component = QQmlComponent(engine)
    themed_component.setData(b'import QtQuick; import "."; ThemedText { sourceFont.family: "Jost"; sourceFont.pixelSize: 14; sourceFont.weight: Font.DemiBold }',QUrl.fromLocalFile(str(root/"test_fixture.qml")))
    themed = themed_component.create()
    assert themed is not None, themed_component.errors()
    try:
        assert themed.property("font") == ordinary.property("font")
    finally:
        ordinary.deleteLater()
        themed.deleteLater()


def test_settings_shared_tooltip_font_is_reversible_and_does_not_accumulate(qt_app):
    from PySide6.QtWidgets import QToolTip
    from ui.theme_typography import apply_settings_tooltip_typography
    original = QFont(QToolTip.font())
    try:
        apply_settings_tooltip_typography(_palette(True))
        first = QFont(QToolTip.font())
        assert QFontInfo(first).weight() > QFontInfo(original).weight()
        apply_settings_tooltip_typography(_palette(True))
        assert QToolTip.font() == first
        apply_settings_tooltip_typography(_palette(False))
        assert QToolTip.font() == original
    finally:
        apply_settings_tooltip_typography(_palette(False))
        QToolTip.setFont(original)


@pytest.mark.parametrize("component_name", ["ThemedText", "ShadowedText"])
def test_shared_quick_text_uses_one_generation_semantic_font_copy(qt_app, component_name):
    from pathlib import Path
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from ui.theme_typography import WidgetThemeTypography

    root = Path(__file__).resolve().parents[1] / "rendering/quick/qml"
    engine = QQmlEngine()
    adapter = WidgetThemeTypography(True, engine)
    engine.rootContext().setContextProperty("widgetThemeTypography", adapter)
    font_property = "sourceFont" if component_name == "ThemedText" else "font"
    component = QQmlComponent(engine)
    component.setData((f'import QtQuick; import "."; {component_name} {{ '
                       f'{font_property}.family: "Jost"; {font_property}.pixelSize: 18; '
                       f'{font_property}.weight: Font.DemiBold; {font_property}.italic: true }}').encode(),
                      QUrl.fromLocalFile(str(root / "test_fixture.qml")))
    item = component.create()
    assert item is not None, component.errors()
    try:
        source = item.property(font_property)
        effective = item.property("font" if component_name == "ThemedText" else "effectiveFont")
        assert source.family() == "Jost"
        assert QFontInfo(effective).weight() == QFontInfo(source).weight() + 50
        assert effective.pixelSize() == source.pixelSize()
        assert effective.italic() == source.italic()
    finally:
        item.deleteLater()
