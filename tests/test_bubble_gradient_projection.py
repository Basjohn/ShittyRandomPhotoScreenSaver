"""Driver-rendered compatibility for packed Bubble gradient inputs."""
import numpy as np

from core.settings.default_contract import require_canonical_default
from rendering.quick.visualizer.implementations import bubble
from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
from tools.labs.render_target import OffscreenRenderTarget
from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot


def test_existing_gradient_pixels_match_the_original_formula_on_the_driver(qt_app, monkeypatch):
    source = bubble.load_fragment_shader("bubble")
    # Original shader's centred dot product and integer radial branching. Keep
    # only the transport packed so both programs receive identical input data.
    reference = source.replace("float gradient_mode = u_gradient.w;", "int gradient_mode = int(u_gradient.w);")
    reference = reference.replace("gradient_mode == 1.0", "gradient_mode == 1").replace("gradient_mode == 2.0", "gradient_mode == 2")
    reference = reference.replace("dot(uv - center, grad_dir) + 0.5 + u_gradient.z", "dot(uv - center, grad_dir) + 0.5")
    assert reference != source
    target = OffscreenRenderTarget(160, 80)
    host = QuickVisualizerRenderHost()
    config = dict(require_canonical_default("widgets.spotify_visualizer"))
    matrix = (2/160, 0, 0, 0, 0, -2/80, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)

    def draw():
        target.bind()
        host.render(snapshot=snapshot, viewport=(0, 0, 160, 80), logical_size=(160., 80.), matrix_values=matrix)
        return target.read_rgba()

    try:
        snapshots = []
        for direction in ("top", "bottom", "left", "right", "top_left", "top_right", "bottom_left", "bottom_right",
                          "center_out", "center_out_reverse"):
            config["bubble_gradient_direction"] = direction
            snapshots.append(_build_spectrum_preview_snapshot(width=160, height=80, mode="bubble", settings=config))
        expected = []
        with monkeypatch.context() as patch:
            patch.setattr(bubble, "load_fragment_shader", lambda _mode: reference)
            for snapshot in snapshots:
                expected.append(draw())
        host.release_resources()
        for snapshot, old_pixels in zip(snapshots, expected):
            np.testing.assert_array_equal(draw(), old_pixels)
        # A real bias must affect pixels: the fixture discriminates the new input.
        snapshot = snapshots[5]
        original = draw()
        renderer = host._implementations["bubble"]
        project = renderer._gradient_parameters
        monkeypatch.setattr(renderer, "_gradient_parameters", lambda p, l: (*project(p, l)[:2], .25, 0.))
        assert np.any(draw() != original)
    finally:
        try:
            with target.current():
                host.release_resources()
        finally:
            target.close()
