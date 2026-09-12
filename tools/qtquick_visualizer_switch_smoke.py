"""Real-GL repeated-mode-switch smoke for the inline Quick visualizer host (P3).

Authority: ``Docs/Future_Work/Visualizer_Post_Switch_Performance.md`` phase P3.
Guardrail: ``Docs/Guardrails/Performance_Optimization_Contract.md``.

This reuses the proven real-``QQuickWindow`` / ``VisualizerRenderItem`` /
``VisualizerSnapshotBridge`` plumbing and the per-mode snapshot factories from
``qtquick_visualizer_clip_smoke.py`` rather than inventing a fake compositor. It
drives a deterministic mode sequence (default
``spectrum -> oscilloscope -> sine_wave -> bubble -> devcurve``) for N cycles,
then holds Bubble, advancing only after each target mode has produced and drawn
an accepted snapshot -- never on a blind wall-clock toggle.

It reports one JSON object: requested/completed switch counts, the active mode
after every completion, the boundary-only render-host lifecycle telemetry (P1)
after each switch, a separate ``settled_hold`` record for the final Bubble hold
(kept out of the ``per_switch`` series so the switch record stays honest), node
render/sync/draw/invalidation deltas, GL error status at the existing bounded
capture points, and the final teardown resource/thread state. The tool admits the
opt-in switch telemetry itself (tools enable it directly, not via app argv).

This is the PERMANENT-mode real-GL retirement probe: it deliberately does NOT
include the experimental Sphere architecture (that is exercised at the P2
ownership seam and in the P4 real-product exposure). Passing here is not proof
that the Sphere-starting P4 exposure is clean. It is a lifecycle/ownership probe;
it cannot prove the physical performance bug. Its acceptance is only that
ownership stays bounded through the real-GL sequence and teardown is clean (any
accumulation is a concrete H1 lead, not a fix mandate).

Run (only on a machine with a live display/GL surface)::

    python tools/qtquick_visualizer_switch_smoke.py --cycles 5 --hold-seconds 2.0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import threading
import time
from dataclasses import asdict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_TOOLS_DIR = str(Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

# Importing the clip smoke runs its module-level configure_quick_environment()
# and gives us the maintained per-mode snapshot factories + window sizing without
# duplicating ~700 lines. This is the sibling the P3 phase explicitly allows.
import qtquick_visualizer_clip_smoke as clip  # noqa: E402

from PySide6.QtCore import QMetaObject, QObject, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQuick import (  # noqa: E402
    QQuickItem,
    QQuickWindow,
    QSGRendererInterface,
)

from core.settings.visualizer_mode_registry import (  # noqa: E402
    get_visualizer_presentation_policy,
)
from rendering.quick.bootstrap import configure_quick_graphics  # noqa: E402
from rendering.quick.visualizer import (  # noqa: E402
    VisualizerRenderItem,
    VisualizerRenderNodeTelemetry,
)
from widgets.spotify_visualizer.presentation_geometry import (  # noqa: E402
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.render_bridge import (  # noqa: E402
    VisualizerRenderIdentity,
    VisualizerSnapshotBridge,
)


_WINDOW_SIZE = (760, 600)
_ORIGIN = (80.0, 60.0)

# Modes with a maintained real-GL snapshot factory in the clip smoke. Sphere is
# the architecturally isolated experimental mode and has no clip-smoke factory,
# so it is out of scope for this permanent-mode ownership probe.
_SNAPSHOT_FACTORIES = {
    "spectrum": clip._spectrum_snapshot,
    "oscilloscope": clip._oscilloscope_snapshot,
    "sine_wave": clip._sine_snapshot,
    "bubble": clip._bubble_snapshot,
    "devcurve": clip._devcurve_snapshot,
}
_DEFAULT_SEQUENCE = ("spectrum", "oscilloscope", "sine_wave", "bubble", "devcurve")


# Neutral card/shadow inputs: this ownership probe measures switch/retirement, not
# the card/border/shadow presentation, so the migrated card kwargs are supplied as
# a transparent, no-shadow neutral (mirrors tests/_visualizer_presentation.py).
_NEUTRAL_CARD_SHADOW = {
    "content_inset": 0.0,
    "background_color": (0, 0, 0, 0),
    "border_color": (255, 255, 255, 255),
    "shadow_color": (0, 0, 0, 0),
    "shadow_blur": 0.0,
    "shadow_offset": (0.0, 0.0),
    "shadow_spread": 0.0,
    "shadow_extensions": (0.0, 0.0, 0.0, 0.0),
}


def _presentation_for(mode_id: str):
    return resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(mode_id),
        display_size=_WINDOW_SIZE,
        outer_origin=_ORIGIN,
        viewport_extent=(420.0, 280.0),
        uniform_visual_scale=1.0,
        border_width=4.0,
        corner_radius=12.0,
        shadow_enabled=False,
        **_NEUTRAL_CARD_SHADOW,
    )


class _SwitchRunner(QObject):
    """Drive the deterministic switch sequence and record boundary telemetry."""

    def __init__(
        self,
        app: QGuiApplication,
        *,
        sequence: tuple[str, ...],
        cycles: int,
        hold_seconds: float,
        deadline_seconds: float,
    ) -> None:
        super().__init__()
        self._app = app
        self._hold_seconds = float(hold_seconds)
        self._deadline = time.monotonic() + float(deadline_seconds)
        # The full plan is `cycles` passes of `sequence`, then a Bubble hold.
        self._plan: list[str] = []
        for _ in range(cycles):
            self._plan.extend(sequence)
        self._plan.append("bubble")  # final settled hold mode
        self._plan_index = 0

        self._telemetry = VisualizerRenderNodeTelemetry()
        self._window = QQuickWindow()
        self._window.setColor(clip._BACKGROUND)
        self._window.resize(*_WINDOW_SIZE)
        self._window.setPersistentGraphics(False)
        self._window.setPersistentSceneGraph(False)
        self._host = QQuickItem(self._window.contentItem())
        self._item = VisualizerRenderItem(self._host, telemetry=self._telemetry)
        self._bridge = VisualizerSnapshotBridge()

        self._frame_swap_count = 0
        self._window.frameSwapped.connect(self._on_frame_swapped)

        self._requested_switches = 0
        self._completed_switches = 0
        self._active_mode: str | None = None
        self._pending_mode: str | None = None
        self._pending_draw_baseline = 0
        self._pending_swap_baseline = 0
        self._per_switch: list[dict[str, object]] = []
        self._settled_hold: dict[str, object] | None = None
        self._last_telemetry = self._telemetry.snapshot()
        self._error: str | None = None
        self._closing = False
        self._hold_deadline: float | None = None

    def _on_frame_swapped(self) -> None:
        self._frame_swap_count += 1

    def start(self) -> None:
        self._window.show()
        self._request_next_mode()
        QTimer.singleShot(20, self._poll)

    # ---- mode-switch driving -------------------------------------------------

    def _request_next_mode(self) -> None:
        if self._plan_index >= len(self._plan):
            self._pending_mode = None
            self._hold_deadline = time.monotonic() + self._hold_seconds
            return
        mode_id = self._plan[self._plan_index]
        self._plan_index += 1
        presentation = _presentation_for(mode_id)
        self._item.set_presentation(presentation)
        # Each mode change is a fresh activation; a switch only counts once the
        # target has produced and drawn an accepted snapshot (checked in _poll).
        self._bridge.begin_activation(
            runtime_generation=1,
            engine_generation=2,
            activation_id=3,
            mode_id=mode_id,
        )
        snapshot = _SNAPSHOT_FACTORIES[mode_id](
            "canonical" if mode_id != "bubble" else "trail", presentation
        )
        if not self._bridge.publish(snapshot):
            self._error = f"{mode_id} switch snapshot was rejected"
            return
        identity = VisualizerRenderIdentity(
            runtime_generation=1, engine_generation=2, activation_id=3,
            mode_id=mode_id,
        )
        self._item.bind_render_source(self._bridge, identity)
        self._pending_mode = mode_id
        self._pending_draw_baseline = self._telemetry.snapshot().draw_count
        self._pending_swap_baseline = self._frame_swap_count
        self._requested_switches += 1
        self._item.update()
        self._window.update()

    def _ownership_record(self, mode_id: str) -> dict[str, object]:
        """Build one boundary ownership record (lifecycle + node deltas/totals).

        Pure: it reads telemetry but does not advance ``_last_telemetry`` or
        ``_active_mode`` so it can serve both a completed switch and the separate
        settled Bubble-hold record.
        """
        telemetry = self._telemetry.snapshot()
        lifecycle = self._item.render_host_lifecycle_snapshot()
        return {
            "active_mode": mode_id,
            "render_host": asdict(lifecycle) if lifecycle is not None else None,
            "node_deltas": {
                "sync": telemetry.sync_count - self._last_telemetry.sync_count,
                "render": telemetry.render_count - self._last_telemetry.render_count,
                "draw": telemetry.draw_count - self._last_telemetry.draw_count,
                "invalidation": (
                    telemetry.invalidation_count
                    - self._last_telemetry.invalidation_count
                ),
            },
            "node_totals": {
                "sync": telemetry.sync_count,
                "render": telemetry.render_count,
                "draw": telemetry.draw_count,
                "release": telemetry.release_count,
                "invalidation": telemetry.invalidation_count,
            },
        }

    def _record_completed_switch(self, mode_id: str) -> None:
        record = self._ownership_record(mode_id)
        record = {"completed_index": self._completed_switches, **record}
        self._per_switch.append(record)
        self._last_telemetry = self._telemetry.snapshot()
        self._active_mode = mode_id

    # ---- poll loop -----------------------------------------------------------

    def _poll(self) -> None:
        if self._error is not None:
            self._finish(valid=False)
            return
        if time.monotonic() > self._deadline:
            self._error = "switch smoke timed out"
            self._finish(valid=False)
            return
        node_error = self._telemetry.snapshot().error
        if node_error is not None:
            self._error = node_error
            self._finish(valid=False)
            return

        if self._pending_mode is not None:
            telemetry = self._telemetry.snapshot()
            drew = (
                telemetry.draw_count > self._pending_draw_baseline
                and telemetry.drawn_mode_id == self._pending_mode
                and self._frame_swap_count > self._pending_swap_baseline
            )
            if drew:
                self._completed_switches += 1
                self._record_completed_switch(self._pending_mode)
                self._pending_mode = None
                self._request_next_mode()
            QTimer.singleShot(20, self._poll)
            return

        # Sequence complete: settle on the final Bubble hold, then tear down.
        if self._hold_deadline is not None and time.monotonic() < self._hold_deadline:
            self._window.update()
            QTimer.singleShot(30, self._poll)
            return

        if not self._closing:
            self._closing = True
            # The settled Bubble hold is its own result, NOT another switch record:
            # keep it in a dedicated field so the switch series stays honest.
            self._settled_hold = self._ownership_record(self._active_mode or "bubble")
            for method in ("hide", "releaseResources", "close"):
                QMetaObject.invokeMethod(
                    self._window, method, Qt.ConnectionType.QueuedConnection
                )
            QTimer.singleShot(30, self._poll)
            return

        telemetry = self._telemetry.snapshot()
        if telemetry.release_count < 1:
            QTimer.singleShot(20, self._poll)
            return
        self._finish(valid=True)

    def _finish(self, *, valid: bool) -> None:
        telemetry = self._telemetry.snapshot()
        final_lifecycle = self._item.render_host_lifecycle_snapshot()
        report = {
            "valid": bool(valid and self._error is None),
            "error": self._error,
            "requested_switches": self._requested_switches,
            "completed_switches": self._completed_switches,
            "active_mode_final": self._active_mode,
            "per_switch": self._per_switch,
            "settled_hold": self._settled_hold,
            "final_render_host": (
                asdict(final_lifecycle) if final_lifecycle is not None else None
            ),
            "final_node_telemetry": {
                "sync_count": telemetry.sync_count,
                "render_count": telemetry.render_count,
                "draw_count": telemetry.draw_count,
                "release_count": telemetry.release_count,
                "invalidation_count": telemetry.invalidation_count,
                "render_thread_id": telemetry.render_thread_id,
                "release_thread_id": telemetry.release_thread_id,
                "error": telemetry.error,
            },
            "gui_thread_id": threading.get_ident(),
        }
        print(json.dumps(report, sort_keys=True), flush=True)
        self._app.exit(0 if report["valid"] else 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=5, help="sequence repetitions")
    parser.add_argument(
        "--hold-seconds", type=float, default=2.0,
        help="settled Bubble hold after the switch sequence",
    )
    parser.add_argument(
        "--deadline-seconds", type=float, default=60.0,
        help="overall wall-clock safety deadline",
    )
    parser.add_argument(
        "--sequence", default=",".join(_DEFAULT_SEQUENCE),
        help="comma-separated permanent-mode switch order",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    sequence = tuple(
        mode.strip() for mode in args.sequence.split(",") if mode.strip()
    )
    unknown = [mode for mode in sequence if mode not in _SNAPSHOT_FACTORIES]
    if unknown:
        print(json.dumps({"valid": False, "error": f"unknown modes: {unknown}"}))
        return 2

    # This tool IS the diagnostic: admit the opt-in boundary render-host telemetry
    # directly (tools inject/enable it rather than depending on the app argv), so
    # the render host allocates its lifecycle telemetry and the snapshots below are
    # populated instead of None.
    from core.diagnostics.experiment_flags import (
        ExperimentFlags,
        activate_experiment_flags,
    )

    activate_experiment_flags(ExperimentFlags(viz_switch_telemetry=True))

    configure_quick_graphics(reason="visualizer-switch-smoke")
    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("SRPSSQuickVisualizerSwitchSmoke")
    app.setQuitOnLastWindowClosed(False)
    if QQuickWindow.graphicsApi() != QSGRendererInterface.GraphicsApi.OpenGL:
        print(json.dumps({"valid": False, "error": "Quick is not using OpenGL"}))
        return 1
    runner = _SwitchRunner(
        app,
        sequence=sequence,
        cycles=max(1, int(args.cycles)),
        hold_seconds=max(0.0, float(args.hold_seconds)),
        deadline_seconds=max(5.0, float(args.deadline_seconds)),
    )
    QTimer.singleShot(0, runner.start)
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
