"""EB tooltip completeness and non-acceptance language; Qt-free Settings spec check.

The actual on-screen hover is verified by the separate native lazy-bucket test.
These checks do not validate the renderer or resolve any operator visual complaint.
"""
from core.settings.visualizer_mode_settings import Range, require_mode_settings

MUSIC_RANGES = {
    'extruded_bubble_rays', 'extruded_bubble_large_bubbles',
    'extruded_bubble_mid_bubbles', 'extruded_bubble_bead_chains',
    'extruded_bubble_stream_speed', 'extruded_bubble_drift',
    'extruded_bubble_breathing', 'extruded_bubble_small_pulse',
    'extruded_bubble_particles',
}


def test_eb_every_visible_control_has_an_explanatory_tooltip():
    entries = [c for c in require_mode_settings('extruded_bubble').entries if c.bucket]
    assert len(entries) == 58  # Includes the independently authored Lens FOV control.
    assert len({c.key for c in entries}) == len(entries)
    for entry in entries:
        assert entry.tooltip.strip(), entry.key
        assert len(entry.tooltip) > 45, entry.key
        assert not entry.tooltip.lstrip().startswith('[NEEDS AUDIT]'), entry.key
        if '[NEEDS AUDIT]' in entry.tooltip:
            first, marker, reason = entry.tooltip.partition('[NEEDS AUDIT]')
            assert first.rstrip().endswith('.'), entry.key
            assert len(first.strip()) > 25, entry.key
            assert len(reason.strip()) > 25, entry.key
        assert '\n' not in entry.tooltip, entry.key


def test_all_nine_range_wiring_disputes_remain_flagged_in_the_ui():
    entries = {c.key: c for c in require_mode_settings('extruded_bubble').entries if c.bucket}
    assert {key for key, c in entries.items() if isinstance(c, Range)} == MUSIC_RANGES
    for key in MUSIC_RANGES:
        tip = entries[key].tooltip
        assert '[NEEDS AUDIT]' in tip, key
        assert 'quiet' in tip.lower() and 'loud' in tip.lower(), key


def test_existing_known_control_defects_have_explicit_flags():
    spec = require_mode_settings('extruded_bubble')
    entries = {c.key: c for c in spec.entries if c.bucket}
    for key in ('light_direction', 'light_strength', 'ray_path', 'smoothing',
                'sustained', 'sparkle', 'focus', 'aperture', 'camera_position'):
        assert '[NEEDS AUDIT]' in entries['extruded_bubble_' + key].tooltip
