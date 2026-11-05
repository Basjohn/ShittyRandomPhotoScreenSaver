"""Tools name the operator's chosen curated preset by its stable file-name identity, never by slot (side defect).

A slot index silently changes meaning when the catalogue changes (a new preset, a reindex); a named look either
resolves to the same file or fails loudly. Never asserts preset counts, slots or values: positions are derived.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.settings import visualizer_presets as vp


def _fake_catalogue(monkeypatch, names):
    paths = [Path(f"preset_{i + 1}_{name}.json") for i, name in enumerate(names)]
    monkeypatch.setattr(vp, "get_custom_preset_index", lambda mode: len(paths))
    monkeypatch.setattr(vp, "get_preset_file_path", lambda mode, index: paths[index] if 0 <= index < len(paths) else None)


def test_onboarding_preview_follows_its_named_preset_when_the_catalogue_moves(monkeypatch):
    from tools import onboarding_preview_foundry as foundry

    mode, wanted = next(iter(foundry._PREVIEW_PRESETS.items()))
    _fake_catalogue(monkeypatch, ["alpha", wanted, "omega"])
    assert foundry._preview_preset_index(mode) == 1
    _fake_catalogue(monkeypatch, ["alpha", "beta", "gamma", "delta", wanted])
    assert foundry._preview_preset_index(mode) == 4
    assert foundry._preview_preset_index("a_mode_without_a_named_preview") == 0


def test_onboarding_preview_fails_loudly_when_its_named_preset_is_gone(monkeypatch):
    """Negative control: a missing look is an error, never a silent fallback to another slot."""
    from tools import onboarding_preview_foundry as foundry

    mode, wanted = next(iter(foundry._PREVIEW_PRESETS.items()))
    _fake_catalogue(monkeypatch, ["alpha", "beta", f"{wanted}_two"])
    with pytest.raises(LookupError, match=wanted):
        foundry._preview_preset_index(mode)


def test_onboarding_preview_named_preset_exists_in_the_real_catalogue():
    from tools import onboarding_preview_foundry as foundry

    for mode, wanted in foundry._PREVIEW_PRESETS.items():
        index = foundry._preview_preset_index(mode)
        assert vp.get_preset_file_path(mode, index).stem.endswith(f"_{wanted}")


def test_projection_gate_probe_reads_named_presets_against_current_source():
    from tools.visualizer_replay import extruded_bubble_projection_gate_probe as probe

    result = probe.inspect()  # also checks its mirrored shader/renderer signatures are still current
    assert set(result["near_layer_gate"]) == {probe.preset_path(name).stem for name in probe.PRESETS}
    with pytest.raises(LookupError):
        probe.preset_path("a_preset_nobody_authored")
