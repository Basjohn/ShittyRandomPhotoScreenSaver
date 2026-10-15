"""Opt-in QApplication fixture for focused GL tests without storage/env setup.

    python -m pytest --noconftest -p tools.pytest_qt_noenv tests/test_neon_lake_renderer.py

This plugin provides only ``qt_app``. It does not replace the full suite's lifecycle,
storage or QML-import fixtures. Tests selected with it must own their data/lifetimes.
Qt's public APIs select OpenGL and its surface format; no environment is modified.
"""
import pytest


@pytest.fixture(scope="session")
def qt_app():
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QSurfaceFormat
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
    from PySide6.QtWidgets import QApplication
    from rendering.quick.bootstrap import QUICK_OPENGL_VERSION

    app = QCoreApplication.instance()
    if app is not None and not isinstance(app, QApplication):
        raise RuntimeError("focused Qt test requires QApplication; existing application cannot be replaced")
    if app is None:
        fmt = QSurfaceFormat()
        fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setVersion(*QUICK_OPENGL_VERSION)
        fmt.setDepthBufferSize(24)
        QSurfaceFormat.setDefaultFormat(fmt)
        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
        app = QApplication([])
    yield app
