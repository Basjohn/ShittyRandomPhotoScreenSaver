"""Native mandatory FEEDS gate: detect invalid custom QML component properties.

A source test cannot catch 'Cannot assign to non-existent property wrapMode';
load the real file through the same QQmlComponent path as QuickSceneFactory.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine

pytestmark = pytest.mark.usefixtures("qt_app")
QML_ROOT = Path(__file__).resolve().parents[1] / "rendering" / "quick" / "qml"


def test_feed_presentation_qml_component_compiles_with_shadowed_text_contract(qt_app):
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_ROOT / "FeedPresentation.qml")))
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
