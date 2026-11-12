"""Thin Quick per-display visualizer ownership edge (H).

This is the small destination-side assembly that owns one
``VisualizerRuntimeController`` per display/generation and binds it into a
``QuickDisplayRuntime``. It invents no visualizer subsystem: the controller
already owns mode/settings, the shared BeatEngine/source, the authored
``VisualizerLogicalRuntime`` and controller-owned logical tick state, viewport
configuration and render-bridge publication.

Native core P2b (work order 5): by default (``experiment_flags.visualizer_engine_worker_admitted``, read once per
construction; ``--viz-in-process`` keeps the in-process path; on Linux the default is source-level only, never run:
``Linux_Plan.md``), the owner runs its Visualizer on the
engine worker (``engine_worker_link``): the controller keeps no beat engine and runs no tick; each control edge below
is sent to the ``WorkerType.VISUALIZER`` session, and the worker's frames reach the same presentation path through the
controller's logical mailbox (the session's frame mapping, read side). A worker that cannot run (no process
supervisor) or fails to configure or start leaves that activation in process; a session that ends later is replaced
once (the held frame fades out, the new session fades in), and a second failure before that replacement is revealed,
or a failure once the run's recoveries are spent (``engine_worker_link.MAX_RECOVERIES_PER_RUN``), keeps the owner in
process for the run. In process, every edge runs here: the controller's beat engine, capture, DSP and the tick.
"""

from __future__ import annotations

import math
import time
from dataclasses import replace
from typing import Any, Callable, Mapping

from core.logging.logger import get_logger, is_viz_diagnostics_enabled
from rendering.quick.lifecycle_errors import RetainedRuntimeIncoherenceError
from widgets.spotify_visualizer.render_state import (
    CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
)
from core.authored_clock import authored_now
from widgets.spotify_visualizer.logical_edges import (
    ActivationProgress,
    LogicalRuntimeNotJoined,
    DEFAULT_LOGICAL_HZ,
    admit_engine_start,
    apply_logical_configuration,
    apply_playback_edge,
    commit_logical_activation,
    configure_logical_controller,
    mode_runtime_factory,
    park_logical_side,
    prepare_engine_start,
    release_engine_started_parked,
    start_logical_cadence,
    unpark_logical_side,
)

logger = get_logger(__name__)

_DEFAULT_MAX_FPS = DEFAULT_LOGICAL_HZ
_MODE_TRANSITION_HALF_DURATION_S = 0.25
# Authored first-appearance reveal for the visualizer scene fade. The whole
# visualizer (card + GL content) eases up from zero once per activation so it
# never snaps in when its heavy first frame lands outside the coordinated
# startup-reveal window. This is the visualizer's own single scene-fade
# authority; the generation startup-reveal gate is a separate root multiplicand.
_ACTIVATION_SCENE_FADE_DURATION_S = 1.3
# A ``prepared_reveal`` target stays hidden while the render thread prepares its renderer on
# the hidden frames (one spaced unit each, ``QuickVisualizerRenderHost``), so its first-use
# compile and allocation land behind the fade; past this it reveals anyway and the renderer
# finishes on its first visible frame, as before (a window that renders nothing cannot strand
# the activation or its completion).
_PREPARED_REVEAL_DEADLINE_S = 1.5
# One Qt GUI-thread single-shot guard per REQUEST, not a polling/display ticker.
# It protects all transition phases, including no logical publication at all.
# Actual prepared-reveal deadline above is shorter and remains unchanged.
_ACTIVATION_TRANSACTION_DEADLINE_MS = 6000
# A committed target is slow but alive when the render thread completed a preparation unit for it since the deadline
# was armed (or last extended): one unit can be a multi-second driver link, and the GUI thread waits in Qt's sync for
# it, so the overdue single-shot fires the moment the link returns (R-180). Such a deadline is extended, at most this
# many times; a target with no render progress in a whole window fails as before (one fenced reconstruction).
_SLOW_TARGET_DEADLINE_EXTENSIONS = 4


class _TakeoverFade:
    """One display-wide viewport change in flight (Expanded Visualizer, plan 01 §D1.7/§D2.4).

    The whole Visualizer presentation fades out where it is, the viewport swaps at the midpoint, and it fades in
    at the target: one GL target reallocation, at the swap, never one per frame of a geometry tween. It is sampled
    on the existing publication edge against the owner's transition clock, like the activation and mode fades; it
    owns no timer.
    """

    __slots__ = ("target", "source", "started_at", "on_complete", "drawn_expanded", "done", "move",
                 "source_style", "target_style", "drawn_target")

    def __init__(self, *, target: bool, source: bool, started_at: float,
                 on_complete: Callable[[], None] | None, source_style: str = "default",
                 target_style: str = "default") -> None:
        self.target = target
        self.source = source
        self.started_at = started_at
        self.on_complete = on_complete
        self.drawn_expanded = source
        self.done = False
        #: A fade-through across two displays (1C.2): its midpoint is the move (``_DisplayMove``).
        self.move: _DisplayMove | None = None
        #: The display style (1D.2) each side draws when it is display-wide, and whether the target side is drawn now
        #: (an expanded-to-expanded fade-through, a style change, has the same ``drawn_expanded`` on both sides).
        self.source_style = source_style
        self.target_style = target_style
        self.drawn_target = False

    @property
    def drawn_style(self) -> str:
        return self.target_style if self.drawn_target else self.source_style


# The prewarmed target's card while its renderer prepares (1C.2): below one 8-bit level, so nothing shows, yet above
# Qt Quick's opacity cut (a subtree under 0.001 is not rendered, and an unrendered node prepares nothing).
_PREWARM_SCENE_FADE = 0.002


class _DisplayMove:
    """One display move as one fade-through (1C.2): warm the target while the source draws, fade out, move the
    admission at zero opacity (``hop``), wait for the source's render-thread history to land, fade in on the target."""

    __slots__ = ("target_runtime", "hop", "on_fade_out", "on_fade_in", "on_complete", "stage", "stage_at",
                 "moved", "identity", "prewarm_scene", "fade_out_due", "fade_in_due")

    def __init__(self, target_runtime: Any, hop: Callable[[], bool], on_fade_out: Callable[[], None] | None,
                 on_fade_in: Callable[[bool], None] | None, on_complete: Callable[[bool], None] | None,
                 started_at: float) -> None:
        self.target_runtime = target_runtime
        self.hop = hop
        self.on_fade_out = on_fade_out
        self.on_fade_in = on_fade_in
        self.on_complete = on_complete
        self.stage = "warm"          # warm -> out -> hop -> hold -> in
        self.stage_at = started_at
        self.moved: bool | None = None
        self.identity: Any = None
        self.prewarm_scene: Any = None
        self.fade_out_due = False
        self.fade_in_due = False


def _expanded_display_size(runtime: Any, style: str) -> tuple[float, float]:
    """The display size the display-wide record is resolved on (1D.2).

    Default keeps today's input, the display identity's geometry (Qt's whole-logical screen size), so its record is
    unchanged. A style whose card meets the display's edges uses the display's exact laid-out size (the window's
    on-desktop rect, ``visible_display_size``): on 2560 px at 150 % Qt's 1707 would put the card's right edge half a
    device pixel past the monitor, and the snapped frame one pixel off it. Before the window publishes that rect
    (an unshown window), the identity's geometry stands in.
    """

    _x, _y, width, height = runtime.display_identity.geometry
    if style != "default":
        getter = getattr(getattr(runtime, "scene_controller", None), "visible_display_size", None)
        size = getter() if callable(getter) else None
        if size is not None:
            return (float(size[0]), float(size[1]))
    return (float(width), float(height))


def _shared_beat_engine(bar_count: int) -> Any:
    """The production engine factory: the registry's one shared beat engine (imported on first use, so building
    an owner imports no capture code)."""
    from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine
    return get_shared_spotify_beat_engine(bar_count)


# The canonical descriptor wiring's frame-runtime factory (one owner: ``logical_edges``).
_mode_runtime_factory = mode_runtime_factory

_in_process_path_noted = False


def _note_in_process_path() -> None:
    """Say once per process why the Visualizer runs in process when the engine worker is the product's default:
    the diagnostic ``--viz-in-process`` choice, or a platform whose default is in process (``[PLATFORM]``; none
    today: ``experiment_flags.visualizer_engine_worker_platform_default``). The worker's own fallbacks log at their
    failure."""
    global _in_process_path_noted
    if _in_process_path_noted:
        return
    _in_process_path_noted = True
    from core.diagnostics.experiment_flags import (
        active_experiment_flags,
        visualizer_engine_worker_platform_default,
    )

    if active_experiment_flags().visualizer_engine_worker is False:
        logger.info("[SPOTIFY_VIS][ENGINE_WORKER] --viz-in-process: the Visualizer runs in process for this run")
    elif not visualizer_engine_worker_platform_default():
        logger.info("[PLATFORM] Visualizer engine worker: this platform's default is the in-process path")


class QuickDisplayVisualizerOwner:
    """Own + bind one visualizer controller for one Quick display generation."""

    # Console display power defaults (on); __init__ and set_display_power own the instance values.
    _display_power_on = True
    _engine_released_for_display_power = False
    # Expanded Visualizer route defaults (ordinary); __init__ and set_expanded_display own the instance values.
    _expanded_display = False
    _takeover: "_TakeoverFade | None" = None
    _expanded_source: Any = None
    _expanded_overlays_drawn = False
    _expanded_display_style = "default"
    # Engine-worker path class defaults (in process until __init__ reads the path); the worker path owns the values.
    _engine_worker_admitted = False
    _retiring = False            # set first by retire(), joined or not (A9-L1)
    _worker: Any = None
    _worker_identity: "tuple[int, int] | None" = None
    _worker_failures = 0
    _worker_recovery: "dict[str, Any] | None" = None
    _recovery_held: "tuple[Any, float] | None" = None
    _activation_inputs: "dict[str, Any] | None" = None
    _configure_services: Mapping[str, Any] = {}
    _view_dirty = False
    _in_sync_present = False
    _worker_commit: "dict[str, Any] | None" = None
    _bind_deferred = False
    _recovery_stage = 0
    _worker_playback_edges = 0
    _display_power_edges = 0
    _frame_completion: Any = None
    # The fade a crossfade's fade-out starts from: the fade drawn at the request (1.0 whenever the owner is idle).
    _fade_out_from = 1.0

    def __init__(
        self,
        runtime: Any,
        *,
        bar_count: int,
        initial_mode: str,
        engine_factory: Callable[[int], Any] | None = None,
        presentation_resolver: Callable[[], Any] | None = None,
        committed_layout_profile_resolver: Callable[[str], tuple[
            tuple[float, float, float, float], tuple[float, float] | None, object
        ] | None] | None = None,
        edit_layout_profile_activator: Callable[[str], bool] | None = None,
        card_shadow_kwargs: Mapping[str, object],
        transition_failure_callback: Callable[[str], None] | None = None,
        transition_clock: Callable[[], float] | None = None,
        transition_half_duration_s: float = _MODE_TRANSITION_HALF_DURATION_S,
    ) -> None:
        from widgets.spotify_visualizer.runtime_controller import (
            VisualizerRuntimeController,
        )

        self._runtime = runtime
        self._presentation_runtime = runtime
        self._controller = VisualizerRuntimeController(
            runtime_generation=runtime.runtime_generation,
            bar_count=int(bar_count),
            initial_mode=str(initial_mode),
            # The production owner is where the process's one beat engine enters a controller.
            engine_factory=engine_factory if engine_factory is not None else _shared_beat_engine,
        )
        self._controller.logical_mailbox.set_trace_screen_index(
            int(runtime.screen_index)
        )
        self._presentation_resolver = presentation_resolver
        # The DisplayManager resolves this through the one canonical
        # ``custom_layout`` map.  It is consulted only at the hidden mode
        # activation boundary, never from the logical/render cadence.
        self._committed_layout_profile_resolver = committed_layout_profile_resolver
        self._edit_layout_profile_activator = edit_layout_profile_activator
        required_card_fields = {
            "background_color",
            "border_color",
            "border_width",
            "corner_radius",
            "content_inset",
            "shadow_enabled",
            "shadow_color",
            "shadow_blur",
            "shadow_offset",
            "shadow_spread",
            "shadow_extensions",
        }
        self._card_shadow_kwargs = dict(card_shadow_kwargs)
        missing_card_fields = required_card_fields.difference(self._card_shadow_kwargs)
        if missing_card_fields:
            raise ValueError(
                "resolved visualizer card style is incomplete: "
                + ", ".join(sorted(missing_card_fields))
            )
        self._transition_clock = transition_clock or time.perf_counter
        self._transition_half_duration_s = max(
            0.0, float(transition_half_duration_s)
        )
        self._committed_layout_rect: tuple[float, float, float, float] | None = None
        self._committed_layout_extent: tuple[float, float] | None = None
        self._legacy_layout_profile: str | None = None
        self._legacy_layout_source_variant: str | None = None
        self._authored_outer_origin: tuple[float, float] = (0.0, 0.0)
        self._mode_transition_phase = "idle"
        self._mode_transition_started_at = 0.0
        self._mode_transition_fade = 1.0
        # (mode, activation id) the waiting target's reveal holds for, and since when.
        self._preparing_activation: tuple[str, int] | None = None
        # (activation, its preparation units last seen, when they last advanced): the reveal's liveness bound.
        self._preparing_progress: tuple[tuple[str, int], int, float] | None = None
        # (request serial, preparation units at the last deadline, extensions): slow-but-alive deadline state.
        self._deadline_liveness: tuple[int | None, int, int] = (None, 0, 0)
        self._waiting_target_since = 0.0
        # ``None`` until the owner first starts: any presentation resolved before
        # then is fully opaque (never hidden). Once armed, the authored scene
        # fade eases 0 -> 1 over ``_ACTIVATION_SCENE_FADE_DURATION_S`` sampled
        # against the same clock the mode-transition fade already uses.
        self._activation_fade_started_at: float | None = None
        self._pending_mode_activation: dict[str, Any] | None = None
        self._transition_failure_callback = transition_failure_callback
        self._transition_request_serial = 0
        self._transition_recovery_issued = False
        self._sync: Any = None
        self._publication_wake: Any = None
        self._configured = False
        self._started = False
        self._bound = False
        self._engine_acquired = False
        self._retired = False
        self._render_identity: Any = None
        # Console display power (core.display_power), applied by DisplayManager.
        self._display_power_on = True
        self._engine_released_for_display_power = False
        # Expanded Visualizer (plan 01 M2): the display-wide viewport is a presentation route, swapped at event
        # edges only. ``_expanded_display`` is the committed route; ``_takeover`` a fade-through in flight;
        # ``_expanded_source`` the ordinary record the last display-wide one derived from (its metrics, never the
        # display-wide ones, reach the controller, so the ordinary geometry round-trips untouched).
        self._expanded_display = False
        self._takeover: _TakeoverFade | None = None
        # A neighbouring display prepared ahead of Edit's hop or a hover transfer arrow (1C.2): (runtime, scene), from
        # the edge that begins it (``prepare_display``) to the edge that ends it or the hop that adopts it.
        self._neighbour_prewarm: tuple[Any, Any] | None = None
        self._expanded_source: Any = None
        # The full-display overlays (plan 01 §G, M3b) exist only while the display-wide card is drawn and the displays
        # are on; the last value projected to the scene, so it is written at its edges only.
        self._expanded_overlays_drawn = False
        # The display-wide card's display style (Current_Plan 1D.2; Settings' ``fullscreen_overlays.display_style``,
        # pushed by the display manager): what the display-wide route draws. A change while expanded retargets the
        # card in place through the expanded-to-expanded fade-through; a change while collapsed applies at the next
        # expansion. The ordinary record never depends on it.
        self._expanded_display_style = "default"
        # Native core P2b: the process path, read once per construction (never an environment flag): the engine worker
        # by default, in process when ``--viz-in-process`` chose it. ``_worker`` is the live
        # ``engine_worker_link.EngineWorkerLink`` while this owner runs on the worker (None: in process);
        # ``_worker_identity`` its engine's (generation, activation id); ``_activation_inputs`` the current
        # activation's resolved inputs (a reconfigure or the in-process fallback re-applies them).
        from core.diagnostics.experiment_flags import visualizer_engine_worker_admitted

        self._engine_worker_admitted = bool(visualizer_engine_worker_admitted())
        if not self._engine_worker_admitted:
            _note_in_process_path()
        self._worker: Any = None
        self._worker_identity: tuple[int, int] | None = None
        self._worker_failures = 0
        self._worker_recovery: dict[str, Any] | None = None
        self._recovery_held: tuple[Any, float] | None = None
        self._activation_inputs: dict[str, Any] | None = None
        self._configure_services: dict[str, Any] = {}
        # Slice 5.5: a hidden activation's commit in flight (its reply binds the target), a first bind waiting for the
        # configure's reply, and the recovery's deadline stage (0 none, 1 the replacement, 2 after the fallback).
        self._worker_commit: dict[str, Any] | None = None
        self._bind_deferred = False
        self._recovery_stage = 0
        self._fade_out_from = 1.0
        # Audit 8: the display-power edges sent to the worker (only the newest one's reply acts, A8-L3) and the reader's
        # frame completion (the reflected wallpaper, per session, released with it: A8-L1).
        self._display_power_edges = 0
        self._frame_completion: Any = None

    @property
    def controller(self) -> Any:
        return self._controller

    @property
    def display_power_on(self) -> bool:
        return self._display_power_on

    def set_display_power(self, on: bool) -> bool:
        """Park the Visualizer while the console displays are off; resume it warm.

        Off: the sole logical runtime parks (its thread blocks with no cadence,
        all simulation state stays warm), the unread publication is dropped so
        it cannot be shown hours later, and this owner's engine reference is
        released, which stops audio capture and analysis when it was the last.
        On: the engine reference and capture come back, the fresh-frame fence
        is armed (no retained pre-off audio frame is admitted as the first
        reactive result), every logical last-step clock is rebased (the first
        resumed step integrates no parked gap) and the runtime resumes on a new
        deadline sequence. Ordinary Play/Pause and mode/preset activation keep
        their own owners; an activation that lands while off starts parked.
        Returns whether the state changed.
        """

        if self._retired:
            return False
        on = bool(on)
        if on == self._display_power_on:
            return False
        controller = self._controller
        self._display_power_on = on
        self._project_expanded_overlays()
        if self._recovery_stage:
            # An engine-worker recovery in flight (on the worker, or after its fallback in process): no held frame
            # survives a park (A7-L3); the unpark re-arms its deadline.
            if not on:
                self._drop_recovery_hold()
            else:
                self._rearm_recovery_deadline()
        if self._worker is not None:
            return self._set_display_power_on_worker(on)
        if not on:
            if park_logical_side(controller, engine_acquired=self._engine_acquired,
                                 clear_reader=controller.logical_mailbox.clear):
                self._engine_acquired = False
                self._engine_released_for_display_power = True
            logger.info("[SPOTIFY_VIS][DISPLAY_POWER] Visualizer parked mode=%s", controller.mode_id)
            return True
        unpark_logical_side(
            controller,
            started=self._started,
            released_for_display_power=self._engine_released_for_display_power,
            on_reacquired=self._on_engine_reacquired_for_display_power,
        )
        logger.info("[SPOTIFY_VIS][DISPLAY_POWER] Visualizer resumed mode=%s", controller.mode_id)
        return True

    def _on_engine_reacquired_for_display_power(self) -> None:
        self._engine_acquired = True
        self._engine_released_for_display_power = False

    @property
    def render_identity(self) -> Any:
        return self._render_identity

    @property
    def presentation_runtime(self) -> Any:
        return self._presentation_runtime

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def is_retired(self) -> bool:
        return self._retired

    def configure(
        self,
        *,
        logical_kwargs: Mapping[str, Any] | None = None,
        presentation_kwargs: Mapping[str, Any] | None = None,
        technical_config: Mapping[str, Any] | None = None,
        thread_manager: Any | None = None,
        process_supervisor: Any | None = None,
        playing: bool = False,
        activation: Mapping[str, Any] | None = None,
    ) -> None:
        """The first activation's configuration (``logical_edges.configure_logical_controller``, shared with the
        engine worker's session): ``activation`` is what the host binding resolved (settings model, resolved
        activation, technical cache; None keeps what the controller holds)."""
        if self._retired:
            raise RuntimeError("cannot configure a retired visualizer owner")
        if (self._engine_worker_admitted and not self._configured and activation is not None
                and logical_kwargs is not None and presentation_kwargs is not None):
            inputs = {**dict(activation), "logical_kwargs": dict(logical_kwargs),
                      "presentation_kwargs": dict(presentation_kwargs)}
            self._configure_services = {"thread_manager": thread_manager, "process_supervisor": process_supervisor}
            if self._configure_on_engine_worker(inputs, playing=playing):
                self._configured = True
                return
        configure_logical_controller(
            self._controller,
            activation=activation,
            logical_kwargs=logical_kwargs,
            presentation_kwargs=presentation_kwargs,
            technical_config=technical_config,
            thread_manager=thread_manager,
            process_supervisor=process_supervisor,
            playing=playing,
            refresh_presentation=self._refresh_backdrop,
        )
        self._configured = True

    def _apply_configuration(
        self,
        *,
        logical_kwargs: Mapping[str, Any] | None,
        presentation_kwargs: Mapping[str, Any] | None,
        technical_config: Mapping[str, Any] | None,
        thread_manager: Any | None,
        process_supervisor: Any | None,
        playing: bool,
        reason: str,
    ) -> None:
        apply_logical_configuration(
            self._controller,
            logical_kwargs=logical_kwargs,
            presentation_kwargs=presentation_kwargs,
            technical_config=technical_config,
            thread_manager=thread_manager,
            process_supervisor=process_supervisor,
            playing=playing,
            reason=reason,
            refresh_presentation=self._refresh_backdrop,
        )

    def _refresh_backdrop(self) -> None:
        """Keep the reflected wallpaper (``backdrop.py``) while the active mode reflects it (its
        descriptor's ``backdrop_setting`` above zero, on a tier with reflections), nothing
        otherwise: made once per displayed photograph, here on the GUI thread (~1.4 ms at 4K)."""
        from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
        from rendering.gl_programs.scene3d import scene3d_detail

        state = self._controller.presentation_state
        setting = get_visualizer_mode_descriptor(self._controller.mode_id).backdrop_setting
        reflects = (bool(setting) and float(getattr(state, f"_{setting}")) > 0.0
                    and scene3d_detail(state._scene3d_detail).reflections)
        # A running transition's incoming photograph wins: the reflection crossfades to it from the
        # transition's start, over its duration (the "seed" a transition already carries), so it
        # has finished changing when the scene adopts the photograph. Nothing is read unless the
        # mode reflects.
        incoming = image = None
        if reflects:
            scene = self._presentation_runtime.scene_controller
            incoming = scene.incoming_image
            image = incoming[0] if incoming is not None else scene.presentation_image
        current = getattr(state, "_backdrop", None)
        if image is None:
            if current is not None:
                state._backdrop = None
            return
        if current is not None and current.identity == image.identity:
            return
        from widgets.spotify_visualizer.backdrop import make_visualizer_backdrop

        state._backdrop = make_visualizer_backdrop(image)
        state._backdrop_blend_s = None if incoming is None else incoming[1]

    def engine_identity(self) -> tuple[int, int]:
        """The (engine generation, activation id) the host binding binds render admission for: the controller's
        engine's in process, the configured session's on the engine worker (which keeps no engine here; (-1, -1) until
        the configure's reply, which binds it: ``bind`` defers the render binding until then)."""
        if self._worker is not None:
            return self._worker_identity if self._worker_identity is not None else (-1, -1)
        engine = self._controller.engine
        return int(engine.get_generation_id()), int(engine.get_activation_id())

    def bind(self, *, engine_generation: int, activation_id: int) -> Any:
        if self._retired:
            raise RuntimeError("cannot bind a retired visualizer owner")
        if self._worker is not None and self._worker_identity is None:
            # The engine worker's configure is unanswered (never awaited, slice 5.5): its reply binds render admission
            # for the session's identity (``_on_worker_configured``); everything else binds now.
            self._bind_deferred = True
            self._render_identity = None
        else:
            self._render_identity = self._runtime.bind_visualizer_render_source(
                self._controller,
                engine_generation=int(engine_generation),
                activation_id=int(activation_id),
            )
        self._runtime.bind_visualizer_viewport_config(
            self._controller.set_custom_viewport_override, framed_view_sink=self._controller.set_framed_view
        )
        self._presentation_runtime.scene_controller.set_presentation_image_listener(self._refresh_backdrop)
        self._refresh_backdrop()
        from widgets.spotify_visualizer.quick_presentation_sync import (
            QuickVisualizerPresentationSync,
            QuickVisualizerPublicationWake,
        )

        self._sync = QuickVisualizerPresentationSync(
            self._controller,
            resolve_presentation=self._resolve_current_presentation,
            commit_presentation=self._apply_resolved_presentation,
            request_present=self._request_retained_present,
            resolve_screen_index=lambda: int(self._presentation_runtime.screen_index),
        )
        self._publication_wake = QuickVisualizerPublicationWake(self.sync_present)
        self._controller.logical_mailbox.set_wake_callback(
            self._publication_wake.request
        )
        self._controller.render_bridge.set_sync_admission(self._admit_latest_at_sync)
        self._bound = True
        return self._render_identity

    def _admit_latest_at_sync(self) -> bool:
        """Render thread, at Quick synchronization: the steady-state freshest-revision admission.

        Mode transitions keep their GUI-side, one-publication-per-wake fade
        sequencing, so they are left entirely to ``sync_present``.
        """

        sync = self._sync
        if self._retired or sync is None or self._mode_transition_phase != "idle":
            return False
        if self._worker is not None and self._worker_identity is None:
            return False                              # the engine worker's identity is not bound yet
        return sync.admit_latest_at_sync()

    def _request_retained_present(self) -> None:
        """Request one retained visualizer sync after a new revision is published.

        Wired into QuickVisualizerPresentationSync so each successful publication
        of a fresh logical revision marks the retained item dirty even when
        presentation geometry is unchanged; without it the retained render node
        synced once and then froze while logical cadence stayed healthy (observed
        in the 08_30_RuntimeSwap_03_37 run: sync_count=1, render/draw in the
        thousands). This targets the current presentation runtime so it follows a
        CUSTOM presentation transfer.
        """

        if self._retired:
            return
        requested = self._presentation_runtime.scene_controller.request_visualizer_present()
        if not requested:
            raise RuntimeError(
                "fresh visualizer publication has no retained presentation item"
            )
        neighbour = self._neighbour_prewarm
        if neighbour is not None:
            # A prepared neighbour (1C.2) draws the snapshot just published, so its render thread keeps preparing.
            neighbour[1].feed_visualizer_prewarm(self._controller.render_bridge.peek())

    def set_playing(
        self,
        playing: bool,
        *,
        observed_ts: float | None = None,
    ) -> None:
        """Apply canonical Media playback truth to logical + source owners."""

        if self._retired:
            return
        active = bool(playing)
        controller = self._controller
        previous = bool(controller.playing)
        if self._worker is not None:
            # Media stays the one owner of "playing": its edge goes to the session (a not yet started session
            # takes Media's state with its start, as the host binding's play edge before ``start``).
            controller.playing = active
            if self._started and active != previous:
                self._worker_set_playing(active, observed_ts)
            return
        edge_ts = float(observed_ts if observed_ts is not None else authored_now())
        edge_seq = 0
        if active != previous and is_viz_diagnostics_enabled():
            from widgets.spotify_visualizer.reactivity_diagnostics import (
                begin_playback_edge,
            )

            edge_seq = begin_playback_edge(
                controller.logical_tick_state,
                now_ts=edge_ts,
                playing=active,
            )
            logger.debug(
                "[VIS_PLAYBACK_EDGE] stage=T1 edge=%d mode=%s playing=%s ts=%.6f",
                edge_seq,
                controller.mode_id,
                active,
                edge_ts,
            )

        engine = apply_playback_edge(controller, active, started=self._started)
        if edge_seq > 0:
            committed_ts = authored_now()
            warm_resume = bool(
                active
                and float(getattr(engine, "_play_ramp_start_ts", 0.0) or 0.0) <= 0.0
            )
            logger.debug(
                "[VIS_PLAYBACK_EDGE] stage=T2 edge=%d mode=%s playing=%s dt_ms=%.1f "
                "engine=%s/%s warm_resume=%s",
                edge_seq,
                controller.mode_id,
                active,
                max(0.0, (committed_ts - edge_ts) * 1000.0),
                getattr(engine, "get_generation_id", lambda: -1)(),
                getattr(engine, "get_activation_id", lambda: -1)(),
                warm_resume,
            )

    def set_presentation_runtime(self, runtime: Any) -> bool:
        """Move the retained display edge while preserving one logical owner.

        CUSTOM cross-display transfer moves the actual VisualizerRenderItem. The
        frame-pacer/bind/retirement edge must move with it; leaving ``_runtime``
        on the source display lets a later preset/mode activation create a second
        dead admission there and lets retirement clean the wrong scene. No audio,
        logical runtime, controller, activation identity, or authored cadence is
        recreated here.
        """

        if self._retired:
            return False
        if runtime is self._presentation_runtime and runtime is self._runtime:
            return False

        old_presentation_runtime = self._presentation_runtime
        old_runtime = self._runtime
        old_presentation_runtime.scene_controller.set_visualizer_viewport_config_sink(None)
        old_presentation_runtime.scene_controller.set_presentation_image_listener(None)
        try:
            self._presentation_runtime = runtime
            self._runtime = runtime
            runtime.bind_visualizer_viewport_config(
                self._controller.set_custom_viewport_override, framed_view_sink=self._controller.set_framed_view
            )
            runtime.scene_controller.set_presentation_image_listener(self._refresh_backdrop)
            self._refresh_backdrop()      # the new display's own photograph
            self._controller.logical_mailbox.set_trace_screen_index(
                int(runtime.screen_index)
            )
            # Visualizer presentation is publication-driven, not display-pacer
            # driven. The one logical mailbox wake stays bound to this owner and
            # therefore follows whichever retained scene ``_presentation_runtime``
            # currently names without moving a timer/cadence owner.
            if self._started and self._controller.logical_mailbox.peek() is not None:
                wake = self._publication_wake
                if wake is not None:
                    wake.request()
        except Exception:
            # Transfer is one event-bound transaction. Restore the old display
            # edge rather than leave the logical owner attached to half a scene.
            try:
                runtime.scene_controller.set_visualizer_viewport_config_sink(None)
                runtime.scene_controller.set_presentation_image_listener(None)
            except Exception:
                logger.exception(
                    "[SPOTIFY_VIS] Failed clearing partial target viewport route"
                )
            self._presentation_runtime = old_presentation_runtime
            self._runtime = old_runtime
            self._controller.logical_mailbox.set_trace_screen_index(
                int(old_presentation_runtime.screen_index)
            )
            old_presentation_runtime.bind_visualizer_viewport_config(
                self._controller.set_custom_viewport_override, framed_view_sink=self._controller.set_framed_view
            )
            old_presentation_runtime.scene_controller.set_presentation_image_listener(self._refresh_backdrop)
            raise
        neighbour = self._neighbour_prewarm
        if neighbour is not None:
            # The hop that moved here adopted a neighbour prepared on this display (its renderer kept, nothing to
            # end); one prepared elsewhere is released.
            self._neighbour_prewarm = None
            if neighbour[1] is not runtime.scene_controller:
                self._end_prewarm_on(neighbour[1])
        return True

    def prepare_display(self, target_runtime: Any) -> bool:
        """Prepare ``target_runtime``'s display for a hop that may follow (1C.2): Edit's display hop and the hover
        transfer arrows move the live view at full opacity, so the target's renderer is built ahead of the hop on the
        target's own render thread, exactly as a glyph move's warm (``begin_visualizer_prewarm``), until
        ``release_prepared_display`` or the hop (which adopts it). Called at an edge only: the pointer entering a
        transfer arrow, a drag's card nearing the seam. One neighbour at a time; a second replaces the first. False
        (nothing done) when not running, during a display move (it warms its own target), or for this display."""

        if self._retired or self._sync is None or not self._started:
            return False
        if target_runtime is None or target_runtime is self._presentation_runtime:
            return False
        if self.display_move_active:
            return False
        neighbour = self._neighbour_prewarm
        if neighbour is not None:
            if neighbour[0] is target_runtime:
                return True
            self.release_prepared_display()
        identity = self._render_identity
        scene = getattr(target_runtime, "scene_controller", None)
        begin = getattr(scene, "begin_visualizer_prewarm", None)
        if identity is None or not callable(begin):
            return False
        record = self._move_target_presentation(target_runtime, False)
        if record is None or not begin(identity, record):
            return False
        self._neighbour_prewarm = (target_runtime, scene)
        scene.feed_visualizer_prewarm(self._controller.render_bridge.peek())
        logger.info("[SPOTIFY_VIS] Neighbouring display prepared screen=%s -> %s",
                    getattr(self._presentation_runtime, "screen_index", "?"),
                    getattr(target_runtime, "screen_index", "?"))
        return True

    def release_prepared_display(self, target_runtime: Any = None) -> bool:
        """End the neighbour's preparation (the pointer left the arrow, the drag turned back or ended): its renderer is
        released once. ``target_runtime``: only when that display is the prepared one. False when nothing was."""

        neighbour = self._neighbour_prewarm
        if neighbour is None or (target_runtime is not None and neighbour[0] is not target_runtime):
            return False
        self._neighbour_prewarm = None
        runtime = self._presentation_runtime
        if runtime is None or neighbour[1] is not runtime.scene_controller:
            self._end_prewarm_on(neighbour[1])
        return True

    @property
    def prepared_display(self) -> Any:
        """The runtime whose display is prepared ahead of a hop, or None."""
        neighbour = self._neighbour_prewarm
        return None if neighbour is None else neighbour[0]

    @staticmethod
    def _end_prewarm_on(scene: Any) -> None:
        try:
            scene.end_visualizer_prewarm()
        except RuntimeError:
            pass                                      # a scene already retiring with its display

    def set_authored_outer_origin(self, x: float, y: float) -> bool:
        """Set ordinary/non-CUSTOM presentation origin without adding a cadence.

        A committed CUSTOM rect is authoritative and rejects this path entirely.
        When the owner is already active, the new origin is projected once at
        this event boundary; subsequent normal visualizer publications reuse it.
        """

        if self._retired or self._committed_layout_rect is not None:
            return False
        origin = (float(x), float(y))
        if origin == self._authored_outer_origin:
            return False
        self._authored_outer_origin = origin
        if self._configured:
            if self._started:
                # Through the current route: an expanded view stays display-wide while its ordinary rect moves.
                self._reapply_route()
            else:
                self._controller.commit_presentation_metrics(self._resolve_current_presentation())
        return True

    def resolved_outer_size(self) -> tuple[float, float]:
        """Return current outer size for ordinary layout planning (the ordinary rect, also while expanded)."""

        presentation = self._resolve_current_presentation()
        return (float(presentation.outer_rect[2]), float(presentation.outer_rect[3]))

    # ------------------------------------------------- display-wide viewport (Expanded Visualizer, plan 01 M2)

    @property
    def expanded_display(self) -> bool:
        """True once the display-wide route is committed (and while a collapse from it is still fading)."""

        return self._expanded_display

    @property
    def expanded_display_transition_active(self) -> bool:
        return self._takeover is not None

    @property
    def expanded_display_fade_half_s(self) -> float:
        """One half of the fade-through (seconds): the ordinary widgets on this display fade over the same span, out
        while the card fades out at its ordinary rect, back in while the display-wide card fades out (plan 01 M3)."""

        return self._transition_half_duration_s

    def set_expanded_display(
        self,
        expanded: bool,
        *,
        animate: bool = False,
        on_complete: Callable[[], None] | None = None,
    ) -> bool:
        """Show the Visualizer card near the display's extents, or back at its ordinary rect, at this event edge.

        The display-wide card is inset by only what its own chrome needs (``expanded_card_inset``).
        The display-wide record is a variant of the ordinary one (``resolve_expanded_visualizer_presentation``);
        it never reaches the controller's committed metrics, CUSTOM, presets or Settings, so collapsing restores
        the ordinary rect exactly. ``animate`` fades the whole presentation out, swaps the viewport and fades it
        back in on the publication edge, then calls ``on_complete`` once; without it the route swaps now (the
        readiness restore before reveal, or Edit's collapse) and ``on_complete`` runs before this returns. A new
        call supersedes one in flight (its ``on_complete`` is dropped). Returns False, changing nothing, when the
        owner is retired or not bound.
        """

        if self._retired or self._sync is None:
            return False
        expanded = bool(expanded)
        drawn_style = self._drawn_expanded_style()
        self._abandon_display_move()
        self._takeover = None
        if not animate:
            self._finish_takeover(expanded, on_complete, reapply=True)
            return True
        self._takeover = _TakeoverFade(
            target=expanded,
            source=self._expanded_display,
            started_at=float(self._transition_clock()),
            on_complete=on_complete,
            source_style=drawn_style,
            target_style=self._expanded_display_style,
        )
        self._sync.set_presentation_route(
            self._resolve_takeover_presentation, self._commit_takeover_presentation
        )
        if self._started:
            # Present the first faded frame now; later frames ride the logical publications.
            self._reapply_route(request_present=True)
        return True

    @property
    def expanded_display_style(self) -> str:
        """The display style the display-wide card is drawn in (or will be, at the next expansion)."""

        return self._expanded_display_style

    def _drawn_expanded_style(self) -> str:
        takeover = self._takeover
        return takeover.drawn_style if takeover is not None else self._expanded_display_style

    def set_expanded_display_style(self, style: object) -> bool:
        """Take the display-wide card's display style (1D.2) at this event edge; True when it changed.

        Retarget before rebuild: nothing is created or torn down (engine, controller, render item and overlays stay).
        While the card is drawn display-wide and no fade-through runs, the change runs the existing expanded-to-
        expanded fade-through (``set_expanded_display`` machinery): out in the old style, the swap at zero opacity, in
        in the new one, sampled on the publication edge (no timer). A fade-through in flight takes it for its target
        side when that side is not drawn yet, or follows with its own fade-through once it completes. While
        collapsed it is stored and applies at the next expansion. The ordinary record is never changed by it.
        """

        from core.settings.fullscreen_overlays import normalize_display_style

        style = normalize_display_style(style)
        if self._retired or style == self._expanded_display_style:
            return False
        previous = self._drawn_expanded_style()
        self._expanded_display_style = style
        takeover = self._takeover
        if takeover is not None:
            if takeover.target and not takeover.drawn_target:
                takeover.target_style = style            # its display-wide side has not been drawn yet
            # Otherwise the fade-through in flight finishes in its own style and the change follows it.
            return True
        if not self._expanded_display or self._sync is None:
            return True                                   # applies at the next expansion
        self._begin_style_fade(previous)
        logger.info("[EXPANDED_VIS] Display style %s -> %s (retargeted in place)", previous, style)
        return True

    def _begin_style_fade(self, source_style: str) -> None:
        self._takeover = _TakeoverFade(
            target=True, source=True, started_at=float(self._transition_clock()), on_complete=None,
            source_style=source_style, target_style=self._expanded_display_style,
        )
        self._sync.set_presentation_route(self._resolve_takeover_presentation, self._commit_takeover_presentation)
        if self._started:
            self._reapply_route(request_present=True)

    def move_display(
        self,
        target_runtime: Any,
        *,
        end_expanded: bool,
        hop: Callable[[], bool],
        on_fade_out: Callable[[], None] | None = None,
        on_fade_in: Callable[[bool], None] | None = None,
        on_complete: Callable[[bool], None] | None = None,
    ) -> bool:
        """Move the live view to ``target_runtime``'s display as one fade-through (Current_Plan 1C.2).

        Nothing is torn down: this owner, its controller, logical runtime and engine (worker session) stay; only the
        presentation edge moves. In order, each step at a publication edge (no timer): the target's renderer is
        prepared on the target's own render thread from the latest snapshot while the source keeps drawing (bounded by
        the prepared reveal's deadline); the view fades out where it is (``on_fade_out``); at zero opacity it is put
        on its ordinary card and ``hop`` moves the admission (the CUSTOM move and its Save; the scene transfer carries
        the mode's render-thread history); once that history has landed it fades in on the target, display-wide when
        ``end_expanded`` (``on_fade_in(moved)``), and ``on_complete(moved)`` follows the fully visible frame. A hop
        that fails fades the view back in where it was. False (nothing done) when retired, not running, or already
        on that display. A later ``set_expanded_display`` or retirement abandons the move (its callbacks are dropped).
        """

        if self._retired or self._sync is None or not self._started:
            return False
        if target_runtime is None or target_runtime is self._presentation_runtime:
            return False
        if self._neighbour_prewarm is not None:
            if self._neighbour_prewarm[0] is target_runtime:
                self._neighbour_prewarm = None        # the move's warm below continues what is prepared there
            else:
                self.release_prepared_display()
        drawn_style = self._drawn_expanded_style()
        self._abandon_display_move()
        now = float(self._transition_clock())
        takeover = _TakeoverFade(target=bool(end_expanded), source=self._expanded_display, started_at=now,
                                 on_complete=None, source_style=drawn_style,
                                 target_style=self._expanded_display_style)
        move = _DisplayMove(target_runtime, hop, on_fade_out, on_fade_in, on_complete, now)
        takeover.move = move
        self._takeover = takeover
        identity = self._render_identity
        scene = getattr(target_runtime, "scene_controller", None)
        begin = getattr(scene, "begin_visualizer_prewarm", None)
        if identity is not None and callable(begin):
            record = self._move_target_presentation(target_runtime, bool(end_expanded))
            if record is not None and begin(identity, record):
                move.identity = identity
                move.prewarm_scene = scene
                scene.feed_visualizer_prewarm(self._controller.render_bridge.peek())
        self._sync.set_presentation_route(self._resolve_takeover_presentation, self._commit_takeover_presentation)
        self._reapply_route(request_present=True)
        logger.info("[SPOTIFY_VIS] Display move began screen=%s -> %s end_expanded=%s prewarm=%s",
                    getattr(self._presentation_runtime, "screen_index", "?"),
                    getattr(target_runtime, "screen_index", "?"), bool(end_expanded), move.prewarm_scene is not None)
        return True

    @property
    def display_move_active(self) -> bool:
        takeover = self._takeover
        return takeover is not None and takeover.move is not None

    def _move_target_presentation(self, runtime: Any, end_expanded: bool) -> Any:
        """The record the view arrives in on ``runtime``'s display, at the prewarm's sub-visible opacity."""

        ordinary = self._resolve_current_presentation()
        if ordinary is None:
            return None
        try:
            identity = runtime.display_identity
            display_size = _expanded_display_size(runtime, self._expanded_display_style)
            dpr = float(identity.device_pixel_ratio)
        except Exception:
            return None
        if end_expanded:
            from widgets.spotify_visualizer.presentation_geometry import resolve_expanded_visualizer_presentation

            record = resolve_expanded_visualizer_presentation(ordinary, display_size=display_size,
                                                              dpr=dpr, display_style=self._expanded_display_style)
        else:
            record = replace(ordinary, dpr=dpr)
        return replace(record, scene_fade=_PREWARM_SCENE_FADE, content_fade=0.0)

    def _abandon_display_move(self) -> None:
        takeover = self._takeover
        move = None if takeover is None else takeover.move
        if move is None:
            return
        takeover.move = None
        scene = move.prewarm_scene
        move.prewarm_scene = None
        runtime = self._presentation_runtime
        if scene is not None and (runtime is None or scene is not runtime.scene_controller):
            self._end_prewarm_on(scene)

    def _move_fade(self, takeover: _TakeoverFade, move: _DisplayMove) -> float:
        """Sample one display move's fade-through (``move_display``) at a publication edge."""

        half = self._transition_half_duration_s
        now = float(self._transition_clock())
        if move.stage == "warm":
            takeover.drawn_expanded, takeover.drawn_target = takeover.source, False
            scene = move.prewarm_scene
            if scene is not None and now - move.stage_at < _PREPARED_REVEAL_DEADLINE_S:
                if not scene.visualizer_prewarm_prepared(move.identity):
                    return 1.0
            elif scene is not None:
                logger.info("[SPOTIFY_VIS] Display move goes ahead before the target's renderer prepared (%.1f s)",
                            _PREPARED_REVEAL_DEADLINE_S)
            move.stage, move.stage_at, move.fade_out_due = "out", now, True
        if move.stage == "out":
            takeover.drawn_expanded, takeover.drawn_target = takeover.source, False
            elapsed = now - move.stage_at
            if half > 0.0 and elapsed < half:
                linear = 1.0 - elapsed / half
                return linear * linear * (3.0 - 2.0 * linear)
            move.stage = "hop"                        # the commit edge moves the admission at zero opacity
            return 0.0
        if move.stage == "hop":
            return 0.0
        if move.stage == "hold":
            takeover.drawn_expanded, takeover.drawn_target = takeover.target, True
            scene = self._presentation_runtime.scene_controller
            landed = bool(getattr(scene, "visualizer_arrival_settled", True))
            if not landed and now - move.stage_at < _PREPARED_REVEAL_DEADLINE_S:
                return 0.0
            move.stage, move.stage_at, move.fade_in_due = "in", now, True
        takeover.drawn_expanded, takeover.drawn_target = takeover.target, True
        elapsed = now - move.stage_at
        if half <= 0.0 or elapsed >= half:
            takeover.done = True
            return 1.0
        linear = elapsed / half
        return linear * linear * (3.0 - 2.0 * linear)

    def _run_display_hop(self, takeover: _TakeoverFade, move: _DisplayMove) -> None:
        """The move's midpoint, at a commit edge with the view at zero opacity on the source."""

        move.stage, move.stage_at = "hold", float(self._transition_clock())
        source_expanded = bool(takeover.source)
        # The move admits, projects and commits the ordinary card (CUSTOM truth), never the display-wide one: put the
        # view on its ordinary card first, still at zero opacity, its overlays leaving with it.
        self._expanded_display = False
        self._expanded_source = None
        takeover.drawn_expanded = False
        self._project_expanded_overlays()
        ordinary = self._resolve_current_presentation()
        if ordinary is not None:
            self._apply_resolved_presentation(replace(ordinary, scene_fade=0.0))
        moved = False
        try:
            moved = bool(move.hop())
        except Exception:
            logger.exception("[SPOTIFY_VIS] Display move failed; the view returns where it was")
        move.moved = moved
        scene = move.prewarm_scene
        move.prewarm_scene = None
        if scene is not None and scene is not self._presentation_runtime.scene_controller:
            scene.end_visualizer_prewarm()            # the move did not land there
        if not moved:
            takeover.target = source_expanded
        takeover.on_complete = (lambda m=move: m.on_complete(bool(m.moved))) if move.on_complete else None
        logger.info("[SPOTIFY_VIS] Display move %s screen=%s", "landed" if moved else "refused",
                    getattr(self._presentation_runtime, "screen_index", "?"))
        request = getattr(self._presentation_runtime.scene_controller, "request_visualizer_present", None)
        if callable(request):
            request()

    def _route_pair(self) -> tuple[Callable[[], Any], Callable[[Any], None]]:
        if self._takeover is not None:
            return self._resolve_takeover_presentation, self._commit_takeover_presentation
        if self._expanded_display:
            return self._resolve_expanded_presentation, self._apply_expanded_presentation
        return self._resolve_current_presentation, self._apply_resolved_presentation

    def _reapply_route(self, *, request_present: bool = False) -> None:
        """Resolve and commit once through the current route at an event edge (not a cadence)."""

        resolve, commit = self._route_pair()
        presentation = resolve()
        if presentation is None:
            return
        commit(presentation)
        if request_present:
            request = getattr(self._presentation_runtime.scene_controller, "request_visualizer_present", None)
            if callable(request):
                request()

    def _finish_takeover(
        self, expanded: bool, on_complete: Callable[[], None] | None, *, reapply: bool,
        drawn_style: str | None = None,
    ) -> None:
        """Commit the steady route. ``drawn_style``: the display style a completed fade-through ended in; when the
        style changed meanwhile (1D.2), its own expanded-to-expanded fade-through follows at once, so the steady
        route never swaps the style without a fade."""

        self._takeover = None
        self._expanded_display = bool(expanded)
        if not expanded:
            self._expanded_source = None
        if expanded and drawn_style is not None and drawn_style != self._expanded_display_style:
            self._begin_style_fade(drawn_style)
        else:
            resolve, commit = self._route_pair()
            self._sync.set_presentation_route(resolve, commit)
            if reapply and self._started:
                self._reapply_route(request_present=True)
        self._project_expanded_overlays()
        if on_complete is not None:
            on_complete()

    def _expanded_drawn(self) -> bool:
        """The side the card is drawn on now: display-wide or ordinary (a fade-through draws its source first)."""

        takeover = self._takeover
        return bool(takeover.drawn_expanded) if takeover is not None else self._expanded_display

    def _project_expanded_overlays(self) -> None:
        """Admit the full-display overlays exactly while the display-wide card is drawn and the displays are on.

        Called at the route's edges only: a committed swap, the fade-through's midpoint (where the card is at zero
        opacity, so the overlays appear and leave with it, never popping), display power and retirement. Parked
        displays hold no overlay (no fade animation runs while the displays are off); waking brings them back.
        """

        drawn = bool(not self._retired and self._display_power_on and self._expanded_drawn())
        if drawn == self._expanded_overlays_drawn:
            return
        runtime = self._presentation_runtime
        setter = getattr(getattr(runtime, "scene_controller", None), "set_visualizer_expanded_overlays_drawn", None)
        self._expanded_overlays_drawn = drawn
        if callable(setter):
            setter(drawn)

    def _resolve_expanded_presentation(self, style: str | None = None) -> Any:
        """The display-wide record in ``style`` (the owner's display style when None: the steady route)."""

        ordinary = self._resolve_current_presentation()
        if ordinary is None:
            return None
        from widgets.spotify_visualizer.presentation_geometry import (
            resolve_expanded_visualizer_presentation,
        )

        style = self._expanded_display_style if style is None else style
        self._expanded_source = ordinary
        return resolve_expanded_visualizer_presentation(
            ordinary, display_size=_expanded_display_size(self._presentation_runtime, style), display_style=style)

    def _apply_expanded_presentation(self, presentation: Any) -> None:
        """Commit a display-wide record: the scene shows it; the controller keeps the ordinary metrics."""

        self._presentation_runtime.scene_controller.apply_visualizer_presentation(
            presentation,
            active=True,
        )
        ordinary = self._expanded_source
        if ordinary is not None and not self._controller.has_custom_viewport_override:
            self._controller.commit_presentation_metrics(ordinary)
        self._committed_layout_extent = None

    def _takeover_fade(self, takeover: _TakeoverFade) -> float:
        """Sample the fade-through and pick the side drawn now (smoothstep each half)."""

        if takeover.move is not None:
            return self._move_fade(takeover, takeover.move)
        half = self._transition_half_duration_s
        elapsed = max(0.0, float(self._transition_clock()) - takeover.started_at)
        if half <= 0.0 or elapsed >= 2.0 * half:
            takeover.drawn_expanded, takeover.drawn_target = takeover.target, True
            takeover.done = True
            return 1.0
        if elapsed < half:
            takeover.drawn_expanded, takeover.drawn_target = takeover.source, False
            linear = 1.0 - elapsed / half
        else:
            takeover.drawn_expanded, takeover.drawn_target = takeover.target, True
            linear = (elapsed - half) / half
        return linear * linear * (3.0 - 2.0 * linear)

    def _resolve_takeover_presentation(self) -> Any:
        takeover = self._takeover
        if takeover is None:
            resolve, _commit = self._route_pair()
            return resolve()
        fade = self._takeover_fade(takeover)
        base = (
            self._resolve_expanded_presentation(takeover.drawn_style)
            if takeover.drawn_expanded
            else self._resolve_current_presentation()
        )
        if base is None:
            return None
        return replace(base, scene_fade=float(base.scene_fade) * fade)

    def _commit_takeover_presentation(self, presentation: Any) -> None:
        takeover = self._takeover
        if takeover is None or not takeover.drawn_expanded:
            self._apply_resolved_presentation(presentation)
        else:
            self._apply_expanded_presentation(presentation)
        if takeover is not None and takeover.drawn_expanded != self._expanded_overlays_drawn:
            # The fade-through's midpoint (only this route carries it, and only during the fade).
            self._project_expanded_overlays()
        move = None if takeover is None else takeover.move
        if move is not None and self._takeover is takeover:
            if move.stage == "warm" and move.prewarm_scene is not None:
                # The target prepares from the snapshot just published (the source consumes its own copy).
                move.prewarm_scene.feed_visualizer_prewarm(self._controller.render_bridge.peek())
            if move.fade_out_due:
                move.fade_out_due = False
                if move.on_fade_out is not None:
                    move.on_fade_out()
            if move.stage == "hop":
                self._run_display_hop(takeover, move)
                return
            if move.fade_in_due:
                move.fade_in_due = False
                if move.on_fade_in is not None:
                    move.on_fade_in(bool(move.moved))
        if takeover is not None and takeover.done and self._takeover is takeover:
            # The target is on screen at full opacity: commit the steady route, then report completion.
            self._finish_takeover(takeover.target, takeover.on_complete, reapply=False,
                                  drawn_style=takeover.target_style)

    def configure_committed_layout(
        self,
        *,
        local_rect: tuple[float, float, float, float] | None,
        viewport_extent: tuple[float, float] | None = None,
        content_rotation_by_mode: object = None,
        legacy_layout_profile: str | None = None,
        legacy_source_variant: str | None = None,
    ) -> None:
        """Hydrate one saved CUSTOM outer rect before logical runtime start.

        The rect, optional physical viewport extent and sparse per-mode content
        orientation are ordinary committed truth. The retained CUSTOM session
        may later install temporary overrides, but no edit-session owner is
        duplicated here.
        """

        if self._retired or self._started:
            raise RuntimeError("visualizer committed layout must bind before start")
        if local_rect is None:
            self._committed_layout_rect = None
            self._committed_layout_extent = None
            self._legacy_layout_profile = None
            self._legacy_layout_source_variant = None
            return
        x, y, width, height = (float(value) for value in local_rect)
        if width <= 0.0 or height <= 0.0:
            raise ValueError("visualizer committed layout rect must be positive")
        if viewport_extent is None:
            extent = None
        else:
            extent = (float(viewport_extent[0]), float(viewport_extent[1]))
            if extent[0] <= 0.0 or extent[1] <= 0.0:
                raise ValueError("visualizer committed viewport extent must be positive")
        self._committed_layout_rect = (x, y, width, height)
        self._committed_layout_extent = extent
        self._legacy_layout_profile = (
            str(legacy_layout_profile).strip().lower()
            if legacy_layout_profile is not None
            else None
        )
        self._legacy_layout_source_variant = (
            str(legacy_source_variant).strip().lower()
            if legacy_source_variant is not None
            else None
        )
        if (self._legacy_layout_profile is None) != (self._legacy_layout_source_variant is None):
            raise ValueError("legacy visualizer layout claim requires both profile and source variant")
        # Rehydrate physical CUSTOM truth before the authored logical runtime can
        # consume it. Orientation is layout state, not a Visualizer preset.
        hydration_extent = extent or self._controller.committed_viewport_extent
        self._controller.hydrate_committed_layout_metrics(
            hydration_extent,
            content_rotation_by_mode,
        )
        # The same resolved record is later published by the GUI synchronization
        # edge, validating the current mode policy without creating another owner.
        self._controller.commit_presentation_metrics(
            self._resolve_current_presentation()
        )
        # Keep the persisted extent as a one-shot recreation hydration fence
        # until the first retained presentation is actually committed.  A
        # same-process replacement can otherwise briefly republish canonical
        # metrics between construction and first presentation, which leaves
        # viewport-sensitive Bubble presentation scaling wrong until a cold
        # restart.  This is state-only and adds no cadence/polling owner.

    def _activate_committed_layout_profile(self, target_mode: str) -> None:
        """Select a cross-family CUSTOM pose while the target remains hidden."""

        resolver = self._committed_layout_profile_resolver
        resolved = None if resolver is None else resolver(str(target_mode))
        if resolved is None:
            logger.info(
                "[CUSTOM_LAYOUT] Visualizer target has no saved profile pose "
                "mode=%s; selecting authored baseline", target_mode,
            )
            # A profile that has never been authored deliberately starts from
            # its normal fitted baseline.  Do not copy the outgoing family
            # rectangle: it is exactly the malformed 2D/3D coupling this seam
            # removes.  The next normal CUSTOM Save writes the named profile.
            self._committed_layout_rect = None
            self._committed_layout_extent = None
            self._controller.hydrate_committed_layout_metrics(
                CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
                {},
            )
            return
        local_rect, viewport_extent, rotations = resolved
        x, y, width, height = (float(value) for value in local_rect)
        if width <= 0.0 or height <= 0.0:
            raise ValueError("visualizer profile rect must be positive")
        if viewport_extent is None:
            extent = CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
        else:
            extent = (float(viewport_extent[0]), float(viewport_extent[1]))
            if extent[0] <= 0.0 or extent[1] <= 0.0:
                raise ValueError("visualizer profile viewport extent must be positive")
        self._committed_layout_rect = (x, y, width, height)
        self._committed_layout_extent = extent
        self._controller.hydrate_committed_layout_metrics(extent, rotations)

    def commit_live_custom_layout(
        self,
        *,
        local_rect: tuple[float, float, float, float],
        viewport_extent: tuple[float, float],
        content_rotation_by_mode: object = None,
    ) -> None:
        """Promote active CUSTOM geometry/orientation without recreating its generation."""

        if self._retired or not self._started or not self._bound:
            raise RetainedRuntimeIncoherenceError("live CUSTOM layout requires a bound running visualizer")
        x, y, width, height = (float(value) for value in local_rect)
        extent_width, extent_height = (float(value) for value in viewport_extent)
        if not all(
            math.isfinite(value)
            for value in (x, y, width, height, extent_width, extent_height)
        ) or width <= 0.0 or height <= 0.0 or extent_width <= 0.0 or extent_height <= 0.0:
            raise ValueError("live CUSTOM visualizer geometry must be finite and positive")
        if not self._controller.has_custom_viewport_override:
            raise RetainedRuntimeIncoherenceError("live CUSTOM visualizer commit requires an active override")
        drawn = self._presentation_runtime.scene_controller.visualizer_item.presentation
        # Display-wide (Fullscreen Edit's Rotate Widget Content): the scene draws the expanded variant; the ordinary
        # card's record it derives from is the CUSTOM truth promoted here (never the display-wide one).
        presentation = self.ordinary_presentation
        if presentation is None or drawn is None:
            raise RetainedRuntimeIncoherenceError("live CUSTOM visualizer has no retained presentation")
        if presentation.viewport_extent != (extent_width, extent_height):
            raise RetainedRuntimeIncoherenceError("live CUSTOM visualizer extent differs from retained presentation")
        from widgets.spotify_visualizer.presentation_orientation import (
            resolve_content_rotation_for_mode,
        )
        expected_rotation = resolve_content_rotation_for_mode(
            content_rotation_by_mode,
            self._controller.mode_id,
        )
        if presentation.content_rotation_quarters != expected_rotation:
            raise RetainedRuntimeIncoherenceError(
                "live CUSTOM visualizer orientation differs from retained presentation"
            )
        expected = (x, y, width, height)
        # CUSTOM owns an integer QRect while the retained visualizer owns a
        # uniform floating projection.  Each edge of that QRect is rounded
        # independently, so require the exact half-pixel envelope rather than
        # falsely rejecting valid tall/narrow worlds.  The presentation is the
        # authoritative visible value promoted below.
        if any(
            abs(value - target) > 0.500001
            for value, target in zip(presentation.outer_rect, expected, strict=True)
        ):
            raise RetainedRuntimeIncoherenceError("live CUSTOM visualizer rectangle differs from retained presentation")
        # The retained scene already displays this exact projection. Promote
        # it before CUSTOM removes its temporary extent override, so the next
        # ordinary publication resolves the same rect/world pair.
        # Validate the controller policy before changing either owner field.
        # This preserves the prior committed pair if a malformed presentation
        # is ever routed here.
        self._controller.commit_presentation_metrics(presentation)
        # The editor displayed this presentation, but an unread logical snapshot
        # may have been composed against the *previous* CUSTOM authority. It is
        # never legal to relabel its immutable geometry as current. Discard only
        # that unconsumed snapshot; the next ordinary logical publication carries
        # the freshly committed, coherent stage/viewport pair.
        self._controller.render_bridge.discard_if_presentation_differs(drawn)
        # Save promotes the complete sparse map, not only the currently visible
        # mode, so modes rotated earlier in the same edit session survive an
        # in-process mode switch without requiring recreation.
        self._controller.commit_content_rotation_map(content_rotation_by_mode)
        self._committed_layout_rect = tuple(float(value) for value in presentation.outer_rect)
        self._committed_layout_extent = (extent_width, extent_height)
        self._legacy_layout_profile = None
        self._legacy_layout_source_variant = None

    @property
    def ordinary_presentation(self) -> Any:
        """The ordinary card's resolved record: the drawn one, or, while the card is display-wide, the record the
        display-wide one derives from (its latest resolve). None before the first presentation."""

        if self._expanded_drawn():
            return self._expanded_source
        item = self._presentation_runtime.scene_controller.visualizer_item
        return None if item is None else item.presentation

    def _activation_scene_fade(self) -> float:
        """Return the authored 0 -> 1 first-appearance scene fade progress.

        Before the owner starts (``started_at is None``) this is fully opaque so
        no pre-start metrics commit can hide the scene. Once armed it eases with
        a smoothstep against the shared transition clock and lands exactly on
        1.0, after which it stays there for the generation's lifetime.
        """

        started = self._activation_fade_started_at
        if started is None:
            return 1.0
        duration = _ACTIVATION_SCENE_FADE_DURATION_S
        if duration <= 0.0:
            return 1.0
        linear = (float(self._transition_clock()) - started) / duration
        if linear <= 0.0:
            return 0.0
        if linear >= 1.0:
            return 1.0
        return linear * linear * (3.0 - 2.0 * linear)

    def _resolve_current_presentation(self) -> Any:
        scene_fade = self._activation_scene_fade()
        if self._presentation_resolver is not None:
            presentation = self._presentation_resolver()
            if presentation is None:
                return None
            return replace(
                presentation,
                scene_fade=float(presentation.scene_fade) * scene_fade,
                content_fade=(
                    float(presentation.content_fade) * self._mode_transition_fade
                ),
            )
        from widgets.spotify_visualizer.presentation_geometry import (
            resolve_visualizer_presentation,
        )

        identity = self._presentation_runtime.display_identity
        _x, _y, width, height = identity.geometry
        dpr = float(identity.device_pixel_ratio)
        if dpr <= 0.0:
            dpr = 1.0
        committed_rect = self._committed_layout_rect
        # A live CUSTOM working override remains the strongest temporary
        # authority.  Otherwise, a freshly rehydrated persisted extent wins
        # only until the first retained presentation consumes it; after that
        # the controller's committed extent is authoritative as before.
        controller_extent, content_rotation_quarters, has_custom_override = (
            self._controller.presentation_layout_metrics
        )
        if has_custom_override:
            # A display-wide card is never the ordinary working stage (Fullscreen Edit's orientation preview sets an
            # override while the scene draws the expanded variant): resolve the ordinary record from committed truth.
            working = (None if self._expanded_drawn()
                       else self._presentation_runtime.scene_controller.visualizer_item.presentation)
            if (working is not None and
                    tuple(working.viewport_extent) == tuple(controller_extent) and
                    working.content_rotation_quarters == content_rotation_quarters):
                # GUI-side sync: retained CUSTOM's live stage is already the
                # presentation authority. Reuse that exact stage for logical
                # composition, never republish the previous committed size into
                # the edit scene. No shadow rectangle or queue is introduced.
                return replace(
                    working, scene_fade=scene_fade,
                    # Fade is derived from this owner's current transition,
                    # never multiplied by the *previous* retained record.
                    # Reusing old fade recursively could trap a mode at zero
                    # opacity after an Edit/profile hot-swap.
                    content_fade=self._mode_transition_fade,
                )
            viewport_extent = controller_extent
        elif self._committed_layout_extent is not None:
            viewport_extent = self._committed_layout_extent
        else:
            viewport_extent = controller_extent
        if committed_rect is None:
            outer_origin = self._authored_outer_origin
            uniform_scale = 1.0
        else:
            outer_origin = (committed_rect[0], committed_rect[1])
            uniform_scale = committed_rect[2] / max(1e-6, viewport_extent[0])
        from core.settings.visualizer_mode_registry import get_visualizer_geometry_kind
        is_freeform = get_visualizer_geometry_kind(self._controller.mode_id) == "freeform_3d"
        return resolve_visualizer_presentation(
            policy=self._controller.presentation_policy,
            display_size=(float(width), float(height)),
            outer_origin=outer_origin,
            committed_outer_size=(committed_rect[2], committed_rect[3]) if (
                is_freeform and committed_rect is not None and not has_custom_override
            ) else None,
            dpr=dpr,
            uniform_visual_scale=uniform_scale,
            viewport_extent=viewport_extent,
            content_rotation_quarters=content_rotation_quarters,
            scene_fade=scene_fade,
            content_fade=self._mode_transition_fade,
            **self._card_shadow_kwargs,
        )

    def _apply_resolved_presentation(self, presentation: Any) -> None:
        """Commit the exact presentation embedded in the published snapshot.

        The scene controller owns retained shell/item projection. Keeping this
        callback on the GUI-side synchronization edge prevents a bridge snapshot
        from being published while the VisualizerRenderItem still has no (or a
        different) presentation record.
        """

        self._presentation_runtime.scene_controller.apply_visualizer_presentation(
            presentation,
            active=True,
        )
        # CUSTOM's live projection is temporary working truth. Committing it
        # here would overwrite the normal baseline on every logical frame, so
        # Cancel could only restore the last edit rectangle. Save promotes it
        # explicitly through commit_live_custom_layout instead.
        if not self._controller.has_custom_viewport_override:
            self._controller.commit_presentation_metrics(presentation)
        # The retained scene has now consumed one coherent presentation.  Drop
        # the one-shot persisted-layout hydration fence so later live CUSTOM
        # edits / transfers continue to follow the controller normally.
        self._committed_layout_extent = None

    def _signal_transition_failure(self, reason: str) -> None:
        """Escalate an unrecoverable activation once through generation-fenced reload.

        No alternate renderer, Settings write or retry scheduler is created.
        The existing display-recreation authority reconstructs the last
        committed layout rather than promoting an incomplete Edit transaction.
        """
        if self._retired or self._transition_recovery_issued:
            return
        self._transition_recovery_issued = True
        previous_phase = self._mode_transition_phase
        self._mode_transition_phase = "failed"
        pending = getattr(self, "_pending_mode_activation", None)
        target = pending.get("mode") if isinstance(pending, dict) else None
        logger.error(
            "[SPOTIFY_VIS] [MODE_ACTIVATION_FAIL] reason=%s phase=%s "
            "controller_mode=%s target=%s render_identity=%s; "
            "requesting committed-runtime reconstruction",
            reason, previous_phase,
            getattr(getattr(self, "_controller", None), "mode_id", None),
            target, getattr(self, "_render_identity", None),
        )
        callback = getattr(self, "_transition_failure_callback", None)
        if callback is not None:
            try:
                callback(str(reason))
            except Exception:
                logger.exception("[SPOTIFY_VIS] Activation reconstruction request failed")

    @property
    def _runtime_generation(self) -> Any:
        """The display generation that owns this owner's delayed work.

        ``ThreadManager.single_shot`` reads it from a bound method's owner, so the
        generation's ``cancel_scheduled_single_shots`` edge cancels the transition
        deadline with the rest of its callbacks.
        """
        return getattr(getattr(self, "_runtime", None), "runtime_generation", None)

    def _arm_transition_deadline(self) -> None:
        """One bounded single-shot per activation; successful ones expire inert.

        Without this, a target which never publishes a fresh logical frame
        leaves waiting_target permanently hidden, and Edit Save/Cancel permanently
        refused. No frame-driven or periodic timeout service can solve silence.
        The deadline is a ``ThreadManager.single_shot`` on a bound method (held
        weakly, tagged with this owner's display generation), so retiring the
        generation cancels it (AC-10); the request serial fences a superseded one.
        """
        if self._transition_failure_callback is None:
            return
        from core.threading.manager import ThreadManager

        ThreadManager.single_shot(
            _ACTIVATION_TRANSACTION_DEADLINE_MS,
            self._on_transition_deadline,
            self._transition_request_serial,
        )

    def _on_transition_deadline(self, serial: int) -> None:
        if self._retired or self._transition_request_serial != serial:
            return
        phase = self._mode_transition_phase
        if phase == "idle":
            return
        if phase == "fading_out":
            # The outgoing logical owner was never stopped. Abandon the
            # uncommitted request and restore its opacity, without a reload.
            self._pending_mode_activation = None
            self._mode_transition_phase = "idle"
            self._mode_transition_started_at = 0.0
            self._mode_transition_fade = self._fade_out_from
            try:
                self._reapply_route()
                self._request_retained_present()
            except Exception:
                logger.exception("[SPOTIFY_VIS] Could not restore stalled outgoing scene")
                self._signal_transition_failure("fade_out_restore_failed")
            else:
                logger.error("[SPOTIFY_VIS] Cancelled stalled fade-out while outgoing mode remained live")
            return
        if phase in ("waiting_target", "fading_in") and self._slow_target_alive(serial):
            # Hidden (or fading in) and still being prepared: keep the faded frame and wait, never reload.
            from core.threading.manager import ThreadManager

            logger.warning(
                "[SPOTIFY_VIS] Activation slow but alive phase=%s mode=%s: the render thread completed %d "
                "preparation unit(s); deadline extended (%d/%d)", phase, self._controller.mode_id,
                self._deadline_liveness[1], self._deadline_liveness[2], _SLOW_TARGET_DEADLINE_EXTENSIONS,
            )
            ThreadManager.single_shot(_ACTIVATION_TRANSACTION_DEADLINE_MS, self._on_transition_deadline, serial)
            return
        self._signal_transition_failure("deadline:" + phase)

    def _target_preparation_progress(self) -> int:
        """Preparation units the render thread completed for the committed target (0 while it is not bound)."""
        if getattr(self, "_worker", None) is not None and getattr(self, "_worker_commit", None) is not None:
            return 0                                  # the engine worker has not committed the target yet
        identity = getattr(self, "_render_identity", None)
        if identity is None:
            return 0
        item = self._presentation_runtime.scene_controller.visualizer_item
        return int(item.renderer_preparation_progress(identity.mode_id, identity.activation_id))

    def _slow_target_alive(self, serial: int) -> bool:
        """True (and the window's progress recorded) when the target's render advanced since the last deadline."""
        seen_serial, seen, extensions = getattr(self, "_deadline_liveness", (None, 0, 0))
        if seen_serial != serial:
            seen, extensions = 0, 0
        try:
            progress = self._target_preparation_progress()
        except Exception:
            logger.exception("[SPOTIFY_VIS] Could not read the target's render progress")
            return False
        if progress <= seen or extensions >= _SLOW_TARGET_DEADLINE_EXTENSIONS:
            return False
        self._deadline_liveness = (serial, progress, extensions + 1)
        return True

    def sync_present(self) -> bool:
        on_worker = self._worker is not None
        if on_worker:
            self._in_sync_present = True
        try:
            return self._sync_present_transaction()
        except Exception:
            if getattr(self, "_mode_transition_phase", "idle") == "idle":
                raise
            logger.exception("[SPOTIFY_VIS] Retained visualizer mode activation failed")
            self._signal_transition_failure("activation_exception")
            return False
        finally:
            if on_worker:
                # The layout metrics this presentation committed reach the worker's tick before its next step.
                self._in_sync_present = False
                self._forward_view()

    def _sync_present_transaction(self) -> bool:
        if self._retired or self._sync is None:
            return False
        phase = self._mode_transition_phase
        if phase == "idle":
            if self._worker is not None and self._worker_identity is None:
                return False                          # the engine worker's identity is not bound yet (its reply is)
            return self._sync.sync_latest()
        if phase == "failed":
            # One fenced reconstruction request already owns recovery. Never
            # turn subsequent logical mailbox wakes into an exception storm.
            return False
        if phase == "recovering":
            return self._sync_recovery(float(self._transition_clock()))

        now = float(self._transition_clock())
        elapsed = max(0.0, now - self._mode_transition_started_at)
        duration = self._transition_half_duration_s
        progress = 1.0 if duration <= 0.0 else min(1.0, elapsed / duration)
        if phase == "fading_out":
            self._mode_transition_fade = self._fade_out_from * (1.0 - progress)
            published = self._sync.sync_latest()
            # Do not replace the source until the retained item has consumed an
            # outgoing snapshot at zero content opacity. This keeps identity and
            # presentation atomic even when logical and GUI opportunities skew.
            if progress >= 1.0 and published:
                self._activate_pending_mode(now)
            return published

        if phase == "waiting_target":
            # The old source is already hidden and retired. Keep the target
            # hidden until its canonical engine activation has produced a fresh
            # logical frame; then start the authored 250 ms reveal.
            #
            # Exception: a presentation-owned-idle mode (Spectrum) whose playback
            # is idle produces its resting scene from presentation, not from engine
            # ticks. The tick side already publishes that idle while deliberately
            # keeping the fresh-source fence armed for later reactive authority
            # (tick_pipeline). Honor the same capability here so the paused idle
            # reveal is not stranded waiting for an engine frame that only arrives
            # on playback. The fence stays armed; only the reveal proceeds.
            if (
                (self._controller.logical_tick_state._waiting_for_fresh_engine_frame if self._worker is None
                 else self._worker_waiting_for_fresh_frame())
                and not self._target_reveals_paused_idle_without_engine_frame()
            ):
                return self._sync.sync_latest()
            published = self._sync.sync_latest()
            if published and self._target_renderer_preparing(now):
                return published
            if published:
                self._mode_transition_phase = "fading_in"
                self._mode_transition_started_at = now
                self._mode_transition_fade = 0.0
            return published

        if phase == "fading_in":
            self._mode_transition_fade = progress
            published = self._sync.sync_latest()
            # Persistence/action completion follows a fully visible target
            # snapshot, never merely elapsed wall time.
            if progress >= 1.0 and published:
                pending = self._pending_mode_activation
                self._pending_mode_activation = None
                self._mode_transition_phase = "idle"
                self._mode_transition_started_at = 0.0
                self._mode_transition_fade = 1.0
                if self._recovery_stage and self._worker is not None and self._worker_failures:
                    # An engine-worker recovery's replacement session is fully revealed (its first presentable frame
                    # faded in): it proved itself, so the two-strike rule starts again (checkpoint audit 10, A10-L4). A
                    # second strike is now a failure before a recovery completes; an isolated failure hours later (a
                    # fail-closed run of failed steps during a device change, a crash) recovers again instead of
                    # leaving the worker for the run, up to the run's recovery limit (A11-M1: each recovery takes one
                    # of ``engine_worker_link.MAX_RECOVERIES_PER_RUN``, so a failure that recurs after every reveal
                    # ends in process). A recovery revealed after the fallback (stage 2) runs in process.
                    logger.info("[SPOTIFY_VIS][ENGINE_WORKER] Recovery completed; the failure count starts again "
                                "mode=%s", self._controller.mode_id)
                    self._worker_failures = 0
                self._recovery_stage = 0              # an engine-worker recovery's reveal completed
                callback = None if pending is None else pending.get("on_complete")
                if callable(callback):
                    try:
                        callback(self._controller.mode_id)
                    except Exception:
                        # Completion persists mode/preset ownership. A partial
                        # persistence failure must not masquerade as a healthy
                        # newly-visible target. Reconstruct from Settings once.
                        logger.exception("[SPOTIFY_VIS] Activation completion persistence failed")
                        self._signal_transition_failure("completion_failed")
            return published

        raise RuntimeError(f"unknown visualizer mode transition phase: {phase}")

    def set_edit_orbit_publication_callback(
        self, callback: Callable[[Any, Any], None] | None,
    ) -> None:
        """Bind held-orbit/one-shot first-source Edit framing to the GUI owner."""
        if self._sync is not None and not self._retired:
            self._sync.set_authored_view_publication_callback(callback)

    def _target_renderer_preparing(self, now: float) -> bool:
        """True while a ``prepared_reveal`` target's renderer is still preparing (bounded)."""
        activation = self._preparing_activation
        if activation is None:
            return False
        item = self._presentation_runtime.scene_controller.visualizer_item
        # The bound runs from the last preparation unit the render thread completed, not only from the commit: a
        # long unit (a cold driver link holds this GUI thread in Qt's sync for its whole length, R-180) must not
        # reveal the target into the rest of its compiles on visible frames. No progress for the bound: reveal.
        progress = int(item.renderer_preparation_progress(*activation))
        seen = getattr(self, "_preparing_progress", None)
        if seen is None or seen[0] != activation or seen[1] != progress:
            seen = (activation, progress, now if progress else self._waiting_target_since)
            self._preparing_progress = seen
        if now - max(self._waiting_target_since, seen[2]) < _PREPARED_REVEAL_DEADLINE_S:
            if not item.renderer_prepared(*activation):
                return True
        else:
            logger.info(
                "[SPOTIFY_VIS] Revealing %s before its renderer prepared (%.1f s)",
                activation[0],
                _PREPARED_REVEAL_DEADLINE_S,
            )
        self._preparing_activation = None
        return False

    def _target_reveals_paused_idle_without_engine_frame(self) -> bool:
        """True when the active target may reveal its paused idle with no engine frame.

        A presentation-owned-idle mode (Spectrum) builds its resting scene from
        presentation rather than engine ticks, so while playback is idle its reveal
        must not wait for a fresh engine frame (which only arrives on playback).
        Playing targets, and modes whose idle is engine-driven, are unaffected.
        """
        controller = self._controller
        if bool(getattr(controller, "playing", False)):
            return False
        from widgets.spotify_visualizer import mode_capabilities

        return mode_capabilities.has_presentation_owned_idle_scene(
            getattr(controller, "mode_id", None)
        )

    def request_mode_change(
        self,
        target_mode: str,
        *,
        settings_model: Any,
        resolved_activation: Any,
        technical_cache: Mapping[str, Mapping[str, Any]],
        logical_kwargs: Mapping[str, Any],
        presentation_kwargs: Mapping[str, Any],
        on_complete: Callable[[str], None] | None = None,
    ) -> bool:
        """Begin one retained crossfade into one canonical target activation."""

        return self._request_visualizer_activation(
            kind="mode",
            target_mode=target_mode,
            settings_model=settings_model,
            resolved_activation=resolved_activation,
            technical_cache=technical_cache,
            logical_kwargs=logical_kwargs,
            presentation_kwargs=presentation_kwargs,
            on_complete=on_complete,
        )

    def request_preset_change(
        self,
        target_mode: str,
        *,
        settings_model: Any,
        resolved_activation: Any,
        technical_cache: Mapping[str, Mapping[str, Any]],
        logical_kwargs: Mapping[str, Any],
        presentation_kwargs: Mapping[str, Any],
        on_complete: Callable[[str], None] | None = None,
    ) -> bool:
        """Begin one retained same-mode preset activation transaction."""

        return self._request_visualizer_activation(
            kind="preset",
            target_mode=target_mode,
            settings_model=settings_model,
            resolved_activation=resolved_activation,
            technical_cache=technical_cache,
            logical_kwargs=logical_kwargs,
            presentation_kwargs=presentation_kwargs,
            on_complete=on_complete,
        )

    def _request_visualizer_activation(
        self,
        *,
        kind: str,
        target_mode: str,
        settings_model: Any,
        resolved_activation: Any,
        technical_cache: Mapping[str, Mapping[str, Any]],
        logical_kwargs: Mapping[str, Any],
        presentation_kwargs: Mapping[str, Any],
        on_complete: Callable[[str], None] | None,
    ) -> bool:
        """Admit one mode or preset activation into the shared transaction."""

        if self._retired or not self._started:
            return False
        from core.settings.visualizer_mode_registry import (
            coerce_visualizer_mode_id,
            is_mode_active,
        )

        requested = str(target_mode or "").strip().lower()
        target = coerce_visualizer_mode_id(requested)
        if target != requested or not is_mode_active(target):
            return False
        current = self._controller.mode_id
        if kind == "mode":
            target_is_valid = target != current
        elif kind == "preset":
            target_is_valid = target == current
        else:
            raise ValueError(f"unknown visualizer activation kind: {kind}")
        if not target_is_valid or self._mode_transition_phase != "idle":
            return False
        self._pending_mode_activation = {
            "kind": kind,
            "mode": target,
            "settings_model": settings_model,
            "resolved_activation": resolved_activation,
            "technical_cache": dict(technical_cache),
            "logical_kwargs": dict(logical_kwargs),
            "presentation_kwargs": dict(presentation_kwargs),
            "on_complete": on_complete,
        }
        # The fade-out starts from the fade drawn now (1.0 in process, and after every completed engine-worker
        # recovery since audit 8's A8-M2; kept so a request can never flash a hidden frame back in).
        self._fade_out_from = float(self._mode_transition_fade)
        self._mode_transition_phase = "fading_out"
        self._mode_transition_started_at = float(self._transition_clock())
        self._transition_request_serial += 1
        self._transition_recovery_issued = False
        try:
            self._arm_transition_deadline()
        except Exception:
            # A GUI with no effective deadline cannot safely admit a potentially
            # infinite hidden transition. Leave the previous source untouched.
            self._pending_mode_activation = None
            self._mode_transition_phase = "idle"
            self._mode_transition_fade = self._fade_out_from
            logger.exception("[SPOTIFY_VIS] Rejected transition without a bounded recovery guard")
            return False
        logger.info(
            "[SPOTIFY_VIS] Quick %s activation requested %s -> %s",
            kind,
            current,
            target,
        )
        return True

    def _activate_pending_mode(self, now: float) -> None:
        """Commit the hidden target with one engine transaction and one runtime."""

        pending = self._pending_mode_activation
        if pending is None:
            raise RuntimeError("visualizer mode transition has no target activation")
        controller = self._controller
        target_mode = str(pending["mode"])
        previous_mode = str(controller.mode_id)
        kind = str(pending.get("kind") or "mode")
        edit_profile_switched = False
        # The Edit profile projection is fallible (QML, persisted payload, and
        # display bindings). Validate/project it while the outgoing logical
        # runtime is still alive and hidden. A failure here must NOT strand a
        # stopped old runtime with an undelivered new mesh. The retained render
        # identity remains the outgoing one until the target is configured.
        if kind == "mode":
            from core.settings.visualizer_mode_registry import get_visualizer_layout_profile
            if get_visualizer_layout_profile(target_mode) != get_visualizer_layout_profile(previous_mode):
                activator = self._edit_layout_profile_activator
                if activator is not None:
                    try:
                        if not activator(target_mode):
                            raise RuntimeError("active CUSTOM edit profile switch was refused")
                        edit_profile_switched = True
                    except Exception:
                        logger.exception(
                            "[SPOTIFY_VIS] Edit profile preflight FAILED source=%s target=%s; "
                            "outgoing logical runtime still active", previous_mode, target_mode,
                        )
                        self._pending_mode_activation = None
                        self._mode_transition_phase = "idle"
                        self._mode_transition_fade = 1.0
                        return
        target = target_mode
        outgoing_mode = previous_mode
        if self._worker is not None:
            self._activate_pending_mode_on_worker(now, pending, kind=kind, target=target, outgoing_mode=outgoing_mode,
                                                  edit_profile_switched=edit_profile_switched)
            return
        progress = ActivationProgress()

        def change_layout_profile(profile_target: str) -> None:
            # The logical runtime is stopped and the target is still hidden.
            # Drop any unread old-mode snapshot before switching geometry so
            # it cannot be rejected later as a one-frame stale presentation.
            controller.render_bridge.discard_pending()
            progress.step = "activate_committed_profile"
            # Edit's target profile was already projected/validated
            # BEFORE stopping the outgoing logical runtime. Never
            # repeat a fallible QML projection inside this transaction.
            self._activate_committed_layout_profile(profile_target)

        def recover(activation_step: str) -> bool:
            # Inside the failed transaction, before it ends. Qt's GUI callback
            # boundary may otherwise discard the Python traceback, leaving only
            # an invisible Visualizer and a stopped logical runtime. Record the
            # exact failed transaction stage.
            logger.exception(
                "[SPOTIFY_VIS] Hidden %s activation FAILED step=%s "
                "source=%s target=%s; retained Edit Save must refuse",
                kind, activation_step, outgoing_mode, target,
            )
            if kind == "mode" and str(controller.mode_id) == outgoing_mode:
                try:
                    if edit_profile_switched and self._edit_layout_profile_activator is not None:
                        self._edit_layout_profile_activator(outgoing_mode)
                    if edit_profile_switched:
                        self._activate_committed_layout_profile(outgoing_mode)
                    self._start_logical_runtime()
                except Exception:
                    logger.exception(
                        "[SPOTIFY_VIS] Could not restore outgoing logical mode=%s", outgoing_mode,
                    )
                else:
                    # Recovery is event-owned: no new fade timer, no polling,
                    # no Settings write, and no half-switched Edit transaction.
                    self._pending_mode_activation = None
                    self._mode_transition_started_at = 0.0
                    self._mode_transition_fade = 1.0
                    self._mode_transition_phase = "idle"
                    logger.warning(
                        "[SPOTIFY_VIS] Restored outgoing mode after failed hidden "
                        "activation source=%s target=%s", outgoing_mode, target,
                    )
                    return True
            self._mode_transition_phase = "failed"
            return False

        # One logical activation commit (``logical_edges``), shared with the
        # engine worker's session: runtime stop, engine transaction, target
        # configuration, reset, pending identity.
        try:
            committed = commit_logical_activation(
                controller,
                kind=kind,
                target=target,
                settings_model=pending["settings_model"],
                resolved_activation=pending["resolved_activation"],
                technical_cache=pending["technical_cache"],
                logical_kwargs=pending["logical_kwargs"],
                presentation_kwargs=pending["presentation_kwargs"],
                progress=progress,
                on_layout_profile_change=change_layout_profile,
                configure=self._apply_configuration,
                recover=recover,
            )
        except LogicalRuntimeNotJoined:
            if edit_profile_switched and self._edit_layout_profile_activator is not None:
                self._edit_layout_profile_activator(previous_mode)
            self._mode_transition_phase = "failed"
            raise
        except Exception:
            # ``prepare``: the runtime stop itself raised (unchanged state);
            # ``transaction``: ``recover`` already ran.
            if progress.stage == "begin":
                self._mode_transition_phase = "failed"
            elif progress.stage == "bind":
                logger.exception(
                    "[SPOTIFY_VIS] Hidden %s activation FAILED step=%s "
                    "source=%s target=%s; retained Edit Save must refuse",
                    kind, progress.step, outgoing_mode, target,
                )
                self._mode_transition_phase = "failed"
            raise
        if committed is None:
            return                                   # restored the outgoing mode
        generation, activation_id = committed

        activation_step = "bind_fresh_target"
        try:
            self._render_identity = self._runtime.bind_visualizer_render_source(
                controller,
                engine_generation=generation,
                activation_id=activation_id,
            )
            self._start_logical_runtime()
        except Exception:
            logger.exception(
                "[SPOTIFY_VIS] Hidden %s activation FAILED step=%s "
                "source=%s target=%s; retained Edit Save must refuse",
                kind, activation_step, outgoing_mode, target,
            )
            self._mode_transition_phase = "failed"
            raise
        from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor

        self._preparing_activation = (
            (target, activation_id) if get_visualizer_mode_descriptor(target).prepared_reveal else None
        )
        self._preparing_progress = None
        self._waiting_target_since = now
        self._mode_transition_phase = "waiting_target"
        self._mode_transition_started_at = 0.0
        self._mode_transition_fade = 0.0
        logger.info(
            "[SPOTIFY_VIS] Quick %s activation committed mode=%s generation=%s activation=%s",
            kind,
            target,
            generation,
            activation_id,
        )

    def _start_logical_runtime(self, *, interval_s: float | None = None) -> None:
        # The cadence owner (``logical_edges.start_logical_cadence``; the engine worker's session paces itself with
        # the same one).
        start_logical_cadence(self._controller, interval_s=interval_s)

    def start(self, *, interval_s: float | None = None) -> None:
        if self._retired:
            raise RuntimeError("cannot start a retired visualizer owner")
        controller = self._controller
        if not self._configured or not self._bound:
            raise RuntimeError("visualizer owner must be configured and bound before start")
        if self._worker is not None:
            self._activation_fade_started_at = float(self._transition_clock())
            self._started = True
            link = self._worker
            try:
                # Sent, never awaited; a failed start leaves this activation in process (logged once, an event).
                link.start(bool(controller.playing),
                           on_failed=lambda failure, _link=link: self._on_worker_start_failed(_link, failure))
            except Exception as exc:
                self._on_worker_start_failed(link, exc)
            return
        engine = prepare_engine_start(controller)

        def acquired() -> None:
            self._engine_acquired = True

        try:
            admit_engine_start(controller, engine, on_acquired=acquired, commit_playback=self.set_playing)
            # Arm the authored scene fade before the logical producer can publish
            # the first frame. Mailbox empty->populated publication wakes Qt's GUI
            # thread directly; there is no display-refresh polling pacer here.
            self._activation_fade_started_at = float(self._transition_clock())
            self._started = True
            self._start_logical_runtime(interval_s=interval_s)
            if release_engine_started_parked(engine, display_on=self._display_power_on,
                                             engine_acquired=self._engine_acquired):
                # Started while the displays are off: the runtime started parked;
                # hold no capture reference until they come back.
                self._engine_acquired = False
                self._engine_released_for_display_power = True
        except Exception:
            self._started = False
            controller.stop_logical_runtime()
            if self._engine_acquired:
                release = getattr(engine, "release", None)
                if callable(release):
                    release()
                self._engine_acquired = False
            raise

    # ------------------------------------------- the engine worker (native core P2b, work order 5 slices 5.2 and 5.5)
    # Every control edge below is sent and never awaited (``engine_worker_link``: replies and failures arrive as queued
    # events on this GUI thread). An edge that needs a reply's identity proceeds on that event: the configure's engine
    # identity binds render admission (``_on_worker_configured``), a hidden activation's committed identity binds the
    # target (``_on_worker_committed``). Failures always arrive as events (never inside the edge that caused them), so
    # the failure path never re-enters an edge in flight (A7-L2).

    def _configure_on_engine_worker(self, inputs: dict[str, Any], *, playing: bool) -> bool:
        """Configure the first activation on the engine worker (sent, never awaited: the worker's spawn included);
        False (logged once) leaves it in process."""
        from widgets.spotify_visualizer import engine_worker_link as link_module

        controller = self._controller
        supervisor = self._configure_services.get("process_supervisor")
        if link_module.worker_disabled_for_run():
            logger.warning("[SPOTIFY_VIS][ENGINE_WORKER] Engine worker disabled for this run after earlier failures; "
                           "mode=%s runs in process", controller.mode_id)
            return False
        try:
            link = self._open_engine_worker_session(inputs, supervisor)
        except Exception as exc:
            logger.warning("[SPOTIFY_VIS][ENGINE_WORKER] Configure failed (%s); this activation runs in process "
                           "mode=%s", exc, controller.mode_id)
            return False
        link_module.configure_presentation_side(
            controller, activation=inputs, playing=playing, refresh_presentation=self._refresh_backdrop,
            **self._configure_services,
        )
        self._adopt_engine_worker_session(link, inputs)
        self._arm_first_configure_deadline(link)
        logger.info("[SPOTIFY_VIS][ENGINE_WORKER] Visualizer configuring on the engine worker mode=%s namespace=%d",
                    controller.mode_id, link.label_namespace)
        return True

    def _arm_first_configure_deadline(self, link: Any) -> None:
        """The first configure is bounded on its own (A8-L5): the recovery deadline's one-shot (the transaction
        deadline's machinery, generation-fenced, never a poll), fenced by the session's label namespace (unique per
        configure). A configure stuck in the worker (a device open, a build) or a spawn queued behind a busy IO pool
        no longer waits for the heartbeat (twice, with the resend) or for ever."""
        from core.threading.manager import ThreadManager

        ThreadManager.single_shot(_ACTIVATION_TRANSACTION_DEADLINE_MS, self._on_first_configure_deadline,
                                  int(link.label_namespace))

    def _on_first_configure_deadline(self, namespace: int) -> None:
        """One cold configure timeout leaves the worker disabled for this run. The existing six-second bound
        includes startup; normal/stale/retired replies remain fenced and cannot disable a healthy successor."""
        link = self._worker
        # ``_retiring`` (A9-L1): a retire whose logical join failed returns before ``_retired`` with its routes already
        # detached; its first configure's deadline must not fall back and start a runtime on that half-retired owner.
        if (self._retired or self._retiring or link is None or link.configured
                or int(link.label_namespace) != int(namespace)):
            return
        logger.error("[SPOTIFY_VIS][ENGINE_WORKER] The first configure was not answered in %d ms; disabling the worker "
                     "for this run and running in process mode=%s",
                     _ACTIVATION_TRANSACTION_DEADLINE_MS, self._controller.mode_id)
        self._fall_back_in_process(f"configure unanswered in {_ACTIVATION_TRANSACTION_DEADLINE_MS} ms",
                                   count_for_run=True)

    def _open_engine_worker_session(self, inputs: dict[str, Any], supervisor: Any) -> Any:
        """A session for the controller's current mode and ``inputs``: its configure sent (closed again if sending
        fails); the reply binds its identity (``_on_worker_configured``)."""
        from widgets.spotify_visualizer.engine_worker_link import EngineWorkerLink

        controller = self._controller
        link = EngineWorkerLink(supervisor, on_lost=self._on_engine_worker_lost,
                                thread_manager=self._configure_services.get("thread_manager"))
        link.configure(runtime_generation=controller.runtime_generation, mode=controller.mode_id,
                       bar_count=controller.bar_count, activation=inputs,
                       on_configured=lambda identity, _link=link: self._on_worker_configured(_link, identity))
        return link

    def _adopt_engine_worker_session(self, link: Any, inputs: dict[str, Any]) -> None:
        """The session's reader becomes the controller's logical mailbox (with the owner's wake, once bound); its
        identity is unknown until the configure's reply."""
        controller = self._controller
        link.mailbox.set_trace_screen_index(int(self._presentation_runtime.screen_index))
        controller.replace_logical_mailbox(link.mailbox)
        wake = self._publication_wake
        if wake is not None:
            link.mailbox.set_wake_callback(wake.request)
        self._worker = link
        self._worker_identity = None
        self._activation_inputs = dict(inputs)
        # The framed view the tick reads follows the main controller's layout metrics and the presentation inputs the
        # capture reads (the view records, the mode's presentation-only controls: slice 5.4), latest wins, never
        # awaited; the reflected wallpaper stays here and completes each frame taken (A7-M1).
        from widgets.spotify_visualizer.backdrop import FrameBackdropCompletion
        from widgets.spotify_visualizer.logical_edges import presentation_inputs_snapshot

        presentation = controller.presentation_state
        link.set_view_source(lambda: (controller.layout_metrics_snapshot,
                                      presentation_inputs_snapshot(presentation, controller.mode_id)))
        self._release_frame_completion()
        self._frame_completion = FrameBackdropCompletion(presentation)
        link.mailbox.set_frame_completion(self._frame_completion)
        controller.set_layout_metrics_observer(self._on_layout_metrics_written)
        self._view_dirty = False
        link.send_view()

    def _release_frame_completion(self) -> None:
        """The frame completion's wallpaper goes with the session it completed (A8-L1): called once the session's
        reader is closed (no completion in flight: the reader's lock) or replaced."""
        completion, self._frame_completion = self._frame_completion, None
        if completion is not None:
            completion.release()

    def _on_worker_configured(self, link: Any, identity: tuple[int, int]) -> None:
        """GUI thread, the configure's reply: the session's engine identity. A first bind deferred for it binds now;
        a recovery takes it for its reveal; otherwise (a failed phase) the replacement is bound as it is."""
        if link is not self._worker or self._retired:
            return
        identity = (int(identity[0]), int(identity[1]))
        self._worker_identity = identity
        if link.bar_count is not None:
            self._controller.bar_count = link.bar_count   # presentation readers (Edit's envelope) see the session's
        logger.info("[SPOTIFY_VIS][ENGINE_WORKER] Visualizer configured on the engine worker mode=%s namespace=%d "
                    "engine=%s/%s", self._controller.mode_id, link.label_namespace, identity[0], identity[1])
        now = float(self._transition_clock())
        recovery = self._worker_recovery
        if recovery is not None:
            recovery["identity"] = identity
            if recovery["done"]:
                self._finish_worker_recovery(now)
        elif self._bind_deferred:
            self._bind_deferred = False
            self._render_identity = self._runtime.bind_visualizer_render_source(
                self._controller, engine_generation=identity[0], activation_id=identity[1])
        elif self._bound:
            self._bind_replacement(identity, now, reveal=False)
        if self._publication_wake is not None:
            self._publication_wake.request()          # a frame that arrived before the identity is presented now

    def _on_layout_metrics_written(self) -> None:
        """The controller's layout-metrics observer (engine worker only): one queued send per GUI turn, or, inside a
        presentation (which commits them on every publication), once at its end."""
        if self._in_sync_present:
            self._view_dirty = True
            return
        link = self._worker
        if link is not None:
            link.view_changed()

    def _forward_view(self) -> None:
        """At the end of a presentation: the layout metrics it committed, and any presentation input changed since
        (Edit's orbit, the camera keys, Auto Rotate, Home...), reach the session before its next step."""
        self._view_dirty = False
        self.forward_presentation_inputs()

    def forward_presentation_inputs(self) -> bool:
        """Send the session the framed view and presentation inputs changed since the last send (engine worker only;
        latest wins, at most one in flight). Runs at the end of every presentation; a host that changes them outside
        one (a rig's scripted orbit) calls it at once. Whether a send went out."""
        link = self._worker
        return bool(link is not None and link.send_view())

    def _set_display_power_on_worker(self, on: bool) -> bool:
        """Display power on the engine worker (sent, never awaited): the session parks (cadence, capture) or resumes
        warm. The park's reply follows the worker's last pre-park publish, so the reader drops its unread frame then,
        never before it (checkpoint audit 6, A6-L8), and no pre-park frame is presented hours later. Logged on the
        reply (A7-L5). Only the newest edge's reply acts (A8-L3): after OFF then ON, the OFF reply finds the displays
        back on and must not drop a post-unpark frame. (A recovery's held frame and deadline at a park / unpark:
        ``set_display_power``.)"""
        controller = self._controller
        link = self._worker
        self._display_power_edges += 1
        edge = self._display_power_edges

        def applied(_reply: dict, _link: Any = link, _edge: int = edge) -> None:
            if _link is not self._worker or _edge != self._display_power_edges:
                return                                # a newer display-power edge was sent: its reply settles it
            if not on:
                controller.logical_mailbox.clear()
            logger.info("[SPOTIFY_VIS][DISPLAY_POWER] Visualizer %s mode=%s (engine worker)",
                        "resumed" if on else "parked", controller.mode_id)

        try:
            link.set_display_power(on, on_reply=applied)
        except Exception as exc:
            self._on_engine_worker_failed(f"display power: {exc}")
        return True

    def _worker_set_playing(self, active: bool, observed_ts: float | None) -> None:
        """Media's play edge to the session (sent, never awaited). With the reactivity diagnostics on, the edge's T1
        is the send and its T2 the worker's reply (A7-L5; the tick-side records are the worker's)."""
        link = self._worker
        edge_seq = 0
        sent_ts = float(observed_ts if observed_ts is not None else authored_now())
        if is_viz_diagnostics_enabled():
            self._worker_playback_edges += 1
            edge_seq = self._worker_playback_edges
            logger.debug("[VIS_PLAYBACK_EDGE] stage=T1 edge=%d mode=%s playing=%s ts=%.6f (engine worker)",
                         edge_seq, self._controller.mode_id, active, sent_ts)

        def applied(_reply: dict) -> None:
            if edge_seq > 0:
                logger.debug("[VIS_PLAYBACK_EDGE] stage=T2 edge=%d mode=%s playing=%s dt_ms=%.1f (engine worker)",
                             edge_seq, self._controller.mode_id, active,
                             max(0.0, (authored_now() - sent_ts) * 1000.0))

        try:
            link.set_playing(active, on_reply=applied)
        except Exception as exc:
            self._on_engine_worker_failed(f"play edge: {exc}")

    def _worker_waiting_for_fresh_frame(self) -> bool:
        """``waiting_target`` on the engine worker: the session's tick state is the worker's, so the target's
        newest frame says it (a current-identity frame the tick marked presentable). Always waiting while the target's
        identity is not bound yet (a hidden activation's commit or a replacement's configure unanswered)."""
        if self._worker_commit is not None or self._worker_identity is None:
            return True
        publication = self._controller.logical_mailbox.peek()
        if publication is None:
            return True
        logical = publication.state
        identity = self._controller.render_identity
        return not (identity is not None and logical is not None and bool(logical.present_frame)
                    and int(logical.engine_generation) == identity.engine_generation
                    and int(logical.activation_id) == identity.activation_id
                    and str(logical.mode_id) == identity.mode_id)

    def _activate_pending_mode_on_worker(self, now: float, pending: dict[str, Any], *, kind: str, target: str,
                                         outgoing_mode: str, edit_profile_switched: bool) -> None:
        """The hidden activation commit on the engine worker: ``VIS_SET_MODE`` sent (applied at once in the session:
        the owner's ``commit_logical_activation`` there), the target kept hidden; the reply's committed identity binds
        the target and configures its presentation (``_on_worker_committed``). A same-mode preset or settings change is
        a whole re-activation of the session (interim: slice 5.4 applies a resolved settings delta instead)."""
        from core.settings.visualizer_mode_registry import get_visualizer_layout_profile

        controller = self._controller
        inputs = {key: pending[key] for key in ("settings_model", "resolved_activation", "technical_cache",
                                                 "logical_kwargs", "presentation_kwargs")}
        link = self._worker
        profile_changed = kind == "mode" and (get_visualizer_layout_profile(target)
                                              != get_visualizer_layout_profile(outgoing_mode))
        from widgets.spotify_visualizer.logical_edges import VIEW_RECORD_ATTRS

        state = controller.presentation_state
        commit = {"link": link, "kind": kind, "target": target, "outgoing": outgoing_mode, "inputs": inputs,
                  "profile_changed": profile_changed, "edit_profile_switched": edit_profile_switched,
                  # The main side's view records as the commit is sent: one the GUI thread replaces before the reply
                  # (a camera key meanwhile) is newer than the session's commit and is kept (A8-L2).
                  "view_records": {attr: getattr(state, attr, None) for attr in VIEW_RECORD_ATTRS}}
        self._worker_commit = commit
        self._waiting_target_since = now
        self._mode_transition_phase = "waiting_target"
        self._mode_transition_started_at = 0.0
        self._mode_transition_fade = 0.0
        if profile_changed:
            # The hidden transaction's profile switch, before the session commits the target: its configuration and
            # first tick read the target's committed layout metrics, as in process (sent now, before VIS_SET_MODE).
            controller.render_bridge.discard_pending()
            # The discarded snapshot was the fade-out's last, at zero content opacity, published in this same GUI
            # turn: the render item never consumed it and still retains the frame before it. In process the
            # target's identity is bound in this turn, which drops that frame at the next sync; here the identity
            # waits for the reply, so the outgoing frame is dropped explicitly (R-184).
            drop = getattr(self._presentation_runtime.scene_controller, "drop_visualizer_retained_frame", None)
            if callable(drop):
                drop()
            self._activate_committed_layout_profile(target)
            self._view_dirty = False
            link.send_view(force=True)
        try:
            link.set_mode(target, inputs,
                          on_committed=lambda identity, records, _commit=commit: self._on_worker_committed(
                              _commit, identity, records),
                          on_failed=lambda failure, _commit=commit: self._on_worker_commit_failed(_commit, failure))
        except Exception as exc:
            self._on_worker_commit_failed(commit, exc)

    def _on_worker_committed(self, commit: dict[str, Any], identity: tuple[int, int],
                             view_records: Mapping[str, Any] | None = None) -> None:
        """GUI thread, ``VIS_SET_MODE``'s reply: the target's committed identity (and the session's view records as
        its commit left them). The main side's presentation of the target, bound for that identity; the target stays
        hidden until its first presentable frame (``waiting_target``)."""
        from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
        from widgets.spotify_visualizer.engine_worker_link import configure_presentation_side

        if commit is not self._worker_commit or commit["link"] is not self._worker or self._retired:
            return
        self._worker_commit = None
        controller = self._controller
        kind, target, inputs = commit["kind"], commit["target"], commit["inputs"]
        generation, activation_id = int(identity[0]), int(identity[1])
        now = float(self._transition_clock())
        if kind == "mode":
            controller.set_mode(target)
        if commit["link"].bar_count is not None:
            controller.bar_count = commit["link"].bar_count  # the target's technical config, as in process (A7-M2)
        configure_presentation_side(controller, activation=inputs, playing=controller.playing,
                                    refresh_presentation=self._refresh_backdrop, **self._configure_services)
        if kind == "preset":
            from widgets.spotify_visualizer.view_orbit import rebase_view_orbit_motion

            # One arming owner (A8-L2): the session's commit rebased the motion and armed Auto Rotate (as the
            # in-process commit does, once, at its own time); the main side adopts those records instead of arming
            # again at the reply, which stepped the turn back by the reply's latency. The rebase here only drops the
            # GUI's own drag tail and inertia; a record the GUI replaced since the commit was sent is newer and stays
            # (it is forwarded as any edit is).
            state = controller.presentation_state
            before = commit["view_records"]
            current = {attr: getattr(state, attr, None) for attr in before}
            rebase_view_orbit_motion(state, now)
            adopted = {attr: value for attr, value in (view_records or {}).items()
                       if attr in before and current[attr] is before[attr]}
            for attr, value in adopted.items():
                setattr(state, attr, value)
            commit["link"].adopt_presentation_inputs(adopted)
        self._activation_inputs = dict(inputs)
        self._worker_identity = (generation, activation_id)
        self._render_identity = self._runtime.bind_visualizer_render_source(
            controller, engine_generation=generation, activation_id=activation_id)
        self._preparing_activation = (
            (target, activation_id) if get_visualizer_mode_descriptor(target).prepared_reveal else None
        )
        self._preparing_progress = None
        self._waiting_target_since = now
        logger.info("[SPOTIFY_VIS] Quick %s activation committed mode=%s generation=%s activation=%s (engine worker)",
                    kind, target, generation, activation_id)
        if self._publication_wake is not None:
            self._publication_wake.request()

    def _on_worker_commit_failed(self, commit: dict[str, Any], failure: Exception) -> None:
        """GUI thread: the hidden activation's commit failed (the session closed: A6-M2). The outgoing profiles are
        restored and the session's failure path runs; the frame stays at the fade it was drawn at (A7-L1: the
        completed fade-out drew it at 0, so nothing flashes back)."""
        if commit is not self._worker_commit:
            return
        if commit['link'] is self._worker and self._fail_closed_on_worker_capacity(commit['link']):
            return
        logger.error("[SPOTIFY_VIS][ENGINE_WORKER] Hidden %s activation FAILED source=%s target=%s: %s",
                     commit["kind"], commit["outgoing"], commit["target"], failure)
        self._abandon_worker_commit()
        if commit["link"] is self._worker:
            self._on_engine_worker_failed(f"activation failed: {failure}")

    def _abandon_worker_commit(self) -> None:
        """An uncommitted (or unanswered) hidden activation is dropped: the outgoing Edit and layout profiles are
        restored and the request is gone (the outgoing activation is the one a recovery replaces)."""
        commit, self._worker_commit = self._worker_commit, None
        if commit is None:
            return
        outgoing = commit["outgoing"]
        if commit["edit_profile_switched"] and self._edit_layout_profile_activator is not None:
            try:
                self._edit_layout_profile_activator(outgoing)
            except Exception:
                logger.exception("[SPOTIFY_VIS] Could not restore the outgoing Edit profile mode=%s", outgoing)
        if commit["profile_changed"]:
            try:
                self._activate_committed_layout_profile(outgoing)
            except Exception:
                logger.exception("[SPOTIFY_VIS] Could not restore the outgoing layout profile mode=%s", outgoing)
        self._pending_mode_activation = None

    def _on_engine_worker_lost(self, link: Any, reason: str) -> None:
        """GUI thread (an event): a reply failed, a correlation was cancelled, or the session's wake pipe ended. A
        first session whose configure never succeeded leaves the activation in process (not counted for the run);
        anything later is the session's failure path."""
        if link is not self._worker or self._retired:
            return
        if self._fail_closed_on_worker_capacity(link):
            return
        if not link.configured and self._worker_failures == 0:
            logger.warning("[SPOTIFY_VIS][ENGINE_WORKER] Configure failed (%s); this activation runs in process "
                           "mode=%s", reason, self._controller.mode_id)
            self._fall_back_in_process(f"configure failed: {reason}", count_for_run=False)
            return
        self._on_engine_worker_failed(reason)

    def _fail_closed_on_worker_capacity(self, link: Any) -> bool:
        """A violated admission envelope cannot be cured by retry or a different execution path."""
        mailbox = getattr(link, 'mailbox', None)
        failure = (getattr(link, 'capacity_failure_report', None)
                   or getattr(mailbox, 'capacity_failure', None))
        if failure is None:
            return False
        logger.error('[SPOTIFY_VIS][ENGINE_WORKER] Frame capacity contract FAILED mode=%s actual_bytes=%d '
                     'capacity_bytes=%d; session retired, activation held failed', self._controller.mode_id,
                     failure['actual_bytes'], failure['capacity_bytes'])
        self._abandon_worker_commit()
        self._mode_transition_phase = 'failed'
        self._worker_identity = None
        link.retire()
        return True

    def _on_worker_start_failed(self, link: Any, failure: Exception) -> None:
        """GUI thread: the first session's ``VIS_START`` failed; this activation runs in process (logged once, not
        counted for the run)."""
        if link is self._worker and not self._retired:
            if self._fail_closed_on_worker_capacity(link):
                return
            self._fall_back_in_process(f"start failed: {failure}", count_for_run=False)

    def _on_engine_worker_failed(self, reason: str) -> None:
        """A session failed (a failed reply, ``session_closed``, the session's end or worker death, a cancelled
        correlation: the supervisor's heartbeat restarted a hung worker). The last presented frame is held and fades
        out (never vanishes) while the replacement comes up: the first failure reconfigures the worker once, a second
        before that recovery's reveal completed keeps this owner in process for the run (a completed reveal starts the
        count again: A10-L4), and so does a failure once the run's recoveries are spent
        (``engine_worker_link.MAX_RECOVERIES_PER_RUN``, A11-M1). Never waits on the worker (the old session's stop and
        the replacement's configure are sent); bounded by the recovery deadline (``_on_recovery_deadline``)."""
        if self._retired or self._worker is None:
            return
        from widgets.spotify_visualizer import engine_worker_link as link_module

        link, self._worker = self._worker, None
        self._abandon_worker_commit()
        self._hold_for_recovery(link)
        link.retire()
        self._worker_failures += 1
        if self._mode_transition_phase == "failed":
            return                                   # one fenced reconstruction request already owns recovery
        if self._mode_transition_phase == "fading_out":
            # The request never committed: the outgoing activation is the one replaced.
            self._pending_mode_activation = None
        if self._worker_failures == 1 and not link_module.worker_disabled_for_run():
            if not link_module.claim_recovery_for_run():
                # The run's recoveries are spent (A11-M1): a failure that recurs after every completed reveal would
                # otherwise fade out, rebuild and fade in for the whole run.
                self._fall_back_in_process(
                    f"recovery limit ({link_module.MAX_RECOVERIES_PER_RUN} recoveries this run): {reason}")
                return
            logger.warning("[SPOTIFY_VIS][ENGINE_WORKER] Session failed (%s); reconfiguring once mode=%s",
                           reason, self._controller.mode_id)
            try:
                self._begin_worker_recovery()
                replacement = self._open_engine_worker_session(
                    self._activation_inputs, self._configure_services.get("process_supervisor"))
                self._adopt_engine_worker_session(replacement, self._activation_inputs)
                if self._worker is not replacement:
                    return
                if not self._display_power_on:
                    replacement.set_display_power(False)
                if self._started:
                    replacement.start(bool(self._controller.playing))
            except Exception as exc:
                self._fall_back_in_process(f"reconfigure failed: {exc}")
            return
        self._fall_back_in_process(f"second failure: {reason}")

    def _hold_for_recovery(self, link: Any) -> None:
        """Keep the frame on screen (the newest one taken from the failed session, and the fade it is drawn at) for
        the recovery's fade-out; a recovery already running keeps the frame it holds. Nothing is held while the
        displays are off (A7-L3: a held pre-park frame would be re-presented at the unpark)."""
        if self._worker_recovery is not None or self._recovery_held is not None or not self._display_power_on:
            return
        mailbox = link.mailbox
        held = mailbox.last_taken if mailbox is not None else None
        if held is not None:
            self._recovery_held = (held, float(self._mode_transition_fade))

    def _drop_recovery_hold(self) -> None:
        """The displays went off during a recovery: its held frame is dropped (A7-L3), and the replacement reveals
        from hidden after the unpark."""
        self._recovery_held = None
        recovery = self._worker_recovery
        if recovery is not None and recovery["held"] is not None:
            recovery["held"] = None
            recovery["done"] = True
            recovery["reveal"] = True
            self._mode_transition_fade = 0.0

    def _fall_back_in_process(self, reason: str, *, count_for_run: bool = True) -> None:
        """Leave the engine worker (contained: a fallback that raises never escapes into the edge's caller, Media's or
        display power's handlers: A7-M3; it escalates once to the generation-fenced reconstruction instead)."""
        try:
            self._fall_back_in_process_unguarded(reason, count_for_run=count_for_run)
        except Exception:
            logger.exception("[SPOTIFY_VIS][ENGINE_WORKER] The in-process fallback failed (%s)", reason)
            self._worker_recovery = None
            self._signal_transition_failure("engine_worker_fallback_failed")

    def _fall_back_in_process_unguarded(self, reason: str, *, count_for_run: bool = True) -> None:
        """The current activation configured, bound and (if started) started in process, exactly as the host binding
        builds it. ``count_for_run``: a second failure turns the worker off for the run (a failed first configure or
        start only leaves this activation in process)."""
        from widgets.spotify_visualizer import engine_worker_link as link_module
        from widgets.spotify_visualizer.logical_runtime import LatestStateMailbox
        from widgets.spotify_visualizer.technical_config import resolve_technical_config

        link, self._worker = self._worker, None
        self._abandon_worker_commit()
        if link is not None:
            self._hold_for_recovery(link)
            link.retire()
        self._release_frame_completion()
        if count_for_run and link_module.disable_worker_for_run(reason):
            logger.error("[SPOTIFY_VIS][ENGINE_WORKER] Off for the rest of the run: %s", reason)
        logger.warning("[SPOTIFY_VIS][ENGINE_WORKER] Running in process (%s) mode=%s", reason,
                       self._controller.mode_id)
        controller = self._controller
        inputs = self._activation_inputs
        playing = bool(controller.playing)
        controller.set_layout_metrics_observer(None)            # in process the tick reads them directly
        mailbox = LatestStateMailbox()
        mailbox.set_trace_screen_index(int(self._presentation_runtime.screen_index))
        controller.replace_logical_mailbox(mailbox)
        if self._publication_wake is not None:
            mailbox.set_wake_callback(self._publication_wake.request)
        self._worker_identity = None
        configure_logical_controller(
            controller,
            activation={key: inputs[key] for key in ("settings_model", "resolved_activation", "technical_cache")},
            logical_kwargs=inputs["logical_kwargs"],
            presentation_kwargs=inputs["presentation_kwargs"],
            technical_config=resolve_technical_config(inputs["technical_cache"], controller.mode_id),
            playing=False,
            refresh_presentation=self._refresh_backdrop,
            **self._configure_services,
        )
        # Media's state, as the host binding commits it before ``start`` (the engine is not started yet).
        apply_playback_edge(controller, playing, started=False)
        if not self._display_power_on:
            park_logical_side(controller, engine_acquired=False, clear_reader=controller.logical_mailbox.clear)
        if self._started:
            engine = prepare_engine_start(controller)

            def acquired() -> None:
                self._engine_acquired = True

            admit_engine_start(controller, engine, on_acquired=acquired, commit_playback=self.set_playing)
            self._start_logical_runtime()
            if release_engine_started_parked(engine, display_on=self._display_power_on,
                                             engine_acquired=self._engine_acquired):
                self._engine_acquired = False
                self._engine_released_for_display_power = True
        identity = self.engine_identity()
        if self._bind_deferred:
            # The first configure never answered: bind as the host binding would have, in process.
            self._bind_deferred = False
            self._render_identity = self._runtime.bind_visualizer_render_source(
                controller, engine_generation=identity[0], activation_id=identity[1])
            self._recovery_held = None
            return
        recovery = self._worker_recovery
        if recovery is not None:
            recovery["identity"] = identity           # the recovery goes on, revealing the in-process activation
            if recovery["done"]:
                self._finish_worker_recovery(float(self._transition_clock()))
            return
        self._begin_worker_recovery()
        if self._worker_recovery is not None:
            self._worker_recovery["identity"] = identity
            if self._worker_recovery["done"]:
                self._finish_worker_recovery(float(self._transition_clock()))

    def _begin_worker_recovery(self) -> None:
        """Hold the frame and fade it out on the replacement's own publications (they pace the fade and are not shown),
        from the fade it was drawn at, then reveal the replacement as an activation does (hidden until it publishes a
        presentable frame, then faded in) once its identity is known (``_on_worker_configured`` or the fallback). With
        nothing held (or the displays off) there is no fade: the replacement is bound, hidden when anything was shown
        or an activation was in flight. Never vanishes. Bounded: the recovery deadline is armed (``_on_recovery_deadline``)
        and the request serial is bumped, so a crossfade deadline armed earlier cannot fire into it (A7-M3)."""
        held, self._recovery_held = self._recovery_held, None
        if not self._bound or self._mode_transition_phase == "failed":
            return
        recovery = self._worker_recovery
        if recovery is not None:
            recovery["identity"] = None              # a second replacement goes on with the same fade
            return
        if not self._display_power_on:
            held = None
        reveal = (held is not None or self._mode_transition_phase != "idle" or self._mode_transition_fade < 1.0
                  or not self._display_power_on)
        publication, fade_from = held if held is not None else (None, 0.0)
        self._worker_recovery = {"held": publication, "revision": int(publication.revision) if publication else 0,
                                 "started_at": None, "fade_from": fade_from, "identity": None, "reveal": reveal,
                                 "done": publication is None}
        self._mode_transition_phase = "recovering"
        self._mode_transition_started_at = 0.0
        self._transition_request_serial += 1
        self._recovery_stage = 1
        self._arm_recovery_deadline()

    def _finish_worker_recovery(self, now: float) -> None:
        recovery, self._worker_recovery = self._worker_recovery, None
        if recovery is None:
            return
        if recovery["reveal"]:
            self._bind_replacement(recovery["identity"], now, reveal=True)
            # The reveal has its own deadline (A8-M1): the serial moves on, so the failure's shot is inert and a slow
            # but healthy replacement gets the whole window from here, not what is left of the failure's.
            self._transition_request_serial += 1
            self._arm_recovery_deadline()
        else:
            self._bind_replacement(recovery["identity"], now, reveal=False)
            self._mode_transition_phase = "idle"
            self._recovery_stage = 0

    def _bind_replacement(self, identity: tuple[int, int], now: float, *, reveal: bool) -> None:
        controller = self._controller
        controller.close_render_admission()       # a replacement may reuse the old identity; its revisions restart
        self._render_identity = self._runtime.bind_visualizer_render_source(
            controller, engine_generation=int(identity[0]), activation_id=int(identity[1]))
        self._preparing_activation = None
        if reveal:
            self._waiting_target_since = now
            self._mode_transition_phase = "waiting_target"
            self._mode_transition_started_at = 0.0
            self._mode_transition_fade = 0.0

    def _sync_recovery(self, now: float) -> bool:
        """``recovering``: each replacement publication paces one step of the held frame's fade-out (the replacement's
        frame is taken, never shown); once faded out (or with nothing held), the replacement is bound and revealed as
        soon as its identity is known."""
        recovery = self._worker_recovery
        if recovery is None:
            self._mode_transition_phase = "idle"
            return False
        if recovery["done"]:
            if recovery["identity"] is not None:
                self._finish_worker_recovery(now)
                return self._sync.sync_latest()
            return False
        publication = self._controller.logical_mailbox.take()
        if publication is None:
            return False
        if recovery["started_at"] is None:
            recovery["started_at"] = now
        duration = self._transition_half_duration_s
        elapsed = max(0.0, now - recovery["started_at"])
        progress = 1.0 if duration <= 0.0 else min(1.0, elapsed / duration)
        if progress < 1.0:
            self._mode_transition_fade = float(recovery["fade_from"]) * (1.0 - progress)
            resolve, commit = self._route_pair()
            presentation = resolve()
            if presentation is None:
                return False
            recovery["revision"] += 1
            held = recovery["held"]
            if not self._controller.publish_render_snapshot(held.state, presentation,
                                                            logical_revision=recovery["revision"]):
                return False
            commit(presentation)
            self._request_retained_present()
            return True
        recovery["done"] = True
        self._mode_transition_fade = 0.0
        if recovery["identity"] is not None:
            self._finish_worker_recovery(now)
        return True

    # The recovery's bound (A7-M3) -------------------------------------------------------------------------------

    def _arm_recovery_deadline(self) -> None:
        """One generation-fenced single-shot per recovery stage (the transaction deadline's machinery, never a poll),
        fenced by the request serial; never armed while the displays are off (a parked replacement publishes nothing:
        the unpark arms it)."""
        if self._retired or not self._display_power_on:
            return
        from core.threading.manager import ThreadManager

        ThreadManager.single_shot(_ACTIVATION_TRANSACTION_DEADLINE_MS, self._on_recovery_deadline,
                                  self._transition_request_serial)

    def _rearm_recovery_deadline(self) -> None:
        if self._recovery_stage and self._mode_transition_phase in ("recovering", "waiting_target"):
            self._transition_request_serial += 1
            self._arm_recovery_deadline()

    def _on_recovery_deadline(self, serial: int) -> None:
        """The recovery did not complete in time. First: the replacement never published (or never revealed), so the
        owner falls back in process once (counted for the run); the in-process runtime's publications pace the held
        frame's fade and the reveal, under a second deadline. Second (now in process): a reveal that never came, or a
        held frame nothing paced any more, escalates to the generation-fenced reconstruction, exactly as an in-process
        activation's deadline does (``_on_transition_deadline``; A8-M2): the display's reload retires this owner (its
        hidden runtime with it) and the rebuilt one fades in, as in process. As in process, the reconstruction is
        neither capped nor guaranteed: a reload the engine refuses (Settings owns runtime recreation, a recreation is
        pending, a stale request) leaves this owner in ``failed`` at fade 0 with its runtime running, and an
        activation that never reveals reloads about every deadline (checkpoint audit 9, A9-L3; a general follow-up in
        ``Current_Plan.md``, not an engine-worker one)."""
        if self._retired or self._transition_request_serial != serial or not self._display_power_on:
            return
        phase = self._mode_transition_phase
        if not self._recovery_stage or phase not in ("recovering", "waiting_target"):
            return
        if self._recovery_stage == 1 and self._worker is not None:
            self._recovery_stage = 2
            logger.error("[SPOTIFY_VIS][ENGINE_WORKER] The replacement session did not come back in %d ms (phase=%s); "
                         "falling back in process", _ACTIVATION_TRANSACTION_DEADLINE_MS, phase)
            self._fall_back_in_process(f"recovery deadline ({phase})")
            if self._mode_transition_phase in ("recovering", "waiting_target"):
                self._transition_request_serial += 1
                self._arm_recovery_deadline()
            return
        self._recovery_stage = 0
        self._worker_recovery = None
        self._preparing_activation = None
        if phase == "waiting_target":
            logger.error("[SPOTIFY_VIS][ENGINE_WORKER] The recovered Visualizer never revealed (no presentable frame "
                         "in %d ms) mode=%s", _ACTIVATION_TRANSACTION_DEADLINE_MS, self._controller.mode_id)
        self._signal_transition_failure("deadline:" + phase)

    def retire(self) -> bool:
        if self._retired:
            return False
        self._retiring = True       # the first configure's deadline is inert from here, joined or not (A9-L1)
        # Disarm the queued one-shot before touching Qt/engine retirement roots;
        # even a failed logical join must not make a stale transition callback
        # re-enter this partially detached generation.
        self._transition_request_serial = getattr(self, "_transition_request_serial", 0) + 1
        self.set_edit_orbit_publication_callback(None)
        # The mailbox wake is installed during bind(), before start(). A failed
        # start must not leave a logical-thread callback targeting a retired Qt
        # object, so detach this edge regardless of whether logical cadence ran.
        self._controller.logical_mailbox.set_wake_callback(None)
        self._controller.render_bridge.set_sync_admission(None)
        # On the engine-worker path the controller holds this owner's layout-metrics observer (a bound method), so
        # owner -> controller -> observer -> owner is a cycle: the destruction barrier, which judges the retiring
        # generation's owners by reference counting, never saw this owner released and timed out (R-178). In process
        # no observer is installed (a no-op).
        self._controller.set_layout_metrics_observer(None)
        wake = self._publication_wake
        if wake is not None:
            wake.close()
        if self._started:
            self._runtime.scene_controller.set_visualizer_double_click_admission(None)
            self._runtime.scene_controller.set_visualizer_middle_click_admission(None)
        if self._expanded_overlays_drawn and self._presentation_runtime is not None:
            # The full-display overlays leave with the owner (a reload or Visualizer off; a retiring scene ignores it).
            self._expanded_overlays_drawn = False
            setter = getattr(self._presentation_runtime.scene_controller,
                             "set_visualizer_expanded_overlays_drawn", None)
            if callable(setter):
                setter(False)
        if self._bound:
            # Especially after a CUSTOM display transfer, the active scene must
            # not retain controller.set_custom_viewport_override and thereby keep
            # this generation-scoped owner alive past the destruction barrier.
            self._presentation_runtime.scene_controller.set_visualizer_viewport_config_sink(None)
            self._presentation_runtime.scene_controller.set_presentation_image_listener(None)
            self._controller.presentation_state._backdrop = None
        if self._worker is not None:
            link, self._worker = self._worker, None
            # The session's stop is sent, never awaited (it ends in the worker in order: capture and its mapping view
            # released), then the reader closes and the main process unlinks the mapping. Before the logical join
            # (checkpoint audit 10, A10-L1): a join that fails or raises returns before the rest of the retirement, and
            # the link's retire never waits, so the session's VIS_STOP and its lease's release never depend on it (an
            # owner on the worker normally has no logical runtime to join; one in process has no link).
            link.retire()
        self._release_frame_completion()          # its reader is closed (or there was none): nothing in flight
        try:
            self.release_prepared_display()        # a neighbour prepared ahead of a hop (1C.2)
        except Exception:
            logger.exception("[SPOTIFY_VIS] A prepared neighbour could not be released at retirement")
        joined = bool(self._controller.stop_logical_runtime())
        if not joined:
            return False
        if self._engine_acquired:
            release = getattr(self._controller.engine, "release", None)
            if callable(release):
                release()
            self._engine_acquired = False
        self._retired = True
        self._controller.close_render_admission()
        # All product/runtime routes have detached, the sole authored logical
        # runtime has joined, and the engine release fence has been applied
        # above. Explicitly sever the remaining
        # owner -> Quick-runtime links before the display starts window
        # retirement.  Those links otherwise complete a signal/closure cycle
        # through the live scene that a startup-frozen generation cannot
        # collect until process stop.  Keep the controller for post-retirement
        # diagnostics (and its stopped-runtime contract), but never leave it
        # reachable through a retired Quick scene.
        self._runtime = None
        self._presentation_runtime = None
        self._sync = None
        self._publication_wake = None
        self._pending_mode_activation = None
        self._preparing_activation = None
        self._worker_recovery = None
        self._recovery_held = None
        self._worker_commit = None
        self._recovery_stage = 0
        # A takeover fade dies with the owner; its completion is never reported to a retired generation.
        try:
            self._abandon_display_move()
        except Exception:
            logger.exception("[SPOTIFY_VIS] A display move's prewarm could not be ended at retirement")
        self._takeover = None
        self._expanded_display = False
        self._expanded_source = None
        self._transition_request_serial += 1  # disarm any queued one-shot
        self._transition_failure_callback = None
        self._presentation_resolver = None
        self._committed_layout_profile_resolver = None
        self._edit_layout_profile_activator = None
        self._render_identity = None
        self._started = False
        self._bound = False
        self._card_shadow_kwargs.clear()
        return True


__all__ = ["QuickDisplayVisualizerOwner"]
