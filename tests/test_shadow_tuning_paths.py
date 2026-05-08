"""Tests for shadow tuning defaults and profile path resolution."""


def test_shadow_tuning_hardcoded_defaults_match_user_values():
    """Verify hardcoded defaults match the user's shadowtuning.json values."""
    from core.settings import shadow_tuning

    assert shadow_tuning._CARD_DEFAULTS["blur_steps"] == 55
    assert shadow_tuning._CARD_DEFAULTS["spread"] == 8
    assert shadow_tuning._CARD_DEFAULTS["max_alpha"] == 8

    assert shadow_tuning._VOLUME_SLIDER_DEFAULTS["card_shrink_right"] == 7
    assert shadow_tuning._VOLUME_SLIDER_DEFAULTS["card_shrink_bottom"] == 7
    assert shadow_tuning._VOLUME_SLIDER_DEFAULTS["offset_x"] == 4
    assert shadow_tuning._VOLUME_SLIDER_DEFAULTS["offset_y"] == 4
    assert shadow_tuning._VOLUME_SLIDER_DEFAULTS["blur_steps"] == 60
    assert shadow_tuning._VOLUME_SLIDER_DEFAULTS["spread"] == 3
    assert shadow_tuning._VOLUME_SLIDER_DEFAULTS["max_alpha"] == 4

    assert shadow_tuning._TEXT_DEFAULTS["offset_x"] == 3
    assert shadow_tuning._TEXT_DEFAULTS["offset_y"] == 3
    assert shadow_tuning._TEXT_DEFAULTS["alpha"] == 180

    assert shadow_tuning._TEXT_LARGE_DEFAULTS["offset_x"] == 4
    assert shadow_tuning._TEXT_LARGE_DEFAULTS["offset_y"] == 4
    assert shadow_tuning._TEXT_LARGE_DEFAULTS["alpha"] == 100

    assert shadow_tuning._HEADER_DEFAULTS["alpha"] == 220

    assert shadow_tuning._ICON_DEFAULTS["alpha"] == 95
    assert shadow_tuning._ICON_DEFAULTS["scale"] == 1.5


def test_missing_shadow_tuning_writes_user_defaults(monkeypatch, tmp_path):
    """Verify missing file writes the new user defaults."""
    import json
    from core.settings import storage_paths
    from core.settings import shadow_tuning

    monkeypatch.setenv("APPDATA", str(tmp_path))
    storage_paths.reset_module_cache()
    monkeypatch.setattr("sys.argv", ["SRPSS.exe"])

    path = shadow_tuning.ensure_shadow_tuning_file()
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["card"]["blur_steps"] == 55
    assert data["card"]["max_alpha"] == 8
    assert data["volume_slider"]["blur_steps"] == 60
    assert data["text"]["alpha"] == 180
    assert data["text_large"]["alpha"] == 100
    assert data["header"]["alpha"] == 220
    assert data["icon"]["scale"] == 1.5


def test_shadow_tuning_path_uses_normal_profile(monkeypatch, tmp_path):
    """Verify normal profile uses SRPSS directory."""
    from core.settings import storage_paths
    from core.settings import shadow_tuning

    monkeypatch.setenv("APPDATA", str(tmp_path))
    storage_paths.reset_module_cache()
    monkeypatch.setattr("sys.argv", ["SRPSS.exe"])

    path = shadow_tuning._shadow_tuning_path()

    assert path == tmp_path / "SRPSS" / "shadowtuning.json"


def test_shadow_tuning_path_uses_mc_profile(monkeypatch, tmp_path):
    """Verify MC profile uses SRPSS_MC directory."""
    from core.settings import storage_paths
    from core.settings import shadow_tuning

    monkeypatch.setenv("APPDATA", str(tmp_path))
    storage_paths.reset_module_cache()
    monkeypatch.setattr("sys.argv", ["SRPSS_MC.exe"])

    path = shadow_tuning._shadow_tuning_path()

    assert path == tmp_path / "SRPSS_MC" / "shadowtuning.json"


def test_mc_first_run_copies_existing_normal_shadow_tuning(monkeypatch, tmp_path):
    """Verify MC copies existing normal profile tuning on first run."""
    import json
    from core.settings import storage_paths
    from core.settings import shadow_tuning

    monkeypatch.setenv("APPDATA", str(tmp_path))
    storage_paths.reset_module_cache()
    monkeypatch.setattr("sys.argv", ["SRPSS_MC.exe"])

    normal_dir = tmp_path / "SRPSS"
    normal_dir.mkdir(parents=True)
    normal_payload = {
        "card": {
            "card_shrink_right": 11,
            "card_shrink_bottom": 11,
            "offset_x": 4,
            "offset_y": 6,
            "blur_steps": 55,
            "spread": 8,
            "max_alpha": 8,
            "radius_extra": 0
        }
    }
    (normal_dir / "shadowtuning.json").write_text(json.dumps(normal_payload), encoding="utf-8")

    path = shadow_tuning.ensure_shadow_tuning_file()

    assert path == tmp_path / "SRPSS_MC" / "shadowtuning.json"
    assert path.is_file()

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["card"]["blur_steps"] == 55
    assert data["card"]["max_alpha"] == 8
    assert "volume_slider" in data
    assert "text" in data
    assert "text_large" in data
    assert "header" in data
    assert "icon" in data
    assert "control" in data


def test_existing_mc_shadow_tuning_is_not_overwritten(monkeypatch, tmp_path):
    """Verify existing MC file is not overwritten by normal profile."""
    import json
    from core.settings import storage_paths
    from core.settings import shadow_tuning

    monkeypatch.setenv("APPDATA", str(tmp_path))
    storage_paths.reset_module_cache()
    monkeypatch.setattr("sys.argv", ["SRPSS_MC.exe"])

    normal_dir = tmp_path / "SRPSS"
    mc_dir = tmp_path / "SRPSS_MC"
    normal_dir.mkdir(parents=True)
    mc_dir.mkdir(parents=True)

    (normal_dir / "shadowtuning.json").write_text(
        json.dumps({"card": {"blur_steps": 55}}),
        encoding="utf-8",
    )
    (mc_dir / "shadowtuning.json").write_text(
        json.dumps({"card": {"blur_steps": 77}}),
        encoding="utf-8",
    )

    path = shadow_tuning.ensure_shadow_tuning_file()
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["card"]["blur_steps"] == 77


def test_shadow_tuning_partial_file_is_canonicalized_with_new_defaults(monkeypatch, tmp_path):
    """Verify partial files are canonicalized with new defaults."""
    import json
    from core.settings import storage_paths
    from core.settings import shadow_tuning

    monkeypatch.setenv("APPDATA", str(tmp_path))
    storage_paths.reset_module_cache()
    monkeypatch.setattr("sys.argv", ["SRPSS.exe"])

    path = tmp_path / "SRPSS" / "shadowtuning.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"card": {"offset_x": 99}}), encoding="utf-8")

    shadow_tuning.ensure_shadow_tuning_file()

    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["card"]["offset_x"] == 99
    assert data["card"]["blur_steps"] == 55
    assert data["card"]["max_alpha"] == 8
    assert data["volume_slider"]["blur_steps"] == 60
    assert data["text"]["alpha"] == 180
    assert data["text_large"]["alpha"] == 100
    assert data["header"]["alpha"] == 220
    assert data["icon"]["scale"] == 1.5
