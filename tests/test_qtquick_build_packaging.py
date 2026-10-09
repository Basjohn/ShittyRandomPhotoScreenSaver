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
CANONICAL_PRODUCT_WORKERS = (
    ROOT / "scripts" / "venv" / "build_nuitka.ps1",
    ROOT / "scripts" / "venv" / "build_nuitka_mc_onedir.ps1",
)


def test_every_product_nuitka_worker_packages_the_quick_qml_contract():
    # The legacy entry points are delegates. The canonical workers own the
    # actual compiler argv, so verify the effective packaging authority.
    for worker in CANONICAL_PRODUCT_WORKERS:
        source = worker.read_text(encoding="utf-8")
        assert (
            "--include-data-dir=rendering/quick/qml=rendering/quick/qml" in source
        ), worker
        assert (
            "--include-data-dir=widgets/spotify_visualizer/shaders="
            "widgets/spotify_visualizer/shaders" in source
        ), worker
        assert '"--include-package=rendering.quick"' in source, worker
        assert '"--include-qt-plugins=qml"' in source, worker
        assert '"--include-qt-plugins=multimedia"' in source, worker
        assert '"--include-module=PySide6.QtQuick"' in source, worker
        assert '"--include-module=PySide6.QtQml"' in source, worker
        assert "--include-qt-plugins=all" not in source, worker

    for old_name, worker_name in (
        ("build_nuitka.ps1", "build_nuitka.ps1"),
        ("build_nuitka_mc_onedir.ps1", "build_nuitka_mc_onedir.ps1"),
    ):
        wrapper = (ROOT / "scripts" / old_name).read_text(encoding="utf-8")
        assert f"'venv\\{worker_name}'" in wrapper
        assert "& $worker" in wrapper


def test_work_in_progress_usu_assets_stay_out_of_resource_packs_and_frozen_builds():
    """``assets/usu`` (rig sources and renders, ~130 MB) is nowhere near product use: no QRC
    manifest lists it, no build or installer script ships it (nor ``assets`` wholesale), and no
    product code imports it, so Nuitka never follows it."""
    import re
    import subprocess

    for manifest in (ROOT / "ui" / "resources").glob("*.qrc"):
        assert "assets/usu" not in manifest.read_text(encoding="utf-8").replace("\\", "/"), manifest
    scripts = [*PRODUCT_WORKERS, ROOT / "scripts" / "venv" / "build_nuitka_diagnostic.ps1",
               ROOT / "tools" / "build_layout.ps1", *(ROOT / "scripts").glob("*.iss")]
    for script in scripts:
        source = script.read_text(encoding="utf-8").replace("\\", "/").lower()
        assert "usu" not in re.findall(r"[a-z_]+", source), script
        assert not re.search(r"include-data-dir=assets(/|=)", source), script
        assert not re.search(r'source:\s*"?[^"\n]*assets/?(\*|")', source), script
    tracked = subprocess.run(["git", "grep", "-l", "-E", r"(from|import) assets\.usu", "--", "*.py"],
                             cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert [path for path in tracked if not path.startswith("assets/usu/")] == []


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
    visualizer_qml_path = (
        ROOT / "rendering" / "quick" / "qml" / "VisualizerPresentation.qml"
    )
    source = qml_path.read_text(encoding="utf-8")
    visualizer_source = visualizer_qml_path.read_text(encoding="utf-8")
    smoke = (ROOT / "tools" / "qtquick_render_node_smoke.py").read_text(
        encoding="utf-8"
    )
    scene_owner = (
        ROOT / "rendering" / "quick" / "scene_controller.py"
    ).read_text(encoding="utf-8")

    assert "import QtQuick" in source
    assert 'objectName: "displaySceneRoot"' in source
    assert 'source: "VisualizerPresentation.qml"' in source
    assert "active: false" in source
    assert "import QtQuick.Effects" in visualizer_source
    assert 'objectName: "visualizerPresentationRoot"' in visualizer_source
    assert 'objectName: "visualizerContentHost"' in visualizer_source
    assert "QuickSceneFactory(self)" in smoke
    assert "QQmlEngine" in scene_owner
    assert "QQmlComponent" in scene_owner
    assert "quick_qml_root()" in scene_owner
    assert '"DisplayScene.qml"' in scene_owner
