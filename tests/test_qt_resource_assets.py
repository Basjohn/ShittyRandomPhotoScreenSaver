"""Focused ownership bars for immutable Qt resources and lazy Guided Setup art."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

from PySide6.QtCore import QFile, QIODevice
from PySide6.QtGui import QImage

from ui.resources.assets import resource_path, resource_url
from ui.resources.onboarding_assets import onboarding_resource_path


ROOT = Path(__file__).resolve().parents[1]
_HASHES = json.loads(
    (ROOT / "tests" / "fixtures" / "qrc_assets" / "immutable_sha256.json").read_text(
        encoding="utf-8"
    )
)


def _read(path: str) -> bytes:
    source = QFile(path)
    assert source.open(QIODevice.OpenModeFlag.ReadOnly), path
    try:
        return bytes(source.readAll())
    finally:
        source.close()


def test_core_qrc_owns_representative_runtime_assets_without_loose_paths() -> None:
    manifest = ET.parse(ROOT / "ui" / "resources" / "assets.qrc")
    aliases = {node.attrib["alias"] for node in manifest.findall(".//file")}
    assert {
        "fonts/Jost-Regular.ttf",
        "ui/icons/circle_checkbox_checked.svg",
        "branding/logos/Steam_Logo_Cropped.png",
        "branding/about/Logo.png",
        "weather/presented/clear-day.png",
        "widgets/system/system_stats_tools.svg",
    } <= aliases
    assert all(not Path(node.text or "").as_posix().startswith("../../images") for node in manifest.findall(".//file"))
    for name in (
        "fonts/Jost-Regular.ttf",
        "branding/logos/Steam_Logo_Cropped.png",
        "weather/presented/clear-day.png",
    ):
        assert _read(resource_path(name))
        assert resource_url(name) == f"qrc:/srpss/{name}"


def test_every_qrc_entry_matches_its_canonical_source_and_locked_image_bytes() -> None:
    """A QRC rebuild cannot silently alter any moved immutable image or font."""

    entries_seen: set[str] = set()
    for manifest_name, resolve_resource in (
        ("assets.qrc", resource_path),
        ("onboarding_assets.qrc", onboarding_resource_path),
    ):
        manifest = ROOT / "ui" / "resources" / manifest_name
        for node in ET.parse(manifest).findall(".//file"):
            alias = node.attrib["alias"]
            source = (manifest.parent / (node.text or "")).resolve()
            assert source.is_relative_to(ROOT / "ui" / "assets"), source
            expected_key = f"{manifest_name}:{alias}"
            expected_hash = _HASHES[expected_key]
            source_bytes = source.read_bytes()
            resource_bytes = _read(resolve_resource(alias))
            assert hashlib.sha256(source_bytes).hexdigest() == expected_hash
            assert hashlib.sha256(resource_bytes).hexdigest() == expected_hash
            entries_seen.add(expected_key)

            if source.suffix.lower() == ".png":
                source_image = QImage(str(source))
                resource_image = QImage.fromData(resource_bytes)
                assert not source_image.isNull() and not resource_image.isNull(), source
                assert resource_image.size() == source_image.size(), source
                assert resource_image.hasAlphaChannel() == source_image.hasAlphaChannel(), source

    assert entries_seen == set(_HASHES)


def test_onboarding_pack_is_not_imported_until_an_asset_is_requested() -> None:
    script = """
import sys
from ui.onboarding import common
assert 'ui.resources.onboarding_assets_rc' not in sys.modules
path = common.asset_path('onboarding/widget_weather.png')
assert path == ':/srpss/onboarding/widget_weather.png'
assert 'ui.resources.onboarding_assets_rc' in sys.modules
first = sys.modules['ui.resources.onboarding_assets_rc']
assert common.asset_path('onboarding/widget_weather.png')
assert sys.modules['ui.resources.onboarding_assets_rc'] is first
"""
    completed = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_runtime_resource_lookup_does_not_import_the_settings_dialog() -> None:
    script = """
import sys
from ui.resources.assets import resource_path
assert resource_path('branding/logos/Steam_Logo_Cropped.png')
assert 'ui.settings_dialog' not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_resource_helpers_reject_path_traversal() -> None:
    import pytest

    with pytest.raises(ValueError):
        resource_path("../client_secrets.json")
