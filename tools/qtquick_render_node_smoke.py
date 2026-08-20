"""Production-shaped standalone threaded Qt Quick runtime lifecycle smoke."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any

from rendering.quick.bootstrap import (
    configure_quick_environment,
    configure_quick_graphics,
)


# Fix process-owned Quick environment before importing Qt.
configure_quick_environment()

from PySide6.QtCore import QObject, QSize, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QScreen  # noqa: E402
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface  # noqa: E402

from rendering.quick.render import RenderNodeSnapshot, RenderNodeTelemetry  # noqa: E402
from rendering.quick.runtime import QuickDisplayRuntime  # noqa: E402
from rendering.quick.scene_controller import (  # noqa: E402
    QuickSceneController,
    QuickSceneFactory,
)
from rendering.quick.state import QuickWindowPolicy  # noqa: E402
from rendering.quick.window import QuickDisplayWindow  # noqa: E402


@dataclass
class _WindowProbe:
    index: int
    generation: int
    screen_name: str
    runtime: QuickDisplayRuntime
    window: QuickDisplayWindow
    scene: QuickSceneController
    telemetry: RenderNodeTelemetry
    qml_object_name: str
    qml_runtime_role: str
    qml_screen_index: int
    qml_runtime_generation: int | None
    target_geometry: tuple[int, int, int, int]
    qml_root_identity: int
    initial_capture: dict[str, Any] | None = None
    resized_capture: dict[str, Any] | None = None
    initial_scene_state: dict[str, object] | None = None
    hide_show_cycles: list[dict[str, Any]] = field(default_factory=list)


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
    parser.add_argument("--generations", type=int, default=1)
    parser.add_argument("--hide-show-cycles", type=int, default=0)
    parser.add_argument("--size", type=_parse_size, default=QSize(480, 270))
    parser.add_argument("--phase-delay-ms", type=int, default=350)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.windows < 1:
        parser.error("--windows must be positive")
    if not 1 <= args.generations <= 3:
        parser.error("--generations must be between 1 and 3")
    if not 0 <= args.hide_show_cycles <= 3:
        parser.error("--hide-show-cycles must be between 0 and 3")
    if not 100 <= args.phase_delay_ms <= 5000:
        parser.error("--phase-delay-ms must be between 100 and 5000")
    return args


def _capture_from_snapshot(snapshot: RenderNodeSnapshot) -> dict[str, Any]:
    return {
        "size": list(snapshot.render_target_size),
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
        self._reports: list[dict[str, Any]] = []
        self._errors: list[str] = []
        self._scene_factory = QuickSceneFactory(self)
        self._generation = 0
        self._completed_generations = 0
        self._retired_runtime_ids: set[int] = set()
        self._cycle_token = 0
        self._hide_show_cycle = 0
        self._active_hide_records: dict[int, dict[str, Any]] = {}
        self._visibility_deadline = 0.0

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
        self._window_count = window_count
        self._start_generation()

    def _start_generation(self) -> None:
        self._cycle_token += 1
        token = self._cycle_token
        self._probes = []
        self._initial_snapshots = []
        self._retired_runtime_ids = set()
        self._hide_show_cycle = 0
        self._active_hide_records = {}
        current_screens = list(QGuiApplication.screens())
        if len(current_screens) < self._window_count:
            self._errors.append(
                f"generation{self._generation} has only {len(current_screens)} "
                f"screens; expected {self._window_count}"
            )
            self._finish_report()
            return
        self._current_screens = current_screens[: self._window_count]
        try:
            for index, screen in enumerate(self._current_screens):
                self._probes.append(
                    self._create_window(index, screen, generation=self._generation)
                )
        except Exception as exc:
            self._errors.append(
                f"generation{self._generation} construction failed: "
                f"{type(exc).__name__}: {exc}"
            )
            self._finish_report()
            return

        # Construct the complete display generation before any native window
        # is shown, matching production multi-display ownership ordering.
        for probe in self._probes:
            if probe.window.screen() is not self._current_screens[probe.index]:
                self._errors.append(
                    f"generation{self._generation} screen{probe.index} "
                    "was not bound before show"
                )
            probe.runtime.show_on_screen()
            probe.window.setGeometry(*probe.target_geometry)
            probe.window.update()
        self._visibility_deadline = self._visibility_timeout_deadline()
        QTimer.singleShot(10, lambda token=token: self._capture_initial(token))

    def _create_window(
        self,
        index: int,
        screen: QScreen,
        *,
        generation: int,
    ) -> _WindowProbe:
        telemetry = RenderNodeTelemetry(
            gui_thread_id=threading.get_ident(),
            capture_pixels=True,
        )
        runtime = QuickDisplayRuntime(
            screen_index=index,
            runtime_generation=generation,
            screen=screen,
            scene_factory=self._scene_factory,
            window_policy=QuickWindowPolicy(
                always_on_top=False,
                accepts_focus=index == 0,
                blank_cursor=False,
            ),
            telemetry=telemetry,
            parent=self,
        )
        runtime.retirement_completed.connect(
            lambda retired_generation, runtime=runtime: self._on_runtime_retired(
                runtime,
                retired_generation,
            )
        )
        window = runtime.window
        window.setColor(QColor("#080b14"))

        size: QSize = self._args.size
        geometry = screen.availableGeometry()
        x = geometry.x() + max(0, (geometry.width() - size.width()) // 2)
        y = geometry.y() + max(0, (geometry.height() - size.height()) // 2)
        target_geometry = (x, y, size.width(), size.height())
        window.setGeometry(*target_geometry)

        scene = runtime.scene_controller
        scene.set_background_proof_progress(0.36 + (0.08 * index))
        scene_root = scene.scene_root
        return _WindowProbe(
            index=index,
            generation=generation,
            screen_name=screen.name(),
            runtime=runtime,
            window=window,
            scene=scene,
            telemetry=telemetry,
            qml_object_name=scene_root.objectName(),
            qml_runtime_role=str(scene_root.property("runtimeRole")),
            qml_screen_index=int(scene_root.property("screenIndex")),
            qml_runtime_generation=scene_root.property("runtimeGeneration"),
            target_geometry=target_geometry,
            qml_root_identity=id(scene_root),
        )

    def _capture_initial(self, token: int) -> None:
        if token != self._cycle_token:
            return
        initial_ready = all(
            probe.runtime.scene_readiness.ready_for_reveal
            and probe.telemetry.snapshot().render_count >= 1
            and probe.telemetry.snapshot().pixel_sample_count >= 1
            for probe in self._probes
        )
        if not initial_ready and time.monotonic() < self._visibility_deadline:
            QTimer.singleShot(10, lambda token=token: self._capture_initial(token))
            return
        if not initial_ready:
            self._errors.append(
                f"generation{self._generation} initial reveal readiness timed out"
            )
        try:
            for probe in self._probes:
                snapshot = probe.telemetry.snapshot()
                probe.initial_capture = _capture_from_snapshot(snapshot)
                probe.initial_scene_state = probe.scene.describe_scene_state()
                self._initial_snapshots.append(snapshot)
                probe.scene.set_background_proof_progress(0.68)
                probe.window.resize(
                    probe.window.width() + 80,
                    probe.window.height() + 45,
                )
                probe.window.update()
        except Exception as exc:
            self._errors.append(f"initial capture failed: {type(exc).__name__}: {exc}")
        self._visibility_deadline = self._visibility_timeout_deadline()
        QTimer.singleShot(10, lambda token=token: self._capture_resized(token))

    def _capture_resized(self, token: int) -> None:
        if token != self._cycle_token:
            return
        resized_ready = len(self._initial_snapshots) == len(self._probes) and all(
            (
                probe.telemetry.snapshot().render_target_size
                != self._initial_snapshots[position].render_target_size
                and probe.telemetry.snapshot().pixel_sample_count
                > self._initial_snapshots[position].pixel_sample_count
                and probe.runtime.scene_readiness.ready_for_reveal
            )
            for position, probe in enumerate(self._probes)
        )
        if not resized_ready and time.monotonic() < self._visibility_deadline:
            QTimer.singleShot(10, lambda token=token: self._capture_resized(token))
            return
        if not resized_ready:
            self._errors.append(
                f"generation{self._generation} resized presentation timed out"
            )
        try:
            for probe in self._probes:
                probe.resized_capture = _capture_from_snapshot(
                    probe.telemetry.snapshot()
                )
        except Exception as exc:
            self._errors.append(f"resized capture failed: {type(exc).__name__}: {exc}")
        if self._args.hide_show_cycles > 0 and not self._errors:
            self._begin_hide_show_cycle(token)
            return
        self._retire_generation(token)

    def _begin_hide_show_cycle(self, token: int) -> None:
        if token != self._cycle_token:
            return
        self._active_hide_records = {}
        try:
            for probe in self._probes:
                probe.runtime.frame_pacer.set_visualizer_active(True)
                before = probe.telemetry.snapshot()
                geometry = probe.window.geometry()
                self._active_hide_records[id(probe)] = {
                    "cycle": self._hide_show_cycle,
                    "before": _snapshot_dict(before),
                    "resume_geometry": list(geometry.getRect()),
                }
                probe.runtime.hide()
        except Exception as exc:
            self._errors.append(
                f"hide/show cycle {self._hide_show_cycle} hide failed: "
                f"{type(exc).__name__}: {exc}"
            )
            self._retire_generation(token)
            return
        self._visibility_deadline = self._visibility_timeout_deadline()
        QTimer.singleShot(10, lambda token=token: self._poll_hidden(token))

    def _poll_hidden(self, token: int) -> None:
        if token != self._cycle_token:
            return
        hidden_ready = True
        for probe in self._probes:
            record = self._active_hide_records[id(probe)]
            before = record["before"]
            snapshot = probe.telemetry.snapshot()
            readiness = probe.runtime.scene_readiness
            if (
                probe.window.isVisible()
                or probe.runtime.phase.value != "paused"
                or not readiness.scene_graph_invalidated
                or snapshot.invalidation_count <= before["invalidation_count"]
                or snapshot.release_count <= before["release_count"]
            ):
                hidden_ready = False
                break

        if not hidden_ready:
            if time.monotonic() < self._visibility_deadline:
                QTimer.singleShot(10, lambda token=token: self._poll_hidden(token))
                return
            self._errors.append(
                f"generation{self._generation} hide/show cycle "
                f"{self._hide_show_cycle} did not reach hidden invalidation"
            )
            self._retire_generation(token)
            return

        try:
            for probe in self._probes:
                record = self._active_hide_records[id(probe)]
                record["hidden"] = _snapshot_dict(probe.telemetry.snapshot())
                record["hidden_runtime_state"] = (
                    probe.runtime.describe_runtime_state()
                )
                record["qml_root_preserved_while_hidden"] = (
                    id(probe.scene.scene_root) == probe.qml_root_identity
                )
                probe.runtime.show_on_screen()
                probe.window.setGeometry(*record["resume_geometry"])
                probe.window.update()
        except Exception as exc:
            self._errors.append(
                f"hide/show cycle {self._hide_show_cycle} show failed: "
                f"{type(exc).__name__}: {exc}"
            )
            self._retire_generation(token)
            return
        self._visibility_deadline = self._visibility_timeout_deadline()
        QTimer.singleShot(10, lambda token=token: self._poll_resumed(token))

    def _poll_resumed(self, token: int) -> None:
        if token != self._cycle_token:
            return
        resumed_ready = True
        for probe in self._probes:
            record = self._active_hide_records[id(probe)]
            before = record["before"]
            snapshot = probe.telemetry.snapshot()
            if (
                not probe.window.isVisible()
                or probe.runtime.phase.value != "visible"
                or not probe.runtime.scene_readiness.ready_for_reveal
                or snapshot.initialize_count <= before["initialize_count"]
                or snapshot.render_count <= before["render_count"]
                or not probe.runtime.frame_pacer.is_active()
            ):
                resumed_ready = False
                break

        if not resumed_ready:
            if time.monotonic() < self._visibility_deadline:
                QTimer.singleShot(10, lambda token=token: self._poll_resumed(token))
                return
            self._errors.append(
                f"generation{self._generation} hide/show cycle "
                f"{self._hide_show_cycle} did not reach resumed readiness"
            )
            self._retire_generation(token)
            return

        for probe in self._probes:
            record = self._active_hide_records[id(probe)]
            record["resumed"] = _snapshot_dict(probe.telemetry.snapshot())
            record["resumed_capture"] = _capture_from_snapshot(
                probe.telemetry.snapshot()
            )
            record["resumed_runtime_state"] = probe.runtime.describe_runtime_state()
            record["qml_root_preserved_after_resume"] = (
                id(probe.scene.scene_root) == probe.qml_root_identity
            )
            probe.hide_show_cycles.append(record)

        self._hide_show_cycle += 1
        if self._hide_show_cycle < self._args.hide_show_cycles:
            QTimer.singleShot(0, lambda token=token: self._begin_hide_show_cycle(token))
            return
        self._retire_generation(token)

    def _visibility_timeout_deadline(self) -> float:
        timeout_ms = max(1500, self._args.phase_delay_ms * 8)
        return time.monotonic() + (timeout_ms / 1000.0)

    def _retire_generation(self, token: int) -> None:
        if token != self._cycle_token:
            return
        try:
            for probe in self._probes:
                if not probe.runtime.close_runtime():
                    self._errors.append(
                        f"generation{probe.generation} screen{probe.index} "
                        "runtime retirement was not admitted"
                    )
        except Exception as exc:
            self._errors.append(
                f"runtime retirement failed: {type(exc).__name__}: {exc}"
            )
        QTimer.singleShot(
            max(1500, self._args.phase_delay_ms * 8),
            lambda token=token: self._retirement_timeout(token),
        )

    def _on_runtime_retired(
        self,
        runtime: QuickDisplayRuntime,
        retired_generation: int,
    ) -> None:
        if retired_generation != self._generation:
            self._errors.append(
                f"stale runtime retirement generation={retired_generation} "
                f"current={self._generation}"
            )
            return
        self._retired_runtime_ids.add(id(runtime))
        if len(self._retired_runtime_ids) == len(self._probes):
            token = self._cycle_token
            QTimer.singleShot(0, lambda token=token: self._finish_generation(token))

    def _retirement_timeout(self, token: int) -> None:
        if token != self._cycle_token:
            return
        pending = [
            f"screen{probe.index}:{probe.runtime.phase.value}"
            for probe in self._probes
            if id(probe.runtime) not in self._retired_runtime_ids
        ]
        if pending:
            self._errors.append(
                f"generation{self._generation} retirement timed out: {pending}"
            )
            self._finish_report()

    def _finish_generation(self, token: int) -> None:
        if token != self._cycle_token:
            return
        for position, probe in enumerate(self._probes):
            initial = self._initial_snapshots[position]
            final = probe.telemetry.snapshot()
            initial_capture = probe.initial_capture or {}
            resized_capture = probe.resized_capture or {}
            runtime_state = probe.runtime.describe_runtime_state()
            errors = self._validate_probe(
                probe,
                initial,
                final,
                initial_capture,
                resized_capture,
                runtime_state,
            )
            self._errors.extend(errors)
            self._reports.append(
                {
                    "index": probe.index,
                    "generation": probe.generation,
                    "screen": probe.screen_name,
                    "runtime_type": type(probe.runtime).__name__,
                    "window_type": type(probe.window).__name__,
                    "display_identity": probe.runtime.display_identity.as_dict(),
                    "runtime_state": runtime_state,
                    "window_state": runtime_state.get("window"),
                    "initial_scene_state": probe.initial_scene_state,
                    "final_scene_state": runtime_state.get("scene"),
                    "initial": _snapshot_dict(initial),
                    "final": _snapshot_dict(final),
                    "initial_capture": initial_capture,
                    "resized_capture": resized_capture,
                    "hide_show_cycles": probe.hide_show_cycles,
                    "errors": errors,
                }
            )
            probe.runtime.deleteLater()

        self._completed_generations += 1
        if self._errors or self._completed_generations >= self._args.generations:
            self._finish_report()
            return
        self._generation += 1
        QTimer.singleShot(0, self._start_generation)

    def _finish_report(self) -> None:
        report = {
            "valid": not self._errors,
            "requested_windows": self._args.windows,
            "requested_generations": self._args.generations,
            "requested_hide_show_cycles": self._args.hide_show_cycles,
            "completed_generations": self._completed_generations,
            "physical_screens": len(QGuiApplication.screens()),
            "created_windows": len(self._reports),
            "concurrent_windows": self._window_count,
            "render_loop": os.environ.get("QSG_RENDER_LOOP"),
            "graphics_api": QQuickWindow.graphicsApi().name,
            "qml_url": self._scene_factory.qml_url.toLocalFile(),
            "qml_loaded": self._scene_factory.is_ready,
            "windows": self._reports,
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
        runtime_state: dict[str, Any],
    ) -> list[str]:
        prefix = f"generation{probe.generation}.screen{probe.index}"
        errors: list[str] = []
        if final.error:
            errors.append(f"{prefix} render error: {final.error}")
        if probe.qml_object_name != "displaySceneRoot":
            errors.append(f"{prefix} did not instantiate DisplayScene.qml")
        if probe.qml_runtime_role != "display-scene":
            errors.append(f"{prefix} QML runtime role is incorrect")
        if probe.qml_screen_index != probe.index:
            errors.append(f"{prefix} QML screen identity is incorrect")
        if probe.qml_runtime_generation != probe.generation:
            errors.append(f"{prefix} QML runtime generation is incorrect")
        initial_scene = probe.initial_scene_state or {}
        initial_readiness = initial_scene.get("readiness", {})
        if not isinstance(initial_readiness, dict) or not initial_readiness.get(
            "ready_for_reveal"
        ):
            errors.append(f"{prefix} scene never reached explicit reveal readiness")
        final_scene = runtime_state.get("scene", {})
        if not isinstance(final_scene, dict):
            final_scene = {}
        final_readiness = final_scene.get("readiness", {})
        if not isinstance(final_readiness, dict):
            errors.append(f"{prefix} final scene readiness is unavailable")
        else:
            if not final_readiness.get("scene_graph_invalidated"):
                errors.append(f"{prefix} scene controller missed invalidation")
            if not final_readiness.get("qml_objects_retired"):
                errors.append(f"{prefix} scene controller retained QML objects")
        identity = probe.runtime.display_identity
        if identity.screen_index != probe.index:
            errors.append(f"{prefix} display identity index is incorrect")
        if identity.runtime_generation != probe.generation:
            errors.append(f"{prefix} display runtime generation is incorrect")
        if identity.name != probe.screen_name:
            errors.append(f"{prefix} display identity name is incorrect")
        if runtime_state.get("phase") != "retired":
            errors.append(f"{prefix} runtime did not reach retired phase")
        if not runtime_state.get("close_meta_calls_queued"):
            errors.append(f"{prefix} runtime did not use queued window teardown")
        if not runtime_state.get("window_delete_queued"):
            errors.append(f"{prefix} window deletion was not queued")
        if not runtime_state.get("retirement_completed"):
            errors.append(f"{prefix} window destruction was not observed")
        if initial.render_thread_id is None:
            errors.append(f"{prefix} never rendered")
        elif initial.render_thread_id == initial.gui_thread_id:
            errors.append(f"{prefix} render callback ran on the GUI thread")
        expected_resource_cycles = 1 + self._args.hide_show_cycles
        if final.initialize_count != expected_resource_cycles:
            errors.append(
                f"{prefix} GL initialized {final.initialize_count} times; "
                f"expected {expected_resource_cycles}"
            )
        if final.render_count < 2 + self._args.hide_show_cycles:
            errors.append(f"{prefix} rendered only {final.render_count} frames")
        if final.release_count != expected_resource_cycles:
            errors.append(
                f"{prefix} GL released {final.release_count} times; "
                f"expected {expected_resource_cycles}"
            )
        if final.release_thread_id != final.render_thread_id:
            errors.append(f"{prefix} GL release did not run on its render thread")
        if final.invalidation_count < expected_resource_cycles:
            errors.append(
                f"{prefix} scene graph invalidated {final.invalidation_count} times; "
                f"expected at least {expected_resource_cycles}"
            )
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
        if len(probe.hide_show_cycles) != self._args.hide_show_cycles:
            errors.append(
                f"{prefix} completed {len(probe.hide_show_cycles)} hide/show cycles; "
                f"expected {self._args.hide_show_cycles}"
            )
        for cycle_index, cycle in enumerate(probe.hide_show_cycles):
            cycle_prefix = f"{prefix}.hide_show{cycle_index}"
            hidden_runtime = cycle.get("hidden_runtime_state", {})
            hidden_snapshot = cycle.get("hidden", {})
            hidden_window = hidden_runtime.get("window", {})
            hidden_scene = hidden_runtime.get("scene_readiness", {})
            hidden_pacer = hidden_runtime.get("frame_pacer", {})
            resumed_runtime = cycle.get("resumed_runtime_state", {})
            resumed_window = resumed_runtime.get("window", {})
            resumed_scene = resumed_runtime.get("scene_readiness", {})
            resumed_pacer = resumed_runtime.get("frame_pacer", {})
            if hidden_runtime.get("phase") != "paused" or hidden_window.get(
                "visible"
            ):
                errors.append(f"{cycle_prefix} did not become hidden/paused")
            if (
                not hidden_scene.get("scene_graph_invalidated")
                or not hidden_scene.get("qml_root_created")
                or hidden_scene.get("qml_objects_retired")
                or not hidden_scene.get("admission_open")
            ):
                errors.append(
                    f"{cycle_prefix} did not preserve the invalidated QML scene"
                )
            if (
                not hidden_pacer.get("paused")
                or hidden_pacer.get("active")
                or hidden_pacer.get("demands") != ["visualizer"]
            ):
                errors.append(f"{cycle_prefix} did not preserve paused frame demand")
            if not cycle.get("qml_root_preserved_while_hidden"):
                errors.append(f"{cycle_prefix} replaced its QML root while hidden")
            if hidden_snapshot.get("release_thread_id") != hidden_snapshot.get(
                "render_thread_id"
            ):
                errors.append(f"{cycle_prefix} released off its render thread")
            if resumed_runtime.get("phase") != "visible" or not resumed_window.get(
                "visible"
            ):
                errors.append(f"{cycle_prefix} did not become visible again")
            if not resumed_scene.get("ready_for_reveal"):
                errors.append(f"{cycle_prefix} did not regain reveal readiness")
            if (
                resumed_pacer.get("paused")
                or not resumed_pacer.get("active")
                or resumed_pacer.get("demands") != ["visualizer"]
            ):
                errors.append(f"{cycle_prefix} did not resume frame demand")
            if not cycle.get("qml_root_preserved_after_resume"):
                errors.append(f"{cycle_prefix} replaced its QML root on resume")
            if cycle.get("resumed_capture", {}).get("sample_count", 0) < 3:
                errors.append(f"{cycle_prefix} did not render resumed pixels")
        viewport_size = list(final.viewport[2:])
        if viewport_size != list(final.render_target_size):
            errors.append(
                f"{prefix} viewport {viewport_size} does not match render target "
                f"{list(final.render_target_size)}"
            )
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
