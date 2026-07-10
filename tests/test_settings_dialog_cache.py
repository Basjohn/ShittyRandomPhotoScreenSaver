from __future__ import annotations

import os

import ui.settings_dialog_cache as cache_module


def test_defaults_generation_tracks_canonical_base_and_mc_overlay(
    tmp_path,
    monkeypatch,
) -> None:
    paths = tuple(tmp_path / filename for filename in (
        "defaults.py",
        "default_settings.py",
        "default_profile_overrides.py",
    ))
    for index, path in enumerate(paths, start=1):
        path.write_text("# defaults source\n", encoding="utf-8")
        os.utime(path, (float(index), float(index)))
    monkeypatch.setattr(cache_module, "_DEFAULTS_SOURCE_PATHS", paths)

    initial_generation = cache_module._compute_defaults_generation()
    os.utime(paths[-1], (10.0, 10.0))

    assert initial_generation == 3.0
    assert cache_module._compute_defaults_generation() == 10.0
