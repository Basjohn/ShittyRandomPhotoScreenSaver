"""Gmail asset and packaging guardrails."""
from __future__ import annotations

from pathlib import Path

from widgets.gmail_widget import GMAIL_ACTION_ICON_PATHS, GMAIL_IMAGE_ASSETS


ROOT = Path(__file__).resolve().parents[1]


def test_gmail_required_image_assets_exist():
    """Every Gmail image referenced by the widget should be present in the repo."""
    missing = [
        asset_path
        for asset_path in GMAIL_IMAGE_ASSETS
        if not (ROOT / asset_path).is_file()
    ]

    assert missing == []


def test_gmail_asset_resolver_finds_logo_without_repo_cwd(monkeypatch, tmp_path):
    """Standard onefile/SCR builds should not depend only on the process cwd."""
    from widgets.gmail_widget import _gmail_asset_path

    monkeypatch.chdir(tmp_path)
    assert _gmail_asset_path("images/google-gmail.png").is_file()


def test_gmail_envelope_png_sources_are_high_resolution(qt_app):
    """Envelope PNGs should be clean source assets, not tiny jagged 16px icons."""
    from PySide6.QtGui import QImage

    for asset_path in ("images/gmail-envelope.png", "images/gmail-read.png"):
        image = QImage(str(ROOT / asset_path))
        assert not image.isNull()
        assert image.width() >= 64
        assert image.height() >= 64
        assert image.hasAlphaChannel()


def test_gmail_unread_envelope_is_inverse_white_asset():
    """Unread should be the white filled inverse; read should remain the plain black envelope."""
    from PIL import Image

    def _average_visible_luma(asset_path: str) -> float:
        image = Image.open(ROOT / asset_path).convert("RGBA")
        pixels = [px for px in image.getdata() if px[3] > 16]
        return sum((px[0] + px[1] + px[2]) / 3 for px in pixels) / len(pixels)

    unread_luma = _average_visible_luma("images/gmail-envelope.png")
    read_luma = _average_visible_luma("images/gmail-read.png")

    assert unread_luma > read_luma + 40


def test_gmail_action_icon_paths_are_covered_by_asset_manifest():
    """The menu icon loader should only reference tracked Gmail asset paths."""
    manifest = set(GMAIL_IMAGE_ASSETS)
    referenced = {
        path
        for path_options in GMAIL_ACTION_ICON_PATHS.values()
        for path in path_options
    }

    assert referenced <= manifest


def test_nuitka_builds_include_images_directory():
    """Normal and MC Nuitka builds must package image assets used by Gmail."""
    scripts = (
        ROOT / "scripts" / "build_nuitka.ps1",
        ROOT / "scripts" / "build_nuitka_mc_onedir.ps1",
    )

    for script in scripts:
        text = script.read_text(encoding="utf-8")
        assert "--include-data-dir=images=images" in text


def test_nuitka_builds_include_ui_tabs_package_for_descriptor_loaded_sections():
    """Frozen builds must include dynamically imported WidgetsTab section modules."""
    scripts = (
        ROOT / "scripts" / "build_nuitka.ps1",
        ROOT / "scripts" / "build_nuitka_mc_onedir.ps1",
    )

    for script in scripts:
        text = script.read_text(encoding="utf-8")
        assert "--include-package=ui.tabs" in text


def test_builds_package_gmail_notification_sound_and_qt_multimedia():
    """Frozen builds need the default sound file and Qt multimedia plugins."""
    scripts = (
        ROOT / "scripts" / "build_nuitka.ps1",
        ROOT / "scripts" / "build_nuitka_mc_onedir.ps1",
    )

    for script in scripts:
        text = script.read_text(encoding="utf-8")
        assert "--include-data-files=resources/tutuogg.ogg=resources/tutuogg.ogg" in text
        assert "--include-data-dir=resources=resources" not in text
        assert "client_secrets.json" not in text
        assert "--include-qt-plugins=multimedia" in text
        assert "--include-module=PySide6.QtMultimedia" in text


def test_installers_ship_default_gmail_notification_sound_to_programdata():
    """Both installers should place the default OGG in the shared ProgramData sound folder."""
    scripts = (
        ROOT / "scripts" / "SRPSS_Installer.iss",
        ROOT / "scripts" / "SRPSS_MediaCenter_Installer.iss",
    )

    for script in scripts:
        text = script.read_text(encoding="utf-8")
        assert "tutuogg.ogg" in text
        assert r"{commonappdata}\SRPSS\sounds" in text
