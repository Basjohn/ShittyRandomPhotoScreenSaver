"""Render retained Gmail states through a real Quick window."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
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
configure_quick_graphics(reason="qtquick-gmail-smoke")

from PySide6.QtCore import QEventLoop, QObject, QSize, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402

from core.gmail.gmail_client import EmailMetadata  # noqa: E402
from rendering.quick.scene_controller import QuickSceneFactory  # noqa: E402
from rendering.quick.widgets.gmail import (  # noqa: E402
    GmailPresentationConfig,
    GmailPresentationModel,
    GmailPresentationStyle,
    RetainedGmailPresentation,
)
from rendering.quick.widgets.host import (  # noqa: E402
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
)
from widgets.gmail_runtime import GmailRuntimeSnapshot  # noqa: E402


def _config(**overrides) -> GmailPresentationConfig:
    values = {
        "limit": 5,
        "font_family": "Inter",
        "font_size": 18,
        "color": [248, 249, 252, 242],
        "show_sender": True,
        "show_subject": True,
        "show_envelope_icon": True,
        "show_three_dot": True,
        "show_refresh_spiral": True,
        "show_unread_count": True,
        "show_header_border": True,
        "show_timestamp": True,
        "group_threads": True,
        "auto_title_case": True,
        "clean_sender_names": True,
        "max_sender_words": 3,
        "sender_subject_ratio": 34,
        "max_subject_words": 9,
        "desaturate_when_no_unread": True,
        "show_background": True,
        "bg_color": [28, 31, 38, 255],
        "bg_opacity": 0.9,
        "border_color": [235, 238, 244, 255],
        "border_opacity": 0.88,
        "show_separators": True,
        "separator_color": [225, 228, 235, 80],
        "separator_thickness": 1,
        "boundary_separator_color": [255, 190, 90, 210],
        "boundary_separator_thickness": 2,
    }
    values.update(overrides)
    return GmailPresentationConfig.from_mapping(values)


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


def _email(
    identity: str,
    *,
    thread_id: str | None = None,
    sender: str,
    subject: str,
    unread: bool,
    minute: int,
) -> EmailMetadata:
    return EmailMetadata(
        id=identity,
        thread_id=thread_id or f"thread-{identity}",
        sender=sender,
        subject=subject,
        date=datetime(2026, 8, 27, 14, minute, tzinfo=timezone.utc),
        labels=("INBOX", "UNREAD") if unread else ("INBOX",),
        is_unread=unread,
        provider="gmail_api",
    )


def _emails() -> tuple[EmailMetadata, ...]:
    return (
        _email(
            "one",
            thread_id="thread-grouped",
            sender='"Alexandra Verylongsendername" <alexandra@example.com>',
            subject="a deliberately long grouped conversation subject proving retained elision",
            unread=True,
            minute=12,
        ),
        _email(
            "two",
            thread_id="thread-grouped",
            sender="Alexandra Verylongsendername <alexandra@example.com>",
            subject="Re: a deliberately long grouped conversation subject",
            unread=True,
            minute=8,
        ),
        _email(
            "three",
            sender="Build Pipeline <ci@example.com>",
            subject="nightly build completed successfully",
            unread=True,
            minute=5,
        ),
        _email(
            "four",
            sender="Calendar <calendar@example.com>",
            subject="tomorrow's retained architecture review",
            unread=False,
            minute=1,
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
        raise RuntimeError("Gmail grabToImage returned a null image")
    return image


def _find_visual_item(root: QQuickItem, object_name: str) -> QQuickItem | None:
    if root.objectName() == object_name:
        return root
    for child in root.childItems():
        found = _find_visual_item(child, object_name)
        if found is not None:
            return found
    return None


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
                painter.fillRect(x, y, tile, tile, colors[(x // tile + y // tile) % 2])
        painter.drawImage(0, 0, overlay)
    finally:
        painter.end()
    if not canvas.save(str(path), "PNG"):
        raise RuntimeError(f"failed to save {path}")


def run(output_dir: Path) -> dict[str, object]:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    owner = QObject()
    factory = QuickSceneFactory(owner)
    window = QQuickWindow()
    window.resize(1500, 920)
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
            "gmail_grouped_popup_card",
            _config(),
            "SE",
            "ready",
            _emails(),
            3,
            True,
            OverlayWidgetGeometry(35, 35, 690, 255),
        ),
        (
            "gmail_no_unread_no_card",
            _config(show_background=False, group_threads=False),
            "NW",
            "ready",
            tuple(
                replace(email, labels=("INBOX",), is_unread=False)
                for email in _emails()[:3]
            ),
            0,
            False,
            OverlayWidgetGeometry(35, 375, 690, 190),
        ),
        (
            "gmail_auth_card",
            _config(font_size=20),
            "W",
            "auth",
            (),
            0,
            False,
            OverlayWidgetGeometry(785, 35, 620, 110),
        ),
        (
            "gmail_error_no_card",
            _config(show_background=False, show_header_border=False),
            "S",
            "error",
            (),
            0,
            False,
            OverlayWidgetGeometry(785, 210, 620, 110),
        ),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    presentations = []
    manifest = []
    try:
        for name, config, direction, state, emails, unread, popup, geometry in cases:
            style = GmailPresentationStyle.project(config, _shadows(direction))
            model = GmailPresentationModel(config, style, parent=owner)
            presentation = RetainedGmailPresentation(
                host=host, model=model, geometry=geometry
            )
            presentation.activate()
            model.set_interaction_enabled(True)
            model.on_gmail_runtime_snapshot(
                GmailRuntimeSnapshot(
                    revision=1,
                    emails=tuple(emails),
                    unread_count=unread,
                    error=state if state in {"auth", "error"} else None,
                    refreshing=False,
                    source="smoke",
                )
            )
            presentations.append(
                (name, config, direction, state, popup, geometry, presentation)
            )
        window.show()
        settle = QEventLoop()
        QTimer.singleShot(1000, settle.quit)
        settle.exec()
        for (
            name,
            config,
            direction,
            state,
            popup,
            geometry,
            presentation,
        ) in presentations:
            if popup:
                menu_button = _find_visual_item(presentation.item, "gmailMenuButton_0")
                if menu_button is None:
                    raise RuntimeError("Gmail popup anchor is unavailable")
                mapped = menu_button.mapToItem(
                    presentation.item, 0.0, menu_button.height()
                )
                presentation.item.setProperty(
                    "actionPopupX", max(0.0, mapped.x() + menu_button.width() - 190.0)
                )
                presentation.item.setProperty("actionPopupY", mapped.y())
                presentation.item.setProperty("activeActionIdentity", "thread-grouped")
                presentation.item.setProperty("activeActionMessageId", "one")
                presentation.item.setProperty("activeActionUnread", True)
                presentation.item.setProperty("activeActionArchiveSupported", True)
                app.processEvents()
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
                    "state": state,
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
