"""The Studio opens on the world the live card shows (the 'stuck zoomed in' defect).

The visible world of a Studio frame is measured exactly as production measures its own: the production
presentation resolver gives the card's content aspect and lens aperture, and the production camera
(``physical_view``) turns them into lens tangents and a visible world span at the camera pivot. The
Studio's Live Card framing must match production's live card; Fill must show the same vertical world and
at least the card's horizontal world; no framing may show less world than the card. Nothing renders.
"""
from __future__ import annotations

import numpy as np
import pytest

from core.settings.visualizer_presets import get_preset_names, resolve_visualizer_activation_payload
from ui.studio.adapter import fill_extent
from ui.studio.waveform_adapter import MODE, WaveformStudioEvaluator, studio_presentation

# A wide CUSTOM card on a 4K display (the operator's TV card shape) and the 420x280 baseline card.
CARDS = {"tv_wide": ((3874.7, 1449.5), (3840.0, 2160.0)), "baseline": ((420.0, 280.0), (1920.0, 1080.0))}
STYLE = (("border_width", 4.0), ("content_inset", 0.0))
SLOT = (1326.0, 392.0)          # the dashboard viewport slot at the 1600x900 evidence size


def production_presentation(extent, display):
    """The live card as the display owner resolves it: CUSTOM extent, uniform scale to its committed rect."""
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation
    scale = min(0.95 * display[0] / extent[0], 0.95 * display[1] / extent[1])
    style = dict(STYLE)
    return resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(MODE), display_size=display, outer_origin=(0.0, 0.0),
        uniform_visual_scale=scale, viewport_extent=extent, border_width=style["border_width"],
        corner_radius=0.0, content_inset=style["content_inset"], background_color=(0, 0, 0, 0),
        border_color=(0, 0, 0, 0), shadow_enabled=False, shadow_color=(0, 0, 0, 0), shadow_blur=0.0,
        shadow_offset=(0.0, 0.0), shadow_spread=0.0, shadow_extensions=(0.0, 0.0, 0.0, 0.0))


def studio_frame_presentation(slot, extent):
    """The Studio viewport's presentation of ``extent`` letterboxed into ``slot`` (as the shell host fits it)."""
    scale = min(slot[0] / extent[0], slot[1] / extent[1])
    return studio_presentation((extent[0] * scale, extent[1] * scale), extent, STYLE)


def visible_world(frame, presentation):
    """(horizontal tangent, vertical tangent, world-x span, world-y span) at the camera pivot."""
    from core.settings.framed_camera import spec_for_mode
    from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
    from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale
    content = presentation.content_rect
    width, height = float(content[2]), float(content[3])
    aperture = framed_aperture_scale(presentation, content=True)
    parameters = frame.parameters
    view, projection, _eye, lens = physical_view(parameters, width / height, aperture,
                                                 zoom=float(getattr(frame, "zoom", 1.0)))
    clip = projection @ view
    pivot = np.asarray(spec_for_mode(MODE).pivot, dtype=float)

    def span(axis):
        samples = np.linspace(-4000.0, 4000.0, 16001)
        points = np.tile(np.append(pivot, 1.0), (samples.size, 1))
        points[:, axis] += samples
        projected = points @ clip.T
        w = projected[:, 3]
        ndc = projected[:, axis] / np.where(np.abs(w) > 1e-9, w, np.nan)
        inside = samples[(w > 0) & (np.abs(ndc) <= 1.0)]
        return float(inside.max() - inside.min()) if inside.size else 0.0
    return float(lens[0]), float(lens[1]), span(0), span(1), visible_crests(frame, clip)


def visible_crests(frame, clip) -> int:
    """Crests of the lead ribbon inside the frame (upward turning points of its projected knots)."""
    from ui.studio.waveform_adapter import ribbon_world_points
    points = ribbon_world_points(frame, 0)
    if len(points) < 3:
        return 0
    projected = np.c_[points[:, :3], np.ones(len(points))] @ clip.T
    w = projected[:, 3]
    ndc = projected[:, :2] / np.where(np.abs(w) > 1e-9, w, np.nan)[:, None]
    inside = (w > 0) & (np.abs(ndc[:, 0]) <= 1.0)
    y = ndc[:, 1]
    peaks = (y[1:-1] > y[:-2]) & (y[1:-1] >= y[2:]) & inside[1:-1]
    return int(np.count_nonzero(peaks))


def preset_frames():
    evaluator = WaveformStudioEvaluator()
    evaluator.select("mid")
    try:
        for index, name in enumerate(get_preset_names(MODE)[:-1]):
            values = resolve_visualizer_activation_payload({"mode": MODE, f"preset_{MODE}": index},
                                                           mode=MODE).resolved_config
            yield name, evaluator.evaluate(3.0, values)
    finally:
        evaluator.release()


def measure():
    """name -> card -> {'production', 'live_card', 'fill'} visible-world tuples (also used for the report)."""
    out = {}
    for name, frame in preset_frames():
        out[name] = {}
        for card, (extent, display) in CARDS.items():
            fill = fill_extent(extent, SLOT[0] / SLOT[1])
            out[name][card] = {
                "production": visible_world(frame, production_presentation(extent, display)),
                "live_card": visible_world(frame, studio_frame_presentation(SLOT, extent)),
                "fill": visible_world(frame, studio_presentation(SLOT, fill, STYLE)),
                "fill_extent": fill,
            }
    return out


def test_live_card_framing_shows_exactly_the_world_production_shows():
    for name, cards in measure().items():
        for card, record in cards.items():
            production, studio = record["production"], record["live_card"]
            assert production[2] > 0 and production[3] > 0, (name, card)
            assert studio[0] == pytest.approx(production[0], rel=0.02), (name, card, "horizontal")
            assert studio[1] == pytest.approx(production[1], rel=0.02), (name, card, "vertical")
            assert studio[2] == pytest.approx(production[2], rel=0.03), (name, card, "world x span")


def test_fill_framing_keeps_the_live_cards_scale_and_reveals_more_world_at_the_sides():
    for name, cards in measure().items():
        for card, record in cards.items():
            production, fill = record["production"], record["fill"]
            extent, grown = CARDS[card][0], record["fill_extent"]
            # The viewport here is wider than the card: same vertical world, horizontal world grows in
            # proportion to the extra width (production's edge-resize rule), never shrinks.
            assert fill[1] == pytest.approx(production[1], rel=0.02), (name, card)
            assert fill[0] >= production[0] * 0.98, (name, card)
            assert fill[0] / production[0] == pytest.approx((grown[0] / grown[1]) / (extent[0] / extent[1]),
                                                            rel=0.03), (name, card)


def test_a_mismatched_card_is_detected_negative_control():
    """The old behaviour (Studio at the 420x280 baseline while the live card is the wide TV card)."""
    name, frame = next(preset_frames())
    production = visible_world(frame, production_presentation(*CARDS["tv_wide"]))
    stale = visible_world(frame, studio_frame_presentation(SLOT, (280.0 * 16 / 9, 280.0)))
    assert stale[1] < production[1] * 0.5, name


class _CardStore:
    """An in-memory canonical store standing for Settings, on the wide TV card."""

    def __init__(self, values):
        self.values = dict(values)

    def snapshot(self):
        return dict(self.values)

    def commit(self, values, changed):
        self.values.update(values)
        return dict(self.values)

    def preset_label(self):
        return "Preset"

    def card_extent(self):
        return CARDS["tv_wide"][0]

    def card_style(self):
        return dict(STYLE)


class _Quiet:
    def prepare(self, card, frame):
        return True

    def render(self, card, frame):
        pass

    def release(self):
        pass


class _Presence:
    concealed = False

    def conceal(self):
        pass

    def reveal(self):
        pass


@pytest.fixture
def card_studio(qt_app):
    """A Studio on the wide TV card (in-memory store, offscreen surface, a no-op renderer)."""
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.studio.controller import StudioController
    from ui.studio.surface import OffscreenStudioSurface
    from ui.studio.waveform_adapter import WaveformStudioAdapter

    class Adapter(WaveformStudioAdapter):
        def create_renderer(self):
            return _Quiet()

        def recorded_clips(self):
            return ()

    disable_per_call_gl_error_checking()
    values = resolve_visualizer_activation_payload({"mode": MODE, f"preset_{MODE}": 0}, mode=MODE).resolved_config
    surfaces = []

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(1600, 900), present_on_show=False))
        return surfaces[0]
    controller = StudioController(Adapter(), _CardStore(values), _Presence(), factory)
    assert controller.open()
    surfaces[0].pump(3)
    yield controller, surfaces[0], values
    controller.close()


def _items(root, name):
    out = []

    def walk(item):
        for child in item.childItems():
            if child.objectName() == name:
                out.append(child)
            walk(child)
    walk(root)
    return out


def _click(surface, item):
    from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    for kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
        QCoreApplication.sendEvent(surface.window, QMouseEvent(kind, centre, centre, Qt.MouseButton.LeftButton,
                                                               Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    QCoreApplication.processEvents()
    surface.pump()


def test_the_studio_opens_filling_on_the_live_card_and_zooms_out_from_there(card_studio):
    controller, surface, values = card_studio
    viewport, slot = surface.viewport, surface.host.slot
    # Opens on Fill: the picture spans the viewport's whole width (no side bars) on the live card's world.
    assert controller.bridge.framingId == "fill"
    assert viewport.width() == pytest.approx(slot.width()) and viewport.x() == pytest.approx(0.0)
    card = CARDS["tv_wide"][0]
    assert viewport.extent[1] == pytest.approx(card[1]) and viewport.extent[0] >= card[0]

    def seen():
        frame = controller.evaluator.evaluate(3.0, controller.evaluation_values())
        return visible_world(frame, studio_presentation((viewport.width(), viewport.height()),
                                                        viewport.extent, STYLE))
    opening = seen()
    nav = controller.adapter.navigation()
    for _ in range(3):
        controller.bridge.zoomBy(-1.0, False)              # wheel out: a wider lens
    wider = seen()
    assert wider[1] > opening[1] * 1.2 and wider[3] > opening[3] * 1.2
    controller.bridge.resetCamera()
    assert seen()[1] == pytest.approx(opening[1])
    controller.bridge.zoomBy(-2.0, True)                   # Shift+wheel out: dolly back
    assert controller.evaluation_values()[nav.dolly.key] < values[nav.dolly.key]
    assert seen()[3] > opening[3] * 1.05


def test_viewport_toolbar_hides_overlays_expands_and_copies_the_frame(card_studio):
    controller, surface, _values = card_studio
    root = surface.host.root
    (handles,) = _items(root, "handleLayer")
    (panels,) = _items(root, "dashboardPanels")
    slot = surface.host.slot
    assert handles.isVisible()
    _click(surface, _items(root, "overlaysButton")[0])
    assert not handles.isVisible()
    _click(surface, _items(root, "overlaysButton")[0])
    assert handles.isVisible()
    narrow = (slot.width(), slot.height())
    _click(surface, _items(root, "expandViewportButton")[0])
    surface.pump(2)
    assert not panels.isVisible() and slot.width() > narrow[0] and slot.height() > narrow[1]
    # Fill follows the larger viewport: still no side bars, still the live card's world at least.
    assert surface.viewport.width() == pytest.approx(slot.width())
    assert surface.viewport.extent[1] >= CARDS["tv_wide"][0][1] - 1e-6
    # The handles follow the resized frame (projected for the new size, not left where they were).
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.processEvents()
    shown = controller.bridge.handles
    assert shown.get("handles")
    controller.refresh_handles()
    assert controller.bridge.handles == shown
    _click(surface, _items(root, "expandViewportButton")[0])
    surface.pump(2)
    assert panels.isVisible() and slot.width() == pytest.approx(narrow[0])
    _click(surface, _items(root, "copyFrameButton")[0])
    for _ in range(10):
        if getattr(controller, "copied_frame", None) is not None:
            break
        surface.pump()
    image = controller.copied_frame
    assert image is not None and not image.isNull()
    assert image.width() >= int(surface.viewport.width()) and image.height() >= int(surface.viewport.height())


def test_the_per_object_panel_steps_through_the_ribbons(card_studio):
    controller, surface, _values = card_studio
    bridge = controller.bridge
    objects = [o["id"] for o in bridge.objects]
    assert len(objects) > 1
    bridge.selectObject(objects[0])
    surface.pump()
    steppers = [i for i in _items(surface.host.root, "objectStepper") if i.isVisible()]
    assert steppers
    (forward,) = [i for i in _items(steppers[0], "nextObject")]
    _click(surface, forward)
    assert bridge.selectedObject == objects[1]
    bridge.stepObject(-2)                                     # wraps
    assert bridge.selectedObject == objects[-1]


def test_curve_shape_thumbnails_pick_the_response_curve(card_studio):
    controller, surface, _values = card_studio
    bridge = controller.bridge
    bridge.setWorkspace("reactivity")
    surface.pump(3)
    tiles = [t for t in _items(surface.host.root, "curveShapeTile") if t.isVisible()]
    presets = bridge.response["presets"]
    assert len(tiles) == len(presets) >= 2
    target = next(t for t in bridge.response["targets"] if t["id"] == bridge.selectedTarget)
    cell = next(c for c in target["cells"] if c["source"] == bridge.selectedSource)
    shape = next(p for p in presets if abs(bridge.values[cell["power"]] - p["power"]) > 1e-3)
    _click(surface, tiles[presets.index(shape)])
    assert bridge.values[cell["power"]] == pytest.approx(shape["power"])
    assert bridge.canUndo
