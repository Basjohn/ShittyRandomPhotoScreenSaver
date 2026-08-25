"""Render focused retained-Clock visual evidence through a real Quick window."""

from __future__ import annotations

import argparse
from datetime import datetime
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
configure_quick_graphics(reason="qtquick-clock-smoke")

from PySide6.QtCore import QEventLoop, QObject, QSize, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402

from rendering.quick.scene_controller import QuickSceneFactory  # noqa: E402
from rendering.quick.widgets import (  # noqa: E402
    ClockPresentationConfig,
    ClockPresentationModel,
    ClockPresentationStyle,
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
    RetainedClockPresentation,
)


def _shadow_values(direction: str) -> dict[str, object]:
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


def _config(widget_id: str, **overrides: object) -> ClockPresentationConfig:
    values: dict[str, object] = {
        "format": "24h",
        "show_seconds": True,
        "timezone": "UTC+2",
        "show_timezone": True,
        "show_day_of_week": True,
        "show_date": True,
        "show_digital_separator": True,
        "calendar_layout": "shared_line",
        "calendar_font_size": 22,
        "font_family": "Inter",
        "font_size": 48,
        "color": [240, 245, 250, 240],
        "show_background": True,
        "bg_color": [24, 31, 42, 255],
        "bg_opacity": 0.88,
        "border_color": [115, 190, 255, 255],
        "border_opacity": 0.9,
        "display_mode": "digital",
        "show_numerals": True,
        "analog_face_shadow": True,
    }
    values.update(overrides)
    return ClockPresentationConfig.from_mapping(widget_id, values)


def _grab(item: QQuickItem, size: QSize, timeout_ms: int = 5000):
    result = item.grabToImage(size)
    loop = QEventLoop()
    timed_out = {"value": False}

    def _timeout() -> None:
        timed_out["value"] = True
        loop.quit()

    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(_timeout)
    result.ready.connect(loop.quit)
    timer.start(timeout_ms)
    loop.exec()
    timer.stop()
    if timed_out["value"]:
        raise RuntimeError("Clock grabToImage timed out")
    image = result.image()
    if image.isNull():
        raise RuntimeError("Clock grabToImage returned a null image")
    return image


def _save_on_busy_background(image: QImage, path: Path) -> None:
    """Composite authored alpha over a high-contrast checker for eyes-on QA."""
    canvas = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(canvas)
    try:
        tile = max(24, image.width() // 12)
        colors = (QColor(20, 58, 88), QColor(118, 52, 42))
        for y in range(0, image.height(), tile):
            for x in range(0, image.width(), tile):
                painter.fillRect(
                    x,
                    y,
                    tile,
                    tile,
                    colors[((x // tile) + (y // tile)) % 2],
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
    window.resize(1100, 720)
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
        raise RuntimeError("DisplayScene ordinary widget host is unavailable")
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
        create_family_item=factory.create_ordinary_widget_family,
    )

    cases = (
        (
            "clock_digital_card_se",
            _config("clock", display_mode="digital"),
            _shadow_values("SE"),
            OverlayWidgetGeometry(40.0, 40.0, 430.0, 190.0),
        ),
        (
            "clock2_digital_no_card_n",
            _config(
                "clock2",
                display_mode="digital",
                show_background=False,
                show_timezone=False,
                calendar_layout="two_lines",
                font_size=38,
            ),
            _shadow_values("N"),
            OverlayWidgetGeometry(500.0, 40.0, 360.0, 175.0),
        ),
        (
            "clock3_analogue_card_nw",
            _config("clock3", display_mode="analog", font_size=72),
            _shadow_values("NW"),
            OverlayWidgetGeometry(40.0, 245.0, 420.0, 450.0),
        ),
        (
            "clock_analogue_no_face_shadow_e",
            _config(
                "clock",
                display_mode="analog",
                show_background=False,
                analog_face_shadow=False,
                show_seconds=False,
                font_size=64,
            ),
            _shadow_values("E"),
            OverlayWidgetGeometry(500.0, 245.0, 380.0, 420.0),
        ),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    presentations: list[RetainedClockPresentation] = []
    manifest: list[dict[str, object]] = []
    try:
        for name, config, shadows, geometry in cases:
            style = ClockPresentationStyle.project(config, shadows)
            model = ClockPresentationModel(
                config,
                style,
                now_provider=lambda _zone: datetime(2026, 8, 25, 13, 24, 30),
                parent=owner,
            )
            presentation = RetainedClockPresentation(
                host=host,
                model=model,
                geometry=geometry,
                display_bounds=OverlayWidgetGeometry(0.0, 0.0, 1100.0, 720.0),
                display_identity="clock-smoke",
            )
            presentations.append(presentation)

        window.show()
        settle = QEventLoop()
        QTimer.singleShot(750, settle.quit)
        settle.exec()

        for (name, config, shadows, geometry), presentation in zip(
            cases, presentations, strict=True
        ):
            target = QSize(
                int(geometry.width),
                int(geometry.height),
            )
            image = _grab(presentation.item, target)
            path = output_dir / f"{name}.png"
            if not image.save(str(path), "PNG"):
                raise RuntimeError(f"failed to save {path}")
            busy_path = output_dir / f"{name}_busy.png"
            _save_on_busy_background(image, busy_path)
            manifest.append(
                {
                    "name": name,
                    "widget_id": config.widget_id,
                    "mode": config.display_mode,
                    "direction": shadows["direction"],
                    "card": config.show_background,
                    "analog_face_shadow": config.analog_face_shadow,
                    "logical_size": [int(geometry.width), int(geometry.height)],
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
    (output_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    payload = run(args.output_dir.resolve())
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
