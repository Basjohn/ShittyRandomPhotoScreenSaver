"""Render deterministic Friend Pulse and System Stats retained-Quick cards.

The smoke uses the production scene, ordinary host, models, QML, theme
projection, and uniform-resize path.  Its inert services perform no source,
credential, cache, network, timer, or system-sampler work.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rendering.quick.bootstrap import (  # noqa: E402
    configure_quick_environment,
    configure_quick_graphics,
)


configure_quick_environment()
configure_quick_graphics(reason="qtquick-friend-system-stats-smoke")

from PySide6.QtCore import (  # noqa: E402
    QEventLoop,
    QObject,
    QSize,
    Qt,
    QTimer,
    qInstallMessageHandler,
)
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QFont,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
)
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402

from core.settings.default_contract import require_canonical_default  # noqa: E402
from core.steam.friend_pulse import (  # noqa: E402
    FriendPulseEntry,
    FriendPulseSnapshot,
    project_friend_pulse,
)
from core.steam.models import SteamResultStatus  # noqa: E402
from core.system_stats.source import CpuRamSample  # noqa: E402
from rendering.quick.scene_controller import QuickSceneFactory  # noqa: E402
from rendering.quick.widgets.friend_pulse import (  # noqa: E402
    FriendPulsePresentationConfig,
    FriendPulsePresentationModel,
    FriendPulsePresentationStyle,
    RetainedFriendPulsePresentation,
)
from rendering.quick.widgets.host import (  # noqa: E402
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
)
from rendering.quick.widgets.system_stats import (  # noqa: E402
    RetainedSystemStatsPresentation,
    SystemStatsPresentationConfig,
    SystemStatsPresentationModel,
    SystemStatsPresentationStyle,
)


class _InertService:
    """Activation-compatible service with deliberately zero source ownership."""

    def configure(self, _config: Any) -> None:
        return None

    def set_thread_manager(self, _manager: Any) -> None:
        return None

    def attach_consumer(self, consumer: Any) -> None:
        self.consumer = consumer

    def detach_consumer(self, consumer: Any) -> None:
        if getattr(self, "consumer", None) is consumer:
            self.consumer = None

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        return None

    def refresh(self) -> bool:
        return False


def _settle(milliseconds: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def _grab(item: QQuickItem) -> QImage:
    size = QSize(max(1, round(item.width())), max(1, round(item.height())))
    result = item.grabToImage(size)
    loop = QEventLoop()
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    result.ready.connect(loop.quit)
    timeout.start(5000)
    loop.exec()
    timeout.stop()
    image = result.image()
    if image.isNull():
        raise RuntimeError("retained card capture returned no pixels")
    return image


def _save_on_busy_background(image: QImage, path: Path) -> None:
    canvas = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(canvas)
    try:
        tile = max(16, image.width() // 12)
        colors = (QColor(14, 48, 72), QColor(91, 42, 58))
        for y in range(0, image.height(), tile):
            for x in range(0, image.width(), tile):
                painter.fillRect(
                    x,
                    y,
                    tile,
                    tile,
                    colors[(x // tile + y // tile) % 2],
                )
        painter.drawImage(0, 0, image)
    finally:
        painter.end()
    if not canvas.save(str(path), "PNG"):
        raise RuntimeError(f"could not save {path}")


def _avatar(path: Path, start: QColor, end: QColor, initial: str) -> None:
    image = QImage(96, 96, QImage.Format.Format_ARGB32_Premultiplied)
    gradient = QLinearGradient(0.0, 0.0, 96.0, 96.0)
    gradient.setColorAt(0.0, start)
    gradient.setColorAt(1.0, end)
    painter = QPainter(image)
    try:
        painter.fillRect(image.rect(), gradient)
        painter.setPen(QColor(255, 255, 255, 235))
        font = QFont("Arial", 34)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, initial)
    finally:
        painter.end()
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"could not save {path}")


def _capture_case(
    *,
    name: str,
    presentation: Any,
    output_dir: Path,
) -> dict[str, object]:
    image = _grab(presentation.item)
    image_path = output_dir / f"{name}.png"
    busy_path = output_dir / f"{name}_busy.png"
    if not image.save(str(image_path), "PNG"):
        raise RuntimeError(f"could not save {image_path}")
    _save_on_busy_background(image, busy_path)
    return {
        "name": name,
        "size": [image.width(), image.height()],
        "path": str(image_path.resolve()),
        "busy_background_path": str(busy_path.resolve()),
    }


def run(output_dir: Path) -> dict[str, object]:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    output_dir.mkdir(parents=True, exist_ok=False)
    avatar_paths = (output_dir / "avatar_ada.png", output_dir / "avatar_lee.png")
    _avatar(avatar_paths[0], QColor("#5bd6ff"), QColor("#3152a4"), "A")
    _avatar(avatar_paths[1], QColor("#c995ff"), QColor("#6c3ca5"), "L")

    messages: list[str] = []
    prior_handler = qInstallMessageHandler(
        lambda _kind, _context, message: messages.append(str(message))
    )
    owner = QObject()
    factory = QuickSceneFactory(owner)
    window = QQuickWindow()
    window.resize(1240, 460)
    context, root = factory.create_display_root(
        owner=owner,
        screen_index=0,
        runtime_generation=501,
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

    shadows = dict(require_canonical_default("widgets.shadows"))
    friend_config = FriendPulsePresentationConfig.from_widgets_mapping({})
    friend_model = FriendPulsePresentationModel(
        friend_config,
        FriendPulsePresentationStyle.project(friend_config, shadows),
        runtime_generation=501,
        parent=owner,
    )
    friend_model.set_runtime_service(_InertService())
    friend = RetainedFriendPulsePresentation(
        host=host,
        model=friend_model,
        geometry=OverlayWidgetGeometry(
            28,
            28,
            friend_config.authored_width,
            friend_config.authored_height,
        ),
    )
    friend.activate(object())
    friend_snapshot = FriendPulseSnapshot(
        status=SteamResultStatus.SUCCESS,
        authoritative=True,
        playing_count=4,
        online_count=11,
        entries=(
            FriendPulseEntry(
                "ada",
                "Ada Lovelace",
                70,
                "Half-Life",
                persona_state=1,
                changed=True,
            ),
            FriendPulseEntry("lee", "Lee", 1245620, "ELDEN RING", persona_state=3),
            FriendPulseEntry("sam", "Sam", 220, "Half-Life 2", persona_state=2),
            FriendPulseEntry("zoe", "Zoë", 753640, "Outer Wilds", persona_state=1),
        ),
    )
    rich = project_friend_pulse(
        friend_snapshot,
        privacy_mode="Rich",
        capacity=3,
        avatar_sources={
            "ada": avatar_paths[0].resolve().as_uri(),
            "lee": avatar_paths[1].resolve().as_uri(),
        },
    )
    friend_model.on_friend_pulse_runtime_snapshot(friend_snapshot, rich)

    six_config = FriendPulsePresentationConfig.from_widgets_mapping(
        {"friend_pulse": {"visible_row_capacity": 6}}
    )
    six_snapshot = FriendPulseSnapshot(
        status=SteamResultStatus.SUCCESS,
        authoritative=True,
        playing_count=6,
        online_count=15,
        entries=(
            *friend_snapshot.entries,
            FriendPulseEntry(
                "grace",
                "Grace Hopper",
                367520,
                "Hollow Knight",
                persona_state=1,
            ),
            FriendPulseEntry(
                "dennis",
                "Dennis Ritchie",
                620,
                "Portal 2",
                persona_state=3,
            ),
        ),
    )
    six_projection = project_friend_pulse(
        six_snapshot,
        privacy_mode="Rich",
        capacity=6,
        avatar_sources={
            "ada": avatar_paths[0].resolve().as_uri(),
            "lee": avatar_paths[1].resolve().as_uri(),
        },
    )

    stats_config = SystemStatsPresentationConfig.from_widgets_mapping({})
    stats_model = SystemStatsPresentationModel(
        stats_config,
        SystemStatsPresentationStyle.project(stats_config, shadows),
        runtime_generation=501,
        parent=owner,
    )
    stats_model.set_runtime_service(_InertService())
    stats = RetainedSystemStatsPresentation(
        host=host,
        model=stats_model,
        geometry=OverlayWidgetGeometry(650, 28, 520, 270),
    )
    stats.activate(object())
    stats_model.on_system_stats_runtime_snapshot(
        SimpleNamespace(
            revision=1,
            sample=CpuRamSample(
                "ok",
                37.6,
                "ok",
                round(10.7 * 1024**3),
                round(31.9 * 1024**3),
            ),
        )
    )

    cases: list[dict[str, object]] = []
    try:
        window.show()
        _settle(900)
        cases.append(
            _capture_case(
                name="friend_pulse_rich",
                presentation=friend,
                output_dir=output_dir,
            )
        )
        cases.append(
            _capture_case(
                name="system_stats_ready",
                presentation=stats,
                output_dir=output_dir,
            )
        )

        friend_model.on_friend_pulse_runtime_snapshot(
            friend_snapshot,
            project_friend_pulse(
                friend_snapshot,
                privacy_mode="Strict",
                capacity=3,
            ),
        )
        _settle(80)
        cases.append(
            _capture_case(
                name="friend_pulse_strict",
                presentation=friend,
                output_dir=output_dir,
            )
        )

        friend_model.on_friend_pulse_runtime_snapshot(friend_snapshot, rich)
        friend.set_geometry(
            OverlayWidgetGeometry(
                28,
                28,
                friend_config.authored_width * 0.4,
                friend_config.authored_height * 0.4,
            )
        )
        stats.set_geometry(OverlayWidgetGeometry(650, 28, 208, 108))
        _settle(120)
        cases.append(
            _capture_case(
                name="friend_pulse_floor_40pct",
                presentation=friend,
                output_dir=output_dir,
            )
        )
        cases.append(
            _capture_case(
                name="system_stats_floor_40pct",
                presentation=stats,
                output_dir=output_dir,
            )
        )

        friend.retire()
        six_model = FriendPulsePresentationModel(
            six_config,
            FriendPulsePresentationStyle.project(six_config, shadows),
            runtime_generation=501,
            parent=owner,
        )
        six_model.set_runtime_service(_InertService())
        six_friend = RetainedFriendPulsePresentation(
            host=host,
            model=six_model,
            geometry=OverlayWidgetGeometry(
                28,
                28,
                six_config.authored_width,
                six_config.authored_height,
            ),
        )
        six_friend.activate(object())
        six_model.on_friend_pulse_runtime_snapshot(six_snapshot, six_projection)
        _settle(120)
        cases.append(
            _capture_case(
                name="friend_pulse_six_grid",
                presentation=six_friend,
                output_dir=output_dir,
            )
        )
        six_friend.retire()

        rows_config = FriendPulsePresentationConfig.from_widgets_mapping(
            {"friend_pulse": {"view_mode": "rows"}}
        )
        rows_model = FriendPulsePresentationModel(
            rows_config,
            FriendPulsePresentationStyle.project(rows_config, shadows),
            runtime_generation=501,
            parent=owner,
        )
        rows_model.set_runtime_service(_InertService())
        rows_friend = RetainedFriendPulsePresentation(
            host=host,
            model=rows_model,
            geometry=OverlayWidgetGeometry(
                28,
                28,
                rows_config.authored_width,
                rows_config.authored_height,
            ),
        )
        rows_friend.activate(object())
        rows_model.on_friend_pulse_runtime_snapshot(friend_snapshot, rich)
        _settle(120)
        cases.append(
            _capture_case(
                name="friend_pulse_activity_rows",
                presentation=rows_friend,
                output_dir=output_dir,
            )
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
        qInstallMessageHandler(prior_handler)

    payload = {
        "graphics_api": "OpenGL",
        "render_loop": "threaded",
        "device_pixel_ratio": window.devicePixelRatio(),
        "cases": cases,
        "qml_messages": messages,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["manifest"] = str(manifest_path.resolve())
    if messages:
        raise RuntimeError(f"Qt emitted messages; inspect {manifest_path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir.resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
