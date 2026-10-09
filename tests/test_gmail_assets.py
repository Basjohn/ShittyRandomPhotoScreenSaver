"""Gmail asset and packaging guardrails."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PySide6.QtCore import QFile, QIODevice
from PySide6.QtGui import QImage

from rendering.quick.widgets.gmail import (
    _GMAIL_ACTION_ICONS,
    _GMAIL_LOGO,
    _GMAIL_READ_ENVELOPE,
    _GMAIL_UNREAD_ENVELOPE,
)


ROOT = Path(__file__).resolve().parents[1]


def _presentation_assets() -> set[str]:
    return {
        _GMAIL_LOGO,
        _GMAIL_READ_ENVELOPE,
        _GMAIL_UNREAD_ENVELOPE,
        *_GMAIL_ACTION_ICONS.values(),
    }


def _qrc_path(asset_url: str) -> str:
    return ":" + asset_url.removeprefix("qrc:")


def test_gmail_required_image_assets_exist():
    """Every immutable Gmail asset is registered in the canonical QRC."""
    missing = []
    for asset_url in _presentation_assets():
        source = QFile(_qrc_path(asset_url))
        if not source.open(QIODevice.OpenModeFlag.ReadOnly):
            missing.append(asset_url)
        else:
            source.close()

    assert missing == []


def test_gmail_asset_resolver_finds_logo_without_repo_cwd(monkeypatch, tmp_path):
    """The retained presenter resolves its logo independently of process cwd."""
    monkeypatch.chdir(tmp_path)
    source = QFile(_qrc_path(_GMAIL_LOGO))
    assert source.open(QIODevice.OpenModeFlag.ReadOnly)
    source.close()


def test_gmail_envelope_png_sources_are_high_resolution(qt_app):
    """Envelope PNGs should be clean source assets, not tiny jagged 16px icons."""
    for asset_url in (_GMAIL_UNREAD_ENVELOPE, _GMAIL_READ_ENVELOPE):
        image = QImage(_qrc_path(asset_url))
        assert not image.isNull()
        assert image.width() >= 64
        assert image.height() >= 64
        assert image.hasAlphaChannel()


def test_gmail_unread_envelope_is_inverse_white_asset():
    """Unread should be the white filled inverse; read should remain the plain black envelope."""
    from PIL import Image

    def _average_visible_luma(asset_url: str) -> float:
        source = QFile(_qrc_path(asset_url))
        assert source.open(QIODevice.OpenModeFlag.ReadOnly)
        try:
            image = Image.open(BytesIO(bytes(source.readAll()))).convert("RGBA")
        finally:
            source.close()
        pixels = [px for px in image.getdata() if px[3] > 16]
        return sum((px[0] + px[1] + px[2]) / 3 for px in pixels) / len(pixels)

    unread_luma = _average_visible_luma(_GMAIL_UNREAD_ENVELOPE)
    read_luma = _average_visible_luma(_GMAIL_READ_ENVELOPE)

    assert unread_luma > read_luma + 40


def test_gmail_action_icon_paths_are_covered_by_asset_manifest():
    """The retained menu icon loader only references tracked Gmail assets."""
    manifest = _presentation_assets()
    referenced = set(_GMAIL_ACTION_ICONS.values())

    assert referenced <= manifest


def test_nuitka_builds_include_binary_qrc_packs():
    """Normal and MC builds ship binary immutable-resource packs as data."""
    scripts = (
        ROOT / "scripts" / "venv" / "build_nuitka.ps1",
        ROOT / "scripts" / "venv" / "build_nuitka_mc_onedir.ps1",
    )

    for script in scripts:
        text = script.read_text(encoding="utf-8")
        assert "--include-data-dir=images=images" not in text
        assert "--include-data-files=ui/resources/assets.rcc=ui/resources/assets.rcc" in text
        assert "--include-data-files=ui/resources/onboarding_assets.rcc=ui/resources/onboarding_assets.rcc" in text


def test_nuitka_builds_include_ui_tabs_package_for_descriptor_loaded_sections():
    """Frozen builds must include dynamically imported WidgetsTab section modules."""
    scripts = (
        ROOT / "scripts" / "venv" / "build_nuitka.ps1",
        ROOT / "scripts" / "venv" / "build_nuitka_mc_onedir.ps1",
    )

    for script in scripts:
        text = script.read_text(encoding="utf-8")
        assert "--include-package=ui.tabs" in text


def test_builds_package_gmail_notification_sound_and_qt_multimedia():
    """Frozen builds need the default sound file and Qt multimedia plugins."""
    scripts = (
        ROOT / "scripts" / "venv" / "build_nuitka.ps1",
        ROOT / "scripts" / "venv" / "build_nuitka_mc_onedir.ps1",
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
