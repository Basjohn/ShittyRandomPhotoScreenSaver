"""Offscreen renders of the Fullscreen Visualizer's display styles (Current_Plan 1D.2) for the lead's pixel review.

    .venv/Scripts/python tools/expanded_display_styles_evidence.py --label review

For each mode (a 2D mode and a 3D framed mode by default) and each display style (Default, Borders To Edge,
Fullscreen (Hide Borders)), a recorded clip replays through the production controller into the production
``DisplayScene.qml`` on the hidden ``QQuickRenderControl`` host (``tools/expanded_visualizer_evidence.
HiddenDisplayHost``; no window is ever shown), on a real photo wallpaper, with the preset toast on its own card.
Written (PNG): ``<mode>__<style>.png`` (the whole display), one sheet per mode with the three styles side by side
and 4x nearest-neighbour crops of the card's top-left corner and right edge, and ``report.json`` (each style's
record: outer and content rects, border, radius, extent, scale, glyph inset, safe inset).

Offscreen output is not physical acceptance: the overscan, the window and Qt Quick's stretch on a real display are
the lead's D1 run (``tools/d1_run.py``: its display-styles recipe).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PHOTO = Path(r"C:\Users\Basjohn\Documents\[4] WALLPAPERS\PERSONALSET\859804.png")
MODES = ("devcurve", "extruded_bubble")
CARD = {"border_width": 5.0, "corner_radius": 8.0, "content_inset": 0.0, "background_color": (14, 16, 22, 210),
        "border_color": (214, 178, 255, 255), "shadow_enabled": True, "shadow_color": (0, 0, 0, 150),
        "shadow_blur": 12.0, "shadow_offset": (0.0, 4.0), "shadow_spread": 0.0,
        "shadow_extensions": (0.0, 0.0, 0.0, 2.0)}


def _wallpaper(path: Path, logical: tuple[int, int], dpr: float):
    from PIL import Image, ImageOps

    from rendering.quick.image_state import PresentationImage

    pixels = (round(logical[0] * dpr), round(logical[1] * dpr))
    image = ImageOps.fit(Image.open(path).convert("RGB"), pixels, Image.Resampling.LANCZOS).convert("RGBA")
    return PresentationImage(f"display-styles:{path.name}", str(path), (float(logical[0]), float(logical[1])), dpr,
                             pixels, pixels[0] * 4, image.tobytes())


def render_mode(mode: str, *, logical: tuple[int, int], dpr: float, frames: int, photo: Path) -> dict:
    """Each style's frame (RGB numpy) and its facts, from one replay per style on one hidden host."""
    from core.settings.fullscreen_overlays import DISPLAY_STYLES, canonical_fullscreen_overlays
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    from tools.expanded_visualizer_evidence import HiddenDisplayHost, shipped_clip
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from widgets.spotify_visualizer.expanded_overlays import resolve_expanded_overlay_config
    from widgets.spotify_visualizer.feature_replay import configure_offline_controller, deterministic_clock
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_expanded_visualizer_presentation,
        resolve_visualizer_presentation,
    )
    from widgets.spotify_visualizer.quick_presentation_sync import QuickVisualizerPresentationSync
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.tick_pipeline import logical_tick

    host = HiddenDisplayHost(*logical, dpr=dpr)
    results: dict = {}
    try:
        scene = host.scene
        if photo.is_file():
            scene.set_presentation_image(_wallpaper(photo, logical, dpr))
        ordinary = resolve_visualizer_presentation(
            policy=get_visualizer_presentation_policy(mode), display_size=logical,
            outer_origin=(24.0, logical[1] - 280.0 - 24.0), dpr=dpr, **CARD)
        overlays = canonical_fullscreen_overlays()
        overlays["preset"].update(card=True, always_show=True)
        clip = shipped_clip(max(4.0, frames / 60.0 + 1.0))
        for style in DISPLAY_STYLES:
            record = resolve_expanded_visualizer_presentation(ordinary, display_size=logical, dpr=dpr,
                                                              display_style=style)
            with deterministic_clock() as clock:
                engine = ReplayBeatEngine(32)
                controller = VisualizerRuntimeController(runtime_generation=1, initial_mode=mode,
                                                         engine_factory=lambda _count, e=engine: e)
                controller.engine = engine
                configure_offline_controller(controller, mode, settings=frozen_visualizer_settings(mode))
                identity = controller.begin_render_activation(
                    engine_generation=engine.get_generation_id(), activation_id=engine.get_activation_id())
                scene.set_visualizer_render_source(controller.render_bridge, identity)
                sync = QuickVisualizerPresentationSync(
                    controller, resolve_presentation=lambda r=record: r,
                    commit_presentation=lambda presentation: scene.apply_visualizer_presentation(
                        presentation, active=True),
                    request_present=scene.request_visualizer_present)
                scene.set_visualizer_expanded_overlay_config(
                    resolve_expanded_overlay_config({"fullscreen_overlays": overlays}))
                scene.announce_visualizer_preset("Display Style: " + style.replace("_", " ").title(), reveal=True)
                scene.set_visualizer_expanded_overlays_drawn(True)
                for feature in clip.frames[:frames]:
                    clock[0] = feature.timestamp_us / 1_000_000.0
                    controller.playing = feature.playing
                    engine.set_playback_state(feature.playing)
                    engine.accept_feature_frame(feature)
                    if logical_tick(controller.logical_tick_state) is None:
                        raise RuntimeError("missing logical frame")
                    sync.sync_latest()
                    host.render()
                for _ in range(3):
                    host.render()
                rgba = host.read()
                root = scene._visualizer_root
                stage = scene._expanded_overlay_stage()
                results[style] = {
                    "image": rgba[..., :3].copy(),
                    "facts": {
                        "outer_rect": list(record.outer_rect), "content_rect": list(record.content_rect),
                        "border_width": record.border_width,
                        "corner_radius": float(record.shell_style["corner_radius"]),
                        "shadow_enabled": bool(record.shell_style["shadow_enabled"]),
                        "viewport_extent": list(record.viewport_extent),
                        "uniform_visual_scale": record.uniform_visual_scale,
                        "glyph_row_inset": float(root.property("glyphRowInset")),
                        "safe_inset": None if stage is None else float(stage.property("safeInset")),
                    },
                }
                scene.set_visualizer_expanded_overlays_drawn(False)
                controller.close_render_admission()
    finally:
        host.close()
    return results


def _sheet(mode: str, results: dict, dpr: float, out: Path) -> Path:
    from PIL import Image, ImageDraw

    styles = list(results)
    full = [Image.fromarray(results[s]["image"], "RGB") for s in styles]
    thumb_w = 640
    thumbs = [image.resize((thumb_w, round(image.height * thumb_w / image.width)), Image.Resampling.LANCZOS)
              for image in full]
    crop, zoom = 40, 4
    crops = []
    for style, image in zip(styles, full):
        x, y, w, h = results[style]["facts"]["outer_rect"]
        points = {"top-left": (x * dpr, y * dpr), "right-mid": ((x + w) * dpr, (y + h / 2) * dpr)}
        row = []
        for name, (px, py) in points.items():
            left = int(min(max(0, round(px - crop / 2)), image.width - crop))
            top = int(min(max(0, round(py - crop / 2)), image.height - crop))
            row.append((name, image.crop((left, top, left + crop, top + crop)).resize((crop * zoom, crop * zoom),
                                                                                       Image.Resampling.NEAREST)))
        crops.append(row)
    label_h = 28
    height = label_h + thumbs[0].height + 8 + crop * zoom + label_h
    sheet = Image.new("RGB", (len(styles) * (thumb_w + 16) + 16, height), (24, 24, 28))
    draw = ImageDraw.Draw(sheet)
    for index, style in enumerate(styles):
        x0 = 16 + index * (thumb_w + 16)
        draw.text((x0, 8), f"{mode} - {style}", fill=(235, 235, 235))
        sheet.paste(thumbs[index], (x0, label_h))
        cx = x0
        for name, image in crops[index]:
            sheet.paste(image, (cx, label_h + thumbs[index].height + 8))
            draw.text((cx, label_h + thumbs[index].height + 12 + crop * zoom), f"{name} x{zoom}", fill=(200, 200, 200))
            cx += crop * zoom + 8
    path = out / f"{mode}__sheet.png"
    sheet.save(path)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--label", default="review")
    parser.add_argument("--modes", nargs="+", default=list(MODES))
    parser.add_argument("--logical", type=int, nargs=2, default=(1280, 720))
    parser.add_argument("--dpr", type=float, default=1.5)
    parser.add_argument("--frames", type=int, default=150)
    parser.add_argument("--photo", type=Path, default=PHOTO)
    args = parser.parse_args(argv)
    sys.path.insert(0, os.path.abspath(args.repo))
    from tools import artifact_paths

    artifact_paths.repository_root(args.repo)
    from rendering.gl_error_policy import disable_per_call_gl_error_checking

    disable_per_call_gl_error_checking()
    if os.environ.get("QT_QPA_PLATFORM", "").lower() not in ("", "windows"):
        raise SystemExit("needs the Windows QPA (hidden GL); nothing is ever shown")
    from rendering.quick.bootstrap import configure_quick_graphics

    configure_quick_graphics(reason="expanded-display-styles-evidence")
    from PySide6.QtWidgets import QApplication

    app = QApplication(["expanded-display-styles-evidence"])
    destination = artifact_paths.evidence_dir("visualizers/shared", "expanded_display_styles", args.label)
    from PIL import Image

    from tools import evidence_media

    report = {"logical": list(args.logical), "dpr": args.dpr, "photo": args.photo.name, "modes": {}}
    # Written in owner scratch and published unchanged (stills stay PNG) only when every mode rendered.
    with evidence_media.evidence_workspace("expanded_display_styles", destination) as out:
        out.mkdir(parents=True, exist_ok=True)
        for mode in args.modes:
            results = render_mode(mode, logical=tuple(args.logical), dpr=args.dpr, frames=args.frames,
                                  photo=args.photo)
            for style, entry in results.items():
                Image.fromarray(entry["image"], "RGB").save(out / f"{mode}__{style}.png")
            _sheet(mode, results, args.dpr, out)
            report["modes"][mode] = {style: entry["facts"] for style, entry in results.items()}
            print(mode, {style: entry["facts"]["outer_rect"] for style, entry in results.items()}, flush=True)
        (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    app.processEvents()
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
