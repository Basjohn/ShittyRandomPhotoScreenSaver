"""Render retained Media controls/progress/app-volume through a real Quick window."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rendering.quick.bootstrap import (  # noqa: E402
    configure_quick_environment,
    configure_quick_graphics,
)


configure_quick_environment()
configure_quick_graphics(reason="qtquick-media-smoke")

from PySide6.QtCore import QEventLoop, QObject, QSize, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo  # noqa: E402
from rendering.quick.scene_controller import QuickSceneFactory  # noqa: E402
from rendering.quick.widgets import (  # noqa: E402
    MediaPresentationConfig,
    MediaPresentationModel,
    MediaPresentationStyle,
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
    RetainedMediaPresentation,
)
from widgets.media_runtime import MediaRuntimeSnapshot, PreparedMediaArtwork  # noqa: E402
from widgets.media_volume_runtime import MediaVolumeRuntimeSnapshot  # noqa: E402


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


def _grab(item: QQuickItem, size: QSize) -> QImage:
    result = item.grabToImage(size)
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    result.ready.connect(loop.quit)
    timer.start(5000)
    loop.exec()
    timer.stop()
    image = result.image()
    if image.isNull():
        raise RuntimeError("Media grabToImage returned a null image")
    return image


def _busy(image: QImage, path: Path) -> None:
    canvas = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(canvas)
    try:
        tile = max(24, image.width() // 12)
        colors = (QColor(20, 58, 88), QColor(118, 52, 42))
        for y in range(0, image.height(), tile):
            for x in range(0, image.width(), tile):
                painter.fillRect(x, y, tile, tile, colors[(x // tile + y // tile) % 2])
        painter.drawImage(0, 0, image)
    finally:
        painter.end()
    if not canvas.save(str(path), "PNG"):
        raise RuntimeError(f"failed to save {path}")


def run(output_dir: Path) -> dict[str, object]:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    owner = QObject()
    factory = QuickSceneFactory(owner)
    window = QQuickWindow()
    window.resize(1180, 760)
    context, root = factory.create_display_root(
        owner=owner, screen_index=0, runtime_generation=1
    )
    root.setParent(window.contentItem())
    root.setParentItem(window.contentItem())
    root.setWidth(window.width())
    root.setHeight(window.height())
    host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
    if host_item is None:
        raise RuntimeError("ordinary widget host is unavailable")
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
        create_family_item=factory.create_ordinary_widget_family,
    )
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
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    presentations = []
    manifest = []
    try:
        for index, (name, config, direction, art, state, geometry) in enumerate(
            cases, 1
        ):
            runtime = _Runtime()
            style = MediaPresentationStyle.project(config, _shadows(direction))
            model = MediaPresentationModel(
                config,
                style,
                factory.media_artwork_provider,
                runtime,
                volume_runtime_service=_VolumeRuntime(),
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
            presentations.append((name, config, direction, geometry, presentation))
        window.show()
        settle = QEventLoop()
        QTimer.singleShot(1200, settle.quit)
        settle.exec()
        for name, config, direction, geometry, presentation in presentations:
            image = _grab(
                presentation.item, QSize(int(geometry.width), int(geometry.height))
            )
            path = output_dir / f"{name}.png"
            busy_path = output_dir / f"{name}_busy.png"
            image.save(str(path), "PNG")
            _busy(image, busy_path)
            manifest.append(
                {
                    "name": name,
                    "direction": direction,
                    "card": config.show_background,
                    "image_size": [image.width(), image.height()],
                    "path": str(path.resolve()),
                    "busy_background_path": str(busy_path.resolve()),
                }
            )
    finally:
        host.retire_all()
        window.hide()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        window.deleteLater()
        owner.deleteLater()
        app.processEvents()
    payload = {
        "graphics_api": "OpenGL",
        "render_loop": "threaded",
        "device_pixel_ratio": window.devicePixelRatio(),
        "cases": manifest,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["manifest"] = str(manifest_path.resolve())
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
