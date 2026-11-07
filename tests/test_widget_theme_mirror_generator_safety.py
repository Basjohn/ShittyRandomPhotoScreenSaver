"""The Widget mirror generator cannot destroy authored themes by accident (AC-17 follow-up).

Wholesale regeneration rewrites every mirror from its Settings theme and deletes every other
``.srwtheme`` in the folder. Shipped mirrors carry hand-authored colour roles and the folder
holds unlinked material themes, so:
- the script with no arguments changes nothing and prints what regeneration would do;
- ``--regenerate-all`` alone refuses (and writes nothing) while it would overwrite an authored
  mirror or delete another theme; each needs its own explicit flag;
- once nothing authored is at stake, ``--regenerate-all`` alone succeeds and is idempotent.

Every run works on a copy of the shipped ``themes`` tree in ``tmp_path``. The script is pointed
at the copy by relocating its ``__file__`` (the script derives its themes root from it).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

import tools.generate_widget_theme_mirrors as generator

ROOT = Path(__file__).resolve().parents[1]
THEMES = ROOT / "themes"


def _snapshot(widgets: Path) -> dict[str, str]:
    return {path.name: path.read_bytes().decode("utf-8").replace("\r\n", "\n")
            for path in sorted(widgets.glob("*.srwtheme"))}


def _assert_unchanged(before: dict[str, str], after: dict[str, str]) -> None:
    erased = sorted(name for name in before if name in after and after[name] != before[name])
    deleted = sorted(name for name in before if name not in after)
    added = sorted(name for name in after if name not in before)
    assert not erased, f"authored mirrors erased: {erased}"
    assert not deleted, f"themes deleted: {deleted}"
    assert not added, f"files added: {added}"


@pytest.fixture
def project_copy(tmp_path, monkeypatch):
    if not (THEMES / "widgets").is_dir():
        pytest.skip("optional generated mirrors are absent from this source bundle")
    project = tmp_path / "project"
    shutil.copytree(THEMES, project / "themes")
    monkeypatch.setattr(generator, "__file__", str(project / "tools" / "generate_widget_theme_mirrors.py"))
    widgets = project / "themes" / "widgets"
    return widgets, _snapshot(widgets)


def _run(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["generate_widget_theme_mirrors.py", *args])
    return generator.main()


def test_no_arguments_changes_nothing_and_prints_what_regeneration_would_do(project_copy, monkeypatch, capsys):
    widgets, before = project_copy
    code = _run(monkeypatch)
    _assert_unchanged(before, _snapshot(widgets))
    assert code != 0
    printed = capsys.readouterr()
    plan = generator.plan_widget_theme_mirror_regeneration(widgets.parent)
    # The shipped pack has both hazards; the printout names every file at stake.
    assert plan.overwrites_authored and plan.deletes
    for path in (*plan.overwrites_authored, *plan.deletes):
        assert path.name in printed.err


def test_regenerate_all_refuses_each_hazard_until_its_own_flag_names_it(project_copy, monkeypatch):
    widgets, before = project_copy
    assert _run(monkeypatch, "--regenerate-all") != 0
    _assert_unchanged(before, _snapshot(widgets))
    assert _run(monkeypatch, "--regenerate-all", "--overwrite-authored") != 0      # deletes still at stake
    _assert_unchanged(before, _snapshot(widgets))
    assert _run(monkeypatch, "--regenerate-all", "--delete-unlinked") != 0         # authored still at stake
    _assert_unchanged(before, _snapshot(widgets))

    with pytest.raises(generator.MirrorRegenerationRefused):
        generator.generate_widget_theme_mirrors(widgets.parent)
    _assert_unchanged(before, _snapshot(widgets))

    plan = generator.plan_widget_theme_mirror_regeneration(widgets.parent)
    assert _run(monkeypatch, "--regenerate-all", "--overwrite-authored", "--delete-unlinked") == 0
    after = _snapshot(widgets)
    assert set(after) == {target.name for target in plan.writes}
    assert all(after[target.name] == text for target, text in plan.writes.items())

    # Nothing authored or foreign is left at stake: the bare flag now succeeds, idempotently.
    assert _run(monkeypatch, "--regenerate-all") == 0
    assert _snapshot(widgets) == after
