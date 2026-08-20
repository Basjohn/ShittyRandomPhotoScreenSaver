"""Production-shaped script smoke for the Phase A2 inline Quick render node."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys
import threading
from typing import Any

from rendering.quick.bootstrap import (
    configure_quick_environment,
    configure_quick_graphics,
)


# Fix process-owned Quick environment before importing Qt.
configure_quick_environment()

from PySide6.QtCore import QMetaObject, QObject, QSize, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QScreen  # noqa: E402
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface  # noqa: E402

from rendering.quick.render import (  # noqa: E402
    BackgroundRenderItem,
    RenderNodeSnapshot,
    RenderNodeTelemetry,
)


@dataclass
class _WindowProbe:
    index: int
    screen_name: str
    window: QQuickWindow
    item: BackgroundRenderItem
    telemetry: RenderNodeTelemetry
    initial_capture: dict[str, Any] | None = None
    resized_capture: dict[str, Any] | None = None


def _parse_size(value: str) -> QSize:
    try:
        width_text, height_text = value.lower().split("x", 1)
        width = int(width_text)
        height = int(height_text)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("size must be WIDTHxHEIGHT") from exc
    if width < 64 or height < 64:
        raise argparse.ArgumentTypeError("size must be at least 64x64")
    return QSize(width, height)


def _arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows", type=int, default=2)
    parser.add_argument("--size", type=_parse_size, default=QSize(480, 270))
    parser.add_argument("--phase-delay-ms", type=int, default=350)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.windows < 1:
        parser.error("--windows must be positive")
    if not 100 <= args.phase_delay_ms <= 5000:
        parser.error("--phase-delay-ms must be between 100 and 5000")
    return args


def _capture_from_snapshot(snapshot: RenderNodeSnapshot) -> dict[str, Any]:
    physical_size = [
        round(snapshot.logical_size[0] * snapshot.device_pixel_ratio),
        round(snapshot.logical_size[1] * snapshot.device_pixel_ratio),
    ]
    return {
        "size": physical_size,
        "viewport": list(snapshot.viewport),
        "device_pixel_ratio": float(snapshot.device_pixel_ratio),
        "sample_count": int(snapshot.pixel_sample_count),
        "colors": sorted(set(snapshot.sample_colors)),
    }


def _snapshot_dict(snapshot: RenderNodeSnapshot) -> dict[str, Any]:
    return asdict(snapshot)


class _SmokeRunner(QObject):
    def __init__(self, app: QGuiApplication, args: argparse.Namespace) -> None:
        super().__init__()
        self._app = app
        self._args = args
        self._probes: list[_WindowProbe] = []
        self._initial_snapshots: list[RenderNodeSnapshot] = []
        self._errors: list[str] = []

    def start(self) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            self._finish_with_error("Qt reported no physical screens")
            return
        window_count = min(self._args.windows, len(screens))
        if window_count < self._args.windows:
            print(
                f"[QUICK-A2] requested={self._args.windows} available={len(screens)} "
                f"using={window_count}",
                flush=True,
            )
        for index, screen in enumerate(screens[:window_count]):
            self._probes.append(self._create_window(index, screen))
        QTimer.singleShot(self._args.phase_delay_ms, self._capture_initial)

    def _create_window(self, index: int, screen: QScreen) -> _WindowProbe:
        window = QQuickWindow()
        window.setObjectName(f"qtquick-a2-screen-{index}")
        window.setColor(QColor("#080b14"))
        window.setPersistentGraphics(False)
        window.setPersistentSceneGraph(False)
        window.setScreen(screen)

        size: QSize = self._args.size
        geometry = screen.availableGeometry()
        x = geometry.x() + max(0, (geometry.width() - size.width()) // 2)
        y = geometry.y() + max(0, (geometry.height() - size.height()) // 2)
        window.setGeometry(x, y, size.width(), size.height())

        telemetry = RenderNodeTelemetry(
            gui_thread_id=threading.get_ident(),
            capture_pixels=True,
        )
        content = window.contentItem()
        item = BackgroundRenderItem(content, telemetry=telemetry)
        item.setSize(content.size())
        content.widthChanged.connect(
            lambda item=item, content=content: item.setWidth(content.width())
        )
        content.heightChanged.connect(
            lambda item=item, content=content: item.setHeight(content.height())
        )
        item.setProofProgress(0.36 + (0.08 * index))

        if window.screen() is not screen:
            self._errors.append(f"screen{index} was not bound before show")
        window.show()
        window.requestActivate()
        window.update()
        return _WindowProbe(
            index=index,
            screen_name=screen.name(),
            window=window,
            item=item,
            telemetry=telemetry,
        )

    def _capture_initial(self) -> None:
        try:
            for probe in self._probes:
                snapshot = probe.telemetry.snapshot()
                probe.initial_capture = _capture_from_snapshot(snapshot)
                self._initial_snapshots.append(snapshot)
                probe.item.setProofProgress(0.68)
                probe.window.resize(
                    probe.window.width() + 80,
                    probe.window.height() + 45,
                )
                probe.window.update()
        except Exception as exc:
            self._errors.append(f"initial capture failed: {type(exc).__name__}: {exc}")
        QTimer.singleShot(self._args.phase_delay_ms, self._capture_resized)

    def _capture_resized(self) -> None:
        try:
            for probe in self._probes:
                probe.resized_capture = _capture_from_snapshot(
                    probe.telemetry.snapshot()
                )
                # A direct Python close() call holds the GIL while Qt waits for
                # the render thread.  The Python QSGRenderNode cleanup then
                # cannot acquire that GIL.  Queued C++ meta-calls let the event
                # loop perform the same legal teardown without that inversion.
                for method in ("hide", "releaseResources", "close"):
                    if not QMetaObject.invokeMethod(
                        probe.window,
                        method,
                        Qt.ConnectionType.QueuedConnection,
                    ):
                        self._errors.append(
                            f"screen{probe.index} could not queue {method}()"
                        )
        except Exception as exc:
            self._errors.append(f"resized capture failed: {type(exc).__name__}: {exc}")
        QTimer.singleShot(self._args.phase_delay_ms, self._finalize)

    def _finalize(self) -> None:
        reports: list[dict[str, Any]] = []
        for position, probe in enumerate(self._probes):
            initial = self._initial_snapshots[position]
            final = probe.telemetry.snapshot()
            initial_capture = probe.initial_capture or {}
            resized_capture = probe.resized_capture or {}
            errors = self._validate_probe(
                probe,
                initial,
                final,
                initial_capture,
                resized_capture,
            )
            self._errors.extend(errors)
            reports.append(
                {
                    "index": probe.index,
                    "screen": probe.screen_name,
                    "initial": _snapshot_dict(initial),
                    "final": _snapshot_dict(final),
                    "initial_capture": initial_capture,
                    "resized_capture": resized_capture,
                    "errors": errors,
                }
            )

        report = {
            "valid": not self._errors,
            "requested_windows": self._args.windows,
            "physical_screens": len(QGuiApplication.screens()),
            "created_windows": len(self._probes),
            "render_loop": os.environ.get("QSG_RENDER_LOOP"),
            "graphics_api": QQuickWindow.graphicsApi().name,
            "windows": reports,
            "errors": self._errors,
        }
        rendered = json.dumps(report, indent=2, sort_keys=True)
        print(rendered, flush=True)
        if self._args.output is not None:
            self._args.output.parent.mkdir(parents=True, exist_ok=True)
            self._args.output.write_text(rendered + "\n", encoding="utf-8")
        self._app.exit(0 if report["valid"] else 1)

    def _validate_probe(
        self,
        probe: _WindowProbe,
        initial: RenderNodeSnapshot,
        final: RenderNodeSnapshot,
        initial_capture: dict[str, Any],
        resized_capture: dict[str, Any],
    ) -> list[str]:
        prefix = f"screen{probe.index}"
        errors: list[str] = []
        if final.error:
            errors.append(f"{prefix} render error: {final.error}")
        if initial.render_thread_id is None:
            errors.append(f"{prefix} never rendered")
        elif initial.render_thread_id == initial.gui_thread_id:
            errors.append(f"{prefix} render callback ran on the GUI thread")
        if final.initialize_count != 1:
            errors.append(
                f"{prefix} GL initialized {final.initialize_count} times instead of once"
            )
        if final.render_count < 2:
            errors.append(f"{prefix} rendered only {final.render_count} frames")
        if final.release_count != 1:
            errors.append(
                f"{prefix} GL released {final.release_count} times instead of once"
            )
        if final.release_thread_id != final.render_thread_id:
            errors.append(f"{prefix} GL release did not run on its render thread")
        if final.invalidation_count < 1:
            errors.append(f"{prefix} scene graph was not invalidated")
        if final.invalidation_thread_id != final.render_thread_id:
            errors.append(f"{prefix} invalidation did not run on its render thread")
        if not final.gl_version:
            errors.append(f"{prefix} did not report a live GL context/version")
        if initial.logical_size == final.logical_size:
            errors.append(f"{prefix} item geometry did not follow window resize")
        if initial.device_pixel_ratio <= 0.0 or final.device_pixel_ratio <= 0.0:
            errors.append(f"{prefix} reported an invalid DPR")
        if initial_capture.get("sample_count", 0) < 1:
            errors.append(f"{prefix} initial render-thread pixel sample was missing")
        if resized_capture.get("sample_count", 0) < 2:
            errors.append(f"{prefix} resized render-thread pixel sample was missing")
        if len(initial_capture.get("colors", ())) < 2:
            errors.append(f"{prefix} initial capture did not contain deterministic bands")
        if len(resized_capture.get("colors", ())) < 2:
            errors.append(f"{prefix} resized capture did not contain deterministic bands")
        if initial_capture.get("size") == resized_capture.get("size"):
            errors.append(f"{prefix} physical capture size did not change after resize")
        viewport_size = list(final.viewport[2:])
        capture_size = resized_capture.get("size", [0, 0])
        if any(
            viewport_extent < capture_extent
            for viewport_extent, capture_extent in zip(viewport_size, capture_size)
        ):
            errors.append(
                f"{prefix} viewport {viewport_size} did not contain item pixels "
                f"{capture_size}"
            )
        return errors

    def _finish_with_error(self, message: str) -> None:
        print(json.dumps({"valid": False, "errors": [message]}), flush=True)
        self._app.exit(1)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(sys.argv[1:] if argv is None else argv)
    bootstrap = configure_quick_graphics(reason="a2-render-node-smoke")
    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("SRPSSQuickRenderNodeSmoke")
    app.setQuitOnLastWindowClosed(False)

    if QQuickWindow.graphicsApi() != QSGRendererInterface.GraphicsApi.OpenGL:
        print(
            json.dumps(
                {
                    "valid": False,
                    "errors": [
                        f"Quick graphics API is {QQuickWindow.graphicsApi().name}, "
                        f"expected {bootstrap.graphics_api}"
                    ],
                }
            ),
            flush=True,
        )
        return 1

    runner = _SmokeRunner(app, args)
    QTimer.singleShot(0, runner.start)
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
