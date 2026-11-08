"""The visualizer engine worker (native core P2, work order 4: P2a's tick out of process).

``EngineSession`` hosts one activation's logical tick and mode runtime exactly as the main process does today: the
runtime controller with its tick state, configured on the logical side only, a post-DSP input engine fed one input
per tick, and the logical mailbox replaced by the writer side of the frame packet ABI (``PacketMailbox``), so every
tick lands in the shared mapping the main process owns and reads. ``VisualizerEngineWorker`` runs sessions in a
``WorkerType.VISUALIZER`` process under ``ProcessSupervisor`` (control messages only: configure, input, stop).

A session ticks recorded post-DSP inputs (``FeatureFrame``, the replay schema the live engine records) or live
inputs, the main process's lossless engine snapshots (``engine_snapshot``), one acknowledged input per tick, which is
what the identity gates need: the worker's frames equal the in-process tick's for every mode
(``tests/test_visualizer_engine_worker.py``, ``tests/test_visualizer_engine_snapshot.py``). P2b's rig
(``inputs="live"``) runs the production ``_SpotifyBeatEngine`` itself, with its real audio worker, capture lane and
compute pool, fed the recordings' PCM through the capture callback (``recorded_capture``;
``tests/test_visualizer_engine_live.py``). Every session configures through the production owner's own
configuration (``logical_edges.configure_logical_controller``, then the owner's bind: render admission for the
configured identity; checkpoint audit 5, A5-M2), never a replay copy. Production wiring (latest-wins snapshots without
acknowledgements, park, crash fail-closed) is work order 5; its first slice (5.1) is built: a ``cadence="worker"``
live session ticks on its own clock, the logical runtime's own cadence (``VisualizerLogicalRuntime``, started through
``logical_edges.start_logical_cadence`` as the owner starts it), fed a recorded PCM stream paced on the audio clock at
the cadence's edges (``recorded_capture.PacedPcmSource``), and its frames reach the reader through the same mailbox
and wake (``tests/test_visualizer_engine_paced.py``). Imports load QtCore only; a configuration loads QtGui
(``QColor`` in the presentation config the tick still reads: no QGuiApplication, no QtQuick; A5-L2); work order 5
slice 5.4 moves those reads to the logical config.
"""
from __future__ import annotations

import contextlib
import itertools
import sys
from typing import Any, Optional

from core.process.types import MessageType, WorkerMessage, WorkerResponse, WorkerType
from core.process.workers.base import BaseWorker
from core.visualizer_engine.engine_snapshot import SnapshotContractError


class EngineSession:
    """One activation's tick host: inputs in, frames into the shared mapping ``mapping`` (attached as writer)."""

    #: ``feature``: recorded post-DSP inputs (``FeatureFrame``) through ``ReplayBeatEngine`` (the replay contract).
    #: ``lanes``: the same inputs through production DSP on their native PCM (``ProductionLaneEngine``), the
    #: in-process reference for live inputs. ``snapshot``: live inputs, the main process's lossless engine snapshots
    #: (``engine_snapshot``), through ``SnapshotBeatEngine``; requires ``initial_snapshot``. ``live`` (P2b): the
    #: production ``_SpotifyBeatEngine`` with its real audio worker, capture lane and compute pool on the session's
    #: own ``ThreadManager``, fed each ``FeatureFrame``'s native PCM through the capture callback
    #: (``recorded_capture.RecordedCaptureBackend``; a device is refused for the session's life); ``order`` decides
    #: when the asynchronous commit lands relative to the tick (``ORDERS``).
    INPUTS = ("feature", "lanes", "live", "snapshot")

    #: Live sessions' commit order. ``production`` (the reference for the off-steady-state gates; checkpoint audit
    #: 3, A3-H1): the tick's own engine step consumes the newest block and submits its analysis, the tick reads the
    #: previous commit, as live (``tick_pipeline.consume_engine_bars``); the analysis is held at the compute lane's
    #: admission gate until the tick returns, then the session waits for it to commit, so the next tick reads it,
    #: deterministically. ``settled`` (slice 1, the portability gate): the session steps first and the tick reads
    #: the commit of the block it was fed. ``free``: production order with no hold and no wait (stress only: the
    #: commit races the tick, frames are not reproducible).
    ORDERS = ("production", "settled", "free")

    #: Who paces the ticks. ``input`` (every gate so far): one tick per input (``tick``), deterministic. ``worker``
    #: (work order 5, slice 5.1; live inputs in ``free`` order only): the session ticks on its own cadence, the logical
    #: runtime the owner runs in process (``logical_edges.start_logical_cadence``: ``VisualizerLogicalRuntime``, one
    #: non-Qt thread, missed deadlines skipped, parked with the display), started by ``start``; audio comes from
    #: ``pcm`` (a recorded mono stream at ``pcm_rate``) handed to the capture callback on the audio clock at each
    #: cadence edge (``recorded_capture.PacedPcmSource``); frames go out through the mailbox and wake as always, and a
    #: reader that stalls only coalesces (latest wins in the ABI). The authored clock is the process's own.
    CADENCES = ("input", "worker")

    #: How long a live session waits for its own capture to open or its analysis to settle before failing closed.
    LIVE_EDGE_TIMEOUT_S = 30.0

    def __init__(self, **kwargs: Any) -> None:
        # A session that fails while being built releases what it entered (the pinned authored clock, the attached
        # mapping) before the error reaches the worker (checkpoint audit 2, A2-M1).
        try:
            self._construct(**kwargs)
        except BaseException:
            stack = self.__dict__.get("_stack")
            if stack is not None:
                stack.close()
            raise

    def _construct(self, *, mapping: str, mode: str, runtime_generation: int, preset: int = 0, settings: Any = None,
                 bar_count: int = 32, label_namespace: int = 0, wake: Any = None, inputs: str = "feature",
                 initial_snapshot: Any = None, seed: int | None = None, order: str = "production",
                 cadence: str = "input", pcm: Any = None, pcm_rate: int | None = None,
                 interval_s: float | None = None) -> None:
        from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
        from core.visualizer_engine.engine_snapshot import SnapshotBeatEngine
        from core.visualizer_engine.packet_mailbox import PacketMailbox
        from widgets.spotify_visualizer import extruded_bubble_drift_log
        from widgets.spotify_visualizer.feature_replay import (
            PcmReanalysis, ProductionLaneEngine, ReplayBeatEngine, deterministic_clock,
        )
        from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

        if not 0 <= int(label_namespace) < (1 << 30):
            raise ValueError(f"label namespace out of range: {label_namespace}")
        if inputs not in self.INPUTS or (inputs == "snapshot") != (initial_snapshot is not None):
            raise ValueError(f"inputs {inputs!r} with{'' if initial_snapshot is not None else 'out'} an initial snapshot")
        if order not in self.ORDERS:
            raise ValueError(f"unknown live commit order {order!r}")
        if cadence not in self.CADENCES:
            raise ValueError(f"unknown cadence {cadence!r}")
        if (cadence == "worker") != (pcm is not None) or (
                cadence == "worker" and (inputs != "live" or order != "free" or not pcm_rate)):
            raise ValueError("a worker-paced session is a live session in free order fed a recorded PCM stream")
        self.inputs = inputs
        self.order = order
        self.cadence = cadence
        self._paced = cadence == "worker"
        self._stack = contextlib.ExitStack()
        # The session's authored clock follows its inputs' own timestamps (each input carries the time it was
        # produced), so the worker ticks the same frames whatever its scheduling. Live (snapshot) sessions pin only
        # the authored clock: ``time.*`` and ``random`` stay the process's own (audit H6), so a tick that read a wall
        # clock or the RNG would fail the identity gates instead of being pinned equal. Recorded-input sessions are
        # replays and keep the replay harness's full pin.
        if inputs in ("snapshot", "live"):
            from core.authored_clock import pinned_authored_clock

            self._clock = [0.0]
            if not self._paced:                # a worker-paced session runs on the process's own clocks
                self._stack.enter_context(pinned_authored_clock(lambda: self._clock[0]))
            # Bubble's spawn draws from the process RNG, by design random (as in process). ``seed`` (a control
            # input) lets the identity gates compare against a seeded replay; production passes none. With the seed
            # passed, the gates cannot tell a new global-RNG read in the tick from Bubble's (checkpoint audit 2,
            # A2-M2): giving Bubble its own generator is a P2b item.
            if seed is not None:
                import random

                random.seed(int(seed))
        else:
            self._clock = self._stack.enter_context(deterministic_clock())
        # Extruded Bubble's drift-family revisions are the renderer's geometry cache identity, so no two sessions may
        # reuse one: the main process gives every session its own ``label_namespace`` (>= 1, never repeated), and its
        # revisions start at ``namespace << 32`` (the main process's own counter stays far below). Namespace 0 numbers
        # from 1, as a fresh in-process replay does (the identity gates).
        extruded_bubble_drift_log._REVISIONS = itertools.count((int(label_namespace) << 32) + 1)
        # ``wake``: the writer end of the owner's wake pipe (one byte per publish; the owner's emitter coalesces).
        self.mailbox = PacketMailbox(role="writer", attach=mapping, wake_sender=wake)
        self._stack.callback(self.mailbox.close)
        self._live = inputs == "live"
        if inputs == "snapshot":
            engine = SnapshotBeatEngine(initial_snapshot)
            self._clock[0] = initial_snapshot.timestamp
        elif self._live:
            import threading

            from core.visualizer_engine.recorded_capture import CaptureHistoryStream
            from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

            engine = _SpotifyBeatEngine(bar_count)
            self._backend = None
            self._backends: list = []                  # every recorded source capture opened (the gates report them)
            self._settled = threading.Event()
            self._admission = threading.Event()        # the compute lane's admission gate (production order)
            self._admission.set()
            self._admission_failed = False
            self._stream = CaptureHistoryStream()
            self._live_started = False         # the owner's ``start`` runs at the first input (its clock)
            self._engine_acquired = False      # the session's engine reference (taken at ``start``)
            self._released_for_display_power = False
            self._display_on = True            # display power: a parked session does not tick
            self._pending_mode: tuple | None = None   # the newest mode request, applied at the next tick boundary
            if self._paced:
                from core.visualizer_engine.recorded_capture import PacedPcmSource

                self._source = PacedPcmSource(pcm, int(pcm_rate))
                self._interval_s = interval_s
                self._paced_failure: str | None = None
                self._paced_failed = threading.Event()
                self._cadence_record: dict | None = None
        else:
            engine = (ProductionLaneEngine if inputs == "lanes" else ReplayBeatEngine)(bar_count)
        # The main process's runtime generation (a control input: every frame carries it).
        controller = VisualizerRuntimeController(runtime_generation=int(runtime_generation), initial_mode=mode,
                                                 engine_factory=lambda _count: engine)
        controller.engine = engine
        controller.replace_logical_mailbox(self.mailbox)
        self._engine, self._controller = engine, controller
        self.mode = mode
        self._configure(preset, settings, self._prepare_live_engine() if self._live else None)
        if self._live:
            self._wire_live_engine(mode)
        if self._paced:
            # Closed first (LIFO): the cadence joins before capture, the compute lane and the mapping go.
            self._stack.callback(self._stop_cadence)
        # The header's configure-time identity, before any frame (audit H5); every slot carries its own frame's
        # identity under its seqlock (A3-M4), so an in-place mode switch never relabels a slot.
        self.mailbox.write_identity(runtime_generation=int(runtime_generation),
                                    engine_generation=int(engine.get_generation_id()),
                                    activation_id=int(engine.get_activation_id()), mode=mode)
        # A raw-musical mode replays production DSP on the input's PCM; ``ProductionLaneEngine`` does that itself.
        raw = get_visualizer_mode_descriptor(mode).raw_musical_signals
        self._reanalysis = PcmReanalysis() if raw and inputs == "feature" else None

    def _configure(self, preset: int, settings: Any, thread_manager: Any) -> None:
        """The host binding's configure and bind on the logical side (checkpoint audit 5, A5-M2): the owner's
        ``configure`` (``logical_edges.configure_logical_controller``: the activation's resolved inputs recorded, then
        the configuration with separate logical / presentation kwargs, the technical config, the mode's logical state
        and the warm re-entry fence; Media's state not playing until its edge, as the host binding passes it), then the
        owner's bind (render admission for the configured identity). The logical capture still reads presentation
        config (Spectrum's decoration fades and colours, the Oscilloscope/Bubble spec parameters), which loads QtGui
        for ``QColor`` here (A5-L2; work order 5 slice 5.4)."""
        from widgets.spotify_visualizer.feature_replay import offline_activation_request
        from widgets.spotify_visualizer.logical_edges import configure_logical_controller
        from widgets.spotify_visualizer.technical_config import resolve_technical_config

        controller, engine = self._controller, self._engine
        request = offline_activation_request(controller.mode_id, preset, None, settings)
        configure_logical_controller(
            controller,
            activation={key: request[key] for key in ("settings_model", "resolved_activation", "technical_cache")},
            logical_kwargs=request["logical_kwargs"], presentation_kwargs=request["presentation_kwargs"],
            technical_config=resolve_technical_config(request["technical_cache"], controller.mode_id),
            thread_manager=thread_manager, process_supervisor=None, playing=False,
        )
        controller.begin_render_activation(engine_generation=engine.get_generation_id(),
                                           activation_id=engine.get_activation_id())

    def _prepare_live_engine(self) -> Any:
        """Before the configuration: the device refused and the session's own ``ThreadManager`` (the capture lane and
        the compute pool), which the configuration hands the controller as the owner's ``configure`` does."""
        from core.threading.manager import ThreadManager

        # A recorded-PCM session never opens a device, in whichever process it runs (checkpoint audit 3, A3-L1: a
        # test's monkeypatch reaches only its own process): this engine's audio worker refuses the device path for
        # its life (per engine, never a process-wide swap: A4-L3). The refusal matters only while no capture factory
        # is installed (the factory, installed below, is always the source when present), so it is defence in depth
        # for this session's own engine; another engine in the same process is not refused (checkpoint audit 5,
        # A5-L6; the worker hosts one engine).
        self._engine.refuse_capture_devices()
        manager = ThreadManager()
        self._stack.callback(manager.shutdown, wait=True, timeout=self.LIVE_EDGE_TIMEOUT_S)
        return manager

    def _wire_live_engine(self, mode: str) -> None:
        """Wire the configured engine: the recorded capture source, the commit observers; the owner's ``start``
        (engine reference, playback commit, cold capture) runs at the first input."""
        from widgets.spotify_visualizer.tick_pipeline import declare_mode_engine_demands

        engine = self._engine
        engine.set_capture_backend_factory(self._open_capture)
        engine.set_analysis_settled_observer(self._settled.set)
        if self.order == "production":
            engine.set_analysis_admission_gate(self._admit_analysis)
            # An admission failure refuses that tick's frame before it reaches the mapping (A4-L6).
            self.mailbox.set_publish_guard(self._check_admission)
        # Closed before the manager shuts down (LIFO): capture fenced and released on its lane, the compute lane
        # stopped, then the manager joins both.
        self._stack.callback(engine.force_stop)
        # The mode's demands are rules of the mode, which the tick declares before every engine step; capture needs
        # them before the first block arrives (the history accumulates in the capture callback).
        declare_mode_engine_demands(engine, mode)

    @property
    def device_refused(self) -> bool:
        """Whether this session's engine refuses an audio device (the gates assert it in the worker)."""
        return bool(getattr(self._engine, "capture_devices_refused", False))

    def _admit_analysis(self) -> None:
        """The compute lane's admission gate (production order): an analysis waits until the tick has read."""
        if not self._admission.wait(self.LIVE_EDGE_TIMEOUT_S):
            self._admission_failed = True

    def _check_admission(self) -> None:
        """The mailbox's publish guard (production order): a tick whose analysis outwaited the admission gate ran
        in an unheld order, so its frame never reaches the mapping (fail closed before the publish)."""
        if self._admission_failed:
            raise RuntimeError("an analysis waited too long at the admission gate")

    def _open_capture(self, config: Any) -> Any:
        """The audio worker's capture source (its factory seam): a recorded backend, opened on the capture lane. A
        worker-paced session's source restarts its audio clock at every open (no burst for a closed gap)."""
        from core.visualizer_engine.recorded_capture import RecordedCaptureBackend

        on_started = (lambda _backend: self._source.rebase()) if self._paced else None
        self._backend = RecordedCaptureBackend(config, on_started=on_started)
        self._backends.append(self._backend)
        return self._backend

    @property
    def capture_counts(self) -> tuple[int, int]:
        """(opens, restarts) of the recorded capture source so far (reported by the gates, never gated)."""
        return len(self._backends), sum(backend.restarts for backend in self._backends)

    # ------------------------------------------------------------------------------------- live control edges
    # Each is the production owner's own sequence (``logical_edges``, shared with ``quick_display_visualizer_owner``;
    # ``tests/test_visualizer_logical_edges_parity.py`` compares the engine call logs); capture (re)opens and closes
    # asynchronously on its lane, so every edge ends on the lane's completion edge.

    def _settle_capture(self) -> None:
        """Wait until every capture start/stop/restart admitted so far has run on the capture lane (the lane's own
        completion edge: bounded, fail closed; never a sleep or poll), then check capture is open iff it should be."""
        import threading

        done = threading.Event()
        if self._engine.fence_capture_transactions(done.set) and not done.wait(self.LIVE_EDGE_TIMEOUT_S):
            raise RuntimeError("the live engine's capture lane never settled")
        backend = self._backend
        should_run = self._live_started and self._display_on and self._controller.playing
        if should_run and (backend is None or not backend.is_running()):
            raise RuntimeError("the live engine's capture never opened")

    def _start_playback(self, playing: bool) -> None:
        """The host binding's start at the first input: Media's state as the owner's ``set_playing`` edge (configure
        left it not playing), then the owner's ``start``: the engine bound to the session's ``ThreadManager``, the
        engine reference, Media's state committed with no edge, the cold capture admission when playing, and, when
        the displays are off, the reference released again (the runtime starts parked)."""
        from widgets.spotify_visualizer.logical_edges import (
            admit_engine_start, apply_playback_edge, prepare_engine_start, release_engine_started_parked,
        )

        controller = self._controller
        apply_playback_edge(controller, playing, started=False)
        engine = prepare_engine_start(controller)
        admit_engine_start(controller, engine, on_acquired=self._on_engine_acquired)
        self._live_started = True
        if self._paced:
            self._start_cadence()            # the owner's ``_start_logical_runtime`` (parked if the displays are off)
        if release_engine_started_parked(engine, display_on=self._display_on, engine_acquired=self._engine_acquired):
            self._engine_acquired = False
            self._released_for_display_power = True
        self._settle_capture()

    # ------------------------------------------------------------------------------- worker-paced (slice 5.1)

    def start(self, playing: bool) -> None:
        """A worker-paced session's start (``VIS_START``): the host binding's play edge and the owner's ``start``,
        which starts the session's own cadence. Input-paced sessions start at their first input."""
        if not self._live or not self._paced:
            raise ValueError("only a worker-paced session is started explicitly (input-paced ones start at an input)")
        if self._live_started:
            raise RuntimeError("the session has already started")
        self._start_playback(playing)

    def set_playing(self, playing: bool) -> None:
        """Media's play edge on a worker-paced session (``VIS_SET_PLAYING``), applied at once as the owner applies it
        on the GUI thread while its cadence runs (an input-paced session takes play edges from its inputs)."""
        if not self._live or not self._paced:
            raise ValueError("play edges reach an input-paced session through its inputs")
        if bool(playing) != bool(self._controller.playing):
            self._set_playing(playing)

    def _start_cadence(self) -> None:
        from widgets.spotify_visualizer.logical_edges import start_logical_cadence

        start_logical_cadence(self._controller, interval_s=self._interval_s, step=self._paced_step)

    def _paced_step(self, deadline_ts: float) -> None:
        """One cadence edge (the cadence thread): the audio the clock produced since the previous edge goes through
        the capture callback, then the tick (its own engine step consumes the newest block and submits the analysis,
        which commits on the compute lane while the tick reads the previous commit, as live). A step that raised
        fails the session closed: nothing more is ticked or published (the owner's fade and reconfigure are slice
        5.5)."""
        from widgets.spotify_visualizer.tick_pipeline import logical_tick

        if self._paced_failure is not None:
            return
        try:
            backend, controller = self._backend, self._controller
            if backend is not None:
                if backend.sample_rate != self._source.sample_rate:
                    raise ValueError(f"recorded rate {self._source.sample_rate} != capture rate "
                                     f"{backend.sample_rate}")
                running = backend.is_running() and controller.playing
                for block in self._source.due(deadline_ts, backend.block_size, running=running):
                    backend.offer(block)
            logical_tick(controller.logical_tick_state)
        except (Exception, SnapshotContractError) as exc:
            self._paced_failure = f"{type(exc).__name__}: {exc}"
            self._paced_failed.set()

    def _stop_cadence(self) -> None:
        """Stop and join the session's cadence (idempotent), keeping its final accounting."""
        runtime = self._controller.logical_runtime
        if runtime is None:
            return
        if not self._controller.stop_logical_runtime():
            raise RuntimeError("the session's cadence did not join")
        self._cadence_record = runtime.describe()

    def finish(self) -> dict:
        """Stop the cadence, then report (``VIS_STOP``'s reply): the frames published, the cadence's accounting (steps,
        skipped deadlines, step failures), the audio the source paced, a failure that closed the session."""
        if self._paced:
            self._stop_cadence()
        report: dict = {"revision": self.mailbox.revision}
        if self._paced:
            report.update(cadence=self._cadence_record, audio=self._source.describe(), failure=self._paced_failure,
                          capture=self.capture_counts)
        return report

    def _on_engine_acquired(self) -> None:
        self._engine_acquired = True
        self._released_for_display_power = False

    def _set_playing(self, active: bool) -> None:
        """A playback edge: the owner's ``set_playing`` (``logical_edges.apply_playback_edge``)."""
        from widgets.spotify_visualizer.logical_edges import apply_playback_edge

        apply_playback_edge(self._controller, active, started=self._live_started)
        self._settle_capture()

    def set_display_power(self, on: bool) -> bool:
        """Display power (park/unpark), the owner's ``set_display_power`` logical side (``logical_edges``): park parks
        the cadence and releases the engine reference (capture stops) and no input ticks while parked; unpark
        re-acquires it, reopens capture when playing, arms the warm re-entry fence and rebases the logical clocks while
        the cadence is still parked, then unparks it. The owner's reader-side mailbox clear stays the main process's.
        Whether anything changed."""
        from widgets.spotify_visualizer.logical_edges import park_logical_side, unpark_logical_side

        if not self._live:
            raise ValueError("display power is a live-session control")
        on = bool(on)
        if on == self._display_on:
            return False
        self._display_on = on
        controller = self._controller
        if not on:
            if park_logical_side(controller, engine_acquired=self._engine_acquired):
                self._engine_acquired = False
                self._released_for_display_power = True
        else:
            unpark_logical_side(controller, started=self._live_started,
                                released_for_display_power=self._released_for_display_power,
                                on_reacquired=self._on_engine_acquired)
        self._settle_capture()
        return True

    def request_mode(self, mode: str, *, preset: int = 0, settings: Any = None) -> None:
        """An in-session activation, applied at the next tick boundary (the newest request wins): the owner's
        activation commit (``logical_edges.commit_logical_activation``) on the existing engine and controller, never a
        rebuild. Another mode is a mode activation; the current mode with its ``preset`` / ``settings`` is the
        owner's same-mode preset activation (A4-M3: never dropped)."""
        from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
        from core.visualizer_engine.packet_abi import mode_code

        if not self._live:
            raise ValueError("an in-session mode switch is a live-session control")
        get_visualizer_mode_descriptor(mode)
        mode_code(mode)                                   # a mode the header cannot name fails here, not mid-tick
        self._pending_mode = (str(mode), int(preset), settings)
        if self._paced:
            # The owner's activation stops its runtime (the tick boundary), commits and restarts it: at once, as the
            # owner does on the GUI thread.
            self._apply_pending_mode()

    def _apply_pending_mode(self) -> None:
        from widgets.spotify_visualizer.feature_replay import offline_activation_request
        from widgets.spotify_visualizer.logical_edges import commit_logical_activation

        if self._pending_mode is None:
            return
        mode, preset, settings = self._pending_mode
        self._pending_mode = None
        controller = self._controller
        generation, activation_id = commit_logical_activation(
            controller, kind="preset" if mode == self.mode else "mode", target=mode,
            **offline_activation_request(mode, preset, None, settings),
        )
        # Render admission for the committed identity (the owner binds it into its scene).
        controller.begin_render_activation(engine_generation=generation, activation_id=activation_id)
        self.mode = mode
        if self._paced and self._live_started:
            self._start_cadence()            # the owner restarts its runtime after the bind
        # The target's block size may differ: capture restarts on its lane before the next block.
        self._settle_capture()

    def _tick_live(self, feature: Any) -> None:
        """At the tick boundary: a pending mode switch, then the input's playback edge. Playing: push the input's new
        PCM through the capture callback, step the engine (it consumes the newest block and submits it to the
        compute lane) and wait for that analysis to commit (the engine's settled edge) before the tick. Paused: the
        tick's own engine step runs the paused path (idle waveform/bars, the warm-capture grace)."""
        if not self._display_on:
            raise RuntimeError("a parked session does not tick (its cadence is parked)")
        engine = self._engine
        self._apply_pending_mode()
        if not self._live_started:
            self._start_playback(feature.playing)
        elif bool(feature.playing) != bool(self._controller.playing):
            self._set_playing(feature.playing)
        backend = self._backend
        history = feature.capture_history
        if not feature.playing:
            # The recorder records no new publication while paused (the paused engine consumes no capture); a
            # paused input that carries one is outside the rig's contract.
            if history is not None and self._stream.blocks(history, feature.timestamp_us, 1):
                raise ValueError("a paused input carries a new capture publication")
            return
        if history is not None and history.sample_rate != backend.sample_rate:
            raise ValueError(f"recorded rate {history.sample_rate} != capture rate {backend.sample_rate}")
        for block in self._stream.blocks(history, feature.timestamp_us, backend.block_size):
            backend.push(block)
        if self.order == "settled":
            from widgets.spotify_visualizer.tick_pipeline import declare_mode_engine_demands

            # The step the tick would take, taken first (with the tick's own demand declarations) so the tick reads
            # the commit of the block it was fed; the tick's step then finds no new block.
            declare_mode_engine_demands(engine, self.mode)
            self._settled.clear()
            engine.tick()
            self._wait_settled()

    def _wait_settled(self) -> None:
        if self._engine.has_analysis_in_flight() and not self._settled.wait(self.LIVE_EDGE_TIMEOUT_S):
            raise RuntimeError("the live engine's analysis never settled")

    def _logical_tick_live(self) -> Any:
        """The tick, in the session's commit order (``ORDERS``)."""
        from widgets.spotify_visualizer.tick_pipeline import logical_tick

        if self.order != "production":
            return logical_tick(self._controller.logical_tick_state)
        self._settled.clear()
        self._admission.clear()
        try:
            frame = logical_tick(self._controller.logical_tick_state)   # the publish guard checks admission first
        finally:
            self._admission.set()
        self._wait_settled()
        self._check_admission()             # an analysis that failed after the publish fails the next edge here
        return frame

    @property
    def clock(self) -> list:
        """The session's authored clock cell (in-process gates step their main-side engine on it)."""
        return self._clock

    def tick_snapshot(self, snapshot: Any) -> int:
        """Run the tick on one live input (an engine snapshot); the mailbox revision after it."""
        from widgets.spotify_visualizer.tick_pipeline import logical_tick

        if self.inputs != "snapshot":
            raise ValueError("this session ticks recorded inputs")
        self._clock[0] = snapshot.timestamp
        self._controller.playing = snapshot.playing
        self._engine.accept_snapshot(snapshot)
        if logical_tick(self._controller.logical_tick_state) is None:
            raise RuntimeError("the tick produced no logical frame")
        return self.mailbox.revision

    def tick(self, feature: Any) -> int:
        """Accept one post-DSP input, run the tick, publish its frame; the mailbox revision after it."""
        from widgets.spotify_visualizer.tick_pipeline import logical_tick

        if self.inputs == "snapshot":
            raise ValueError("this session ticks engine snapshots")
        if self._paced:
            raise ValueError("a worker-paced session ticks on its own cadence")
        self._clock[0] = feature.timestamp_us / 1_000_000.0
        if self._live:
            self._tick_live(feature)      # playback edges are the owner's, applied at the boundary
            if self._logical_tick_live() is None:
                raise RuntimeError("the tick produced no logical frame")
            return self.mailbox.revision
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
                return self._reply(msg, qt_modules=qt, device_refused=self._session.device_refused)
            if msg.msg_type == MessageType.VIS_INPUT:
                if self._session is None:
                    return self._reply(msg, success=False, error="no engine session is configured")
                try:
                    if "snapshot" in msg.payload:
                        revision = self._session.tick_snapshot(msg.payload["snapshot"])
                    else:
                        revision = self._session.tick(msg.payload["frame"])
                except (Exception, SnapshotContractError) as exc:
                    # Fail closed (audit M2): a tick that raised left its controller half-updated, so the session
                    # ends; the owner treats it as a worker crash (fade, reconfigure once).
                    self._close_session()
                    return self._reply(msg, success=False, error=f"{type(exc).__name__}: {exc}", session_closed=True)
                return self._reply(msg, revision=revision)
            if msg.msg_type in (MessageType.VIS_SET_MODE, MessageType.VIS_SET_DISPLAY_POWER, MessageType.VIS_START,
                                MessageType.VIS_SET_PLAYING):
                if self._session is None:
                    return self._reply(msg, success=False, error="no engine session is configured")
                if msg.msg_type in (MessageType.VIS_START, MessageType.VIS_SET_PLAYING):
                    session = self._session
                    try:
                        if msg.msg_type == MessageType.VIS_START:
                            session.start(bool(msg.payload["playing"]))
                        else:
                            session.set_playing(bool(msg.payload["playing"]))
                    except (Exception, SnapshotContractError) as exc:
                        self._close_session()       # the edge may have half-applied: fail closed
                        return self._reply(msg, success=False, error=f"{type(exc).__name__}: {exc}",
                                           session_closed=True)
                    return self._reply(msg)
                if msg.msg_type == MessageType.VIS_SET_MODE:
                    # Validated now, applied at the session's next tick boundary (the newest request wins).
                    payload = dict(msg.payload)
                    self._session.request_mode(payload.pop("mode"), **payload)
                    return self._reply(msg)
                try:
                    changed = self._session.set_display_power(bool(msg.payload["on"]))
                except (Exception, SnapshotContractError) as exc:
                    # The edge may have half-applied (capture reference, fence): fail closed, as a tick does.
                    self._close_session()
                    return self._reply(msg, success=False, error=f"{type(exc).__name__}: {exc}", session_closed=True)
                return self._reply(msg, changed=changed)
            if msg.msg_type == MessageType.VIS_STOP:
                report = self._session.finish() if self._session is not None else None
                self._close_session()
                # The Qt modules the process has loaded so far (the fresh-spawn probe reads them at spawn too).
                return self._reply(msg, report=report, qt_modules=sorted(name for name in sys.modules
                                                                         if name.startswith("PySide6.Qt")))
        except (Exception, SnapshotContractError) as exc:   # reported to the owner, never a silent worker death
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
