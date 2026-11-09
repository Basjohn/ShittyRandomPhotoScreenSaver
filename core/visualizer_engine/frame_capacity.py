"""Bounded packet capacity, resolved once at a configure/hidden activation edge."""
from __future__ import annotations

from collections.abc import Mapping

from core.visualizer_engine.packet_abi import mode_code

# Non-geometry frame envelope: maximum step/wake/body records, parameters and codec/publication metadata.
BASE_SLOT_BYTES = 1 << 20


def required_slot_bytes(mode: str, logical_kwargs: Mapping) -> int:
    """Reserve the canonical maximum of each admitted EB drift family; other modes keep the common envelope.

    Emission can overshoot the authored endpoints and capacity retains its high-water mark. Never estimate it from
    the first frame or multiply the endpoints into geometry counts. No default/preset values are owned here.
    """
    mode_code(mode)
    if mode != 'extruded_bubble':
        return BASE_SLOT_BYTES
    from core.constants.extruded_bubble_world import SPECKS_FULL, SNOW_FULL
    from widgets.spotify_visualizer.extruded_bubble_drift_log import CHAIN_GEOMETRY_BYTES, CLOUD_GEOMETRY_BYTES
    from widgets.spotify_visualizer.extruded_bubble_material_paths import drawable_chains

    def active(suffix):
        return any(float(value) != 0. for value in logical_kwargs['extruded_bubble_'+suffix])

    if not active('drift'):
        return BASE_SLOT_BYTES
    geometry = 0
    if active('drift_chains'):
        geometry += drawable_chains(logical_kwargs['extruded_bubble_bead_chains'])*CHAIN_GEOMETRY_BYTES
    if active('particles'):
        if active('drift_snow'):
            geometry += SNOW_FULL*CLOUD_GEOMETRY_BYTES
        if active('drift_specks'):
            geometry += SPECKS_FULL*CLOUD_GEOMETRY_BYTES
    return (BASE_SLOT_BYTES+geometry+15)//16*16
