"""Headless source guard for QML duplicate-property parse failures."""
from pathlib import Path

from core.build_qml_contract import duplicate_direct_property_assignments


def test_duplicate_direct_qml_property_is_rejected(tmp_path: Path) -> None:
    qml = tmp_path / "Broken.qml"
    qml.write_text(
        "import QtQuick\nItem {\n    visible: true\n    Rectangle {\n        visible: true\n    }\n    visible: false\n}\n",
        encoding="utf-8",
    )
    issues = duplicate_direct_property_assignments(qml)
    assert len(issues) == 1
    assert issues[0].property_name == "visible"
    assert issues[0].first_line == 3 and issues[0].second_line == 7


def test_nested_qml_properties_do_not_conflict(tmp_path: Path) -> None:
    qml = tmp_path / "Valid.qml"
    qml.write_text(
        "import QtQuick\nItem {\n    visible: true\n    Rectangle {\n        visible: false\n    }\n}\n",
        encoding="utf-8",
    )
    assert duplicate_direct_property_assignments(qml) == ()


def test_shipped_quick_qml_has_no_duplicate_direct_property_assignments() -> None:
    from core.build_qml_contract import audit_qml_source_contract

    root = Path(__file__).resolve().parents[1]
    assert audit_qml_source_contract(root) == ()
