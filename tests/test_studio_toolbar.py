"""The viewport toolbar never shows the scene through its chips and buttons (every mode's shared shell).

Each toolbar group sits on an opaque themed backing. Proven on the real shell with each mode's production renderer
at two different instants of a busy fixture: the toolbar's pixels do not change while the scene under it does. The
negative control makes one backing translucent and the same check fails. Nothing shows a window.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF


class _Store:
    def __init__(self, mode):
        from core.settings.visualizer_presets import resolve_visualizer_activation_payload
        self.values = dict(resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": 0},
                                                                 mode=mode).resolved_config)

    def snapshot(self):
        return dict(self.values)

    def commit(self, values, changed):
        self.values.update(values)
        return dict(self.values)

    def preset_label(self):
        return "Preset"


class _Presence:
    concealed = False

    def conceal(self):
        pass

    def reveal(self):
        pass


def _backings(root):
    out = []

    def walk(item):
        for child in item.childItems():
            if child.objectName() == "toolbarBacking":
                out.append(child)
            walk(child)
    walk(root)
    return out


def _rect(item):
    top_left = item.mapToScene(QPointF(0, 0))
    return int(top_left.x()), int(top_left.y()), int(item.width()), int(item.height())


@pytest.fixture
def studio(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.studio.controller import StudioController
    from ui.studio.registry import create_adapter
    from ui.studio.surface import OffscreenStudioSurface
    disable_per_call_gl_error_checking()
    opened = []

    def open_mode(mode):
        adapter = create_adapter(mode)
        adapter.recorded_clips = lambda: ()
        surfaces = []

        def factory(controller):
            surfaces.append(OffscreenStudioSurface(controller, size=(1280, 760), present_on_show=False))
            return surfaces[0]
        controller = StudioController(adapter, _Store(mode), _Presence(), factory)
        assert controller.open()
        opened.append(controller)
        surface = surfaces[0]
        for _ in range(400):
            surface.pump()
            if controller.bridge.viewportStatus != "preparing":
                break
        assert controller.bridge.viewportStatus == "live", controller.bridge.viewportError
        return controller, surface
    yield open_mode
    for controller in opened:
        controller.close()


def _toolbar_and_scene(controller, surface, seconds):
    import numpy as np
    controller.select_fixture("peak", user=True)
    controller.seek(seconds)
    surface.pump(3)
    image = surface.grab()[..., :3].astype(np.int16)
    backings = [_rect(b) for b in _backings(surface.host.root) if b.isVisible()]
    # Everything inside the backing's border except its anti-aliased rounded corners.
    toolbar = [image[y + 2:y + h - 2, x + 10:x + w - 10] for x, y, w, h in backings]
    slot = surface.host.slot
    sx, sy, sw, sh = _rect(slot)
    scene = image[sy + sh // 3: sy + 2 * sh // 3, sx + sw // 4: sx + 3 * sw // 4]
    return toolbar, scene


def _scene_shows_through(controller, surface) -> bool:
    import numpy as np
    first, scene_a = _toolbar_and_scene(controller, surface, 2.0)
    second, scene_b = _toolbar_and_scene(controller, surface, 7.3)
    assert np.abs(scene_a - scene_b).mean() > 1.0          # the scene under the toolbar did change
    # Text rasterization may differ by one level between frames; the scene showing through differs by far more.
    return any(np.abs(a - b).max() > 8 for a, b in zip(first, second))


@pytest.mark.parametrize("mode", ["bubble", "waveform_ribbon"])
def test_toolbar_backings_are_opaque_and_hide_the_scene(studio, mode):
    controller, surface = studio(mode)
    backings = [b for b in _backings(surface.host.root) if b.isVisible()]
    assert len(backings) == 2
    for backing in backings:
        assert backing.property("color").alphaF() == pytest.approx(1.0)
    assert not _scene_shows_through(controller, surface)


def test_a_translucent_backing_lets_the_scene_through_negative_control(studio):
    from PySide6.QtGui import QColor
    controller, surface = studio("bubble")
    backing = next(b for b in _backings(surface.host.root) if b.isVisible())
    colour = QColor(backing.property("color"))
    colour.setAlphaF(0.2)
    backing.setProperty("color", colour)
    assert _scene_shows_through(controller, surface)


def _named(root, name):
    found = []

    def walk(item):
        for child in item.childItems():
            if child.objectName() == name:
                found.append(child)
            walk(child)
    walk(root)
    return found[0]


def _frame_hidden_by_scrub_bar(surface) -> bool:
    slot = surface.host.slot
    scrub = _named(surface.host.root, "scrubBar")
    frame_bottom = slot.mapToScene(QPointF(0, slot.property("frameY") + slot.property("frameHeight"))).y()
    return frame_bottom > scrub.mapToScene(QPointF(0, 0)).y() + 0.5 or scrub.property("color").alphaF() < 1.0


@pytest.mark.parametrize("mode", ["bubble", "waveform_ribbon"])
def test_no_part_of_the_frame_lies_under_the_opaque_scrub_bar(studio, mode):
    controller, surface = studio(mode)
    for framing in controller.framings:
        controller.select_framing(framing.id)
        surface.pump(2)
        assert not _frame_hidden_by_scrub_bar(surface), framing.id


def test_a_frame_running_under_the_scrub_bar_is_detected_negative_control(studio):
    controller, surface = studio("bubble")
    slot = surface.host.slot
    slot.setHeight(slot.height() + 40)               # the old layout: the slot ran under the scrub bar
    surface.pump(2)
    assert _frame_hidden_by_scrub_bar(surface)
