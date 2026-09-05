"""Bounded, frame-event-driven real Quick Sphere capture and callback-cost proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rendering.quick.bootstrap import configure_quick_environment, configure_quick_graphics

configure_quick_environment()

from PySide6.QtCore import QObject, Qt, QTimer, Slot, QSize, QMetaObject, Signal, QUrl
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtQml import QQmlComponent, QQmlEngine

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from rendering.quick.visualizer.item import VisualizerRenderItem
from rendering.quick.visualizer.node import VisualizerRenderNode
from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation
from widgets.spotify_visualizer.render_bridge import VisualizerSnapshotBridge
from widgets.spotify_visualizer.render_state import (
    SphereFrame, VisualizerCommonState, VisualizerEnergyState, VisualizerTransientState, VisualizerLogicalFrame,
    compose_visualizer_render_snapshot, freeze_render_fields,
)


class _MeasuredNode(VisualizerRenderNode):
    def __init__(self, telemetry, measurements):
        super().__init__(telemetry)
        self._measurements = measurements

    def render(self, state):
        start = time.perf_counter()
        super().render(state)
        self._measurements.append((time.perf_counter() - start) * 1000.0)


class _MeasuredItem(VisualizerRenderItem):
    def __init__(self, parent):
        self.measurements = []
        super().__init__(parent)

    def _create_render_node(self):
        self.probe_node = _MeasuredNode(self.telemetry, self.measurements)
        return self.probe_node


class _Runner(QObject):
    retirement_checked = Signal(object)

    def __init__(self, app, args):
        super().__init__()
        self.app, self.args = app, args
        self.window = QQuickWindow()
        self.window.setTitle("Sphere material / lifecycle proof")
        self.window.setColor(QColor(13, 19, 29))
        self.window.resize(args.width, args.height)
        self.window.setPersistentGraphics(False)
        self.window.setPersistentSceneGraph(False)
        # Windows may clamp an oversized native window to the monitor's track
        # limits. Keep the capture subtree at its authored extent so a 4K grab
        # cannot stretch a smaller native content item into an ellipse.
        self.capture_root = QQuickItem(self.window.contentItem())
        self.capture_root.setWidth(args.width)
        self.capture_root.setHeight(args.height)
        if args.checkerboard:
            # Static retained background makes actual transmission and smoke
            # blending visible in the capture; the normal transparent grab
            # cannot distinguish a glass surface from a dark opaque material.
            self.background_engine = QQmlEngine()
            component = QQmlComponent(self.background_engine)
            component.setData(b'''import QtQuick
                Rectangle {
                    color: "#263442"
                    Repeater {
                        model: Math.ceil(parent.width / 48) * Math.ceil(parent.height / 48)
                        Rectangle {
                            required property int index
                            readonly property int columns: Math.ceil(parent.width / 48)
                            x: (index % columns) * 48
                            y: Math.floor(index / columns) * 48
                            width: 48; height: 48
                            color: ((index % columns) + Math.floor(index / columns)) % 2
                                ? "#607482" : "#263442"
                        }
                    }
                }''', QUrl())
            background = component.create()
            if not isinstance(background, QQuickItem):
                raise RuntimeError("Sphere proof background failed: " + str(component.errors()))
            background.setParentItem(self.capture_root)
            background.setParent(self.capture_root)
            background.setWidth(args.width)
            background.setHeight(args.height)
            background.setZ(-1.0)
            self.background = background
        self.entries = []
        self.frame_number = 0
        self.closing = False
        self.capture_saved = False
        self.inactive_released = False
        materials = ("Chrome", "Obsidian", "Magma", "Silver", "Water") if args.material == "All" else (args.material,)
        self.material_parameters = {material: freeze_render_fields({"sphere_material": material})
                                    for material in materials}
        if args.preset_settings:
            from types import SimpleNamespace
            from core.settings.visualizer_presets import resolve_visualizer_activation_payload
            from widgets.spotify_visualizer.config_applier import apply_logical_vis_mode_kwargs
            for material in materials:
                index = ("Chrome", "Obsidian", "Magma", "Silver", "Water").index(material)
                config = resolve_visualizer_activation_payload({"mode": "sphere", "preset_sphere": index}).resolved_config
                host = SimpleNamespace()
                apply_logical_vis_mode_kwargs(host, config)
                self.material_parameters[material] = host._sphere_parameters
        for index, material in enumerate(materials):
            columns = 3 if len(materials) > 1 else 1
            rows = 2 if len(materials) > 1 else 1
            cell_width = args.width / columns
            cell_height = args.height / rows
            resolved = resolve_visualizer_presentation(
                policy=get_visualizer_presentation_policy("sphere"),
                display_size=(args.width, args.height),
                viewport_extent=(args.extent_width, args.extent_height),
                uniform_visual_scale=args.scale, dpr=self.window.devicePixelRatio(),
            )
            width, height = resolved.outer_rect[2:]
            origin = ((index % columns) * cell_width + (cell_width - width) * .5,
                      (index // columns) * cell_height + (cell_height - height) * .5)
            p = resolve_visualizer_presentation(
                policy=get_visualizer_presentation_policy("sphere"),
                display_size=(args.width, args.height), outer_origin=origin,
                viewport_extent=(args.extent_width, args.extent_height),
                uniform_visual_scale=args.scale, dpr=self.window.devicePixelRatio(),
            )
            parent = QQuickItem(self.capture_root)
            parent.setX(p.outer_rect[0])
            parent.setY(p.outer_rect[1])
            parent.setWidth(p.outer_rect[2])
            parent.setHeight(p.outer_rect[3])
            item = _MeasuredItem(parent)
            item.set_presentation(p)
            bridge = VisualizerSnapshotBridge()
            identity = bridge.begin_activation(runtime_generation=1, engine_generation=2,
                                               activation_id=3, mode_id="sphere")
            item.bind_render_source(bridge, identity)
            self.entries.append((material, item, bridge, p, parent))
        self.window.frameSwapped.connect(self.advance, Qt.ConnectionType.QueuedConnection)
        self.window.sceneGraphInvalidated.connect(self.finish, Qt.ConnectionType.QueuedConnection)
        self.retirement_checked.connect(self.retirement_ready, Qt.ConnectionType.QueuedConnection)
        # One bounded failure deadline, never an animation/presentation poller.
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self.timeout)

    def publish(self):
        args = self.args
        for material, item, bridge, p, _parent in self.entries:
            logical = VisualizerLogicalFrame(
                runtime_generation=1, engine_generation=2, activation_id=3,
                source_generation=2, source_activation_id=3, mode_id="sphere", playing=True,
                logical_timestamp=10.0 + self.frame_number / 60.0, source_timestamp=10.0,
                changed=True, present_frame=True, mode_reveal_ready=True,
                common=VisualizerCommonState(bars=(), bar_count=0,
                    energy=VisualizerEnergyState(bass=args.bass, mid=args.mid, high=args.high,
                                                 overall=max(args.bass, args.mid, args.high)),
                    transient=VisualizerTransientState(mid=args.transient)),
                mode_state=SphereFrame(authored_time=3.4 + self.frame_number / 60.0,
                    parameters=self.material_parameters[material]),
            )
            snapshot = compose_visualizer_render_snapshot(logical, p, logical_revision=self.frame_number + 1)
            if not bridge.publish(snapshot):
                raise RuntimeError("Sphere smoke publication rejected")
            item.update()

    def start(self):
        self.publish()
        self.window.show()
        self.window.update()
        self.deadline.start(30000)

    @Slot()
    def advance(self):
        if self.closing:
            return
        self.frame_number += 1
        if self.frame_number < self.args.frames:
            self.publish()
            return
        self.closing = True
        output = Path(self.args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        # Asynchronous readback leaves the GIL available to Python render nodes.
        self.capture_result = self.capture_root.grabToImage(QSize(self.args.width, self.args.height))
        if self.capture_result is None:
            raise RuntimeError("Sphere Quick capture could not be scheduled")
        self.capture_result.ready.connect(self.capture_ready)

    @Slot()
    def capture_ready(self):
        capture = self.capture_result.image()
        output = Path(self.args.output)
        self.capture_saved = not capture.isNull() and capture.save(str(output))
        for _material, item, _bridge, _p, _parent in self.entries:
            item.clear_render_source()
            item.setVisible(False)
        self.window.beforeRendering.connect(self.capture_retirement, Qt.ConnectionType.DirectConnection)
        self.window.update()

    def capture_retirement(self):
        # Connected after every inactive-release event, on the same render
        # context. Hidden items must have no mode resources before invalidation.
        self.window.beforeRendering.disconnect(self.capture_retirement)
        self.retirement_checked.emit(tuple(item.probe_node.render_host.resolved_mode_ids
                                          for _, item, _, _, _ in self.entries))

    @Slot(object)
    def retirement_ready(self, resolved_modes):
        self.inactive_released = all(not modes for modes in resolved_modes)
        for method in ("hide", "releaseResources", "close"):
            QMetaObject.invokeMethod(self.window, method, Qt.ConnectionType.QueuedConnection)

    @Slot()
    def finish(self):
        if not self.closing:
            return
        self.deadline.stop()
        reports = []
        for material, item, _bridge, _p, _parent in self.entries:
            telemetry = item.telemetry.snapshot()
            samples = sorted(item.measurements[5:])
            reports.append({
                "material": material, "draws": telemetry.draw_count,
                "released": telemetry.release_count, "error": telemetry.error,
                "warm_callback_median_ms": round(statistics.median(samples), 3) if samples else None,
                "warm_callback_p95_ms": round(samples[int(.95 * (len(samples) - 1))], 3) if samples else None,
                "render_thread": telemetry.render_thread_id, "release_thread": telemetry.release_thread_id,
            })
        valid = self.capture_saved and self.inactive_released and all(r["draws"] > 0 and r["released"] > 0 and not r["error"]
                                           and r["render_thread"] == r["release_thread"] for r in reports)
        report = {"valid": valid, "size": (self.args.width, self.args.height),
                  "native_window_size": (self.window.width(), self.window.height()),
                  "dpr": self.window.devicePixelRatio(),
                  "capture": str(Path(self.args.output).resolve()), "modes": reports,
                  "inactive_resources_released_before_invalidation": self.inactive_released,
                  "measurement": "Render callback wall time; not GPU time or physical cadence acceptance"}
        print(json.dumps(report), flush=True)
        Path(self.args.output).with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        self.app.exit(0 if valid else 1)

    @Slot()
    def timeout(self):
        print(json.dumps({"valid": False, "error": "Sphere Quick proof deadline expired"}), flush=True)
        self.app.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="logs/evidence_chest/fw_sphere/materials.png")
    parser.add_argument("--material", choices=("All", "Chrome", "Obsidian", "Magma", "Silver", "Water"), default="All")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--extent-width", type=float, default=420)
    parser.add_argument("--extent-height", type=float, default=280)
    parser.add_argument("--scale", type=float, default=1.2)
    parser.add_argument("--frames", type=int, default=80)
    parser.add_argument("--checkerboard", action="store_true", help="Retained background for transparency/smoke inspection")
    parser.add_argument("--preset-settings", action="store_true", help="Resolve actual curated Sphere settings before capture")
    parser.add_argument("--bass", type=float, default=.65)
    parser.add_argument("--mid", type=float, default=.75)
    parser.add_argument("--high", type=float, default=.35)
    parser.add_argument("--transient", type=float, default=0.0)
    args = parser.parse_args()
    configure_quick_graphics()
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    runner = _Runner(app, args)
    runner.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
