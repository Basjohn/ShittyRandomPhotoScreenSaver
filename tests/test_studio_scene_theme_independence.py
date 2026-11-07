"""The Studio's scene never follows the Settings theme; only its chrome does (every registered Studio).

Each registered Studio is opened twice through the hidden ``OffscreenStudioSurface``, under the darkest and the
lightest shipped Settings theme (active theme and Studio tokens both), at the same fixture and time. With the chrome
drawn over the scene hidden (toolbars, handles, the frame's border), the viewport slot's pixels must be the same, up to
the documented multisample noise (``tests/_msaa_render_noise.py``).

The leak this guards (6 Nov): production modes draw over their card (transparent backgrounds, translucent bubble
rims), so the themed viewport surface under the render node composited into the scene (Bubble 7-9 levels on its rims;
Spectrum, Sphere, DevCurve, Oscilloscope, Extruded Spectrum: their whole background). The viewport now clears the
scene's region to one fixed backing (``ui.studio.viewport.SCENE_BACKING``), the one snapshots use. The negative
control renders without that clear and finds the theme in the scene.

Nothing shows a window.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPointF

from tests._msaa_render_noise import MSAA_NOISE_LEVELS, MSAA_NOISE_SHARE, msaa_render_difference
from ui.studio.registry import studio_modes

THEMES = sorted((Path(__file__).resolve().parents[1] / "themes").glob("*.srtheme"))


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


def _viewport_luminance(theme) -> float:
    from ui.studio.theme import studio_theme
    text = studio_theme(theme)["viewportBg"].lstrip("#")[-6:]
    return sum(int(text[i:i + 2], 16) for i in (0, 2, 4))


@pytest.fixture(scope="module")
def dark_and_light():
    """The shipped themes whose viewport chrome lies furthest apart (a dark and a light theme)."""
    from ui.settings_theme_io import load_settings_theme_file
    from ui.theme_semantics import settings_theme_is_light
    themes = [load_settings_theme_file(path) for path in THEMES]
    dark = [t for t in themes if not settings_theme_is_light(t)]
    light = [t for t in themes if settings_theme_is_light(t)]
    if not dark or not light:
        pytest.skip("needs a dark and a light shipped theme")
    return min(dark, key=_viewport_luminance), max(light, key=_viewport_luminance)


def _named(root, name):
    found, stack = [], [root]
    while stack:
        item = stack.pop()
        if item.objectName() == name:
            found.append(item)
        stack.extend(item.childItems())
    return found


def _settle(controller, surface, *, analysis: bool) -> None:
    """Pump until the evaluator shows the exact frame: no background analysis (when ``analysis``) and no budgeted
    replay still converging. An engine-answer mode reuses the process's analysed answers (``analysed_cache``), so a
    session after another one starts straight on an exact replay that a frame budget spreads over frames, the frame
    shown before staying meanwhile: a capture taken a few frames after a seek showed the pre-seek (silent) frame."""
    import time
    evaluator = controller.evaluator
    for _ in range(3000):
        surface.pump()
        if (controller.bridge.viewportStatus != "preparing"
                and not (analysis and getattr(evaluator, "analysing", False))
                and not getattr(evaluator, "converging", False)):
            return
        time.sleep(0.005)


def _scene_pixels(qt_app, mode, theme, *, settle: bool = True):
    """The viewport slot's pixels with every chrome item drawn over the scene hidden. ``settle=False`` is the former
    capture (waiting only for the viewport to stop preparing)."""
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.settings_theme_runtime import get_active_settings_theme, set_active_settings_theme
    from ui.studio.controller import StudioController
    from ui.studio.registry import create_adapter
    from ui.studio.surface import OffscreenStudioSurface
    from ui.studio.theme import studio_theme
    disable_per_call_gl_error_checking()
    original = get_active_settings_theme()
    set_active_settings_theme(theme)
    adapter = create_adapter(mode)
    adapter.recorded_clips = lambda: ()
    surfaces = []

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(1600, 900), present_on_show=False))
        return surfaces[0]
    controller = StudioController(adapter, _Store(mode), _Presence(), factory,
                                  theme_provider=lambda: studio_theme(theme))
    try:
        assert controller.open()
        surface = surfaces[0]
        if settle:
            _settle(controller, surface, analysis=True)
        else:
            for _ in range(400):
                surface.pump()
                if controller.bridge.viewportStatus != "preparing":
                    break
        assert controller.bridge.viewportStatus == "live", controller.bridge.viewportError
        controller.seek(2.0)
        surface.pump(2)
        if settle:
            _settle(controller, surface, analysis=False)
        (frame,) = _named(surface.host.root, "viewportFrame")
        slot, viewport = surface.host.slot, surface.viewport
        for child in frame.childItems():                 # toolbars and the border drawn over the scene
            if child is not slot and child.objectName() != "viewportFrameSurface":
                child.setVisible(False)
        for child in slot.childItems():                  # handles, status overlays, letterbox outline
            if child is not viewport:
                child.setVisible(False)
        surface.pump(3)
        image = surface.grab()
        origin = slot.mapToScene(QPointF(0, 0))
        x0, y0 = int(round(origin.x())) + 4, int(round(origin.y())) + 4
        pixels = image[y0:y0 + int(slot.height()) - 8, x0:x0 + int(slot.width()) - 8].copy()
        assert pixels[..., :3].std() > 2.0, "the scene drew nothing"
        return pixels
    finally:
        controller.close()
        set_active_settings_theme(original)


@pytest.mark.parametrize("mode", [entry.mode_id for entry in studio_modes()])
def test_the_scene_is_the_same_under_a_dark_and_a_light_theme(qt_app, dark_and_light, mode):
    dark, light = dark_and_light
    largest, share = msaa_render_difference(_scene_pixels(qt_app, mode, dark), _scene_pixels(qt_app, mode, light))
    assert largest <= MSAA_NOISE_LEVELS and share <= MSAA_NOISE_SHARE, (
        f"{mode}: the scene follows the Settings theme ({largest} levels on {share:.2%} of its pixels)")


def test_without_the_scene_backing_the_theme_leaks_into_the_scene_negative_control(qt_app, dark_and_light,
                                                                                 monkeypatch):
    from ui.studio.viewport import StudioRenderNode
    monkeypatch.setattr(StudioRenderNode, "clear_backing",
                        lambda self, state, viewport, matrix: self.apply_clip(state))
    dark, light = dark_and_light
    for mode in ("bubble", "spectrum"):
        largest, share = msaa_render_difference(_scene_pixels(qt_app, mode, dark), _scene_pixels(qt_app, mode, light))
        assert not (largest <= MSAA_NOISE_LEVELS and share <= MSAA_NOISE_SHARE), (mode, largest, share)


# ----------------------------- the capture is the same whatever an earlier session left in the analysed-answer cache
def _warm_engine_answers(qt_app, mode, theme):
    """A session that waited for its analysis leaves the answers in the process cache (as any earlier test may)."""
    from ui.studio.engine_answers import analysed_cache
    _scene_pixels(qt_app, mode, theme)
    assert analysed_cache(mode), "the warming session left no analysed answers"


def test_a_warm_analysed_answer_cache_still_captures_the_scene(qt_app, dark_and_light):
    """The 6 Nov combined-run failure: any earlier Spectrum session that waited for its analysis made this capture
    black. The capture now waits for the exact frame."""
    dark, _light = dark_and_light
    _warm_engine_answers(qt_app, "spectrum", dark)
    assert _scene_pixels(qt_app, "spectrum", dark)[..., :3].std() > 2.0


def test_the_former_capture_on_a_warm_cache_shows_the_pre_seek_frame_negative_control(qt_app, dark_and_light):
    dark, _light = dark_and_light
    _warm_engine_answers(qt_app, "spectrum", dark)
    with pytest.raises(AssertionError, match="the scene drew nothing"):
        _scene_pixels(qt_app, "spectrum", dark, settle=False)
