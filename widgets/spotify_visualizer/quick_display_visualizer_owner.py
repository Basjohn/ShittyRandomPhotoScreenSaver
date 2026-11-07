"""Thin Quick per-display visualizer ownership edge (H).

This is the small destination-side assembly that owns one
``VisualizerRuntimeController`` per display/generation and binds it into a
``QuickDisplayRuntime``. It invents no visualizer subsystem: the controller
already owns mode/settings, the shared BeatEngine/source, the authored
``VisualizerLogicalRuntime`` and controller-owned logical tick state, viewport
configuration and render-bridge publication.
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

logger = get_logger(__name__)

_DEFAULT_MAX_FPS = 90.0
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


class _TakeoverFade:
    """One display-wide viewport change in flight (Expanded Visualizer, plan 01 §D1.7/§D2.4).

    The whole Visualizer presentation fades out where it is, the viewport swaps at the midpoint, and it fades in
    at the target: one GL target reallocation, at the swap, never one per frame of a geometry tween. It is sampled
    on the existing publication edge against the owner's transition clock, like the activation and mode fades; it
    owns no timer.
    """

    __slots__ = ("target", "source", "started_at", "on_complete", "drawn_expanded", "done")

    def __init__(self, *, target: bool, source: bool, started_at: float,
                 on_complete: Callable[[], None] | None) -> None:
        self.target = target
        self.source = source
        self.started_at = started_at
        self.on_complete = on_complete
        self.drawn_expanded = source
        self.done = False


def _shared_beat_engine(bar_count: int) -> Any:
    """The production engine factory: the registry's one shared beat engine (imported on first use, so building
    an owner imports no capture code)."""
    from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine
    return get_shared_spotify_beat_engine(bar_count)


def _mode_runtime_factory(mode_id: str) -> Callable[[], Any]:
    """Resolve a mode's frame-runtime class from the canonical descriptor wiring.

    The per-mode import path lives once in
    ``core.settings.visualizer_mode_registry``; this reads that string and
    imports lazily, so no frame runtime is imported until its mode is actually
    constructed. An unknown/empty mode falls back to Spectrum exactly as the
    previous hand-written switch did.
    """
    from importlib import import_module

    from core.settings.visualizer_mode_registry import (
        get_visualizer_mode_descriptor,
    )

    normalized = str(mode_id or "").lower()
    try:
        descriptor = get_visualizer_mode_descriptor(normalized)
    except KeyError:
        descriptor = get_visualizer_mode_descriptor("spectrum")
    module = import_module(descriptor.frame_runtime_module)
    return getattr(module, descriptor.frame_runtime_class)


class QuickDisplayVisualizerOwner:
    """Own + bind one visualizer controller for one Quick display generation."""

    # Console display power defaults (on); __init__ and set_display_power own the instance values.
    _display_power_on = True
    _engine_released_for_display_power = False

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
        self._expanded_source: Any = None
        self._expanded_edge_margin = 0.0

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
        if not on:
            if not controller.set_logical_parked(True):
                logger.error("[SPOTIFY_VIS][DISPLAY_POWER] Logical runtime did not park; it stays requested")
            controller.logical_mailbox.clear()
            if self._engine_acquired:
                release = getattr(controller.engine, "release", None)
                if callable(release):
                    release()
                self._engine_acquired = False
                self._engine_released_for_display_power = True
            logger.info("[SPOTIFY_VIS][DISPLAY_POWER] Visualizer parked mode=%s", controller.mode_id)
            return True
        engine = controller.ensure_engine() if self._started else None
        if engine is not None:
            if self._engine_released_for_display_power:
                acquire = getattr(engine, "acquire", None)
                if callable(acquire):
                    acquire()
                self._engine_acquired = True
                self._engine_released_for_display_power = False
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
                logger.error("[SPOTIFY_VIS][DISPLAY_POWER] Resume found the logical runtime unparked; "
                             "clocks not rebased")
        controller.set_logical_parked(False)
        logger.info("[SPOTIFY_VIS][DISPLAY_POWER] Visualizer resumed mode=%s", controller.mode_id)
        return True

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
    ) -> None:
        if self._retired:
            raise RuntimeError("cannot configure a retired visualizer owner")
        self._apply_configuration(
            logical_kwargs=logical_kwargs,
            presentation_kwargs=presentation_kwargs,
            technical_config=technical_config,
            thread_manager=thread_manager,
            process_supervisor=process_supervisor,
            playing=playing,
            reason="quick_owner_configure",
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
        from widgets.spotify_visualizer.config_applier import (
            apply_logical_vis_mode_kwargs,
            apply_presentation_vis_mode_kwargs,
        )
        from widgets.spotify_visualizer.logical_tick_state import (
            install_default_logical_tick_state,
        )

        from widgets.spotify_visualizer.presentation_state import (
            install_default_presentation_state,
        )

        controller = self._controller
        state = controller.logical_tick_state
        from widgets.spotify_visualizer.source_config_applier import (
            resolve_mode_source_config,
        )

        resolved_logical_kwargs = (
            resolve_mode_source_config(controller.mode_id, logical_kwargs)
            if logical_kwargs is not None
            else None
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
            apply_presentation_vis_mode_kwargs(
                controller.presentation_state, resolved_presentation_kwargs
            )
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

        # Source-owned preset semantics used to be side effects of the mixed
        # QWidget config applier.  Quick has no widget presenter, so route those
        # values explicitly to the one existing BeatEngine at configuration
        # time.  ``logical_kwargs`` is the canonical settings payload in
        # production; presentation is only a fallback for focused callers.
        source_kwargs = (
            resolved_logical_kwargs
            if resolved_logical_kwargs is not None
            else resolved_presentation_kwargs
        )
        if source_kwargs:
            from widgets.spotify_visualizer.source_config_applier import (
                apply_engine_vis_mode_kwargs,
            )

            apply_engine_vis_mode_kwargs(engine, source_kwargs)

        # Technical settings are a complete canonical/preset-resolved contract.
        # Missing mode configuration is an authority error at configuration
        # time; it must not leak into renderer/DSP fallbacks later.
        resolved_technical = technical_config
        if resolved_technical is None:
            cache = controller.technical_config_cache
            if not isinstance(cache, dict):
                raise RuntimeError("visualizer technical cache is unavailable")
            from widgets.spotify_visualizer.technical_config import (
                resolve_technical_config,
            )
            resolved_technical = resolve_technical_config(cache, controller.mode_id)
        from widgets.spotify_visualizer.quick_technical_config import (
            apply_controller_technical_config,
        )

        apply_controller_technical_config(
            controller,
            resolved_technical,
            reason=reason,
        )
        self._refresh_backdrop()

        controller.resolve_logical_mode_state(
            controller.mode_id, _mode_runtime_factory(controller.mode_id)
        )
        state._mode_teardown_block_until_ready = False
        state._mode_transition_ready = True
        # Lead E1: a persistent (shared) beat engine keeps its last committed frame
        # across owner recreation. On a same-generation warm re-entry that retained
        # frame would satisfy the generation-only fresh-frame fence and be admitted
        # as the first reactive result (a flash of seconds-old audio energy). Arm
        # the fence with a commit-seq watermark so only a frame committed after this
        # re-entry is accepted. A cold engine (no prior frame) is left unfenced, so
        # cold start is byte-for-byte unchanged.
        from widgets.spotify_visualizer.tick_pipeline import (
            arm_reentry_fresh_frame_fence,
        )

        warm_reentry = arm_reentry_fresh_frame_fence(state, engine)
        if warm_reentry and is_viz_diagnostics_enabled():
            # E2 attribution (diagnostics-only): arm the existing T3..T6 markers on
            # this warm recreation so the fresh-source -> retained-presentation gap
            # is attributable exactly like a play/pause edge, labelled kind=recreation.
            from widgets.spotify_visualizer.reactivity_diagnostics import (
                begin_playback_edge,
            )

            begin_playback_edge(
                state,
                now_ts=authored_now(),
                playing=bool(controller.playing),
                kind="recreation",
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

    def bind(self, *, engine_generation: int, activation_id: int) -> Any:
        if self._retired:
            raise RuntimeError("cannot bind a retired visualizer owner")
        self._render_identity = self._runtime.bind_visualizer_render_source(
            self._controller,
            engine_generation=int(engine_generation),
            activation_id=int(activation_id),
        )
        self._runtime.bind_visualizer_viewport_config(
            self._controller.set_custom_viewport_override
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

        controller.playing = active
        engine = controller.ensure_engine()
        if active and not previous and self._started:
            wake = getattr(engine, "wake", None)
            if callable(wake):
                # Historical pause->play contract: wake the sole shared capture
                # owner before committing playback truth.  wake() itself only
                # restarts stale capture and otherwise remains a cheap no-op.
                wake()
        set_playback_state = getattr(engine, "set_playback_state", None)
        if not callable(set_playback_state):
            raise RuntimeError("visualizer BeatEngine has no playback-state authority")
        set_playback_state(active)
        if active and not previous:
            # Lead E1: warm resume must not admit the pre-pause retained frame as
            # the first reactive result. Arm the commit-seq watermark so the first
            # accepted reactive frame is one the engine committed after this resume
            # edge. Cold engines are left unfenced (see the helper).
            from widgets.spotify_visualizer.tick_pipeline import (
                arm_reentry_fresh_frame_fence,
            )

            arm_reentry_fresh_frame_fence(controller.logical_tick_state, engine)
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
                self._controller.set_custom_viewport_override
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
                self._controller.set_custom_viewport_override
            )
            old_presentation_runtime.scene_controller.set_presentation_image_listener(self._refresh_backdrop)
            raise
        return True

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

    def set_expanded_display(
        self,
        expanded: bool,
        *,
        animate: bool = False,
        on_complete: Callable[[], None] | None = None,
        edge_margin: float | None = None,
    ) -> bool:
        """Show the Visualizer card near the display's extents, or back at its ordinary rect, at this event edge.

        ``edge_margin`` (logical px, the card's ordinary edge margin) insets the display-wide card on every side;
        ``None`` keeps the last one.

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
        if edge_margin is not None:
            margin = float(edge_margin)
            self._expanded_edge_margin = margin if math.isfinite(margin) and margin > 0.0 else 0.0
        self._takeover = None
        if not animate:
            self._finish_takeover(expanded, on_complete, reapply=True)
            return True
        self._takeover = _TakeoverFade(
            target=expanded,
            source=self._expanded_display,
            started_at=float(self._transition_clock()),
            on_complete=on_complete,
        )
        self._sync.set_presentation_route(
            self._resolve_takeover_presentation, self._commit_takeover_presentation
        )
        if self._started:
            # Present the first faded frame now; later frames ride the logical publications.
            self._reapply_route()
        return True

    def _route_pair(self) -> tuple[Callable[[], Any], Callable[[Any], None]]:
        if self._takeover is not None:
            return self._resolve_takeover_presentation, self._commit_takeover_presentation
        if self._expanded_display:
            return self._resolve_expanded_presentation, self._apply_expanded_presentation
        return self._resolve_current_presentation, self._apply_resolved_presentation

    def _reapply_route(self) -> None:
        """Resolve and commit once through the current route at an event edge (not a cadence)."""

        resolve, commit = self._route_pair()
        presentation = resolve()
        if presentation is None:
            return
        commit(presentation)
        scene = self._presentation_runtime.scene_controller
        request = getattr(scene, "request_visualizer_present", None)
        if callable(request):
            request()

    def _finish_takeover(
        self, expanded: bool, on_complete: Callable[[], None] | None, *, reapply: bool
    ) -> None:
        self._takeover = None
        self._expanded_display = bool(expanded)
        if not expanded:
            self._expanded_source = None
        resolve, commit = self._route_pair()
        self._sync.set_presentation_route(resolve, commit)
        if reapply and self._started:
            self._reapply_route()
        if on_complete is not None:
            on_complete()

    def _resolve_expanded_presentation(self) -> Any:
        ordinary = self._resolve_current_presentation()
        if ordinary is None:
            return None
        from widgets.spotify_visualizer.presentation_geometry import (
            resolve_expanded_visualizer_presentation,
        )

        _x, _y, width, height = self._presentation_runtime.display_identity.geometry
        self._expanded_source = ordinary
        return resolve_expanded_visualizer_presentation(
            ordinary,
            display_size=(float(width), float(height)),
            # Never more than a quarter of the shorter side: a card always remains.
            edge_margin=min(self._expanded_edge_margin, min(float(width), float(height)) / 4.0),
        )

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

        half = self._transition_half_duration_s
        elapsed = max(0.0, float(self._transition_clock()) - takeover.started_at)
        if half <= 0.0 or elapsed >= 2.0 * half:
            takeover.drawn_expanded = takeover.target
            takeover.done = True
            return 1.0
        if elapsed < half:
            takeover.drawn_expanded = takeover.source
            linear = 1.0 - elapsed / half
        else:
            takeover.drawn_expanded = takeover.target
            linear = (elapsed - half) / half
        return linear * linear * (3.0 - 2.0 * linear)

    def _resolve_takeover_presentation(self) -> Any:
        takeover = self._takeover
        if takeover is None:
            resolve, _commit = self._route_pair()
            return resolve()
        fade = self._takeover_fade(takeover)
        base = (
            self._resolve_expanded_presentation()
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
        if takeover is not None and takeover.done and self._takeover is takeover:
            # The target is on screen at full opacity: commit the steady route, then report completion.
            self._finish_takeover(takeover.target, takeover.on_complete, reapply=False)

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
        presentation = self._presentation_runtime.scene_controller.visualizer_item.presentation
        if presentation is None:
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
        self._controller.render_bridge.discard_if_presentation_differs(presentation)
        # Save promotes the complete sparse map, not only the currently visible
        # mode, so modes rotated earlier in the same edit session survive an
        # in-process mode switch without requiring recreation.
        self._controller.commit_content_rotation_map(content_rotation_by_mode)
        self._committed_layout_rect = tuple(float(value) for value in presentation.outer_rect)
        self._committed_layout_extent = (extent_width, extent_height)
        self._legacy_layout_profile = None
        self._legacy_layout_source_variant = None

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
            working = self._presentation_runtime.scene_controller.visualizer_item.presentation
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
            self._mode_transition_fade = 1.0
            try:
                self._reapply_route()
                self._request_retained_present()
            except Exception:
                logger.exception("[SPOTIFY_VIS] Could not restore stalled outgoing scene")
                self._signal_transition_failure("fade_out_restore_failed")
            else:
                logger.error("[SPOTIFY_VIS] Cancelled stalled fade-out while outgoing mode remained live")
            return
        self._signal_transition_failure("deadline:" + phase)

    def sync_present(self) -> bool:
        try:
            return self._sync_present_transaction()
        except Exception:
            if getattr(self, "_mode_transition_phase", "idle") == "idle":
                raise
            logger.exception("[SPOTIFY_VIS] Retained visualizer mode activation failed")
            self._signal_transition_failure("activation_exception")
            return False

    def _sync_present_transaction(self) -> bool:
        if self._retired or self._sync is None:
            return False
        phase = self._mode_transition_phase
        if phase == "idle":
            return self._sync.sync_latest()
        if phase == "failed":
            # One fenced reconstruction request already owns recovery. Never
            # turn subsequent logical mailbox wakes into an exception storm.
            return False

        now = float(self._transition_clock())
        elapsed = max(0.0, now - self._mode_transition_started_at)
        duration = self._transition_half_duration_s
        progress = 1.0 if duration <= 0.0 else min(1.0, elapsed / duration)
        if phase == "fading_out":
            self._mode_transition_fade = 1.0 - progress
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
                self._controller.logical_tick_state._waiting_for_fresh_engine_frame
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
        if now - self._waiting_target_since < _PREPARED_REVEAL_DEADLINE_S:
            item = self._presentation_runtime.scene_controller.visualizer_item
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
        self._mode_transition_phase = "fading_out"
        self._mode_transition_started_at = float(self._transition_clock())
        self._mode_transition_fade = 1.0
        self._transition_request_serial += 1
        self._transition_recovery_issued = False
        try:
            self._arm_transition_deadline()
        except Exception:
            # A GUI with no effective deadline cannot safely admit a potentially
            # infinite hidden transition. Leave the previous source untouched.
            self._pending_mode_activation = None
            self._mode_transition_phase = "idle"
            self._mode_transition_fade = 1.0
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
        engine = controller.ensure_engine()
        if not controller.stop_logical_runtime():
            if edit_profile_switched and self._edit_layout_profile_activator is not None:
                self._edit_layout_profile_activator(previous_mode)
            self._mode_transition_phase = "failed"
            raise RuntimeError("visualizer logical runtime did not join for activation")

        begin = getattr(engine, "begin_activation_transaction", None)
        end = getattr(engine, "end_activation_transaction", None)
        if not callable(begin) or not callable(end):
            self._mode_transition_phase = "failed"
            raise RuntimeError("visualizer BeatEngine has no activation transaction")

        target = str(pending["mode"])
        kind = str(pending.get("kind") or "mode")
        outgoing_mode = str(controller.mode_id)
        activation_step = "begin_engine_transaction"
        try:
            begin()
        except Exception:
            self._mode_transition_phase = "failed"
            raise
        try:
            if kind == "mode":
                from core.settings.visualizer_mode_registry import (
                    get_visualizer_layout_profile,
                )

                if (
                    get_visualizer_layout_profile(target)
                    != get_visualizer_layout_profile(controller.mode_id)
                ):
                    # The logical runtime is stopped and the target is still hidden.
                    # Drop any unread old-mode snapshot before switching geometry so
                    # it cannot be rejected later as a one-frame stale presentation.
                    controller.render_bridge.discard_pending()
                    # Edit's target profile was already projected/validated
                    # BEFORE stopping the outgoing logical runtime. Never
                    # repeat a fallible QML projection inside this transaction.
                    activation_step = "activate_committed_profile"
                    self._activate_committed_layout_profile(target)
                activation_step = "set_controller_mode"
                controller.set_mode(target)
            elif target != controller.mode_id:
                raise RuntimeError("preset activation attempted to change visualizer mode")
            activation_step = "configure_target"
            controller.settings_model = pending["settings_model"]
            controller.record_resolved_activation(pending["resolved_activation"])
            controller.technical_config_cache = dict(pending["technical_cache"])
            from widgets.spotify_visualizer.technical_config import (
                resolve_technical_config,
            )
            self._apply_configuration(
                logical_kwargs=pending["logical_kwargs"],
                presentation_kwargs=pending["presentation_kwargs"],
                technical_config=resolve_technical_config(
                    controller.technical_config_cache, target
                ),
                thread_manager=controller.thread_manager,
                process_supervisor=controller.process_supervisor,
                playing=controller.playing,
                reason=f"quick_owner_{kind}_change",
            )
            if kind == "preset":
                from widgets.spotify_visualizer.view_orbit import (
                    arm_view_auto_rotate, rebase_view_orbit_motion,
                )
                # The target is configured and hidden, and logical capture is
                # stopped. Publish its complete motion state before restarting:
                # old same-mode auto rotation must not override its first pose.
                activation_step = "activate_target_view_motion"
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
            # Qt's GUI callback boundary may otherwise discard the Python
            # traceback, leaving only an invisible Visualizer and a stopped
            # logical runtime. Record the exact failed transaction stage.
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
                    return
            self._mode_transition_phase = "failed"
            raise
        finally:
            end(reason=f"quick_{kind}_change:{target}")

        activation_step = "bind_fresh_target"
        try:
            generation = int(engine.get_generation_id())
            activation_id = int(engine.get_activation_id())
            state = controller.logical_tick_state
            state._pending_engine_generation = generation
            state._pending_engine_activation_id = activation_id
            state._waiting_for_fresh_engine_frame = True
            state._waiting_for_fresh_frame = True
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
        from widgets.spotify_visualizer.tick_pipeline import logical_tick

        # Warm the first-publish import chain here, during activation and before
        # the cadence thread starts, so the first logical tick does not pay the
        # one-shot cold import of the immutable frame-capture module (and its
        # render-state / config-applier / frame-runtime deps) on the cadence
        # thread's first step. This moves a one-shot activation cost off the
        # first frame; it adds no per-frame work (the import is a no-op once
        # cached) and does not change the authored cadence.
        from widgets.spotify_visualizer import logical_frame_capture  # noqa: F401

        controller = self._controller
        interval = (
            float(interval_s)
            if interval_s is not None
            else 1.0 / max(15.0, _DEFAULT_MAX_FPS)
        )
        controller.start_logical_runtime(
            step=lambda _deadline_ts, _s=controller.logical_tick_state: logical_tick(_s),
            interval_s=interval,
        )

    def start(self, *, interval_s: float | None = None) -> None:
        if self._retired:
            raise RuntimeError("cannot start a retired visualizer owner")
        controller = self._controller
        if not self._configured or not self._bound:
            raise RuntimeError("visualizer owner must be configured and bound before start")
        engine = controller.ensure_engine()
        set_thread_manager = getattr(engine, "set_thread_manager", None)
        if controller.thread_manager is not None and callable(set_thread_manager):
            set_thread_manager(controller.thread_manager)
        set_generation = getattr(engine, "set_runtime_generation", None)
        if callable(set_generation):
            set_generation(controller.runtime_generation)
        acquire = getattr(engine, "acquire", None)
        try:
            if callable(acquire):
                acquire()
                self._engine_acquired = True
            self.set_playing(controller.playing)
            if controller.playing:
                # Media may have committed True before start acquired the source and bound ThreadManager.
                # Same-state playback does not create a BeatEngine edge, so cold admission is explicit here.
                ensure_started=getattr(engine,'ensure_started',None)
                if callable(ensure_started):ensure_started()
            # Arm the authored scene fade before the logical producer can publish
            # the first frame. Mailbox empty->populated publication wakes Qt's GUI
            # thread directly; there is no display-refresh polling pacer here.
            self._activation_fade_started_at = float(self._transition_clock())
            self._started = True
            self._start_logical_runtime(interval_s=interval_s)
            if not self._display_power_on and self._engine_acquired:
                # Started while the displays are off: the runtime started parked;
                # hold no capture reference until they come back.
                release = getattr(engine, "release", None)
                if callable(release):
                    release()
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

    def retire(self) -> bool:
        if self._retired:
            return False
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
        wake = self._publication_wake
        if wake is not None:
            wake.close()
        if self._started:
            self._runtime.scene_controller.set_visualizer_double_click_admission(None)
            self._runtime.scene_controller.set_visualizer_middle_click_admission(None)
        if self._bound:
            # Especially after a CUSTOM display transfer, the active scene must
            # not retain controller.set_custom_viewport_override and thereby keep
            # this generation-scoped owner alive past the destruction barrier.
            self._presentation_runtime.scene_controller.set_visualizer_viewport_config_sink(None)
            self._presentation_runtime.scene_controller.set_presentation_image_listener(None)
            self._controller.presentation_state._backdrop = None
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
        # A takeover fade dies with the owner; its completion is never reported to a retired generation.
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
