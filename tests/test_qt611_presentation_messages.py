"""Production QML and painted onboarding fonts must not emit malformed-property warnings."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtCore import QRect, QtMsgType, QUrl, qInstallMessageHandler
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtQml import QQmlComponent, QQmlEngine

from core.settings.default_settings import DEFAULT_SETTINGS
from rendering.quick.bootstrap import quick_qml_root
from rendering.quick.widgets.preferred_size_measurement import OrdinaryPreferredSizeMeter
from rendering.widget_descriptors import get_widget_runtime_descriptors
from ui.onboarding.arrange import _ArrangeCanvas
from ui.onboarding.arrange_model import ArrangeDisplay, ArrangeModel
from ui.onboarding.basic_pages import _PracticeStoryCard
from ui.onboarding.common import font_with_point_delta
from ui.onboarding.selection_pages import TransitionStrip


def test_every_canonical_qml_component_parses_without_native_warnings(qt_app):
    messages = []
    previous = qInstallMessageHandler(lambda level, context, text: messages.append((level, text)))
    engine = QQmlEngine()
    try:
        root = quick_qml_root()
        engine.addImportPath(str(root))
        paths = sorted(root.rglob("*.qml"))
        assert paths
        for path in paths:
            component = QQmlComponent(engine, QUrl.fromLocalFile(str(path)))
            assert component.isReady(), (path.name, [error.toString() for error in component.errors()])
            component.deleteLater()
    finally:
        engine.deleteLater()
        qt_app.processEvents()
        qInstallMessageHandler(previous)
    assert not [text for level, text in messages if level in
                (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg)]


def test_every_ordinary_family_constructs_without_qml_or_font_warnings(qt_app):
    messages = []
    previous = qInstallMessageHandler(lambda level, context, text: messages.append((context.category, text)))
    meter = OrdinaryPreferredSizeMeter()
    try:
        widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
        for descriptor in get_widget_runtime_descriptors():
            widget_id = descriptor.widget_id
            if widget_id == "spotify_visualizer":
                continue
            assert all(value > 0 for value in meter.measure(widget_id, widgets))
        widgets["clock"]["display_mode"] = "analog"
        assert all(value > 0 for value in meter.measure("clock", widgets))
    finally:
        meter.close()
        qInstallMessageHandler(previous)
    assert not [text for category, text in messages if category.startswith("qt.qml")
                or "QFont::" in text or "ReferenceError" in text or "TypeError" in text]


@pytest.mark.parametrize("pixel_sized", [True, False])
def test_onboarding_paint_uses_a_positive_size_in_the_fonts_original_units(qt_app, pixel_sized):
    card = _PracticeStoryCard()
    strip = TransitionStrip()
    meter = OrdinaryPreferredSizeMeter()
    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    widgets["family_activation"] = {family: False for family in widgets["family_activation"]}
    display = ArrangeDisplay("screen:paint", ("screen:paint",), QRect(0, 0, 800, 600), "1")
    canvas = _ArrangeCanvas(ArrangeModel(widgets, (display,), meter=meter))
    painted = (card, strip, canvas)
    messages = []
    try:
        font = QFont("Jost")
        if pixel_sized:
            font.setPixelSize(14)
        else:
            font.setPointSizeF(10.5)
        for widget in painted:
            widget.setFont(font)
            widget.resize(600, 160)
            widget.ensurePolished()
        strip.set_transition("blinds")
        previous = qInstallMessageHandler(lambda level, context, text: messages.append(text))
        try:
            for widget in painted:
                widget.render(QPixmap(widget.size()))
                larger = font_with_point_delta(widget, 1.5)
                smaller = font_with_point_delta(widget, -1.0)
                if pixel_sized:
                    assert larger.pixelSize() > 14 > smaller.pixelSize() > 0
                else:
                    assert larger.pointSizeF() == 12.0 and smaller.pointSizeF() == 9.5
            tiny = QFont(font)
            tiny.setPixelSize(1) if pixel_sized else tiny.setPointSizeF(1)
            canvas.setFont(tiny)
            canvas.render(QPixmap(canvas.size()))
            minimum = font_with_point_delta(canvas, -1, minimum_points=7)
            assert (minimum.pixelSize() == round(7 * canvas.logicalDpiY() / 72)
                    if pixel_sized else minimum.pointSizeF() == 7)
        finally:
            qInstallMessageHandler(previous)
        assert not [text for text in messages if "QFont::" in text]
    finally:
        for widget in painted:
            widget.deleteLater()
        meter.close()


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows 11 style regression")
def test_windows11_combo_fonts_keep_original_text_metrics_without_native_size_warning():
    source = '''
import json, sys
from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtGui import QFontInfo, QFontMetrics
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
app = QApplication([])
assert app.setStyle("windows11") is not None
messages = []
previous = qInstallMessageHandler(lambda level, context, text: messages.append(text))
from ui.tabs import shared_styles
from ui.widgets.styled_font_combo_box import StyledFontComboBox
from ui.widgets.styled_combo_box import StyledComboBox
style = shared_styles.COMBOBOX_STYLE
if sys.argv[1] == "old":
    for before, after in (("10.5pt", "14px"), ("9.75pt", "13px"), ("9pt", "12px")):
        style = style.replace(before, after)
parent = QWidget()
parent.setStyleSheet(style)
layout = QVBoxLayout(parent)
metrics = []
for kind in (StyledFontComboBox, StyledComboBox):
    for size in ("regular", "compact", "mini", "hero"):
        control = kind(parent, size_variant=size)
        if kind is StyledComboBox:
            control.addItems(["Jost", "Inter"])
        layout.addWidget(control)
        control.ensurePolished()
        font = control.font()
        info = QFontInfo(font)
        fm = QFontMetrics(font)
        metrics.append([kind.__name__, size, info.pixelSize(), fm.height(), fm.horizontalAdvance("Jost Inter")])
        if sys.argv[1] == "new":
            assert font.pointSizeF() > 0
parent.show()
app.processEvents()
control.showPopup()
app.processEvents()
control.hidePopup()
parent.close()
app.processEvents()
qInstallMessageHandler(previous)
print(json.dumps({"font_warnings": [m for m in messages if "QFont::" in m], "metrics": metrics}))
'''
    reports = []
    for mode in ("old", "new"):
        result = subprocess.run([sys.executable, "-c", source, mode], cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stdout + result.stderr
        reports.append(json.loads(result.stdout))
    old, new = reports
    assert any("Point size <= 0 (-1)" in message for message in old["font_warnings"])
    assert new["font_warnings"] == []
    assert new["metrics"] == old["metrics"]
