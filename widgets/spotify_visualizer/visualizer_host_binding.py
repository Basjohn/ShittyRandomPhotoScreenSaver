"""The Visualizer host binding: one owner bound to one host unit at a time.

This module owns everything that binds the single
:class:`~widgets.spotify_visualizer.quick_display_visualizer_owner.QuickDisplayVisualizerOwner`
to a host unit: construction (with the one-owner rejection), bind/start,
authored (non-CUSTOM) layout and its Media docking, input admissions, the
transactional cross-host transfer, route release and retirement.

The caller (``DisplayManager`` today; a future SMP dock or Pop Out host) keeps
only the "which unit" decision and the admitted ``(owner, unit)`` routing
record, reached through :class:`VisualizerHostServices`. The binding holds no
state of its own between calls, owns no timer, cadence, settings or clock, and
creates no second owner, controller, BeatEngine or logical runtime.

A host unit is any object with the display-unit surface the binding uses:
``runtime`` (``scene_controller``, ``window``), ``presenter`` (authored
geometry, layout observer, external stack obstacles, ``authored_layout_enabled``),
``display_bounds()``, ``visualizer_owner``, ``attach_visualizer_owner``,
``detach_visualizer_owner``, ``is_retired`` and ``screen_index``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from core.logging.logger import get_logger
from core.settings.capability_activation import is_widget_family_effective

if TYPE_CHECKING:
    from rendering.visualizer_placement import VisualizerAuthoredPlacement

logger = get_logger(__name__)


@dataclass(frozen=True)
class VisualizerHostServices:
    """What the binding needs from the "which unit" side, as explicit callables.

    Every member is read at call time, so a caller's state is never copied.
    The callables must reach their caller weakly: the binding hands them to a
    presenter-held layout observer, and ``caller_retired`` must answer True
    (and nothing else be called) once the caller is gone.
    """

    # The admitted (owner, unit) routing record the caller keeps.
    admitted_owner: Callable[[], Any]
    admitted_unit: Callable[[], Any]
    record_admission: Callable[[Any, Any], None]
    record_unit: Callable[[Any], None]
    live_units: Callable[[], Sequence[Any]]
    caller_retired: Callable[[], bool]
    # Generation inputs.
    widgets_config: Callable[[], Mapping[str, Any]]
    shadow_values: Callable[[], Mapping[str, Any]]
    thread_manager: Callable[[], Any]
    process_supervisor: Callable[[], Any]
    display_power_on: Callable[[], bool]
    # Owner construction seams.
    set_construct_outcome: Callable[..., None]
    committed_layout_profile_resolver: Callable[[str], Any]
    edit_layout_profile_activator: Callable[[str], bool]
    transition_failure: Callable[[str], None]
    presentation_kwargs: Callable[[Any, str], dict[str, Any]]
    # Playback, view and menus (caller-owned routes the binding sequences).
    media_model_for: Callable[[Any], Any]
    bind_media: Callable[[Any], None]
    disconnect_media: Callable[[], None]
    publish_view_orbit_admission: Callable[[], None]
    release_view_state: Callable[[], None]
    # Input consequences the caller routes (mode/preset requests, Media volume).
    cycle_mode: Callable[[], None]
    cycle_preset: Callable[[], None]
    volume_step: Callable[[int], bool]
    refresh_context_menus: Callable[[], None]
    refresh_transfer_glyphs: Callable[[], None]


def resolve_visualizer_card_shadow_kwargs(
    widgets: Mapping[str, Any],
    shadow_values: Mapping[str, Any],
) -> dict[str, Any]:
    """The Visualizer card's chrome: theme colours, the shared border width, shadow."""

    from core.settings.default_contract import resolve_card_border_width_px
    from core.settings.shadow_direction import (
        resolve_directional_extensions,
        resolve_signed_offset,
    )
    from rendering.quick.shadow_snapshot import QuickShadowSnapshot
    from rendering.quick.widgets.host import ORDINARY_CARD_SHADOW_BASE
    from ui.widget_theme_active import get_active_widget_theme
    from widgets.spotify_visualizer.presentation_geometry import (
        VISUALIZER_CARD_CONTENT_INSET,
        VISUALIZER_CARD_CORNER_RADIUS,
        VISUALIZER_CARD_SHADOW_SPREAD,
    )

    shadow = QuickShadowSnapshot.from_mapping(shadow_values)
    channels = list(shadow.color)
    channels[3] = max(
        0,
        min(255, int(round(channels[3] * shadow.frame_opacity))),
    )
    widget_theme = get_active_widget_theme()
    return {
        "background_color": widget_theme.color("card.background").as_tuple(),
        "border_color": widget_theme.color("card.border").as_tuple(),
        "border_width": resolve_card_border_width_px(widgets),
        "corner_radius": VISUALIZER_CARD_CORNER_RADIUS,
        "content_inset": VISUALIZER_CARD_CONTENT_INSET,
        "shadow_enabled": shadow.enabled,
        "shadow_color": tuple(channels),
        "shadow_blur": min(80.0, shadow.blur_radius),
        "shadow_offset": resolve_signed_offset(
            shadow.direction, *ORDINARY_CARD_SHADOW_BASE
        ),
        "shadow_spread": VISUALIZER_CARD_SHADOW_SPREAD,
        "shadow_extensions": resolve_directional_extensions(
            shadow.direction, shadow.frame_extra_offset
        ),
    }


def install_visualizer_input_admissions(
    unit: Any,
    owner: Any,
    services: VisualizerHostServices,
) -> None:
    """Admit double-click (next mode), middle-click (next preset) and wheel (volume).

    The admissions travel with the retained scene on a cross-display transfer
    (``VisualizerSceneTransfer``). In-card controls consume their own presses
    before any of these see them (``QuickDisplayWindow``).
    """

    from rendering.quick.visualizer.double_click_admission import (
        QuickVisualizerDoubleClickAdmission,
    )
    from rendering.quick.visualizer.middle_click_admission import (
        QuickVisualizerMiddleClickAdmission,
    )

    def _visualizer_region_contains(
        scene_position: Any,
        admitted: Any = owner,
    ) -> bool:
        return bool(
            admitted.presentation_runtime.scene_controller
            .visualizer_contains_scene_position(scene_position)
        )

    scene = unit.runtime.scene_controller
    scene.set_visualizer_double_click_admission(
        QuickVisualizerDoubleClickAdmission(
            region_contains=_visualizer_region_contains,
            is_active=lambda admitted=owner: (
                admitted.is_started and not admitted.is_retired
            ),
            cycle_mode=services.cycle_mode,
        )
    )
    scene.set_visualizer_middle_click_admission(
        QuickVisualizerMiddleClickAdmission(
            region_contains=_visualizer_region_contains,
            is_active=lambda admitted=owner: (
                admitted.is_started and not admitted.is_retired
            ),
            cycle_preset=services.cycle_preset,
        )
    )
    scene.set_visualizer_volume_wheel_handler(services.volume_step)


def clear_visualizer_input_admissions(unit: Any) -> None:
    """Drop the unit's Visualizer double-click, middle-click and wheel admissions."""

    scene = unit.runtime.scene_controller
    scene.set_visualizer_double_click_admission(None)
    scene.set_visualizer_middle_click_admission(None)
    scene.set_visualizer_volume_wheel_handler(None)


class VisualizerHostBinding:
    """Construct, bind, lay out, transfer, release and retire the one owner."""

    def __init__(self, services: VisualizerHostServices) -> None:
        self._services = services

    # ------------------------------------------------------------------ layout

    def resolve_placement(
        self,
        chosen: Any,
        owner: Any,
        *,
        media_geometry: Any | None = None,
        authored_layout_enabled: bool | None = None,
    ) -> "VisualizerAuthoredPlacement | None":
        """Resolve the authored Visualizer placement on ``chosen`` once.

        One function for the saver and Settings Arrange
        (:func:`rendering.visualizer_placement.resolve_visualizer_authored_placement`).
        ``authored_layout_enabled`` defaults to the host presenter's switch;
        global CUSTOM always resolves undocked, on Media's plain authored slot.
        A committed Visualizer CUSTOM rect remains authoritative inside the owner
        and rejects any authored origin. Returns ``None`` only when the owner
        cannot report its size. No timer/poller/cadence owner is involved.
        """

        from rendering.visualizer_placement import (
            DOCKED_TO_MEDIA,
            resolve_visualizer_authored_placement,
            resolve_visualizer_docked_to,
        )

        widgets = self._services.widgets_config()
        if authored_layout_enabled is None:
            authored_layout_enabled = bool(chosen.presenter.authored_layout_enabled)
        bounds = chosen.display_bounds()
        try:
            visualizer_size = owner.resolved_outer_size()
        except Exception:
            logger.warning(
                "[SPOTIFY_VIS] Failed to resolve authored visualizer size",
                exc_info=True,
            )
            return None
        media_rect = None
        docked_to = resolve_visualizer_docked_to(
            widgets, authored_layout_enabled=authored_layout_enabled
        )
        if docked_to == DOCKED_TO_MEDIA:
            # Docking follows Media's unstacked authored card. Media's route
            # still anchors the Visualizer when the Media card itself is
            # disabled (no retained rectangle): it then sits on Media's slot.
            geometry = media_geometry or chosen.presenter.authored_geometry_for("media")
            if geometry is not None:
                media_rect = (
                    float(geometry.x - bounds.x),
                    float(geometry.y - bounds.y),
                    float(geometry.width),
                    float(geometry.height),
                )
        placement = resolve_visualizer_authored_placement(
            widgets,
            display_size=(float(bounds.width), float(bounds.height)),
            visualizer_size=visualizer_size,
            media_rect=media_rect,
            authored_layout_enabled=authored_layout_enabled,
        )
        if placement.overfull:
            logger.warning(
                "[SPOTIFY_VIS] Media+Visualizer ordinary pair exceeds available adjacent space"
            )
        return placement

    def project_base_authored_origin(self) -> bool:
        """Project the plain (undocked) authored Visualizer origin once, if admitted.

        Used when live Edit or a slot load holds authored layout off: the
        Visualizer stays on Media's plain slot, never at the owner's (0, 0).
        """

        owner = self._services.admitted_owner()
        chosen = self._services.admitted_unit()
        if owner is None or chosen is None or chosen.is_retired:
            return False
        placement = self.resolve_placement(chosen, owner, authored_layout_enabled=False)
        if placement is None:
            return False
        return bool(owner.set_authored_outer_origin(placement.x, placement.y))

    def install_authored_layout(
        self,
        chosen: Any,
        owner: Any,
        *,
        install_observer: bool,
        media_geometry: Any | None = None,
        defer_presenter_reflow: bool = False,
    ) -> bool:
        """Project the authored placement, its stacking reservation and its docking.

        Returns False (and touches nothing) when authored placement does not
        apply: CUSTOM is a hard boundary. A Visualizer docked to a presented
        Media card installs one Media-geometry observer, so it follows Media;
        an undocked one installs none, so moving Media leaves it in place.
        """

        placement = self.resolve_placement(
            chosen, owner, media_geometry=media_geometry
        )
        if placement is None or not placement.authored:
            return False
        owner.set_authored_outer_origin(placement.x, placement.y)
        obstacles, fixed_widget_ids = placement.stack_obstacles()
        if fixed_widget_ids:
            chosen.presenter.set_external_stack_obstacles(
                obstacles,
                fixed_widget_ids=fixed_widget_ids,
                reflow=not defer_presenter_reflow,
            )
        else:
            # Media may be disabled (or the Visualizer undocked) while the
            # Visualizer remains ordinary. It still occupies real screen space,
            # so authored stacking routes other ordinary cards around it.
            chosen.presenter.set_external_stack_obstacles(
                obstacles,
                reflow=not defer_presenter_reflow,
            )
        if not install_observer:
            return True
        if placement.media_rect is None:
            chosen.presenter.set_layout_observer(None)
            return True

        # The services reach the caller weakly (see VisualizerHostServices),
        # so this presenter-held observer never keeps the caller alive.
        services = self._services

        def _on_authored_geometry(widget_id: str, geometry: Any) -> None:
            if widget_id != "media":
                return
            if (
                services.caller_retired()
                or services.admitted_owner() is not owner
                or services.admitted_unit() is not chosen
            ):
                return
            VisualizerHostBinding(services).install_authored_layout(
                chosen,
                owner,
                install_observer=False,
                media_geometry=geometry,
                defer_presenter_reflow=True,
            )

        chosen.presenter.set_layout_observer(_on_authored_geometry)
        return True

    # -------------------------------------------------------------- construct

    def construct(self, chosen: Any) -> bool:
        """Construct, bind and start the single visualizer owner on ``chosen``.

        Final-create boundary for admission. Re-resolves the current model/config
        and fails closed when the visualizers capability is no longer effective
        or the instance is disabled. A second owner is rejected here. Returns
        True only when the single owner is admitted.
        """

        services = self._services
        if services.admitted_owner() is not None:
            services.set_construct_outcome(
                "rejected",
                "owner_already_admitted",
            )
            return False
        widgets = services.widgets_config()
        section = widgets.get("spotify_visualizer", {})
        if not isinstance(section, dict):
            services.set_construct_outcome(
                "rejected",
                "invalid_visualizer_section",
            )
            return False
        if not is_widget_family_effective(widgets, "visualizers"):
            services.set_construct_outcome(
                "rejected",
                "visualizer_capability_not_effective",
            )
            return False

        from core.settings.models import SpotifyVisualizerSettings
        from core.settings.visualizer_mode_registry import (
            resolve_effective_visualizer_section,
        )
        from core.settings.visualizer_presets import (
            resolve_visualizer_activation_payload,
        )

        # Resolve a disabled/stale persisted mode to an enabled one BEFORE the
        # activation/model payload is resolved (pre-V5/V6 startup-substitution
        # ordering gate): re-enter the canonical resolver for the substitute so
        # mode-A activation/preset state is never field-patched onto mode B. With
        # every mode enabled (today's default) this is a no-op.
        section, mode_substituted, requested_mode, effective_mode = (
            resolve_effective_visualizer_section(section)
        )
        if mode_substituted:
            logger.info(
                "[SPOTIFY_VIS] Persisted visualizer mode %r is not enabled; "
                "starting enabled mode %r instead",
                requested_mode,
                effective_mode,
            )

        activation = resolve_visualizer_activation_payload(section)
        model = SpotifyVisualizerSettings.from_mapping(
            activation.resolved_config,
            apply_preset_overlay=False,
            resolve_preset_indices=False,
        )
        if not bool(model.enabled):
            services.set_construct_outcome(
                "rejected",
                "visualizer_instance_disabled",
            )
            return False
        if not bool(model.visualizers_enabled):
            services.set_construct_outcome(
                "rejected",
                "visualizers_disabled",
            )
            return False

        from widgets.spotify_visualizer.quick_display_visualizer_owner import (
            QuickDisplayVisualizerOwner,
        )
        from widgets.spotify_visualizer.technical_config import (
            build_technical_cache,
        )

        mode = str(model.mode)
        technical_cache = build_technical_cache(None, model)
        card_shadow_kwargs = resolve_visualizer_card_shadow_kwargs(
            widgets, services.shadow_values()
        )

        owner = QuickDisplayVisualizerOwner(
            chosen.runtime,
            bar_count=model.resolve_bar_count(mode),
            initial_mode=mode,
            committed_layout_profile_resolver=services.committed_layout_profile_resolver,
            edit_layout_profile_activator=services.edit_layout_profile_activator,
            transition_failure_callback=services.transition_failure,
            card_shadow_kwargs=card_shadow_kwargs,
        )
        try:
            owner.controller.settings_model = model
            owner.controller.record_resolved_activation(activation)
            owner.controller.technical_config_cache = technical_cache
            from widgets.spotify_visualizer.technical_config import (
                resolve_technical_config,
            )
            owner.configure(
                logical_kwargs=asdict(model),
                presentation_kwargs=services.presentation_kwargs(model, mode),
                technical_config=resolve_technical_config(technical_cache, mode),
                thread_manager=services.thread_manager(),
                process_supervisor=services.process_supervisor(),
                playing=False,
            )
            self._configure_committed_layout(chosen, owner, widgets, mode)
            # Authored placement is resolved before start so the first retained
            # Visualizer presentation never appears at the old (0, 0) default.
            # Global CUSTOM disables docking, not authored anchoring: an
            # uncommitted Visualizer then sits on Media's plain authored slot (a
            # committed CUSTOM rect rejects the origin inside the owner).
            # Stacking reservation/observer are installed only after successful
            # single-owner admission below.
            placement = self.resolve_placement(chosen, owner)
            if placement is not None:
                owner.set_authored_outer_origin(placement.x, placement.y)

            engine = owner.controller.engine
            generation = int(engine.get_generation_id())
            activation_id = int(engine.get_activation_id())
            owner.bind(
                engine_generation=generation,
                activation_id=activation_id,
            )
            media_model = services.media_model_for(chosen)
            if media_model is not None:
                owner.set_playing(
                    str(getattr(media_model, "playbackState", "unknown")).lower()
                    == "playing"
                )
            if not services.display_power_on():
                # Built while the displays are off: start parked, holding no capture.
                owner.set_display_power(False)
            owner.start()
            services.record_admission(owner, chosen)
            services.publish_view_orbit_admission()
            if media_model is not None:
                services.bind_media(media_model)
            chosen.attach_visualizer_owner(owner)
            self.install_authored_layout(chosen, owner, install_observer=True)
            install_visualizer_input_admissions(chosen, owner, services)
            services.refresh_context_menus()
        except Exception:
            services.set_construct_outcome(
                "exception",
                "owner_configuration_failed",
            )
            if services.admitted_owner() is owner:
                self.release_routes()
            if not owner.is_retired:
                owner.retire()
            raise

        logger.info(
            "[SPOTIFY_VIS] Admitted one Quick owner screen=%s mode=%s generation=%s activation=%s",
            chosen.screen_index,
            mode,
            generation,
            activation_id,
        )
        services.set_construct_outcome("admitted")
        return True

    @staticmethod
    def _configure_committed_layout(
        chosen: Any,
        owner: Any,
        widgets: Mapping[str, Any],
        mode: str,
    ) -> None:
        """Hydrate the committed CUSTOM rect for ``mode`` before start, if any."""

        from rendering.quick.custom_layout_hydration import (
            resolve_committed_visualizer_rect,
            resolve_visualizer_custom_entry,
        )

        custom_entry = resolve_visualizer_custom_entry(
            widgets, chosen.runtime.window.screen(), mode
        )
        if custom_entry is None:
            return
        from rendering.custom_layout_session import normalize_viewport_extent

        local_rect = resolve_committed_visualizer_rect(
            custom_entry,
            chosen.runtime.window.screen().geometry().size(),
        )
        from widgets.spotify_visualizer.presentation_orientation import (
            CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY,
            CONTENT_ROTATION_QUARTERS_PAYLOAD_KEY,
        )
        from core.settings.visualizer_mode_registry import (
            get_visualizer_layout_profile,
        )
        legacy_source_variant = (
            custom_entry.geometry_variant
            if custom_entry.geometry_variant in {"default", "freeform_3d"}
            else None
        )

        owner.configure_committed_layout(
            local_rect=(
                float(local_rect.x()),
                float(local_rect.y()),
                float(local_rect.width()),
                float(local_rect.height()),
            ),
            viewport_extent=normalize_viewport_extent(
                custom_entry.size_payload.get("viewport_extent")
            ),
            content_rotation_by_mode=custom_entry.size_payload.get(
                CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY,
                custom_entry.size_payload.get(
                    CONTENT_ROTATION_QUARTERS_PAYLOAD_KEY, 0
                ),
            ),
            legacy_layout_profile=(
                get_visualizer_layout_profile(mode)
                if legacy_source_variant is not None else None
            ),
            legacy_source_variant=legacy_source_variant,
        )

    # --------------------------------------------------------------- transfer

    def transfer(self, target: Any) -> bool:
        """Move the single visualizer's host-retirement authority transactionally.

        The enclosing CUSTOM transaction moves the retained scene item (with its
        input admissions) first and calls this seam before it can commit the
        session placement. The binding owns the matching Python lifecycle edge:
        owner runtime/pacer routes, the admitted unit and the unit that will
        eventually retire the owner all move together. No controller,
        BeatEngine, logical runtime, activation, or cadence is recreated.
        """

        services = self._services
        if services.caller_retired():
            raise RuntimeError("cannot transfer visualizer on a retired display manager")
        owner = services.admitted_owner()
        source = services.admitted_unit()
        if owner is None or source is None:
            raise RuntimeError("visualizer display transfer has no admitted owner")
        if target is source:
            return False
        if target not in services.live_units() or target.is_retired:
            raise RuntimeError("visualizer display transfer target is not live")
        if bool(getattr(owner, "is_retired", False)):
            raise RuntimeError("visualizer display transfer owner is retired")
        if owner.presentation_runtime is not source.runtime:
            raise RuntimeError(
                "visualizer presentation runtime disagrees with manager source unit"
            )
        if source.visualizer_owner is not owner:
            raise RuntimeError("visualizer source unit lost retirement ownership")
        target_owner = target.visualizer_owner
        if target_owner is not None and target_owner is not owner:
            raise RuntimeError("visualizer target unit owns another visualizer")
        if target_owner is owner:
            raise RuntimeError("visualizer target already owns retirement authority")

        owner.set_presentation_runtime(target.runtime)
        source_detached = False
        target_attached = False
        try:
            source_detached = source.detach_visualizer_owner(owner)
            if not source_detached:
                raise RuntimeError("visualizer source unit could not detach owner")
            target.attach_visualizer_owner(owner)
            target_attached = True
            services.record_unit(target)
            services.refresh_transfer_glyphs()
        except Exception:
            # The scene transfer has already happened, but the host-side
            # lifecycle move is still one bounded transaction.  Restore the old
            # retirement/pacer edge rather than leave teardown split between two
            # host units.
            if target_attached and target.visualizer_owner is owner:
                try:
                    target.detach_visualizer_owner(owner)
                except Exception:
                    logger.exception(
                        "[SPOTIFY_VIS] Failed rolling back target retirement owner"
                    )
            if source_detached and source.visualizer_owner is None:
                try:
                    source.attach_visualizer_owner(owner)
                except Exception:
                    logger.exception(
                        "[SPOTIFY_VIS] Failed restoring source retirement owner"
                    )
            services.record_unit(source)
            try:
                owner.set_presentation_runtime(source.runtime)
            except Exception:
                logger.exception(
                    "[SPOTIFY_VIS] Failed restoring source display edge after transfer"
                )
            raise

        logger.info(
            "[SPOTIFY_VIS] Moved visualizer display ownership screen=%s -> %s",
            source.screen_index,
            target.screen_index,
        )
        return True

    # ----------------------------------------------------- release / retire

    def release_routes(self, unit: Any | None = None) -> bool:
        """Drop the routing references; the admitted unit owns retirement.

        Clears the Media route, the presenter's docking observer and stacking
        reservation and the unit's input admissions, then the routing record.
        """

        services = self._services
        if unit is not None and unit is not services.admitted_unit():
            return False
        services.disconnect_media()
        chosen = services.admitted_unit()
        if chosen is not None:
            chosen.presenter.set_layout_observer(None)
            chosen.presenter.set_external_stack_obstacles(None)
            clear_visualizer_input_admissions(chosen)
        # An orbit still held when the Visualizer goes is saved now; its release never comes.
        services.release_view_state()
        services.record_admission(None, None)
        services.publish_view_orbit_admission()
        return True

    def retire(self) -> bool | None:
        """Retire the admitted owner and release its host (CUSTOM Edit disable).

        Returns ``None`` when nothing is admitted, ``False`` when retirement
        failed or is unconfirmed (ownership is retained for the runtime
        destruction barrier to retry) and ``True`` once the owner is retired,
        detached and its routes released.
        """

        services = self._services
        host = services.admitted_unit()
        owner = services.admitted_owner()
        if owner is None or host is None:
            return None
        services.disconnect_media()
        host.presenter.set_layout_observer(None)
        host.presenter.set_external_stack_obstacles(None)
        scene = host.runtime.scene_controller
        clear_visualizer_input_admissions(host)
        try:
            if not owner.is_retired:
                owner.retire()
        except Exception:
            logger.warning("[SPOTIFY_VIS] Visualizer retirement failed", exc_info=True)
            return False
        if not owner.is_retired:
            logger.warning("[SPOTIFY_VIS] Visualizer retirement unconfirmed; retaining ownership")
            return False
        host.detach_visualizer_owner(owner)
        self.release_routes(host)
        scene.discard_unowned_visualizer_admission()
        services.refresh_context_menus()
        return True


__all__ = [
    "VisualizerHostBinding",
    "VisualizerHostServices",
    "clear_visualizer_input_admissions",
    "install_visualizer_input_admissions",
    "resolve_visualizer_card_shadow_kwargs",
]
