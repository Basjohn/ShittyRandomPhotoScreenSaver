"""Frozen installer packaging, presentation, and Build Foundry contracts."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
STANDARD = SCRIPTS / "SRPSS_Installer.iss"
MEDIA_CENTER = SCRIPTS / "SRPSS_MediaCenter_Installer.iss"
BUILD_RUNNER = ROOT / "tools" / "build_runner.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_installers_are_self_contained_no_third_visual_iss() -> None:
    assert not (SCRIPTS / "SRPSS_Installer_Visuals.iss").exists()
    for path in (STANDARD, MEDIA_CENTER):
        source = _text(path)
        assert "SRPSS_Installer_Visuals.iss" not in source
        assert "#if Ver < EncodeVer(6, 7, 2)" in source
        assert "Inno Setup 7.x is supported" in source
        assert "WizardStyle=modern dark includetitlebar hidebevels" in source
        assert "WizardBackColor=#0d181e" in source
        assert "WizardImageFile=" in source
        assert r"WizardSmallImageFile=..\ui\assets\installer\SRPSSWizard.png" in source
        assert "LogoBMP.bmp" not in source


def test_transparent_png_is_compile_time_wizard_brand_asset() -> None:
    wizard_image = ROOT / "ui" / "assets" / "installer" / "SRPSSWizard.png"
    assert wizard_image.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    for path in (STANDARD, MEDIA_CENTER):
        source = _text(path)
        assert r"WizardSmallImageFile=..\ui\assets\installer\SRPSSWizard.png" in source
        assert "InitializeBitmapImageFromIcon" not in source
        assert "ExtractTemporaryFile('SRPSS.ico')" not in source
        assert r"{app}\SRPSS.ico" in source
        icon_line = next(
            line for line in source.splitlines()
            if line.startswith("Source:") and "SRPSS.ico" in line
        )
        assert "noencryption" not in icon_line


def test_installer_compile_cannot_leave_stale_success_artifact() -> None:
    for path, expected_output in (
        (STANDARD, "Setup_SRPSS.exe"),
        (MEDIA_CENTER, "Setup_SRPSS_Media_Center.exe"),
    ):
        source = _text(path)
        assert "DeleteFileNow" in source
        assert expected_output in source
        assert source.index("DeleteFileNow") < source.index("#if Ver < EncodeVer(6, 7, 2)")


def test_standard_installer_does_not_resurrect_qrc_owned_provider_images() -> None:
    source = _text(STANDARD)
    assert "icons8-musicbee-96.png" not in source
    assert r"\images" not in source
    assert "assets.qrc is the runtime authority" in source


def test_media_center_wildcard_is_the_single_app_payload_copy() -> None:
    source = _text(MEDIA_CENTER)
    wildcard = r'Source: "..\release\media_center\*"; DestDir: "{app}"'
    explicit_exe = r'Source: "..\release\media_center\SRPSS_Media_Center.exe"; DestDir: "{app}"'
    assert wildcard in source
    assert explicit_exe not in source


def test_build_foundry_discovers_inno_7_and_keeps_6_compatibility() -> None:
    source = _text(BUILD_RUNNER)
    for token in (
        r"C:\Program Files\Inno Setup 7\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 7\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    ):
        assert token in source
    assert 'os.environ.get("SRPSS_ISCC_PATH")' in source
    assert 'shutil.which("ISCC.exe") or shutil.which("ISCC")' in source
    assert "Supported Inno Setup console compiler (ISCC.exe, 6.7.2+) was not found" in source
    assert '"--version"' in source
    assert "MIN_ISCC_VERSION = (6, 7, 2)" in source
    assert "Could not determine Inno Setup compiler version" in source
    assert "Inno Setup 6 console compiler" not in source


def test_build_foundry_no_longer_requires_retired_bmp_and_clears_stale_installer() -> None:
    source = _text(BUILD_RUNNER)
    build_layout = _text(ROOT / "tools" / "build_layout.ps1")
    assert "LogoBMP.bmp" not in source
    assert "LogoBMP.bmp" not in build_layout
    clear = 'job.expected_artifact.unlink(missing_ok=True)'
    stamp = 'stamp_iss_version(job.script)'
    assert clear in source
    assert source.index(clear) < source.index(stamp)


def test_installers_clean_replace_owned_app_payload_without_destroying_inno_log() -> None:
    for path in (STANDARD, MEDIA_CENTER):
        source = _text(path)
        assert "procedure CleanInstallerOwnedAppPayload();" in source
        assert "IsInstallerBookkeepingFile" in source
        assert "Pos('unins', LowerName) = 1" in source
        assert "DelTree(EntryPath, True, True, True)" in source
        assert "DelTree(EntryPath, False, True, False)" in source
        assert "if CurStep = ssInstall then" in source
        assert "CleanInstallerOwnedAppPayload" in source
        assert "CloseApplications=yes" in source
        assert "CloseApplicationsFilter=*.exe,*.dll,*.scr" in source
        assert "RestartApplications=no" in source


def test_legacy_python_qrc_fallback_is_retired() -> None:
    registration = _text(ROOT / "ui" / "resources" / "registration.py")
    assert "assets_rc" not in registration
    assert "onboarding_assets_rc" not in registration
    assert "importlib" not in registration
    assert "_source_fallback" not in registration

def test_standard_installer_cleans_cached_onefile_payload_without_wildcarding_system32() -> None:
    source = _text(STANDARD)
    onefile_cleanup = 'Type: filesandordirs; Name: "{localappdata}\\SRPSS\\onefile"'

    assert source.count(onefile_cleanup) == 2  # upgrade + uninstall
    assert 'Type: filesandordirs; Name: "{sys}' not in source
    assert 'Name: "{sys}\\*"' not in source
    assert 'Name: "{sys}\\SRPSS.scr"' not in source
    assert 'Source: ".\\..\\release\\screensaver\\SRPSS.scr"; DestDir: "{sys}"' in source

