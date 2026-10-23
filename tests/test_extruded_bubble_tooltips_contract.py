"""EB Settings tooltip completeness and range semantics, without historical audit-tag goldens.

The spec is authoritative about which controls exist. Outstanding visual/audio
issues remain in the relevant investigation and acceptance documents, not tooltip
markers or a frozen control count.
"""
from core.settings.visualizer_mode_settings import Range, require_mode_settings


def test_eb_visible_controls_have_unique_keys_and_useful_tooltips():
    entries = [entry for entry in require_mode_settings("extruded_bubble").entries if entry.bucket]
    assert entries, "the EB Settings spec must expose controls"
    assert len({entry.key for entry in entries}) == len(entries)
    for entry in entries:
        tip = entry.tooltip.strip()
        assert tip, entry.key
        assert not tip.startswith("[NEEDS AUDIT]"), entry.key
        assert "\n" not in tip, entry.key
        if "[NEEDS AUDIT]" in tip:
            explanation, _, followup = tip.partition("[NEEDS AUDIT]")
            assert explanation.strip() and followup.strip(), entry.key


def test_each_eb_music_range_explains_both_ends_of_its_response():
    # New ranges are automatically admitted; no hardcoded list of today's controls.
    entries = [entry for entry in require_mode_settings("extruded_bubble").entries
               if entry.bucket and isinstance(entry, Range)]
    assert entries, "the EB spec must retain at least one musical response range"
    for entry in entries:
        tip = entry.tooltip.lower()
        assert "quiet" in tip and "loud" in tip, entry.key
