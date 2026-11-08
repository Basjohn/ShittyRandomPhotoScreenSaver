"""The Studio window wears Settings' chrome through Settings' own owners (every registered Studio: one shell).

* Frameless, with the shell's custom title bar and the forged rounded edge painted by the same painter
  Settings' edge overlay calls (``ui.settings_window_edge``).
* The native material follows the active Settings theme through the shared mode -> AccentPolicy mapping
  (``core.windows.dwm_blur.apply_backdrop``): Normal is an opaque window with no backdrop call.
* Card and section frames stroke their border as ONE path (no seams on a translucent border; the negative control
  strokes it in QSS-like pieces and seams).
* The viewport's scene is clipped to the frame's rounded corners (read back from a hidden render whose scene fills
  its slot with magenta; the negative control puts the slot back at the frame's square corner).
* Chrome paints are static: idle frames repaint nothing and request nothing.

Nothing shows a window: the visible-window surface is built but never shown, everything else renders through the
hidden ``OffscreenStudioSurface``.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen


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


def _named(root, name):
    found, stack = [], [root]
    while stack:
        item = stack.pop()
        if item.objectName() == name:
            found.append(item)
        stack.extend(item.childItems())
    return found


def _theme(name):
    from pathlib import Path
    from ui.settings_theme_io import load_settings_theme_file
    return load_settings_theme_file(next(Path("themes").glob(name)))


class _MagentaRenderer:
    """A scene that fills everything it may draw (its slot's scissor) with magenta."""

    def prepare(self, card, frame):
        return True

    def render(self, card, frame):
        from OpenGL import GL as gl
        gl.glClearColor(1.0, 0.0, 1.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

    def release(self):
        pass


@pytest.fixture
def studio(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.studio.controller import StudioController
    from ui.studio.registry import create_adapter
    from ui.studio.surface import OffscreenStudioSurface
    from ui.studio.theme import studio_theme
    disable_per_call_gl_error_checking()
    opened = []

    def open_mode(mode, *, renderer=None, theme=None):
        adapter = create_adapter(mode)
        adapter.recorded_clips = lambda: ()
        if renderer is not None:
            adapter.create_renderer = renderer
        surfaces = []

        def factory(controller):
            surfaces.append(OffscreenStudioSurface(controller, size=(1600, 900), present_on_show=False))
            return surfaces[0]
        controller = StudioController(adapter, _Store(mode), _Presence(), factory,
                                      theme_provider=(lambda: studio_theme(theme)) if theme is not None else None)
        assert controller.open()
        opened.append(controller)
        surface = surfaces[0]
        for _ in range(400):
            surface.pump()
            if controller.bridge.viewportStatus != "preparing":
                break
        return controller, surface
    yield open_mode
    for controller in opened:
        controller.close()


# ----------------------------------------------------------------- frameless + title bar
def test_the_studio_window_is_frameless_with_the_settings_title_bar_and_edge(studio, qt_app, monkeypatch):
    import ui.settings_dialog as settings_dialog
    import ui.settings_window_edge as edge
    from ui.studio.chrome import StudioWindowEdge
    from ui.studio.surface import StudioWindowSurface

    # Same edge painter as Settings: Settings' edge overlay (ForgedWindowEdgeOverlay.paintEvent) calls this very function.
    assert settings_dialog.ForgedWindowEdgeOverlay is edge.ForgedWindowEdgeOverlay
    calls = []
    original = edge.paint_forged_window_edge
    monkeypatch.setattr(edge, "paint_forged_window_edge", lambda *a, **k: (calls.append(k), original(*a, **k)))

    controller, surface = studio("waveform_ribbon")
    root = surface.host.root
    (title_bar,) = _named(root, "studioTitleBar")
    buttons = [b.property("action") for b in _named(root, "titleBarButton")]
    assert sorted(buttons) == ["close", "maximize", "minimize"]
    (window_edge,) = _named(root, "studioWindowEdge")
    assert isinstance(window_edge, StudioWindowEdge)
    assert window_edge.z() > max(item.z() for item in root.childItems() if item is not window_edge
                                 and item.objectName() != "resizeEdge")
    surface.pump()
    assert calls and calls[0]["maximized"] is False
    # Every existing header control is still there, under the title bar.
    for name in ("presetPill", "helpButton", "closeButton"):
        (item,) = _named(root, name)
        assert item.mapToScene(QPointF(0, 0)).y() >= title_bar.height()

    # The visible window (built, never shown) is frameless.
    window_surface = StudioWindowSurface(controller)
    try:
        assert window_surface.window.flags() & Qt.WindowType.FramelessWindowHint
        assert not window_surface.window.isVisible()
    finally:
        window_surface.host.retire()
        window_surface.window.deleteLater()
        window_surface.host.release_engine()


# ----------------------------------------------------------------- material follows the theme
def _theme_with_mode(mode):
    """The first shipped Settings theme on ``mode`` (themes are authored content: picked by property, never name)."""
    from pathlib import Path
    from ui.settings_theme_io import load_settings_theme_file
    for path in sorted(Path("themes").glob("*.srtheme")):
        theme = load_settings_theme_file(path)
        if theme.backdrop.mode == mode:
            return theme
    pytest.skip(f"no shipped Settings theme uses {mode}")


@pytest.mark.parametrize("mode", ["off", "acrylic", "glass", "frosted", "mica", "smoked"])
def test_normal_and_materials_follow_the_active_theme(studio, monkeypatch, mode):
    from core import platform_paths
    from ui.studio.surface import StudioWindowSurface
    from ui.studio.theme import studio_theme
    theme = _theme_with_mode(mode)
    # The Windows contract: the material shows through the window surface (off Windows it is composed over the
    # opaque underlay instead, tests/test_linux_settings_material_underlay.py).
    monkeypatch.setattr(platform_paths, "IS_WINDOWS", True)
    tokens = studio_theme(theme)
    assert tokens["backdrop"] == mode
    window_alpha = QColor(tokens["windowSurface"]).alphaF()
    if mode == "off":
        assert window_alpha == 1.0 and float(tokens["panelAlpha"]) == 1.0
    else:
        assert window_alpha < 1.0 and float(tokens["panelAlpha"]) < 1.0

    calls = []
    monkeypatch.setattr("core.windows.dwm_blur.apply_backdrop",
                        lambda hwnd, applied_mode, tint=None: calls.append((applied_mode, tint)) or True)
    controller, _surface = studio("waveform_ribbon")
    window_surface = StudioWindowSurface(controller, theme=theme)
    try:
        window_surface.window.winId = lambda: 4242          # never create or show the native window
        assert window_surface.material == mode
        assert (window_surface.window.format().alphaBufferSize() == 8) == (mode != "off")
        window_surface.apply_backdrop()
        window_surface.apply_backdrop()                      # once, like Settings' first show
        assert calls == ([] if mode == "off" else [(mode, theme.backdrop.native_tint())])
    finally:
        window_surface.host.retire()
        window_surface.window.deleteLater()
        window_surface.host.release_engine()


def test_settings_uses_the_same_backdrop_mapping(monkeypatch):
    """SettingsDialog's native backdrop goes through the shared mapping the Studio uses."""
    from dataclasses import replace
    from core import platform_paths
    from ui.settings_dialog import SettingsDialog
    from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, NativeBackdropStyle, Rgba
    calls = []
    monkeypatch.setattr(platform_paths, "IS_WINDOWS", True)
    monkeypatch.setattr("core.windows.dwm_blur.apply_backdrop",
                        lambda hwnd, mode, tint=None: calls.append((hwnd, mode)) or True)

    class _Dialog:
        _apply_native_backdrop_theme = SettingsDialog._apply_native_backdrop_theme
        _native_backdrop_mode = None
        _backdrop_applied = False

        def winId(self):
            return 7

    theme = replace(DEFAULT_DARK_SETTINGS_THEME, backdrop=NativeBackdropStyle(mode="acrylic", tint=Rgba(1, 2, 3, 90)))
    assert _Dialog()._apply_native_backdrop_theme(theme) is True
    assert calls == [(7, "acrylic")]


# ----------------------------------------------------------------- one-path borders, no seams
def _frame(width=120.0, height=80.0, stroke=QColor(255, 255, 255, 110)):
    from ui.studio.chrome import StudioFrame
    frame = StudioFrame()
    frame.setWidth(width)
    frame.setHeight(height)
    frame.setProperty("radius", 10.0)
    frame.setProperty("strokeWidth", 1.5)
    frame.setProperty("strokeColor", stroke)
    return frame


class _RecordingPainter(QPainter):
    def __init__(self, device):
        super().__init__(device)
        self.strokes = []

    def drawPath(self, path):  # noqa: N802 - Qt override
        self.strokes.append(QPainterPath(path))
        super().drawPath(path)


def _ring_alpha(image: QImage, rect: QRectF, radius: float, width: float):
    """Alpha along the middle of the border stroke: every straight edge and every corner arc."""
    import math
    inset = width / 2.0
    r = radius - inset
    left, top, right, bottom = rect.left() + inset, rect.top() + inset, rect.right() - inset, rect.bottom() - inset
    samples = []
    for k in range(0, 360, 3):                         # the four corner arcs
        a = math.radians(k)
        for cx, cy, sx, sy in ((left + r, top + r, -1, -1), (right - r, top + r, 1, -1),
                               (left + r, bottom - r, -1, 1), (right - r, bottom - r, 1, 1)):
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            if (x - cx) * sx >= 0 and (y - cy) * sy >= 0:
                samples.append(image.pixelColor(int(x), int(y)).alpha())
    for x in range(int(left + r + 2), int(right - r - 2), 4):   # the straight edges
        samples.append(image.pixelColor(x, int(top)).alpha())
        samples.append(image.pixelColor(x, int(bottom)).alpha())
    return samples


def _render_frame(frame, scale=8):
    image = QImage(int(frame.width() * scale), int(frame.height() * scale), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = _RecordingPainter(image)
    painter.scale(scale, scale)
    frame.paint(painter)
    painter.end()
    return image, painter.strokes


def test_card_borders_are_one_continuous_path(qt_app):
    frame = _frame()
    image, strokes = _render_frame(frame)
    assert len(strokes) == 1                                   # stroked once
    assert len(strokes[0].toSubpathPolygons()) == 1            # one closed path
    assert frame.property("strokeWidth") == 1.5               # 0.5 px thicker than the former 1 px
    straight = [a for a in _ring_alpha(image, QRectF(0, 0, 120 * 8, 80 * 8), 80.0, 12.0)]
    # A translucent border composites once everywhere: no brighter join anywhere along the ring.
    assert max(straight) - min(straight) <= 6, (min(straight), max(straight))


def test_a_border_stroked_in_pieces_seams_negative_control(qt_app):
    """QSS draws a rounded border as edge and corner pieces whose antialiased ends overlap (R-101)."""
    from ui.widgets.continuous_border import rounded_border_path
    scale = 8
    image = QImage(120 * scale, 80 * scale, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(scale, scale)
    pen = QPen(QColor(255, 255, 255, 110), 1.5)
    pen.setCapStyle(Qt.PenCapStyle.SquareCap)
    painter.setPen(pen)
    path = rounded_border_path(QRectF(0, 0, 120, 80), 1.5, 10.0)
    polygon = path.toSubpathPolygons()[0]
    # The same outline in pieces: each segment its own stroke, so the capped ends overlap at every join.
    step = max(1, polygon.size() // 24)
    for index in range(0, polygon.size() - step, step):
        piece = QPainterPath(polygon[index])
        piece.lineTo(polygon[min(polygon.size() - 1, index + step)])
        painter.drawPath(piece)
    painter.end()
    samples = _ring_alpha(image, QRectF(0, 0, 120 * scale, 80 * scale), 80.0, 12.0)
    assert max(samples) - min(samples) > 6


# ----------------------------------------------------------------- viewport corners
def _corner_pixels(controller, surface):
    import numpy as np
    surface.pump(3)
    image = surface.grab()
    (frame,) = _named(surface.host.root, "viewportFrame")
    origin = frame.mapToScene(QPointF(0, 0))
    x0, y0 = int(round(origin.x())), int(round(origin.y()))
    x1 = x0 + int(round(frame.width())) - 1
    # Pixels outside the rounded outline (the frame's square corners), top-left and top-right.
    outside = [image[y0 + dy, x0 + dx, :3] for dx, dy in ((0, 0), (1, 1), (0, 2), (2, 0))] + \
              [image[y0 + dy, x1 - dx, :3] for dx, dy in ((0, 0), (1, 1), (0, 2), (2, 0))]
    inside = image[y0 + 8, x0 + 8, :3]                    # inside the curve: the scene
    return np.array(outside, dtype=int), np.array(inside, dtype=int)


def _magenta(pixel) -> bool:
    return pixel[0] > 200 and pixel[1] < 60 and pixel[2] > 200


def test_the_scene_is_clipped_to_the_viewport_frames_rounded_corners(studio):
    controller, surface = studio("bubble", renderer=_MagentaRenderer)
    outside, inside = _corner_pixels(controller, surface)
    assert _magenta(inside)                                 # the scene fills its slot
    assert not any(_magenta(p) for p in outside)
    # What is outside the outline is the shell behind the frame, the same with or without the scene.
    surface.viewport.setVisible(False)
    hidden, _inside = _corner_pixels(controller, surface)
    assert (abs(outside - hidden) <= 2).all()


def test_a_slot_at_the_frames_square_corner_bleeds_negative_control(studio):
    controller, surface = studio("bubble", renderer=_MagentaRenderer)
    slot = surface.host.slot
    slot.setX(0.0)
    slot.setY(0.0)
    outside, _inside = _corner_pixels(controller, surface)
    assert any(_magenta(p) for p in outside)


def test_the_scene_keeps_its_place_and_size(studio):
    """The frame grew around the slot; the slot (and so every scene pixel) is where it was: 1 px inside the
    viewport column, ending at the scrub bar."""
    controller, surface = studio("waveform_ribbon")
    slot = surface.host.slot
    column = slot.parentItem().parentItem()
    (scrub,) = _named(surface.host.root, "scrubBar")
    top_left = slot.mapToItem(column, QPointF(0, 0))
    assert (top_left.x(), top_left.y()) == (1.0, 1.0)
    assert slot.width() == column.width() - 2
    assert slot.height() == column.height() - 2 - scrub.height()


# ----------------------------------------------------------------- static chrome
def test_chrome_paints_once_and_idles(studio):
    from ui.studio.chrome import StudioFrame, StudioWindowEdge
    controller, surface = studio("waveform_ribbon")
    surface.pump(3)
    items = [i for i in _named(surface.host.root, "panelFrame") + _named(surface.host.root, "viewportFrameSurface")
             + _named(surface.host.root, "viewportFrameBorder") + _named(surface.host.root, "studioWindowEdge")]
    assert items and all(isinstance(i, (StudioFrame, StudioWindowEdge)) for i in items)
    painted = [i.paints for i in items]
    evaluations = controller.evaluations
    surface.frame_requests = 0
    surface.pump(5)
    assert [i.paints for i in items] == painted              # nothing repainted while idle
    assert surface.frame_requests == 0                      # and nothing asked for another frame
    assert controller.evaluations == evaluations             # the viewport did not re-evaluate for the chrome
