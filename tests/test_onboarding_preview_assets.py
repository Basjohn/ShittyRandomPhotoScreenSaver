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
ASSETS = ROOT / "images" / "onboarding"


def test_onboarding_preview_manifest_covers_visible_catalogues() -> None:
    manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["format"] == "png"
    assert {row["family_id"] for row in manifest["widgets"]} == {
        family.family_id for family in get_widget_family_catalog()
    }
    assert {row["transition_id"] for row in manifest["transitions"]} == {
        item.transition_id for item in iter_quick_transition_implementations()
    }
    assert manifest["generation"] == {
        "widgets": "hidden Windows-QPA QQuickRenderControl worker",
        "gl": "hidden Windows-QPA QOffscreenSurface worker",
    }


def test_onboarding_preview_assets_are_nonempty_pngs_with_declared_dimensions() -> None:
    from PIL import Image

    manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
    for row in (*manifest["widgets"], *manifest["transitions"]):
        path = ASSETS / row["path"]
        assert path.is_file() and path.stat().st_size > 0
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert list(image.size) == row["size"]
    total = sum(path.stat().st_size for path in ASSETS.glob("*.png"))
    assert total <= 10 * 1024 * 1024
    assert manifest["total_png_bytes"] == total


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


def test_spectrum_preview_uses_canonical_preset_and_logical_capture(monkeypatch) -> None:
    """The onboarding still must cross the real Spectrum frame-capture seam."""

    from core.settings.models import SpotifyVisualizerSettings
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from tools import onboarding_preview_foundry
    from widgets.spotify_visualizer import logical_frame_capture

    activation = resolve_visualizer_activation_payload(
        {"mode": "spectrum", "preset_spectrum": 0}, mode="spectrum"
    )
    model = SpotifyVisualizerSettings.from_mapping(
        activation.resolved_config, apply_preset_overlay=False
    )
    expected_count = model.resolve_bar_count("spectrum")
    expected_fill = tuple(model.resolve_bar_fill_color("spectrum"))
    expected_border = tuple(model.resolve_bar_border_color("spectrum"))
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
        width=680, height=360
    )

    assert len(calls) == 2
    assert snapshot.logical.mode_id == "spectrum"
    assert snapshot.logical.common.bar_count == expected_count
    assert snapshot.logical.common.style["fill_color"] == expected_fill
    assert snapshot.logical.common.style["border_color"] == expected_border
    assert snapshot.logical.mode_state.parameters["rainbow_enabled"] is True
    assert snapshot.logical.mode_state.parameters["rainbow_per_bar"] is True
    assert snapshot.logical.mode_state.parameters["spectrum_rainbow_fill"] is False
    assert snapshot.logical.mode_state.parameters["spectrum_rainbow_border"] is True
