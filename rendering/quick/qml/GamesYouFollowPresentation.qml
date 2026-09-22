import QtQuick
import QtQuick.Effects

// One retained ordinary Steam card. The shared CUSTOM session owns geometry
// persistence; this family alone owns child rails, flip and independent X/Y reflow.
OverlayWidget {
    id: followsRoot
    objectName: "gamesYouFollowPresentation"
    required property var followedModel
    uniformScaleTransform: true
    preferredContentWidth: followedModel.authoredWidth
    preferredContentHeight: followedModel.authoredHeight
    readonly property real childNormalizationWidth: followedModel.baseAuthoredWidth
    readonly property real childNormalizationHeight: followedModel.baseAuthoredHeight
    readonly property var childGeometry: followedModel.customChildGeometry
    signal refreshRequested()
    signal articleRequested(int slot)

    function childRecord(roleId) {
        return childGeometry ? childGeometry[roleId] : null
    }
    function childWidthScale(roleId) {
        const rec = childRecord(roleId)
        return rec && rec.width_scale !== undefined ? Number(rec.width_scale) : 1.0
    }
    function childHeightScale(roleId) {
        const rec = childRecord(roleId)
        return rec && rec.height_scale !== undefined ? Number(rec.height_scale) : 1.0
    }
    function childOffsetX(roleId) {
        const rec = childRecord(roleId)
        return (rec && rec.x_offset !== undefined ? Number(rec.x_offset) : 0.0)
            * childNormalizationWidth
    }
    function childOffsetY(roleId) {
        const rec = childRecord(roleId)
        return (rec && rec.y_offset !== undefined ? Number(rec.y_offset) : 0.0)
            * childNormalizationHeight
    }
    function childAlignment(roleId, fallback) {
        const rec = childRecord(roleId)
        return rec && rec.alignment !== undefined ? String(rec.alignment) : fallback
    }
    function childAnchor(roleId) {
        const rec = childRecord(roleId)
        return rec && rec.anchor !== undefined ? String(rec.anchor) : ""
    }

    // Role identity never depends on source, available row count or card aspect.
    // No per-story CUSTOM handles and no child-to-parent preferred-size feedback.
    customEditableChildRoles: [
        {"roleId": "header", "normalizationTarget": followsRoot,
         "normalizationWidthProperty": "childNormalizationWidth",
         "normalizationHeightProperty": "childNormalizationHeight",
         "target": header, "semanticCornerInsetX": 12.0,
         "semanticCornerInsetY": 12.0, "semanticInsetUsesUniformCard": true},
        {"roleId": "refresh", "normalizationTarget": followsRoot,
         "normalizationWidthProperty": "childNormalizationWidth",
         "normalizationHeightProperty": "childNormalizationHeight",
         "target": refreshGlyph},
        {"roleId": "story_tiles", "normalizationTarget": followsRoot,
         "normalizationWidthProperty": "childNormalizationWidth",
         "normalizationHeightProperty": "childNormalizationHeight",
         "target": storyGroup},
        {"roleId": "overflow_summary", "normalizationTarget": followsRoot,
         "normalizationWidthProperty": "childNormalizationWidth",
         "normalizationHeightProperty": "childNormalizationHeight",
         "target": overflowSummary}
    ]

    readonly property bool headerFlipped: childAlignment("header", "left") === "right"
    BrandedHeader {
        id: header
        objectName: "followedHeader"
        frameObjectName: "followedHeaderFrame"
        readonly property string customAnchor: followsRoot.childAnchor("header")
        readonly property real customScale: followsRoot.childWidthScale("header")
        // The shared CUSTOM overlay expects family-owned right/bottom anchoring
        // to report its displacement from the authored left/top rail.
        property real customEditPlacementCompensationX:
            customAnchor.length > 0 || followsRoot.headerFlipped
                ? x - (12.0 + followsRoot.childOffsetX("header")) : 0.0
        property real customEditPlacementCompensationY:
            customAnchor.length > 0
                ? y - (12.0 + followsRoot.childOffsetY("header")) : 0.0
        x: customAnchor.endsWith("right")
            || (followsRoot.headerFlipped && !customAnchor.endsWith("left"))
            ? parent.width - 12.0 - width * scale
                + (customAnchor.length > 0 ? 0.0 : followsRoot.childOffsetX("header"))
            : (customAnchor.endsWith("left") ? 12.0
                : 12.0 + followsRoot.childOffsetX("header"))
        y: customAnchor.startsWith("bottom")
            ? parent.height - 12.0 - height * scale
            : (customAnchor.startsWith("top") ? 12.0
                : 12.0 + followsRoot.childOffsetY("header"))
        // A narrow portrait parent must not crop the shared full-label header.
        // Its authored CUSTOM size remains the authority; this is only the
        // same display-local containment applied to the paint transform.
        scale: Math.min(customScale, Math.max(0.1,
            (parent.width - 24.0) / Math.max(1.0, width)))
        transformOrigin: Item.TopLeft
        label: "GAMES YOU FOLLOW"
        logoSource: followedModel.steamLogo
        contentReversed: followsRoot.headerFlipped
        fillColor: followedModel.headerFillColor
        borderColor: followedModel.headerBorderColor
        borderWidth: followsRoot.scaleAwareHeaderStrokeWidth(
            followedModel.headerBorderWidth)
        textColor: followedModel.headerTextColor
        fontFamily: followedModel.fontFamily
        textShadowEnabled: followedModel.textShadowEnabled
        textShadowColor: followedModel.textShadowColor
        textShadowOffsetX: followedModel.textShadowOffsetX
        textShadowOffsetY: followedModel.textShadowOffsetY
        shadowEnabled: followsRoot.cardShadowEnabled
        shadowColor: Qt.rgba(followsRoot.cardShadowColor.r,
            followsRoot.cardShadowColor.g, followsRoot.cardShadowColor.b,
            followsRoot.cardShadowColor.a * 0.45)
        shadowBlur: Math.max(2.0, Math.min(6.0, followsRoot.cardShadowBlur * 0.25))
        shadowOffsetX: followsRoot.cardShadowOffsetX * 1.15
        shadowOffsetY: followsRoot.cardShadowOffsetY * 1.15
        interactionEnabled: false
    }

    Rectangle {
        id: refreshGlyph
        objectName: "followedRefreshTarget"
        readonly property bool canActivate: visible
            && !followsRoot.customLayoutInputBlocked
        // Peer-family contract: a bounded accessory disappears rather than
        // painting across the branded header in extreme vertical or CUSTOM.
        readonly property real paintedHeaderRight: header.x + header.width * header.scale
        readonly property real paintedHeaderBottom: header.y + header.height * header.scale
        readonly property bool collidesWithHeader:
            x < paintedHeaderRight + 5.0 && x + width > header.x - 5.0
            && y < paintedHeaderBottom + 4.0 && y + height > header.y - 4.0
        visible: width >= 16.0 && height >= 16.0
            && x >= 6.0 && y >= 6.0 && x + width <= parent.width - 6.0
            && y + height <= parent.height - 6.0 && !collidesWithHeader
        x: (followsRoot.headerFlipped ? 14.0 : parent.width - width - 14.0)
            + childOffsetX("refresh")
        y: 15.0 + childOffsetY("refresh")
        width: 28.0 * childWidthScale("refresh")
        height: 28.0 * childHeightScale("refresh")
        radius: 7.0
        color: followedModel.showRefreshFrame ? followedModel.headerFillColor : "transparent"
        border.color: refreshHover.hovered && canActivate
            ? followedModel.accentColor
            : followedModel.showRefreshFrame ? followedModel.headerBorderColor : "transparent"
        border.width: refreshHover.hovered && canActivate
            ? followsRoot.scaleAwareStrokeWidth(1.5)
            : followedModel.showRefreshFrame ? followsRoot.scaleAwareStrokeWidth(1.0) : 0.0
        HoverHandler {
            id: refreshHover
            enabled: refreshGlyph.canActivate
            blocking: false
            cursorShape: Qt.PointingHandCursor
        }
        ShadowedText {
            anchors.centerIn: parent
            width: parent.width
            height: parent.height
            text: "↻"
            textFormat: Text.PlainText
            font.pixelSize: Math.min(parent.width, parent.height) * 0.8
            color: followedModel.primaryColor
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            shadowEnabled: followedModel.textShadowEnabled
            shadowColor: followedModel.textShadowColor
            shadowOffsetX: followedModel.textShadowOffsetX
            shadowOffsetY: followedModel.textShadowOffsetY
        }
        TapHandler {
            acceptedButtons: Qt.LeftButton
            enabled: refreshGlyph.canActivate
            onTapped: followsRoot.refreshRequested()
        }
    }

    Item {
        id: storyGroup
        objectName: "followedStoryGroup"
        x: 14.0 + childOffsetX("story_tiles")
        // The header may grow in CUSTOM; content must never paint into it.
        y: Math.max(66.0, header.y + header.height * header.scale + 10.0)
            + childOffsetY("story_tiles")
        width: Math.max(0.0, (parent.width - 28.0) * childWidthScale("story_tiles"))
        // The grouped child has its natural CONTENT height, not the whole
        // remaining card height. Unused outer-card space must not become a giant
        // editable child bounding box that swallows resize handles. This is a
        // parent/data-derived authored baseline, never its own resized height.
        // Match the pure parent-layout calculator. Five readable/image-capable
        // cards fit a 1,570 px wide rail; eight 180 px slivers do not.
        readonly property real minimumTileWidth: followedModel.showArtwork ? 294.0 : 235.0
        // The Python projection alone decides authored-parent capacity. Qt may
        // deliver outer geometry and the model's extent in separate change
        // notifications; a second QML calculator caused the native 2-versus-3
        // story failure during repeated parent reflow. CUSTOM child edits use
        // the local constrained rail below without publishing parent geometry.
        readonly property int authoredColumns: Math.max(1, followedModel.layoutColumns)
        readonly property int authoredRows: Math.ceil(
            followedModel.selectedStoryCount / authoredColumns)
        readonly property real authoredGroupHeight: Math.min(
            Math.max(0.0, parent.height - 110.0),
            Math.max(0.0, authoredRows * 160.0 + Math.max(0, authoredRows - 1) * 8.0))
        // This target MUST have a truthful independent CUSTOM Y extent. Do not
        // clamp the editable rectangle to a sibling: that freezes the resize
        // handle. The visible whole-story capacity is separately bounded by
        // the card's paint rail below.
        height: Math.max(0.0, authoredGroupHeight * childHeightScale("story_tiles"))
        clip: true
        visible: followedModel.selectedStoryCount > 0
        readonly property int columnsFit: Math.max(0,
            Math.floor((width + 4.0) / (followedModel.layoutArrangement === "tall"
                ? 180.0 : minimumTileWidth)))
        readonly property real paintHeight: Math.max(0.0, Math.min(
            height, overflowSummary.y - y - 6.0))
        readonly property int rowsFit: Math.max(0, Math.floor((paintHeight + 14.0) / 112.0))
        readonly property bool onAuthoredRail:
            Math.abs(followsRoot.childWidthScale("story_tiles") - 1.0) < 0.0001
            && Math.abs(followsRoot.childHeightScale("story_tiles") - 1.0) < 0.0001
            && Math.abs(followsRoot.childOffsetX("story_tiles")) < 0.0001
            && Math.abs(followsRoot.childOffsetY("story_tiles")) < 0.0001
        // Keep the *default* group capacity congruent with followed_news_layout.
        // CUSTOM X/Y changes affect only this retained visual rail, never the
        // parent's preferred size, source revision or persisted story count.
        readonly property int columns: onAuthoredRail
            ? authoredColumns : Math.max(1,
                followedModel.layoutArrangement === "tall" ? 1
                : Math.min(followedModel.layoutArrangement === "wide" ? 8 : 4, columnsFit))
        // Rows may wrap in a wide but tall-enough parent. This is the existing
        // adaptive child flow, not a fixed single-row slice hiding good stories.
        readonly property int rows: onAuthoredRail ? followedModel.layoutRows
            : Math.max(0, Math.min(8, rowsFit,
                Math.ceil(followedModel.selectedStoryCount / columns)))
        readonly property int visibleCapacity: onAuthoredRail
            ? followedModel.visibleStoryCount
            : columnsFit === 0 || rows === 0 ? 0
                : Math.min(8, followedModel.selectedStoryCount, columns * rows)
        readonly property real tileWidth: columns > 0
            ? Math.max(0.0, (width - (columns - 1) * 8.0) / columns) : 0.0
        readonly property real tileHeight: rows > 0
            ? Math.min(160.0, (paintHeight - (rows - 1) * 8.0) / rows) : 104.0

        Repeater {
            id: stableStories
            objectName: "followedStableStories"
            model: followedModel.storyRows // Fixed eight slots; no array rebuild on resize.
            delegate: Item {
                id: tile
                objectName: "followedStoryTile" + storySlot
                visible: storyFilled && storySlot < storyGroup.visibleCapacity
                readonly property bool canActivate: visible && storyActionEnabled
                    && !followsRoot.customLayoutInputBlocked
                x: followsRoot.headerFlipped
                    ? storyGroup.width - storyGroup.tileWidth
                        - (storySlot % storyGroup.columns) * (storyGroup.tileWidth + 8.0)
                    : (storySlot % storyGroup.columns) * (storyGroup.tileWidth + 8.0)
                y: Math.floor(storySlot / storyGroup.columns) * (storyGroup.tileHeight + 8.0)
                width: storyGroup.tileWidth
                height: storyGroup.tileHeight
                clip: false
                RectangularShadow {
                    objectName: "followedStoryShadow" + storySlot
                    visible: tile.visible && followsRoot.cardShadowEnabled
                    x: 0.0
                    y: 0.0
                    width: tile.width
                    height: tile.height
                    radius: 7.0
                    color: Qt.rgba(followsRoot.cardShadowColor.r,
                        followsRoot.cardShadowColor.g, followsRoot.cardShadowColor.b,
                        followsRoot.cardShadowColor.a * 0.35)
                    blur: Math.max(2.0, Math.min(5.0, followsRoot.cardShadowBlur * 0.2))
                    offset: Qt.vector2d(followsRoot.cardShadowOffsetX * 0.5,
                        followsRoot.cardShadowOffsetY * 0.5)
                    cached: true
                }
                Rectangle {
                    id: tileFrame
                    objectName: "followedStoryFrame" + storySlot
                    anchors.fill: parent
                    radius: 7.0
                    color: followedModel.tileColor
                    // The accepted Steam artwork interaction contract: the
                    // whole story is the link target, not just its image.
                    border.color: followedModel.accentColor
                    border.width: followsRoot.scaleAwareStrokeWidth(1.25)
                    clip: true
                }
                HoverHandler {
                    id: tileHover
                    enabled: tile.canActivate
                    blocking: false
                    cursorShape: Qt.PointingHandCursor
                }
                // Retain all eight story delegates, but do not acquire a Qt
                // image for an invisible slot or a temporarily hidden rail.
                readonly property bool showArt: tile.visible && storyGroup.visible
                    && followedModel.anyStoryArtwork
                    // Evaluate authored image/text room, never a raw pixel
                    // threshold against the outer scaled card rectangle.
                    && width >= 176.0 && height >= 84.0
                readonly property real artWidth: showArt
                    ? Math.min(width * 0.35, followedModel.artworkShape === "portrait"
                        ? 60.0 : followedModel.artworkShape === "square" ? 78.0 : 94.0) : 0.0
                readonly property real artX: followsRoot.headerFlipped
                    ? width - artWidth - 8.0 : 8.0
                readonly property real textX: followsRoot.headerFlipped
                    ? 10.0 : (showArt ? artWidth + 17.0 : 10.0)
                readonly property real textW: Math.max(0.0, width - artWidth
                    - (showArt ? 27.0 : 20.0))
                readonly property int fittedHeadlineSize: Math.max(9,
                    Math.min(followedModel.fontSize, Math.floor(Math.min(
                        textW / 7.0, textW * 3.4 /
                        Math.max(1.0, Math.min(storyTitle.length,
                            followedModel.headlineChars))))))
                // An image-optional generation reserves the same artwork rail
                // for every tile. Missing art gets an intentional, restrained
                // local surface, never a broken/empty image or changing text X.
                // A static directional contact shadow belongs to the image
                // rail, not a per-image GPU blur or new animation owner.
                Rectangle {
                    objectName: "followedStoryArtworkContactShadow" + storySlot
                    parent: tileFrame
                    visible: tile.showArt && followsRoot.cardShadowEnabled
                    x: tile.artX + Math.max(-3.0, Math.min(3.0,
                        followsRoot.cardShadowOffsetX * 0.45))
                    y: 8.0 + Math.max(-3.0, Math.min(3.0,
                        followsRoot.cardShadowOffsetY * 0.45))
                    width: tile.artWidth
                    height: Math.max(0.0, tile.height - 16.0)
                    radius: 4.0
                    color: Qt.rgba(followsRoot.cardShadowColor.r,
                        followsRoot.cardShadowColor.g, followsRoot.cardShadowColor.b,
                        followsRoot.cardShadowColor.a * 0.22)
                }
                Rectangle {
                    objectName: "followedStoryArtworkFallback" + storySlot
                    parent: tileFrame
                    visible: tile.showArt
                    x: tile.artX
                    y: 8.0
                    width: tile.artWidth
                    height: Math.max(0.0, tile.height - 16.0)
                    radius: 4.0
                    color: followedModel.headerFillColor
                    border.color: followedModel.headerBorderColor
                    border.width: followsRoot.scaleAwareStrokeWidth(0.75)
                    ShadowedText {
                        anchors.centerIn: parent
                        width: parent.width - 4.0
                        text: "STEAM"
                        textFormat: Text.PlainText
                        color: followedModel.accentColor
                        opacity: storyArtwork.length > 0 ? 0.0 : 0.48
                        font.family: followedModel.fontFamily
                        font.pixelSize: 9
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
                ArtworkFadeImage {
                    objectName: "followedStoryArtwork" + storySlot
                    parent: tileFrame
                    visible: tile.showArt
                    x: tile.artX
                    y: 8.0
                    width: tile.artWidth
                    height: Math.max(0.0, tile.height - 16.0)
                    source: tile.showArt && storyArtwork.length > 0 ? storyArtwork : ""
                    fillMode: followedModel.artworkShape === "portrait"
                        ? Image.PreserveAspectFit : Image.PreserveAspectCrop
                }
                // The image itself covers the fallback's original stroke; an
                // independent semantic outline stays on top of both surfaces.
                Rectangle {
                    objectName: "followedStoryArtworkOutline" + storySlot
                    parent: tileFrame
                    visible: tile.showArt
                    x: tile.artX
                    y: 8.0
                    width: tile.artWidth
                    height: Math.max(0.0, tile.height - 16.0)
                    radius: 4.0
                    color: "transparent"
                    border.color: followedModel.headerBorderColor
                    border.width: followsRoot.scaleAwareStrokeWidth(0.9)
                }
                ShadowedText {
                    id: game
                    objectName: "followedStoryGame" + storySlot
                    parent: tileFrame
                    visible: storyGame.length > 0
                    x: tile.textX
                    y: 7.0
                    width: tile.textW
                    height: visible ? 16.0 : 0.0
                    text: storyGame
                    textFormat: Text.PlainText
                    shadowEnabled: followedModel.textShadowEnabled
                    shadowColor: followedModel.textShadowColor
                    shadowOffsetX: followedModel.textShadowOffsetX
                    shadowOffsetY: followedModel.textShadowOffsetY
                    color: followedModel.accentColor
                    font.family: followedModel.fontFamily
                    font.pixelSize: Math.max(9, Math.min(11, tile.textW / 12.0))
                    font.bold: true
                    elide: Text.ElideRight
                    horizontalAlignment: followsRoot.headerFlipped ? Text.AlignRight : Text.AlignLeft
                }
                ShadowedText {
                    id: headline
                    objectName: "followedStoryHeadline" + storySlot
                    parent: tileFrame
                    x: tile.textX
                    y: game.visible ? 24.0 : 10.0
                    width: tile.textW
                    height: Math.min(48.0, Math.max(20.0, tile.height - y
                        - (storyPreview.length > 0 && tile.height >= 108.0 ? 52.0 : 27.0)))
                    text: storyTitle.length > followedModel.headlineChars
                        ? storyTitle.substring(0, followedModel.headlineChars) + "…" : storyTitle
                    textFormat: Text.PlainText
                    shadowEnabled: followedModel.textShadowEnabled
                    shadowColor: followedModel.textShadowColor
                    shadowOffsetX: followedModel.textShadowOffsetX
                    shadowOffsetY: followedModel.textShadowOffsetY
                    color: followedModel.primaryColor
                    font.family: followedModel.fontFamily
                    // Prefer reducing text size to dropping words in a narrow
                    // retained tile. This is display-only, not a Settings write.
                    font.pixelSize: tile.fittedHeadlineSize
                    font.bold: true
                    wrap: true
                    maximumLineCount: 2
                    elide: Text.ElideRight
                    horizontalAlignment: followedModel.headlineAlignment === "center"
                        ? Text.AlignHCenter : followedModel.headlineAlignment === "right"
                        ? Text.AlignRight : followsRoot.headerFlipped ? Text.AlignRight : Text.AlignLeft
                }
                // Pick the number actually visible in this tile, not the number
                // persisted in the source. X/Y Edit geometry can therefore
                // restore the preview when a three-image rail becomes too small.
                // No refresh, new worker, or model re-publication on resize.
                readonly property real inlineY: headline.y + headline.height + 2.0
                readonly property real inlineH: Math.min(92.0,
                    Math.max(0.0, tile.height - inlineY - 27.0))
                readonly property real inlineGap: 5.0
                readonly property int inlineAvailable: storyInlineArtwork1.length === 0 ? 0
                    : storyInlineArtwork2.length === 0 ? 1
                    : storyInlineArtwork3.length === 0 ? 2 : 3
                // Two and three image rails consume the body area outright.
                // A lone image must leave a readable text preview to its side.
                readonly property int inlineCount: !tile.visible || tile.inlineH < 36.0 ? 0
                    : tile.inlineAvailable >= 3 && tile.textW >= 3.0 * 76.0 + 2.0 * inlineGap ? 3
                    : tile.inlineAvailable >= 2 && tile.textW >= 2.0 * 76.0 + inlineGap ? 2
                    : tile.inlineAvailable >= 1 && tile.textW >= 76.0 + 110.0 + inlineGap ? 1 : 0
                readonly property bool showInline: tile.inlineCount > 0
                readonly property real inlineW: tile.inlineCount > 0 ? Math.max(0.0,
                    Math.min(168.0, tile.inlineH * 1.85,
                    (tile.textW - (tile.inlineCount === 1 ? 110.0 + inlineGap : 0.0)
                        - inlineGap * (tile.inlineCount - 1)) / tile.inlineCount)) : 0.0
                readonly property real inlineRailW: tile.inlineCount > 0
                    ? tile.inlineW * tile.inlineCount + inlineGap * (tile.inlineCount - 1) : 0.0
                readonly property real inlineX: followsRoot.headerFlipped
                    ? tile.textX + tile.textW - tile.inlineRailW : tile.textX
                Rectangle {
                    objectName: "followedStoryInlineContactShadow1" + storySlot
                    parent: tileFrame
                    visible: tile.inlineCount >= 1 && followsRoot.cardShadowEnabled
                    x: tile.inlineX + (tile.inlineW + tile.inlineGap) * 0.0
                        + Math.max(-3.0, Math.min(3.0, followsRoot.cardShadowOffsetX * 0.45))
                    y: tile.inlineY + Math.max(-3.0, Math.min(3.0,
                        followsRoot.cardShadowOffsetY * 0.45))
                    width: tile.inlineW
                    height: tile.inlineH
                    radius: 3.0
                    color: Qt.rgba(followsRoot.cardShadowColor.r,
                        followsRoot.cardShadowColor.g, followsRoot.cardShadowColor.b,
                        followsRoot.cardShadowColor.a * 0.22)
                }
                Rectangle {
                    objectName: "followedStoryInlineImageFrame1" + storySlot
                    parent: tileFrame
                    visible: tile.showInline
                    x: tile.inlineX
                    y: tile.inlineY
                    width: tile.inlineW
                    height: tile.inlineH
                    radius: 3.0
                    clip: true
                    color: followedModel.headerFillColor
                    Image {
                        objectName: "followedStoryInlineImage1" + storySlot
                        anchors.fill: parent
                        source: parent.visible ? storyInlineArtwork1 : ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                    }
                    Rectangle {
                        anchors.fill: parent
                        radius: parent.radius
                        color: "transparent"
                        border.color: followedModel.headerBorderColor
                        border.width: followsRoot.scaleAwareStrokeWidth(0.9)
                    }
                }
                Rectangle {
                    objectName: "followedStoryInlineContactShadow2" + storySlot
                    parent: tileFrame
                    visible: tile.inlineCount >= 2 && followsRoot.cardShadowEnabled
                    x: tile.inlineX + (tile.inlineW + tile.inlineGap) * 1.0
                        + Math.max(-3.0, Math.min(3.0, followsRoot.cardShadowOffsetX * 0.45))
                    y: tile.inlineY + Math.max(-3.0, Math.min(3.0,
                        followsRoot.cardShadowOffsetY * 0.45))
                    width: tile.inlineW
                    height: tile.inlineH
                    radius: 3.0
                    color: Qt.rgba(followsRoot.cardShadowColor.r,
                        followsRoot.cardShadowColor.g, followsRoot.cardShadowColor.b,
                        followsRoot.cardShadowColor.a * 0.22)
                }
                Rectangle {
                    objectName: "followedStoryInlineImageFrame2" + storySlot
                    parent: tileFrame
                    visible: tile.inlineCount >= 2
                    x: tile.inlineX + tile.inlineW + tile.inlineGap
                    y: tile.inlineY
                    width: tile.inlineW
                    height: tile.inlineH
                    radius: 3.0
                    clip: true
                    color: followedModel.headerFillColor
                    Image {
                        objectName: "followedStoryInlineImage2" + storySlot
                        anchors.fill: parent
                        source: parent.visible ? storyInlineArtwork2 : ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                    }
                    Rectangle {
                        anchors.fill: parent
                        radius: parent.radius
                        color: "transparent"
                        border.color: followedModel.headerBorderColor
                        border.width: followsRoot.scaleAwareStrokeWidth(0.9)
                    }
                }
                Rectangle {
                    objectName: "followedStoryInlineContactShadow3" + storySlot
                    parent: tileFrame
                    visible: tile.inlineCount >= 3 && followsRoot.cardShadowEnabled
                    x: tile.inlineX + (tile.inlineW + tile.inlineGap) * 2.0
                        + Math.max(-3.0, Math.min(3.0, followsRoot.cardShadowOffsetX * 0.45))
                    y: tile.inlineY + Math.max(-3.0, Math.min(3.0,
                        followsRoot.cardShadowOffsetY * 0.45))
                    width: tile.inlineW
                    height: tile.inlineH
                    radius: 3.0
                    color: Qt.rgba(followsRoot.cardShadowColor.r,
                        followsRoot.cardShadowColor.g, followsRoot.cardShadowColor.b,
                        followsRoot.cardShadowColor.a * 0.22)
                }
                Rectangle {
                    objectName: "followedStoryInlineImageFrame3" + storySlot
                    parent: tileFrame
                    visible: tile.inlineCount >= 3
                    x: tile.inlineX + (tile.inlineW + tile.inlineGap) * 2.0
                    y: tile.inlineY
                    width: tile.inlineW
                    height: tile.inlineH
                    radius: 3.0
                    clip: true
                    color: followedModel.headerFillColor
                    Image {
                        objectName: "followedStoryInlineImage3" + storySlot
                        anchors.fill: parent
                        source: parent.visible ? storyInlineArtwork3 : ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                    }
                    Rectangle {
                        anchors.fill: parent
                        radius: parent.radius
                        color: "transparent"
                        border.color: followedModel.headerBorderColor
                        border.width: followsRoot.scaleAwareStrokeWidth(0.9)
                    }
                }
                ShadowedText {
                    objectName: "followedStoryPreview" + storySlot
                    parent: tileFrame
                    visible: storyPreview.length > 0 && tile.height >= 108.0 && tile.textW >= 105.0
                        && tile.inlineCount < 2
                    x: tile.textX + (tile.inlineCount === 1 && !followsRoot.headerFlipped
                        ? tile.inlineRailW + 6.0 : 0.0)
                    y: tile.inlineY
                    width: Math.max(0.0, tile.textW - (tile.inlineCount === 1 ? tile.inlineRailW + 6.0 : 0.0))
                    height: Math.max(0.0, tile.height - y - 27.0)
                    text: storyPreview
                    textFormat: Text.PlainText
                    shadowEnabled: followedModel.textShadowEnabled
                    shadowColor: followedModel.textShadowColor
                    shadowOffsetX: followedModel.textShadowOffsetX
                    shadowOffsetY: followedModel.textShadowOffsetY
                    color: followedModel.primaryColor
                    opacity: 0.76
                    horizontalAlignment: followsRoot.headerFlipped ? Text.AlignRight : Text.AlignLeft
                    font.family: followedModel.fontFamily
                    font.pixelSize: Math.max(9, Math.min(11, tile.textW / 12.0))
                    wrap: true
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }
                ShadowedText {
                    objectName: "followedStorySource" + storySlot
                    parent: tileFrame
                    x: tile.textX
                    y: tile.height - 23.0
                    width: tile.textW
                    height: 16.0
                    // Date must remain readable before the long provider label
                    // is elided at narrow widths.
                    text: storyPublished + "  ·  " + storySource
                    textFormat: Text.PlainText
                    shadowEnabled: followedModel.textShadowEnabled
                    shadowColor: followedModel.textShadowColor
                    shadowOffsetX: followedModel.textShadowOffsetX
                    shadowOffsetY: followedModel.textShadowOffsetY
                    color: followedModel.accentColor
                    font.family: followedModel.fontFamily
                    font.pixelSize: Math.max(9, Math.min(10, tile.textW / 16.0))
                    horizontalAlignment: followsRoot.headerFlipped ? Text.AlignRight : Text.AlignLeft
                    elide: Text.ElideRight
                }
                // As in Achievement Pulse artwork, keep the interactive
                // outline ABOVE the image and text instead of painting it
                // underneath retained image content. No animation or timer.
                Rectangle {
                    objectName: "followedStoryHoverOutline" + storySlot
                    parent: tileFrame
                    anchors.fill: parent
                    radius: tileFrame.radius
                    color: "transparent"
                    visible: tileHover.hovered && tile.canActivate
                    border.color: followedModel.primaryColor
                    border.width: followsRoot.scaleAwareStrokeWidth(1.75)
                }
                TapHandler {
                    acceptedButtons: Qt.LeftButton
                    enabled: tile.canActivate
                    onTapped: followsRoot.articleRequested(storySlot)
                }
            }
        }
    }

    ShadowedText {
        id: overflowSummary
        objectName: "followedOverflowSummary"
        readonly property int omitted: Math.max(0,
            followedModel.selectedStoryCount - storyGroup.visibleCapacity)
            + followedModel.omittedBySetting
        visible: (omitted > 0 || followedModel.selectedStoryCount === 0
            || followedModel.remainingFollowedCount > 0)
            && y > header.y + header.height * header.scale + 3.0
        x: 14.0 + childOffsetX("overflow_summary")
        y: parent.height - 31.0 + childOffsetY("overflow_summary")
        width: Math.max(0.0, (parent.width - 28.0) * childWidthScale("overflow_summary"))
        height: 20.0 * childHeightScale("overflow_summary")
        // Coverage takes priority over the display's overflow. Otherwise
        // the first four-game batch can masquerade as a complete newest feed.
        text: followedModel.remainingFollowedCount > 0
                ? "Checking " + followedModel.coveredCount + " / "
                    + followedModel.followedCount + " followed games"
                    + (omitted > 0 ? "  ·  +" + omitted + " more" : "")
            : omitted > 0 ? "+" + omitted + " more updates"
            : followedModel.selectedStoryCount === 0 ? followedModel.statusLabel : ""
        color: followedModel.primaryColor
        font.family: followedModel.fontFamily
        font.pixelSize: 11
        textFormat: Text.PlainText
        elide: Text.ElideRight
        shadowEnabled: followedModel.textShadowEnabled
        shadowColor: followedModel.textShadowColor
        shadowOffsetX: followedModel.textShadowOffsetX
        shadowOffsetY: followedModel.textShadowOffsetY
        horizontalAlignment: childAlignment("overflow_summary",
            followsRoot.headerFlipped ? "right" : "left") === "right"
            ? Text.AlignRight : Text.AlignLeft
        clip: true
    }
}
