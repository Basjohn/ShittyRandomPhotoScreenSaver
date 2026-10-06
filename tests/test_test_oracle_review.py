"""Self-tests for the advisory durability/operator-intrusion scanner."""
from __future__ import annotations

from pathlib import Path

from tools import test_oracle_review
from tools.test_oracle_review import review_test_file


def _kinds(tmp_path: Path, source: str) -> set[str]:
    path = tmp_path / "test_probe.py"
    path.write_text(source, encoding="utf-8")
    return {item.kind for item in review_test_file(path)}


def test_review_flags_literal_source_spelling_oracle(tmp_path: Path) -> None:
    kinds = _kinds(
        tmp_path,
        '''\nfrom pathlib import Path\n\ndef test_spelling():\n    source = Path("production.py").read_text(encoding="utf-8")\n    assert "specific_method_name(" in source\n''',
    )
    assert "source-string-oracle" in kinds


def test_review_allows_documented_static_source_invariant(tmp_path: Path) -> None:
    kinds = _kinds(
        tmp_path,
        '''\nfrom pathlib import Path\n\ndef test_negative_architecture():\n    source = Path("production.py").read_text(encoding="utf-8")\n    # SOURCE-ORACLE INVARIANT: direct process polling is forbidden by lifecycle policy.\n    assert "process.poll()" not in source\n''',
    )
    assert "source-string-oracle" not in kinds


def test_review_flags_uncontained_show(tmp_path: Path) -> None:
    kinds = _kinds(
        tmp_path,
        '''\ndef test_window():\n    window = make_window()\n    window.show()\n''',
    )
    assert "visible-window-candidate" in kinds


def test_review_allows_invisible_real_window_helper(tmp_path: Path) -> None:
    kinds = _kinds(
        tmp_path,
        '''\ndef test_window():\n    window = keep_off_screen(make_window())\n    window.show()\n''',
    )
    assert "visible-window-candidate" not in kinds


def test_review_allows_offscreen_qpa_subprocess_fixture(tmp_path: Path) -> None:
    kinds = _kinds(
        tmp_path,
        '''\ndef test_window():\n    env = {"QT_QPA_PLATFORM": "offscreen"}\n    window = make_window()\n    window.show()\n''',
    )
    assert "visible-window-candidate" not in kinds



def test_review_flags_uncontained_modal_dialog_exec(tmp_path: Path) -> None:
    kinds = _kinds(
        tmp_path,
        '''
def test_modal():
    dialog = make_dialog()
    dialog.exec()
''',
    )
    assert "modal-dialog-candidate" in kinds


def test_review_allows_modal_dialog_kept_off_screen(tmp_path: Path) -> None:
    kinds = _kinds(
        tmp_path,
        '''
def test_modal():
    dialog = make_dialog()
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    dialog.exec()
''',
    )
    assert "modal-dialog-candidate" not in kinds

def test_review_queue_never_blocks_test_execution(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "test_visible_probe.py"
    path.write_text(
        '''
def test_window():
    window = make_window()
    window.show()
''',
        encoding="utf-8",
    )
    monkeypatch.setattr(test_oracle_review, "TEST_ROOT", tmp_path)

    assert test_oracle_review.main() == 0
    assert review_test_file(path)


def test_review_flags_exact_ui_copy_oracle(tmp_path: Path) -> None:
    kinds = _kinds(
        tmp_path,
        '''
def test_button_copy():
    assert button.text() == "EXPORT VISUALIZERS"
''',
    )
    assert "ui-copy-oracle" in kinds


def test_review_allows_explicit_ui_copy_contract(tmp_path: Path) -> None:
    kinds = _kinds(
        tmp_path,
        '''
def test_button_copy():
    # UI-COPY INVARIANT: this exact warning wording is the compatibility contract.
    assert button.text() == "DO NOT DISCONNECT"
''',
    )
    assert "ui-copy-oracle" not in kinds
