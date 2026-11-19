"""Start-up gate: compile every ordinary presentation before a display starts.

The scene factory eagerly compiles every family. One duplicate property (even in
an unused family) prevents the entire screensaver engine from starting. This is
the same production gate, not an approximate standalone QML component probe.
"""
from __future__ import annotations

import pytest


@pytest.mark.qt
def test_all_presentation_components_compile_at_scene_factory_startup(qt_app) -> None:
    from rendering.quick.scene_controller import QuickSceneFactory

    factory = QuickSceneFactory()
    try:
        assert factory.is_ready
    finally:
        factory.deleteLater()
        qt_app.processEvents()
