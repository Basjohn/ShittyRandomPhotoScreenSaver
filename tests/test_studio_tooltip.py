"""The Studio's one tooltip form: wrapped, width-bounded, inside the window and drawn in the open Studio's theme.

Every ``C.ToolTip`` in ``ui/studio/qml/StudioShell.qml`` shows Qt's single shared tooltip; the shell styles that
instance once. Before (1B.4 side defect), a long row tip was one unwrapped line that ran off the window, in the
style's fixed black. The instance outlives one Studio (it belongs to the engine), so a second Studio must restyle
it with its own theme. Hidden surfaces only.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor

THEMES = sorted((Path(__file__).resolve().parents[1] / "themes").glob("*.srtheme"))
LONG_TIP = " ".join(["A long row tooltip sentence that keeps going so it is far wider than any window."] * 6)


def _items(root):
    stack = [root]
    while stack:
        item = stack.pop()
        yield item
        stack.extend(item.childItems())


def _shown(item):
    while item is not None:
        if not item.isVisible():
            return False
        item = item.parentItem()
    return True


def _skin(light: bool):
    from ui.settings_theme_io import load_settings_theme_file
    from ui.studio.theme import studio_theme
    for path in THEMES:
        skin = studio_theme(load_settings_theme_file(path))
        if (skin["light"] == "true") == light:
            return skin
    pytest.skip(f"no {'light' if light else 'dark'} theme file")


def _open(skin):
    from tools.waveform_studio_capture import MemoryStore, NoPresence
    from core.settings.visualizer_presets import get_preset_names, resolve_visualizer_activation_payload
    from ui.studio.controller import StudioController
    from ui.studio.registry import create_adapter
    from ui.studio.surface import OffscreenStudioSurface
    values = dict(resolve_visualizer_activation_payload({"mode": "spectrum", "preset_spectrum": 0},
                                                        mode="spectrum").resolved_config)
    adapter = create_adapter("spectrum")
    adapter.recorded_clips = lambda: ()
    surfaces = []

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(1200, 760), present_on_show=False))
        return surfaces[0]

    controller = StudioController(adapter, MemoryStore(values, get_preset_names("spectrum")[0]), NoPresence(),
                                  factory, theme_provider=lambda: skin)
    assert controller.open()
    return controller, surfaces[0]


def _hover_long_tip(surface):
    from tools.studio_shape_capture import Pointer, settle
    root = surface.host.root
    settle(surface, 1.0)                       # the panels lay out on rendered frames
    labels = [item for item in _items(root)
              if item.property("propId") not in (None, "") and item.property("tip") is not None and _shown(item)]
    # The top row of the right-hand panel (rows further down can sit below its scrolled view).
    label = min(labels, key=lambda item: (-item.mapToScene(QPointF(0.0, 0.0)).x(),
                                          item.mapToScene(QPointF(0.0, 0.0)).y()))
    label.setProperty("tip", LONG_TIP)
    settle(surface, 0.2)
    Pointer(surface, label).hover(label.width() / 2.0, label.height() / 2.0)
    deadline = time.perf_counter() + 5.0
    while time.perf_counter() < deadline:
        surface.pump()
        backgrounds = [item for item in _items(surface.window.contentItem())
                       if item.objectName() == "studioTipBackground" and _shown(item)]
        if backgrounds and backgrounds[0].width() > 0:
            return root, backgrounds[0]
        time.sleep(0.02)
    raise AssertionError("the long row tooltip never showed")


def _check(controller, surface):
    root, background = _hover_long_tip(surface)
    window = surface.window
    top_left = background.mapToScene(QPointF(0.0, 0.0))
    limit = float(root.property("tipMaxWidth"))
    texts = [item for item in _items(window.contentItem()) if item.objectName() == "studioTipText" and _shown(item)]
    assert len(texts) == 1, [text.parentItem() for text in texts]
    text = texts[0]
    assert text.parentItem() is background.parentItem(), "the tip's text is not inside its popup"
    # Bounded and wrapped: the tip is no wider than the Studio's bound, which is far narrower than the line.
    assert float(text.property("implicitWidth")) > limit
    assert background.width() <= limit + 0.5
    assert text.property("lineCount") > 1
    # Inside the window on every side.
    assert top_left.x() >= 0 and top_left.y() >= 0
    assert top_left.x() + background.width() <= window.width() + 0.5
    assert top_left.y() + background.height() <= window.height() + 0.5
    # Drawn in this Studio's theme: the shell's raised surface (opaque) and its text role.
    raised, ink = QColor(root.property("cRaised")), QColor(root.property("cText"))
    fill = QColor(background.property("color"))
    assert (fill.red(), fill.green(), fill.blue(), fill.alpha()) == (raised.red(), raised.green(), raised.blue(), 255)
    assert QColor(text.property("color")) == ink
    return fill


def test_a_long_row_tip_wraps_inside_the_window_in_each_studios_theme(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    fills = []
    for light in (False, True):              # the second Studio reuses the engine's shared tooltip instance
        controller, surface = _open(_skin(light))
        try:
            fills.append(_check(controller, surface))
        finally:
            controller.close()
    assert fills[0] != fills[1], "the second Studio kept the first Studio's tooltip theme"
