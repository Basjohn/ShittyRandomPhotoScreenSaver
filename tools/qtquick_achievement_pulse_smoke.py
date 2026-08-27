"""Render retained Achievement Pulse states through one real Quick window."""

from __future__ import annotations

import argparse
from dataclasses import replace
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
configure_quick_graphics(reason="qtquick-achievement-pulse-smoke")

from PySide6.QtCore import QEventLoop, QObject, QSize, Qt, QTimer  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
)
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402

from rendering.quick.scene_controller import QuickSceneFactory  # noqa: E402
from rendering.quick.widgets.achievement_pulse import (  # noqa: E402
    AchievementPulsePresentationConfig,
    AchievementPulsePresentationModel,
    AchievementPulsePresentationStyle,
    RetainedAchievementPulsePresentation,
)
from rendering.quick.widgets.host import (  # noqa: E402
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
)
from widgets.steam_achievement_preparation import (  # noqa: E402
    AchievementPulsePreparedPresentation,
)
from widgets.steam_card_models import (  # noqa: E402
    SteamCardViewModel,
    build_mock_steam_view_model,
    with_long_title,
    with_stale_connection_info,
    with_unavailable_state,
)


def _config(**overrides) -> AchievementPulsePresentationConfig:
    values = {
        "font_family": "Inter",
        "font_size": 14,
        "text_color": (248, 249, 252, 242),
        "show_background": True,
        "background_color": (24, 29, 36, 255),
        "background_opacity": 0.88,
        "border_color": (235, 238, 244, 255),
        "border_opacity": 0.9,
        "show_artwork": True,
        "artwork_shape": "portrait",
        "square_artwork_size": 140,
        "show_latest_artwork": True,
        "latest_unlock_count": 5,
        "double_capsules": True,
        "capsule_font_size": 12,
    }
    values.update(overrides)
    return replace(AchievementPulsePresentationConfig(), **values)


def _shadows(direction: str) -> dict[str, object]:
    return {
        "enabled": True,
        "direction": direction,
        "color": [0, 0, 0, 255],
        "blur_radius": 18,
        "frame_opacity": 0.76,
        "frame_extra_offset": 1,
        "text_enabled": True,
        "text_opacity": 0.48,
        "text_extra_offset": 1,
    }


def _synthetic_art(path: Path, *, accent: QColor, portrait: bool) -> QImage:
    width, height = (360, 504) if portrait else (720, 344)
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        gradient = QLinearGradient(0.0, 0.0, float(width), float(height))
        gradient.setColorAt(0.0, accent.lighter(150))
        gradient.setColorAt(0.55, accent)
        gradient.setColorAt(1.0, QColor(14, 18, 24))
        painter.fillRect(image.rect(), gradient)
        painter.setPen(QColor(255, 255, 255, 210))
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(max(24, width // 10))
        painter.setFont(font)
        painter.drawText(
            image.rect().adjusted(20, 20, -20, -20),
            Qt.AlignmentFlag.AlignCenter,
            "ACHIEVEMENT\nPULSE",
        )
    finally:
        painter.end()
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"failed to save synthetic art {path}")
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
        raise RuntimeError("Achievement Pulse grabToImage returned a null image")
    return image


def _busy(image: QImage, path: Path) -> None:
    canvas = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
    overlay = image.copy()
    overlay.setDevicePixelRatio(1.0)
    painter = QPainter(canvas)
    try:
        tile = max(24, image.width() // 12)
        colors = (QColor(22, 62, 88), QColor(105, 48, 54))
        for y in range(0, image.height(), tile):
            for x in range(0, image.width(), tile):
                painter.fillRect(
                    x,
                    y,
                    tile,
                    tile,
                    colors[(x // tile + y // tile) % 2],
                )
        painter.drawImage(0, 0, overlay)
    finally:
        painter.end()
    if not canvas.save(str(path), "PNG"):
        raise RuntimeError(f"failed to save {path}")


def _prepared(
    model: SteamCardViewModel,
    *,
    artwork: QImage,
    artwork_path: Path,
    latest_artwork: QImage,
    latest_path: Path,
) -> AchievementPulsePreparedPresentation:
    return AchievementPulsePreparedPresentation(
        model=model,
        artwork=artwork,
        artwork_identity=str(artwork_path),
        artwork_key=f"{model.appid or 0}:smoke",
        latest_artwork=latest_artwork,
        latest_artwork_identity=str(latest_path),
        latest_artwork_key="smoke-unlock",
    )


def run(output_dir: Path) -> dict[str, object]:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    output_dir.mkdir(parents=True, exist_ok=True)
    portrait_path = output_dir / "synthetic_portrait.png"
    wide_path = output_dir / "synthetic_wide.png"
    latest_path = output_dir / "synthetic_latest.png"
    portrait = _synthetic_art(
        portrait_path,
        accent=QColor(53, 126, 167),
        portrait=True,
    )
    wide = _synthetic_art(
        wide_path,
        accent=QColor(123, 73, 166),
        portrait=False,
    )
    latest = _synthetic_art(
        latest_path,
        accent=QColor(190, 128, 45),
        portrait=False,
    )

    owner = QObject()
    factory = QuickSceneFactory(owner)
    window = QQuickWindow()
    window.resize(1540, 1180)
    context, root = factory.create_display_root(
        owner=owner,
        screen_index=0,
        runtime_generation=1,
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

    base = build_mock_steam_view_model("achievement_pulse")
    stale = with_stale_connection_info(
        base,
        cache_age_seconds=26 * 60 * 60,
        enabled=True,
        connection_needs_attention=True,
    )
    cases = (
        (
            "achievement_portrait_card",
            _config(),
            "SE",
            base,
            portrait,
            portrait_path,
            OverlayWidgetGeometry(30, 25, 600, 334),
        ),
        (
            "achievement_square_long_card",
            _config(artwork_shape="square", square_artwork_size=170),
            "NW",
            with_long_title(base),
            portrait,
            portrait_path,
            OverlayWidgetGeometry(700, 25, 600, 318),
        ),
        (
            "achievement_wide_no_card",
            _config(show_background=False, artwork_shape="wide"),
            "W",
            stale,
            wide,
            wide_path,
            OverlayWidgetGeometry(30, 410, 600, 290),
        ),
        (
            "achievement_unavailable_no_art",
            _config(show_artwork=False, show_latest_artwork=False),
            "S",
            with_unavailable_state(base),
            QImage(),
            portrait_path,
            OverlayWidgetGeometry(700, 410, 600, 290),
        ),
    )
    connect_case = (
        "achievement_connect_card",
        _config(artwork_shape="wide"),
        "E",
        None,
        QImage(),
        wide_path,
        OverlayWidgetGeometry(30, 790, 600, 290),
    )

    presentations = []
    manifest = []
    try:
        for name, config, direction, card, art, art_path, geometry in (
            *cases,
            connect_case,
        ):
            style = AchievementPulsePresentationStyle.project(
                config,
                _shadows(direction),
            )
            model = AchievementPulsePresentationModel(
                config,
                style,
                parent=owner,
            )
            presentation = RetainedAchievementPulsePresentation(
                host=host,
                model=model,
                geometry=geometry,
                fade_opacity=1.0,
            )
            presentation.activate()
            model.set_interaction_enabled(True)
            if card is not None:
                model.on_achievement_presentation(
                    _prepared(
                        card,
                        artwork=art,
                        artwork_path=art_path,
                        latest_artwork=latest,
                        latest_path=latest_path,
                    ),
                    animate=False,
                )
            presentations.append(
                (name, config, direction, geometry, presentation)
            )

        window.show()
        settle = QEventLoop()
        QTimer.singleShot(1200, settle.quit)
        settle.exec()
        for name, config, direction, geometry, presentation in presentations:
            image = _grab(
                presentation.item,
                QSize(int(geometry.width), int(geometry.height)),
            )
            path = output_dir / f"{name}.png"
            busy_path = output_dir / f"{name}_busy.png"
            if not image.save(str(path), "PNG"):
                raise RuntimeError(f"failed to save {path}")
            _busy(image, busy_path)
            manifest.append(
                {
                    "name": name,
                    "direction": direction,
                    "card": config.show_background,
                    "artwork_shape": config.artwork_shape,
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
