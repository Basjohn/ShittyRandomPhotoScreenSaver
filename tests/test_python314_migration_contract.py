"""Static migration-owner tests; actual Windows wheel/GL acceptance is separate."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_one_interpreter_and_compiler_authority() -> None:
    for path in (
        "scripts/venv/build_nuitka.ps1",
        "scripts/venv/build_nuitka_mc_onedir.ps1",
        "scripts/venv/build_reddit_helper.ps1",
    ):
        text = source(path)
        assert '3.14' in text and 'sys._is_gil_enabled()' in text
        assert '3.11' not in text
        assert 'Resolve-BasePython' in text
        assert 'python314_runtime.ps1' in text
    for path in (
        "scripts/venv/build_nuitka.ps1",
        "scripts/venv/build_nuitka_mc_onedir.ps1",
        "scripts/build_qtquick_smoke.ps1",
    ):
        text = source(path)
        assert '--msvc=latest' in text
        assert '--mingw64' not in text
    for legacy, target in (
        ("scripts/build_nuitka.ps1", "venv\\build_nuitka.ps1"),
        ("scripts/build_nuitka_mc_onedir.ps1", "venv\\build_nuitka_mc_onedir.ps1"),
        ("scripts/build_reddit_helper.ps1", "venv\\build_reddit_helper.ps1"),
    ):
        text = source(legacy)
        assert target in text
        assert '& $worker' in text
        assert ' -m nuitka' not in text


def test_pinned_wheels_and_native_dependency_probe():
    req = source('requirements.txt')
    assert 'threadpoolctl==3.6.0' in req
    assert 'from threadpoolctl import threadpool_info' in source('tests/test_native_thread_pools.py')
    # The pins are exact (==) and the probe checks the pins themselves, so a version bump edits requirements.txt only.
    from tools.python314_probe import pinned_versions
    pins = pinned_versions()
    for name in ('PySide6', 'PySide6_Addons', 'PySide6_Essentials', 'shiboken6', 'numpy', 'Nuitka', 'PyAudioWPatch', 'psutil'):
        assert f'{name}=={pins[name]}' in req
    assert len({pins[name] for name in ('PySide6', 'PySide6_Addons', 'PySide6_Essentials', 'shiboken6')}) == 1
    probe = source('tools/python314_probe.py')
    assert 'pinned_versions()' in probe and '"6.' not in probe
    for token in ('QtCore.qVersion()', 'sys._is_gil_enabled()', 'struct.pack(', 'winrt.windows.media.control'):
        assert token in probe


def test_destructive_cutover_has_no_backup_or_global_fallback():
    script = source('scripts/cutover_python314.ps1')
    assert 'Remove-Item -LiteralPath $VenvPath -Recurse -Force' in script
    assert 'pip check' in script and 'python314_probe.py' in script
    assert 'python314_runtime.ps1' in script and 'Resolve-BasePython' in script
    assert 'C:\\Python314\\python.exe' not in script
    assert 'Python.Python.3.11' in script


def test_python_install_manager_locator_is_shared_by_workers():
    locator = source('scripts/python314_runtime.ps1')
    assert 'Python\\pythoncore-3.14-64\\python.exe' in locator
    assert 'pymanager' in locator and 'py' in locator
    assert 'sys._is_gil_enabled()' in locator
    assert "Resolve-BasePython" in source('scripts/cutover_python314.ps1')

def test_foundry_and_build_runner_do_not_launch_global_python():
    runner = source('tools/build_runner.py')
    assert 'return repo_root / ".venv" / "Scripts" / "python.exe"' in runner
    assert 'shutil.which("python")' not in runner
    foundry = source('tools/godzip_foundry.py')
    assert 'CHUNKED_SUITE_COMMAND = r".\\.venv\\Scripts\\python.exe' in foundry
    assert 'command = [str(python_exe), str(script)]' in foundry


def test_normal_and_venv_mode_temp_build_paths_still_distinct():
    for parent, worker in (('scripts/build_nuitka.ps1', 'scripts/venv/build_nuitka.ps1'),
                           ('scripts/build_nuitka_mc_onedir.ps1', 'scripts/venv/build_nuitka_mc_onedir.ps1'),
                           ('scripts/build_reddit_helper.ps1', 'scripts/venv/build_reddit_helper.ps1')):
        assert '-BuildWorkspace normal' in source(parent)
        assert '$BuildWorkspace = "venv"' in source(worker)
