"""Phase A1 contracts for the production Qt Quick process bootstrap."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from rendering.quick import bootstrap


ROOT = Path(__file__).resolve().parents[1]


def test_environment_bootstrap_forces_threaded_loop_and_real_qml_root(monkeypatch):
    existing = str(ROOT / "existing-qml-import")
    monkeypatch.setenv("QSG_RENDER_LOOP", "basic")
    monkeypatch.setenv("QML_IMPORT_PATH", existing)

    qml_root = bootstrap.configure_quick_environment()

    assert os.environ["QSG_RENDER_LOOP"] == "threaded"
    assert qml_root == ROOT / "rendering" / "quick" / "qml"
    assert qml_root.is_dir()
    assert (qml_root / "qmldir").is_file()
    assert os.environ["QML_IMPORT_PATH"].split(os.pathsep) == [
        str(qml_root),
        existing,
    ]


def test_environment_bootstrap_is_idempotent(monkeypatch):
    monkeypatch.delenv("QML_IMPORT_PATH", raising=False)

    first = bootstrap.configure_quick_environment()
    second = bootstrap.configure_quick_environment()

    assert first == second
    assert os.environ["QML_IMPORT_PATH"].split(os.pathsep) == [str(first)]


def test_main_bootstraps_environment_before_qt_and_graphics_before_application():
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert source.index("configure_quick_environment()") < source.index(
        "from PySide6.QtWidgets import QApplication"
    )
    assert source.index("configure_quick_graphics(reason=\"startup\")") < source.index(
        "app = QApplication(sys.argv)"
    )


def test_graphics_bootstrap_selects_proven_opengl_profile_in_clean_process():
    script = r'''
import json
import os

from rendering.quick.bootstrap import configure_quick_graphics

state = configure_quick_graphics(reason="a1-subprocess")

from PySide6.QtGui import QSurfaceFormat
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

fmt = QSurfaceFormat.defaultFormat()
print(json.dumps({
    "render_loop": os.environ.get("QSG_RENDER_LOOP"),
    "graphics_api": QQuickWindow.graphicsApi().name,
    "major": fmt.majorVersion(),
    "minor": fmt.minorVersion(),
    "profile": fmt.profile().name,
    "renderable": fmt.renderableType().name,
    "swap_interval": fmt.swapInterval(),
    "qml_root": str(state.qml_root),
}))
'''
    env = os.environ.copy()
    env["QSG_RENDER_LOOP"] = "basic"
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    import json

    report = json.loads(completed.stdout.strip().splitlines()[-1])
    assert report == {
        "render_loop": "threaded",
        "graphics_api": "OpenGL",
        "major": 4,
        "minor": 1,
        "profile": "CoreProfile",
        "renderable": "OpenGL",
        "swap_interval": 0,
        "qml_root": str(ROOT / "rendering" / "quick" / "qml"),
    }


def test_quick_package_contains_no_prohibited_presenter_or_fallback():
    package_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "rendering" / "quick").rglob("*.py")
    )
    for forbidden in (
        "QQuickWidget",
        "QRhiWidget",
        "DisplayWidgetCompatibilityFacade",
    ):
        assert forbidden not in package_source
