"""Sphere promotion/review cases must never read authored curated preset values."""
from __future__ import annotations

import pytest

from tools.visualizer_replay import sphere_golden


def _test_owned_reference():
    return {"presets": {
        name: {"settings": {"sphere_base_rotation_speed": 0.31 + index * 0.12}}
        for index, (name, _overrides) in enumerate(sphere_golden.CASES)
    }}


def test_frozen_cases_use_only_the_reference(monkeypatch):
    # The real preset resolver must never be consulted, even to fill missing values.
    from core.settings import visualizer_presets
    monkeypatch.setattr(visualizer_presets, "resolve_visualizer_activation_payload",
                        lambda *args, **kwargs: pytest.fail("read live authored preset"))
    source = _test_owned_reference()
    frozen = sphere_golden.case_settings(source)
    assert frozen == {name: entry["settings"] for name, entry in source["presets"].items()}
    frozen["glass_current"]["sphere_base_rotation_speed"] = 99.0
    assert source["presets"]["glass_current"]["settings"]["sphere_base_rotation_speed"] != 99.0


@pytest.mark.parametrize("missing", [name for name, _ in sphere_golden.CASES])
def test_missing_frozen_case_refuses_live_preset_fallback(missing):
    source = _test_owned_reference()
    del source["presets"][missing]
    with pytest.raises(ValueError, match="never seed from a curated preset"):
        sphere_golden.case_settings(source)


def test_no_replay_or_reference_write_path_imports_curated_preset_resolver():
    # Source-level guard on the optional tool, including its --write path.
    import inspect
    source = inspect.getsource(sphere_golden)
    assert "resolve_visualizer_activation_payload" not in source
    assert "_seed_settings" not in source
