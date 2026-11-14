"""The application icon's one owner (``ui/app_icon.py``) finds ``SRPSS.ico`` in every shipped layout.

Simulated frozen layouts (Nuitka 4.2 ``--file-reference-choice=runtime``: every compiled module's ``__file__`` is
relative to the running executable's folder):

* onefile (``SRPSS.scr``): the launcher sits in ``System32`` with nothing beside it; the payload, ``SRPSS.ico``
  included, is extracted to ``{CACHE_DIR}/SRPSS/onefile/<identity>/``, which holds the running ``SRPSS.exe`` and is
  the package root;
* onedir (the Media Center): the executable, ``SRPSS.ico`` and the package root are one folder.

A file that exists but does not decode is never taken (the old lookups took any existing file).
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pytest

from ui import app_icon

REPO = Path(__file__).resolve().parents[1]
ICON = REPO / app_icon.ICON_FILE_NAME


def _onefile_layout(root: Path) -> dict:
    launcher = root / "Windows" / "System32" / "SRPSS.scr"
    launcher.parent.mkdir(parents=True)
    launcher.write_bytes(b"MZ")
    extraction = root / "AppData" / "Local" / "SRPSS" / "onefile" / "a765cafa83d50bcd6feb"
    (extraction / "ui" / "studio").mkdir(parents=True)
    (extraction / "SRPSS.exe").write_bytes(b"MZ")
    shutil.copyfile(ICON, extraction / app_icon.ICON_FILE_NAME)
    return {"package_root": extraction, "executable": str(extraction / "SRPSS.exe"), "launcher": str(launcher),
            "expected": extraction / app_icon.ICON_FILE_NAME}


def _onedir_layout(root: Path) -> dict:
    dist = root / "Program Files" / "SRPSS Media Center"
    (dist / "ui" / "studio").mkdir(parents=True)
    (dist / "SRPSS_Media_Center.exe").write_bytes(b"MZ")
    shutil.copyfile(ICON, dist / app_icon.ICON_FILE_NAME)
    exe = str(dist / "SRPSS_Media_Center.exe")
    return {"package_root": dist, "executable": exe, "launcher": exe, "expected": dist / app_icon.ICON_FILE_NAME}


@pytest.mark.parametrize("layout", [_onefile_layout, _onedir_layout], ids=["onefile", "onedir"])
def test_icon_path_resolves_in_frozen_layouts(layout, tmp_path, qt_app):
    case = layout(tmp_path)
    candidates = app_icon.icon_path_candidates(package_root=case["package_root"], executable=case["executable"],
                                               launcher=case["launcher"])
    assert app_icon.application_icon_path(candidates) == case["expected"]


def test_icon_path_resolves_in_source(qt_app):
    assert app_icon.application_icon_path(app_icon.icon_path_candidates(executable="", launcher="")) == ICON


def test_a_file_that_does_not_decode_is_skipped(tmp_path, qt_app):
    """Negative control: an existing but unreadable ``SRPSS.ico`` at the package root is passed over for the next
    candidate (the old ``exists()``/``is_file()`` lookups set it as an empty icon)."""
    case = _onefile_layout(tmp_path)
    broken_root = tmp_path / "broken"
    broken_root.mkdir()
    (broken_root / app_icon.ICON_FILE_NAME).write_bytes(b"not an icon")
    candidates = app_icon.icon_path_candidates(package_root=broken_root, executable=case["executable"],
                                               launcher=case["launcher"])
    assert candidates[0] == broken_root / app_icon.ICON_FILE_NAME
    assert app_icon.application_icon_path(candidates) == case["expected"]
    assert app_icon.application_icon_path([broken_root / app_icon.ICON_FILE_NAME]) is None


@pytest.mark.skipif(sys.platform != "win32", reason="executable icon resources are a Windows fallback")
def test_executable_icon_resource_fallback(qt_app):
    icon = app_icon._executable_resource_icon(sys.executable)
    assert not icon.isNull()
    assert icon.availableSizes()


def test_main_and_studio_read_the_one_owner():
    """No product module but the owner names the icon file; ``main.py`` and the Studio window read the owner."""
    pattern = re.compile(r"SRPSS\.ico")
    product = [REPO / "main.py", REPO / "main_mc.py", REPO / "main_diagnostic.py"]
    for folder in ("core", "engine", "rendering", "ui", "widgets"):
        product.extend((REPO / folder).rglob("*.py"))
    owner = (REPO / "ui" / "app_icon.py").resolve()
    naming = [str(p.relative_to(REPO)) for p in product
              if p.resolve() != owner and pattern.search(p.read_text(encoding="utf-8", errors="replace"))]
    assert naming == []
    assert "from ui.app_icon import" in (REPO / "main.py").read_text(encoding="utf-8")
    assert "apply_application_icon(window)" in (REPO / "ui" / "studio" / "surface.py").read_text(encoding="utf-8")
