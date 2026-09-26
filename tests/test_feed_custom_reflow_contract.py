"""Guards for FEEDS CUSTOM-slot independent X/Y and child reflow."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text("utf-8")


def test_feed_descriptor_and_retained_model_own_independent_xy_extent():
    descriptors = _text("rendering/widget_descriptors.py")
    start = descriptors.index("def _feed_runtime_descriptor(")
    block = descriptors[start:descriptors.index("WIDGET_RUNTIME_DESCRIPTORS", start)]
    assert 'content_extent_axes=("horizontal", "vertical")' in block
    assert 'content_extent_minimum_size=FEED_CONTENT_EXTENT_MINIMUM' in block

    from core.feeds.config import FEED_WIDGET_IDS
    from rendering.feed_child_roles import FEED_CONTENT_EXTENT_MINIMUM
    from rendering.widget_descriptors import get_widget_runtime_descriptor

    for widget_id in FEED_WIDGET_IDS:
        descriptor = get_widget_runtime_descriptor(widget_id)
        assert descriptor.content_extent_axes == ("horizontal", "vertical")
        assert descriptor.content_extent_minimum_size == FEED_CONTENT_EXTENT_MINIMUM

    model = _text("rendering/quick/widgets/feeds.py")
    assert "contentExtentChanged = Signal()" in model
    assert "def set_content_extent(" in model
    assert "def apply_custom_layout_size_payload(" in model
    assert "set_custom_layout_size_payload_handler(model.apply_custom_layout_size_payload)" in model


def test_feed_qml_reflows_from_geometry_without_io_or_cadence():
    qml = _text("rendering/quick/qml/FeedPresentation.qml")
    assert "preferredContentWidth: feedModel.preferredWidth" in qml
    assert "preferredContentHeight: feedModel.preferredHeight" in qml
    assert "readonly property int listCapacity" in qml
    assert "readonly property int gridColumns" in qml
    assert "readonly property int gridRowCapacity" in qml
    assert "readonly property real renderedGridCellHeight" in qml
    assert "gridVisibleRows === gridRowCapacity" in qml
    assert "(body.height - gridSpacing * Math.max(0, gridVisibleRows - 1))" in qml
    assert "layoutHeight - bodyTop - footerHeight" in qml
    assert "feedRoot.layoutHeight - feedRoot.footerHeight" in qml
    for forbidden in ("Timer {", "XMLHttpRequest", "NetworkAccess", "Qt.openUrlExternally"):
        assert forbidden not in qml


def test_feed_vertical_slice_uses_shared_stable_child_geometry_contract():
    roles = _text("rendering/feed_child_roles.py")
    descriptors = _text("rendering/widget_descriptors.py")
    model = _text("rendering/quick/widgets/feeds.py")
    qml = _text("rendering/quick/qml/FeedPresentation.qml")

    assert 'FEED_CONTENT_EXTENT_MINIMUM = (320.0, 180.0)' in roles
    for role_id in ("header", "refresh", "articles", "artwork", "overflow"):
        assert f'"{role_id}"' in roles
    assert 'freeform_artwork_child_role(' in roles
    assert 'custom_child_roles=FEED_CUSTOM_CHILD_ROLES' in descriptors
    assert 'content_extent_minimum_size=FEED_CONTENT_EXTENT_MINIMUM' in descriptors
    assert 'set_custom_child_geometry' in model
    assert 'customChildGeometry' in model
    assert 'FEED_CONTENT_EXTENT_MINIMUM' in model

    # Repeated article identities are volatile. One stable artwork role controls
    # all repeated image rectangles, matching the existing grouped-child pattern.
    assert 'customEditableChildRoles: [' in qml
    for role_id in ("header", "refresh", "articles", "artwork", "overflow"):
        assert f'{{"roleId": "{role_id}"' in qml
    role_block = qml.split('customEditableChildRoles: [', 1)[1].split(']', 1)[0]
    assert 'feedItemId' not in role_block
    assert 'objectName: "feedCustomArtworkRoleTarget"' in qml
    assert 'childWidthScale("artwork")' in qml
    assert 'childHeightScale("artwork")' in qml
    assert 'childOffsetX("artwork")' in qml
    assert 'childOffsetY("artwork")' in qml
    for forbidden in ("UndoStack", "SettingsManager", "save_child", "child_timer", "Timer {"):
        assert forbidden not in qml


def test_feed_grid_artwork_geometry_reflows_text_instead_of_landscape_only_slot():
    qml = _text("rendering/quick/qml/FeedPresentation.qml")

    assert "readonly property string textRegion:" in qml
    for region in ("leftTextArea", "rightTextArea", "topTextArea", "bottomTextArea"):
        assert f"readonly property real {region}:" in qml
    assert "readonly property bool sideText:" in qml
    assert "readonly property real textX:" in qml
    assert "readonly property real textWidth:" in qml
    assert "readonly property real textTop:" in qml
    assert "readonly property real textHeight:" in qml
    assert "fontSizeMode: Text.Fit" in qml
    assert "minimumPointSize:" in qml
    assert 'visible: feedSummary.length > 0 && height >= 18.0' in qml
    assert "maximumLineCount: gridCard.textHeight" in qml


def test_feed_artwork_editor_targets_real_sparse_art_without_per_story_saved_roles():
    model = _text("rendering/quick/widgets/feeds.py")
    qml = _text("rendering/quick/qml/FeedPresentation.qml")

    assert "def firstArtworkRowIndex(self) -> int:" in model
    assert "if row.image_source:" in model
    assert "readonly property int sourceIndex: feedRoot.feedModel.firstArtworkRowIndex" in qml
    assert "sourceIndex >= 0 && sourceIndex < visibleLimit" in qml
    assert "&& (gridMode || body.width >= 260.0)" in qml
    assert "readonly property int hostRow:" in qml
    assert "readonly property int visualColumn:" in qml


def test_feed_grid_never_republishes_rows_or_calls_python_from_geometry_only_resize():
    qml = _text("rendering/quick/qml/FeedPresentation.qml")
    model = _text("rendering/quick/widgets/feeds.py")
    projection = _text("core/feeds/projection.py")

    assert 'setVisibleCapacity' not in qml
    assert 'setVisibleCapacity' not in model
    assert 'visible_item_capacity' not in projection
    assert 'visible: index < feedRoot.visibleCapacity' in qml
    assert 'readonly property int gridColumns' in qml
    assert 'readonly property int gridRowCapacity' in qml


def test_feed_grid_sparse_local_art_is_per_story_not_global_veto():
    projection = _text("core/feeds/projection.py")
    qml = _text("rendering/quick/qml/FeedPresentation.qml")

    assert 'image_sources = requested_local' in projection
    assert 'else "sparse" if present else "none"' in projection
    assert 'readonly property bool hasArt: visible && feedImageSource.length > 0' in qml
    assert 'visible: gridCard.hasArt' in qml
