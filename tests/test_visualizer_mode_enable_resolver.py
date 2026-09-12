"""Current Visualizer mode-activation / substitution resolver contracts.

Persisted enable state is the explicit ``mode_activation`` boolean mapping.
Internal Settings helpers may still use a derived enabled-id tuple, but ordinary
runtime/settings readers must not treat the retired ``enabled_modes`` list as a
second product schema. Legacy-list migration is covered separately by
``test_visualizer_mode_activation_schema_current.py``.
"""
from __future__ import annotations

from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    apply_visualizer_mode_disable,
    build_visualizer_mode_activation,
    can_disable_visualizer_mode,
    get_default_visualizer_mode_id,
    resolve_admissible_enabled_modes,
    resolve_effective_enabled_modes,
    resolve_effective_mode,
    resolve_effective_visualizer_section,
)


def _activation(*mode_ids: str) -> dict[str, bool]:
    return build_visualizer_mode_activation(mode_ids)


def test_absent_activation_resolves_through_canonical_defaults():
    assert resolve_effective_enabled_modes(None) == VISUALIZER_MODE_IDS


def test_malformed_non_mapping_activation_never_disables_the_family():
    # The retired enabled-id list is intentionally NOT a runtime schema anymore.
    # Malformed/currently-invalid shapes recover through canonical defaults.
    assert resolve_effective_enabled_modes([]) == VISUALIZER_MODE_IDS
    assert resolve_effective_enabled_modes(["bubble", "spectrum"]) == VISUALIZER_MODE_IDS
    assert resolve_effective_enabled_modes(123) == VISUALIZER_MODE_IDS


def test_write_side_builder_dedupes_and_resolver_uses_registry_order():
    activation = build_visualizer_mode_activation(
        ["bubble", "spectrum", "bubble"]
    )
    assert resolve_effective_enabled_modes(activation) == ("spectrum", "bubble")

    activation = build_visualizer_mode_activation(
        ["devcurve", "bubble", "nope", "spectrum"]
    )
    assert resolve_effective_enabled_modes(activation) == (
        "spectrum",
        "bubble",
        "devcurve",
    )


def test_write_side_builder_accepts_single_mode_id():
    activation = build_visualizer_mode_activation("sine_wave")
    assert resolve_effective_enabled_modes(activation) == ("sine_wave",)


def test_requested_enabled_mode_is_returned_unchanged():
    assert resolve_effective_mode(
        "bubble", _activation("spectrum", "bubble")
    ) == ("bubble", False)


def test_disabled_canonical_mode_substitutes_next_enabled_in_canonical_order():
    mode, substituted = resolve_effective_mode(
        "oscilloscope",
        _activation("spectrum", "sine_wave", "bubble", "devcurve"),
    )
    assert (mode, substituted) == ("sine_wave", True)


def test_disabled_canonical_mode_wraps_once_when_needed():
    mode, substituted = resolve_effective_mode(
        "spectrum", _activation("bubble", "devcurve")
    )
    assert (mode, substituted) == ("bubble", True)


def test_unknown_mode_prefers_configured_default_when_enabled():
    default_mode = get_default_visualizer_mode_id()
    activation = build_visualizer_mode_activation((default_mode, "spectrum"))
    mode, substituted = resolve_effective_mode("garbage", activation)
    assert (mode, substituted) == (default_mode, True)


def test_unknown_mode_falls_back_to_first_enabled_when_default_disabled():
    default_mode = get_default_visualizer_mode_id()
    enabled = tuple(
        mode for mode in ("spectrum", "oscilloscope") if mode != default_mode
    )
    activation = build_visualizer_mode_activation(enabled)
    mode, substituted = resolve_effective_mode("garbage", activation)
    assert substituted is True
    assert mode == resolve_effective_enabled_modes(activation)[0]


def test_substitute_is_never_a_disabled_mode():
    activation = _activation("bubble")
    for requested in VISUALIZER_MODE_IDS + ("garbage",):
        mode, _ = resolve_effective_mode(requested, activation)
        assert mode in resolve_effective_enabled_modes(activation)


def test_cycling_restricted_to_mode_activation_v3():
    from rendering.quick.visualizer.double_click_admission import (
        next_visualizer_mode_id,
    )

    # No activation context -> full registered cycle.
    assert next_visualizer_mode_id("spectrum") == "oscilloscope"

    activation = _activation("spectrum", "bubble")
    assert next_visualizer_mode_id("spectrum", activation) == "bubble"
    assert next_visualizer_mode_id("bubble", activation) == "spectrum"
    # A disabled current mode starts at the first enabled mode.
    assert next_visualizer_mode_id("sine_wave", activation) == "spectrum"

    single = _activation("bubble")
    assert next_visualizer_mode_id("bubble", single) == "bubble"

    for current in VISUALIZER_MODE_IDS:
        assert next_visualizer_mode_id(current, activation) in ("spectrum", "bubble")


# ---------------------------------------------------------------------------
# resolve_effective_visualizer_section: startup substitution ordering
# ---------------------------------------------------------------------------


def test_effective_section_passes_enabled_mode_through_unchanged():
    activation = _activation("spectrum", "bubble")
    section = {"mode": "spectrum", "mode_activation": activation, "foo": 1}
    effective, substituted, requested, resolved = (
        resolve_effective_visualizer_section(section)
    )
    assert substituted is False
    assert requested == "spectrum"
    assert resolved == "spectrum"
    assert effective["mode"] == "spectrum"
    assert effective["foo"] == 1
    assert effective["mode_activation"] == activation
    assert section["mode"] == "spectrum"  # pure: input never mutated


def test_effective_section_substitutes_disabled_mode_before_activation():
    activation = _activation("spectrum", "bubble")
    section = {"mode": "oscilloscope", "mode_activation": activation}
    effective, substituted, requested, resolved = (
        resolve_effective_visualizer_section(section)
    )
    assert substituted is True
    assert requested == "oscilloscope"
    assert resolved == "bubble"
    assert effective["mode"] == "bubble"
    assert effective["mode_activation"] == activation
    assert section["mode"] == "oscilloscope"


def test_effective_section_absent_activation_uses_canonical_defaults():
    section = {"mode": "bubble"}
    effective, substituted, requested, resolved = (
        resolve_effective_visualizer_section(section)
    )
    assert substituted is False
    assert requested == "bubble"
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


# ---------------------------------------------------------------------------
# Last-enabled-mode guard uses the derived in-memory enabled-id view by design.
# ---------------------------------------------------------------------------


def test_cannot_disable_the_final_enabled_mode():
    assert can_disable_visualizer_mode(["spectrum", "bubble"], "spectrum") is True
    assert can_disable_visualizer_mode(["bubble"], "bubble") is False
    assert can_disable_visualizer_mode(["bubble"], "spectrum") is False


def test_apply_disable_never_widens_to_all_modes():
    assert apply_visualizer_mode_disable(
        ["spectrum", "bubble"], "spectrum"
    ) == ("bubble",)
    result = apply_visualizer_mode_disable(["bubble"], "bubble")
    assert result == ("bubble",)
    assert result != VISUALIZER_MODE_IDS


def test_admissible_modes_intersect_activation_with_dev_active():
    activation = _activation("bubble", "spectrum")
    assert resolve_admissible_enabled_modes(activation) == ("spectrum", "bubble")
    assert resolve_admissible_enabled_modes(None) == VISUALIZER_MODE_IDS
