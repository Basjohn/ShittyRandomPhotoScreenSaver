"""Import-free FEEDS branded-header / semantic-flip vertical-slice guards."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text("utf-8")


def test_feed_header_is_shared_branded_header_with_semantic_palette_and_corner_flip():
    roles = _text("rendering/feed_child_roles.py")
    qml = _text("rendering/quick/qml/FeedPresentation.qml")
    palette = _text("ui/widget_visual_roles.py")
    model = _text("rendering/quick/widgets/feeds.py")

    header_start = roles.index('CustomChildRoleDescriptor(\n        "header"')
    header = roles[header_start:roles.index('    ),', header_start) + 6]
    assert "uniform_scale=True" in header
    assert "alignment_flip=True" in header
    assert 'authored_alignment="left"' in header
    assert "semantic_corner_anchor=True" in header

    assert "BrandedHeader {" in qml
    assert 'objectName: "feedHeader"' in qml
    assert 'frameObjectName: "feedHeaderFrame"' in qml
    assert 'logoObjectName: "feedHeaderLogo"' in qml
    assert 'textObjectName: "feedHeaderText"' in qml
    assert "contentReversed: feedRoot.headerFlipped" in qml
    assert 'fillColor: feedRoot.feedModel.headerFillColor' in qml
    assert 'borderColor: feedRoot.feedModel.headerBorderColor' in qml
    assert 'textColor: feedRoot.feedModel.headerTextColor' in qml
    assert '"semanticCornerInsetX": 0.0' in qml
    assert '"semanticCornerInsetY": 0.0' in qml
    assert "feedMonogramFrame" not in qml

    for role in ("fill", "border", "text"):
        assert f'"feeds_custom_1.header.{role}": "header.{role}"' in palette
    assert "resolve_header_colors(" in model
    assert "header_fill_color=header_fill" in model
    assert "header_border_color=header_border" in model
    assert "header_text_color=header_text" in model

    # Refresh shares the semantic header rail and switches to the opposite side.
    assert "(feedRoot.headerFlipped ? 0.0 : headerArea.width - width)" in qml
    assert 'objectName: "feedRefreshTarget"' in qml


def test_feed_monogram_is_once_cached_qpainter_vector_not_runtime_font_glyph():
    source = _text("rendering/quick/widgets/feeds.py")

    assert "@lru_cache(maxsize=64)" in source
    assert "def _vector_monogram_data_uri(" in source
    assert "QPainter(image)" in source
    assert "glyph_segments = {" in source
    assert "painter.drawLine(" in source
    assert "glyph_pen.setWidthF(7.0)" in source
    assert 'return f"data:image/png;base64,{payload}"' in source
    assert "QFont" not in source
    assert "QPainterPath" not in source
    assert ".addText(" not in source
    assert "_vector_monogram_data_uri(self.monogram, self.config.header_text_color)" in source


def test_feed_subtitle_is_small_metadata_below_not_inside_shared_header_pill():
    shared = _text("rendering/quick/qml/BrandedHeader.qml")
    feed = _text("rendering/quick/qml/FeedPresentation.qml")

    # The primitive may support a secondary label for other consumers, but FEEDS
    # deliberately does not use it. Publisher metadata is a separate small rail.
    assert "property string secondaryLabel" in shared
    assert "secondaryLabel: feedRoot.feedModel.feedTitle" not in feed
    assert "secondaryMaximumWidth:" not in feed
    assert 'id: headerSubtitle' in feed
    assert 'objectName: "feedHeaderSubtitle"' in feed
    assert "readonly property real subtitleGap: 2.5" in feed
    assert "y: headerFrame.y + headerFrame.height * headerFrame.scale + feedRoot.subtitleGap" in feed
    assert "feedModel.showSubtitle" in feed
    assert "font.pointSize: Math.max(8.5, feedRoot.feedModel.fontSize - 3.0)" in feed
    assert "elide: Text.ElideRight" in feed


def test_feed_header_flip_is_widget_wide_semantic_layout_not_header_only():
    qml = _text("rendering/quick/qml/FeedPresentation.qml")

    # Header intent mirrors body rails/order without mirroring image pixels.
    assert "layoutDirection: feedRoot.headerFlipped ? Qt.RightToLeft : Qt.LeftToRight" in qml
    assert "readonly property real authoredArtworkX: feedRoot.headerFlipped" in qml
    assert "readonly property real contentLeft: hasArt && feedRoot.headerFlipped" in qml
    assert "horizontalAlignment: feedRoot.headerFlipped ? Text.AlignRight : Text.AlignLeft" in qml
    assert "horizontalAlignment: feedRoot.headerFlipped ? Text.AlignLeft : Text.AlignRight" in qml
    assert "fillMode: Image.PreserveAspectCrop" in qml
    assert "transform: Scale" not in qml
