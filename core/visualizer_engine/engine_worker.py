"""The visualizer engine worker (native core P2, work order 4: P2a's tick out of process).

``EngineSession`` hosts one activation's logical tick and mode runtime exactly as the main process does today: the
runtime controller with its tick state, configured on the logical side only, a post-DSP input engine fed one input
per tick, and the logical mailbox replaced by the writer side of the frame packet ABI (``PacketMailbox``), so every
tick lands in the shared mapping the main process owns and reads. ``VisualizerEngineWorker`` runs sessions in a
``WorkerType.VISUALIZER`` process under ``ProcessSupervisor`` (control messages only: configure, input, stop).

This slice drives the session from recorded post-DSP inputs (``FeatureFrame``, the replay schema the live engine
records), one acknowledged input per tick, which is what the identity gate needs: the worker's frames equal the
in-process owner's for every mode (``tests/test_visualizer_engine_worker.py``). Production wiring (live inputs from
the main process's beat engine, latest-wins without acknowledgements, the GUI wake, park, crash fail-closed) is work
order 5. The worker loads QtCore and, for the presentation config the tick still reads, QtGui (QColor only:
no QGuiApplication, no QtQuick); removing that read is part of work order 5.
"""
from __future__ import annotations

import contextlib
import itertools
import sys
from typing import Any, Optional

from core.process.types import MessageType, WorkerMessage, WorkerResponse, WorkerType
from core.process.workers.base import BaseWorker


class EngineSession:
    """One activation's tick host: inputs in, frames into the shared mapping ``mapping`` (attached as writer)."""

    def __init__(self, *, mapping: str, mode: str, runtime_generation: int, preset: int = 0, settings: Any = None,
                 bar_count: int = 32, label_namespace: int = 0) -> None:
        from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
        from core.visualizer_engine.packet_mailbox import PacketMailbox
        from widgets.spotify_visualizer import extruded_bubble_drift_log
        from widgets.spotify_visualizer.feature_replay import (
            PcmReanalysis, ReplayBeatEngine, configure_offline_controller, deterministic_clock,
        )
        from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

        if not 0 <= int(label_namespace) < (1 << 30):
            raise ValueError(f"label namespace out of range: {label_namespace}")
        self._stack = contextlib.ExitStack()
        # The session's authored clock follows its inputs' own timestamps (each input carries the time it was
        # produced), so the worker ticks the same frames whatever its scheduling.
        self._clock = self._stack.enter_context(deterministic_clock())
        # Extruded Bubble's drift-family revisions are the renderer's geometry cache identity, so no two sessions may
        # reuse one: the main process gives every session its own ``label_namespace`` (>= 1, never repeated), and its
        # revisions start at ``namespace << 32`` (the main process's own counter stays far below). Namespace 0 numbers
        # from 1, as a fresh in-process replay does (the identity gates).
        extruded_bubble_drift_log._REVISIONS = itertools.count((int(label_namespace) << 32) + 1)
        self.mailbox = PacketMailbox(role="writer", attach=mapping)
        self._stack.callback(self.mailbox.close)
        engine = ReplayBeatEngine(bar_count)
        # The main process's runtime generation (a control input: every frame carries it).
        controller = VisualizerRuntimeController(runtime_generation=int(runtime_generation), initial_mode=mode,
                                                 engine_factory=lambda _count: engine)
        controller.engine = engine
        controller.replace_logical_mailbox(self.mailbox)
        # Both sides: the logical capture still reads presentation config (Spectrum's decoration fades and colours,
        # the Oscilloscope/Bubble spec parameters), which loads QtGui for QColor here. Work order 5 moves those
        # reads into the logical config so the worker imports QtCore only (P2 design, Risks).
        configure_offline_controller(controller, mode, preset, None, settings)
        self._engine, self._controller = engine, controller
        self._reanalysis = PcmReanalysis() if get_visualizer_mode_descriptor(mode).raw_musical_signals else None

    def tick(self, feature: Any) -> int:
        """Accept one post-DSP input, run the tick, publish its frame; the mailbox revision after it."""
        from widgets.spotify_visualizer.tick_pipeline import logical_tick

        self._clock[0] = feature.timestamp_us / 1_000_000.0
        self._controller.playing = feature.playing
        self._engine.set_playback_state(feature.playing)
        if not self._engine.accept_feature_frame(feature):
            raise ValueError("the engine rejected a post-DSP input")
        if self._reanalysis is not None:
            self._reanalysis.accept(self._engine, feature)
        if logical_tick(self._controller.logical_tick_state) is None:
            raise RuntimeError("the tick produced no logical frame")
        return self.mailbox.revision

    def close(self) -> None:
        self._stack.close()


class VisualizerEngineWorker(BaseWorker):
    """``WorkerType.VISUALIZER``: one engine session at a time, driven by control messages."""

    def __init__(self, request_queue, response_queue) -> None:
        super().__init__(request_queue, response_queue)
        self._session: Optional[EngineSession] = None

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.VISUALIZER

    def _reply(self, msg: WorkerMessage, *, success: bool = True, error: str | None = None,
               **payload: Any) -> WorkerResponse:
        return WorkerResponse(msg_type=msg.msg_type, seq_no=msg.seq_no, correlation_id=msg.correlation_id,
                              success=success, error=error, payload=payload)

    def handle_message(self, msg: WorkerMessage) -> Optional[WorkerResponse]:
        try:
            if msg.msg_type == MessageType.VIS_CONFIGURE:
                self._close_session()
                payload = dict(msg.payload)
                self._session = EngineSession(**payload)
                qt = sorted(name for name in sys.modules if name.startswith("PySide6.Qt"))
                return self._reply(msg, qt_modules=qt)
            if msg.msg_type == MessageType.VIS_INPUT:
                if self._session is None:
                    return self._reply(msg, success=False, error="no engine session is configured")
                return self._reply(msg, revision=self._session.tick(msg.payload["frame"]))
            if msg.msg_type == MessageType.VIS_STOP:
                self._close_session()
                return self._reply(msg)
        except Exception as exc:                       # reported to the owner, never a silent worker death
            return self._reply(msg, success=False, error=f"{type(exc).__name__}: {exc}")
        return self._reply(msg, success=False, error=f"unsupported message {msg.msg_type}")

    def _close_session(self) -> None:
        if self._session is not None:
            session, self._session = self._session, None
            session.close()

    def _cleanup(self) -> None:
        self._close_session()
        super()._cleanup()


def visualizer_worker_main(request_queue, response_queue) -> None:
    """``ProcessSupervisor`` factory for ``WorkerType.VISUALIZER``."""
    VisualizerEngineWorker(request_queue, response_queue).run()
