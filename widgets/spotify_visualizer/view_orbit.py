"""Live W/A/S/D view orbiting for 3D freeform Visualizer modes.

A mode opts in through its descriptor's ``view_orbit_settings`` (its turn and tilt
presentation settings; turn spans -1..1 as a full circle and wraps, tilt clamps to its
range) and ``view_orbit_steps`` (one key event's step of each). A key event steps the live
presentation state the next logical capture reads, so the view moves at once with no new
clock, timer or Settings write; the caller persists the result once, when orbiting stops
(``resolve_visualizer_view_orbit`` in ``core.settings.visualizer_view_orbit``).

Keys move the camera around the scene: W up over it, S down, A to the left, D to the
right (the near end of the row then swings toward the side the camera went). An Alt + left
drag on the Visualizer in interaction/Ctrl mode does the same, the scene turning toward the
drag (rendering/runtime_input.py).
"""

from __future__ import annotations

from typing import Any, Dict

from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor


def view_orbit_settings(mode_id: str) -> tuple[str, str] | tuple[()]:
    """The (turn, tilt) settings W/A/S/D adjust for ``mode_id``, or () when it has none."""
    try:
        return get_visualizer_mode_descriptor(mode_id).view_orbit_settings
    except (KeyError, ValueError):
        return ()


def view_orbit_values(host: Any, mode_id: str) -> Dict[str, float]:
    """The live turn and tilt of ``mode_id`` from the presentation state ``host``."""
    return {key: float(getattr(host, f"_{key}")) for key in view_orbit_settings(mode_id)}


def orbit_visualizer_view(host: Any, mode_id: str, turn_steps: float, tilt_steps: float) -> Dict[str, float]:
    """Step the live view (whole key steps, or a drag's fractional ones); returns the new values
    ({} when the mode cannot orbit). The canonical presentation applier clamps tilt to its range."""
    keys = view_orbit_settings(mode_id)
    if not keys:
        return {}
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs

    turn_key, tilt_key = keys
    turn_step, tilt_step = get_visualizer_mode_descriptor(mode_id).view_orbit_steps
    values = view_orbit_values(host, mode_id)
    turn = values[turn_key] + turn_step * float(turn_steps)
    apply_presentation_vis_mode_kwargs(host, {
        turn_key: (turn + 1.0) % 2.0 - 1.0,                     # a full circle: round and round
        tilt_key: values[tilt_key] + tilt_step * float(tilt_steps),
    })
    return view_orbit_values(host, mode_id)
