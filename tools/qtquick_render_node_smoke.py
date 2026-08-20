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

from PySide6.QtCore import (  # noqa: E402
    QCoreApplication,
    QEvent,
    QObject,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QGuiApplication,
    QImage,
    QKeyEvent,
    QScreen,
)
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface  # noqa: E402

from rendering.quick.image_boundary import capture_qimage  # noqa: E402
from rendering.quick.image_state import PresentationImage  # noqa: E402
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
    proof_progress_on_construction: float
    presentation_state_replayed: bool
    replayed_from_generation: int | None
    presentation_image: PresentationImage
    replacement_image: PresentationImage
    retired_proof_progress: float | None = None
    initial_capture: dict[str, Any] | None = None
    resized_capture: dict[str, Any] | None = None
    replacement_capture: dict[str, Any] | None = None
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
    parser.add_argument("--exit-via-input", action="store_true")
    parser.add_argument("--topology-recreate", action="store_true")
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
    if args.exit_via_input and args.generations != 1:
        parser.error("--exit-via-input requires exactly one generation")
    if args.topology_recreate and (
        args.windows != 2
        or args.generations != 3
        or args.hide_show_cycles != 0
        or args.exit_via_input
    ):
        parser.error(
            "--topology-recreate requires --windows 2 --generations 3 "
            "without hide/show or input-exit scenarios"
        )
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
        "active_image_identity": snapshot.active_image_identity,
        "image_upload_count": int(snapshot.image_upload_count),
        "image_release_count": int(snapshot.image_release_count),
    }


def _presentation_image(
    *,
    screen_index: int,
    generation: int,
    variant: str,
) -> PresentationImage:
    palettes = {
        "initial": (
            QColor(16, 52, 120),
            QColor(22, 108, 184),
            QColor(28, 168, 192),
            QColor(64, 188, 128),
            QColor(154, 206, 72),
            QColor(230, 220, 54),
        ),
        "replacement": (
            QColor(212, 40, 52),
            QColor(230, 82, 42),
            QColor(236, 132, 36),
            QColor(206, 66, 132),
            QColor(150, 54, 176),
            QColor(92, 60, 188),
        ),
    }
    colors = palettes[variant]
    image = QImage(12, 8, QImage.Format.Format_RGBA8888)
    for x in range(image.width()):
        color = colors[min(len(colors) - 1, x // 2)]
        for y in range(image.height()):
            image.setPixelColor(x, y, color)
    return capture_qimage(
        image,
        identity=(
            f"quick-smoke:g{generation}:screen{screen_index}:variant:{variant}"
        ),
        source_path=f"synthetic://quick-smoke/{variant}",
    )


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
        self._retirement_started = False
        self._exit_request_count = 0
        self._exit_retirement_scheduled = False
        self._exit_sequence: dict[str, Any] | None = None
        self._report_finished = False
        self._pending_runtime_root_ids: set[int] = set()
        self._destroyed_runtime_root_ids: set[int] = set()
        self._runtime_root_destruction_barriers: list[dict[str, Any]] = []
        self._active_runtime_root_barrier: dict[str, Any] | None = None
        self._presentation_state_by_screen_key: dict[str, dict[str, Any]] = {}
        self._topology_generations: list[dict[str, Any]] = []
        self._topology_replacements: list[dict[str, Any]] = []
        self._active_topology_generation: dict[str, Any] | None = None

    def start(self) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            self._finish_with_error("Qt reported no physical screens")
            return
        if self._args.topology_recreate and len(screens) < 2:
            self._finish_with_error(
                "topology recreate requires two physical QScreens"
            )
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
        if self._generation > 0 and self._runtime_root_destruction_barriers:
            previous_barrier = self._runtime_root_destruction_barriers[-1]
            previous_barrier["next_generation_started"] = True
            previous_barrier["next_generation_started_after_crossing"] = bool(
                previous_barrier.get("crossed")
            )
        self._cycle_token += 1
        token = self._cycle_token
        self._probes = []
        self._initial_snapshots = []
        self._retired_runtime_ids = set()
        self._hide_show_cycle = 0
        self._active_hide_records = {}
        self._retirement_started = False
        self._exit_retirement_scheduled = False
        self._pending_runtime_root_ids = set()
        self._destroyed_runtime_root_ids = set()
        self._active_runtime_root_barrier = None
        current_screens = list(QGuiApplication.screens())
        selected_indices = self._selected_screen_indices()
        missing_indices = [
            index for index in selected_indices if index >= len(current_screens)
        ]
        if missing_indices:
            self._errors.append(
                f"generation{self._generation} cannot bind physical screens "
                f"{missing_indices}; available={len(current_screens)}"
            )
            self._finish_report()
            return
        self._current_screen_by_index = {
            index: current_screens[index] for index in selected_indices
        }
        try:
            for position, index in enumerate(selected_indices):
                screen = self._current_screen_by_index[index]
                self._probes.append(
                    self._create_window(
                        index,
                        screen,
                        generation=self._generation,
                        accepts_focus=position == 0,
                    )
                )
        except Exception as exc:
            self._errors.append(
                f"generation{self._generation} construction failed: "
                f"{type(exc).__name__}: {exc}"
            )
            self._finish_report()
            return

        self._record_topology_generation(selected_indices)

        # Construct the complete display generation before any native window
        # is shown, matching production multi-display ownership ordering.
        for probe in self._probes:
            if probe.window.screen() is not self._current_screen_by_index[probe.index]:
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
        accepts_focus: bool,
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
                accepts_focus=accepts_focus,
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
        if self._args.exit_via_input:
            runtime.exit_requested.connect(
                lambda runtime=runtime: self._on_runtime_exit_requested(runtime)
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
        screen_key = runtime.display_identity.screen_key
        saved_state = self._presentation_state_by_screen_key.get(screen_key)
        if saved_state is None:
            proof_progress = 0.36 + (0.08 * index)
            replayed_from_generation = None
        else:
            proof_progress = float(saved_state["proof_progress"])
            replayed_from_generation = int(saved_state["generation"])
        scene.set_background_proof_progress(proof_progress)
        presentation_image = _presentation_image(
            screen_index=index,
            generation=generation,
            variant="initial",
        )
        replacement_image = _presentation_image(
            screen_index=index,
            generation=generation,
            variant="replacement",
        )
        runtime.set_presentation_image(presentation_image)
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
            proof_progress_on_construction=proof_progress,
            presentation_state_replayed=saved_state is not None,
            replayed_from_generation=replayed_from_generation,
            presentation_image=presentation_image,
            replacement_image=replacement_image,
        )

    def _selected_screen_indices(self) -> list[int]:
        if not self._args.topology_recreate:
            return list(range(self._window_count))
        topology_plan = ([0, 1], [1], [0, 1])
        return list(topology_plan[self._generation])

    def _record_topology_generation(self, selected_indices: list[int]) -> None:
        if not self._args.topology_recreate:
            return
        generation_record = {
            "generation": self._generation,
            "selected_screen_indices": list(selected_indices),
            "construction_after_completed_generations": self._completed_generations,
            "construction_after_root_barriers": sum(
                1
                for barrier in self._runtime_root_destruction_barriers
                if barrier.get("crossed")
            ),
            "screens": [
                {
                    "screen_index": probe.index,
                    "screen_key": probe.runtime.display_identity.screen_key,
                    "display_identity": probe.runtime.display_identity.as_dict(),
                    "window_object_name": probe.window.objectName(),
                    "qml_runtime_generation": probe.qml_runtime_generation,
                    "proof_progress_on_construction": (
                        probe.proof_progress_on_construction
                    ),
                    "presentation_state_replayed": (
                        probe.presentation_state_replayed
                    ),
                    "replayed_from_generation": probe.replayed_from_generation,
                    "retired_proof_progress": None,
                }
                for probe in self._probes
            ],
            "retirement_complete": False,
            "runtime_root_barrier_crossed": False,
        }
        if self._topology_generations:
            previous = self._topology_generations[-1]
            old_keys = {
                screen["screen_key"] for screen in previous["screens"]
            }
            new_keys = {
                screen["screen_key"] for screen in generation_record["screens"]
            }
            self._topology_replacements.append(
                {
                    "from_generation": previous["generation"],
                    "to_generation": self._generation,
                    "old_screen_keys": sorted(old_keys),
                    "new_screen_keys": sorted(new_keys),
                    "removed_screen_keys": sorted(old_keys - new_keys),
                    "added_screen_keys": sorted(new_keys - old_keys),
                    "old_generation_retired": previous["retirement_complete"],
                    "old_runtime_root_barrier_crossed": previous[
                        "runtime_root_barrier_crossed"
                    ],
                    "replayed_screen_keys": sorted(
                        screen["screen_key"]
                        for screen in generation_record["screens"]
                        if screen["presentation_state_replayed"]
                    ),
                }
            )
        self._active_topology_generation = generation_record
        self._topology_generations.append(generation_record)

    def _capture_initial(self, token: int) -> None:
        if token != self._cycle_token:
            return
        initial_ready = all(
            probe.runtime.scene_readiness.ready_for_reveal
            and probe.telemetry.snapshot().render_count >= 1
            and probe.telemetry.snapshot().pixel_sample_count >= 1
            and probe.telemetry.snapshot().image_upload_count == 1
            and probe.telemetry.snapshot().active_image_identity
            == probe.presentation_image.identity
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
                # Re-admit the same immutable identity and force further frames;
                # the render owner must not upload it again.
                probe.runtime.set_presentation_image(probe.presentation_image)
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
                and probe.telemetry.snapshot().image_upload_count
                == self._initial_snapshots[position].image_upload_count
                and probe.telemetry.snapshot().active_image_identity
                == probe.presentation_image.identity
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
                probe.runtime.set_presentation_image(probe.replacement_image)
                probe.window.update()
        except Exception as exc:
            self._errors.append(f"resized capture failed: {type(exc).__name__}: {exc}")
        self._visibility_deadline = self._visibility_timeout_deadline()
        QTimer.singleShot(10, lambda token=token: self._capture_replacement(token))

    def _capture_replacement(self, token: int) -> None:
        if token != self._cycle_token:
            return
        replacement_ready = all(
            probe.resized_capture is not None
            and probe.telemetry.snapshot().image_upload_count
            == int(probe.resized_capture["image_upload_count"]) + 1
            and probe.telemetry.snapshot().active_image_identity
            == probe.replacement_image.identity
            and probe.telemetry.snapshot().pixel_sample_count
            > int(probe.resized_capture["sample_count"])
            and probe.runtime.scene_readiness.ready_for_reveal
            for probe in self._probes
        )
        if not replacement_ready and time.monotonic() < self._visibility_deadline:
            QTimer.singleShot(
                10,
                lambda token=token: self._capture_replacement(token),
            )
            return
        if not replacement_ready:
            self._errors.append(
                f"generation{self._generation} replacement image timed out"
            )
        try:
            for probe in self._probes:
                probe.replacement_capture = _capture_from_snapshot(
                    probe.telemetry.snapshot()
                )
        except Exception as exc:
            self._errors.append(
                f"replacement capture failed: {type(exc).__name__}: {exc}"
            )
        if self._args.topology_recreate and not self._errors:
            self._advance_topology_presentation_state()
        if self._args.hide_show_cycles > 0 and not self._errors:
            self._begin_hide_show_cycle(token)
            return
        self._finish_presentation_sequence(token)

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
                or snapshot.image_release_count <= before["image_release_count"]
                or snapshot.active_image_identity is not None
                or snapshot.pending_image_release_count != 0
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
                or snapshot.image_upload_count <= before["image_upload_count"]
                or snapshot.active_image_identity
                != probe.replacement_image.identity
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
        self._finish_presentation_sequence(token)

    def _finish_presentation_sequence(self, token: int) -> None:
        if token != self._cycle_token:
            return
        if self._args.exit_via_input:
            self._request_exit_via_input(token)
            return
        self._retire_generation(token)

    def _request_exit_via_input(self, token: int) -> None:
        if token != self._cycle_token:
            return
        if not self._probes:
            self._errors.append("input exit requested without an active runtime")
            self._retire_generation(token)
            return

        source = self._probes[0]
        event = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
        try:
            QCoreApplication.sendEvent(source.window, event)
        except Exception as exc:
            self._errors.append(
                f"input exit dispatch failed: {type(exc).__name__}: {exc}"
            )
            QTimer.singleShot(0, lambda token=token: self._retire_generation(token))
            return

        if self._exit_sequence is not None:
            self._exit_sequence["source_event_accepted"] = event.isAccepted()
        if self._exit_request_count != 1:
            self._errors.append(
                f"input exit emitted {self._exit_request_count} requests instead of one"
            )
            if not self._exit_retirement_scheduled:
                QTimer.singleShot(0, lambda token=token: self._retire_generation(token))

    def _on_runtime_exit_requested(self, runtime: QuickDisplayRuntime) -> None:
        self._exit_request_count += 1
        if all(probe.runtime is not runtime for probe in self._probes):
            self._errors.append("exit request came from a runtime outside the active set")
            return
        if runtime.runtime_generation != self._generation:
            self._errors.append(
                f"stale exit request generation={runtime.runtime_generation} "
                f"current={self._generation}"
            )
            return

        if self._exit_sequence is None:
            self._exit_sequence = {
                "source_screen_index": runtime.screen_index,
                "source_runtime_generation": runtime.runtime_generation,
                "source_event_accepted": False,
                "request_count": self._exit_request_count,
                "runtime_state_at_request": runtime.describe_runtime_state(),
                "runtime_phases_at_request": [
                    probe.runtime.phase.value for probe in self._probes
                ],
                "retirement_deferred": True,
            }
        else:
            self._exit_sequence["request_count"] = self._exit_request_count

        if self._exit_retirement_scheduled:
            return
        self._exit_retirement_scheduled = True
        token = self._cycle_token
        # Leave the QQuickWindow keyPressEvent stack before beginning teardown.
        QTimer.singleShot(0, lambda token=token: self._begin_exit_retirement(token))

    def _begin_exit_retirement(self, token: int) -> None:
        if token != self._cycle_token:
            return
        self._retire_generation(token)
        sequence = self._exit_sequence
        if sequence is None or not self._probes:
            return

        target = self._probes[-1]
        post_close_event = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
        try:
            QCoreApplication.sendEvent(target.window, post_close_event)
        except Exception as exc:
            self._errors.append(
                f"post-close input fence dispatch failed: {type(exc).__name__}: {exc}"
            )
            return
        sequence.update(
            {
                "coordinated_runtime_count": len(self._probes),
                "post_close_event_screen_index": target.index,
                "post_close_event_accepted": post_close_event.isAccepted(),
                "request_count_after_post_close_event": self._exit_request_count,
                "runtime_states_after_admission_close": [
                    probe.runtime.describe_runtime_state() for probe in self._probes
                ],
            }
        )
        if self._exit_request_count != 1:
            self._errors.append(
                "closed Quick input admitted a duplicate exit request"
            )

    def _visibility_timeout_deadline(self) -> float:
        timeout_ms = max(1500, self._args.phase_delay_ms * 8)
        return time.monotonic() + (timeout_ms / 1000.0)

    def _advance_topology_presentation_state(self) -> None:
        """Change per-screen model state so replacement must replay, not default."""

        for probe in self._probes:
            progress = round(
                0.61 + (0.07 * self._generation) + (0.03 * probe.index),
                6,
            )
            probe.scene.set_background_proof_progress(progress)

    def _retire_generation(self, token: int) -> None:
        if token != self._cycle_token:
            return
        if self._retirement_started:
            return
        self._retirement_started = True
        if self._args.topology_recreate:
            self._capture_topology_presentation_state()
        for probe in self._probes:
            try:
                if not probe.runtime.close_runtime():
                    self._errors.append(
                        f"generation{probe.generation} screen{probe.index} "
                        "runtime retirement was not admitted"
                    )
            except Exception as exc:
                self._errors.append(
                    f"generation{probe.generation} screen{probe.index} "
                    f"runtime retirement failed: {type(exc).__name__}: {exc}"
                )
        QTimer.singleShot(
            max(1500, self._args.phase_delay_ms * 8),
            lambda token=token: self._retirement_timeout(token),
        )

    def _capture_topology_presentation_state(self) -> None:
        generation_record = self._active_topology_generation
        screens_by_index = (
            {
                int(screen["screen_index"]): screen
                for screen in generation_record["screens"]
            }
            if generation_record is not None
            else {}
        )
        for probe in self._probes:
            try:
                progress = float(probe.scene.background_item.getProofProgress())
            except Exception as exc:
                self._errors.append(
                    f"generation{probe.generation} screen{probe.index} "
                    f"presentation-state capture failed: {type(exc).__name__}: {exc}"
                )
                continue
            probe.retired_proof_progress = progress
            screen_key = probe.runtime.display_identity.screen_key
            self._presentation_state_by_screen_key[screen_key] = {
                "generation": probe.generation,
                "proof_progress": progress,
            }
            screen_record = screens_by_index.get(probe.index)
            if screen_record is not None:
                screen_record["retired_proof_progress"] = progress

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
            replacement_capture = probe.replacement_capture or {}
            runtime_state = probe.runtime.describe_runtime_state()
            errors = self._validate_probe(
                probe,
                initial,
                final,
                initial_capture,
                resized_capture,
                replacement_capture,
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
                    "replacement_capture": replacement_capture,
                    "hide_show_cycles": probe.hide_show_cycles,
                    "proof_progress_on_construction": (
                        probe.proof_progress_on_construction
                    ),
                    "presentation_state_replayed": (
                        probe.presentation_state_replayed
                    ),
                    "replayed_from_generation": probe.replayed_from_generation,
                    "retired_proof_progress": probe.retired_proof_progress,
                    "errors": errors,
                }
            )
        if self._active_topology_generation is not None:
            self._active_topology_generation["retirement_complete"] = all(
                probe.runtime.phase.value == "retired" for probe in self._probes
            )
            self._active_topology_generation["render_resources_released"] = all(
                probe.telemetry.snapshot().release_count
                == 1 + self._args.hide_show_cycles
                for probe in self._probes
            )
        self._pending_runtime_root_ids = {
            id(probe.runtime) for probe in self._probes
        }
        self._destroyed_runtime_root_ids = set()
        barrier = {
            "generation": self._generation,
            "expected_runtime_roots": len(self._pending_runtime_root_ids),
            "destroyed_runtime_roots": 0,
            "crossed": False,
            "next_generation_started": False,
            "next_generation_started_after_crossing": False,
        }
        self._active_runtime_root_barrier = barrier
        self._runtime_root_destruction_barriers.append(barrier)
        for probe in self._probes:
            runtime_root_id = id(probe.runtime)
            probe.runtime.destroyed.connect(
                lambda *_args, runtime_root_id=runtime_root_id, token=token: (
                    self._on_runtime_root_destroyed(runtime_root_id, token)
                )
            )
            probe.runtime.deleteLater()
        QTimer.singleShot(
            max(1500, self._args.phase_delay_ms * 8),
            lambda token=token: self._runtime_root_destruction_timeout(token),
        )

    def _on_runtime_root_destroyed(self, runtime_root_id: int, token: int) -> None:
        if token != self._cycle_token:
            return
        if runtime_root_id not in self._pending_runtime_root_ids:
            self._errors.append(
                f"generation{self._generation} destroyed an untracked runtime root"
            )
            return
        self._destroyed_runtime_root_ids.add(runtime_root_id)
        barrier = self._active_runtime_root_barrier
        if barrier is not None:
            barrier["destroyed_runtime_roots"] = len(
                self._destroyed_runtime_root_ids
            )
        if self._destroyed_runtime_root_ids == self._pending_runtime_root_ids:
            if barrier is not None:
                barrier["crossed"] = True
            if self._active_topology_generation is not None:
                self._active_topology_generation[
                    "runtime_root_barrier_crossed"
                ] = True
            QTimer.singleShot(0, lambda token=token: self._complete_generation(token))

    def _runtime_root_destruction_timeout(self, token: int) -> None:
        if token != self._cycle_token:
            return
        pending = self._pending_runtime_root_ids - self._destroyed_runtime_root_ids
        if not pending:
            return
        self._errors.append(
            f"generation{self._generation} runtime-root destruction timed out: "
            f"{len(pending)} pending"
        )
        self._finish_report()

    def _complete_generation(self, token: int) -> None:
        if token != self._cycle_token:
            return
        barrier = self._active_runtime_root_barrier
        if barrier is None or not barrier.get("crossed"):
            self._errors.append(
                f"generation{self._generation} completed before its runtime-root barrier"
            )
            self._finish_report()
            return

        self._completed_generations += 1
        if self._errors or self._completed_generations >= self._args.generations:
            self._finish_report()
            return
        self._generation += 1
        QTimer.singleShot(0, self._start_generation)

    def _finish_report(self) -> None:
        if self._report_finished:
            return
        self._report_finished = True
        self._errors.extend(self._validate_exit_sequence())
        self._errors.extend(self._validate_runtime_root_barriers())
        self._errors.extend(self._validate_topology_recreate())
        report = {
            "valid": not self._errors,
            "requested_windows": self._args.windows,
            "requested_generations": self._args.generations,
            "requested_hide_show_cycles": self._args.hide_show_cycles,
            "requested_exit_via_input": self._args.exit_via_input,
            "requested_topology_recreate": self._args.topology_recreate,
            "exit_sequence": self._exit_sequence,
            "runtime_root_destruction_barriers": (
                self._runtime_root_destruction_barriers
            ),
            "topology_generations": self._topology_generations,
            "topology_replacements": self._topology_replacements,
            "presentation_state_by_screen_key": (
                self._presentation_state_by_screen_key
            ),
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

    def _validate_topology_recreate(self) -> list[str]:
        if not self._args.topology_recreate:
            if self._topology_generations or self._topology_replacements:
                return ["unexpected topology replacement records were created"]
            return []

        errors: list[str] = []
        expected_indices = ([0, 1], [1], [0, 1])
        if len(self._topology_generations) != len(expected_indices):
            return ["topology recreate did not complete all three generations"]

        retired_progress: dict[tuple[int, str], float] = {}
        window_names: list[str] = []
        for expected_generation, (record, indices) in enumerate(
            zip(self._topology_generations, expected_indices)
        ):
            if record.get("generation") != expected_generation:
                errors.append("topology generation order changed")
            if record.get("selected_screen_indices") != list(indices):
                errors.append(
                    f"generation{expected_generation} selected the wrong QScreens"
                )
            if record.get("construction_after_completed_generations") != (
                expected_generation
            ):
                errors.append(
                    f"generation{expected_generation} constructed before retirement completion"
                )
            if record.get("construction_after_root_barriers") != expected_generation:
                errors.append(
                    f"generation{expected_generation} constructed before root destruction"
                )
            if not record.get("retirement_complete"):
                errors.append(
                    f"generation{expected_generation} did not retire its runtime set"
                )
            if not record.get("render_resources_released"):
                errors.append(
                    f"generation{expected_generation} retained render resources"
                )
            if not record.get("runtime_root_barrier_crossed"):
                errors.append(
                    f"generation{expected_generation} retained runtime roots"
                )
            for screen in record.get("screens", []):
                screen_index = int(screen["screen_index"])
                identity = screen.get("display_identity", {})
                if identity.get("screen_index") != screen_index:
                    errors.append("topology screen identity was renumbered")
                if identity.get("runtime_generation") != expected_generation:
                    errors.append("topology runtime generation identity is stale")
                if screen.get("qml_runtime_generation") != expected_generation:
                    errors.append("topology QML generation identity is stale")
                window_names.append(str(screen.get("window_object_name")))
                retired = screen.get("retired_proof_progress")
                if retired is None:
                    errors.append("topology presentation state was not captured")
                else:
                    retired_progress[
                        (expected_generation, str(screen["screen_key"]))
                    ] = float(retired)
                replayed_from = screen.get("replayed_from_generation")
                if replayed_from is None:
                    if expected_generation != 0:
                        errors.append("replacement scene did not replay presentation state")
                    continue
                source = retired_progress.get(
                    (int(replayed_from), str(screen["screen_key"]))
                )
                applied = float(screen["proof_progress_on_construction"])
                if source is None or abs(source - applied) > 1e-6:
                    errors.append("replacement scene replayed stale presentation state")

        if len(window_names) != len(set(window_names)):
            errors.append("topology replacement reused a Quick window owner")
        if len(self._topology_replacements) != 2:
            errors.append("topology recreate did not record remove and add replacements")
        else:
            remove_event, add_event = self._topology_replacements
            if len(remove_event.get("removed_screen_keys", [])) != 1 or remove_event.get(
                "added_screen_keys"
            ):
                errors.append("topology removal event is incorrect")
            if len(add_event.get("added_screen_keys", [])) != 1 or add_event.get(
                "removed_screen_keys"
            ):
                errors.append("topology addition event is incorrect")
            for event in self._topology_replacements:
                if not event.get("old_generation_retired"):
                    errors.append("topology replacement started before old retirement")
                if not event.get("old_runtime_root_barrier_crossed"):
                    errors.append("topology replacement started before root destruction")
                if sorted(event.get("replayed_screen_keys", [])) != sorted(
                    event.get("new_screen_keys", [])
                ):
                    errors.append("topology replacement did not replay every selected screen")
        return errors

    def _validate_runtime_root_barriers(self) -> list[str]:
        barriers = self._runtime_root_destruction_barriers
        if len(barriers) != self._completed_generations:
            return ["not every completed generation crossed a runtime-root barrier"]

        errors: list[str] = []
        for position, barrier in enumerate(barriers):
            if not barrier.get("crossed"):
                errors.append(
                    f"generation{barrier.get('generation')} runtime-root barrier was not crossed"
                )
            if barrier.get("destroyed_runtime_roots") != barrier.get(
                "expected_runtime_roots"
            ):
                errors.append(
                    f"generation{barrier.get('generation')} retained runtime roots"
                )
            if position < len(barriers) - 1 and not barrier.get(
                "next_generation_started_after_crossing"
            ):
                errors.append(
                    f"generation{barrier.get('generation')} replacement started before destruction"
                )
        return errors

    def _validate_exit_sequence(self) -> list[str]:
        if not self._args.exit_via_input:
            if self._exit_sequence is not None or self._exit_request_count:
                return ["unexpected input exit occurred during lifecycle smoke"]
            return []

        sequence = self._exit_sequence
        if sequence is None:
            return ["Quick runtime input exit was not observed"]

        errors: list[str] = []
        if sequence.get("request_count") != 1 or self._exit_request_count != 1:
            errors.append("Quick runtime input exit was not emitted exactly once")
        if not sequence.get("source_event_accepted"):
            errors.append("Quick window did not accept the exit key event")
        if sequence.get("source_runtime_generation") != self._generation:
            errors.append("Quick runtime exit used the wrong generation")
        runtime_at_request = sequence.get("runtime_state_at_request", {})
        input_at_request = runtime_at_request.get("input", {})
        if runtime_at_request.get("phase") != "visible":
            errors.append("Quick runtime exit was not observed from a visible runtime")
        if not input_at_request.get("admission_open") or not input_at_request.get(
            "exiting"
        ):
            errors.append("Quick input state did not publish the admitted exit")
        if sequence.get("runtime_phases_at_request") != [
            "visible"
        ] * self._window_count:
            errors.append("Quick runtime teardown began reentrantly inside keyPressEvent")
        if not sequence.get("retirement_deferred"):
            errors.append("Quick runtime exit retirement was not deferred")
        if sequence.get("coordinated_runtime_count") != self._window_count:
            errors.append("Quick input exit did not coordinate the complete runtime set")
        if not sequence.get("post_close_event_accepted"):
            errors.append("closed Quick input did not consume a stale exit event")
        if sequence.get("request_count_after_post_close_event") != 1:
            errors.append("closed Quick input emitted a stale exit request")
        states_after_close = sequence.get("runtime_states_after_admission_close", [])
        if len(states_after_close) != self._window_count:
            errors.append("Quick input exit did not capture every retiring runtime")
        for state in states_after_close:
            if state.get("phase") != "retiring":
                errors.append("Quick input exit left a runtime outside retirement")
            if state.get("input", {}).get("admission_open"):
                errors.append("Quick input remained open after coordinated exit")
            if not state.get("close_meta_calls_queued"):
                errors.append("Quick input exit bypassed queued window teardown")
        return errors

    def _validate_probe(
        self,
        probe: _WindowProbe,
        initial: RenderNodeSnapshot,
        final: RenderNodeSnapshot,
        initial_capture: dict[str, Any],
        resized_capture: dict[str, Any],
        replacement_capture: dict[str, Any],
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
        initial_image_state = initial_scene.get("presentation_image")
        if (
            not isinstance(initial_image_state, dict)
            or initial_image_state.get("identity")
            != probe.presentation_image.identity
            or "rgba8" in initial_image_state
        ):
            errors.append(f"{prefix} scene did not expose detached image metadata")
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
        expected_image_cycles = 2 + self._args.hide_show_cycles
        if final.image_upload_count != expected_image_cycles:
            errors.append(
                f"{prefix} image uploaded {final.image_upload_count} times; "
                f"expected {expected_image_cycles}"
            )
        if final.image_release_count != expected_image_cycles:
            errors.append(
                f"{prefix} image released {final.image_release_count} times; "
                f"expected {expected_image_cycles}"
            )
        if final.image_upload_thread_id != final.render_thread_id:
            errors.append(f"{prefix} image upload did not run on its render thread")
        if final.image_release_thread_id != final.render_thread_id:
            errors.append(f"{prefix} image release did not run on its render thread")
        if final.active_image_identity is not None:
            errors.append(f"{prefix} retained an active image after retirement")
        if final.pending_image_release_count:
            errors.append(f"{prefix} retained pending image texture deletion")
        if final.image_upload_bytes <= 0:
            errors.append(f"{prefix} did not account uploaded image bytes")
        if final.image_upload_bytes != final.image_release_bytes:
            errors.append(f"{prefix} image byte ownership did not balance")
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
        if replacement_capture.get("sample_count", 0) < 3:
            errors.append(f"{prefix} replacement image pixel sample was missing")
        if initial_capture.get("image_upload_count") != 1:
            errors.append(f"{prefix} initial image was not uploaded exactly once")
        if resized_capture.get("image_upload_count") != 1:
            errors.append(f"{prefix} stable image was re-uploaded during resize")
        if replacement_capture.get("image_upload_count") != 2:
            errors.append(f"{prefix} replacement identity did not upload once")
        if (
            replacement_capture.get("active_image_identity")
            != probe.replacement_image.identity
        ):
            errors.append(f"{prefix} replacement identity did not reach render state")
        if len(initial_capture.get("colors", ())) < 2:
            errors.append(f"{prefix} initial capture did not contain deterministic bands")
        if len(resized_capture.get("colors", ())) < 2:
            errors.append(f"{prefix} resized capture did not contain deterministic bands")
        if len(replacement_capture.get("colors", ())) < 2:
            errors.append(
                f"{prefix} replacement capture did not contain deterministic bands"
            )
        if initial_capture.get("colors") == replacement_capture.get("colors"):
            errors.append(f"{prefix} replacement image did not change rendered pixels")
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
            if hidden_snapshot.get("active_image_identity") is not None:
                errors.append(f"{cycle_prefix} retained an image while invalidated")
            if hidden_snapshot.get("pending_image_release_count"):
                errors.append(f"{cycle_prefix} left image deletion pending")
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
            resumed_snapshot = cycle.get("resumed", {})
            if (
                resumed_snapshot.get("active_image_identity")
                != probe.replacement_image.identity
            ):
                errors.append(f"{cycle_prefix} did not recreate its image texture")
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
