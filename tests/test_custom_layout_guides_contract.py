from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_custom_alignment_guides_have_explicit_above_below_layering() -> None:
    scene = _text("rendering/quick/qml/DisplayScene.qml")
    overlay = _text("rendering/quick/qml/CustomLayoutOverlay.qml")
    underlay = _text("rendering/quick/qml/CustomLayoutGuideUnderlay.qml")
    qmldir = _text("rendering/quick/qml/qmldir")

    assert "CustomLayoutGuideUnderlay 1.0 CustomLayoutGuideUnderlay.qml" in qmldir
    assert "id: customLayoutGuideUnderlay" in scene
    assert "z: 4" in scene
    assert 'objectName: "pixelShiftLayer"' in scene
    assert "z: 5" in scene
    assert "id: customLayoutOverlay" in scene
    assert "z: 100" in scene

    # Peer-edge alignment is a gentle blue high-layer guide.
    assert 'color: "#aa5ea8ff"' in overlay
    assert 'objectName: "customLayoutVerticalGuide"' in overlay
    assert 'objectName: "customLayoutHorizontalGuide"' in overlay

    # Centering guides and the stronger absolute centre cross stay under widgets.
    assert 'color: "#a8b46eff"' in underlay
    assert 'objectName: "customLayoutVerticalCenterGuide"' in underlay
    assert 'objectName: "customLayoutHorizontalCenterGuide"' in underlay
    assert 'color: "#70ffffff"' in underlay
    assert 'color: index % 4 === 0 ? "#3affffff" : "#1cffffff"' in underlay


def test_custom_move_publishes_existing_snap_metadata_without_new_cadence() -> None:
    owner = _text("rendering/quick/custom_layout_owner.py")
    scene = _text("rendering/quick/scene_controller.py")
    overlay_qml = _text("rendering/quick/qml/CustomLayoutOverlay.qml")

    assert "resolution = resolve_snap_local_rect_for_edit(" in owner
    assert "self._publish_move_guides(target.identity, resolution)" in owner
    assert 'allowed_kinds = {"peer", "peer_center", "display_center"}' in owner
    assert 'getattr(resolution, "vertical_assists", ())' in owner
    assert 'getattr(resolution, "horizontal_assists", ())' in owner
    assert "move_finished_handler=self.clear_move_guides" in owner
    assert "def set_custom_layout_guides(" in scene
    assert 'center_kinds = {"display_center", "peer_center"}' in scene
    assert "onReleased: customLayoutOverlay.sessionModel.finishMove()" in overlay_qml
    assert "onCanceled: customLayoutOverlay.sessionModel.finishMove()" in overlay_qml

    # The restoration is event-driven: do not introduce a guide-owned cadence.
    combined = owner + scene + overlay_qml
    assert "QTimer" not in combined
    assert "Timer {" not in combined
