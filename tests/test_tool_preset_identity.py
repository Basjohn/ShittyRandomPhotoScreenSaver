"""Tools never name presets in code: an onboarding preview's preset is a run choice or recorded data (1D.1).

The onboarding preview foundry's chosen looks live in ``preview_runs.json`` beside the manifest, as the options the
run took (the preset by the number Settings shows); a recorded number past the catalogue falls back quietly to the
mode's default. Never asserts preset names, counts or contents: catalogues are fakes, numbers derived.
"""
from __future__ import annotations

import json

import pytest

from core.settings import visualizer_presets as vp


def _fake_catalogue(monkeypatch, size):
    monkeypatch.setattr(vp, "get_custom_preset_index", lambda mode: size)


def _record(tmp_path, monkeypatch, runs):
    from tools import onboarding_preview_foundry as foundry

    (tmp_path / foundry.PREVIEW_RUNS_FILE).write_text(json.dumps({"visualizer_previews": runs}), encoding="utf-8")
    real = foundry.load_preview_runs
    monkeypatch.setattr(foundry, "load_preview_runs", lambda source=tmp_path: real(tmp_path))
    return foundry


def test_onboarding_preview_preset_comes_from_the_run_then_the_record_then_the_default(tmp_path, monkeypatch):
    foundry = _record(tmp_path, monkeypatch, [{"visualizer_mode": "some_mode", "visualizer_preset": 3}])
    monkeypatch.setattr(foundry, "_PRESET_NUMBERS", {})
    _fake_catalogue(monkeypatch, 5)
    assert foundry._preview_preset_index("some_mode") == 2            # recorded number, 1-based
    assert foundry._preview_preset_index("an_unrecorded_mode") == 0   # the mode's own default
    monkeypatch.setattr(foundry, "_PRESET_NUMBERS", {"some_mode": 5})
    assert foundry._preview_preset_index("some_mode") == 4            # this run's choice wins
    # A recorded number the catalogue no longer has falls back quietly; this run's own choice stays loud.
    monkeypatch.setattr(foundry, "_PRESET_NUMBERS", {})
    _fake_catalogue(monkeypatch, 2)
    assert foundry._preview_preset_index("some_mode") == 0
    monkeypatch.setattr(foundry, "_PRESET_NUMBERS", {"some_mode": 3})
    with pytest.raises(LookupError):
        foundry._preview_preset_index("some_mode")


def test_onboarding_preview_names_no_preset_in_code():
    """The foundry keeps no table of preset names (negative control: the removed ``_PREVIEW_PRESETS``)."""
    from tools import onboarding_preview_foundry as foundry

    assert not hasattr(foundry, "_PREVIEW_PRESETS")


def test_recorded_runs_are_the_options_of_a_real_run_and_rebuild_by_default(tmp_path, monkeypatch):
    """Each recorded run reads back as the command-line options it stands for, and a run without
    ``--visualizer-mode`` renders the recorded modes as well as the rendered set."""
    run = {"visualizer_mode": "bubble", "visualizer_preset": 2, "photo": str(tmp_path / "wall.png")}
    foundry = _record(tmp_path, monkeypatch, [run])
    arguments = foundry.preview_run_arguments(run)
    assert arguments[:2] == ["--visualizer-mode", "bubble"]
    preset = arguments[arguments.index("--visualizer-preset") + 1]
    assert foundry.parse_preset_numbers([preset]) == {"bubble": 2}
    assert arguments[arguments.index("--photo") + 1] == run["photo"]
    modes = foundry.default_rendered_modes()
    assert set(foundry._RENDERED_VISUALIZER_PREVIEWS) | {"bubble"} == set(modes)
    # The recorded wallpaper is missing here: the run keeps the committed preview instead of another look.
    assert foundry._recorded_photo("bubble") == (True, None)
    (tmp_path / "wall.png").write_bytes(b"")
    assert foundry._recorded_photo("bubble") == (True, tmp_path / "wall.png")
    assert foundry._recorded_photo("an_unrecorded_mode") == (False, None)


def test_committed_preview_record_names_registered_modes_with_run_options_only():
    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors
    from tools import onboarding_preview_foundry as foundry

    known = {descriptor.mode_id for descriptor in iter_visualizer_mode_descriptors()}
    for mode, run in foundry.load_preview_runs().items():
        assert mode in known
        assert set(run) <= {"visualizer_mode", "visualizer_preset", "photo"}
        if run.get("visualizer_preset") is not None:
            assert isinstance(run["visualizer_preset"], int) and run["visualizer_preset"] >= 1


def test_sheet_cut_outs_leave_recorded_modes_alone(tmp_path, monkeypatch):
    """``onboarding_sheet_previews`` would restore the sheet's look over a recorded run's preview."""
    from PIL import Image

    from tools import onboarding_sheet_previews as sheets

    sheet = tmp_path / "sheet.png"
    Image.new("RGB", (200, 120), (40, 60, 80)).save(sheet)
    monkeypatch.setattr(sheets, "VISUALIZER_CARDS", {})
    monkeypatch.setattr(sheets, "VISUALIZER_UNFRAMED", {"some_mode": (10, 10, 110, 90)})
    output = tmp_path / "out"
    output.mkdir()
    _record(tmp_path, monkeypatch, [{"visualizer_mode": "some_mode", "visualizer_preset": 1}])
    assert sheets.build_visualizers(sheet, output) == []
    assert not (output / "visualizer_some_mode.png").exists()
    _record(tmp_path, monkeypatch, [])
    assert sheets.build_visualizers(sheet, output) == ["visualizer_some_mode.png"]


def test_bubble_preview_frame_is_seeded(monkeypatch):
    """Two builds of the Bubble preview are the same frame (negative control: unseeded, they differ)."""
    from core.settings.default_contract import require_canonical_default
    from tools import onboarding_preview_foundry as foundry

    config = dict(require_canonical_default("widgets.spotify_visualizer"))

    def positions():
        snapshot = foundry._build_spectrum_preview_snapshot(width=320, height=200, mode="bubble", settings=config)
        return list(snapshot.logical.mode_state.positions)

    assert positions() == positions()
    monkeypatch.setattr(foundry, "_PREVIEW_SEED", None)
    assert positions() != positions()


def test_projection_gate_probe_names_no_preset_in_code(monkeypatch):
    """The projection gate probe measures the presets a run asks for (``--visualizer-preset MODE=N``) through the
    preset owner, and keeps no table of preset names (negative control: the removed ``PRESETS`` list)."""
    import ast
    import inspect as source
    from types import SimpleNamespace

    from tools.visualizer_replay import extruded_bubble_projection_gate_probe as probe

    # No module-level collection of strings: the shape a named preset list takes.
    for node in ast.parse(source.getsource(probe)).body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, (ast.Tuple, ast.List, ast.Set)):
            assert not any(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in node.value.elts)

    # A fake catalogue of three presets: what is measured is exactly what the run asked for, by number.
    asked: list[tuple[str, int]] = []

    def activation(config, *, mode):
        index = config[f"preset_{mode}"]
        asked.append((mode, index))
        return SimpleNamespace(preset_name=f"fake {index}",
                               resolved_config={f"{mode}_focus": 0.5 + 0.1 * index,
                                                f"{mode}_aperture": 0.5 + 0.1 * index})

    monkeypatch.setattr(vp, "get_custom_preset_index", lambda mode: 3)
    monkeypatch.setattr(vp, "resolve_visualizer_activation_payload", activation)
    selection = probe.parse_selection(["some_mode=3", "some_mode=1"])
    result = probe.inspect(selection)  # also checks its mirrored shader/renderer signatures are still current
    assert asked == [("some_mode", 2), ("some_mode", 0)]
    assert list(result["near_layer_gate"]) == ["some_mode=3", "some_mode=1"]
    assert result["near_layer_gate"]["some_mode=3"]["focus"] == pytest.approx(2.5 + 3 * 0.7, abs=1e-4)
    # Without an option the default mode's default preset is measured; a number past the catalogue is loud.
    assert probe.parse_selection(None) == [(probe.DEFAULT_MODE, 1)]
    with pytest.raises(LookupError):
        probe.inspect([("some_mode", 4)])
    with pytest.raises(ValueError):
        probe.parse_selection(["some_mode"])
