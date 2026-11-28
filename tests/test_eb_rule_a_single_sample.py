"""Extruded Bubble's rule (a) judges its multisampled scene by the single-sampled form (D8 point 1; the proof guide,
section 3): inside the owner's ``single_sample_scene_targets`` the native program variant declares one sample, as the
Python scene target then takes."""
from types import SimpleNamespace

from rendering.gl_programs.scene3d import SCENE3D_DETAIL_TIERS


def _snapshot(tier):
    return SimpleNamespace(logical=SimpleNamespace(mode_state=SimpleNamespace(parameters={"scene3d_detail": tier})))


def test_rule_a_single_samples_the_native_scene_as_pythons():
    from rendering.native import extruded_bubble_program as program
    from tools.visualizer_replay import owner_render_parity as parity

    tier = next(name for name, detail in SCENE3D_DETAIL_TIERS.items() if detail.overlay_samples > 1)
    product = program.variant_of(_snapshot(tier))
    assert product[0] > 1
    with parity.single_sample_scene_targets():
        single = program.variant_of(_snapshot(tier))
        assert single == (1,)
        scene = next(t for t in program.program(single)["targets"] if getattr(t, "name", None) == program.SCENE)
        assert scene.samples == 1
    # Negative control: after the block the tier's samples are back, so the product never draws single-sampled.
    assert program.variant_of(_snapshot(tier)) == product
