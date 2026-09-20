"""Import-free admission and retained-family contract for G2 presentation staging."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QT_MODEL = ROOT / "rendering/quick/widgets/games_you_follow.py"
QML = ROOT / "rendering/quick/qml/GamesYouFollowPresentation.qml"
ROLES = ROOT / "rendering/games_followed_child_roles.py"


def test_preview_family_not_admitted_before_shared_steam_lease_and_security_gate():
    registry = (ROOT / "rendering/quick/widgets/registry.py").read_text("utf-8")
    services = (ROOT / "rendering/widget_runtime_services.py").read_text("utf-8")
    binder = (ROOT / "rendering/quick/widgets/family_binder.py").read_text("utf-8")
    assert 'qml_filename="GamesYouFollowPresentation.qml"' not in registry
    assert 'class GamesYouFollowFamilyAdapter' not in binder
    assert '"steam_progress": _FOLLOWED' not in services


def test_g2_model_has_one_fixed_ordinal_row_model_and_grouped_roles():
    source = QT_MODEL.read_text("utf-8")
    tree = ast.parse(source)
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    assert {"FollowedStoryRows", "GamesYouFollowPresentationModel"} <= classes.keys()
    row_methods = {node.name for node in classes["FollowedStoryRows"].body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "apply_display" in row_methods and "rowCount" in row_methods
    assert "_MAX_ROWS = 8" in source
    assert "dataChanged.emit" in source and "beginResetModel" not in source
    descriptors = ROLES.read_text("utf-8")
    assert "from rendering.games_followed_child_roles import FOLLOWED_CHILD_ROLES" in source
    assert all(f'"{name}"' in descriptors for name in ("header", "refresh", "story_tiles", "overflow_summary"))
    assert "CustomChildRoleDescriptor(" in descriptors
    assert "from rendering.custom_child_geometry import CustomChildRoleDescriptor" in descriptors
    assert "from PySide6" not in descriptors  # Descriptors may be shared before a Qt import.
    assert "clamp_child_geometry(" in source
    assert "previous_arrangement=self._layout.arrangement" in source
    assert "project_followed_news(snapshot)" in source
    assert "set_content_extent" in source and "apply_custom_layout_size_payload" in source


def test_g2_quick_has_stable_role_targets_bounded_slots_and_no_side_effects():
    qml = QML.read_text("utf-8")
    assert "uniformScaleTransform: true" in qml
    assert "preferredContentWidth: followedModel.authoredWidth" in qml
    assert "preferredContentHeight: followedModel.authoredHeight" in qml
    assert "customEditableChildRoles: [" in qml
    assert "model: followedModel.storyRows" in qml
    assert "visibleCapacity" in qml and "overflowSummary" in qml
    assert 'textFormat: Text.PlainText' in qml
    for forbidden in ("Timer {", "MouseArea {", "onClicked:", "XMLHttpRequest", "Qt.openUrlExternally", "https://", "http://"):
        assert forbidden not in qml
    assert not any(value in qml for value in ("steamid", "appid", "gid", "providerUrl", "onLinkActivated"))


def test_source_identity_and_private_fields_do_not_flow_through_qt_roles():
    source = QT_MODEL.read_text("utf-8")
    tree = ast.parse(source)
    row_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "FollowedStoryRows")
    role_names = next(node for node in row_class.body if isinstance(node, ast.FunctionDef) and node.name == "roleNames")
    role_source = ast.get_source_segment(source, role_names)
    assert role_source is not None
    for forbidden in ("appId", "steamId", "gid", "providerUrl", "rawHtml", "remoteArtwork"):
        assert forbidden not in role_source
    assert 'return False  # No click permission' in source
