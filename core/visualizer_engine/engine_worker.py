"""The visualizer engine worker (native core P2, work order 4: P2a's tick out of process).

``EngineSession`` hosts one activation's logical tick and mode runtime exactly as the main process does today: the
runtime controller with its tick state, configured on the logical side only, a post-DSP input engine fed one input
per tick, and the logical mailbox replaced by the writer side of the frame packet ABI (``PacketMailbox``), so every
tick lands in the shared mapping the main process owns and reads. ``VisualizerEngineWorker`` runs sessions in a
``WorkerType.VISUALIZER`` process under ``ProcessSupervisor`` (control messages only: configure, input, stop).

A session ticks recorded post-DSP inputs (``FeatureFrame``, the replay schema the live engine records), one
acknowledged input per tick, which is what the identity gates need: the worker's frames equal the in-process tick's
for every mode (``tests/test_visualizer_engine_worker.py``). P2b's rig and product path
(``inputs="live"``) runs the production ``_SpotifyBeatEngine`` itself, with its real audio worker, capture lane and
compute pool, fed the recordings' PCM through the capture callback (``recorded_capture``;
``tests/test_visualizer_engine_live.py``). Every session configures through the production owner's own
configuration (``logical_edges.configure_logical_controller``, then the owner's bind: render admission for the
configured identity; checkpoint audit 5, A5-M2), never a replay copy. Production wiring (park, crash fail-closed) is work
order 5; its first slice (5.1) is built: a ``cadence="worker"``
live session ticks on its own clock, the logical runtime's own cadence (``VisualizerLogicalRuntime``, started through
``logical_edges.start_logical_cadence`` as the owner starts it), fed a recorded PCM stream paced on the audio clock at
the cadence's edges (``recorded_capture.PacedPcmSource``), and its frames reach the reader through the same mailbox
and wake (``tests/test_visualizer_engine_paced.py``). Slice 5.2 runs the production owner on it
(``widgets/spotify_visualizer/engine_worker_link.py``): the session is configured with the host binding's own resolved
activation (``activation``: settings model, resolved activation, technical cache, logical and presentation kwargs),
started, played, parked and switched by the owner's control edges, and in production (no ``pcm``) its engine opens the
real loopback device through the normal capture path on its own capture lane (slice 5.3's core); a capture that fails to
open is a device failure (slice 5.5, A7-L4): the session keeps running and retries it at the next capture edge; a
capture that stops publishing while Media plays (a default-output switch, an unplugged or stale device) is reopened once
on the current default output by the session's delivery watch, a count on its cadence step (slice 5.3's rest).
Imports and every configuration load QtCore only (the presentation config the tick reads is Qt-free since slice 5.4;
A5-L2), and the owner forwards the presentation inputs it changes at runtime (``VIS_SET_VIEW``).
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

    #: ``feature``: recorded post-DSP inputs (``FeatureFrame``) through ``ReplayBeatEngine`` (the replay contract).
    #: ``lanes``: the same inputs through production DSP on their native PCM (``ProductionLaneEngine``), the
    #: in-process reference on production DSP (the Studios' replay). ``live`` (P2b, the product path): the
    #: production ``_SpotifyBeatEngine`` with its real audio worker, capture lane and compute pool on the session's
    #: own ``ThreadManager``, fed each ``FeatureFrame``'s native PCM through the capture callback
    #: (``recorded_capture.RecordedCaptureBackend``; a device is refused for the session's life); ``order`` decides
    #: when the asynchronous commit lands relative to the tick (``ORDERS``).
    INPUTS = ("feature", "lanes", "live")

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
    #: cadence edge (``recorded_capture.PacedPcmSource``), or, with no ``pcm`` (production, work order 5 slice 5.3),
    #: from the loopback device the engine's audio worker opens through the normal capture path on its capture lane;
    #: frames go out through the mailbox and wake as always, and a reader that stalls only coalesces (latest wins in
    #: the ABI). The authored clock is the process's own.
    CADENCES = ("input", "worker")

    #: How long a live session waits for its own capture to open or its analysis to settle before failing closed.
    LIVE_EDGE_TIMEOUT_S = 30.0

    #: A worker-paced session whose steps keep failing fails closed (work order 5 slice 5.7, A6-M3's open half): after
    #: this many consecutive failed steps (about 0.67 s at the 90 Hz cadence; a step that succeeds resets the count), it
    #: parks its cadence, ends its wake pipe (the owner sees the session's end as an event and recovers: hold, fade,
    #: reconfigure once) and answers any later edge with ``session_closed``. A transient failure is still the runtime's
    #: retry, as in process. A count of steps, never a timer.
    FAILED_STEPS_BEFORE_CLOSE = 60

    #: A worker-paced session whose cadence thread is blocked inside a step (a lock, a native call) fails closed too
    #: (phase-boundary audit L4): the process's message loop still answers the supervisor's heartbeat, so nothing else
    #: sees it, and the Visualizer would stay frozen on its last frame for the run. The worker's heartbeat handler asks
    #: the session (``watch_cadence_liveness``): after this many consecutive heartbeats, each at least
    #: ``STALL_OBSERVATION_MIN_S`` after the one before (heartbeats that queued behind a long control edge arrive
    #: together and count once), with the cadence running, not parked and not one step further, the session fails
    #: closed as above. The heartbeat is the supervisor's own (3 s): no timer, thread or polling of the session's.
    STALLED_HEARTBEATS_BEFORE_CLOSE = 2
    STALL_OBSERVATION_MIN_S = 1.0

    # Defaults (a recorded session configured from the offline request); ``_construct`` owns the instance values.
    _activation: Any = None
    _device = False
    _capture_failed = False
    _failed: str | None = None
    _failed_steps = 0
    _liveness_seen: tuple | None = None
    _stalled_heartbeats = 0

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
                 seed: int | None = None, order: str = "production",
                 cadence: str = "input", pcm: Any = None, pcm_rate: int | None = None,
                 interval_s: float | None = None, activation: Any = None, publish_stamps: bool = False,
                 payload: str = "codec") -> None:
        from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
        from core.visualizer_engine.packet_mailbox import PacketMailbox
        from widgets.spotify_visualizer import extruded_bubble_drift_log
        from widgets.spotify_visualizer.feature_replay import (
            REPLAY_SEED, PcmReanalysis, ProductionLaneEngine, ReplayBeatEngine, deterministic_clock,
        )
        from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

        if not 0 <= int(label_namespace) < (1 << 30):
            raise ValueError(f"label namespace out of range: {label_namespace}")
        if inputs not in self.INPUTS:
            raise ValueError(f"unknown session inputs {inputs!r}")
        if order not in self.ORDERS:
            raise ValueError(f"unknown live commit order {order!r}")
        if cadence not in self.CADENCES:
            raise ValueError(f"unknown cadence {cadence!r}")
        if (cadence == "worker" and (inputs != "live" or order != "free")) or (
                pcm is not None and (cadence != "worker" or not pcm_rate)):
            raise ValueError("a worker-paced session is a live session in free order fed a recorded PCM stream or "
                             "the device")
        self.inputs = inputs
        self.order = order
        self.cadence = cadence
        self._paced = cadence == "worker"
        # Production (work order 5 slice 5.3): a worker-paced session with no recorded stream opens the loopback
        # device through the audio worker's normal capture path (no capture factory installed, no refusal).
        self._device = self._paced and pcm is None
        self._capture_failed = False
        # The host binding's own resolved activation (slice 5.2, checkpoint audit 6 A6-L4): settings model, resolved
        # activation, technical cache, logical and presentation kwargs. None: the offline request (the gates).
        self._activation = dict(activation) if activation is not None else None
        self._stack = contextlib.ExitStack()
        # The session's authored clock follows its inputs' own timestamps (each input carries the time it was
        # produced), so the worker ticks the same frames whatever its scheduling. Live sessions pin only
        # the authored clock: ``time.*`` stays the process's own (audit H6), so a tick that read a wall clock would
        # fail the identity gates instead of being pinned equal. Recorded-input sessions are replays and keep the
        # replay harness's clock pin. No session seeds the process RNG (work order 5 slice 5.6): Bubble's spawn
        # draws from its simulation's own generator, which ``seed`` (a control input) seeds through the controller
        # (``seed_mode_generators``); production passes none (OS entropy, as in process), the identity gates pass
        # the replay seed, and recorded-input sessions are seeded with it by default, as every offline replay is. A
        # new process-RNG draw in the tick is therefore unseeded and fails the gates (checkpoint audit 2, A2-M2).
        if inputs == "live":
            from core.authored_clock import pinned_authored_clock

            self._clock = [0.0]
            if not self._paced:                # a worker-paced session runs on the process's own clocks
                self._stack.enter_context(pinned_authored_clock(lambda: self._clock[0]))
        else:
            self._clock = self._stack.enter_context(deterministic_clock())
            if seed is None:
                seed = REPLAY_SEED
        # Extruded Bubble's drift-family revisions are the renderer's geometry cache identity, so no two sessions may
        # reuse one: the main process gives every session its own ``label_namespace`` (>= 1, never repeated), and its
        # revisions start at ``namespace << 32`` (the main process's own counter stays far below). Namespace 0 numbers
        # from 1, as a fresh in-process replay does (the identity gates).
        extruded_bubble_drift_log._REVISIONS = itertools.count((int(label_namespace) << 32) + 1)
        # ``wake``: the writer end of the owner's wake pipe (one byte per publish; the owner's emitter coalesces), or
        # on POSIX the pipe's name, which the session opens itself (``wake_channel``: no descriptor crosses the
        # control channel there, so none can be left behind by a worker that dies before decoding its configure).
        # ``publish_stamps``: the owner's ``--frame-trace`` is admitted, so every slot carries its publish time (the
        # main side's trace records the publish from it; gate 3). Off: the slot carries 0 and no clock is read.
        # ``payload``: what the stream carries (``PacketMailbox``): the tagged codec (production, the main process's
        # Python reader) or the mode's native schema (native core N2.3; nothing in the product configures it yet: a
        # Python codec reader refuses such a stream at its first slot head, the refusal tests' real-worker case).
        from core.visualizer_engine.wake_channel import open_wake_sender

        wake_sender = open_wake_sender(wake)
        try:
            self.mailbox = PacketMailbox(role="writer", attach=mapping, wake_sender=wake_sender,
                                         publish_stamps=bool(publish_stamps), payload=payload)
        except BaseException:
            if wake_sender is not None and wake_sender is not wake:
                wake_sender.close()               # opened here by name, and the mailbox never took it
            raise
        self._stack.callback(self.mailbox.close)
        self._live = inputs == "live"
        if self._live:
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

                self._source = PacedPcmSource(pcm, int(pcm_rate)) if pcm is not None else None
                self._interval_s = interval_s
                self._cadence_record: dict | None = None
                self._cadence_started_ts = 0.0        # the current runtime's start (perf_counter)
                self._cadence_s = 0.0                 # the last stopped runtime's run time
                # What reached the engine (checkpoint audit 6, A6-M1): blocks handed to the capture callback, the
                # blocks the audio worker's callback published into the engine's audio buffer, and the engine's
                # analysis commits since the cadence first started.
                self._offered_blocks = 0
                self._accepted_blocks = 0
                self._accepted_samples = 0
                self._commits_at_start: int | None = None
        else:
            engine = (ProductionLaneEngine if inputs == "lanes" else ReplayBeatEngine)(bar_count)
        # The main process's runtime generation (a control input: every frame carries it).
        controller = VisualizerRuntimeController(runtime_generation=int(runtime_generation), initial_mode=mode,
                                                 engine_factory=lambda _count: engine)
        controller.engine = engine
        if seed is not None:
            controller.seed_mode_generators(int(seed))   # before the configuration builds the mode's state
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
        config (Spectrum's decoration fades and colours, the Oscilloscope/Bubble spec parameters, the 3D view), held
        Qt-free since work order 5 slice 5.4, so this loads QtCore only (A5-L2); the owner keeps it current with
        ``VIS_SET_VIEW``'s presentation inputs."""
        from widgets.spotify_visualizer.feature_replay import offline_activation_request
        from widgets.spotify_visualizer.logical_edges import configure_logical_controller
        from widgets.spotify_visualizer.technical_config import resolve_technical_config

        controller, engine = self._controller, self._engine
        request = (self._activation if self._activation is not None
                   else offline_activation_request(controller.mode_id, preset, None, settings))
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
        if not self._device:
            self._engine.refuse_capture_devices()
        manager = ThreadManager()
        self._stack.callback(manager.shutdown, wait=True, timeout=self.LIVE_EDGE_TIMEOUT_S)
        return manager

    def _wire_live_engine(self, mode: str) -> None:
        """Wire the configured engine: the recorded capture source, the commit observers; the owner's ``start``
        (engine reference, playback commit, cold capture) runs at the first input."""
        from widgets.spotify_visualizer.tick_pipeline import declare_mode_engine_demands

        engine = self._engine
        if not self._device:
            # A recorded source; the production session leaves the factory unset (the device path).
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

    @property
    def identity(self) -> tuple[int, int]:
        """The engine's current (generation, activation id): the owner binds render admission for it (the configure
        and an applied mode request reply with it)."""
        return int(self._engine.get_generation_id()), int(self._engine.get_activation_id())

    @property
    def capture_failed(self) -> bool:
        return self._capture_failed

    # ------------------------------------------------------------- the device's delivery (slice 5.3, the rest)

    #: A device session whose capture publishes nothing into the engine for this many consecutive cadence steps while
    #: Media says playing reopens the device once (about 2 s at the 90 Hz cadence; a count on the cadence's own edge, as
    #: ``FAILED_STEPS_BEFORE_CLOSE`` is, never a timer). A WASAPI loopback stream delivers nothing while nothing renders
    #: to its endpoint, so a stream whose player moved to a new default output, an unplugged (invalidated) device and a
    #: device that went stale all look alike from here: no callbacks at all. Digital silence is not that: a playing
    #: silent passage still renders zeros, which arrive and are published, so it never counts. Twice the stream's own
    #: first-callback grace, so a stream that is still opening (or a player still buffering after its play edge) is not
    #: bounced; the reopen itself also waits until the audio worker calls the stream stale.
    SILENT_CAPTURE_STEPS_BEFORE_REOPEN = 180

    _capture_edges = 0          # capture edges handled (start, play, display power, activation): each re-arms the watch
    _capture_reopens = 0        # the watch's reopens
    _capture_resumed = 0        # reopens after which the device published again
    _delivery_seen = -1         # the engine's capture publications at the watch's previous step
    _delivery_edges = -1        # the capture edges at the watch's previous step
    _silent_steps = 0           # consecutive playing steps with no new publication
    _delivery_latched = False   # this silent run has had its one reopen (or found capture not open)
    _delivery_reopened = False  # ... and it was a reopen (the next publication is the device delivering again)

    @property
    def capture_reopens(self) -> int:
        return self._capture_reopens

    def device_report(self) -> dict:
        """The session's device state, carried in every reply that reports capture (``capture_failed``: the device is
        not open, A7-L4; ``capture_reopens`` / ``capture_resumed``: the delivery watch's reopens, and those after which
        the device published again). The main side logs it when it changes (``engine_worker_link``): the worker
        process's own log lines never reach the main log."""
        return {"capture_failed": self._capture_failed, "capture_reopens": self._capture_reopens,
                "capture_resumed": self._capture_resumed}

    def _watch_device_delivery(self) -> None:
        """The cadence thread, every step of a device session (work order 5 slice 5.3): a capture that publishes nothing
        for ``SILENT_CAPTURE_STEPS_BEFORE_REOPEN`` consecutive steps while Media says playing is reopened once, on its
        capture lane, through the audio worker's own restart (the one Media's play edge makes for a stale capture in
        process: ``_SpotifyBeatEngine.restart_stale_capture``): the stream reopens on the current default output, so the
        capture follows a default-device switch, an unplugged device or a stale stream without waiting for Media's next
        play edge. One reopen per silent run: the run ends when the device publishes again (logged as resumed) or at a
        capture edge (Media's play edge, display power, an activation; each re-arms it), never by retrying. A reopen
        that fails is a device failure (A7-L4: ``capture_failed``, the session keeps running, the next capture edge
        retries); a capture that is not open at all is left to that path. Reads one counter per step (the engine's
        capture publications); never raises into the step (a device problem is never a step failure)."""
        try:
            engine = self._engine
            published = engine.capture_publications()
            edges = self._capture_edges
            if published != self._delivery_seen or edges != self._delivery_edges or not self._controller.playing:
                if self._delivery_reopened and published > self._delivery_seen and edges == self._delivery_edges:
                    self._capture_resumed += 1
                    _log().info("[SPOTIFY_VIS][ENGINE_WORKER] The loopback device publishes again after its reopen")
                self._delivery_seen, self._delivery_edges = published, edges
                self._silent_steps = 0
                self._delivery_latched = self._delivery_reopened = False
                return
            if self._delivery_latched:
                return
            self._silent_steps += 1
            if self._silent_steps < self.SILENT_CAPTURE_STEPS_BEFORE_REOPEN:
                return
            if not engine.is_capture_running():
                self._delivery_latched = True     # not open: a device failure (A7-L4), retried at the next capture edge
                return
            admitted = engine.restart_stale_capture()
            if admitted is None:
                return                            # not stale yet by the stream's own clock (its first-callback grace)
            self._delivery_latched = True
            if not admitted:
                _log().error("[SPOTIFY_VIS][ENGINE_WORKER] The loopback device published nothing for %d steps while "
                             "playing, and its capture lane refused the reopen", self._silent_steps)
                return
            self._delivery_reopened = True
            self._capture_reopens += 1
            _log().warning("[SPOTIFY_VIS][ENGINE_WORKER] The loopback device published nothing for %d steps while "
                           "playing; reopened it on the current default output (reopen %d)", self._silent_steps,
                           self._capture_reopens)
            self._watch_device_capture()          # a reopen that fails is reported as a device failure
        except Exception:
            self._delivery_latched = True
            _log().exception("[SPOTIFY_VIS][ENGINE_WORKER] The loopback device's delivery watch failed")

    @property
    def mapping_name(self) -> str:
        """The frame mapping this session writes (a stop addressed to another mapping leaves it alone)."""
        return self.mailbox.mapping_name

    def _watch_device_capture(self) -> None:
        """The device session's capture check (work order 5 slice 5.3): never a wait on the device (a driver can take
        its time to open, as in process, where the GUI never waits on it either). A check is queued behind every
        capture transaction admitted so far on the capture lane (where the device opens, COM included); if capture
        should be open by then and is not, the open failed, and the session reports it; one that is open again clears
        the report (a later edge reopened it)."""
        engine = self._engine

        def check() -> None:
            should_run = self._live_started and self._display_on and self._controller.playing
            running = engine.is_capture_running()
            if should_run and not running:
                if not self._capture_failed:
                    self._report_capture_failure()
            elif running and self._capture_failed:
                import logging

                self._capture_failed = False
                logging.getLogger(__name__).info("[SPOTIFY_VIS][ENGINE_WORKER] The loopback device opened again")

        engine.fence_capture_transactions(check)

    def _report_capture_failure(self) -> None:
        """The device did not open (slice 5.5, checkpoint audit 7 A7-L4): a device failure, not a worker failure. The
        session keeps running (frames go on: the engine's idle path, as in process when the device is unavailable),
        logs it once per run of failures and reports it in its later replies (``capture_failed``); the next edge that
        opens capture (Media's play edge, an unpark, an activation) retries the device through the audio worker's
        normal path. Counting it as a worker failure would fade and reconfigure onto the same device, and a second
        transient unavailability would end the worker for the run."""
        import logging

        self._capture_failed = True
        logging.getLogger(__name__).error(
            "[SPOTIFY_VIS][ENGINE_WORKER] The loopback device did not open; the session keeps running and retries it "
            "at the next capture edge")

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

        if self._device:
            self._capture_edges += 1          # a capture edge re-arms the delivery watch (slice 5.3)
            self._watch_device_capture()
            return
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
        """A live session's explicit start (``VIS_START``): the host binding's play edge and the owner's ``start``,
        which starts a worker-paced session's own cadence. An input-paced session not started explicitly starts at its
        first input (the gates); the production owner's identity gate starts it explicitly, as the owner does."""
        if not self._live:
            raise ValueError("only a live session is started explicitly")
        if self._live_started:
            raise RuntimeError("the session has already started")
        self._start_playback(playing)

    def set_playing(self, playing: bool) -> None:
        """Media's play edge (``VIS_SET_PLAYING``), applied at once as the owner applies it on the GUI thread. An
        input-paced session also takes play edges from its inputs (an input whose state already holds adds none)."""
        if not self._live:
            raise ValueError("play edges are a live-session control")
        if bool(playing) != bool(self._controller.playing):
            self._set_playing(playing)

    def _start_cadence(self) -> None:
        import time

        from widgets.spotify_visualizer.logical_edges import start_logical_cadence

        if self._commits_at_start is None:
            self._commits_at_start = int(self._engine.get_authoritative_frame_commit_seq())
        self._cadence_started_ts = time.perf_counter()
        start_logical_cadence(self._controller, interval_s=self._interval_s, step=self._paced_step)

    def _paced_step(self, now: float) -> None:
        """One cadence edge (the cadence thread; ``now`` is the runtime's wake time, the ``perf_counter`` read just
        before the step, not its deadline): the audio the clock produced since the previous edge goes through the
        capture callback, then the tick (its own engine step consumes the newest block and submits the analysis,
        which commits on the compute lane while the tick reads the previous commit, as live). The blocks the audio
        worker's callback actually published into the engine are counted (A6-M1).

        A step that raises is the cadence owner's, exactly as in process (checkpoint audit 6, A6-M3): it propagates,
        so ``VisualizerLogicalRuntime`` logs it (once per run of failures), counts it in its ``step_failures`` and the
        next step retries. Here it is also counted as a run: ``FAILED_STEPS_BEFORE_CLOSE`` consecutive failures fail
        the session closed (slice 5.7: ``_fail_closed``), since a session that keeps failing publishes nothing and
        would leave the Visualizer frozen on its last frame."""
        if self._failed is not None:
            return                       # failed closed: the cadence parks at its next turn
        try:
            self._paced_step_body(now)
        except Exception as exc:
            from core.visualizer_engine.packet_abi import FrameCapacityError

            if isinstance(exc, FrameCapacityError):
                self._fail_closed(f"frame capacity violation: {exc}")
                raise
            self._failed_steps += 1
            if self._failed_steps >= self.FAILED_STEPS_BEFORE_CLOSE:
                self._fail_closed(f"{self._failed_steps} consecutive steps failed (last: {type(exc).__name__}: {exc})")
            raise
        self._failed_steps = 0

    @property
    def failed(self) -> str | None:
        """Why the session failed closed on its own (``_fail_closed``), or None."""
        return self._failed

    def watch_cadence_liveness(self, now: float | None = None) -> bool:
        """The message thread, at each of the supervisor's heartbeats (``VisualizerEngineWorker._handle_heartbeat``):
        whether the session failed closed here because its cadence thread stopped stepping
        (``STALLED_HEARTBEATS_BEFORE_CLOSE``). Reads the runtime's step count, nothing else: no lock the cadence
        thread could hold, no wait. A parked cadence (display power, a session already failed closed), one stopped
        for an activation commit and an input-paced session are not watched; a park that was requested and never
        reached (the step it waits behind is the blocked one) is. A step that only raises still counts as a step:
        that run is ``FAILED_STEPS_BEFORE_CLOSE``'s."""
        if self._failed is not None or not self._paced:
            return False
        runtime = self._controller.logical_runtime
        if runtime is None or not runtime.is_running() or runtime.is_parked():
            self._liveness_seen, self._stalled_heartbeats = None, 0
            return False
        if now is None:
            import time

            now = time.perf_counter()
        steps = runtime.steps
        seen = self._liveness_seen
        if seen is None or seen[0] is not runtime or seen[1] != steps:
            self._liveness_seen, self._stalled_heartbeats = (runtime, steps, float(now)), 0
            return False
        if float(now) - seen[2] < self.STALL_OBSERVATION_MIN_S:
            return False                       # queued heartbeats handled together: one observation
        self._liveness_seen = (runtime, steps, float(now))
        self._stalled_heartbeats += 1
        if self._stalled_heartbeats < self.STALLED_HEARTBEATS_BEFORE_CLOSE:
            return False
        self._fail_closed(f"the cadence thread made no step across {self._stalled_heartbeats} heartbeats while "
                          f"running (blocked inside step {steps + 1}; parked={runtime.park_requested})")
        return True

    def _fail_closed(self, reason: str) -> None:
        """The cadence thread (its steps keep failing) or the message thread (the cadence is blocked,
        ``watch_cadence_liveness``). Park the cadence (requested, never awaited: this may run
        inside its own step) and end the wake pipe, so the owner sees the session's end as an event (its listener's
        ``on_closed``) and recovers; any later edge is answered with ``session_closed`` (``VisualizerEngineWorker``)."""
        import logging

        self._failed = str(reason)
        logging.getLogger(__name__).error("[SPOTIFY_VIS][ENGINE_WORKER] The session failed closed: %s", reason)
        runtime = self._controller.logical_runtime
        if runtime is not None:
            runtime.request_park()
        self.mailbox.close_wake_sender()

    def _paced_step_body(self, now: float) -> None:
        from widgets.spotify_visualizer.tick_pipeline import logical_tick

        backend, controller = self._backend, self._controller
        if backend is not None and self._source is not None:
            if backend.sample_rate != self._source.sample_rate:
                raise ValueError(f"recorded rate {self._source.sample_rate} != capture rate {backend.sample_rate}")
            running = backend.is_running() and controller.playing
            blocks = self._source.due(now, backend.block_size, running=running)
            if blocks:
                engine = self._engine
                before = engine.capture_publications()
                for block in blocks:
                    backend.offer(block)
                published = max(0, engine.capture_publications() - before)
                self._offered_blocks += len(blocks)
                self._accepted_blocks += published
                self._accepted_samples += published * len(blocks[0])
        elif self._device:
            self._watch_device_delivery()     # the device's own delivery (slice 5.3): never raises into the step
        logical_tick(controller.logical_tick_state)

    def _stop_cadence(self) -> None:
        """Stop and join the session's cadence (idempotent), keeping its final accounting."""
        import time

        runtime = self._controller.logical_runtime
        if runtime is None:
            return
        stopping = time.perf_counter()
        if not self._controller.stop_logical_runtime():
            raise RuntimeError("the session's cadence did not join")
        self._cadence_s = stopping - self._cadence_started_ts
        self._cadence_record = runtime.describe()

    def finish(self) -> dict:
        """Stop the cadence, then report (``VIS_STOP``'s reply): the frames published, the last runtime's accounting
        (steps, skipped deadlines, step failures, parked time) and run time (``cadence_s``: its start to its stop),
        the audio the source paced, and what reached the engine (``engine``: the blocks offered to the capture
        callback, the blocks and seconds the audio worker's callback published into the engine, the analysis
        commits since the cadence first started; A6-M1)."""
        if self._paced:
            self._stop_cadence()
        report: dict = {"mapping": self.mapping_name, "revision": self.mailbox.revision, "failed": self._failed}
        if self._paced:
            commits = int(self._engine.get_authoritative_frame_commit_seq()) - int(self._commits_at_start or 0)
            report.update(cadence=self._cadence_record, cadence_s=self._cadence_s, capture=self.capture_counts)
            if self._source is None:              # the device: what its callback published, and the commits
                report.update(audio=None, engine={"capture_publications": int(self._engine.capture_publications()),
                                                  "analysis_commits": commits, **self.device_report()})
            else:
                report.update(audio=self._source.describe(),
                              engine={"offered_blocks": self._offered_blocks, "accepted_blocks": self._accepted_blocks,
                                      "accepted_s": self._accepted_samples / self._source.sample_rate,
                                      "analysis_commits": commits})
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

    def set_view(self, *, version: Any, extent: Any, rotations: Any, override_extent: Any = None,
                 override_rotations: Any = None, framed_view: Any = None, presentation: Any = None) -> None:
        """The framed view the tick reads (``VIS_SET_VIEW``, latest wins; work order 5 slice 5.2): the owner's
        controller's layout metrics (committed extent and per-mode rotations, the live CUSTOM override or None) onto
        this session's controller, which resolves them for its own mode as the owner's does. The tick reads them under
        the controller's lock, so a step sees the old or the new metrics, never half of them. ``presentation`` (slice
        5.4): the presentation inputs the main side changed since its last send (``logical_edges
        .presentation_inputs_snapshot``: the view records and the mode's presentation-only controls), set onto the
        session's presentation state between two steps (each attribute is one reference; a pose read mid-update sees
        each record whole). ``framed_view`` (N0.4): the drawn card's exact camera inputs (``core.framed_view``), or None
        before a card is drawn. ``version`` must be ``core.framed_view.VIEW_MESSAGE_VERSION``: any other is refused
        before anything is applied."""
        from core.framed_view import VIEW_MESSAGE_VERSION, admit_framed_view
        from widgets.spotify_visualizer.logical_edges import apply_presentation_inputs

        if version != VIEW_MESSAGE_VERSION:
            raise ValueError(f"VIS_SET_VIEW version {version!r} is not {VIEW_MESSAGE_VERSION}")
        framed_view = admit_framed_view(framed_view)
        controller = self._controller
        if presentation:
            apply_presentation_inputs(controller.presentation_state, presentation)
        controller.hydrate_committed_layout_metrics(tuple(extent), dict(rotations or {}))
        controller.set_custom_viewport_override(
            None if override_extent is None else tuple(override_extent),
            dict(override_rotations) if override_rotations is not None else 0)
        controller.set_framed_view(framed_view)

    @property
    def bar_count(self) -> int:
        """The session's controller's bar count (a mode's technical config sets it; the owner's main side mirrors it
        for presentation readers such as Fullscreen Edit's envelope, A7-M2)."""
        return int(self._controller.bar_count)

    @property
    def view_records(self) -> dict:
        """The session's view records (``logical_edges.VIEW_RECORD_ATTRS``: held-key orbit, framed flight, drag
        inertia, Auto Rotate), as its activation commit left them: a preset's commit rebases the motion and arms Auto
        Rotate here, once, and the owner's main side adopts these instead of arming again (checkpoint audit 8,
        A8-L2)."""
        from widgets.spotify_visualizer.logical_edges import VIEW_RECORD_ATTRS

        state = self._controller.presentation_state
        return {attr: getattr(state, attr, None) for attr in VIEW_RECORD_ATTRS}

    def request_mode(self, mode: str, *, preset: int = 0, settings: Any = None, activation: Any = None,
                     at_once: bool = False, capacity_change: dict | None = None) -> tuple[int, int] | None:
        """An in-session activation, applied at the next tick boundary (the newest request wins): the owner's
        activation commit (``logical_edges.commit_logical_activation``) on the existing engine and controller, never a
        rebuild. Another mode is a mode activation; the current mode with its ``preset`` / ``settings`` is the
        owner's same-mode preset activation (A4-M3: never dropped). ``activation``: the owner's own resolved inputs
        for the target (work order 5 slice 5.2; None: the offline request for ``preset`` / ``settings``). Applied at
        once on a worker-paced session or with ``at_once`` (the owner's request between two inputs: the same tick
        boundary); then the committed (generation, activation id), else None."""
        self.validate_mode_request(mode)
        if capacity_change is not None and self.mapping_name != capacity_change['previous_mapping']:
            raise ValueError('stale capacity activation')
        self._pending_mode = (str(mode), int(preset), settings, None if activation is None else dict(activation),
                              capacity_change)
        if self._paced or at_once:
            # The owner's activation stops its runtime (the tick boundary), commits and restarts it: at once, as the
            # owner does on the GUI thread. A failure here may have half-applied (the runtime stopped, the engine
            # transaction, the capture settle), so ``VIS_SET_MODE`` closes the session (A6-M2).
            return self._apply_pending_mode()
        return None

    def validate_mode_request(self, mode: str) -> None:
        """Refuse a mode request before anything is applied (the session stays as it was)."""
        from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
        from core.visualizer_engine.packet_abi import mode_code

        if not self._live:
            raise ValueError("an in-session mode switch is a live-session control")
        get_visualizer_mode_descriptor(mode)
        mode_code(mode)                                   # a mode the header cannot name fails here, not mid-tick

    def _apply_pending_mode(self) -> tuple[int, int] | None:
        from widgets.spotify_visualizer.feature_replay import offline_activation_request
        from widgets.spotify_visualizer.logical_edges import commit_logical_activation

        if self._pending_mode is None:
            return None
        mode, preset, settings, activation, capacity_change = self._pending_mode
        self._pending_mode = None
        controller = self._controller
        request = activation if activation is not None else offline_activation_request(mode, preset, None, settings)
        generation, activation_id = commit_logical_activation(
            controller, kind="preset" if mode == self.mode else "mode", target=mode, **request,
        )
        if capacity_change is not None:
            # commit_logical_activation joined the previous producer; no writer can still access the old mapping.
            self.mailbox.attach_capacity(capacity_change)
            self.mailbox.write_identity(runtime_generation=self._controller.runtime_generation,
                                        engine_generation=generation, activation_id=activation_id, mode=mode)
        # Render admission for the committed identity (the owner binds it into its scene).
        controller.begin_render_activation(engine_generation=generation, activation_id=activation_id)
        self.mode = mode
        if self._paced and self._live_started:
            self._start_cadence()            # the owner restarts its runtime after the bind
        # The target's block size may differ: capture restarts on its lane before the next block.
        self._settle_capture()
        return int(generation), int(activation_id)

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

    def tick(self, feature: Any) -> int:
        """Accept one post-DSP input, run the tick, publish its frame; the mailbox revision after it."""
        from widgets.spotify_visualizer.tick_pipeline import logical_tick

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

    def __init__(self, request_queue, response_queue, *, diagnostics=None) -> None:
        super().__init__(request_queue, response_queue)
        self._session: Optional[EngineSession] = None
        self._diagnostics = diagnostics

    def _setup_logging(self):
        from core.logging.logger import (WorkerLoggingBootstrap, LoggingBootstrapProfile,
                                         setup_visualizer_worker_logging)
        from core.logging.crash_capture import enable_diagnostic_crash_capture
        from pathlib import Path

        bootstrap = self._diagnostics or WorkerLoggingBootstrap(LoggingBootstrapProfile(), None)
        logger = setup_visualizer_worker_logging(bootstrap)
        if bootstrap.log_directory is not None and bootstrap.native_fault_capture:
            path = enable_diagnostic_crash_capture(Path(bootstrap.log_directory)/'worker_visualizer',
                                                   allow_runtime_capture=True)
            if path is None:
                logger.error('Worker native-fault capture admission failed')
            else:
                logger.info('Worker native-fault capture: %s', path)
        return logger

    def _teardown_logging(self) -> None:
        from core.logging.logger import flush_and_close_logging
        from core.logging.crash_capture import close_diagnostic_crash_capture

        close_diagnostic_crash_capture()
        flush_and_close_logging()
        self._logger = None

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.VISUALIZER

    def _reply(self, msg: WorkerMessage, *, success: bool = True, error: str | None = None,
               **payload: Any) -> WorkerResponse:
        return WorkerResponse(msg_type=msg.msg_type, seq_no=msg.seq_no, correlation_id=msg.correlation_id,
                              success=success, error=error, payload=payload)

    def handle_message(self, msg: WorkerMessage) -> Optional[WorkerResponse]:
        try:
            session = self._session
            if (session is not None and session.failed is not None
                    and msg.msg_type not in (MessageType.VIS_CONFIGURE, MessageType.VIS_STOP)):
                # The session failed closed on its own (its steps kept failing, slice 5.7): no edge drives it again.
                self._close_session()
                return self._reply(msg, success=False, error=f"the session failed closed: {session.failed}",
                                   session_closed=True)
            if msg.msg_type == MessageType.VIS_CONFIGURE:
                self._close_session()
                payload = dict(msg.payload)
                self._session = EngineSession(**payload)
                qt = sorted(name for name in sys.modules if name.startswith("PySide6.Qt"))
                generation, activation_id = self._session.identity
                return self._reply(msg, qt_modules=qt, device_refused=self._session.device_refused,
                                   engine_generation=generation, activation_id=activation_id,
                                   bar_count=self._session.bar_count)
            if msg.msg_type == MessageType.VIS_INPUT:
                if self._session is None:
                    return self._reply(msg, success=False, error="no engine session is configured")
                try:
                    revision = self._session.tick(msg.payload["frame"])
                except Exception as exc:
                    # Fail closed (audit M2): a tick that raised left its controller half-updated, so the session
                    # ends; the owner treats it as a worker crash (fade, reconfigure once).
                    _log().exception('VIS_INPUT failed; closing the engine session')
                    self._close_session()
                    return self._reply(msg, success=False, error=f"{type(exc).__name__}: {exc}", session_closed=True)
                return self._reply(msg, revision=revision)
            if msg.msg_type in (MessageType.VIS_SET_MODE, MessageType.VIS_SET_DISPLAY_POWER, MessageType.VIS_START,
                                MessageType.VIS_SET_PLAYING, MessageType.VIS_SET_VIEW):
                if self._session is None:
                    return self._reply(msg, success=False, error="no engine session is configured")
                if msg.msg_type == MessageType.VIS_SET_VIEW:
                    self._session.set_view(**dict(msg.payload))   # state only: a refused view leaves the session
                    return self._reply(msg, **self._session.device_report())
                if msg.msg_type in (MessageType.VIS_START, MessageType.VIS_SET_PLAYING):
                    session = self._session
                    try:
                        if msg.msg_type == MessageType.VIS_START:
                            session.start(bool(msg.payload["playing"]))
                        else:
                            session.set_playing(bool(msg.payload["playing"]))
                    except Exception as exc:
                        _log().exception('%s failed; closing the engine session', msg.msg_type.value)
                        self._close_session()       # the edge may have half-applied: fail closed
                        return self._reply(msg, success=False, error=f"{type(exc).__name__}: {exc}",
                                           session_closed=True)
                    return self._reply(msg, **session.device_report())
                if msg.msg_type == MessageType.VIS_SET_MODE:
                    # Validated now (a refused request leaves the session as it was), applied at the session's next
                    # tick boundary (the newest request wins), or at once on a worker-paced session: an apply that
                    # raised may have half-applied (runtime stopped, engine transaction, capture), so the session
                    # closes, as a tick does (checkpoint audit 6, A6-M2).
                    payload = dict(msg.payload)
                    mode = payload.pop("mode")
                    session = self._session
                    session.validate_mode_request(mode)
                    try:
                        committed = session.request_mode(mode, **payload)
                    except Exception as exc:
                        _log().exception('VIS_SET_MODE failed; closing the engine session')
                        self._close_session()
                        return self._reply(msg, success=False, error=f"{type(exc).__name__}: {exc}",
                                           session_closed=True)
                    if committed is None:
                        return self._reply(msg)
                    return self._reply(msg, engine_generation=committed[0], activation_id=committed[1],
                                       bar_count=session.bar_count, view_records=session.view_records,
                                        mapping=session.mapping_name,
                                       **session.device_report())
                try:
                    changed = self._session.set_display_power(bool(msg.payload["on"]))
                except Exception as exc:
                    # The edge may have half-applied (capture reference, fence): fail closed, as a tick does.
                    _log().exception('VIS_SET_DISPLAY_POWER failed; closing the engine session')
                    self._close_session()
                    return self._reply(msg, success=False, error=f"{type(exc).__name__}: {exc}", session_closed=True)
                return self._reply(msg, changed=changed, **self._session.device_report())
            if msg.msg_type == MessageType.VIS_STOP:
                # The session closes even when ``finish`` raises (an unjoined cadence: A6-L7), releasing capture,
                # the compute lane and the mapping; the reply then carries the error. A stop addressed to another
                # session's mapping (an owner's stop, never awaited, landing after another session was configured:
                # slice 5.5) leaves the current session alone.
                session = self._session
                addressed = (msg.payload or {}).get("mapping")
                candidates = (msg.payload or {}).get('mapping_candidates', (addressed,))
                if addressed is not None and (session is None or session.mapping_name not in candidates):
                    return self._reply(msg, report=None, stale=True)
                try:
                    report = session.finish() if session is not None else None
                except Exception as exc:
                    _log().exception('VIS_STOP failed; closing the engine session')
                    error = f"{type(exc).__name__}: {exc}"
                    if session is not None and session.failed is not None:
                        # Why it failed closed (a blocked cadence never joins, so no report carries it): the main
                        # side logs this reply's error, and the worker's own log lines never reach the main log.
                        error += f"; the session had failed closed: {session.failed}"
                    try:
                        self._close_session()           # drops the session first, then unwinds all it holds
                    except Exception as close_exc:
                        error += f"; close: {type(close_exc).__name__}: {close_exc}"
                    return self._reply(msg, success=False, error=error, session_closed=True)
                self._close_session()
                # The Qt modules the process has loaded so far (the fresh-spawn probe reads them at spawn too).
                return self._reply(msg, report=report, qt_modules=sorted(name for name in sys.modules
                                                                         if name.startswith("PySide6.Qt")))
        except Exception as exc:   # reported to the owner, never a silent worker death
            _log().exception('%s failed', msg.msg_type.value)
            return self._reply(msg, success=False, error=f"{type(exc).__name__}: {exc}")
        return self._reply(msg, success=False, error=f"unsupported message {msg.msg_type}")

    def _handle_heartbeat(self, msg: WorkerMessage) -> None:
        """The supervisor's heartbeat (the message thread): answered as every worker answers it, after the session's
        cadence liveness is read (phase-boundary audit L4; ``EngineSession.watch_cadence_liveness``). The message loop
        answering proves only itself: the frames come from the session's own cadence thread. The watch never raises
        into the acknowledgement and never waits."""
        session = self._session
        if session is not None:
            try:
                session.watch_cadence_liveness()
            except Exception:
                _log().exception("[SPOTIFY_VIS][ENGINE_WORKER] The cadence liveness watch failed")
        super()._handle_heartbeat(msg)

    def _close_session(self) -> None:
        if self._session is not None:
            session, self._session = self._session, None
            session.close()

    def _cleanup(self) -> None:
        self._close_session()
        super()._cleanup()


def visualizer_worker_main(request_queue, response_queue, *, diagnostics=None) -> None:
    """``ProcessSupervisor`` factory for ``WorkerType.VISUALIZER``."""
    VisualizerEngineWorker(request_queue, response_queue, diagnostics=diagnostics).run()


def _log():
    """This module's logger, looked up only where a line is written (``logging.getLogger`` takes the logging module's
    lock: never on a per-step path such as the device session's delivery watch)."""
    import logging

    return logging.getLogger(__name__)
