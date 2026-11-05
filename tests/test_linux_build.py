"""The Linux build derives its Nuitka declarations from the Windows build scripts."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import linux_build  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_portable_windows_declarations_reach_linux_without_windows_payload() -> None:
    arguments = linux_build.portable_windows_arguments()
    for required in (
        "--enable-plugin=pyside6",
        "--include-data-dir=presets=presets",
        "--include-data-dir=themes=themes",
        "--include-data-dir=rendering/quick/qml=rendering/quick/qml",
        "--include-data-files=ui/resources/assets.rcc=ui/resources/assets.rcc",
        "--include-package=sounddevice",
        "--noinclude-default-mode=error",
    ):
        assert required in arguments
    lowered = " ".join(arguments).lower()
    for windows_only in ("winrt", "pyaudiowpatch", "--msvc", "--onefile", "--windows-", "$"):
        assert windows_only not in lowered
    assert not any(value.startswith(("--jobs=", "--standalone")) for value in arguments)


def test_qt_size_exclusions_translate_to_shared_objects() -> None:
    arguments = linux_build.qt_prune_arguments()
    assert "--noinclude-data-files=PySide6/qml/QtWebEngine/**" in arguments
    assert "--noinclude-dlls=*Qt6WebEngine*.so*" in arguments
    assert "--nofollow-import-to=pytz" in arguments
    assert not any(value.endswith(".dll") for value in arguments)


def test_build_entry_points_and_workflow_reference_existing_files() -> None:
    workflow = (ROOT / ".github" / "workflows" / "linux-build.yml").read_text(encoding="utf-8")
    for path in ("scripts/linux/setup.sh", "tools/linux_build.py", "tools/linux_smoke_dist.py"):
        assert path in workflow and (ROOT / path).is_file()
    assert "linux-build/*" in workflow and "workflow_dispatch" in workflow
    windows = (ROOT / "scripts" / "linux" / "build_from_windows.ps1").read_text(encoding="utf-8")
    assert "linux-build.yml" in windows and "srpss-linux" in workflow and "srpss-linux" in windows
