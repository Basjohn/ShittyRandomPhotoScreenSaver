"""The production owner on the engine worker (native core P2b, work order 5 slice 5.2 and the core of 5.3): its gates.

    python tools/visualizer_replay/owner_worker_gate.py --out <dir> [--modes ...] [--seconds 5.5] [--realtime 3]
        [--cost 3] [--skip-identity] [--skip-realtime] [--skip-cost]

Every run builds the REAL ``QuickDisplayVisualizerOwner`` through the host binding's own ``VisualizerHostBinding
.construct`` on an unshown ``QuickDisplayRuntime`` (the stub host of ``owner_production_replay``: no window is shown,
created or mapped), with the production presentation kwargs; the worker side admits the owner's engine-worker path
(``experiment_flags``' admission, set for the run) and drives a real ``WorkerType.VISUALIZER`` process. No device is
opened: the worker side's sessions take the shipped clip's PCM through ``engine_worker_link
.recorded_capture_for_testing`` (the session refuses the device for its life); the in-process side's live engine refuses
it too and takes the same PCM through ``RecordedCaptureBackend``.

- **identity** (per mode): the owner on the worker vs the same owner in process, both on the live
  ``_SpotifyBeatEngine`` fed the same recorded PCM in the production read order (the tick's own step consumes the newest
  block and reads the previous commit; the analysis is held until the tick returns, then settled, as
  ``EngineSession(order="production")``). The worker side's session is input-paced (one ``VIS_INPUT`` per frame through
  the link's test control); every edge is the owner's own (``set_playing``, ``set_display_power``,
  ``request_mode_change`` and its crossfade commit, ``start``, ``retire``). Script: configure and start, play, a warm
  pause/resume, a park/unpark (A6-L8's reader clear), a mode switch through the owner's crossfade. Gate: the logical
  frames the owner publishes to its render bridge are identical, frame for frame (digest of the frame's ``repr``), and
  the worker path stayed on the worker throughout (no fallback).
- **realtime** (per mode): the owner on the worker-paced session (the worker's own cadence, the clip's PCM paced on
  the audio clock), its frames reaching ``sync_present`` through the real wake path (the listener thread, the queued Qt
  wake, the GUI event loop), the GUI stalling after each presentation. Gate: the cadence within 5% of the authored
  rate, one frame per step, coalescing (presented < published) with latest wins (every take is the newest frame the
  mapping header named before it), the newest frame presented by a wake after the stop (never stranded), 0 torn reads,
  the audio reached the engine, no fallback.
- **cost** (per mode): the main process's CPU per cadence step with the owner in process (its own cadence thread, the
  live engine on paced PCM: capture callbacks, DSP and the tick in this process) vs on the worker (this process only
  takes and presents frames), plus the GUI thread's wall time per presentation (``sync_present``) and per-thread CPU
  (the GUI thread, the logical cadence thread, the capture and compute lanes, the wake listener). The first gate-3 data
  point: no render thread runs here (no window), so the render thread's sync-time take is not measured.

Runs at below-normal priority; exit 1 on any identity mismatch or realtime failure. Report: ``<out>/owner_worker_gate.json``.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import struct
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GENERATION = 9001
#: The identity script's partner per mode (the switch target): a sample drawer into Bubble's spawn, spectrum readers
#: into and out of the 3D modes, Spectrum <-> Extruded Bubble (the live gate's pairs, extended to every mode).
PARTNER = {"spectrum": "extruded_bubble", "extruded_bubble": "spectrum", "oscilloscope": "bubble",
           "bubble": "oscilloscope", "sphere": "waveform_ribbon", "waveform_ribbon": "sphere",
           "devcurve": "shockwave_grid", "shockwave_grid": "devcurve", "extruded_spectrum": "oscilloscope"}
#: The realtime run's GUI stall after each presentation (a GUI busy ~40 ms per frame against a 90 Hz cadence).
STALL_S = 0.04
RATE_TOLERANCE = 0.05


def modes() -> tuple[str, ...]:
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors())


def _after(frames, seconds: float) -> int:
    start = frames[0].timestamp_us
    return next(i for i, frame in enumerate(frames) if frame.timestamp_us - start >= seconds * 1e6)


def identity_script(clip_frames, mode: str) -> list[tuple[str, Any]]:
    """("input", frame) / ("display", on) / ("mode", target): play from the start, a warm pause at 1.5 s for 1 s, a
    park at 3 s (no ticks for 0.5 s, the music goes on; the first two ticks after it carry no new capture, as the
    live gate's re-entry), a mode switch requested at 4.2 s (the owner's crossfade commits it 0.25 s later)."""
    from core.visualizer_engine.recorded_capture import synthesise_pause

    frames = list(synthesise_pause(clip_frames, at_s=1.5, pause_s=1.0))
    park, unpark = _after(frames, 3.0), _after(frames, 3.5)
    held = frames[park - 1].capture_history
    resumed = [dataclasses.replace(frame, capture_history=held) for frame in frames[unpark:unpark + 2]]
    tail = frames[unpark + 2:]
    script = ([("input", frame) for frame in frames[:park]] + [("display", False), ("display", True)]
              + [("input", frame) for frame in resumed])
    switch = _after(tail, 4.2 - (tail[0].timestamp_us - frames[0].timestamp_us) / 1e6) if tail else 0
    script += [("input", frame) for frame in tail[:switch]] + [("mode", PARTNER.get(mode, "spectrum"))]
    script += [("input", frame) for frame in tail[switch:]]
    return script


def identity_script_paused_switch(clip_frames, target: str) -> list[tuple[str, Any]]:
    """Checkpoint audit 7 A7-L6: a mode switch requested while Media is paused (play 1 s, pause 2.5 s with the switch
    0.4 s into it, then play), so the target's reveal predicate runs paused: in process the tick state's fresh-frame
    fence, on the worker the target's newest presentable frame. ``target`` is the switch's target."""
    from core.visualizer_engine.recorded_capture import synthesise_pause

    frames = list(synthesise_pause(clip_frames, at_s=1.0, pause_s=2.5))
    switch = _after(frames, 1.4)
    return ([("input", frame) for frame in frames[:switch]] + [("mode", target)]
            + [("input", frame) for frame in frames[switch:]])


#: The 3D modes whose drawn view the presentation side owns (orbit, Auto Rotate, camera): the view-input gate's modes.
VIEW_MODES = ("sphere", "extruded_spectrum", "extruded_bubble", "shockwave_grid", "waveform_ribbon")
#: The modes that reflect the displayed photograph (their descriptor's ``backdrop_setting``).
REFLECTING_MODES = ("sphere", "extruded_spectrum")


def identity_script_view(clip_frames, mode: str) -> list[tuple[str, Any]]:
    """Work order 5 slice 5.4 (checkpoint audit 7, A7-M1/A7-M2): the presentation inputs the capture reads, exercised
    while playing: a reflecting photograph from the start (a reflecting mode), a held-key orbit from 0.8 s to 1.6 s
    (turn and tilt), a same-mode preset re-activation at 2.2 s (its immediate Auto Rotate), then a second orbit."""
    frames = list(clip_frames)
    script: list[tuple[str, Any]] = [("reflect", True)] if mode in REFLECTING_MODES else []
    marks = {_after(frames, 0.8): ("orbit", (1.0, 0.5)), _after(frames, 1.6): ("orbit", None),
             _after(frames, 2.2): ("preset", mode), _after(frames, 3.4): ("orbit", (-1.0, -0.5)),
             _after(frames, 4.0): ("orbit", None)}
    for index, frame in enumerate(frames):
        if index in marks:
            script.append(marks[index])
        script.append(("input", frame))
    return script


# ------------------------------------------------------------------------------------------------- the owner rig


def activation_inputs(widgets: dict, mode: str) -> dict:
    """``DisplayManager._request_quick_visualizer_mode``'s resolution of a target activation (no Settings manager)."""
    from dataclasses import asdict

    from core.settings.models import SpotifyVisualizerSettings
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from tools.visualizer_replay.owner_production_replay import _presentation_kwargs
    from widgets.spotify_visualizer.technical_config import build_technical_cache

    candidate = dict(widgets["spotify_visualizer"])
    candidate["mode"] = mode
    activation = resolve_visualizer_activation_payload(candidate)
    model = SpotifyVisualizerSettings.from_mapping(activation.resolved_config, apply_preset_overlay=False,
                                                   resolve_preset_indices=False)
    return {"settings_model": model, "resolved_activation": activation,
            "technical_cache": build_technical_cache(None, model), "logical_kwargs": asdict(model),
            "presentation_kwargs": _presentation_kwargs(model, mode)}


class OwnerRig:
    """The real owner built by the host binding on an unshown runtime (``owner_production_replay``'s host).

    ``worker``: admit the engine-worker path (``supervisor`` hosts the process). In process, ``engine="live"`` gives
    the controller the live ``_SpotifyBeatEngine`` on recorded capture (``RecordedCaptureBackend``; the device refused)
    and ``cadence="manual"`` keeps the owner's installed cadence step without its thread (``steps``); ``"thread"``
    runs the real cadence thread with ``paced`` audio delivered before each step (the session's paced step).
    """

    def __init__(self, mode: str, *, worker: bool, supervisor: Any = None, playing: bool = True,
                 clock: list | None = None, cadence: str = "manual", paced: Any = None, extra_modes=()) -> None:
        self.mode = mode
        self.worker = worker
        self.supervisor = supervisor
        self.playing = [bool(playing)]
        self.clock = clock
        self.cadence = cadence
        self.paced = paced
        self.steps: list = []
        self.engines: list = []
        self.backends: list = []
        self.settled = threading.Event()
        self.admission = threading.Event()
        self.admission.set()
        self.owner: Any = None
        self.digests: list[str] = []
        self.published: list[Any] = []
        self.phases: list[tuple[str, float]] = []      # the owner's phase and content fade at each publication
        self.widgets = {
            "family_activation": {"media": True, "visualizers": True},
            "media": {"enabled": True, "position": "Top Left", "monitor": "1"},
            "spotify_visualizer": {"enabled": True, "visualizers_enabled": True, "mode": mode, f"preset_{mode}": 0,
                                   "mode_activation": {m: True for m in (mode, *extra_modes)}},
        }
        self._stack = contextlib.ExitStack()

    # ------------------------------------------------------------------------------------- in-process engine

    def _open_capture(self, config):
        from core.visualizer_engine.recorded_capture import RecordedCaptureBackend

        paced = self.paced
        on_started = (lambda _backend: paced.rebase()) if paced is not None else None
        backend = RecordedCaptureBackend(config, on_started=on_started)
        self.backends.append(backend)
        return backend

    def _admit_analysis(self) -> None:
        self.admission.wait(30.0)

    def _engine_factory(self, count: int):
        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

        engine = _SpotifyBeatEngine(count)
        engine.refuse_capture_devices()
        engine.set_capture_backend_factory(self._open_capture)
        if self.cadence == "manual":
            engine.set_analysis_settled_observer(self.settled.set)
            engine.set_analysis_admission_gate(self._admit_analysis)
        self.engines.append(engine)
        return engine

    def reflect(self) -> None:
        """Make the owner's mode reflect a photograph: its mirror setting and a 3D Detail tier with reflections
        written through the presentation config (as Home or a live tweak writes the presentation state), and a small
        synthetic photograph displayed on the unshown scene (the owner's backdrop listener makes the wallpaper)."""
        from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
        from rendering.quick.image_state import PresentationImage
        from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs

        owner = self.owner
        setting = get_visualizer_mode_descriptor(owner.controller.mode_id).backdrop_setting
        apply_presentation_vis_mode_kwargs(owner.controller.presentation_state,
                                           {setting: 0.6, "scene3d_detail": "High"})
        width, height = 64, 40
        pixels = bytearray()
        for y in range(height):
            for x in range(width):
                pixels += bytes((x * 4 % 256, y * 6 % 256, (x + y) % 256, 255))
        image = PresentationImage(identity="owner-rig-photo", source_path="owner-rig-photo.png",
                                  logical_size=(float(width), float(height)), device_pixel_ratio=1.0,
                                  pixel_size=(width, height), row_stride=width * 4, rgba8=bytes(pixels))
        scene = owner.presentation_runtime.scene_controller
        try:
            scene.set_presentation_image(image)
        except RuntimeError:                        # an unshown scene whose admission is not open: the same edge
            scene.background_item.set_presentation_image(image)
            owner._refresh_backdrop()
        if owner.controller.presentation_state._backdrop is None:
            raise RuntimeError("the rig's photograph made no reflected wallpaper")

    def settle(self) -> None:
        """In process: wait for every capture transaction admitted so far (the session's own completion edge). On the
        worker: run the GUI event loop until the session's link has no request in flight (the owner never waits for
        a reply: slice 5.5; the rig settles on the replies' events, bounded)."""
        if self.worker:
            owner = self.owner
            if owner is not None and owner._worker is not None:
                _event_loop_for(self.app, 30.0, until=lambda: owner._worker is None or not owner._worker.busy)
            return
        if not self.engines:
            return
        done = threading.Event()
        if self.engines[-1].fence_capture_transactions(done.set) and not done.wait(30.0):
            raise RuntimeError("the in-process capture lane never settled")

    # ---------------------------------------------------------------------------------------------- build

    def build(self) -> Any:
        from unittest import mock

        from PySide6.QtWidgets import QApplication

        from core.diagnostics import experiment_flags
        from core.settings.default_contract import require_canonical_default
        from core.threading.manager import ThreadManager
        from rendering.quick.runtime import QuickDisplayRuntime
        from rendering.quick.scene_controller import QuickSceneFactory
        from rendering.quick.state import QuickWindowPolicy
        from tools.visualizer_replay.owner_production_replay import _Host, _presentation_kwargs
        from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module
        from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
        from widgets.spotify_visualizer.visualizer_host_binding import VisualizerHostBinding, VisualizerHostServices

        app = QApplication.instance() or QApplication([])
        self.app = app
        factory = QuickSceneFactory()
        runtime = QuickDisplayRuntime(
            screen_index=0, runtime_generation=GENERATION, screen=app.primaryScreen(), scene_factory=factory,
            window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        )
        self._stack.callback(app.processEvents)
        self._stack.callback(factory.deleteLater)
        self._stack.callback(runtime.close_runtime)
        manager = ThreadManager()
        self._stack.callback(manager.shutdown, wait=True, timeout=30.0)
        self._stack.callback(self._stop_engines)
        host = _Host(runtime)
        record: dict = {"owner": None, "unit": None}
        services = VisualizerHostServices(
            admitted_owner=lambda: record["owner"], admitted_unit=lambda: record["unit"],
            record_admission=lambda owner, unit: record.update(owner=owner, unit=unit),
            record_unit=lambda unit: record.update(unit=unit), live_units=lambda: [host],
            caller_retired=lambda: False, widgets_config=lambda: self.widgets,
            shadow_values=lambda: require_canonical_default("widgets.shadows"),
            thread_manager=lambda: manager, process_supervisor=lambda: self.supervisor,
            display_power_on=lambda: True, set_construct_outcome=lambda *args: record.update(outcome=args),
            committed_layout_profile_resolver=lambda _mode: None, edit_layout_profile_activator=lambda _mode: True,
            transition_failure=lambda reason: record.update(transition_failure=reason),
            presentation_kwargs=_presentation_kwargs,
            media_model_for=lambda _unit: type(
                "Media", (), {"playbackState": "playing" if self.playing[0] else "paused"})(),
            bind_media=lambda _model: None, disconnect_media=lambda: None, publish_view_orbit_admission=lambda: None,
            release_view_state=lambda: None, cycle_mode=lambda: None, cycle_preset=lambda: None,
            volume_step=lambda _direction: True, refresh_context_menus=lambda: None,
            refresh_transfer_glyphs=lambda: None,
        )
        real_owner = owner_module.QuickDisplayVisualizerOwner
        real_start = VisualizerRuntimeController.start_logical_runtime
        rig = self

        def build_owner(_runtime, **kwargs):
            # The live engine on recorded capture: in process the controller's engine; on the worker path the owner
            # never asks for one (a fallback in process would, and then gets it, never the device).
            extra: dict = {"engine_factory": rig._engine_factory}
            if rig.clock is not None:
                extra["transition_clock"] = lambda: rig.clock[0]
            return real_owner(runtime, **extra, **kwargs)

        def start_runtime(controller, *, step, interval_s):
            if rig.cadence == "manual":
                rig.steps.append(step)                  # the owner's installed step, without its thread
                return None
            if rig.paced is None:
                return real_start(controller, step=step, interval_s=interval_s)

            def paced_step(now: float, _inner=step) -> None:   # the session's paced step: audio due, then the tick
                backend = rig.backends[-1] if rig.backends else None
                if backend is not None:
                    running = backend.is_running() and controller.playing
                    for block in rig.paced.due(now, backend.block_size, running=running):
                        backend.offer(block)
                _inner(now)

            return real_start(controller, step=paced_step, interval_s=interval_s)

        flags = experiment_flags.active_experiment_flags()
        experiment_flags.override_active_flags_for_testing(
            dataclasses.replace(flags, visualizer_engine_worker=bool(self.worker)))
        try:
            with mock.patch.object(owner_module, "QuickDisplayVisualizerOwner", build_owner), \
                    mock.patch.object(VisualizerRuntimeController, "start_logical_runtime", start_runtime):
                if not VisualizerHostBinding(services).construct(host):
                    raise RuntimeError(f"the binding refused the owner: {record.get('outcome')}")
        finally:
            experiment_flags.override_active_flags_for_testing(flags)
        # Later activations restart the cadence the same way (the patch is the rig's, for the run).
        patcher = mock.patch.object(VisualizerRuntimeController, "start_logical_runtime", start_runtime)
        patcher.start()
        self._stack.callback(patcher.stop)
        self.owner = record["owner"]
        self._stack.callback(self._retire)
        if self.worker:
            self.settle()                               # the configure's and start's replies (never awaited)
        if self.worker and self.owner._worker is None:
            raise RuntimeError("the owner fell back in process at construction")
        if not self.worker and self.engines:
            from widgets.spotify_visualizer.tick_pipeline import declare_mode_engine_demands

            # The session declares the mode's demands before the first block (capture history accumulates in the
            # callback); the in-process rig does the same before its first push.
            declare_mode_engine_demands(self.engines[-1], self.owner.controller.mode_id)
        self.settle()
        controller = self.owner.controller
        publish = controller.publish_render_snapshot

        def recording(logical, presentation, *, logical_revision):
            published = publish(logical, presentation, logical_revision=logical_revision)
            if published:
                self.published.append(logical)
                self.phases.append((self.owner._mode_transition_phase, round(float(presentation.content_fade), 6)))
            return published

        controller.publish_render_snapshot = recording
        return self.owner

    def _retire(self) -> None:
        owner = self.owner
        if owner is not None and not owner.is_retired:
            owner.retire()

    def _stop_engines(self) -> None:
        for engine in self.engines:
            try:
                engine.force_stop()
            except Exception:
                pass

    def close(self) -> None:
        self._stack.close()

    # ----------------------------------------------------------------------------------------- identity steps

    def tick_in_process(self, feature: Any, stream: Any) -> None:
        """The session's ``_tick_live`` + ``_logical_tick_live`` (production order) around the owner's step."""
        engine = self.engines[-1]
        if feature.playing:
            backend = self.backends[-1]
            for block in stream.blocks(feature.capture_history, feature.timestamp_us, backend.block_size):
                backend.push(block)
        self.settled.clear()
        self.admission.clear()
        try:
            self.steps[-1](self.clock[0])
        finally:
            self.admission.set()
        if engine.has_analysis_in_flight() and not self.settled.wait(30.0):
            raise RuntimeError("the in-process analysis never settled")


def identity_run(mode: str, script, *, worker: bool, supervisor: Any = None, namespace: int | None = None) -> dict:
    """One owner through ``script``; the digests of the logical frames it published to its render bridge."""
    import itertools

    import tools.expanded_visualizer_evidence as evidence
    from core.authored_clock import pinned_authored_clock
    from core.visualizer_engine.recorded_capture import CaptureHistoryStream
    from widgets.spotify_visualizer import engine_worker_link, extruded_bubble_drift_log
    from widgets.spotify_visualizer.feature_replay import REPLAY_SEED

    clock = [0.0]
    first = next(value for kind, value in script if kind == "input")
    partner = next((value for kind, value in script if kind == "mode"), None)
    rig = OwnerRig(mode, worker=worker, supervisor=supervisor, playing=bool(first.playing), clock=clock,
                   extra_modes=(partner,) if partner else ())
    stream = CaptureHistoryStream()
    saved_revisions = extruded_bubble_drift_log._REVISIONS
    report: dict = {"mode": mode, "worker": worker}
    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(pinned_authored_clock(lambda: clock[0]))
            if worker:
                stack.enter_context(engine_worker_link.recorded_capture_for_testing(
                    cadence="input", order="production", seed=REPLAY_SEED))
            else:
                # The worker session's numbering (its label namespace), here.
                extruded_bubble_drift_log._REVISIONS = itertools.count((int(namespace or 0) << 32) + 1)
            owner = rig.build()
            controller = owner.controller
            if not worker:
                # The worker session's mode-generator seed (Bubble's spawn), on this owner's own controller: built,
                # configured and started, nothing ticked yet, so the first draw is the seed's first, as in the session.
                controller.seed_mode_generators(REPLAY_SEED)
            if worker:
                report["namespace"] = owner._worker.label_namespace
            inputs = 0
            for kind, value in script:
                if worker and owner._worker is None:
                    raise RuntimeError(f"the owner left the worker at step {inputs}")
                if kind == "input":
                    if bool(value.playing) != bool(controller.playing):
                        owner.set_playing(bool(value.playing))           # Media's edge (between two ticks)
                        rig.settle()
                    clock[0] = value.timestamp_us / 1_000_000.0
                    if worker:
                        owner._worker.feed_for_testing(value)
                    else:
                        rig.tick_in_process(value, stream)
                    owner.sync_present()
                    # An activation the presentation committed may restart capture (another block size) on its lane:
                    # settled before the next block, as the session's own activation settles it.
                    rig.settle()
                    inputs += 1
                elif kind == "display":
                    owner.set_display_power(bool(value))
                    rig.settle()
                elif kind == "mode":
                    if not owner.request_mode_change(value, **activation_inputs(rig.widgets, value)):
                        raise RuntimeError(f"the owner refused the switch to {value}")
                elif kind == "preset":
                    if not owner.request_preset_change(value, **activation_inputs(rig.widgets, value)):
                        raise RuntimeError(f"the owner refused the preset activation of {value}")
                elif kind in ("orbit", "reflect"):
                    # Presentation inputs, written on the GUI thread between two ticks; on the worker they are
                    # forwarded at once (the presentation boundary that follows such an edge in production).
                    if kind == "reflect":
                        rig.reflect()
                    else:
                        from widgets.spotify_visualizer.view_orbit import set_view_orbit_rates, stop_view_orbit_motion

                        if value is None:
                            stop_view_orbit_motion(controller.presentation_state, clock[0])
                        else:
                            set_view_orbit_rates(controller.presentation_state, controller.mode_id, value[0],
                                                 value[1], clock[0])
                    owner.forward_presentation_inputs()
                    rig.settle()
            report.update(inputs=inputs, final_mode=controller.mode_id, phase=owner._mode_transition_phase,
                          on_worker=bool(owner._worker is not None) if worker else None)
            report["digests"] = [evidence.frame_digest(logical) for logical in rig.published]
            report["phases"] = list(rig.phases)
    finally:
        rig.close()
        extruded_bubble_drift_log._REVISIONS = saved_revisions
    return report


def identity_gate(mode: str, clip_frames, supervisor: Any) -> dict:
    script = identity_script(clip_frames, mode)
    worker = identity_run(mode, script, worker=True, supervisor=supervisor)
    in_process = identity_run(mode, script, worker=False, namespace=worker["namespace"])
    a, b = worker["digests"], in_process["digests"]
    first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
    return {"mode": mode, "partner": PARTNER.get(mode), "inputs": worker["inputs"], "frames_worker": len(a),
            "frames_in_process": len(b), "first_mismatch": first, "final_mode": worker["final_mode"],
            "final_mode_in_process": in_process["final_mode"], "stayed_on_worker": worker["on_worker"],
            "identical": bool(a == b and len(a) > worker["inputs"] // 2 and worker["on_worker"]
                              and worker["final_mode"] == in_process["final_mode"] == PARTNER.get(mode))}


# ----------------------------------------------------------------------------------------------- realtime + cost


def _event_loop_for(app, seconds: float, until=None) -> None:
    """Run the GUI event loop for ``seconds`` (or until ``until()``): the rig's own bounded wait, in short slices so
    ``until`` is checked and a nested loop that an earlier caller left quitting cannot end the wait early."""
    from PySide6.QtCore import QEventLoop, QTimer

    deadline = time.perf_counter() + float(seconds)
    while True:
        app.processEvents()
        if until is not None and until():
            return
        remaining = deadline - time.perf_counter()
        if remaining <= 0.0:
            return
        loop = QEventLoop()
        QTimer.singleShot(max(1, int(min(remaining, 0.05) * 1000)), loop.quit)
        loop.exec()


def _newest_published(mailbox) -> int:
    from core.visualizer_engine.packet_abi import FIRST_SEQUENCE

    latest = struct.unpack_from("<Q", mailbox._reader._view, 32)[0]
    return 0 if latest < FIRST_SEQUENCE else (latest - FIRST_SEQUENCE) // 2 + 1


def _thread_cpu() -> dict[int, float]:
    import psutil

    return {thread.id: thread.user_time + thread.system_time for thread in psutil.Process().threads()}


def _named_threads() -> dict[str, list[int]]:
    names: dict[str, list[int]] = {}
    for thread in threading.enumerate():
        if thread.native_id is not None:
            names.setdefault(thread.name, []).append(thread.native_id)
    return names


def _percentile(values, q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return float(ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))])


def live_run(mode: str, *, worker: bool, supervisor: Any, pcm: Any, seconds: float, stall_s: float = 0.0) -> dict:
    """The owner free-running for ``seconds`` with the real wake path on the GUI event loop; its accounting."""
    import psutil

    from core.visualizer_engine.recorded_capture import PacedPcmSource
    from widgets.spotify_visualizer import engine_worker_link

    samples, rate = pcm
    paced = None if worker else PacedPcmSource(samples, rate)
    rig = OwnerRig(mode, worker=worker, supervisor=supervisor, playing=True, cadence="thread", paced=paced)
    takes: list[int] = []
    stale: list[tuple[int, int]] = []
    sync_ms: list[float] = []
    energetic = [0]
    checks = [0]
    try:
        with contextlib.ExitStack() as stack:
            if worker:
                stack.enter_context(engine_worker_link.recorded_capture_for_testing(pcm=samples, pcm_rate=rate))
            owner = rig.build()
            controller = owner.controller
            mailbox = controller.logical_mailbox
            take = mailbox.take

            def checked_take():
                newest = _newest_published(mailbox) if worker else 0
                publication = take()
                if publication is not None:
                    previous = takes[-1] if takes else 0
                    takes.append(int(publication.revision))
                    if newest > previous + 1:
                        checks[0] += 1
                    if worker and publication.revision < newest:
                        stale.append((int(publication.revision), newest))
                    common = getattr(publication.state, "common", None)
                    if common is not None and float(common.energy.overall) > 0.0:
                        energetic[0] += 1
                return publication

            mailbox.take = checked_take
            sync = owner.sync_present
            stall = threading.Event()

            def timed_sync():
                started = time.perf_counter()
                result = sync()
                sync_ms.append((time.perf_counter() - started) * 1000.0)
                if stall_s > 0.0:
                    stall.wait(stall_s)                     # a slow GUI (never set: a bounded stall)
                return result

            owner.sync_present = timed_sync
            wake = owner._publication_wake
            wake._callback = timed_sync
            process = psutil.Process()
            cpu_before, threads_before = process.cpu_times(), _thread_cpu()
            started = time.perf_counter()
            _event_loop_for(rig.app, seconds)
            elapsed = time.perf_counter() - started
            cpu_after, threads_after = process.cpu_times(), _thread_cpu()
            names = _named_threads()
            if worker:
                link = owner._worker
                on_worker = link is not None
                report = link.stop() if link is not None else None
                last = int(report["revision"]) if report else 0
                _event_loop_for(rig.app, 3.0, until=lambda: bool(takes) and takes[-1] >= last)
                if not takes or takes[-1] < last:
                    _event_loop_for(rig.app, 3.0)
                cadence = (report or {}).get("cadence") or {}
                steps = int(cadence.get("steps", 0))
                running_s = float((report or {}).get("cadence_s", 0.0)) - float(cadence.get("parked_seconds", 0.0))
                torn = mailbox._reader.torn_reads
            else:
                on_worker = None
                runtime = controller.logical_runtime
                described = runtime.describe() if runtime is not None else {}
                stopping = time.perf_counter()
                controller.stop_logical_runtime()
                cadence = described
                steps = int(described.get("steps", 0))
                running_s = stopping - started
                report, last, torn = None, takes[-1] if takes else 0, 0
            per_thread = {}
            for name, ids in names.items():
                spent = sum(threads_after.get(i, 0.0) - threads_before.get(i, 0.0) for i in ids)
                if spent > 0.0005:
                    per_thread[name] = round(spent, 4)
            main_cpu = (cpu_after.user - cpu_before.user) + (cpu_after.system - cpu_before.system)
            interval_ms = float(cadence.get("interval_ms", 0.0) or 0.0)
            authored_hz = 1000.0 / interval_ms if interval_ms else 0.0
            cadence_hz = steps / running_s if running_s > 0 else 0.0
            result = {
                "mode": mode, "worker": worker, "seconds": round(elapsed, 3), "steps": steps,
                "cadence_hz": round(cadence_hz, 2), "authored_hz": round(authored_hz, 2),
                "published": int(report["revision"]) if report else steps, "presented": len(takes),
                "last_presented": takes[-1] if takes else None, "last_published": last,
                "stranded": bool(worker and (not takes or takes[-1] < last)), "torn_reads": int(torn),
                "latest_checks": checks[0], "stale_takes": stale[:5], "stale_count": len(stale),
                "energetic_share": round(energetic[0] / len(takes), 3) if takes else 0.0,
                "on_worker": on_worker, "engine": (report or {}).get("engine"), "audio": (report or {}).get("audio"),
                "main_cpu_s": round(main_cpu, 4), "main_cpu_ms_per_step": round(1000.0 * main_cpu / steps, 4)
                if steps else None,
                "sync_ms_p50": round(_percentile(sync_ms, 0.5), 4), "sync_ms_p90": round(_percentile(sync_ms, 0.9), 4),
                "threads_cpu_s": per_thread,
            }
            if worker:
                engine = result["engine"] or {}
                audio = result["audio"] or {}
                paced_s = float(audio.get("paced_s", 0.0) or 0.0)
                accepted = float(engine.get("accepted_s", 0.0) or 0.0) / paced_s if paced_s else 0.0
                result["accepted_over_paced"] = round(accepted, 4)
                result["cadence_ok"] = bool(steps > 0 and abs(cadence_hz - authored_hz) <= RATE_TOLERANCE * authored_hz)
                result["realtime_ok"] = bool(
                    on_worker and result["cadence_ok"] and result["published"] == steps
                    and (stall_s <= 0.0 or (len(takes) < result["published"] and checks[0] > 0))
                    and not result["stranded"] and torn == 0 and not stale
                    and all(b > a for a, b in zip(takes, takes[1:]))
                    and accepted >= 0.97 and engine.get("accepted_blocks") == engine.get("offered_blocks")
                    and int(engine.get("analysis_commits", 0)) >= 0.8 * steps
                    and result["energetic_share"] >= 0.5)
            return result
    finally:
        rig.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    parser.add_argument("--modes", nargs="*")
    parser.add_argument("--seconds", type=float, default=5.5)
    parser.add_argument("--realtime", type=float, default=3.0)
    parser.add_argument("--cost", type=float, default=3.0)
    parser.add_argument("--skip-identity", action="store_true")
    parser.add_argument("--skip-realtime", action="store_true")
    parser.add_argument("--skip-cost", action="store_true")
    args = parser.parse_args(argv)
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    import tools.expanded_visualizer_evidence as evidence
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import WorkerType
    from core.visualizer_engine.engine_worker import visualizer_worker_main
    from tools.visualizer_replay.live_engine_gate import paced_pcm

    chosen = args.modes or list(modes())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"modes": chosen, "seconds": args.seconds, "realtime_s": args.realtime, "cost_s": args.cost,
                    "identity": {}, "realtime": {}, "cost": {}}
    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    started = time.perf_counter()
    failed = False
    try:
        if not supervisor.start(WorkerType.VISUALIZER):
            raise RuntimeError("the engine worker did not start")
        report["worker_pid"] = supervisor.get_detailed_health(WorkerType.VISUALIZER).get("pid")
        if not args.skip_identity:
            clip = evidence.shipped_clip(args.seconds)
            for mode in chosen:
                verdict = identity_gate(mode, clip.frames, supervisor)
                report["identity"][mode] = verdict
                failed |= not verdict["identical"]
                print(f"[IDENTITY] {mode:18s} -> {verdict['partner']:18s} {verdict['frames_worker']} frames "
                      f"{'OK' if verdict['identical'] else 'MISMATCH at ' + str(verdict['first_mismatch'])}", flush=True)
        pcm = paced_pcm(3.0)
        if not args.skip_realtime:
            for mode in chosen:
                verdict = live_run(mode, worker=True, supervisor=supervisor, pcm=pcm, seconds=args.realtime,
                                   stall_s=STALL_S)
                report["realtime"][mode] = verdict
                failed |= not verdict["realtime_ok"]
                print(f"[REALTIME] {mode:18s} {verdict['steps']} steps {verdict['cadence_hz']} Hz presented "
                      f"{verdict['presented']}/{verdict['published']} {'OK' if verdict['realtime_ok'] else 'FAIL'}",
                      flush=True)
        if not args.skip_cost:
            for mode in chosen:
                off = live_run(mode, worker=False, supervisor=None, pcm=pcm, seconds=args.cost)
                on = live_run(mode, worker=True, supervisor=supervisor, pcm=pcm, seconds=args.cost)
                report["cost"][mode] = {"off": off, "on": on}
                print(f"[COST] {mode:18s} main CPU/step off {off['main_cpu_ms_per_step']} ms on "
                      f"{on['main_cpu_ms_per_step']} ms; sync p50 off {off['sync_ms_p50']} on {on['sync_ms_p50']}",
                      flush=True)
    finally:
        supervisor.shutdown()
        report["elapsed_s"] = round(time.perf_counter() - started, 1)
        (out / "owner_worker_gate.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
