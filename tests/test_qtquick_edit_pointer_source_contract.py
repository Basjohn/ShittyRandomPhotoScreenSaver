"""Cheap guard for the edit target geometry, NOT Qt pointer delivery evidence."""
from pathlib import Path

QML = (Path(__file__).resolve().parents[1] / "rendering" / "quick" /
       "qml" / "CustomLayoutOverlay.qml")


def test_parent_hit_area_covers_entire_edit_frame_except_real_chrome() -> None:
    source = QML.read_text(encoding="utf-8")
    area = source.split('id: moveArea', 1)[1].split('id: transferLeftControl', 1)[0]
    assert 'anchors.fill: parent' in area
    assert 'anchors.topMargin:' not in area
    assert 'customLayoutOverlay.sessionModel.selectItem(editFrame.index)' in area
    assert 'customLayoutOverlay.sessionModel.moveItem(' in area


def test_flip_pointer_surface_is_larger_than_drawn_disc_and_on_top_of_move() -> None:
    source = QML.read_text(encoding="utf-8")
    flip = source.split('id: childAlignmentFlip', 1)[1].split('id: childResizeHandle', 1)[0]
    assert 'width: 30' in flip and 'height: 30' in flip
    assert 'z: 6' in flip
    assert 'width: 16' in flip and 'height: 16' in flip
    assert 'id: childAlignmentFlip' in source
    assert 'customLayoutOverlay.sessionModel.flipChildAlignment(' in flip
    assert 'target: customLayoutOverlay.sessionModel || null' in source
