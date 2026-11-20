"""build.cmd selects the newest installed MSVC toolset the target Python's VC runtime can load.

GitHub's runner moved its default toolset to 14.52 while its Python 3.14 ships VCRUNTIME140 14.51 (21 Nov 2026); the
runtime check refuses a module linked by a newer toolset than the runtime, so the build must not take the default.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "native" / "core" / "python"))

from select_msvc_toolset import choose, installed_toolsets  # noqa: E402

TOOLSETS = [((14, 50, 35717), "14.50.35717"), ((14, 51, 36231), "14.51.36231"), ((14, 52, 36400), "14.52.36400")]


def test_the_newest_toolset_not_newer_than_the_runtime_is_chosen():
    assert choose(TOOLSETS, (14, 51)) == "14.51.36231"
    assert choose(TOOLSETS, (14, 52)) == "14.52.36400"
    assert choose(TOOLSETS, (14, 60)) == "14.52.36400"


def test_no_toolset_old_enough_is_refused():
    assert choose(TOOLSETS, (14, 49)) is None


def test_installed_toolsets_are_read_from_the_vs_tree_and_ignore_other_folders(tmp_path):
    msvc = tmp_path / "VC" / "Tools" / "MSVC"
    for name in ("14.52.36400", "14.51.36231", "notes"):
        (msvc / name).mkdir(parents=True)
    assert [name for _, name in installed_toolsets(tmp_path)] == ["14.51.36231", "14.52.36400"]


def test_build_cmd_passes_the_chosen_toolset_to_vcvars():
    text = (ROOT / "native" / "core" / "build.cmd").read_text(encoding="utf-8")
    assert "select_msvc_toolset.py" in text
    assert "-vcvars_ver=%TOOLSET%" in text
