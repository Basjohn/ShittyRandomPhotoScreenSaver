"""Capture current Neon Lake art through the production GL host, without settings writes.

    .venv/Scripts/python tools/neon_lake_capture.py --output logs/neon_before --suite
    .venv/Scripts/python tools/neon_lake_capture.py --output logs/neon_dpr --size 650x375 --dpr 2

PNG pixels are actual GPU output, not a golden test. The JSON records the current mutable
Preset 1, canonical resolved settings, physical viewport, logical item and scene allocation.
The deterministic foundry audio fixture is not real-music or physical-window acceptance.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Match the production GL policy before importing any GL module.
from rendering.gl_error_policy import disable_per_call_gl_error_checking


def capture(output: Path, *, width=1300, height=750, dpr=1.0, overrides=None, window=None) -> dict:
    from OpenGL import GL as gl
    import numpy as np
    from PySide6.QtGui import QImage

    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from rendering.quick.scene3d.frame import item_pixel_rect
    from rendering.gl_error_policy import raise_pending_gl_error
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
    from tools.transition_contact_sheet import TransitionCapture

    activation = resolve_visualizer_activation_payload(
        {"mode": "shockwave_grid", "preset_shockwave_grid": 0}, mode="shockwave_grid")
    settings = {**activation.resolved_config, **(overrides or {})}
    snapshot = _build_spectrum_preview_snapshot(width=width, height=height, mode="shockwave_grid", settings=settings)
    window_width, window_height = window or (width, height)
    pixel_width, pixel_height = round(window_width * dpr), round(window_height * dpr)
    target = TransitionCapture(pixel_width, pixel_height)
    host = QuickVisualizerRenderHost()
    try:
        offset_x, offset_y = (window_width - width) / 2, (window_height - height) / 2
        matrix = (2 / window_width, 0, 0, 0, 0, -2 / window_height, 0, 0, 0, 0, 1, 0,
                  -1 + 2 * offset_x / window_width, 1 - 2 * offset_y / window_height, 0, 1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        gl.glViewport(0, 0, pixel_width, pixel_height)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glClearColor(0.1, 0.12, 0.16, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        host.render(snapshot=snapshot, viewport=(0, 0, pixel_width, pixel_height),
                    logical_size=(float(width), float(height)), matrix_values=matrix)
        raise_pending_gl_error(gl, "Neon Lake capture")
        gl.glFinish()
        pixels = gl.glReadPixels(0, 0, pixel_width, pixel_height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        rgba = np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(pixel_height, pixel_width, 4)[::-1].copy()
        output.parent.mkdir(parents=True, exist_ok=True)
        image = QImage(rgba.data, pixel_width, pixel_height, 4 * pixel_width, QImage.Format.Format_RGBA8888)
        if not image.save(str(output.with_suffix(".png"))):
            raise OSError(f"could not save {output}")
        renderer = host._implementations["shockwave_grid"]
        render_parameters = dict(snapshot.logical.mode_state.parameters)
        item_rect = item_pixel_rect(SimpleNamespace(viewport=(0, 0, pixel_width, pixel_height),
                                                   logical_size=(width, height), matrix_values=matrix))
        metadata = {
            "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                     capture_output=True, text=True, check=True).stdout.strip(),
            "renderer": target.driver,
            "preset_name": activation.preset_name, "preset_path": activation.preset_path,
            "logical_size": [width, height], "requested_dpr": dpr,
            "effective_dpr": [pixel_width / window_width, pixel_height / window_height],
            "physical_viewport": [0, 0, pixel_width, pixel_height],
            "physical_card_rect": [round(offset_x * dpr), round(offset_y * dpr),
                                   round(width * dpr), round(height * dpr)],
            "projected_item_pixel_rect_gl": item_rect,
            "logical_window": [window_width, window_height], "matrix": matrix,
            "scene_allocation_width_height_samples": renderer._target.allocation,
            "overrides": overrides or {}, "resolved_settings": settings,
            "effective_pose": {key: render_parameters[key] for key in (
                "shockwave_grid_tilt", "shockwave_grid_turn", "shockwave_grid_scene_scale",
                "shockwave_grid_scene_pan_x", "shockwave_grid_scene_pan_y")},
            "effective_scalar_render_parameters": {key: value for key, value in render_parameters.items()
                                                   if isinstance(value, (str, bool, int, float))},
            "fixture": "onboarding production capture; fixed analyser output at logical time 1.12",
        }
        output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        print(f"captured {output.with_suffix('.png')} ({pixel_width}x{pixel_height}, DPR {dpr})", flush=True)
        return metadata
    finally:
        host.release_resources()
        target.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, required=True, help="PNG stem, or directory with --suite")
    parser.add_argument("--size", default="1300x750", help="logical item dimensions")
    parser.add_argument("--dpr", type=float, default=1.0)
    parser.add_argument("--window", help="logical render-window size; centres the card inside it")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=JSON", help="in-memory settings override")
    parser.add_argument("--suite", action="store_true", help="baseline size, DPR, angle, zoom and aspect views")
    args = parser.parse_args()
    width, height = map(int, args.size.lower().split("x"))
    window = tuple(map(int, args.window.lower().split("x"))) if args.window else None
    if (min(width, height) <= 0 or not math.isfinite(args.dpr) or args.dpr <= 0
            or (window is not None and (len(window) != 2 or min(window) <= 0))):
        parser.error("dimensions and finite DPR must be positive")
    if min(round(value * args.dpr) for value in (window or (width, height))) <= 0:
        parser.error("DPR must produce positive physical dimensions")
    overrides = {}
    for pair in args.set:
        key, separator, value = pair.partition("=")
        if not separator:
            parser.error("--set requires KEY=JSON")
        overrides[key] = json.loads(value)
    if not disable_per_call_gl_error_checking():
        raise RuntimeError("OpenGL.GL imported before production error policy")
    cases = (
        ("large", 2100, 1200, 1., {}), ("medium", 1300, 750, 1., {}),
        ("small", 650, 375, 1., {}), ("small_dpr2", 650, 375, 2., {}),
        ("low", 1300, 750, 1., {"shockwave_grid_tilt": .17}),
        ("high", 1300, 750, 1., {"shockwave_grid_tilt": .58}),
        ("zoom_out", 1300, 750, 1., {"shockwave_grid_scene_scale": .75}),
        ("zoom_in", 1300, 750, 1., {"shockwave_grid_scene_scale": 1.85}),
        ("wide", 1600, 500, 1., {}), ("tall", 700, 1050, 1., {}),
        ("turned", 1300, 750, 1., {"shockwave_grid_turn": .2}),
        ("embedded_small", 650, 375, 1., {}, (2560, 1440)),
        ("embedded_medium", 1300, 750, 1., {}, (2560, 1440)),
        ("embedded_large", 2100, 1200, 1., {}, (2560, 1440)),
    ) if args.suite else ((None, width, height, args.dpr, {}),)
    for name, w, h, ratio, pose, *embedded in cases:
        capture(args.output / name if name else args.output, width=w, height=h, dpr=ratio,
                overrides={**overrides, **pose}, window=embedded[0] if embedded else window)


if __name__ == "__main__":
    main()
