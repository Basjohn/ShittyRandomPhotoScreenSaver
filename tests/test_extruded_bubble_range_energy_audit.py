"""EB-R33: fast Qt-free wiring gate for nine music-driven Range widgets.

This checks that the energy paths remain live, not that the endpoints have
correct artistic semantics or that native pixels are visually accepted.
Can run directly with Python, or as a focused pytest module on Windows.
"""
from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.settings.visualizer_mode_settings import Range, require_mode_settings
from tools.visualizer_replay.extruded_bubble_range_energy_audit import report

EXPECTED = {
    "extruded_bubble_rays", "extruded_bubble_large_bubbles", "extruded_bubble_mid_bubbles",
    "extruded_bubble_bead_chains", "extruded_bubble_stream_speed", "extruded_bubble_drift",
    "extruded_bubble_breathing", "extruded_bubble_small_pulse", "extruded_bubble_particles",
}
# Signed per-family Drift multipliers (quiet/loud on the same passage), scaling the Drift Range above.
DRIFT_FAMILIES = {
    f"extruded_bubble_drift_{family}" for family in ("large", "small", "fused", "chains", "snow", "specks")
}


def test_all_eb_music_ranges_have_two_admitted_ends():
    spec = require_mode_settings('extruded_bubble')
    controls = {c.key: c for c in spec.controls if isinstance(c, Range)}
    assert set(controls) == EXPECTED | DRIFT_FAMILIES
    for item in controls.values():
        midpoint = (item.low + item.high) / 2
        admitted = item.admit([item.low, midpoint], [item.low, item.high])
        assert len(admitted) == 2 and admitted[0] <= admitted[1], item.key


def test_all_energy_consumers_move_in_controlled_music_without_pretending_endpoints_are_exact():
    data = report()['controlled_inputs']
    quiet, moderate, full = data['silence'], data['moderate'], data['full_bands']
    for key in ('large_count_target', 'small_count_target', 'bead_chain_target_before_detail_tier',
                'stream_speed_fraction_before_world_units', 'drift', 'particles_emission',
                'large_breath_radius_multiplier', 'small_breath_radius_multiplier',
                'ray_range_output_fraction'):
        assert quiet[key] < moderate[key] < full[key], (key, quiet[key], moderate[key], full[key])
    # Counts/beads can reach the authored high end under all-three-bands full
    # input, whereas other range consumers currently add activity and/or caps.
    assert full['large_count_target'] == 16.0
    assert full['small_count_target'] == 48.0
    assert full['bead_chain_target_before_detail_tier'] == 8.0


if __name__ == '__main__':
    test_all_eb_music_ranges_have_two_admitted_ends()
    test_all_energy_consumers_move_in_controlled_music_without_pretending_endpoints_are_exact()
    print('EB_RANGE_ENERGY_AUDIT: two logical checks passed; nine endpoints NOT visually accepted')
