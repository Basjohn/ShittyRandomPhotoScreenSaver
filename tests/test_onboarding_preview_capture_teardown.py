"""The onboarding preview foundry's hidden Quick scene owns its imported GL context through its render control (R-172).

The render control's RHI keeps using the context it imported until its own destructor, so the context must never be
freed first. Two independent Python owners let PySide's interpreter-exit sweep (or GC) free them in either order; as
the control's Qt children they always go after it. The scene is a never-shown QQuickRenderControl window.
"""
from __future__ import annotations

import sys

import pytest
import shiboken6

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="the foundry's hidden Windows-QPA GL scene")


@pytest.fixture
def scene(qt_app):
    from tools.onboarding_preview_foundry import _HiddenQuickScene
    made = _HiddenQuickScene(320, 200, dpr=1.0)
    made.render()
    yield made
    if shiboken6.isValid(made.control):
        made.close()


def _context_freed_before_control(scene) -> bool:
    """Would a sweep of Python-owned QObjects (any order) be able to free the context before the control?"""
    return shiboken6.ownedByPython(scene.context) or shiboken6.ownedByPython(scene.surface)


def test_the_context_and_surface_are_the_render_controls_children(scene):
    assert scene.context.parent() is scene.control and scene.surface.parent() is scene.control
    assert not _context_freed_before_control(scene)


def test_close_destroys_the_scene_render_control_last(scene):
    events = []
    scene.window.destroyed.connect(lambda *_a: events.append("window"))
    scene.control.destroyed.connect(lambda *_a: events.append("control"))
    scene.context.aboutToBeDestroyed.connect(lambda: events.append("context"))
    context, surface = scene.context, scene.surface
    scene.close()
    assert events == ["window", "control", "context"]
    assert not shiboken6.isValid(context) and not shiboken6.isValid(surface)


def test_a_context_with_its_own_python_owner_is_flagged_negative_control(scene):
    scene.context.setParent(None)                     # the former structure; only the check runs, never the sweep
    try:
        assert _context_freed_before_control(scene)
    finally:
        scene.context.setParent(scene.control)
    assert not _context_freed_before_control(scene)
