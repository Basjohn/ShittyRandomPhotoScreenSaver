"""Render retained Reddit/Reddit2 states through a real Quick window."""

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
configure_quick_graphics(reason="qtquick-reddit-smoke")

from PySide6.QtCore import QEventLoop, QObject, QSize, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402

from core.reddit_preparation import RedditPost  # noqa: E402
from rendering.quick.scene_controller import QuickSceneFactory  # noqa: E402
from rendering.quick.widgets.host import (  # noqa: E402
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
)
from rendering.quick.widgets.reddit import (  # noqa: E402
    RedditPresentationConfig,
    RedditPresentationModel,
    RedditPresentationStyle,
    RetainedRedditPresentation,
)


def _config(widget_id: str, **overrides) -> RedditPresentationConfig:
    values = {
        "subreddit": "wallpapers" if widget_id == "reddit" else "games",
        "limit": 5,
        "font_family": "Inter",
        "font_size": 19,
        "color": [245, 248, 252, 240],
        "show_background": True,
        "bg_color": [24, 31, 42, 255],
        "bg_opacity": 0.88,
        "border_color": [115, 190, 255, 255],
        "border_opacity": 0.9,
        "show_separators": True,
        "show_refresh_spiral": True,
    }
    values.update(overrides)
    return RedditPresentationConfig.from_mapping(values, widget_id=widget_id)


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


def _posts(now: float) -> tuple[RedditPost, ...]:
    return (
        RedditPost(
            "NASA reveals a new deep-space image - source",
            "https://reddit.com/r/wallpapers/comments/1",
            1250,
            now - 18 * 60,
        ),
        RedditPost(
            "A very long retained Reddit title proving single-line elision without recreating the row",
            "https://reddit.com/r/wallpapers/comments/2",
            870,
            now - 2 * 3600,
        ),
        RedditPost(
            "AI tools I use every day",
            "https://reddit.com/r/wallpapers/comments/3",
            640,
            now - 24 * 3600,
        ),
        RedditPost(
            "Small indie game reaches a big milestone",
            "https://reddit.com/r/games/comments/4",
            520,
            now - 15 * 24 * 3600,
        ),
    )


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
        raise RuntimeError("Reddit grabToImage returned a null image")
    return image


def _busy(image: QImage, path: Path) -> None:
    canvas = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(canvas)
    try:
        tile = max(24, image.width() // 12)
        colors = (QColor(20, 58, 88), QColor(118, 52, 42))
        for y in range(0, image.height(), tile):
            for x in range(0, image.width(), tile):
                painter.fillRect(
                    x, y, tile, tile, colors[(x // tile + y // tile) % 2]
                )
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
    window.resize(1280, 760)
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
        ("reddit_ready_card_se", _config("reddit"), "SE", "ready", 4, OverlayWidgetGeometry(35, 35, 590, 305)),
        ("reddit2_ready_no_card_nw", _config("reddit2", show_background=False, font_size=22), "NW", "ready", 3, OverlayWidgetGeometry(35, 400, 590, 275)),
        ("reddit_cached_error_w", _config("reddit", subreddit="python"), "W", "cached_error", 2, OverlayWidgetGeometry(675, 35, 550, 235)),
        ("reddit_empty_s", _config("reddit2", subreddit="games"), "S", "empty", 0, OverlayWidgetGeometry(675, 400, 520, 175)),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    presentations = []
    manifest = []
    now = 100_000_000.0
    try:
        for name, config, direction, state, count, geometry in cases:
            style = RedditPresentationStyle.project(config, _shadows(direction))
            model = RedditPresentationModel(config, style, parent=owner)
            if count:
                model.publish_posts(
                    _posts(now)[:count],
                    from_cache=state == "cached_error",
                    now_ts=now,
                )
            else:
                model.publish_posts((), now_ts=now)
            if state == "cached_error":
                model.publish_error("Offline - showing cached posts")
            presentation = RetainedRedditPresentation(
                host=host, model=model, geometry=geometry
            )
            presentation.activate()
            presentations.append((name, config, direction, geometry, presentation))
        window.show()
        settle = QEventLoop()
        QTimer.singleShot(1000, settle.quit)
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
