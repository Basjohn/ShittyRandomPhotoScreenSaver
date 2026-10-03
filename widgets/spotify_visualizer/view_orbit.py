"""Live W/A/S/D view orbiting for 3D freeform Visualizer modes.

A mode opts in through its descriptor's ``view_orbit_settings`` (its turn and tilt
presentation settings, each spanning its full angle over a range of 1 for tilt and
2 for turn). A key event steps the live presentation state the next logical capture
reads, so the view moves at once with no new clock, timer or Settings write; the
caller persists the result once, when orbiting stops (``resolve_visualizer_view_orbit``
in ``core.settings.visualizer_view_orbit``).

Keys move the camera around the scene: W up over it, S down, A to the left, D to the
right (the near end of the row then swings toward the side the camera went).
"""

from __future__ import annotations

from typing import Any, Dict

from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor

# One key event's step, in setting units (a twentieth of tilt's range: 2 degrees of a 40 degree tilt).
VIEW_ORBIT_STEP = 0.05


def view_orbit_settings(mode_id: str) -> tuple[str, str] | tuple[()]:
    """The (turn, tilt) settings W/A/S/D adjust for ``mode_id``, or () when it has none."""
    try:
        return get_visualizer_mode_descriptor(mode_id).view_orbit_settings
    except (KeyError, ValueError):
        return ()


def view_orbit_values(host: Any, mode_id: str) -> Dict[str, float]:
    """The live turn and tilt of ``mode_id`` from the presentation state ``host``."""
    return {key: float(getattr(host, f"_{key}")) for key in view_orbit_settings(mode_id)}


def orbit_visualizer_view(host: Any, mode_id: str, turn_steps: int, tilt_steps: int) -> Dict[str, float]:
    """Step the live view by whole key steps; returns the new values ({} when the mode
    cannot orbit). The canonical presentation applier clamps each setting to its range."""
    keys = view_orbit_settings(mode_id)
    if not keys:
        return {}
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs

    turn_key, tilt_key = keys
    values = view_orbit_values(host, mode_id)
    apply_presentation_vis_mode_kwargs(host, {
        turn_key: values[turn_key] + VIEW_ORBIT_STEP * int(turn_steps),
        tilt_key: values[tilt_key] + VIEW_ORBIT_STEP * int(tilt_steps),
    })
    return view_orbit_values(host, mode_id)
