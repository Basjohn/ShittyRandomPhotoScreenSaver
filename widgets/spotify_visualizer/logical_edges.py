"""The Visualizer's logical-side activation commit and engine edges: one owner for every host of a controller.

The production Quick owner (``quick_display_visualizer_owner.QuickDisplayVisualizerOwner``) and the engine worker's
session (``core.visualizer_engine.engine_worker.EngineSession``, native core P2b) drive one controller and its beat
engine through the same control edges. Each sequence lives here once and both call it (checkpoint audit 4, A4-H1), so
a change to the owner's order reaches the worker and the call-log parity test
(``tests/test_visualizer_logical_edges_parity.py``) fails if either side runs its own copy:

- ``configure_logical_controller``: the first activation's configuration (the owner's ``configure`` with the
  activation's inputs the host binding resolved: settings model, resolved activation, technical cache), recorded and
  applied through ``apply_logical_configuration`` (checkpoint audit 5, A5-M2: the session configured with a replay
  copy before).
- ``apply_logical_configuration``: the configuration a mode activation (or ``configure``) commits on the logical side:
  tick state, presentation state, engine kwargs, technical config, the mode's logical state and the warm re-entry
  fence.
- ``commit_logical_activation``: the hidden activation commit, from the outgoing runtime's stop through one engine
  activation transaction to the target's pending identity.
- ``apply_playback_edge``, ``prepare_engine_start`` / ``admit_engine_start`` / ``release_engine_started_parked``,
  ``park_logical_side`` / ``unpark_logical_side``: the play edge, ``start`` and display power (the cadence park, the
  engine reference, the fence and the clock rebase, in the owner's order).
- ``start_logical_cadence``: the logical runtime's cadence (``VisualizerLogicalRuntime`` through the controller), the
  owner's and, paced by the worker itself (work order 5, slice 5.1), the session's.

What stays the hosts' own: the owner's Edit profile, backdrop, render binding, crossfade and reader-side mailbox clear;
the session's capture-lane completion edge and recorded audio source. This module imports QtCore at most at import time
(``tests/test_visualizer_engine_import_weight.py``), and a configuration QtCore only at call time too (the presentation
config is Qt-free since work order 5 slice 5.4; checkpoint audit 5, A5-L2). ``presentation_inputs_snapshot`` /
``apply_presentation_inputs`` carry the presentation inputs the capture reads to the engine worker (slice 5.4). It adds
no work at rest: it runs only at the edges.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from core.authored_clock import authored_now
from core.logging.logger import get_logger, is_viz_diagnostics_enabled

logger = get_logger(__name__)

#: The authored logical cadence (Hz). The owner's default cadence, here so every host paces with the one value.
DEFAULT_LOGICAL_HZ = 90.0

#: The configuration reason the owner's ``configure`` reports (``apply_controller_technical_config``'s log label).
CONFIGURE_REASON = "quick_owner_configure"


def mode_runtime_factory(mode_id: str) -> Callable[[], Any]:
    """Resolve a mode's frame-runtime class from the canonical descriptor wiring.

    The per-mode import path lives once in ``core.settings.visualizer_mode_registry``; this reads that string and
    imports lazily, so no frame runtime is imported until its mode is actually constructed. An unknown/empty mode
    falls back to Spectrum exactly as the previous hand-written switch did.
    """
    from importlib import import_module

    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor

    normalized = str(mode_id or "").lower()
    try:
        descriptor = get_visualizer_mode_descriptor(normalized)
    except KeyError:
        descriptor = get_visualizer_mode_descriptor("spectrum")
    module = import_module(descriptor.frame_runtime_module)
    return getattr(module, descriptor.frame_runtime_class)


# ----------------------------------------------------------------------------------------------- configuration


def apply_logical_configuration(
    controller: Any,
    *,
    logical_kwargs: Mapping[str, Any] | None,
    presentation_kwargs: Mapping[str, Any] | None,
    technical_config: Mapping[str, Any] | None,
    thread_manager: Any | None,
    process_supervisor: Any | None,
    playing: bool,
    reason: str,
    refresh_presentation: Callable[[], None] | None = None,
) -> None:
    """Configure ``controller`` (its current mode) from resolved settings, on the logical side.

    ``refresh_presentation`` is the host's presentation step that runs once the technical config is applied (the
    owner's reflected-wallpaper backdrop); the worker has none.
    """
    from widgets.spotify_visualizer.config_applier import (
        apply_logical_vis_mode_kwargs,
        apply_presentation_vis_mode_kwargs,
    )
    from widgets.spotify_visualizer.logical_tick_state import install_default_logical_tick_state
    from widgets.spotify_visualizer.presentation_state import install_default_presentation_state
    from widgets.spotify_visualizer.source_config_applier import resolve_mode_source_config

    state = controller.logical_tick_state
    resolved_logical_kwargs = (
        resolve_mode_source_config(controller.mode_id, logical_kwargs) if logical_kwargs is not None else None
    )
    resolved_presentation_kwargs = (
        resolve_mode_source_config(controller.mode_id, presentation_kwargs)
        if presentation_kwargs is not None
        else None
    )
    install_default_logical_tick_state(state, bar_count=controller.bar_count)
    install_default_presentation_state(controller.presentation_state)
    if resolved_logical_kwargs:
        apply_logical_vis_mode_kwargs(state, resolved_logical_kwargs)
    if resolved_presentation_kwargs:
        apply_presentation_vis_mode_kwargs(controller.presentation_state, resolved_presentation_kwargs)
    if is_viz_diagnostics_enabled():
        presentation_state = controller.presentation_state
        logger.debug(
            "[VIS_RAINBOW] stage=CONFIG reason=%s mode=%s enabled=%s speed=%.3f",
            reason,
            controller.mode_id,
            bool(presentation_state._rainbow_enabled),
            float(presentation_state._rainbow_speed),
        )
    controller.enabled = True
    controller.playing = bool(playing)
    if thread_manager is not None:
        controller.thread_manager = thread_manager
    if process_supervisor is not None:
        controller.process_supervisor = process_supervisor
    engine = controller.ensure_engine()

    # Source-owned preset semantics used to be side effects of the mixed QWidget config applier. Quick has no widget
    # presenter, so route those values explicitly to the one existing BeatEngine at configuration time.
    # ``logical_kwargs`` is the canonical settings payload in production; presentation is only a fallback for
    # focused callers.
    source_kwargs = resolved_logical_kwargs if resolved_logical_kwargs is not None else resolved_presentation_kwargs
    if source_kwargs:
        from widgets.spotify_visualizer.source_config_applier import apply_engine_vis_mode_kwargs

        apply_engine_vis_mode_kwargs(engine, source_kwargs)

    # Technical settings are a complete canonical/preset-resolved contract. Missing mode configuration is an
    # authority error at configuration time; it must not leak into renderer/DSP fallbacks later.
    resolved_technical = technical_config
    if resolved_technical is None:
        cache = controller.technical_config_cache
        if not isinstance(cache, dict):
            raise RuntimeError("visualizer technical cache is unavailable")
        from widgets.spotify_visualizer.technical_config import resolve_technical_config

        resolved_technical = resolve_technical_config(cache, controller.mode_id)
    from widgets.spotify_visualizer.quick_technical_config import apply_controller_technical_config

    apply_controller_technical_config(controller, resolved_technical, reason=reason)
    if refresh_presentation is not None:
        refresh_presentation()

    controller.resolve_logical_mode_state(controller.mode_id, mode_runtime_factory(controller.mode_id))
    state._mode_teardown_block_until_ready = False
    state._mode_transition_ready = True
    # Lead E1: a persistent (shared) beat engine keeps its last committed frame across owner recreation. On a
    # same-generation warm re-entry that retained frame would satisfy the generation-only fresh-frame fence and be
    # admitted as the first reactive result (a flash of seconds-old audio energy). Arm the fence with a commit-seq
    # watermark so only a frame committed after this re-entry is accepted. A cold engine (no prior frame) is left
    # unfenced, so cold start is byte-for-byte unchanged.
    from widgets.spotify_visualizer.tick_pipeline import arm_reentry_fresh_frame_fence

    warm_reentry = arm_reentry_fresh_frame_fence(state, engine)
    if warm_reentry and is_viz_diagnostics_enabled():
        # E2 attribution (diagnostics-only): arm the existing T3..T6 markers on this warm recreation so the
        # fresh-source -> retained-presentation gap is attributable exactly like a play/pause edge, labelled
        # kind=recreation.
        from widgets.spotify_visualizer.reactivity_diagnostics import begin_playback_edge

        begin_playback_edge(state, now_ts=authored_now(), playing=bool(controller.playing), kind="recreation")


def record_activation_inputs(
    controller: Any,
    *,
    settings_model: Any,
    resolved_activation: Any,
    technical_cache: Mapping[str, Any],
) -> None:
    """An activation's resolved inputs onto the controller: settings model, resolved activation, technical cache."""
    controller.settings_model = settings_model
    controller.record_resolved_activation(resolved_activation)
    controller.technical_config_cache = dict(technical_cache)


def configure_logical_controller(
    controller: Any,
    *,
    activation: Mapping[str, Any] | None,
    logical_kwargs: Mapping[str, Any] | None,
    presentation_kwargs: Mapping[str, Any] | None,
    technical_config: Mapping[str, Any] | None,
    thread_manager: Any | None,
    process_supervisor: Any | None,
    playing: bool,
    refresh_presentation: Callable[[], None] | None = None,
) -> None:
    """The owner's ``configure`` on the logical side: ``activation`` (``record_activation_inputs``' keywords: what the
    host binding resolved for the first activation; None keeps what the controller holds), then
    ``apply_logical_configuration``. Media's playing state is ``playing`` (the host binding passes False and commits
    Media's state with the play edge before ``start``). Render admission is the host's bind, after this."""
    if activation is not None:
        record_activation_inputs(controller, **activation)
    apply_logical_configuration(
        controller,
        logical_kwargs=logical_kwargs,
        presentation_kwargs=presentation_kwargs,
        technical_config=technical_config,
        thread_manager=thread_manager,
        process_supervisor=process_supervisor,
        playing=playing,
        reason=CONFIGURE_REASON,
        refresh_presentation=refresh_presentation,
    )


# ------------------------------------------------------------------------------------------- activation commit


class LogicalRuntimeNotJoined(RuntimeError):
    """The outgoing logical runtime did not join, so no activation began (nothing to roll back but the host's own)."""


@dataclass
class ActivationProgress:
    """Where a ``commit_logical_activation`` got to (the host's failure handling reads it).

    ``stage``: ``prepare`` (the outgoing runtime's stop), ``begin`` (the engine transaction's contract and begin),
    ``transaction`` (inside it), ``bind`` (after it, the pending identity). ``step``: the label the owner's failure log names.
    """

    stage: str = "prepare"
    step: str = "begin_engine_transaction"


def commit_logical_activation(
    controller: Any,
    *,
    kind: str,
    target: str,
    settings_model: Any,
    resolved_activation: Any,
    technical_cache: Mapping[str, Any],
    logical_kwargs: Mapping[str, Any],
    presentation_kwargs: Mapping[str, Any],
    progress: ActivationProgress | None = None,
    on_layout_profile_change: Callable[[str], None] | None = None,
    configure: Callable[..., None] | None = None,
    recover: Callable[[str], bool] | None = None,
) -> tuple[int, int] | None:
    """Commit one hidden mode (``kind="mode"``) or same-mode preset (``kind="preset"``) activation.

    The outgoing logical runtime is stopped (its logical mode states and unread publication go with it), then one
    engine activation transaction runs around the target's mode, settings, technical config and engine kwargs
    (``apply_logical_configuration``), a preset's view motion, and the engine's compute / smoothing / floor reset; then
    the fresh-frame fence waits on the committed generation and activation. Returns them; the host binds render
    admission for them and starts its cadence.

    ``on_layout_profile_change(target)``: inside the transaction, when the target's layout profile differs (the
    owner's render-bridge discard and committed profile). The step label stays ``begin_engine_transaction`` while it
    runs; the host moves ``progress.step`` on (the owner names ``activate_committed_profile`` after its discard, as
    before the shared module: checkpoint audit 5, A5-L5). ``configure(**kwargs)``: the host's configuration entry
    (``apply_logical_configuration``'s keywords without the controller; the owner's adds its backdrop), by default
    ``apply_logical_configuration`` itself. ``recover(step)``: called inside the failure, before the
    transaction ends, when a step of it raised; True means the host restored the outgoing activation (the commit
    returns None), False re-raises. Without it every failure raises.
    """
    progress = progress if progress is not None else ActivationProgress()
    progress.stage, progress.step = "prepare", "begin_engine_transaction"
    engine = controller.ensure_engine()
    if not controller.stop_logical_runtime():
        raise LogicalRuntimeNotJoined("visualizer logical runtime did not join for activation")

    progress.stage = "begin"
    begin = getattr(engine, "begin_activation_transaction", None)
    end = getattr(engine, "end_activation_transaction", None)
    if not callable(begin) or not callable(end):
        raise RuntimeError("visualizer BeatEngine has no activation transaction")

    target = str(target)
    begin()
    progress.stage = "transaction"
    try:
        if kind == "mode":
            from core.settings.visualizer_mode_registry import get_visualizer_layout_profile

            if get_visualizer_layout_profile(target) != get_visualizer_layout_profile(controller.mode_id):
                if on_layout_profile_change is not None:
                    on_layout_profile_change(target)
            progress.step = "set_controller_mode"
            controller.set_mode(target)
        elif kind != "preset":
            raise ValueError(f"unknown visualizer activation kind: {kind}")
        elif target != controller.mode_id:
            raise RuntimeError("preset activation attempted to change visualizer mode")
        progress.step = "configure_target"
        record_activation_inputs(controller, settings_model=settings_model, resolved_activation=resolved_activation,
                                 technical_cache=technical_cache)
        from widgets.spotify_visualizer.technical_config import resolve_technical_config

        if configure is None:
            def configure(**kwargs: Any) -> None:
                apply_logical_configuration(controller, **kwargs)
        configure(
            logical_kwargs=logical_kwargs,
            presentation_kwargs=presentation_kwargs,
            technical_config=resolve_technical_config(controller.technical_config_cache, target),
            thread_manager=controller.thread_manager,
            process_supervisor=controller.process_supervisor,
            playing=controller.playing,
            reason=f"quick_owner_{kind}_change",
        )
        if kind == "preset":
            from widgets.spotify_visualizer.view_orbit import arm_view_auto_rotate, rebase_view_orbit_motion

            # The target is configured and hidden, and logical capture is stopped. Publish its complete motion state
            # before restarting: old same-mode auto rotation must not override its first pose.
            progress.step = "activate_target_view_motion"
            view_now = authored_now()
            rebase_view_orbit_motion(controller.presentation_state, view_now)
            arm_view_auto_rotate(controller.presentation_state, target, view_now, immediate=True)
        cancel = getattr(engine, "cancel_pending_compute_tasks", None)
        reset_smoothing = getattr(engine, "reset_smoothing_state", None)
        reset_floor = getattr(engine, "reset_floor_state", None)
        if not all(callable(operation) for operation in (cancel, reset_smoothing, reset_floor)):
            raise RuntimeError("visualizer BeatEngine has no canonical reset contract")
        cancel()
        reset_smoothing()
        reset_floor()
    except Exception:
        if recover is not None and recover(progress.step):
            return None
        raise
    finally:
        end(reason=f"quick_{kind}_change:{target}")

    progress.stage, progress.step = "bind", "bind_fresh_target"
    generation = int(engine.get_generation_id())
    activation_id = int(engine.get_activation_id())
    state = controller.logical_tick_state
    state._pending_engine_generation = generation
    state._pending_engine_activation_id = activation_id
    state._waiting_for_fresh_engine_frame = True
    state._waiting_for_fresh_frame = True
    return generation, activation_id


# ------------------------------------------------------------------------------------------------ engine edges


def apply_playback_edge(controller: Any, playing: bool, *, started: bool) -> Any:
    """Media's playback truth onto the controller and its engine; the engine.

    On resume (and only once the host has started) ``wake`` first: the historical pause->play contract wakes the sole
    shared capture owner before committing playback truth (it restarts a stale capture, otherwise a cheap no-op).
    Then the engine's playback state (pause schedules the warm-capture stop after its grace; play restarts the
    reactivity ramp unless capture stayed warm), and on resume the warm re-entry fence on the engine's commit
    sequence. A same-state call commits the state with no edge.
    """
    active = bool(playing)
    previous = bool(controller.playing)
    controller.playing = active
    engine = controller.ensure_engine()
    if active and not previous and started:
        wake = getattr(engine, "wake", None)
        if callable(wake):
            wake()
    set_playback_state = getattr(engine, "set_playback_state", None)
    if not callable(set_playback_state):
        raise RuntimeError("visualizer BeatEngine has no playback-state authority")
    set_playback_state(active)
    if active and not previous:
        # Lead E1: warm resume must not admit the pre-pause retained frame as the first reactive result. Arm the
        # commit-seq watermark so the first accepted reactive frame is one the engine committed after this resume
        # edge. Cold engines are left unfenced (see the helper).
        from widgets.spotify_visualizer.tick_pipeline import arm_reentry_fresh_frame_fence

        arm_reentry_fresh_frame_fence(controller.logical_tick_state, engine)
    return engine


def prepare_engine_start(controller: Any) -> Any:
    """``start``'s first half: the engine, bound to the controller's ``ThreadManager`` and runtime generation."""
    engine = controller.ensure_engine()
    set_thread_manager = getattr(engine, "set_thread_manager", None)
    if controller.thread_manager is not None and callable(set_thread_manager):
        set_thread_manager(controller.thread_manager)
    set_generation = getattr(engine, "set_runtime_generation", None)
    if callable(set_generation):
        set_generation(controller.runtime_generation)
    return engine


def admit_engine_start(
    controller: Any,
    engine: Any,
    *,
    on_acquired: Callable[[], None],
    commit_playback: Callable[[bool], Any] | None = None,
) -> None:
    """``start``'s second half: the host's engine reference (``on_acquired`` once it is held, so a failure after it
    can release it), Media's state committed with no edge (``commit_playback``, by default ``apply_playback_edge``),
    then the cold capture admission when playing."""
    acquire = getattr(engine, "acquire", None)
    if callable(acquire):
        acquire()
        on_acquired()
    if commit_playback is None:
        apply_playback_edge(controller, controller.playing, started=False)
    else:
        commit_playback(controller.playing)
    if controller.playing:
        # Media may have committed True before start acquired the source and bound ThreadManager. Same-state
        # playback does not create a BeatEngine edge, so cold admission is explicit here.
        ensure_started = getattr(engine, "ensure_started", None)
        if callable(ensure_started):
            ensure_started()


def release_engine_started_parked(engine: Any, *, display_on: bool, engine_acquired: bool) -> bool:
    """``start``'s tail while the displays are off: the runtime started parked, so the host holds no capture
    reference until they come back. Whether the reference was released (the host's resume re-acquires it)."""
    if display_on or not engine_acquired:
        return False
    release = getattr(engine, "release", None)
    if callable(release):
        release()
    return True


def start_logical_cadence(
    controller: Any,
    *,
    interval_s: float | None = None,
    step: Callable[[float], None] | None = None,
) -> Any:
    """Start (or return) the controller's one logical runtime: ``VisualizerLogicalRuntime``, the cadence owner (one
    non-Qt thread, a monotonic deadline sequence, missed deadlines skipped, parking with no wake cadence). ``step``
    (the step's wake time in: the runtime's ``perf_counter`` read just before the step, not its deadline) defaults to the tick on the controller's tick state; ``interval_s`` to the authored
    cadence. A runtime started while the controller is parked starts parked."""
    from widgets.spotify_visualizer.tick_pipeline import logical_tick

    # Warm the first-publish import chain here, during activation and before the cadence thread starts, so the
    # first logical tick does not pay the one-shot cold import of the immutable frame-capture module (and its
    # render-state / config-applier / frame-runtime deps) on the cadence thread's first step. This moves a one-shot
    # activation cost off the first frame; it adds no per-frame work (the import is a no-op once cached) and does
    # not change the authored cadence.
    from widgets.spotify_visualizer import logical_frame_capture  # noqa: F401

    interval = float(interval_s) if interval_s is not None else 1.0 / max(15.0, DEFAULT_LOGICAL_HZ)
    if step is None:
        state = controller.logical_tick_state

        def step(_deadline_ts: float, _state: Any = state) -> None:
            logical_tick(_state)

    return controller.start_logical_runtime(step=step, interval_s=interval)


def release_engine_for_park(controller: Any, *, engine_acquired: bool) -> bool:
    """Display power off, engine side: release the host's engine reference (capture and analysis stop when it was
    the last). Whether a reference was released (the host re-acquires it on resume)."""
    if not engine_acquired:
        return False
    release = getattr(controller.engine, "release", None)
    if callable(release):
        release()
    return True


def resume_engine_after_park(
    controller: Any,
    *,
    started: bool,
    released_for_display_power: bool,
    on_reacquired: Callable[[], None],
) -> Any:
    """Display power on, logical side (before the host unparks its cadence): the engine reference and capture come
    back (``on_reacquired`` once held), the fresh-frame fence is armed (no retained pre-off audio frame is admitted as
    the first reactive result) and every logical last-step clock is rebased while the runtime is still parked (the
    first resumed step integrates no parked gap). A host that never started has nothing to resume. The engine, or
    None."""
    engine = controller.ensure_engine() if started else None
    if engine is None:
        return None
    if released_for_display_power:
        acquire = getattr(engine, "acquire", None)
        if callable(acquire):
            acquire()
        on_reacquired()
        if controller.playing:
            ensure_started = getattr(engine, "ensure_started", None)
            if callable(ensure_started):
                ensure_started()
    from widgets.spotify_visualizer.tick_pipeline import (
        arm_reentry_fresh_frame_fence,
        rebase_logical_clocks_after_park,
    )

    state = controller.logical_tick_state
    arm_reentry_fresh_frame_fence(state, engine)
    runtime = controller.logical_runtime
    if runtime is None or not runtime.is_running() or runtime.is_parked():
        rebase_logical_clocks_after_park(state, controller.logical_mode_states_snapshot())
    else:
        logger.error("[SPOTIFY_VIS][DISPLAY_POWER] Resume found the logical runtime unparked; clocks not rebased")
    return engine


def park_logical_side(
    controller: Any,
    *,
    engine_acquired: bool,
    clear_reader: Callable[[], None] | None = None,
) -> bool:
    """Display power off, logical side, in the owner's order: the cadence parks first (returns once no step is in
    flight; a runtime started later honours the request), then the host's reader-side clear (the owner drops its
    unread frame; the worker has none), then the engine reference goes (``release_engine_for_park``). Whether a
    reference was released."""
    if not controller.set_logical_parked(True):
        logger.error("[SPOTIFY_VIS][DISPLAY_POWER] Logical runtime did not park; it stays requested")
    if clear_reader is not None:
        clear_reader()
    return release_engine_for_park(controller, engine_acquired=engine_acquired)


def unpark_logical_side(
    controller: Any,
    *,
    started: bool,
    released_for_display_power: bool,
    on_reacquired: Callable[[], None],
) -> Any:
    """Display power on, logical side: ``resume_engine_after_park`` while the cadence is still parked (the clocks
    rebase only then), then the cadence unparks on a fresh deadline sequence. The engine, or None."""
    engine = resume_engine_after_park(
        controller,
        started=started,
        released_for_display_power=released_for_display_power,
        on_reacquired=on_reacquired,
    )
    controller.set_logical_parked(False)
    return engine


# ------------------------------------------------------------------------- presentation inputs (work order 5.4)

#: The view records the logical capture's pose evaluation reads (``view_orbit``): held-key orbit, framed flight, drag
#: inertia, Auto Rotate. Written on the GUI thread by Edit's orbit, the camera keys, a preset's activation and Home.
VIEW_RECORD_ATTRS = ("_view_orbit_motion", "_view_framed_flight_motion", "_view_orbit_inertia",
                     "_view_orbit_auto_rotate")
_PRESENTATION_INPUT_ATTRS: dict[str, tuple[str, ...]] = {}
_ALL_PRESENTATION_INPUT_ATTRS: set[str] = set()


def presentation_input_attrs(mode_id: str) -> tuple[str, ...]:
    """The presentation-state attributes ``mode_id``'s logical capture reads that change at runtime without an
    activation (native core P2b, work order 5 slice 5.4; checkpoint audit 7, A7-M1/A7-M2): the view records, the
    resolved 3D Detail tier, and the mode's presentation-only controls (its turn and tilt, framed camera, scene
    transform, mirror, finish...: Edit's orbit and camera writes, Home, live presentation tweaks). Registry data,
    resolved once per mode."""
    attrs = _PRESENTATION_INPUT_ATTRS.get(mode_id)
    if attrs is None:
        from core.settings.visualizer_mode_settings import control_runtime_attr, require_mode_settings

        found = [*VIEW_RECORD_ATTRS, "_scene3d_detail"]
        try:
            controls = require_mode_settings(mode_id).body_controls
        except (KeyError, ValueError):
            controls = ()
        for control in controls:
            attr = control_runtime_attr(control)
            if not control.logical and attr not in found:
                found.append(attr)
        attrs = tuple(found)
        _PRESENTATION_INPUT_ATTRS[mode_id] = attrs
        _ALL_PRESENTATION_INPUT_ATTRS.update(attrs)
    return attrs


def presentation_inputs_snapshot(presentation_state: Any, mode_id: str) -> dict[str, Any]:
    """The values of ``presentation_input_attrs(mode_id)`` the engine worker's tick needs (the main side's, forwarded
    latest-wins with the framed view): plain data only. The values are the state's own, read every presentation and
    compared by value with the last send; only a changed one is copied, by ``detach_presentation_value``, into the send
    and the record of what the session holds (checkpoint audit 8, A8-L6).

    A Qt value never crosses (the worker loads QtCore only, and a pickled Qt object would drag its module in), and it
    is never dropped silently either (phase-boundary audit L4): a colour goes as the (r, g, b, a) the in-process
    capture freezes it to (``plain_presentation_value``); any other Qt value is refused with one error per attribute
    and type (``report_unforwarded_presentation_input``), as the in-process capture refuses it
    (``render_state.freeze_render_value``'s TypeError), and the session keeps the value it holds."""
    values: dict[str, Any] = {}
    for attr in presentation_input_attrs(mode_id):
        value = getattr(presentation_state, attr, None)
        if type(value).__module__.startswith("PySide6"):
            try:
                value = plain_presentation_value(value)
            except TypeError as exc:
                report_unforwarded_presentation_input(attr, exc)
                continue
        values[attr] = value
    return values


_UNFORWARDED_REPORTED: set[tuple[str, str]] = set()


def report_unforwarded_presentation_input(attr: str, failure: Exception) -> None:
    """One error per attribute and failure for a presentation input the engine worker's session cannot be given (a Qt
    value with no plain form): the worker's tick keeps the value its session holds, so the Visualizer on the worker
    would differ from in process for as long as the state holds it. Once, never per presentation."""
    key = (str(attr), str(failure))
    if key in _UNFORWARDED_REPORTED:
        return
    _UNFORWARDED_REPORTED.add(key)
    logger.error("[SPOTIFY_VIS][ENGINE_WORKER] Presentation input %s is not forwarded to the engine worker: %s "
                 "(the session keeps the value it holds)", attr, failure)


def plain_presentation_value(value: Any) -> Any:
    """A Qt value's plain form for the engine worker: a colour as the (r, g, b, a) ``getRgb()`` gives, what the
    in-process capture freezes it to (``render_state.freeze_render_value``) and what the Qt-free presentation config
    holds (``config_applier._color_or_none``). Any other Qt value has none: TypeError, as in the capture."""
    get_rgba = getattr(value, "getRgb", None)
    if callable(get_rgba):
        return tuple(int(channel) for channel in get_rgba()[:4])
    raise TypeError(f"a {type(value).__name__} has no plain form")


def detach_presentation_value(value: Any) -> Any:
    """``value`` with every nested list and dict copied (the same types), so the copy shares nothing mutable with the
    presentation state: an in-place edit of the state's value then compares unequal to the copy and is forwarded
    (A8-L6: Waveform Ribbon's palette is a dict of lists). Immutable values come back as they are; a Qt value nested
    in one goes as its plain form or raises TypeError (``plain_presentation_value``: it never leaves the process)."""
    kind = type(value)
    if kind is list:
        return [detach_presentation_value(item) for item in value]
    if kind is dict:
        return {key: detach_presentation_value(item) for key, item in value.items()}
    if kind is tuple and any(type(item) in (list, dict, tuple) or type(item).__module__.startswith("PySide6")
                             for item in value):
        return tuple(detach_presentation_value(item) for item in value)
    if kind.__module__.startswith("PySide6"):
        return plain_presentation_value(value)
    return value


def apply_presentation_inputs(presentation_state: Any, values: Mapping[str, Any]) -> None:
    """The worker side of ``presentation_inputs_snapshot``: each forwarded attribute onto the session's presentation
    state (only the attributes some mode forwards; anything else is refused)."""
    for attr, value in values.items():
        if attr not in _ALL_PRESENTATION_INPUT_ATTRS:
            # A mode this process has not resolved yet: resolve every mode's set once, then check again.
            from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors

            for descriptor in iter_all_visualizer_mode_descriptors():
                presentation_input_attrs(descriptor.mode_id)
            if attr not in _ALL_PRESENTATION_INPUT_ATTRS:
                raise ValueError(f"not a forwarded presentation input: {attr!r}")
        setattr(presentation_state, attr, value)


__all__ = [
    "CONFIGURE_REASON",
    "VIEW_RECORD_ATTRS",
    "apply_presentation_inputs",
    "detach_presentation_value",
    "plain_presentation_value",
    "report_unforwarded_presentation_input",
    "presentation_input_attrs",
    "presentation_inputs_snapshot",
    "DEFAULT_LOGICAL_HZ",
    "ActivationProgress",
    "LogicalRuntimeNotJoined",
    "admit_engine_start",
    "apply_logical_configuration",
    "apply_playback_edge",
    "commit_logical_activation",
    "configure_logical_controller",
    "mode_runtime_factory",
    "park_logical_side",
    "prepare_engine_start",
    "record_activation_inputs",
    "release_engine_for_park",
    "release_engine_started_parked",
    "resume_engine_after_park",
    "start_logical_cadence",
    "unpark_logical_side",
]
