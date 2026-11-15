"""Fullscreen (Hide Borders) draws nothing but the Visualizer on every edge of its display, whatever pixel shift does
(Current_Plan 1D.13; plan 01 M3c "Display styles of the expanded card": Geometry, Coverage and clip contract).

The production ``DisplayScene.qml`` and scene controller draw the display on the hidden ``QQuickRenderControl`` host
(``tools/expanded_visualizer_evidence.HiddenDisplayHost``; nothing is ever shown) in the product's R-63 placement: the
window and the display's rect inside it come from ``compat_native_rect`` and ``visible_rect_in_window``, so the display
starts at a fractional logical offset (2 device pixels in, 3 down at 150 %; 1 down at 100 %), as on the development
machine's displays. The wallpaper is one sentinel colour and the card's border another; the card's fill is opaque, so
on the display a sentinel pixel can only be the wallpaper showing past the card or the card's frame.

Pixel shift moves every card by whole device pixels (1C.4), through the product's own route
(``apply_auxiliary_state``). A card that is the display (an edge-to-edge display style) cannot move without leaving a
strip of what lies beneath on one side and pushing its other side off the display (the operator's 1 px line, "sometimes
the side, sometimes the bottom"). Checked at 100 % and 150 %, over several entries into Fullscreen at different shifts
and shift steps while it is shown: no sentinel pixel on any of the four edges, nor anywhere on the display; the
full-display overlays still take the shift (burn-in), and the ordinary card and the Default style still move with it.
The same cause made Borders To Edge's frame uneven (1D.13's second box: at a shift of (3, -2) at 150 % its left frame
read 8 device pixels beside a 5 pixel strip of wallpaper and its right frame 3): at every step its four edges read no
wallpaper and the same whole frame width, the record's border as Qt draws its pen (R-191).

Discriminating control in the test itself: the Default style (a margin to the display edge) shows the wallpaper sentinel
on all four edges with the same reading. Negative control (seen 15 Nov 2026 on the pre-fix scene): every shifted entry
showed the wallpaper on two edges (2 device pixels at a shift of 1 at 150 %).
"""
from __future__ import annotations

import pytest

from core.settings.fullscreen_overlays import (
    DISPLAY_STYLE_BORDERS_TO_EDGE,
    DISPLAY_STYLE_DEFAULT,
    DISPLAY_STYLE_HIDE_BORDERS,
)

WALLPAPER = (255, 0, 255)
BORDER = (0, 255, 0, 255)
CARD = {"border_width": 5.0, "corner_radius": 8.0, "content_inset": 0.0, "background_color": (14, 16, 22, 255),
        "border_color": BORDER, "shadow_enabled": True, "shadow_color": (0, 0, 0, 150), "shadow_blur": 12.0,
        "shadow_offset": (0.0, 4.0), "shadow_spread": 0.0, "shadow_extensions": (0.0, 0.0, 0.0, 2.0)}
MODE = "extruded_bubble"
SENTINEL_TOLERANCE = 24          # per channel
EDGE_BAND = 8                    # device pixels read on each edge (the largest shift is 4 logical: 6 at 150 %)
WARMUP_FRAMES = 40
#: (monitor, dpr): single displays whose R-63 window overscans an exterior edge (at 150 % both axes).
LAYOUTS = {"960x540@100": ((0, 0, 960, 540), 1.0), "1280x720@150": ((0, 0, 1280, 720), 1.5)}
#: Each entry: the pixel shift Fullscreen is entered at, then one shift step while it is shown.
ENTRIES = (((1, 1), (-1, -1)), ((3, -2), (-4, 4)), ((-2, 3), (4, -4)))


def _placement(monitor, dpr):
    from rendering.quick.device_geometry import compat_native_rect, visible_rect_in_window

    window = compat_native_rect(monitor, monitor, dpr)
    width, height = (window[2] - window[0]) / dpr, (window[3] - window[1]) / dpr
    assert width == int(width) and height == int(height)          # R-192: a whole logical window
    display = visible_rect_in_window(window, monitor, dpr)
    assert (display[0], display[1]) != (0.0, 0.0)                 # the overscan placement is exercised
    return (int(width), int(height)), display


def _sentinel_wallpaper(display, dpr):
    from rendering.quick.image_state import PresentationImage

    pixels = (round(display[2] * dpr), round(display[3] * dpr))
    return PresentationImage("fullscreen-edges:sentinel", "sentinel", (display[2], display[3]), dpr, pixels,
                             pixels[0] * 4, bytes((*WALLPAPER, 255)) * (pixels[0] * pixels[1]))


def _edge_reading(rgba, display, dpr) -> dict[str, dict[str, int]]:
    """Sentinel pixels (wallpaper, border) in each edge band of the display and on the whole display."""
    import numpy as np

    x0, y0 = round(display[0] * dpr), round(display[1] * dpr)
    x1, y1 = x0 + round(display[2] * dpr), y0 + round(display[3] * dpr)
    image = rgba[y0:y1, x0:x1, :3].astype(int)

    def near(colour):
        return np.all(np.abs(image - np.array(colour[:3])) <= SENTINEL_TOLERANCE, axis=2)

    masks = {"wallpaper": near(WALLPAPER), "border": near(BORDER)}
    bands = {"left": (slice(None), slice(0, EDGE_BAND)), "right": (slice(None), slice(-EDGE_BAND, None)),
             "top": (slice(0, EDGE_BAND), slice(None)), "bottom": (slice(-EDGE_BAND, None), slice(None))}
    reading = {edge: {name: int(mask[band].sum()) for name, mask in masks.items()} for edge, band in bands.items()}
    reading["display"] = {name: int(mask.sum()) for name, mask in masks.items()}
    return reading


def _frame_runs(rgba, display, dpr) -> dict[str, tuple[int, int]]:
    """(wallpaper pixels, then border pixels) inward from each display edge at its midpoint."""
    import numpy as np

    x0, y0 = round(display[0] * dpr), round(display[1] * dpr)
    x1, y1 = x0 + round(display[2] * dpr), y0 + round(display[3] * dpr)
    image = rgba[y0:y1, x0:x1, :3].astype(int)

    def near(colour):
        return np.all(np.abs(image - np.array(colour[:3])) <= SENTINEL_TOLERANCE, axis=2)

    wallpaper, border = near(WALLPAPER), near(BORDER)
    my, mx = image.shape[0] // 2, image.shape[1] // 2
    lines = {"left": (np.s_[my, :]), "right": (np.s_[my, ::-1]), "top": (np.s_[:, mx]), "bottom": (np.s_[::-1, mx])}

    def run(values) -> int:
        count = 0
        for value in values:
            if not value:
                break
            count += 1
        return count

    runs = {}
    for edge, line in lines.items():
        bare = run(wallpaper[line])
        runs[edge] = (bare, run(border[line][bare:]))
    return runs


@pytest.fixture
def placement(qt_app, request):
    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production scene needs the Windows QPA GL")
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    monitor, dpr = LAYOUTS[request.param]
    window, display = _placement(monitor, dpr)
    host = HiddenDisplayHost(*window, dpr=dpr, display_rect=display)
    try:
        yield host, display, dpr
    finally:
        host.close()


@pytest.mark.qt
@pytest.mark.parametrize("placement", list(LAYOUTS), indirect=True)
def test_fullscreen_hide_borders_draws_no_frame_pixel_on_any_edge(placement):
    from PySide6.QtCore import QPointF
    from PySide6.QtQuick import QQuickItem

    from core.settings.fullscreen_overlays import canonical_fullscreen_overlays
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from rendering.quick.auxiliary import QuickAuxiliaryState
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    from tools.expanded_visualizer_evidence import shipped_clip
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from widgets.spotify_visualizer.expanded_overlays import resolve_expanded_overlay_config
    from widgets.spotify_visualizer.feature_replay import configure_offline_controller, deterministic_clock
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_expanded_visualizer_presentation,
        resolve_visualizer_presentation,
        snap_to_device_pixels,
    )
    from widgets.spotify_visualizer.quick_presentation_sync import QuickVisualizerPresentationSync
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.tick_pipeline import logical_tick

    host, display, dpr = placement
    scene = host.scene
    scene.set_presentation_image(_sentinel_wallpaper(display, dpr))
    size = scene.visible_display_size()
    assert size == (display[2], display[3])                       # the display-wide record's input (1D.2)
    ordinary = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(MODE), display_size=size,
        outer_origin=(24.0, size[1] - 280.0 - 24.0), dpr=dpr, **CARD)
    records = {style: resolve_expanded_visualizer_presentation(ordinary, display_size=size, dpr=dpr,
                                                               display_style=style)
               for style in (DISPLAY_STYLE_DEFAULT, DISPLAY_STYLE_HIDE_BORDERS, DISPLAY_STYLE_BORDERS_TO_EDGE)}
    frame_px = int(records[DISPLAY_STYLE_BORDERS_TO_EDGE].border_width * dpr + 0.5)    # Qt's pen (R-191)
    assert frame_px > 0
    route = {"record": ordinary}
    generation = host.window.runtime_generation

    def shift(x: int, y: int) -> None:
        assert scene.apply_auxiliary_state(QuickAuxiliaryState(
            screen_index=0, runtime_generation=generation, pixel_shift_enabled=True, pixel_shift_x=x,
            pixel_shift_y=y)) is True

    loader = scene.scene_root.findChild(QQuickItem, "visualizerPresentationLoader")

    def scene_origin(item) -> tuple[float, float]:
        point = item.mapToScene(QPointF(0.0, 0.0))
        return point.x() - host.scene_offset[0], point.y() - host.scene_offset[1]

    readings: dict[str, dict] = {}
    frames_read: dict[str, dict] = {}
    places: list[tuple[str, tuple[float, float], tuple[float, float]]] = []
    clip = shipped_clip(4.0)
    frames = iter(clip.frames)
    with deterministic_clock() as clock:
        engine = ReplayBeatEngine(32)
        controller = VisualizerRuntimeController(runtime_generation=1, initial_mode=MODE,
                                                 engine_factory=lambda _count: engine)
        controller.engine = engine
        configure_offline_controller(controller, MODE, settings=frozen_visualizer_settings(MODE))
        identity = controller.begin_render_activation(
            engine_generation=engine.get_generation_id(), activation_id=engine.get_activation_id())
        scene.set_visualizer_render_source(controller.render_bridge, identity)
        sync = QuickVisualizerPresentationSync(
            controller, resolve_presentation=lambda: route["record"],
            commit_presentation=lambda presentation: scene.apply_visualizer_presentation(presentation, active=True),
            request_present=scene.request_visualizer_present)
        overlays = canonical_fullscreen_overlays()
        overlays["preset"].update(always_show=True)
        scene.set_visualizer_expanded_overlay_config(resolve_expanded_overlay_config({"fullscreen_overlays": overlays}))

        def advance(count: int) -> None:
            for _ in range(count):
                feature = next(frames)
                clock[0] = feature.timestamp_us / 1_000_000.0
                controller.playing = feature.playing
                engine.set_playback_state(feature.playing)
                engine.accept_feature_frame(feature)
                assert logical_tick(controller.logical_tick_state) is not None
                sync.sync_latest()
                host.render()
            host.render()

        def show(record, *, overlays_drawn: bool) -> None:
            route["record"] = record
            scene.set_visualizer_expanded_overlays_drawn(overlays_drawn)
            advance(3)

        try:
            advance(WARMUP_FRAMES)
            # The discriminating control: Default keeps a margin, so the same reading sees the wallpaper on all edges.
            show(records[DISPLAY_STYLE_DEFAULT], overlays_drawn=True)
            readings["default"] = _edge_reading(host.read(), display, dpr)
            for index, (entry_shift, step_shift) in enumerate(ENTRIES):
                # Between entries the ordinary card moves with pixel shift, as every card does.
                show(ordinary, overlays_drawn=False)
                shift(*entry_shift)
                advance(2)
                expected = (snap_to_device_pixels(entry_shift[0], dpr), snap_to_device_pixels(entry_shift[1], dpr))
                places.append((f"ordinary@{entry_shift}", scene_origin(loader),
                               (loader.x() + expected[0], loader.y() + expected[1])))
                show(records[DISPLAY_STYLE_HIDE_BORDERS], overlays_drawn=True)
                readings[f"entry{index}@{entry_shift}"] = _edge_reading(host.read(), display, dpr)
                places.append((f"hide_borders_card@{entry_shift}", scene_origin(loader), (0.0, 0.0)))
                overlay_layer = scene._visualizer_root.findChild(QQuickItem, "visualizerExpandedOverlays")
                assert overlay_layer is not None
                # The full-display overlays keep the shift (burn-in), the card does not.
                places.append((f"overlays@{entry_shift}", scene_origin(overlay_layer), expected))
                shift(*step_shift)
                advance(2)
                readings[f"entry{index}@{entry_shift}->{step_shift}"] = _edge_reading(host.read(), display, dpr)
                stepped = (snap_to_device_pixels(step_shift[0], dpr), snap_to_device_pixels(step_shift[1], dpr))
                places.append((f"hide_borders_card@{step_shift}", scene_origin(loader), (0.0, 0.0)))
                places.append((f"overlays@{step_shift}", scene_origin(overlay_layer), stepped))
                show(records[DISPLAY_STYLE_BORDERS_TO_EDGE], overlays_drawn=True)
                frames_read[f"borders_to_edge@{step_shift}"] = _frame_runs(host.read(), display, dpr)
                # The Default style keeps moving with the shift (its margin holds the shift on the display).
                show(records[DISPLAY_STYLE_DEFAULT], overlays_drawn=True)
                places.append((f"default_card@{step_shift}", scene_origin(loader),
                               (loader.x() + stepped[0], loader.y() + stepped[1])))
        finally:
            controller.close_render_admission()

    control = readings.pop("default")
    assert all(control[edge]["wallpaper"] > 0 for edge in ("left", "right", "top", "bottom")), control
    seen = {name: reading for name, reading in readings.items()
            if any(counts["wallpaper"] or counts["border"] for counts in reading.values())}
    assert seen == {}
    uneven = {name: runs for name, runs in frames_read.items()
              if any(edge != (0, frame_px) for edge in runs.values())}
    assert uneven == {}, frame_px
    wrong = [(name, actual, expected) for name, actual, expected in places
             if actual != pytest.approx(expected, abs=1e-3)]   # mapToScene is float32
    assert wrong == []
