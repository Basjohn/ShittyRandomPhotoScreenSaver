"""Deterministic process bootstrap for the production Qt Quick presenter.

Environment selection is deliberately separated from Qt configuration so the
render loop and QML root can be fixed before importing Qt.  Graphics and
surface selection must still happen before QApplication and before any Quick
window or scene graph is created.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any


QUICK_RENDER_LOOP = "threaded"
QUICK_OPENGL_VERSION = (4, 1)
QUICK_QML_IMPORT_ENV = "QML_IMPORT_PATH"


@dataclass(frozen=True)
class QuickBootstrapState:
    """Resolved process-level presentation configuration."""

    render_loop: str
    graphics_api: str
    qml_root: Path
    surface_format: Any
    surface_preferences: Any


def quick_qml_root() -> Path:
    """Return the package-owned root for runtime QML data and imports."""

    return Path(__file__).resolve().parent / "qml"


def _prepend_environment_path(name: str, path: Path) -> None:
    resolved = str(path.resolve())
    existing = [part for part in os.environ.get(name, "").split(os.pathsep) if part]
    resolved_key = os.path.normcase(os.path.normpath(resolved))
    if any(
        os.path.normcase(os.path.normpath(part)) == resolved_key
        for part in existing
    ):
        return
    os.environ[name] = os.pathsep.join((resolved, *existing))


def configure_quick_environment() -> Path:
    """Fix the Quick render loop and package QML root before Qt startup."""

    root = quick_qml_root()
    if not root.is_dir():
        raise RuntimeError(f"Qt Quick QML root is unavailable: {root}")

    # This is a production architecture choice, not a user/runtime fallback.
    os.environ["QSG_RENDER_LOOP"] = QUICK_RENDER_LOOP
    _prepend_environment_path(QUICK_QML_IMPORT_ENV, root)
    return root


def configure_quick_graphics(*, reason: str = "quick-bootstrap") -> QuickBootstrapState:
    """Select the production Quick graphics API and global surface format.

    This function intentionally fails if a Qt application already exists.  A
    late call could leave an already-created Quick scene on a different render
    loop, graphics API, or surface format and would make the process topology
    nondeterministic.
    """

    qml_root = configure_quick_environment()

    # Keep these imports local: configure_quick_environment() must be callable
    # before the process imports Qt at all.
    from PySide6.QtCore import QCoreApplication, Qt
    from PySide6.QtGui import QSurfaceFormat
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

    if QCoreApplication.instance() is not None:
        raise RuntimeError(
            "Qt Quick graphics bootstrap must run before QApplication creation"
        )

    from rendering.gl_format import build_surface_format

    QCoreApplication.setAttribute(
        Qt.ApplicationAttribute.AA_UseDesktopOpenGL,
        True,
    )
    QCoreApplication.setAttribute(
        Qt.ApplicationAttribute.AA_ShareOpenGLContexts,
        True,
    )

    surface_format, surface_preferences = build_surface_format(reason=reason)
    surface_format.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    surface_format.setVersion(*QUICK_OPENGL_VERSION)
    surface_format.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    QSurfaceFormat.setDefaultFormat(surface_format)

    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)

    return QuickBootstrapState(
        render_loop=os.environ["QSG_RENDER_LOOP"],
        graphics_api="OpenGL",
        qml_root=qml_root,
        surface_format=surface_format,
        surface_preferences=surface_preferences,
    )
