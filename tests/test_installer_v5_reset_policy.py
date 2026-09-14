"""Post-5.0.0 installer migration-reset policy.

The one-release 5.0.0 default-on reset window is over. Current installers keep
the surgical reset available as an explicit recovery action but default it OFF.
A selected reset must still remove both the JSON snapshot and matching pre-JSON
QSettings registry tree so legacy state cannot immediately repopulate the profile.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _text(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def _reset_task_line(text: str) -> str:
    return next(
        line for line in text.splitlines()
        if line.startswith('Name: "resetsettings";')
    )


def test_post_migration_installers_keep_reset_available_but_opt_in() -> None:
    # EXACT-VALUE INVARIANT: the temporary 5.0.0 default-on migration reset has
    # expired. Current installers must require an explicit reset choice; update
    # this only for another deliberately approved migration window.
    for name in (
        "SRPSS_Installer.iss",
        "SRPSS_MediaCenter_Installer.iss",
        "SRPSS_Diagnostic_Installer.iss",
    ):
        text = _text(name)
        assert "Flags: unchecked" in _reset_task_line(text)

    for name in ("SRPSS_Installer.iss", "SRPSS_MediaCenter_Installer.iss"):
        assert "5.0.0 migration reset remains available manually, but defaults OFF" in _text(name)

def test_selected_reset_clears_json_and_matching_legacy_qsettings_tree() -> None:
    standard = _text("SRPSS_Installer.iss")
    assert 'Name: "{userappdata}\\SRPSS\\settings_v2.json"; Tasks: resetsettings' in standard
    assert (
        'Subkey: "Software\\ShittyRandomPhotoScreenSaver\\Screensaver"; '
        'Flags: deletekey; Tasks: resetsettings'
    ) in standard

    mc = _text("SRPSS_MediaCenter_Installer.iss")
    assert 'Name: "{userappdata}\\SRPSS_MC\\settings_v2.json"; Tasks: resetsettings' in mc
    assert (
        'Subkey: "Software\\ShittyRandomPhotoScreenSaver\\Screensaver_MC"; '
        'Flags: deletekey; Tasks: resetsettings'
    ) in mc

    diagnostic = _text("SRPSS_Diagnostic_Installer.iss")
    assert 'Name: "{userappdata}\\SRPSS\\settings_v2.json"; Tasks: resetsettings' in diagnostic
    assert (
        'Subkey: "Software\\ShittyRandomPhotoScreenSaver\\Screensaver"; '
        'Flags: deletekey; Tasks: resetsettings'
    ) in diagnostic
