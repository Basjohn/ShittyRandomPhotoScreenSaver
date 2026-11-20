"""Render retained Media controls/progress/volume/mute on the hidden Windows-QPA GL host.

The production ``DisplayScene`` is drawn by ``QQuickRenderControl`` into a hidden GL texture
(``tools/onboarding_preview_foundry._HiddenQuickScene``, the same host
``tools/surface_material_capture.py`` uses); no window is shown. Offscreen QPA is not used: it draws
blank artwork. Run it with the default Windows QPA.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo  # noqa: E402
from rendering.quick.widgets.host import OverlayWidgetGeometry  # noqa: E402
from rendering.quick.widgets.media import (  # noqa: E402
    MediaPresentationConfig,
    MediaPresentationModel,
    MediaPresentationStyle,
    RetainedMediaPresentation,
)
from widgets.media_runtime import MediaRuntimeSnapshot, PreparedMediaArtwork  # noqa: E402
from widgets.media_volume_runtime import MediaVolumeRuntimeSnapshot  # noqa: E402
from widgets.system_mute_runtime import SystemMuteRuntimeSnapshot  # noqa: E402
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
if str(_Path(__file__).resolve().parents[1]) not in _sys.path:
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from tools import artifact_paths  # noqa: E402
from tools import evidence_media  # noqa: E402


class _Runtime:
    def __init__(self) -> None:
        self.consumer = None
        self.running = False

    def set_thread_manager(self, _manager) -> None:
        return

    def attach_consumer(self, consumer) -> None:
        self.consumer = consumer

    def detach_consumer(self, consumer=None) -> None:
        if consumer is None or consumer is self.consumer:
            self.consumer = None

    def start(self) -> bool:
        self.running = True
        return True

    def stop(self) -> None:
        self.running = False

    def refresh(self, *, bust_cache=False) -> bool:
        del bust_cache
        return True

    def set_provider_runtime(self, _provider, *, source="settings") -> bool:
        del source
        return True

    def seek_fraction(self, _fraction, *, execute=True) -> bool:
        return bool(execute)


class _VolumeRuntime:
    def __init__(self) -> None:
        self.consumer = None
        self.running = False
        self.snapshot = MediaVolumeRuntimeSnapshot(
            revision=1,
            provider="spotify",
            browser_process=None,
            supported=True,
            available=True,
            level=0.68,
            source="smoke",
        )

    def set_thread_manager(self, _manager) -> None:
        return

    def attach_consumer(self, consumer) -> None:
        self.consumer = consumer

    def detach_consumer(self, consumer=None) -> None:
        if consumer is None or consumer is self.consumer:
            self.consumer = None

    def start(self) -> bool:
        self.running = True
        return True

    def stop(self) -> None:
        self.running = False

    def current_snapshot(self):
        return self.snapshot

    def set_provider_runtime(self, _provider) -> bool:
        return True

    def set_runtime_volume_source(self, _provider, _source_id) -> bool:
        return True

    def set_volume_optimistic(self, _level) -> bool:
        return True


class _SystemMuteRuntime:
    def __init__(self, *, muted: bool) -> None:
        self.consumer = None
        self.running = False
        self.snapshot = SystemMuteRuntimeSnapshot(
            revision=1,
            available=True,
            muted=bool(muted),
            source="smoke",
        )

    def set_thread_manager(self, _manager) -> None:
        return

    def attach_consumer(self, consumer) -> None:
        self.consumer = consumer

    def detach_consumer(self, consumer=None) -> None:
        if consumer is None or consumer is self.consumer:
            self.consumer = None

    def start(self) -> bool:
        self.running = True
        return True

    def stop(self) -> None:
        self.running = False

    def current_snapshot(self):
        return self.snapshot

    def toggle_mute(self) -> bool:
        return True

    def step_system_volume(self, _delta) -> float:
        return 0.5


def _config(**overrides) -> MediaPresentationConfig:
    values = {
        "provider": "spotify",
        "font_family": "Inter",
        "font_size": 22,
        "color": [245, 248, 252, 240],
        "show_background": True,
        "bg_color": [24, 31, 42, 255],
        "bg_opacity": 0.88,
        "border_color": [115, 190, 255, 255],
        "border_opacity": 0.9,
        "show_header_frame": True,
        "artwork_size": 210,
        "rounded_artwork_border": True,
        "show_controls": True,
        "playback_progress_enabled": True,
        "playback_progress_height": 7,
        "playback_progress_fill_color": [50, 205, 255, 235],
        "playback_progress_shadow_enabled": True,
        "playback_progress_glow_enabled": True,
        "playback_progress_glow_color": [50, 205, 255, 180],
        "spotify_volume_enabled": True,
        "spotify_volume_fill_color": [255, 255, 255, 190],
        "mute_button_enabled": True,
    }
    values.update(overrides)
    return MediaPresentationConfig.from_mapping(values)


def _shadows(direction: str) -> dict[str, object]:
    return {
        "enabled": True,
        "color": [0, 0, 0, 255],
        "blur_radius": 18,
        "frame_opacity": 0.77,
        "frame_extra_offset": 1,
        "text_enabled": True,
        "soft_text_on_light_themes": False,
        "header_enabled": True,
        "text_opacity": 0.5,
        "text_extra_offset": 1,
        "direction": direction,
    }


def _artwork(color: str) -> QImage:
    image = QImage(480, 360, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        painter.fillRect(image.rect(), QColor(color))
        painter.fillRect(0, 0, 240, 180, QColor("#ffcf57"))
        painter.fillRect(240, 180, 240, 180, QColor("#5ce1e6"))
    finally:
        painter.end()
    return image


def _busy(image, path: Path) -> None:
    """``image`` (PIL RGBA) over a checker of dark tiles, saved as PNG."""

    from PIL import Image, ImageDraw

    canvas = Image.new("RGBA", image.size, (0, 0, 0, 255))
    draw = ImageDraw.Draw(canvas)
    tile = max(24, image.width // 12)
    colors = ((20, 58, 88, 255), (118, 52, 42, 255))
    for y in range(0, image.height, tile):
        for x in range(0, image.width, tile):
            draw.rectangle((x, y, x + tile - 1, y + tile - 1), fill=colors[(x // tile + y // tile) % 2])
    canvas.alpha_composite(image)
    canvas.convert("RGB").save(path)


def run(output_dir: Path) -> dict[str, object]:
    from tools import onboarding_preview_foundry as foundry
    from rendering.quick.widgets.media import (
        MediaPresentationModel,
        MediaPresentationStyle,
        RetainedMediaPresentation,
    )
    from widgets.media_runtime import MediaRuntimeSnapshot, PreparedMediaArtwork

    foundry.open_hidden_gl_application("qtquick-media-smoke")
    scene_size = (1180, 880)
    scene = foundry._HiddenQuickScene(*scene_size, dpr=1.0)
    owner = scene.owner
    factory = scene.factory
    host = scene.host
    cases = (
        (
            "media_playing_art_card_se",
            _config(),
            "SE",
            _artwork("#8d4de8"),
            MediaPlaybackState.PLAYING,
            OverlayWidgetGeometry(35, 35, 620, 330),
        ),
        (
            "media_paused_art_no_card_nw",
            _config(show_background=False, artwork_size=165),
            "NW",
            _artwork("#e84d75"),
            MediaPlaybackState.PAUSED,
            OverlayWidgetGeometry(35, 400, 560, 280),
        ),
        (
            "media_playing_no_art_w",
            _config(provider="musicbee", artwork_size=145),
            "W",
            None,
            MediaPlaybackState.PLAYING,
            OverlayWidgetGeometry(680, 35, 450, 235),
        ),
        (
            "media_empty_card_s",
            _config(show_header_frame=False),
            "S",
            None,
            MediaPlaybackState.UNKNOWN,
            OverlayWidgetGeometry(680, 400, 420, 190),
        ),
        (
            "media_progress_glow_off_reference",
            _config(
                provider="musicbee",
                artwork_size=145,
                playback_progress_glow_enabled=False,
            ),
            "W",
            None,
            MediaPlaybackState.PLAYING,
            # Its own slot: every case shares the one hidden scene.
            OverlayWidgetGeometry(680, 610, 450, 235),
        ),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    presentations = []
    manifest = []
    try:
        for index, (name, config, direction, art, state, geometry) in enumerate(
            cases, 1
        ):
            runtime = _Runtime()
            # The host keys retained widgets by identity; give each case its own.
            config = replace(config, widget_id=f"media_smoke_{index}")
            style = MediaPresentationStyle.project(config, _shadows(direction))
            model = MediaPresentationModel(
                config,
                style,
                factory.media_artwork_provider,
                runtime,
                volume_runtime_service=_VolumeRuntime(),
                system_mute_runtime_service=_SystemMuteRuntime(
                    muted=index % 2 == 0
                ),
                parent=owner,
            )
            presentation = RetainedMediaPresentation(
                host=host, model=model, geometry=geometry
            )
            presentation.activate(object())
            info = (
                None
                if "empty" in name
                else MediaTrackInfo(
                    title="Midnight City"
                    if index < 3
                    else "A Very Long Track Name for Layout Proof",
                    artist="M83" if index < 3 else "Synthetic Artist",
                    album="Hurry Up, We're Dreaming",
                    state=state,
                    can_play_pause=True,
                    can_next=True,
                    can_previous=True,
                    can_seek=True,
                    position_ms=60_000,
                    duration_ms=240_000,
                )
            )
            key = (index * 100, str(index) * 40) if art is not None else (0, "")
            model.on_media_runtime_snapshot(
                MediaRuntimeSnapshot(
                    index, config.provider, info, PreparedMediaArtwork(key, art, 0.0)
                )
            )
            if art is not None and not model.hasArtwork:
                raise RuntimeError(f"{name}: artwork was not admitted")
            presentations.append((name, config, direction, geometry, presentation))
        # Every case shares the scene, so they settle together and are cropped from one frame.
        scene.settle(
            minimum_ms=1200,
            until=lambda: not any(foundry._unsettled_images(p.item) for *_rest, p in presentations),
        )
        frame = scene.read()
        sheet_cases = []
        for name, config, direction, geometry, presentation in presentations:
            image = foundry.crop_item(scene, frame, presentation.item)
            sheet_cases.append((name, image))
            path = output_dir / f"{name}.png"
            busy_path = output_dir / f"{name}_busy.png"
            image.save(path)
            _busy(image, busy_path)
            manifest.append(
                {
                    "name": name,
                    "direction": direction,
                    "card": config.show_background,
                    "progress_glow": config.playback_progress_glow_enabled,
                    "image_size": [image.width, image.height],
                    "path": str(path.resolve()),
                    "busy_background_path": str(busy_path.resolve()),
                }
            )
        foundry.write_review_sheet(sheet_cases, output_dir / "review_sheet.png")
    finally:
        scene.close()
    payload = {
        "graphics_api": "OpenGL",
        "render_loop": "hidden QQuickRenderControl",
        "device_pixel_ratio": scene.dpr,
        "cases": manifest,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["manifest"] = str(manifest_path.resolve())
    return payload



def _run_published(output_dir: Path) -> dict[str, object]:
    """``run`` in an owner scratch folder; its output is published to ``output_dir`` unchanged."""
    with evidence_media.evidence_workspace('qtquick_media_smoke', output_dir) as work:
        return run(work)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=artifact_paths.evidence_arg,
                        default=artifact_paths.default_evidence("widgets", "media_smoke"))
    args = parser.parse_args()
    print(json.dumps(_run_published(args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
