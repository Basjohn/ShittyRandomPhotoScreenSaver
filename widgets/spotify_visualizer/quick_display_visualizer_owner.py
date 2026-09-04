"""Thin Quick per-display visualizer ownership edge (H).

This is the small destination-side assembly that owns one
``VisualizerRuntimeController`` per display/generation and binds it into a
``QuickDisplayRuntime``. It invents no visualizer subsystem: the controller
already owns mode/settings, the shared BeatEngine/source, the authored
``VisualizerLogicalRuntime`` and controller-owned logical tick state, viewport
configuration and render-bridge publication.
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any, Callable, Mapping

from core.logging.logger import get_logger, is_viz_diagnostics_enabled

logger = get_logger(__name__)

_DEFAULT_MAX_FPS = 90.0
_MODE_TRANSITION_HALF_DURATION_S = 0.25
# Authored first-appearance reveal for the visualizer scene fade. The whole
# visualizer (card + GL content) eases up from zero once per activation so it
# never snaps in when its heavy first frame lands outside the coordinated
# startup-reveal window. This is the visualizer's own single scene-fade
# authority; the generation startup-reveal gate is a separate root multiplicand.
_ACTIVATION_SCENE_FADE_DURATION_S = 1.3


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

    def __init__(
        self,
        runtime: Any,
        *,
        bar_count: int,
        initial_mode: str,
        engine_factory: Callable[[int], Any] | None = None,
        presentation_resolver: Callable[[], Any] | None = None,
        card_shadow_kwargs: Mapping[str, object] | None = None,
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
            engine_factory=engine_factory,
        )
        self._presentation_resolver = presentation_resolver
        self._card_shadow_kwargs = dict(card_shadow_kwargs or {})
        self._transition_clock = transition_clock or time.perf_counter
        self._transition_half_duration_s = max(
            0.0, float(transition_half_duration_s)
        )
        self._committed_layout_rect: tuple[float, float, float, float] | None = None
        self._committed_layout_extent: tuple[float, float] | None = None
        self._authored_outer_origin: tuple[float, float] = (0.0, 0.0)
        self._mode_transition_phase = "idle"
        self._mode_transition_started_at = 0.0
        self._mode_transition_fade = 1.0
        # ``None`` until the owner first starts: any presentation resolved before
        # then is fully opaque (never hidden). Once armed, the authored scene
        # fade eases 0 -> 1 over ``_ACTIVATION_SCENE_FADE_DURATION_S`` sampled
        # against the same clock the mode-transition fade already uses.
        self._activation_fade_started_at: float | None = None
        self._pending_mode_activation: dict[str, Any] | None = None
        self._sync: Any = None
        self._configured = False
        self._started = False
        self._bound = False
        self._engine_acquired = False
        self._retired = False
        self._render_identity: Any = None

    @property
    def controller(self) -> Any:
        return self._controller

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

        controller = self._controller
        state = controller.logical_tick_state
        install_default_logical_tick_state(state, bar_count=controller.bar_count)
        if logical_kwargs:
            apply_logical_vis_mode_kwargs(state, logical_kwargs)
        if presentation_kwargs:
            apply_presentation_vis_mode_kwargs(
                controller.presentation_state, presentation_kwargs
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
            logical_kwargs
            if logical_kwargs is not None
            else presentation_kwargs
        )
        if source_kwargs:
            from widgets.spotify_visualizer.source_config_applier import (
                apply_engine_vis_mode_kwargs,
            )

            apply_engine_vis_mode_kwargs(engine, source_kwargs)

        # Technical settings are already resolved by the canonical settings /
        # preset layer.  Prefer an explicit mapping from the display
        # orchestration caller; the controller-owned cache is the compatible
        # neutral fallback used by settings refresh/replay paths.
        resolved_technical = technical_config
        if resolved_technical is None:
            cache = controller.technical_config_cache
            if isinstance(cache, dict):
                resolved_technical = cache.get(controller.mode_id)
        if resolved_technical:
            from widgets.spotify_visualizer.quick_technical_config import (
                apply_controller_technical_config,
            )

            apply_controller_technical_config(
                controller,
                resolved_technical,
                reason=reason,
            )

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
                now_ts=time.time(),
                playing=bool(controller.playing),
                kind="recreation",
            )

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
        from widgets.spotify_visualizer.quick_presentation_sync import (
            QuickVisualizerPresentationSync,
        )

        self._sync = QuickVisualizerPresentationSync(
            self._controller,
            resolve_presentation=self._resolve_current_presentation,
            commit_presentation=self._apply_resolved_presentation,
            request_present=self._request_retained_present,
        )
        self._bound = True
        return self._render_identity

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
        self._presentation_runtime.scene_controller.request_visualizer_present()

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
        edge_ts = float(observed_ts if observed_ts is not None else time.time())
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
        if active and not previous:
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
            committed_ts = time.time()
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
        """Move retained presentation/config publication, not logical ownership."""

        if self._retired:
            return False
        if runtime is self._presentation_runtime:
            return False
        old_runtime = self._presentation_runtime
        old_runtime.scene_controller.set_visualizer_viewport_config_sink(None)
        self._presentation_runtime = runtime
        runtime.bind_visualizer_viewport_config(
            self._controller.set_custom_viewport_override
        )
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
            presentation = self._resolve_current_presentation()
            if self._started:
                self._apply_resolved_presentation(presentation)
            else:
                self._controller.commit_presentation_metrics(presentation)
        return True

    def resolved_outer_size(self) -> tuple[float, float]:
        """Return current outer size for ordinary layout planning."""

        presentation = self._resolve_current_presentation()
        return (float(presentation.outer_rect[2]), float(presentation.outer_rect[3]))

    def configure_committed_layout(
        self,
        *,
        local_rect: tuple[float, float, float, float] | None,
        viewport_extent: tuple[float, float] | None = None,
    ) -> None:
        """Hydrate one saved CUSTOM outer rect before logical runtime start.

        The rect and optional logical extent are ordinary committed truth.  The
        retained CUSTOM session may later install a temporary extent override,
        but no edit-session state is stored here.
        """

        if self._retired or self._started:
            raise RuntimeError("visualizer committed layout must bind before start")
        if local_rect is None:
            self._committed_layout_rect = None
            self._committed_layout_extent = None
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
        # Rehydrate committed logical-world truth before the authored logical
        # runtime can consume it. The same resolved record is later published
        # by the GUI synchronization edge.
        self._controller.commit_presentation_metrics(
            self._resolve_current_presentation()
        )
        # Keep the persisted extent as a one-shot recreation hydration fence
        # until the first retained presentation is actually committed.  A
        # same-process replacement can otherwise briefly republish canonical
        # metrics between construction and first presentation, which leaves
        # viewport-sensitive Bubble presentation scaling wrong until a cold
        # restart.  This is state-only and adds no cadence/polling owner.

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
        if self._controller.has_custom_viewport_override:
            viewport_extent = self._controller.presentation_viewport_extent
        elif self._committed_layout_extent is not None:
            viewport_extent = self._committed_layout_extent
        else:
            viewport_extent = self._controller.presentation_viewport_extent
        if committed_rect is None:
            outer_origin = self._authored_outer_origin
            uniform_scale = 1.0
        else:
            outer_origin = (committed_rect[0], committed_rect[1])
            uniform_scale = committed_rect[2] / max(1e-6, viewport_extent[0])
        return resolve_visualizer_presentation(
            policy=self._controller.presentation_policy,
            display_size=(float(width), float(height)),
            outer_origin=outer_origin,
            dpr=dpr,
            uniform_visual_scale=uniform_scale,
            viewport_extent=viewport_extent,
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
        self._controller.commit_presentation_metrics(presentation)
        # The retained scene has now consumed one coherent presentation.  Drop
        # the one-shot persisted-layout hydration fence so later live CUSTOM
        # edits / transfers continue to follow the controller normally.
        self._committed_layout_extent = None

    def sync_present(self) -> bool:
        if self._retired or self._sync is None:
            return False
        phase = self._mode_transition_phase
        if phase == "idle":
            return self._sync.sync_latest()
        if phase == "failed":
            raise RuntimeError("visualizer mode transition owner is failed")

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
            if self._controller.logical_tick_state._waiting_for_fresh_engine_frame:
                return self._sync.sync_latest()
            published = self._sync.sync_latest()
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
                    callback(self._controller.mode_id)
            return published

        raise RuntimeError(f"unknown visualizer mode transition phase: {phase}")

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
        engine = controller.ensure_engine()
        if not controller.stop_logical_runtime():
            self._mode_transition_phase = "failed"
            raise RuntimeError("visualizer logical runtime did not join for activation")

        begin = getattr(engine, "begin_activation_transaction", None)
        end = getattr(engine, "end_activation_transaction", None)
        if not callable(begin) or not callable(end):
            self._mode_transition_phase = "failed"
            raise RuntimeError("visualizer BeatEngine has no activation transaction")

        target = str(pending["mode"])
        kind = str(pending.get("kind") or "mode")
        try:
            begin()
        except Exception:
            self._mode_transition_phase = "failed"
            raise
        try:
            if kind == "mode":
                controller.set_mode(target)
            elif target != controller.mode_id:
                raise RuntimeError("preset activation attempted to change visualizer mode")
            controller.settings_model = pending["settings_model"]
            controller.record_resolved_activation(pending["resolved_activation"])
            controller.technical_config_cache = dict(pending["technical_cache"])
            self._apply_configuration(
                logical_kwargs=pending["logical_kwargs"],
                presentation_kwargs=pending["presentation_kwargs"],
                technical_config=controller.technical_config_cache.get(target),
                thread_manager=controller.thread_manager,
                process_supervisor=controller.process_supervisor,
                playing=controller.playing,
                reason=f"quick_owner_{kind}_change",
            )
            cancel = getattr(engine, "cancel_pending_compute_tasks", None)
            reset_smoothing = getattr(engine, "reset_smoothing_state", None)
            reset_floor = getattr(engine, "reset_floor_state", None)
            if not all(callable(operation) for operation in (cancel, reset_smoothing, reset_floor)):
                raise RuntimeError("visualizer BeatEngine has no canonical reset contract")
            cancel()
            reset_smoothing()
            reset_floor()
        except Exception:
            self._mode_transition_phase = "failed"
            raise
        finally:
            end(reason=f"quick_{kind}_change:{target}")

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
            self._mode_transition_phase = "failed"
            raise
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
        pacer = self._runtime.frame_pacer
        try:
            if callable(acquire):
                acquire()
                self._engine_acquired = True
            self.set_playing(controller.playing)
            self._start_logical_runtime(interval_s=interval_s)
            # Arm the authored scene fade before the pacer can publish the first
            # frame so the visualizer eases up from zero instead of snapping in.
            self._activation_fade_started_at = float(self._transition_clock())
            pacer.set_visualizer_sync(self.sync_present)
            pacer.set_visualizer_active(True)
            self._started = True
        except Exception:
            try:
                pacer.set_visualizer_active(False)
                pacer.set_visualizer_sync(None)
            finally:
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
        if self._started:
            pacer = self._runtime.frame_pacer
            pacer.set_visualizer_active(False)
            pacer.set_visualizer_sync(None)
            self._runtime.scene_controller.set_visualizer_double_click_admission(None)
            self._runtime.scene_controller.set_visualizer_middle_click_admission(None)
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
        self._sync = None
        self._pending_mode_activation = None
        self._presentation_resolver = None
        self._card_shadow_kwargs.clear()
        return True


__all__ = ["QuickDisplayVisualizerOwner"]
