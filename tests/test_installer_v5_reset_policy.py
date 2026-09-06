"""5.0.0 installer migration-reset policy.

The v5 settings/runtime migration is intentionally unusual: Standard and MC
installers default the reset task ON for 5.0.0 only.  A selected reset must
remove both the JSON snapshot and the pre-JSON QSettings registry tree, or the
first v5 launch can simply re-import the legacy state that the installer meant
to discard.  Diagnostic remains opt-in because it consumes the ordinary SRPSS
profile deliberately.
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


def test_v5_standard_and_mc_reset_are_default_checked_only_by_explicit_policy() -> None:
    for name in ("SRPSS_Installer.iss", "SRPSS_MediaCenter_Installer.iss"):
        text = _text(name)
        task = _reset_task_line(text)
        assert "Flags: unchecked" not in task
        assert "5.0.0 ONLY:" in text
        assert "Reconsider/remove the default-on policy after the 5.0.0 migration release" in text

    diagnostic = _text("SRPSS_Diagnostic_Installer.iss")
    assert "Flags: unchecked" in _reset_task_line(diagnostic)


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
