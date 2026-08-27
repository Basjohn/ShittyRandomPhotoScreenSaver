"""Render retained Abandonment archive states through one real Quick window."""

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
configure_quick_graphics(reason="qtquick-abandonment-issues-smoke")

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
from rendering.quick.widgets.abandonment_issues import (  # noqa: E402
    AbandonmentIssuesPresentationConfig,
    AbandonmentIssuesPresentationModel,
    AbandonmentIssuesPresentationStyle,
    RetainedAbandonmentIssuesPresentation,
)
from rendering.quick.widgets.host import (  # noqa: E402
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
)
from widgets.steam_abandonment_preparation import (  # noqa: E402
    AbandonmentPreparedPresentation,
)
from widgets.steam_card_models import (  # noqa: E402
    SteamCardField,
    SteamCardViewModel,
)


def _config(**overrides) -> AbandonmentIssuesPresentationConfig:
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
        "artwork_size": 140,
        "accent_color": (222, 157, 88, 225),
    }
    values.update(overrides)
    return replace(AbandonmentIssuesPresentationConfig(), **values)


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


def _card(*, long_title: bool = False) -> SteamCardViewModel:
    return SteamCardViewModel(
        card_id="abandonment_issues",
        appid=753640,
        header="Abandonment Issues",
        title=(
            "The Extremely Long Forgotten Complete Collector's Edition"
            if long_title
            else "Outer Wilds"
        ),
        subtitle="You Don't Even Remember Buying This One Do You?",
        metric_label="Last Visit",
        metric_value="18 MONTHS AGO",
        status="BACKLOG 03/19",
        accent="#de9d58",
        fields=(
            SteamCardField("playtime", "Played", "18h"),
            SteamCardField("achievements", "Achievements", "7 / 31"),
            SteamCardField("last_unlock", "Last Unlock", "14 MONTHS AGO"),
            SteamCardField("last_played", "Last Played", "14/02/2025"),
            SteamCardField("archive_class", "Backlog Class", "Deep Backlog"),
            SteamCardField("queue", "Shelf", "3 of 19"),
        ),
    )


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
            "ABANDONMENT\nISSUES",
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
        raise RuntimeError("Abandonment grabToImage returned a null image")
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
    desaturation_bucket: int = 0,
) -> AbandonmentPreparedPresentation:
    return AbandonmentPreparedPresentation(
        model=model,
        artwork=artwork,
        artwork_identity=str(artwork_path) if not artwork.isNull() else "",
        desaturation_bucket=desaturation_bucket,
    )


def run(output_dir: Path) -> dict[str, object]:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    output_dir.mkdir(parents=True, exist_ok=True)
    portrait_path = output_dir / "synthetic_portrait.png"
    wide_path = output_dir / "synthetic_wide.png"
    portrait = _synthetic_art(
        portrait_path,
        accent=QColor(142, 79, 45),
        portrait=True,
    )
    wide = _synthetic_art(
        wide_path,
        accent=QColor(91, 111, 126),
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

    content = _card()
    unavailable = replace(
        content,
        appid=None,
        title="Rediscovery Shelf",
        subtitle="Previous play history is unavailable.",
        metric_label="History",
        metric_value="Unavailable",
        status="BACKLOG PAUSED",
        fields=(),
        state="unavailable",
    )
    cases = (
        (
            "abandonment_portrait_archive",
            _config(),
            "SE",
            content,
            portrait,
            portrait_path,
            55,
            OverlayWidgetGeometry(30, 25, 600, 331),
        ),
        (
            "abandonment_wide_long_archive",
            _config(artwork_shape="wide", artwork_size=170),
            "NW",
            _card(long_title=True),
            wide,
            wide_path,
            0,
            OverlayWidgetGeometry(700, 25, 600, 331),
        ),
        (
            "abandonment_no_art_no_card",
            _config(show_artwork=False, show_background=False),
            "W",
            content,
            QImage(),
            portrait_path,
            0,
            OverlayWidgetGeometry(30, 410, 600, 331),
        ),
        (
            "abandonment_unavailable",
            _config(show_artwork=False),
            "S",
            unavailable,
            QImage(),
            portrait_path,
            0,
            OverlayWidgetGeometry(700, 410, 600, 331),
        ),
        (
            "abandonment_connect",
            _config(artwork_shape="wide"),
            "E",
            None,
            QImage(),
            wide_path,
            0,
            OverlayWidgetGeometry(30, 790, 600, 300),
        ),
    )

    presentations = []
    manifest = []
    try:
        for (
            name,
            config,
            direction,
            card,
            art,
            art_path,
            bucket,
            geometry,
        ) in cases:
            style = AbandonmentIssuesPresentationStyle.project(
                config,
                _shadows(direction),
            )
            model = AbandonmentIssuesPresentationModel(
                config,
                style,
                parent=owner,
            )
            presentation = RetainedAbandonmentIssuesPresentation(
                host=host,
                model=model,
                geometry=geometry,
                fade_opacity=1.0,
            )
            presentation.activate()
            model.set_interaction_enabled(True)
            if card is not None:
                model.on_abandonment_presentation(
                    _prepared(
                        card,
                        artwork=art,
                        artwork_path=art_path,
                        desaturation_bucket=bucket,
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
        device_pixel_ratio = float(window.devicePixelRatio())
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
                    "desaturation_bucket": presentation.model.desaturationBucket,
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
        "device_pixel_ratio": device_pixel_ratio,
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
