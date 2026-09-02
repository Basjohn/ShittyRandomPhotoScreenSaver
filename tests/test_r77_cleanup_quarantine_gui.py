from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "SRPSS_R77_Cleanup_Quarantine_GUI.py"


def _module():
    spec = importlib.util.spec_from_file_location("r77_quarantine_gui", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "rendering").mkdir()
    (tmp_path / "widgets").mkdir()
    return tmp_path


def test_quarantine_and_undo_are_reversible_without_qt(tmp_path):
    module = _module()
    root = _repo(tmp_path)
    module.PATHS = ("widgets/a.py", "rendering/b.py")
    for rel in module.PATHS:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(rel, encoding="utf-8")

    module.move_to_deletelater(root)
    for rel in module.PATHS:
        assert not (root / rel).exists()
        assert (root / "deletelater" / rel).read_text(encoding="utf-8") == rel

    module.restore_from_deletelater(root)
    for rel in module.PATHS:
        assert (root / rel).read_text(encoding="utf-8") == rel
        assert not (root / "deletelater" / rel).exists()


def test_preflight_conflict_aborts_before_any_move(tmp_path):
    module = _module()
    root = _repo(tmp_path)
    module.PATHS = ("widgets/a.py", "rendering/b.py")

    # First path is a source/destination conflict; second is otherwise movable.
    (root / "widgets/a.py").write_text("source", encoding="utf-8")
    q = root / "deletelater/widgets/a.py"
    q.parent.mkdir(parents=True, exist_ok=True)
    q.write_text("quarantine", encoding="utf-8")
    (root / "rendering/b.py").write_text("must stay", encoding="utf-8")

    try:
        module.move_to_deletelater(root)
    except RuntimeError:
        pass
    else:
        raise AssertionError("conflict should abort the transaction")

    assert (root / "rendering/b.py").read_text(encoding="utf-8") == "must stay"
    assert not (root / "deletelater/rendering/b.py").exists()
