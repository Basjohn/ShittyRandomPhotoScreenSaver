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

    def open_mode(mode, *, renderer=None, theme=None, transparent=False):
        adapter = create_adapter(mode)
        adapter.recorded_clips = lambda: ()
        if renderer is not None:
            adapter.create_renderer = renderer
        surfaces = []

        def factory(controller):
            surfaces.append(OffscreenStudioSurface(controller, size=(1600, 900), present_on_show=False, transparent=transparent))
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


def _resize_area_problems(root):
    """Every way the shell's resize areas fail to line the window edge (an empty list: they all do).

    Each of the eight areas (four sides, four corners) must hug the edges it resizes; the side strips must run
    between the corner areas so the perimeter has no gap; and each window corner pixel must belong to the corner area
    that resizes both of its edges."""
    areas = _named(root, "resizeEdge")
    width, height = root.width(), root.height()
    problems = []

    def sides(area):
        return tuple(bool(area.property(name)) for name in ("onLeft", "onRight", "onTop", "onBottom"))

    def rect(area):
        origin = area.mapToItem(root, QPointF(0, 0))
        return QRectF(origin.x(), origin.y(), area.width(), area.height())

    expected = {(True, False, False, False), (False, True, False, False), (False, False, True, False),
                (False, False, False, True), (True, False, True, False), (False, True, False, True),
                (False, True, True, False), (True, False, False, True)}
    if sorted(sides(area) for area in areas) != sorted(expected):
        problems.append(("areas", sorted(sides(area) for area in areas)))
        return problems
    for area in areas:
        left, right, top, bottom = sides(area)
        r = rect(area)
        if r.width() <= 0 or r.height() <= 0:
            problems.append(("empty", sides(area)))
        if left and r.left() != 0:
            problems.append(("left edge", sides(area), r))
        if right and r.right() != width:
            problems.append(("right edge", sides(area), r))
        if top and r.top() != 0:
            problems.append(("top edge", sides(area), r))
        if bottom and r.bottom() != height:
            problems.append(("bottom edge", sides(area), r))

    def owner(x, y):
        """The resize area under the point (topmost by z, then latest), as its sides."""
        hits = [area for area in areas if rect(area).contains(QPointF(x, y))]
        return sides(max(hits, key=lambda area: area.z())) if hits else None

    # The window corner pixels belong to the corner areas.
    for x, y, want in ((0.5, 0.5, (True, False, True, False)), (width - 0.5, 0.5, (False, True, True, False)),
                       (0.5, height - 0.5, (True, False, False, True)),
                       (width - 0.5, height - 0.5, (False, True, False, True))):
        if owner(x, y) != want:
            problems.append(("corner", (x, y), owner(x, y)))
    # Walking along each edge one pixel in, every point is a resize area that resizes that edge.
    for step in range(0, 101):
        fx, fy = width * step / 100.0, height * step / 100.0
        fx, fy = min(max(fx, 0.5), width - 0.5), min(max(fy, 0.5), height - 0.5)
        for x, y, index in ((fx, 0.5, 2), (fx, height - 0.5, 3), (0.5, fy, 0), (width - 0.5, fy, 1)):
            hit = owner(x, y)
            if hit is None or not hit[index]:
                problems.append(("gap", (x, y), hit))
    return problems


def test_the_resize_areas_line_every_window_edge_and_reach_the_corners(studio):
    """The frameless shell resizes through eight areas (four sides, four corners) at the window's edge; they follow
    the window when it resizes. Negative control: a corner area pulled in from its corner is caught."""
    _controller, surface = studio("waveform_ribbon")
    root = surface.host.root
    surface.pump()
    assert _resize_area_problems(root) == []

    root.setWidth(1100)
    root.setHeight(700)
    surface.pump()
    assert _resize_area_problems(root) == []

    corner = next(area for area in _named(root, "resizeEdge")
                  if area.property("onRight") and area.property("onBottom"))
    corner.setX(corner.x() - 6)
    corner.setY(corner.y() - 6)
    problems = _resize_area_problems(root)
    assert any(problem[0] == "right edge" for problem in problems)
    assert any(problem[0] == "corner" for problem in problems)


def _studio_corner_alphas(surface, dpr):
    """Alpha of every device pixel wholly outside the window border's outer arc, and of the stroke's middle round
    each corner arc, from the shell rendered off-screen over nothing (a transparent clear)."""
    import math
    from ui.settings_window_edge import forged_edge_geometry
    surface.pump(3)
    image = surface.grab()
    h, w = image.shape[:2]
    inset, radius, width = forged_edge_geometry(dpr)
    centre, outer, middle = (inset + radius) * dpr, (radius + width / 2) * dpr, radius * dpr
    outside, ring = [], []
    for sx, sy, ox, oy in ((1, 1, 0, 0), (-1, 1, w - 1, 0), (1, -1, 0, h - 1), (-1, -1, w - 1, h - 1)):
        for y in range(math.ceil(centre)):
            for x in range(math.ceil(centre)):
                if math.hypot(x + 0.5 - centre, y + 0.5 - centre) > outer + 0.75:
                    outside.append(int(image[oy + sy * y, ox + sx * x, 3]))
        for step in range(31):
            angle = math.radians(180 + step * 3)
            x, y = int(centre + middle * math.cos(angle)), int(centre + middle * math.sin(angle))
            ring.append(int(image[oy + sy * y, ox + sx * x, 3]))
    return outside, ring


@pytest.mark.parametrize("dpr", [1.5, 2.0])
def test_the_window_corners_outside_the_rounded_border_are_see_through(qt_app, dpr):
    """The Studio's full-window fills (window surface, title bar) are rounded inside the shared rounded border, so
    nothing the shell paints reaches the corner outside it (a Quick item cannot clear what is beneath it). At 100%
    no pixel lies wholly outside the border's arc (tests/test_window_edge_see_through_corners.py covers 100%)."""
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.settings_window_edge import CORNER_OUTSIDE_ALPHA
    from ui.studio.controller import StudioController
    from ui.studio.registry import create_adapter
    from ui.studio.surface import OffscreenStudioSurface
    from ui.studio.theme import studio_theme
    disable_per_call_gl_error_checking()
    theme = _theme_with_mode("acrylic")
    adapter = create_adapter("waveform_ribbon")
    adapter.recorded_clips = lambda: ()
    surfaces = []

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(1280, 760), dpr=dpr, present_on_show=False,
                                               transparent=True))
        return surfaces[0]
    controller = StudioController(adapter, _Store("waveform_ribbon"), _Presence(), factory,
                                  theme_provider=lambda: studio_theme(theme))
    assert controller.open()
    try:
        outside, ring = _studio_corner_alphas(surfaces[0], dpr)
        assert len(outside) >= 4 and max(outside) <= CORNER_OUTSIDE_ALPHA, outside
        assert min(ring) == 255, ring                        # the border ring is whole round every corner
        # Negative control: a square full-window fill reaches the corner again.
        (window_surface,) = _named(surfaces[0].host.root, "studioWindowSurface")
        window_surface.setProperty("radius", 0)
        outside, _ring = _studio_corner_alphas(surfaces[0], dpr)
        assert max(outside) > 8
    finally:
        controller.close()


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
        assert window_surface.window.format().alphaBufferSize() == 8
        window_surface.apply_backdrop()
        window_surface.apply_backdrop()                      # once, like Settings' first show
        assert calls == ([] if mode == "off" else [theme.native_backdrop_request()])
    finally:
        window_surface.host.retire()
        window_surface.window.deleteLater()
        window_surface.host.release_engine()


def test_open_surface_reconciles_native_material_and_opacity_on_theme_notifications(studio, monkeypatch):
    from dataclasses import replace
    from core import platform_paths
    from core.settings.surface_opacity import project_settings_opacity_adjust, settings_opacity_adjust
    from ui.settings_theme_spec import NativeBackdropStyle
    from ui.studio.surface import StudioWindowSurface

    monkeypatch.setattr(platform_paths, "IS_WINDOWS", True)
    calls = []
    monkeypatch.setattr("core.windows.dwm_blur.apply_backdrop",
                        lambda hwnd, mode, tint=None: calls.append((mode, tint)) or mode != "off")
    theme = _theme_with_mode("glass")
    controller, _surface = studio("waveform_ribbon")
    surface = StudioWindowSurface(controller, theme=theme)
    window = surface.window
    before = settings_opacity_adjust()
    try:
        window.winId = lambda: 4242
        surface.apply_backdrop()
        acrylic = _theme_with_mode("acrylic")
        surface.apply_settings_theme(acrylic)
        first_surface = acrylic.window_surface()
        project_settings_opacity_adjust(.4)
        surface.apply_settings_theme(acrylic)
        assert acrylic.window_surface() != first_surface
        assert calls == [("glass", None)]
        off = replace(theme, backdrop=NativeBackdropStyle("off", theme.backdrop.tint))
        surface.apply_settings_theme(off)
        surface.apply_settings_theme(off)
        assert [mode for mode, _tint in calls] == ["glass", "off"]
        assert surface.window is window and surface.material == "off" and not surface.backdrop_applied
        surface.apply_settings_theme(theme)
        assert calls[-1][0] == "glass" and surface.backdrop_applied
        surface.apply_settings_theme(off)
        surface.apply_settings_theme(off)
        assert [mode for mode, _tint in calls] == ["glass", "off", "glass", "off"]
    finally:
        project_settings_opacity_adjust(before)
        surface.host.retire()
        window.deleteLater()
        surface.host.release_engine()


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
    assert calls == [(7, theme.native_backdrop_request()[0])]


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
    import numpy as np
    from dataclasses import replace
    from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, NativeBackdropStyle, Rgba
    from ui.studio.chrome import StudioFrame, StudioWindowEdge
    theme = replace(DEFAULT_DARK_SETTINGS_THEME,
                    backdrop=NativeBackdropStyle("acrylic", Rgba(13, 32, 60, 100)),
                    colors={**DEFAULT_DARK_SETTINGS_THEME.colors,
                            "panel.group.surface": Rgba(35, 70, 110, 180)})
    controller, surface = studio("waveform_ribbon", theme=theme, transparent=True)
    surface.pump(3)
    panel, = _named(surface.host.root, "objectsPanel")
    frame = next(item for item in _named(surface.host.root, "panelFrame")
                 if abs(item.x()-panel.x()) < .1 and abs(item.y()-panel.y()) < .1)
    origin = panel.mapToScene(QPointF(panel.width()*.5, panel.height()-30))
    x, y = round(origin.x()), round(origin.y())
    painted_pixel = surface.grab()[y, x].astype(float)
    fill = frame.property("surfaceColor")
    top = frame.property("surfaceTopColor")
    # Negative control: keep the actual border/text, remove only the broad fill.
    frame.setProperty("surfaceColor", QColor(0,0,0,0))
    frame.setProperty("surfaceTopColor", QColor(0,0,0,0))
    surface.pump(2)
    background = surface.grab()[y, x].astype(float)
    assert painted_pixel[3] > background[3] + 10
    alpha = fill.alphaF()
    expected = np.array([fill.redF()*255*alpha, fill.greenF()*255*alpha,
                         fill.blueF()*255*alpha, 255*alpha]) + background*(1-alpha)
    assert np.max(np.abs(painted_pixel-expected)) <= 2
    # A second parent-alpha contribution would thicken this retained panel.
    duplicated_alpha = alpha + background[3]/255*(1-alpha)
    duplicate = np.array([fill.redF()*255*duplicated_alpha, fill.greenF()*255*duplicated_alpha,
                          fill.blueF()*255*duplicated_alpha, 255*duplicated_alpha]) + background*(1-duplicated_alpha)
    assert np.max(np.abs(painted_pixel-duplicate)) > 3
    frame.setProperty("surfaceColor", fill)
    frame.setProperty("surfaceTopColor", top)
    surface.pump(2)
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


@pytest.mark.qt
def test_studio_window_inherits_explicit_native_icon_without_widget_chrome(studio, qt_app):
    """The custom QML title glyph isn't the HWND/taskbar icon; the top-level QQuickWindow needs its own."""
    from PySide6.QtGui import QIcon, QPixmap
    from ui.studio.surface import StudioWindowSurface

    original_icon = qt_app.windowIcon()
    image = QPixmap(32, 32)
    image.fill(QColor(190, 95, 55))
    qt_app.setWindowIcon(QIcon(image))
    window_surface = None
    try:
        controller, _hidden = studio("waveform_ribbon")
        window_surface = StudioWindowSurface(controller)
        assert not window_surface.window.icon().isNull()
        assert not window_surface.window.isVisible()  # No native taskbar presence created by this test.
    finally:
        if window_surface is not None:
            window_surface.host.retire()
            window_surface.window.deleteLater()
            window_surface.host.release_engine()
        qt_app.setWindowIcon(original_icon)
