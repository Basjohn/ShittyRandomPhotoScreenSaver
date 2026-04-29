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
