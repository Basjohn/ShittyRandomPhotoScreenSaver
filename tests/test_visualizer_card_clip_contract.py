"""No Visualizer pixel lands outside the card's inner edge, for every registered mode (1C.4, R-187).

The production ``DisplayScene.qml`` and scene controller draw the card through a hidden ``QQuickRenderControl`` host
(``tools/expanded_visualizer_evidence.HiddenDisplayHost``; no window is ever shown). Each mode replays a shipped
clip at frozen test settings (never a curated preset). At each check the frame is read twice: as drawn, and again
with the mode's draw suppressed (``QuickVisualizerRenderHost.render`` returns without drawing), so the second read is
the same scene, chrome and frame with the Visualizer hidden. Every pixel whose centre lies more than 0.71 device pixel
outside the card's inner edge (the rounded inner path the card draws: content rect and inner corner radius, so the
corners are included) must be equal in both reads within 2 levels per channel.

Checks, on the card as drawn now (the item's own record):

* ``steady``: the ordinary card, coherent snapshot.
* ``shrunk``: the card takes a smaller record (a wheel resize) before a coherent snapshot exists, so the node draws
  the retained snapshot, whose record is larger than the card.
* ``expanded``: the display-wide card (Expanded Visualizer) for every mode that supports it.
* ``collapsed``: the ordinary card taken back from the display-wide one before a coherent snapshot exists (the
  retained snapshot's record is display-wide).

Each runs with Normal and with Glass card material. Before R-187 the node built its stencil clip from the retained
snapshot's record, so ``shrunk`` and ``collapsed`` let Spline Curve's fill and lines cross the card's rounded corners.
"""
from __future__ import annotations

import pytest

from core.settings.visualizer_mode_registry import (
    VisualizerShellPolicy,
    get_visualizer_mode_descriptor,
    get_visualizer_presentation_policy,
    iter_all_visualizer_mode_descriptors,
)

DISPLAY = (960, 600)
DPR = 1.0
TOLERANCE = 2              # 8-bit levels per channel
OUTSIDE_PX = 0.71          # a pixel whose centre lies this far out has no footprint inside the inner edge
FRAMES = 150               # replayed frames before the first check (every mode has drawn by then)
CARD = {
    "border_width": 2.0, "corner_radius": 8.0, "content_inset": 0.0,
    "background_color": (0, 0, 0, 255), "border_color": (0, 255, 0, 255),
    "shadow_enabled": False, "shadow_color": (0, 0, 0, 0), "shadow_blur": 0.0,
    "shadow_offset": (0.0, 0.0), "shadow_spread": 0.0, "shadow_extensions": (0.0, 0.0, 0.0, 0.0),
}
MODES = [descriptor.mode_id for descriptor in iter_all_visualizer_mode_descriptors()]


def _outside_inner_edge(presentation, shape):
    """Device pixels lying wholly outside the card's rounded inner path."""
    import numpy

    height, width = shape
    ys, xs = numpy.mgrid[0:height, 0:width].astype(numpy.float64)
    lx, ly = (xs + 0.5) / DPR, (ys + 0.5) / DPR
    x, y, w, h = presentation.content_rect
    radius = min(float(presentation.shell_style["inner_corner_radius"]), w / 2.0, h / 2.0)
    qx = numpy.abs(lx - (x + w / 2.0)) - (w / 2.0 - radius)
    qy = numpy.abs(ly - (y + h / 2.0)) - (h / 2.0 - radius)
    distance = (numpy.sqrt(numpy.maximum(qx, 0.0) ** 2 + numpy.maximum(qy, 0.0) ** 2)
                + numpy.minimum(numpy.maximum(qx, qy), 0.0) - radius)
    return distance * DPR > OUTSIDE_PX


def _settings(mode: str) -> dict:
    from tests._visualizer_frozen_settings import frozen_visualizer_settings

    settings = frozen_visualizer_settings(mode)
    overflow = get_visualizer_mode_descriptor(mode).renderer_overflow_setting
    if overflow:
        # A free-standing overflow renderer may draw past the card by its own declared choice; the card contract
        # binds every mode on the card's clip.
        settings[overflow] = False
    return settings


@pytest.fixture
def host(qt_app):
    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production scene needs the Windows QPA GL")
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    display = HiddenDisplayHost(*DISPLAY, dpr=DPR)
    try:
        yield display
    finally:
        display.close()


@pytest.mark.qt
@pytest.mark.parametrize("material", ["normal", "glass"])
@pytest.mark.parametrize("mode", MODES)
def test_no_visualizer_pixel_lands_outside_the_cards_inner_edge(host, mode, material):
    import numpy
    from unittest.mock import patch

    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.expanded_visualizer_evidence import shipped_clip
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from widgets.spotify_visualizer.feature_replay import (
        PcmReanalysis, configure_offline_controller, deterministic_clock,
    )
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_expanded_visualizer_presentation,
        resolve_visualizer_presentation,
    )
    from widgets.spotify_visualizer.quick_presentation_sync import QuickVisualizerPresentationSync
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.tick_pipeline import logical_tick

    descriptor = get_visualizer_mode_descriptor(mode)
    width, height = DISPLAY
    scene = host.scene

    def ordinary(scale: float = 1.0):
        return resolve_visualizer_presentation(
            policy=get_visualizer_presentation_policy(mode), display_size=DISPLAY,
            outer_origin=(24.0, height - 280.0 * scale - 24.0), dpr=DPR, uniform_visual_scale=scale, **CARD)

    route = {"record": ordinary()}

    def suppressed(self, *, snapshot, **_kwargs):
        return snapshot.logical.mode_id

    def read_pair():
        host.render()
        drawn = host.read()
        with patch.object(QuickVisualizerRenderHost, "render", suppressed):
            scene.request_visualizer_present()
            host.render()
            hidden = host.read()
        return drawn, hidden

    escapes: dict[str, int] = {}
    lit: dict[str, int] = {}

    def check(name: str) -> None:
        drawn, hidden = read_pair()
        card = scene.visualizer_item.presentation
        changed = numpy.abs(drawn[..., :3].astype(int) - hidden[..., :3].astype(int)).max(axis=2) > TOLERANCE
        outside = _outside_inner_edge(card, changed.shape)
        escapes[name] = int((changed & outside).sum())
        lit[name] = int((changed & ~outside).sum())

    clip = shipped_clip(4.0)
    with deterministic_clock() as clock:
        engine = ReplayBeatEngine(32)
        controller = VisualizerRuntimeController(runtime_generation=1, initial_mode=mode,
                                                 engine_factory=lambda _count: engine)
        controller.engine = engine
        configure_offline_controller(controller, mode, settings=_settings(mode))
        reanalysis = PcmReanalysis() if descriptor.raw_musical_signals else None
        identity = controller.begin_render_activation(
            engine_generation=engine.get_generation_id(), activation_id=engine.get_activation_id())
        scene.set_visualizer_render_source(controller.render_bridge, identity)
        sync = QuickVisualizerPresentationSync(
            controller, resolve_presentation=lambda: route["record"],
            commit_presentation=lambda presentation: scene.apply_visualizer_presentation(presentation, active=True),
            request_present=scene.request_visualizer_present,
        )
        frames = iter(clip.frames)

        def step() -> None:
            feature = next(frames)
            clock[0] = feature.timestamp_us / 1_000_000.0
            controller.playing = feature.playing
            engine.set_playback_state(feature.playing)
            assert engine.accept_feature_frame(feature)
            if reanalysis is not None:
                reanalysis.accept(engine, feature)
            assert logical_tick(controller.logical_tick_state) is not None
            assert sync.sync_latest()
            host.render()

        step()
        if material != "normal":
            assert scene.apply_visualizer_surface_material(material)
            host.render()
            # The material is card chrome: a frameless shell draws no card to put it on.
            carded = get_visualizer_presentation_policy(mode).shell_policy is VisualizerShellPolicy.CARD
            assert bool(scene._visualizer_root.property("cardSurfaceMaterialActive")) is carded
        for _ in range(FRAMES):
            step()
        check("steady")

        # A smaller record reaches the card before a coherent snapshot does.
        route["record"] = ordinary(0.85)
        scene.apply_visualizer_presentation(route["record"], active=True)
        check("shrunk")
        route["record"] = ordinary()
        for _ in range(4):
            step()

        if descriptor.supports_expanded_display:
            route["record"] = resolve_expanded_visualizer_presentation(ordinary(), display_size=DISPLAY, dpr=DPR)
            for _ in range(8):
                step()
            check("expanded")
            # The ordinary card comes back before a coherent snapshot does.
            route["record"] = ordinary()
            scene.apply_visualizer_presentation(route["record"], active=True)
            check("collapsed")
        controller.close_render_admission()

    assert lit["steady"] > 0, f"{mode} drew nothing inside the card: the check would be vacuous"
    assert escapes == {name: 0 for name in escapes}, (
        f"{mode} ({material}) changed pixels outside the card's inner edge: {escapes}")
