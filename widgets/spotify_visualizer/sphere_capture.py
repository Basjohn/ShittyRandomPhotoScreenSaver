"""Lazy logical-frame capture for Sphere."""
from __future__ import annotations

from typing import Any

from widgets.spotify_visualizer.config_applier import SPHERE_DEFAULT_PARAMETERS
from widgets.spotify_visualizer.render_state import FrozenFields, SphereFrame


def capture_sphere(widget: Any, engine: Any, context: Any):
    from widgets.spotify_visualizer.logical_frame_capture import _base_extras, _energy_state, _resolve_current_mode_runtime
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
        # Identity 0 is the first valid engine activation, not an unassigned
        # sentinel.  Keep this aligned with the generic render admission fence
        # so Sphere does not silently erase its first live generation's energy.
        and context.source_generation >= 0
        and context.source_activation_id >= 0
        and context.source_generation == context.engine_generation
        and context.source_activation_id == context.activation_id
    )
    energy = (
        _energy_state(extra.get("energy_bands"))
        if source_is_current
        else _energy_state(None)
    )
    parameters = getattr(widget, "_sphere_parameters", SPHERE_DEFAULT_PARAMETERS)
    if not isinstance(parameters, FrozenFields):
        raise TypeError("Sphere capture requires configure-owned FrozenFields")
    resolved = runtime.resolve(now_ts=context.now_ts, runtime_generation=context.runtime_generation,
        engine_generation=context.engine_generation, activation_id=context.activation_id,
        energy=energy, parameters=parameters)
    if resolved is None:
        if controller.peek_logical_mode_state("sphere") is not runtime:
            return None
        raise RuntimeError("Sphere logical state retired during capture")
    if controller.peek_logical_mode_state("sphere") is not runtime:
        return None
    extra["_quick_mode_changed"] = resolved.changed
    extra["_quick_resolved_energy"] = resolved.energy
    return SphereFrame(authored_time=resolved.authored_time, parameters=resolved.parameters), extra


__all__ = ["capture_sphere"]
