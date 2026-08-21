"""Phase-C resolver must inherit sparse values from canonical Settings defaults."""

import pytest

from core.settings.defaults import get_default_settings
from rendering.quick.transitions.parameter_resolution import (
    resolve_parameterized_phase_c_inputs,
)


class _Rng:
    def random(self) -> float:
        return 0.25

    def choice(self, seq):
        return seq[0]

    def randint(self, a: int, b: int) -> int:
        return a


def _defaults(name: str) -> dict[str, object]:
    value = get_default_settings().get("transitions", {}).get(name, {})
    assert isinstance(value, dict)
    return value


def test_sparse_blinds_uses_canonical_feather_and_direction():
    defaults = _defaults("blinds")
    resolved = resolve_parameterized_phase_c_inputs(
        "blinds", {}, random_source=_Rng()
    )
    params = resolved.parameter_dict()
    # Feather derives from the canonical UI value through the preserved
    # UI-scale -> shader-scale conversion, not a renderer magic constant.
    ui_feather = float(defaults.get("feather", 2))
    expected_feather = max(0.001, min(0.5, (ui_feather / 25.0) * 0.5))
    assert params["feather"] == pytest.approx(expected_feather)
    # Canonical default direction drives resolution. "Random" defers to the
    # random source (deterministic _Rng.choice -> first option) instead of a
    # renderer default.
    raw_direction = str(defaults.get("direction", "Horizontal") or "Horizontal")
    if raw_direction == "Random":
        expected_direction = "horizontal"
    else:
        expected_direction = {
            "Horizontal": "horizontal",
            "Vertical": "vertical",
            "Diagonal": "diagonal",
        }.get(raw_direction, "horizontal")
    assert resolved.direction == expected_direction


def test_sparse_ripple_uses_canonical_ripple_count():
    defaults = _defaults("ripple")
    resolved = resolve_parameterized_phase_c_inputs(
        "ripple", {}, random_source=_Rng()
    ).parameter_dict()
    expected_count = max(1, min(8, int(defaults.get("ripple_count", 3))))
    assert resolved["ripple_count"] == expected_count
    # Seed derives from the injected random source, not a renderer constant.
    assert resolved["ripple_seed"] == pytest.approx(0.25 * 1000.0)


def test_sparse_diffuse_uses_canonical_block_size_and_shape():
    defaults = _defaults("diffuse")
    resolved = resolve_parameterized_phase_c_inputs(
        "diffuse", {}, random_source=_Rng()
    ).parameter_dict()
    expected_shape = {
        "rectangle": 0,
        "membrane": 1,
        "lines": 2,
        "diamonds": 3,
        "amorph": 4,
        "random": 5,
    }.get(str(defaults.get("shape", "Rectangle")).strip().lower(), 0)
    assert resolved["block_size"] == int(defaults.get("block_size", 50))
    assert resolved["shape_mode"] == expected_shape


def test_sparse_crumble_uses_canonical_piece_count_and_complexity():
    defaults = _defaults("crumble")
    resolved = resolve_parameterized_phase_c_inputs(
        "crumble", {}, random_source=_Rng()
    ).parameter_dict()
    assert resolved["piece_count"] == int(defaults.get("piece_count", 14))
    assert resolved["crack_complexity"] == pytest.approx(
        float(defaults.get("crack_complexity", 1.0))
    )


def test_sparse_particle_uses_canonical_authored_defaults():
    defaults = _defaults("particle")
    resolved = resolve_parameterized_phase_c_inputs(
        "particle", {}, random_source=_Rng()
    ).parameter_dict()
    assert resolved["particle_radius"] == pytest.approx(
        max(8.0, float(defaults.get("particle_radius", 10.0)))
    )
    assert resolved["overlap"] == pytest.approx(
        max(0.0, float(defaults.get("overlap", 4.0)))
    )
    assert resolved["swirl_turns"] == pytest.approx(
        max(0.5, float(defaults.get("swirl_turns", 3.0)))
    )
    assert resolved["wobble"] is bool(defaults.get("wobble", True))
    assert resolved["use_3d_shading"] is bool(
        defaults.get("use_3d_shading", True)
    )
    assert resolved["texture_mapping"] is bool(
        defaults.get("texture_mapping", True)
    )


def test_sparse_burn_uses_canonical_glow_colour_and_controls():
    defaults = _defaults("burn")
    resolved = resolve_parameterized_phase_c_inputs(
        "burn", {}, random_source=_Rng()
    ).parameter_dict()
    glow = tuple(float(value) for value in defaults.get("glow_color", [255, 140, 30, 255]))
    expected_glow = glow if max(glow) <= 1.0 else tuple(value / 255.0 for value in glow)
    assert resolved["glow_color"] == pytest.approx(expected_glow)
    assert resolved["jaggedness"] == pytest.approx(
        float(defaults.get("jaggedness", 0.5))
    )
    assert resolved["char_width"] == pytest.approx(
        max(0.1, float(defaults.get("char_width", 0.5)))
    )


def test_legacy_boolean_spellings_are_resolved_before_render_ownership():
    resolved = resolve_parameterized_phase_c_inputs(
        "particle",
        {"particle": {"wobble": "false", "use_3d_shading": "0", "texture_mapping": "yes"}},
        random_source=_Rng(),
    ).parameter_dict()
    assert resolved["wobble"] is False
    assert resolved["use_3d_shading"] is False
    assert resolved["texture_mapping"] is True
