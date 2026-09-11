"""Contracts for Particle swirl continuity and Settings label parity."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHADER = ROOT / "rendering/gl_programs/particle_program.py"
SETTINGS = ROOT / "ui/tabs/transitions_tab.py"
RESOLUTION = ROOT / "rendering/quick/transitions/parameter_resolution.py"


def test_center_outward_swirl_uses_periodic_angle_term_without_branch_cut():
    source = SHADER.read_text(encoding="utf-8")
    start = source.index("if (swirlOrder == 1)")
    end = source.index("if (swirlOrder == 2)", start)
    branch = source[start:end]

    assert "float spiralPhase = theta + rNorm * swirlTurns * TWO_PI;" in branch
    assert "float spiralHint = sin(spiralPhase) * 0.045;" in branch
    assert "cwAngle" not in branch
    assert "thetaNorm * 0.18" not in branch


def test_particle_settings_labels_match_persisted_shader_indices():
    source = SETTINGS.read_text(encoding="utf-8")
    assert '''self.particle_light_combo.addItems([\n            "NW",\n            "NE",\n            "Front",\n            "SW",\n            "SE",\n        ])''' in source
    assert '''self.particle_swirl_order_combo.addItems([\n            "Typical",\n            "Center Outward",\n            "Edges Inward",\n        ])''' in source

    resolution = RESOLUTION.read_text(encoding="utf-8")
    assert "the persisted values remain integer indices" in resolution
