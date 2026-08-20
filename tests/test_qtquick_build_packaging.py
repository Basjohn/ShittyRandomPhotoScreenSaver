"""Phase A4 gates for deterministic Qt Quick/QML Nuitka packaging."""

from __future__ import annotations

from pathlib import Path

from tools import build_runner


ROOT = Path(__file__).resolve().parents[1]


PRODUCT_WORKERS = (
    ROOT / "scripts" / "build_nuitka.ps1",
    ROOT / "scripts" / "venv" / "build_nuitka.ps1",
    ROOT / "scripts" / "build_nuitka_mc_onedir.ps1",
    ROOT / "scripts" / "venv" / "build_nuitka_mc_onedir.ps1",
)


def test_every_product_nuitka_worker_packages_the_quick_qml_contract():
    for worker in PRODUCT_WORKERS:
        source = worker.read_text(encoding="utf-8")
        assert (
            "--include-data-dir=rendering/quick/qml=rendering/quick/qml" in source
        ), worker
        assert '"--include-package=rendering.quick"' in source, worker
        assert '"--include-qt-plugins=qml"' in source, worker
        assert '"--include-qt-plugins=multimedia"' in source, worker
        assert '"--include-module=PySide6.QtQuick"' in source, worker
        assert '"--include-module=PySide6.QtQml"' in source, worker
        assert "--include-qt-plugins=all" not in source, worker


def test_diagnostic_build_reuses_the_qml_aware_canonical_worker():
    source = (
        ROOT / "scripts" / "venv" / "build_nuitka_diagnostic.ps1"
    ).read_text(encoding="utf-8")

    assert "$Worker = Join-Path $PSScriptRoot 'build_nuitka.ps1'" in source
    assert "& $Worker" in source


def test_build_runner_dispatches_every_qml_aware_product_worker():
    dispatched = {
        job.script
        for mode in ("normal", "venv")
        for job in build_runner.jobs_for_mode(mode, ROOT)
        if job.key in {"standard", "media_center"}
    }

    assert dispatched == set(PRODUCT_WORKERS)


def test_bounded_compiled_smoke_uses_production_quick_code_and_qml_payload():
    source = (ROOT / "scripts" / "build_qtquick_smoke.ps1").read_text(
        encoding="utf-8"
    )

    assert "tools\\qtquick_render_node_smoke.py" in source
    assert "--include-qt-plugins=qml" in source
    assert "--include-data-dir=rendering/quick/qml=rendering/quick/qml" in source
    assert "--include-package=rendering.quick" in source
    assert "--include-package=OpenGL" in source
    assert "--include-qt-plugins=all" not in source
    assert "build\\a4_qtquick_smoke" in source


def test_display_scene_is_real_packaged_qml_loaded_by_the_runtime_smoke():
    qml_path = ROOT / "rendering" / "quick" / "qml" / "DisplayScene.qml"
    source = qml_path.read_text(encoding="utf-8")
    smoke = (ROOT / "tools" / "qtquick_render_node_smoke.py").read_text(
        encoding="utf-8"
    )
    scene_owner = (
        ROOT / "rendering" / "quick" / "scene_controller.py"
    ).read_text(encoding="utf-8")

    assert "import QtQuick" in source
    assert 'objectName: "displaySceneRoot"' in source
    assert "QuickSceneFactory(self)" in smoke
    assert "QQmlEngine" in scene_owner
    assert "QQmlComponent" in scene_owner
    assert "quick_qml_root()" in scene_owner
    assert '"DisplayScene.qml"' in scene_owner
