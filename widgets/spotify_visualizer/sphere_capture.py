"""Lazy logical-frame capture for Voxel Sphere."""
from __future__ import annotations

from typing import Any

from widgets.spotify_visualizer.render_state import FrozenFields, SphereFrame, freeze_render_fields


def _render_parameters(widget: Any, parameters: FrozenFields, now_ts: float) -> FrozenFields:
    """The runtime's resolved parameters plus the presentation-owned values only the renderer
    reads (the 3D Detail tier, Mirror Cubes and the reflected wallpaper): the logical runtime
    never sees them. Rebuilt only when one of them changes."""
    from widgets.spotify_visualizer.config_applier import _presentation_source

    pres = _presentation_source(widget)
    backdrop = getattr(pres, "_backdrop", None)
    blend_s = getattr(pres, "_backdrop_blend_s", None)
    from widgets.spotify_visualizer.view_orbit import view_orbit_values
    pose = view_orbit_values(pres, "sphere", now_ts)
    key = (str(pres._scene3d_detail), float(pres._sphere_mirror), None if backdrop is None else backdrop.identity,
           blend_s, pose["sphere_turn"], pose["sphere_tilt"])
    cached = getattr(widget, "_sphere_render_parameters", None)
    if cached is not None and cached[0] is parameters and cached[1] == key:
        return cached[2]
    merged = freeze_render_fields({**dict(parameters), "scene3d_detail": key[0], "sphere_mirror": key[1],
                                   "backdrop": backdrop, "backdrop_blend_s": blend_s,
                                   "sphere_turn": pose["sphere_turn"], "sphere_tilt": pose["sphere_tilt"]})
    widget._sphere_render_parameters = (parameters, key, merged)
    return merged


def capture_sphere(widget: Any, engine: Any, context: Any):
    from widgets.spotify_visualizer.logical_frame_capture import (
        _base_extras,
        _energy_state,
        _resolve_current_mode_runtime,
        _transient_state,
    )
    from widgets.spotify_visualizer.sphere_frame_runtime import SphereFrameRuntime

    extra = _base_extras(widget, "sphere", engine)
    controller = getattr(widget, "runtime_controller", None)
    if controller is None:
        raise RuntimeError("Sphere logical capture requires its runtime controller owner")
    runtime = _resolve_current_mode_runtime(controller, "sphere", SphereFrameRuntime)
    if runtime is None:
        return None
    if not isinstance(runtime, SphereFrameRuntime):
        raise TypeError("Sphere logical mode state has the wrong type")

    source_is_current = (
        context.playing
        and context.source_generation >= 0
        and context.source_activation_id >= 0
        and context.source_generation == context.engine_generation
        and context.source_activation_id == context.activation_id
    )
    energy = _energy_state(extra.get("energy_bands")) if source_is_current else _energy_state(None)
    transient = (
        _transient_state(extra.get("transient_energy"))
        if source_is_current
        else _transient_state(None)
    )

    # Keep three different authorities deliberately separate:
    # - Bubble's support-aware energy remains useful only for Sphere spatial
    #   routing / whole-shell articulation;
    # - unsmoothed live pre-AGC energy owns sustained body weight;
    # - an immutable pre-shape/pre-AGC analysis spectrum owns generic onset
    #   detection for fragmentation + tracer travel.
    reactive_energy = _energy_state(None)
    presence_energy = _energy_state(None)
    analysis_spectrum: tuple[float, ...] = ()
    # How much an event counts musically (the shared onset rule): the live pre-AGC lane above
    # is clamped and sits at its cap through ordinary music, so it cannot tell near-silence or a
    # quiet passage from a loud one; the transient bus's unclamped level and presence can.
    musical_level = (0.0, 0.0)
    musical_intensity = 0.0
    if source_is_current and engine is not None:
        level_getter = getattr(engine, "get_musical_level", None)
        if callable(level_getter):
            musical_level = tuple(float(value) for value in level_getter())
        intensity_getter = getattr(engine, "get_musical_intensity", None)
        if callable(intensity_getter):
            musical_intensity = float(intensity_getter())
        getter = getattr(engine, "get_bubble_energy_bands", None)
        if callable(getter):
            try:
                reactive_energy = _energy_state(getter())
            except Exception:
                reactive_energy = _energy_state(None)

        presence_getter = getattr(engine, "get_live_pre_agc_energy_bands", None)
        if callable(presence_getter):
            try:
                presence_energy = _energy_state(presence_getter())
            except Exception:
                presence_energy = _energy_state(None)

        # Fragmentation/tracer onset detection uses a demand-published immutable
        # copy of the existing FFT band's raw analysis spectrum. This snapshot is
        # temporally unsmoothed and precedes Spectrum shape, bar smoothing and AGC.
        spectrum_getter = getattr(engine, "get_pre_agc_analysis_spectrum", None)
        if callable(spectrum_getter):
            try:
                analysis_spectrum = tuple(float(value) for value in spectrum_getter())
            except Exception:
                analysis_spectrum = ()
    scheduler = None
    if source_is_current and engine is not None:
        getter = getattr(engine, "get_event_scheduler", None)
        if callable(getter):
            scheduler = getter()

    parameters = widget._sphere_parameters
    if not isinstance(parameters, FrozenFields):
        raise TypeError("Sphere capture requires configure-owned FrozenFields")

    resolved = runtime.resolve(
        now_ts=context.now_ts,
        runtime_generation=context.runtime_generation,
        engine_generation=context.engine_generation,
        activation_id=context.activation_id,
        source_active=source_is_current,
        energy=energy,
        reactive_energy=reactive_energy,
        presence_energy=presence_energy,
        musical_level=musical_level,
        musical_intensity=musical_intensity,
        transient=transient,
        analysis_spectrum=analysis_spectrum,
        event_scheduler=scheduler,
        parameters=parameters,
    )
    if resolved is None:
        if controller.peek_logical_mode_state("sphere") is not runtime:
            return None
        raise RuntimeError("Sphere logical state retired during capture")
    if controller.peek_logical_mode_state("sphere") is not runtime:
        return None

    extra["_quick_mode_changed"] = resolved.changed
    extra["_quick_resolved_energy"] = resolved.energy
    extra["transient_energy"] = resolved.transient
    return SphereFrame(
        authored_time=resolved.authored_time,
        size_pulse=resolved.size_pulse,
        rotation_drive=resolved.rotation_drive,
        rotation_phase=resolved.rotation_phase,
        tracer_drive=resolved.tracer_drive,
        tracer_phase=resolved.tracer_phase,
        section_drives=resolved.section_drives,
        incoming_drive=resolved.incoming_drive,
        incoming_density=resolved.incoming_density,
        incoming_section=resolved.incoming_section,
        incoming_previous_section=resolved.incoming_previous_section,
        incoming_blend=resolved.incoming_blend,
        particle_cohorts=resolved.particle_cohorts,
        parameters=_render_parameters(widget, resolved.parameters, context.now_ts),
    ), extra


__all__ = ["capture_sphere"]
