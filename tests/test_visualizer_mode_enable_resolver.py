"""V2 effective enabled-mode / mode-substitution resolver contract.

Pure registry logic: normalizing a persisted enabled-mode selection and
resolving a requested mode against the effective enabled set. No Qt, no
settings persistence — those live in the settings model and are covered by the
round-trip audit test.
"""
from __future__ import annotations

from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    get_default_visualizer_mode_id,
    resolve_effective_enabled_modes,
    resolve_effective_mode,
    resolve_effective_visualizer_section,
)


def test_absent_selection_enables_all_modes_migration_default():
    assert resolve_effective_enabled_modes(None) == VISUALIZER_MODE_IDS


def test_empty_or_garbage_selection_never_disables_the_family():
    assert resolve_effective_enabled_modes([]) == VISUALIZER_MODE_IDS
    assert resolve_effective_enabled_modes(["nope", "xxx"]) == VISUALIZER_MODE_IDS
    assert resolve_effective_enabled_modes(123) == VISUALIZER_MODE_IDS


def test_selection_is_deduped_and_canonically_ordered():
    # Stored order is irrelevant; canonical order is authoritative.
    assert resolve_effective_enabled_modes(
        ["bubble", "spectrum", "bubble"]
    ) == ("spectrum", "bubble")
    assert resolve_effective_enabled_modes(
        ["devcurve", "bubble", "nope", "spectrum"]
    ) == ("spectrum", "bubble", "devcurve")


def test_single_string_selection_is_accepted():
    assert resolve_effective_enabled_modes("sine_wave") == ("sine_wave",)


def test_requested_enabled_mode_is_returned_unchanged():
    assert resolve_effective_mode("bubble", ["spectrum", "bubble"]) == ("bubble", False)


def test_disabled_canonical_mode_substitutes_next_enabled_in_canonical_order():
    # oscilloscope disabled -> next enabled after it in canonical order is sine_wave.
    mode, substituted = resolve_effective_mode(
        "oscilloscope", ["spectrum", "sine_wave", "bubble", "devcurve"]
    )
    assert (mode, substituted) == ("sine_wave", True)


def test_disabled_canonical_mode_wraps_once_when_needed():
    # spectrum disabled, only bubble/devcurve enabled -> wraps to bubble.
    mode, substituted = resolve_effective_mode("spectrum", ["bubble", "devcurve"])
    assert (mode, substituted) == ("bubble", True)


def test_unknown_mode_prefers_configured_default_when_enabled():
    default_mode = get_default_visualizer_mode_id()
    mode, substituted = resolve_effective_mode("garbage", [default_mode, "spectrum"])
    assert (mode, substituted) == (default_mode, True)


def test_unknown_mode_falls_back_to_first_enabled_when_default_disabled():
    default_mode = get_default_visualizer_mode_id()
    enabled = [m for m in ("spectrum", "oscilloscope") if m != default_mode]
    mode, substituted = resolve_effective_mode("garbage", enabled)
    assert substituted is True
    assert mode == resolve_effective_enabled_modes(enabled)[0]


def test_substitute_is_never_a_disabled_mode():
    for requested in VISUALIZER_MODE_IDS + ("garbage",):
        enabled = ["bubble"]
        mode, _ = resolve_effective_mode(requested, enabled)
        assert mode in resolve_effective_enabled_modes(enabled)


def test_cycling_restricted_to_enabled_modes_v3():
    from rendering.quick.visualizer.double_click_admission import (
        next_visualizer_mode_id,
    )

    # No enable-state context -> full registered cycle (legacy behavior).
    assert next_visualizer_mode_id("spectrum") == "oscilloscope"

    # Restricted enabled set: cycle only enabled modes, canonical order, wrapping.
    enabled = ["spectrum", "bubble"]
    assert next_visualizer_mode_id("spectrum", enabled) == "bubble"
    assert next_visualizer_mode_id("bubble", enabled) == "spectrum"
    # A disabled current mode starts the cycle at the first enabled mode.
    assert next_visualizer_mode_id("sine_wave", enabled) == "spectrum"

    # A single enabled mode cycles to itself.
    assert next_visualizer_mode_id("bubble", ["bubble"]) == "bubble"

    # Never lands on a disabled mode regardless of the current id.
    for current in VISUALIZER_MODE_IDS:
        assert next_visualizer_mode_id(current, enabled) in tuple(enabled)


# ---------------------------------------------------------------------------
# resolve_effective_visualizer_section: pre-V5/V6 startup substitution ordering
# ---------------------------------------------------------------------------


def test_effective_section_passes_enabled_mode_through_unchanged():
    section = {"mode": "spectrum", "enabled_modes": ["spectrum", "bubble"], "foo": 1}
    effective, substituted, requested, resolved = (
        resolve_effective_visualizer_section(section)
    )
    assert substituted is False
    assert requested == "spectrum"
    assert resolved == "spectrum"
    assert effective["mode"] == "spectrum"
    assert effective["foo"] == 1
    # Pure: the input section is never mutated.
    assert section["mode"] == "spectrum"


def test_effective_section_substitutes_disabled_mode_before_activation():
    # oscilloscope is canonical but disabled; canonical walk skips sine_wave
    # (disabled) and lands on bubble. The returned section carries the
    # substitute so the activation/model payload resolves for mode B, not A.
    section = {"mode": "oscilloscope", "enabled_modes": ["spectrum", "bubble"]}
    effective, substituted, requested, resolved = (
        resolve_effective_visualizer_section(section)
    )
    assert substituted is True
    assert requested == "oscilloscope"
    assert resolved == "bubble"
    assert effective["mode"] == "bubble"
    assert effective["enabled_modes"] == ["spectrum", "bubble"]
    # Input untouched.
    assert section["mode"] == "oscilloscope"


def test_effective_section_absent_selection_keeps_mode_all_enabled():
    # No enabled_modes -> all modes enabled (migration default) -> no substitution.
    section = {"mode": "bubble"}
    effective, substituted, requested, resolved = (
        resolve_effective_visualizer_section(section)
    )
    assert substituted is False
    assert resolved == "bubble"
    assert effective["mode"] == "bubble"


def test_effective_section_non_mapping_yields_default_mode():
    effective, substituted, requested, resolved = (
        resolve_effective_visualizer_section(None)
    )
    assert effective == {}
    assert substituted is False
    assert requested == ""
    assert resolved == get_default_visualizer_mode_id()
