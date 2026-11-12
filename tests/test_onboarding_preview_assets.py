"""Release-asset contract for deterministic Guided Setup previews."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from core.settings.widget_family_catalog import get_widget_family_catalog
from rendering.quick.transitions.implementation_registry import iter_quick_transition_implementations


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "ui" / "assets" / "onboarding" / "source"


def test_onboarding_preview_manifest_covers_visible_catalogues() -> None:
    manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["format"] == "png"
    assert {row["family_id"] for row in manifest["widgets"]} == {
        family.family_id for family in get_widget_family_catalog()
    }
    assert {row["transition_id"] for row in manifest["transitions"]} == {
        item.transition_id for item in iter_quick_transition_implementations()
    }
    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors
    assert {row["mode_id"] for row in manifest["visualizer_modes"]} == {
        mode.mode_id for mode in iter_visualizer_mode_descriptors()
    }
    assert manifest["generation"] == {
        "widgets": "hidden Windows-QPA QQuickRenderControl worker",
        "gl": "hidden Windows-QPA QOffscreenSurface worker",
    }


def test_onboarding_preview_assets_match_declared_formats_and_dimensions() -> None:
    from PIL import Image

    manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
    for rows, expected in ((manifest["widgets"], "PNG"), (manifest["transitions"], "PNG"),
                           (manifest["visualizer_modes"], "PNG")):
        for row in rows:
            path = ASSETS / row["path"]
            assert path.is_file() and path.stat().st_size > 0
            with Image.open(path) as image:
                assert image.format == expected
                assert list(image.size) == row["size"]
    for row in manifest["transitions"]:
        # Strips are unlabelled frames side by side; Settings paints the labels.
        frame_width, frame_height = row["frame_size"]
        assert row["size"] == [frame_width * len(row["progress"]), frame_height]
    generated = [*ASSETS.glob("widget_*.png"), *ASSETS.glob("transition_*.png"), *ASSETS.glob("visualizer_*.png")]
    total = sum(path.stat().st_size for path in generated)
    assert total <= 32 * 1024 * 1024
    assert manifest["total_bytes"] == total
    # Lossless only: no stale lossy files are left to ship.
    assert not list(ASSETS.glob("*.jpg"))


def test_default_foundry_dispatches_isolated_qpa_workers(monkeypatch, tmp_path) -> None:
    from tools import onboarding_preview_foundry

    calls = []

    def worker(kind, output, audit_log):
        calls.append((kind, output, audit_log))

    def manifest(output):
        payload = {"format": "png", "widgets": [], "transitions": []}
        (output / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr(onboarding_preview_foundry, "_run_foundry_worker", worker)
    monkeypatch.setattr(onboarding_preview_foundry, "_write_manifest", manifest)
    result = onboarding_preview_foundry.build(tmp_path / "published")

    assert [call[0] for call in calls] == ["widgets", "gl"]
    assert calls[0][1] == calls[1][1]
    assert calls[0][2] == calls[1][2]
    assert result["format"] == "png"
    assert (tmp_path / "published" / "manifest.json").is_file()


def test_workers_use_hidden_windows_gl_never_offscreen_qpa(monkeypatch, tmp_path) -> None:
    """Offscreen QPA has no GL, so it would silently drop logos and card shadows."""

    from types import SimpleNamespace
    from tools import onboarding_preview_foundry

    environments = []

    def run(*_args, **kwargs):
        environments.append(kwargs["env"])
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(onboarding_preview_foundry.subprocess, "run", run)
    audit = tmp_path / "audit.jsonl"
    onboarding_preview_foundry._run_foundry_worker("widgets", tmp_path, audit)
    onboarding_preview_foundry._run_foundry_worker("gl", tmp_path, audit)

    for environment in environments:
        assert "QT_QPA_PLATFORM" not in environment
        assert "QSG_RHI_BACKEND" not in environment


def test_swallowed_network_and_credential_attempts_fail_worker(tmp_path) -> None:
    script = ROOT / "tools" / "onboarding_preview_foundry.py"
    for probe, category in (
        ("swallowed-network", "network"),
        ("swallowed-credential", "credential"),
    ):
        audit = tmp_path / f"{probe}.jsonl"
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "--guard-probe",
                probe,
                "--audit-log",
                str(audit),
            ],
            cwd=ROOT,
            env=dict(os.environ),
            text=True,
            capture_output=True,
            check=False,
        )
        assert completed.returncode != 0
        attempts = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
        assert attempts and attempts[0]["category"] == category


def test_guard_install_does_not_eagerly_import_credential_owners(tmp_path) -> None:
    audit = tmp_path / "import-audit.jsonl"
    code = (
        "import sys; from pathlib import Path; "
        "from tools.onboarding_preview_foundry import _install_authoring_guards; "
        "names=('core.windows.dpapi','core.steam.credentials','core.gmail.gmail_bootstrap'); "
        "assert not any(name in sys.modules for name in names); "
        f"_install_authoring_guards(Path({str(audit)!r})); "
        "assert not any(name in sys.modules for name in names); "
        "import core.steam.friend_pulse; "
        "assert 'core.gmail.gmail_bootstrap' not in sys.modules"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=dict(os.environ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert not audit.exists()


def test_spectrum_preview_resolves_its_curated_preset_through_activation(monkeypatch) -> None:
    """With no explicit settings the foundry reads the curated preset through the production activation.

    Which preset ships first, and its values, are authored content: only the route is asserted.
    """

    from core.settings import visualizer_presets
    from core.settings.models import SpotifyVisualizerSettings
    from tools import onboarding_preview_foundry

    activations = []
    production_activation = visualizer_presets.resolve_visualizer_activation_payload

    def recording_activation(*args, **kwargs):
        activation = production_activation(*args, **kwargs)
        activations.append(activation)
        return activation

    monkeypatch.setattr(visualizer_presets, "resolve_visualizer_activation_payload", recording_activation)
    snapshot = onboarding_preview_foundry._build_spectrum_preview_snapshot(width=680, height=360)

    assert len(activations) == 1 and activations[0].mode == "spectrum"
    assert not visualizer_presets.get_presets("spectrum")[activations[0].preset_index].is_custom
    model = SpotifyVisualizerSettings.from_mapping(activations[0].resolved_config, apply_preset_overlay=False)
    assert snapshot.logical.mode_id == "spectrum"
    assert snapshot.logical.common.bar_count == model.resolve_bar_count("spectrum")


def test_spectrum_preview_crosses_the_logical_capture_seam_with_its_settings(monkeypatch) -> None:
    """The onboarding still must cross the real Spectrum frame-capture seam.

    Test-owned frozen settings (never the mutable curated preset) decide the expected styling.
    """

    from core.settings.models import SpotifyVisualizerSettings
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    from tools import onboarding_preview_foundry
    from widgets.spotify_visualizer import logical_frame_capture

    # Test-owned rainbow switches (fill off, border on) so each one is seen to travel independently.
    settings = {**frozen_visualizer_settings("spectrum"), "spectrum_rainbow_enabled": True,
                "spectrum_unique_colors": True, "spectrum_rainbow_fill": False, "spectrum_rainbow_border": True}
    model = SpotifyVisualizerSettings.from_mapping(settings, apply_preset_overlay=False)
    expected_count = model.resolve_bar_count("spectrum")
    expected_fill = tuple(model.resolve_bar_fill_color("spectrum"))
    expected_border = tuple(model.resolve_bar_border_color("spectrum"))
    assert model.resolve_bar_border_opacity("spectrum") == 1.0  # the frozen copy keeps the colour's own alpha
    calls = []
    production_capture = logical_frame_capture.capture_visualizer_logical_frame

    def recording_capture(*args, **kwargs):
        frame = production_capture(*args, **kwargs)
        calls.append(frame)
        return frame

    monkeypatch.setattr(
        logical_frame_capture,
        "capture_visualizer_logical_frame",
        recording_capture,
    )
    snapshot = onboarding_preview_foundry._build_spectrum_preview_snapshot(
        width=680, height=360, settings=settings
    )

    assert len(calls) == 2
    assert snapshot.logical.mode_id == "spectrum"
    assert snapshot.logical.common.bar_count == expected_count
    assert snapshot.logical.common.style["fill_color"] == expected_fill
    assert snapshot.logical.common.style["border_color"] == expected_border
    parameters = snapshot.logical.mode_state.parameters
    assert parameters["rainbow_enabled"] is True
    assert parameters["rainbow_per_bar"] is True
    assert parameters["spectrum_rainbow_fill"] is False
    assert parameters["spectrum_rainbow_border"] is True


def test_regeneration_keeps_an_asset_whose_pixels_only_drift(tmp_path: Path) -> None:
    """Multisampling jitter (a level everywhere, or a few speckled pixels on thin lines) and PNG byte
    differences for identical pixels keep the committed file; a real change rewrites it."""
    import numpy
    from PIL import Image

    from tools.onboarding_preview_foundry import PIXEL_DRIFT_SHARE, PIXEL_DRIFT_TOLERANCE, save_png_stable

    path = tmp_path / "strip.png"
    base = numpy.full((100, 100, 3), 100, dtype=numpy.uint8)
    assert save_png_stable(Image.fromarray(base), path)
    written = path.read_bytes()
    allowed = int(PIXEL_DRIFT_SHARE * 100 * 100)
    jitter = base + PIXEL_DRIFT_TOLERANCE                       # every pixel off by the tolerance
    jitter.reshape(-1, 3)[:allowed] = 140                       # plus a few strongly speckled pixels
    assert not save_png_stable(Image.fromarray(jitter), path)
    assert path.read_bytes() == written
    changed = base.copy()
    changed.reshape(-1, 3)[:allowed + 1] = 140                  # one speckle more than allowed
    assert save_png_stable(Image.fromarray(changed), path)
    assert save_png_stable(Image.fromarray(numpy.zeros((100, 101, 3), dtype=numpy.uint8)), path)  # resized


def test_foundry_selects_a_preview_preset_by_its_settings_number(monkeypatch) -> None:
    """``--visualizer-preset MODE=N``: N is the 1-based number Settings shows; past the catalogue is loud."""
    import pytest

    from core.settings import visualizer_presets as vp
    from tools import onboarding_preview_foundry as foundry

    assert foundry.parse_preset_numbers(["spectrum=3", " bubble = 1 "]) == {"spectrum": 3, "bubble": 1}
    for bad in ("spectrum", "spectrum=0", "=2", "spectrum=x"):
        with pytest.raises(ValueError):
            foundry.parse_preset_numbers([bad])
    mode = "spectrum"
    last = vp.get_custom_preset_index(mode)  # the trailing Custom position: one past the authored presets
    monkeypatch.setattr(foundry, "_PRESET_NUMBERS", {mode: last})
    assert foundry._preview_preset_index(mode) == last - 1
    monkeypatch.setattr(foundry, "_PRESET_NUMBERS", {mode: last + 1})
    with pytest.raises(LookupError):
        foundry._preview_preset_index(mode)


def test_foundry_photo_backdrop_is_the_photo_under_the_card_surface(tmp_path) -> None:
    """``--photo``: the wallpaper cover-cropped to the card, under the theme's card surface, fully opaque."""
    from PIL import Image

    from tools.onboarding_preview_foundry import photo_card_backdrop
    from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME

    photo = tmp_path / "wall.png"
    Image.new("RGB", (400, 100), (250, 250, 250)).save(photo)  # wider than the card: cropped, never stretched
    backdrop = photo_card_backdrop(photo, (120, 80))
    assert backdrop.size == (120, 80)
    red, green, blue, alpha = backdrop.getpixel((60, 40))
    assert alpha == 255
    surface = DEFAULT_DARK_WIDGET_THEME.color("card.background").as_tuple()
    expected = round(250 + (surface[0] - 250) * surface[3] / 255)
    assert abs(red - expected) <= 1
