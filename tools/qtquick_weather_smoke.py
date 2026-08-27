"""Render focused retained-Weather visual evidence through a real Quick window."""

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
configure_quick_graphics(reason="qtquick-weather-smoke")

from PySide6.QtCore import QEventLoop, QObject, QSize, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402

from rendering.quick.scene_controller import QuickSceneFactory  # noqa: E402
from rendering.quick.widgets.host import (  # noqa: E402
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
)
from rendering.quick.widgets.weather import (  # noqa: E402
    RetainedWeatherPresentation,
    WeatherPresentationConfig,
    WeatherPresentationModel,
    WeatherPresentationStyle,
)


class _SyntheticWeatherRuntime:
    def __init__(self) -> None:
        self.consumer = None
        self.location = ""
        self.running = False

    def attach_consumer(self, consumer) -> None:
        self.consumer = consumer

    def detach_consumer(self, consumer=None) -> None:
        if consumer is None or consumer is self.consumer:
            self.consumer = None

    def set_thread_manager(self, _thread_manager) -> None:
        return

    def set_location(self, location: str) -> None:
        self.location = str(location or "").strip()
        if not self.location:
            self.running = False

    def has_cached_data(self) -> bool:
        return False

    def start(self, *, immediate_refresh_on_miss: bool = False) -> bool:
        del immediate_refresh_on_miss
        self.running = bool(self.location)
        return self.running

    def stop(self) -> None:
        self.running = False

    def is_running(self) -> bool:
        return self.running

    def fetch_weather(self) -> None:
        return

    def publish(self, data: dict[str, object]) -> None:
        if self.consumer is not None:
            self.consumer.on_weather_state(data, from_cache=False)

    def fail(self, error: str) -> None:
        if self.consumer is not None:
            self.consumer.on_weather_error(error)


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


def _config(**overrides: object) -> WeatherPresentationConfig:
    values: dict[str, object] = {
        "location": "Cape Town",
        "font_family": "Inter",
        "font_size": 25,
        "color": [245, 248, 252, 240],
        "show_background": True,
        "bg_color": [24, 31, 42, 255],
        "bg_opacity": 0.88,
        "border_color": [115, 190, 255, 255],
        "border_opacity": 0.9,
        "show_forecast": True,
        "show_condition_icon": True,
        "icon_alignment": "RIGHT",
        "icon_size": 96,
        "show_details_row": True,
        "detail_icon_size": 24,
    }
    values.update(overrides)
    return WeatherPresentationConfig.from_mapping(values)


def _sample(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "temperature": 22.4,
        "condition": "partly cloudy",
        "location": "Cape Town",
        "weather_code": 2,
        "is_day": 1,
        "precipitation_probability": 17,
        "humidity": 68,
        "windspeed": 12.6,
        "forecast": "Tomorrow: 19°C, light rain",
    }
    values.update(overrides)
    return values


def _grab(item: QQuickItem, size: QSize, timeout_ms: int = 5000) -> QImage:
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
        raise RuntimeError("Weather grabToImage timed out")
    image = result.image()
    if image.isNull():
        raise RuntimeError("Weather grabToImage returned a null image")
    return image


def _save_on_busy_background(image: QImage, path: Path) -> None:
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
    window.resize(1180, 780)
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
            "weather_ready_card_right_se",
            _config(),
            _shadow_values("SE"),
            _sample(),
            "ready",
            OverlayWidgetGeometry(30.0, 30.0, 480.0, 290.0),
        ),
        (
            "weather_ready_no_card_left_nw",
            _config(
                location="Oslo",
                show_background=False,
                icon_alignment="LEFT",
                icon_size=82,
                font_size=22,
            ),
            _shadow_values("NW"),
            _sample(
                location="Oslo",
                temperature=-3.0,
                condition="snow",
                weather_code=71,
                is_day=0,
                forecast="Tomorrow: -5°C, snow showers",
            ),
            "ready",
            OverlayWidgetGeometry(560.0, 30.0, 440.0, 275.0),
        ),
        (
            "weather_loading_card_e",
            _config(location="Tokyo", show_forecast=False),
            _shadow_values("E"),
            None,
            "loading",
            OverlayWidgetGeometry(30.0, 360.0, 380.0, 180.0),
        ),
        (
            "weather_error_no_card_w",
            _config(location="Reykjavik", show_background=False),
            _shadow_values("W"),
            "Network unavailable",
            "error",
            OverlayWidgetGeometry(440.0, 360.0, 380.0, 180.0),
        ),
        (
            "weather_missing_location_card_s",
            _config(location=""),
            _shadow_values("S"),
            None,
            "missing",
            OverlayWidgetGeometry(850.0, 360.0, 300.0, 180.0),
        ),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    presentations: list[RetainedWeatherPresentation] = []
    manifest: list[dict[str, object]] = []
    try:
        for name, config, shadows, payload, state, geometry in cases:
            runtime = _SyntheticWeatherRuntime()
            style = WeatherPresentationStyle.project(config, shadows)
            model = WeatherPresentationModel(config, style, runtime, parent=owner)
            presentation = RetainedWeatherPresentation(
                host=host,
                model=model,
                geometry=geometry,
            )
            presentation.activate(object())
            if state == "ready" and isinstance(payload, dict):
                runtime.publish(payload)
            elif state == "error" and isinstance(payload, str):
                runtime.fail(payload)
            presentations.append(presentation)

        window.show()
        settle = QEventLoop()
        QTimer.singleShot(900, settle.quit)
        settle.exec()

        for case, presentation in zip(cases, presentations, strict=True):
            name, config, shadows, _payload, state, geometry = case
            image = _grab(
                presentation.item,
                QSize(int(geometry.width), int(geometry.height)),
            )
            path = output_dir / f"{name}.png"
            if not image.save(str(path), "PNG"):
                raise RuntimeError(f"failed to save {path}")
            busy_path = output_dir / f"{name}_busy.png"
            _save_on_busy_background(image, busy_path)
            manifest.append(
                {
                    "name": name,
                    "state": state,
                    "direction": shadows["direction"],
                    "card": config.show_background,
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
