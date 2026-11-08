"""Linux-only test selection. The Linux build's declaration checks are platform-neutral text checks and live in
``tests/test_build_linux_declarations.py`` so they also run on Windows, where the Windows build scripts are edited."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_linux_only_tests_are_never_selected_or_run_off_linux(monkeypatch) -> None:
    sys.path.insert(0, str(ROOT))
    from tools import impacted_tests

    linux_files = [path for path in impacted_tests.all_test_files() if path.name.startswith("test_linux_")]
    assert ROOT / "tests" / "test_linux_build.py" in linux_files and len(linux_files) >= 5
    monkeypatch.setattr(impacted_tests.sys, "platform", "win32")
    assert not impacted_tests.runs_on_this_platform(ROOT / "tests" / "test_linux_build.py")
    assert impacted_tests.runs_on_this_platform(ROOT / "tests" / "test_platform_selection.py")
    assert not any(path.name.startswith("test_linux_") for path in impacted_tests.all_test_files())
