"""The rounded window border is the silhouette: outside it the window corner is see-through (Settings and Studio).

Defect (operator, 11 Nov 2026, plan 1B.9): "Corners of application in settings GUI and Studio GUI STILL have
bleed/escape." Both windows are rectangular HWNDs; the shared edge painter (``ui/settings_window_edge.py``) used to
forge the rounded corner with opaque caps and a backing stroke in the title-bar colour. Native captures showed the
border's outer arc reaches almost to the window corner, so the caps left a wedge of flat camouflage colour at each
corner (a near-white speck on light themes) and the backing a 1 px line just inside the border. The painter now
leaves every pixel outside the border's outer edge see-through, whatever the content painted there.

The checks render the painter itself into a device-pixel image at 100/150/200% over opaque "content", so they
fail on the forged-edge painter (opaque corner pixels) and on the negative control that skips the clearing.
"""
from __future__ import annotations

import inspect
import math

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter

CONTENT = QColor(200, 120, 40, 255)        # what the window's own surfaces paint everywhere
BORDER = QColor(90, 40, 140, 255)
SIZE = (160, 100)                          # logical


def _render(dpr: float, monkeypatch=None, skip_clear: bool = False) -> QImage:
    import ui.settings_window_edge as edge

    if skip_clear:
        monkeypatch.setattr(edge, "_clear_outside_border", lambda *args, **kwargs: None)
    image = QImage(round(SIZE[0] * dpr), round(SIZE[1] * dpr), QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(dpr)
    image.fill(CONTENT)
    painter = QPainter(image)
    try:
        kwargs = {"maximized": False, "outer_border": BORDER}
        if "forged_edge" in inspect.signature(edge.paint_forged_window_edge).parameters:
            kwargs["forged_edge"] = CONTENT                 # the former painter's camouflage colour
        edge.paint_forged_window_edge(painter, QRectF(0, 0, *SIZE), dpr, **kwargs)
    finally:
        painter.end()
    return image


def _corner_frames(image: QImage):
    """Each corner as a function (x, y) -> QColor in corner-local device coordinates ([0, 0] = outermost)."""
    w, h = image.width(), image.height()
    for sx, sy, ox, oy in ((1, 1, 0, 0), (-1, 1, w - 1, 0), (1, -1, 0, h - 1), (-1, -1, w - 1, h - 1)):
        yield lambda x, y, sx=sx, sy=sy, ox=ox, oy=oy: image.pixelColor(ox + sx * x, oy + sy * y)


def _geometry(dpr: float):
    from ui.settings_window_edge import forged_edge_geometry

    inset, radius, width = forged_edge_geometry(dpr)[:3]
    centre = (inset + radius) * dpr
    return centre, (radius + width / 2) * dpr, (radius - width / 2) * dpr


@pytest.mark.parametrize("dpr", [1.0, 1.5, 2.0])
def test_corner_pixels_outside_the_rounded_border_are_see_through(qt_app, dpr):
    import ui.settings_window_edge as edge

    # (The forged-edge painter had no such constant: anything above alpha 0 there was painted.)
    CORNER_OUTSIDE_ALPHA = getattr(edge, "CORNER_OUTSIDE_ALPHA", 0)
    image = _render(dpr)
    centre, outer, _inner = _geometry(dpr)
    checked = 0
    for pixel in _corner_frames(image):
        for y in range(math.ceil(centre)):
            for x in range(math.ceil(centre)):
                # Only pixels wholly outside the border's outer arc (its antialiased fringe is the border's).
                if math.hypot(x + 0.5 - centre, y + 0.5 - centre) > outer + 0.75:
                    colour = pixel(x, y)
                    assert colour.alpha() <= CORNER_OUTSIDE_ALPHA, (dpr, x, y, colour.getRgb())
                    checked += 1
    corner = [pixel(0, 0).alpha() for pixel in _corner_frames(image)]
    if dpr > 1.0:
        assert checked >= 4                                 # every corner has pixels wholly outside the border
        # Not zero either: a layered window passes the mouse through alpha-0 pixels only, so the corner keeps its
        # hit-testing (CORNER_OUTSIDE_ALPHA, the module docstring).
        assert corner == [CORNER_OUTSIDE_ALPHA] * 4 and CORNER_OUTSIDE_ALPHA >= 1
    else:
        # At 100% only the corner pixel lies outside the arc, and only partly: the border's faint antialiasing.
        assert all(CORNER_OUTSIDE_ALPHA <= alpha < 128 for alpha in corner), corner


@pytest.mark.parametrize("dpr", [1.0, 1.5, 2.0])
def test_the_border_ring_is_continuous_and_antialiased_round_every_corner(qt_app, dpr):
    image = _render(dpr)
    centre, outer, inner = _geometry(dpr)
    middle = (outer + inner) / 2
    for pixel in _corner_frames(image):
        # The stroke's middle, every 3 degrees round the corner arc: always the opaque border colour.
        for step in range(31):
            angle = math.radians(180 + step * 3)
            x = int(centre + middle * math.cos(angle))
            y = int(centre + middle * math.sin(angle))
            colour = pixel(x, y)
            assert colour.alpha() == 255 and abs(colour.red() - BORDER.red()) <= 2, (dpr, x, y, colour.getRgb())
        # Antialiased outer arc (no staircase): partial-alpha pixels exist on the silhouette.
        fringe = [pixel(x, y).alpha() for y in range(math.ceil(centre)) for x in range(math.ceil(centre))
                  if abs(math.hypot(x + 0.5 - centre, y + 0.5 - centre) - outer) < 0.6]
        assert any(8 < alpha < 247 for alpha in fringe), (dpr, fringe)
    # The straight edges are border too (the stroke's outer half runs off the window edge).
    w, h = image.width(), image.height()
    for x, y in ((w // 2, 0), (0, h // 2), (w - 1, h // 2), (w // 2, h - 1)):
        assert image.pixelColor(x, y).alpha() == 255


def test_without_clearing_the_content_shows_in_the_corner_negative_control(qt_app, monkeypatch):
    image = _render(1.5, monkeypatch, skip_clear=True)
    assert next(_corner_frames(image))(0, 0).alpha() == 255


def test_maximised_the_edge_is_a_plain_rectangle_and_clears_nothing(qt_app):
    import ui.settings_window_edge as edge

    image = QImage(200, 120, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(CONTENT)
    painter = QPainter(image)
    edge.paint_forged_window_edge(painter, QRectF(0, 0, 200, 120), 1.0, maximized=True, outer_border=BORDER)
    painter.end()
    assert image.pixelColor(0, 0).alpha() == 255
