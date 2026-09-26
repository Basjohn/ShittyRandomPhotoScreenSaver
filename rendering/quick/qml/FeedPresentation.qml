import QtQuick
import QtQuick.Effects

OverlayWidget {
    id: feedRoot
    objectName: "feedPresentation"
    uniformScaleTransform: true

    required property var feedModel
    signal openItemRequested(string url)
    signal refreshRequested()

    preferredContentWidth: feedModel.preferredWidth
    preferredContentHeight: feedModel.preferredHeight

    // The shared CUSTOM session owns these stable groups and all saved
    // geometry. Article identities, counts and image readiness are never child
    // role identities. Outside Edit the authored values remain exact.
    readonly property real childNormalizationWidth: feedModel.basePreferredWidth
    readonly property real childNormalizationHeight: feedModel.basePreferredHeight
    readonly property var childGeometry: feedModel.customChildGeometry
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
    function childAlignment(roleId, authored) {
        const rec = childRecord(roleId)
        return rec && rec.alignment !== undefined ? String(rec.alignment) : authored
    }
    function childAnchor(roleId) {
        const rec = childRecord(roleId)
        return rec && rec.anchor !== undefined ? String(rec.anchor) : ""
    }
    readonly property bool headerFlipped: childAlignment("header", "left") === "right"
    function semanticArtworkOffsetX() {
        const raw = childOffsetX("artwork")
        return headerFlipped ? -raw : raw
    }
    customEditableChildRoles: [
        {"roleId": "header", "target": headerFrame,
         "normalizationTarget": feedRoot,
         "normalizationWidthProperty": "childNormalizationWidth",
         "normalizationHeightProperty": "childNormalizationHeight",
         "semanticCornerInsetX": 0.0,
         "semanticCornerInsetY": 0.0,
         "containmentTarget": feedRoot},
        {"roleId": "refresh", "target": refreshTarget,
         "normalizationTarget": feedRoot,
         "normalizationWidthProperty": "childNormalizationWidth",
         "normalizationHeightProperty": "childNormalizationHeight",
         "containmentTarget": feedRoot},
        {"roleId": "articles", "target": body,
         "normalizationTarget": feedRoot,
         "normalizationWidthProperty": "childNormalizationWidth",
         "normalizationHeightProperty": "childNormalizationHeight",
         "containmentTarget": feedRoot,
         "collisionIgnoreRoleIds": ["artwork"],
         "geometryDependencies": [body, listColumn, grid]},
        {"roleId": "artwork", "target": customArtworkRoleTarget,
         "normalizationTarget": feedRoot,
         "normalizationWidthProperty": "childNormalizationWidth",
         "normalizationHeightProperty": "childNormalizationHeight",
         "containmentTarget": body,
         "collisionIgnoreRoleIds": ["articles"],
         "geometryDependencies": [body, listColumn, grid]},
        {"roleId": "overflow", "target": footer,
         "normalizationTarget": feedRoot,
         "normalizationWidthProperty": "childNormalizationWidth",
         "normalizationHeightProperty": "childNormalizationHeight",
         "containmentTarget": feedRoot}
    ]

    readonly property real pad: 10.0
    readonly property bool hasHeaderSubtitle: feedModel.showSubtitle
        && feedModel.feedTitle.length > 0
        && feedModel.feedTitle.toUpperCase() !== feedModel.displayName.toUpperCase()
    // The subtitle is set in points, so its box comes from the font's real
    // line height, never ``fontSize`` read as pixels: a box shorter than the
    // line lets vertically centred glyphs climb out of it toward the pill.
    readonly property font subtitleFont: Qt.font({
        "family": feedModel.fontFamily,
        "pointSize": Math.max(8.5, feedModel.fontSize - 3.0)
    })
    FontMetrics {
        id: subtitleMetrics
        font: feedRoot.subtitleFont
    }
    readonly property real subtitleHeight: hasHeaderSubtitle
        ? Math.ceil(subtitleMetrics.height) : 0.0
    // NEWS rows name their publisher beside the age; the list rail widens to
    // that text. CUSTOM rows keep the fixed age rail.
    FontMetrics {
        id: metaMetrics
        font.family: feedRoot.feedModel.fontFamily
        font.pixelSize: Math.max(8.0, feedRoot.feedModel.fontSize - 3.0)
    }
    function rowMetaText(author, age) {
        if (!feedModel.showSourceAttribution || author.length === 0)
            return age
        return age.length > 0 ? author.toUpperCase() + " · " + age : author.toUpperCase()
    }
    readonly property real subtitleGap: 2.5
    readonly property real headerHeight: Math.max(
        36.0, headerFrame.implicitHeight * childWidthScale("header")
    ) + (hasHeaderSubtitle ? subtitleHeight + subtitleGap : 0.0)
    readonly property real bodyTop: headerArea.height + 8.0
    // A tiny fixed footer is always budgeted so status/overflow text can never
    // paint over the final feed row. Keeping the reserve unconditional also
    // avoids a capacity <-> footer-visibility binding cycle.
    readonly property real footerHeight: Math.max(16.0, feedModel.fontSize * 1.15)
    // Children live in OverlayCard's padded content surface, not directly in
    // OverlayWidget.  Use that real retained surface for reflow/containment so
    // independent X/Y CUSTOM extents cannot create an unreachable dead strip.
    readonly property real layoutWidth: Math.max(0.0, headerArea.width)
    readonly property real layoutHeight: Math.max(0.0,
        headerArea.parent ? headerArea.parent.height : height)
    readonly property real bodyHeight: Math.max(0.0,
        layoutHeight - bodyTop - footerHeight)
    readonly property real listSpacing: 3.0
    readonly property real listRowHeight: feedModel.viewMode === "compact"
        ? Math.max(30.0, feedModel.fontSize * 2.15)
        : Math.max(50.0, feedModel.fontSize * 3.55)
    readonly property int listCapacity: Math.max(1, Math.floor(
        (body.height + listSpacing) / Math.max(1.0, listRowHeight + listSpacing)))
    readonly property real gridSpacing: 6.0
    // Reserve an image-capable cell from Settings, not current image readiness.
    // Readiness-dependent height would make geometry capacity oscillate.
    readonly property real gridCellHeight: feedModel.showImages
        ? Math.max(152.0, feedModel.fontSize * 8.8)
        : Math.max(84.0, feedModel.fontSize * 5.5)
    readonly property int gridColumns: Math.max(1, Math.min(4, Math.floor(
        (Math.max(1.0, body.width) + gridSpacing) / (240.0 + gridSpacing))))
    readonly property int gridRowCapacity: Math.max(1, Math.floor(
        (body.height + gridSpacing) / Math.max(1.0, gridCellHeight + gridSpacing)))
    readonly property int gridVisibleCount: Math.min(
        feedModel.rowCount, gridColumns * gridRowCapacity
    )
    readonly property int gridVisibleRows: gridVisibleCount > 0
        ? Math.max(1, Math.ceil(gridVisibleCount / Math.max(1, gridColumns))) : 0
    // When the Grid fills its current row capacity, consume the harmless
    // remainder across those already-admitted rows instead of leaving a dead
    // strip at the bottom. This
    // is retained geometry only: capacity still derives from the minimum cell
    // height and never republishes rows or performs source work.
    readonly property real renderedGridCellHeight:
        gridVisibleRows > 0 && gridVisibleRows === gridRowCapacity
            ? Math.max(gridCellHeight,
                (body.height - gridSpacing * Math.max(0, gridVisibleRows - 1))
                    / gridVisibleRows)
            : gridCellHeight
    readonly property int visibleCapacity: feedModel.viewMode === "grid"
        ? gridColumns * gridRowCapacity : listCapacity
    readonly property int overflowCount: Math.max(0, feedModel.rowCount - visibleCapacity)
    // Geometry only changes delegate visibility. No QML -> Python callback,
    // row-model reset, cache access or re-publication occurs during resize.

    Item {
        id: headerArea
        objectName: "feedHeaderArea"
        x: 0
        y: 0
        width: parent.width
        height: feedRoot.headerHeight

        BrandedHeader {
            id: headerFrame
            objectName: "feedHeader"
            frameObjectName: "feedHeaderFrame"
            logoObjectName: "feedHeaderLogo"
            textObjectName: "feedHeaderText"
            readonly property string customAnchor: feedRoot.childAnchor("header")
            readonly property real customScale: feedRoot.childWidthScale("header")
            property real customEditPlacementCompensationX:
                customAnchor.length > 0 || feedRoot.headerFlipped
                    ? x - feedRoot.childOffsetX("header") : 0.0
            property real customEditPlacementCompensationY: customAnchor.length > 0
                ? y - feedRoot.childOffsetY("header") : 0.0
            transformOrigin: Item.TopLeft
            scale: customScale
            x: customAnchor.endsWith("right")
                ? headerArea.width - width * scale
                : (customAnchor.endsWith("left") ? 0.0
                    : (feedRoot.headerFlipped ? headerArea.width - width * scale : 0.0)
                        + feedRoot.childOffsetX("header"))
            y: customAnchor.startsWith("bottom")
                ? headerArea.height
                    - (feedRoot.hasHeaderSubtitle
                        ? feedRoot.subtitleHeight + feedRoot.subtitleGap : 0.0)
                    - height * scale
                : (customAnchor.startsWith("top") ? 0.0 : feedRoot.childOffsetY("header"))
            contentReversed: feedRoot.headerFlipped
            label: feedRoot.feedModel.displayName
            logoSource: feedRoot.feedModel.monogramSource
            interactionEnabled: feedRoot.feedModel.interactionEnabled
                && feedRoot.feedModel.homeUrl.length > 0
                && !feedRoot.customLayoutInputBlocked
            fillColor: feedRoot.feedModel.headerFillColor
            borderColor: feedRoot.feedModel.headerBorderColor
            borderWidth: feedRoot.scaleAwareHeaderStrokeWidth(
                feedRoot.feedModel.headerBorderWidth
            )
            textColor: feedRoot.feedModel.headerTextColor
            fontFamily: feedRoot.feedModel.fontFamily
            textShadowEnabled: feedRoot.feedModel.textShadowEnabled
            textShadowColor: feedRoot.feedModel.textShadowColor
            textShadowOffsetX: feedRoot.feedModel.textShadowOffsetX
            textShadowOffsetY: feedRoot.feedModel.textShadowOffsetY
            shadowEnabled: feedRoot.cardShadowEnabled
            shadowColor: Qt.rgba(
                feedRoot.cardShadowColor.r, feedRoot.cardShadowColor.g,
                feedRoot.cardShadowColor.b, feedRoot.cardShadowColor.a * 0.45
            )
            shadowBlur: Math.max(2.0, Math.min(6.0, feedRoot.cardShadowBlur * 0.25))
            shadowOffsetX: feedRoot.cardShadowOffsetX * 1.15
            shadowOffsetY: feedRoot.cardShadowOffsetY * 1.15
            onActivated: feedRoot.openItemRequested(feedRoot.feedModel.homeUrl)
        }

        // Publisher/feed metadata is deliberately *outside* the branded pill.
        // It follows the semantic header rail, stays visually secondary, and
        // never inflates the shared BrandedHeader or its CUSTOM hit geometry.
        // Every feed string is plain text: publishers' titles are data, so a
        // literal "<canvas>" stays text and no markup can load a remote image.
        ShadowedText {
            id: headerSubtitle
            textFormat: Text.PlainText
            objectName: "feedHeaderSubtitle"
            visible: feedRoot.hasHeaderSubtitle
            x: feedRoot.headerFlipped
                ? Math.max(0.0, headerFrame.x + headerFrame.width * headerFrame.scale - width)
                : Math.max(0.0, headerFrame.x)
            y: headerFrame.y + headerFrame.height * headerFrame.scale + feedRoot.subtitleGap
            width: Math.max(0.0, Math.min(headerArea.width * 0.62,
                headerArea.width - 4.0))
            height: feedRoot.subtitleHeight
            text: feedRoot.feedModel.feedTitle
            color: Qt.rgba(
                feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.70
            )
            font: feedRoot.subtitleFont
            horizontalAlignment: feedRoot.headerFlipped ? Text.AlignRight : Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            shadowEnabled: feedRoot.feedModel.textShadowEnabled
            shadowColor: feedRoot.feedModel.textShadowColor
            shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
            shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
        }

        Item {
            id: refreshTarget
            objectName: "feedRefreshTarget"
            width: 30.0 * feedRoot.childWidthScale("refresh")
            height: 30.0 * feedRoot.childHeightScale("refresh")
            x: Math.max(0.0, Math.min(headerArea.width - width,
                (feedRoot.headerFlipped ? 0.0 : headerArea.width - width)
                    + feedRoot.childOffsetX("refresh")))
            y: Math.max(0.0, Math.min(
                Math.max(0.0, headerFrame.height * headerFrame.scale - height),
                (headerFrame.height * headerFrame.scale - height) * 0.5
                    + feedRoot.childOffsetY("refresh")
            ))
            opacity: feedRoot.feedModel.interactionEnabled ? 0.9 : 0.45
            readonly property bool canActivate: visible
                && feedRoot.feedModel.interactionEnabled
                && !feedRoot.feedModel.refreshing
                && !feedRoot.customLayoutInputBlocked

            Rectangle {
                objectName: "feedRefreshHoverFrame"
                anchors.fill: parent
                radius: 6.0
                color: refreshHover.hovered && refreshTarget.canActivate
                    ? Qt.rgba(1.0, 1.0, 1.0, 0.11)
                    : "transparent"
            }
            HoverHandler {
                id: refreshHover
                enabled: refreshTarget.canActivate
                blocking: false
                cursorShape: Qt.PointingHandCursor
            }

            Canvas {
                id: refreshCanvas
                anchors.fill: parent
                onPaint: {
                    const ctx = getContext("2d")
                    ctx.reset()
                    ctx.strokeStyle = feedRoot.feedModel.headerTextColor
                    ctx.globalAlpha = refreshHover.hovered && refreshTarget.canActivate ? 1.0 : 0.78
                    ctx.lineWidth = 1.7
                    ctx.lineCap = "round"
                    ctx.beginPath()
                    ctx.arc(width / 2, height / 2, 7.0, -0.4, 4.8)
                    ctx.stroke()
                    ctx.beginPath()
                    ctx.moveTo(width / 2 + 6.5, height / 2 - 4.0)
                    ctx.lineTo(width / 2 + 8.0, height / 2 + 0.4)
                    ctx.lineTo(width / 2 + 3.5, height / 2 - 0.3)
                    ctx.stroke()
                }
                Connections {
                    target: feedRoot.feedModel
                    function onStateChanged() { refreshCanvas.requestPaint() }
                }
                Connections {
                    target: refreshHover
                    function onHoveredChanged() { refreshCanvas.requestPaint() }
                }
            }

            TapHandler {
                enabled: refreshTarget.canActivate
                acceptedButtons: Qt.LeftButton
                onTapped: feedRoot.refreshRequested()
            }
        }
    }

    Rectangle {
        id: divider
        x: 0
        y: feedRoot.bodyTop - 8.0
        width: parent.width
        height: Math.max(1.0, feedRoot.scaleAwareHeaderStrokeWidth(1.0))
        color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                       feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.20)
    }

    Item {
        id: body
        objectName: "feedBody"
        x: feedRoot.childOffsetX("articles")
        y: feedRoot.bodyTop + feedRoot.childOffsetY("articles")
        width: Math.max(0.0, Math.min(feedRoot.layoutWidth - x,
            feedRoot.layoutWidth * feedRoot.childWidthScale("articles")))
        height: Math.max(0.0, Math.min(feedRoot.layoutHeight - y - feedRoot.footerHeight,
            feedRoot.bodyHeight * feedRoot.childHeightScale("articles")))
        clip: true

        Column {
            id: listColumn
            width: parent.width
            spacing: feedRoot.listSpacing
            visible: feedRoot.feedModel.viewMode !== "grid"

            Repeater {
                model: feedRoot.feedModel.rowModel

                delegate: Item {
                    id: listRow
                    required property int index
                    required property string feedItemId
                    required property string feedTitle
                    required property string feedSummary
                    required property string feedAuthor
                    required property string feedAge
                    required property string feedUrl
                    required property string feedImageSource
                    visible: index < feedRoot.listCapacity
                    width: listColumn.width
                    height: visible ? feedRoot.listRowHeight : 0.0
                    readonly property bool canActivate: visible
                        && feedRoot.feedModel.interactionEnabled
                        && feedUrl.length > 0
                    readonly property bool hasArt: visible
                        && feedRoot.feedModel.viewMode === "list"
                        && feedImageSource.length > 0 && width >= 260.0
                    readonly property real artworkMargin: 3.0
                    readonly property real canonicalArtworkSize:
                        Math.min(54.0, Math.max(1.0, height - artworkMargin * 2.0))
                    readonly property real artworkWidth: hasArt ? Math.max(18.0, Math.min(
                        width * 0.42,
                        canonicalArtworkSize * feedRoot.childWidthScale("artwork")
                    )) : 0.0
                    readonly property real artworkHeight: hasArt ? Math.max(18.0, Math.min(
                        Math.max(18.0, height - artworkMargin * 2.0),
                        canonicalArtworkSize * feedRoot.childHeightScale("artwork")
                    )) : 0.0
                    readonly property real authoredArtworkX: feedRoot.headerFlipped
                        ? artworkMargin : width - artworkMargin - artworkWidth
                    readonly property real artworkX: hasArt ? Math.max(artworkMargin, Math.min(
                        width - artworkMargin - artworkWidth,
                        authoredArtworkX + feedRoot.semanticArtworkOffsetX()
                    )) : 0.0
                    readonly property real artworkY: hasArt ? Math.max(artworkMargin, Math.min(
                        height - artworkMargin - artworkHeight,
                        artworkMargin + feedRoot.childOffsetY("artwork")
                    )) : 0.0
                    readonly property real contentLeft: hasArt && feedRoot.headerFlipped
                        ? artworkX + artworkWidth + 6.0 : 8.0
                    readonly property real contentRight: hasArt && !feedRoot.headerFlipped
                        ? artworkX - 6.0 : width - 8.0
                    readonly property string metaText: feedRoot.rowMetaText(feedAuthor, feedAge)
                    readonly property real ageWidth: feedRoot.feedModel.showSourceAttribution
                        ? Math.min(
                            Math.max(48.0, Math.ceil(metaMetrics.advanceWidth(metaText)) + 2.0),
                            Math.max(48.0, (contentRight - contentLeft) * 0.45))
                        : Math.min(
                            Math.max(48.0, feedRoot.feedModel.fontSize * 4.6),
                            Math.max(48.0, (contentRight - contentLeft) * 0.30))
                    readonly property real ageX: feedRoot.headerFlipped
                        ? contentLeft : Math.max(contentLeft, contentRight - ageWidth)
                    readonly property real titleX: feedRoot.headerFlipped
                        ? Math.min(contentRight, ageX + ageWidth + 6.0) : contentLeft
                    readonly property real titleRight: feedRoot.headerFlipped
                        ? contentRight : Math.max(contentLeft, ageX - 6.0)

                    // Text-dense list rows use the same surface-only hover
                    // language as Reddit/Gmail. A stroke at compact sizes reads
                    // as content decoration and can intersect text rails.
                    Rectangle {
                        objectName: "feedListHoverFrame" + index
                        anchors.fill: parent
                        anchors.margins: 2.0
                        radius: 4.0
                        color: listHover.hovered && listRow.canActivate
                            ? Qt.rgba(1.0, 1.0, 1.0, 0.065)
                            : "transparent"
                        border.width: 0.0
                    }
                    HoverHandler {
                        id: listHover
                        enabled: parent.canActivate
                        blocking: false
                        cursorShape: Qt.PointingHandCursor
                    }

                    Rectangle {
                        id: listArtworkFrame
                        objectName: "feedListArtworkFrame" + index
                        visible: listRow.hasArt
                        x: listRow.artworkX
                        y: listRow.artworkY
                        width: listRow.artworkWidth
                        height: listRow.artworkHeight
                        radius: 3.0
                        clip: true
                        color: "transparent"
                        // Artwork-frame contract: inside the outline's stroke on a
                        // concentric rounded mask; the outline paints on top.
                        readonly property real imageInset: feedRoot.scaleAwareStrokeWidth(0.75)
                        Image {
                            objectName: "feedListArtwork" + index
                            anchors.fill: parent
                            anchors.margins: listArtworkFrame.imageInset
                            source: parent.visible ? feedImageSource : ""
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                            layer.enabled: listArtworkFrame.visible
                            layer.effect: MultiEffect {
                                maskEnabled: true
                                maskSource: listArtworkMask
                            }
                        }
                        Rectangle {
                            id: listArtworkMask
                            anchors.fill: parent
                            anchors.margins: listArtworkFrame.imageInset
                            radius: Math.max(0.0, listArtworkFrame.radius - listArtworkFrame.imageInset)
                            visible: false
                            layer.enabled: listArtworkFrame.visible
                        }
                        Rectangle {
                            anchors.fill: parent
                            radius: parent.radius
                            color: "transparent"
                            border.color: listHover.hovered && listRow.canActivate
                                ? "white" : feedRoot.feedModel.headerBorderColor
                            border.width: feedRoot.scaleAwareStrokeWidth(0.75)
                        }
                    }
                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: feedRoot.scaleAwareStrokeWidth(1.0)
                        color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                                       feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.12)
                    }

                    ShadowedText {
                        id: listTitle
                        textFormat: Text.PlainText
                        x: listRow.titleX
                        y: 4.0
                        width: Math.max(0.0, listRow.titleRight - x)
                        height: Math.max(18.0, implicitHeight)
                        text: feedTitle
                        color: feedRoot.feedModel.textColor
                        font.family: feedRoot.feedModel.fontFamily
                        font.pixelSize: feedRoot.feedModel.fontSize
                        font.bold: true
                        horizontalAlignment: feedRoot.headerFlipped ? Text.AlignRight : Text.AlignLeft
                        elide: Text.ElideRight
                        maximumLineCount: feedRoot.feedModel.viewMode === "compact" ? 1 : 2
                        wrap: true
                        shadowEnabled: feedRoot.feedModel.textShadowEnabled
                        shadowColor: feedRoot.feedModel.textShadowColor
                        shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
                        shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
                    }

                    ShadowedText {
                        id: ageText
                        textFormat: Text.PlainText
                        x: listRow.ageX
                        y: 5.0
                        width: listRow.ageWidth
                        height: Math.max(16.0, implicitHeight)
                        text: listRow.metaText
                        elide: feedRoot.feedModel.showSourceAttribution ? Text.ElideRight : Text.ElideNone
                        color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                                       feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.58)
                        font.family: feedRoot.feedModel.fontFamily
                        font.pixelSize: Math.max(8.0, feedRoot.feedModel.fontSize - 3.0)
                        horizontalAlignment: feedRoot.headerFlipped ? Text.AlignLeft : Text.AlignRight
                        shadowEnabled: feedRoot.feedModel.textShadowEnabled
                        shadowColor: feedRoot.feedModel.textShadowColor
                        shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
                        shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
                    }

                    ShadowedText {
                        textFormat: Text.PlainText
                        x: listRow.titleX
                        y: listTitle.y + listTitle.height + 2.0
                        width: Math.max(0.0, listRow.titleRight - x)
                        height: Math.max(0.0, listRow.height - y - 3.0)
                        visible: feedRoot.feedModel.viewMode !== "compact"
                            && text.length > 0 && height >= 11.0
                        text: feedSummary
                        color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                                       feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.70)
                        font.family: feedRoot.feedModel.fontFamily
                        font.pixelSize: Math.max(9.0, feedRoot.feedModel.fontSize - 2.0)
                        horizontalAlignment: feedRoot.headerFlipped ? Text.AlignRight : Text.AlignLeft
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        shadowEnabled: feedRoot.feedModel.textShadowEnabled
                        shadowColor: feedRoot.feedModel.textShadowColor
                        shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
                        shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
                    }

                    TapHandler {
                        enabled: listRow.canActivate
                        acceptedButtons: Qt.LeftButton
                        onTapped: feedRoot.openItemRequested(feedUrl)
                    }
                }
            }
        }

        Grid {
            id: grid
            visible: feedRoot.feedModel.viewMode === "grid"
            width: parent.width
            columns: feedRoot.gridColumns
            spacing: feedRoot.gridSpacing
            layoutDirection: feedRoot.headerFlipped ? Qt.RightToLeft : Qt.LeftToRight

            Repeater {
                model: feedRoot.feedModel.rowModel
                delegate: Rectangle {
                    id: gridCard
                    objectName: "feedGridCard" + index
                    required property int index
                    required property string feedItemId
                    required property string feedTitle
                    required property string feedSummary
                    required property string feedAuthor
                    required property string feedAge
                    required property string feedUrl
                    required property string feedImageSource
                    visible: index < feedRoot.visibleCapacity
                    width: (grid.width - grid.spacing * Math.max(0, grid.columns - 1))
                        / Math.max(1, grid.columns)
                    height: visible ? feedRoot.renderedGridCellHeight : 0.0
                    radius: 5.0
                    color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                                   feedRoot.feedModel.textColor.b, 0.055)
                    border.color: gridHover.hovered && canActivate
                        ? "white" : feedRoot.feedModel.headerBorderColor
                    border.width: gridHover.hovered && canActivate
                        ? feedRoot.scaleAwareStrokeWidth(1.25) : feedRoot.scaleAwareStrokeWidth(1.0)
                    readonly property bool hasArt: visible && feedImageSource.length > 0
                    readonly property bool canActivate: visible
                        && feedRoot.feedModel.interactionEnabled
                        && feedUrl.length > 0
                    readonly property real contentMargin: 8.0
                    readonly property real artworkMargin: 7.0
                    readonly property real textGap: 6.0
                    // The age rail owns the final 26 px. Artwork may move/resize
                    // freely inside the remaining card surface but never paints
                    // through that stable semantic footer.
                    readonly property real contentBottom: Math.max(contentMargin, height - 26.0)
                    readonly property real canonicalArtworkWidth:
                        Math.max(1.0, width - artworkMargin * 2.0)
                    readonly property real canonicalArtworkHeight:
                        Math.max(1.0, feedRoot.gridCellHeight * 0.50)
                    readonly property real artworkWidth: hasArt ? Math.max(24.0, Math.min(
                        Math.max(24.0, width - artworkMargin * 2.0),
                        canonicalArtworkWidth * feedRoot.childWidthScale("artwork")
                    )) : 0.0
                    readonly property real artworkHeight: hasArt ? Math.max(24.0, Math.min(
                        Math.max(24.0, contentBottom - artworkMargin),
                        canonicalArtworkHeight * feedRoot.childHeightScale("artwork")
                    )) : 0.0
                    readonly property real authoredArtworkX: feedRoot.headerFlipped
                        ? width - artworkMargin - artworkWidth : artworkMargin
                    readonly property real artworkX: hasArt ? Math.max(artworkMargin, Math.min(
                        width - artworkMargin - artworkWidth,
                        authoredArtworkX + feedRoot.semanticArtworkOffsetX()
                    )) : 0.0
                    readonly property real artworkMaxY: Math.max(
                        artworkMargin, contentBottom - artworkHeight
                    )
                    readonly property real artworkY: hasArt ? Math.max(artworkMargin, Math.min(
                        artworkMaxY,
                        artworkMargin + feedRoot.childOffsetY("artwork")
                    )) : 0.0

                    // Reflow around the edited image rectangle instead of owning
                    // one hard-coded landscape slot. Pick the largest usable text
                    // region among left/right/above/below; resizing or moving the
                    // shared artwork child therefore changes both text room and
                    // how much summary/title can be shown, with no model reset.
                    readonly property real fullTextWidth: Math.max(
                        0.0, width - contentMargin * 2.0
                    )
                    readonly property real fullTextHeight: Math.max(
                        0.0, contentBottom - contentMargin
                    )
                    readonly property real leftTextRail: hasArt ? Math.max(
                        0.0, artworkX - textGap - contentMargin
                    ) : 0.0
                    readonly property real rightTextRail: hasArt ? Math.max(
                        0.0, width - contentMargin
                            - (artworkX + artworkWidth + textGap)
                    ) : 0.0
                    readonly property real topTextRail: hasArt ? Math.max(
                        0.0, artworkY - textGap - contentMargin
                    ) : 0.0
                    readonly property real bottomTextRail: hasArt ? Math.max(
                        0.0, contentBottom
                            - (artworkY + artworkHeight + textGap)
                    ) : 0.0
                    readonly property real sideRailMinimum: Math.max(86.0, width * 0.31)
                    readonly property real verticalRailMinimum: Math.max(
                        28.0, feedRoot.feedModel.fontSize * 2.2
                    )
                    readonly property real leftTextArea: leftTextRail >= sideRailMinimum
                        ? leftTextRail * fullTextHeight : -1.0
                    readonly property real rightTextArea: rightTextRail >= sideRailMinimum
                        ? rightTextRail * fullTextHeight : -1.0
                    readonly property real topTextArea: topTextRail >= verticalRailMinimum
                        ? fullTextWidth * topTextRail : -1.0
                    readonly property real bottomTextArea: bottomTextRail >= verticalRailMinimum
                        ? fullTextWidth * bottomTextRail : -1.0
                    readonly property string textRegion: {
                        if (!hasArt) return "full"
                        let best = bottomTextArea
                        let region = "bottom"
                        if (topTextArea > best) { best = topTextArea; region = "top" }
                        if (leftTextArea > best) { best = leftTextArea; region = "left" }
                        if (rightTextArea > best) { best = rightTextArea; region = "right" }
                        return best >= 0.0 ? region : "bottom"
                    }
                    readonly property bool sideText:
                        textRegion === "left" || textRegion === "right"
                    readonly property real textX: textRegion === "right"
                        ? artworkX + artworkWidth + textGap : contentMargin
                    readonly property real textWidth: textRegion === "left"
                        ? leftTextRail : textRegion === "right"
                            ? rightTextRail : fullTextWidth
                    readonly property real textTop: textRegion === "bottom"
                        ? Math.min(contentBottom, artworkY + artworkHeight + textGap)
                        : contentMargin
                    readonly property real textHeight: textRegion === "top"
                        ? topTextRail : textRegion === "bottom"
                            ? bottomTextRail : fullTextHeight
                    readonly property real textBottom: textTop + textHeight

                    HoverHandler {
                        id: gridHover
                        enabled: parent.canActivate
                        blocking: false
                        cursorShape: Qt.PointingHandCursor
                    }

                    Rectangle {
                        id: gridArtworkFrame
                        objectName: "feedGridArtworkFrame" + index
                        visible: gridCard.hasArt
                        x: gridCard.artworkX
                        y: gridCard.artworkY
                        width: gridCard.artworkWidth
                        height: gridCard.artworkHeight
                        radius: 3.0
                        clip: true
                        color: "transparent"
                        // Artwork-frame contract: inside the outline's stroke on a
                        // concentric rounded mask; the outline paints on top.
                        readonly property real imageInset: feedRoot.scaleAwareStrokeWidth(0.75)
                        Image {
                            objectName: "feedGridArtwork" + index
                            anchors.fill: parent
                            anchors.margins: gridArtworkFrame.imageInset
                            source: parent.visible ? feedImageSource : ""
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                            layer.enabled: gridArtworkFrame.visible
                            layer.effect: MultiEffect {
                                maskEnabled: true
                                maskSource: gridArtworkMask
                            }
                        }
                        Rectangle {
                            id: gridArtworkMask
                            anchors.fill: parent
                            anchors.margins: gridArtworkFrame.imageInset
                            radius: Math.max(0.0, gridArtworkFrame.radius - gridArtworkFrame.imageInset)
                            visible: false
                            layer.enabled: gridArtworkFrame.visible
                        }
                        Rectangle {
                            anchors.fill: parent
                            radius: parent.radius
                            color: "transparent"
                            border.color: gridHover.hovered && gridCard.canActivate
                                ? "white" : feedRoot.feedModel.headerBorderColor
                            border.width: feedRoot.scaleAwareStrokeWidth(0.75)
                        }
                    }

                    ShadowedText {
                        id: gridTitle
                        textFormat: Text.PlainText
                        x: gridCard.textX
                        y: gridCard.textTop
                        width: gridCard.textWidth
                        height: Math.max(0.0, Math.min(
                            gridCard.textHeight,
                            Math.max(22.0, feedRoot.feedModel.fontSize *
                                (gridCard.sideText ? 3.2 : 2.7))
                        ))
                        text: feedTitle
                        color: feedRoot.feedModel.textColor
                        font.family: feedRoot.feedModel.fontFamily
                        font.pixelSize: feedRoot.feedModel.fontSize
                        font.bold: true
                        fontSizeMode: Text.Fit
                        minimumPointSize: Math.max(7.5, feedRoot.feedModel.fontSize * 0.68)
                        horizontalAlignment: feedRoot.headerFlipped ? Text.AlignRight : Text.AlignLeft
                        verticalAlignment: Text.AlignTop
                        wrap: true
                        maximumLineCount: gridCard.textHeight >= feedRoot.feedModel.fontSize * 4.8
                            ? 3 : gridCard.textHeight >= feedRoot.feedModel.fontSize * 2.4
                                ? 2 : 1
                        elide: Text.ElideRight
                        shadowEnabled: feedRoot.feedModel.textShadowEnabled
                        shadowColor: feedRoot.feedModel.textShadowColor
                        shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
                        shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
                    }

                    ShadowedText {
                        id: gridSummary
                        textFormat: Text.PlainText
                        x: gridCard.textX
                        y: gridTitle.y + gridTitle.height + 2.0
                        width: gridCard.textWidth
                        height: Math.max(0.0, gridCard.textBottom - y)
                        visible: feedSummary.length > 0 && height >= 18.0
                        text: feedSummary
                        color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                                       feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.68)
                        font.family: feedRoot.feedModel.fontFamily
                        font.pixelSize: Math.max(9.0, feedRoot.feedModel.fontSize - 2.0)
                        fontSizeMode: Text.Fit
                        minimumPointSize: 7.0
                        horizontalAlignment: feedRoot.headerFlipped ? Text.AlignRight : Text.AlignLeft
                        verticalAlignment: Text.AlignTop
                        wrap: true
                        maximumLineCount: height >= 42.0 ? 3 : 2
                        elide: Text.ElideRight
                        shadowEnabled: feedRoot.feedModel.textShadowEnabled
                        shadowColor: feedRoot.feedModel.textShadowColor
                        shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
                        shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
                    }

                    ShadowedText {
                        id: gridAge
                        textFormat: Text.PlainText
                        x: gridCard.contentMargin
                        y: gridCard.height - 24.0
                        width: Math.max(0.0, gridCard.width - gridCard.contentMargin * 2.0)
                        height: 18.0
                        text: feedRoot.rowMetaText(feedAuthor, feedAge)
                        elide: feedRoot.feedModel.showSourceAttribution ? Text.ElideRight : Text.ElideNone
                        color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                                       feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.55)
                        font.family: feedRoot.feedModel.fontFamily
                        font.pixelSize: Math.max(8.0, feedRoot.feedModel.fontSize - 3.0)
                        horizontalAlignment: feedRoot.headerFlipped ? Text.AlignRight : Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                        shadowEnabled: feedRoot.feedModel.textShadowEnabled
                        shadowColor: feedRoot.feedModel.textShadowColor
                        shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
                        shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
                    }

                    TapHandler {
                        enabled: gridCard.canActivate
                        acceptedButtons: Qt.LeftButton
                        onTapped: feedRoot.openItemRequested(feedUrl)
                    }
                }
            }
        }

        // One stable representative edit target controls every repeated image.
        // It paints nothing and performs no source lookup.  Place it over the
        // first *actually admitted* local image, rather than blindly over row 0,
        // so sparse feeds such as NASA still present an honest artwork handle.
        // Every delegate consumes the same role geometry, keeping Edit cost
        // constant with feed size and volatile article IDs out of persistence.
        Item {
            id: customArtworkRoleTarget
            objectName: "feedCustomArtworkRoleTarget"
            readonly property bool gridMode: feedRoot.feedModel.viewMode === "grid"
            readonly property int sourceIndex: feedRoot.feedModel.firstArtworkRowIndex
            readonly property int visibleLimit: gridMode
                ? feedRoot.visibleCapacity : feedRoot.listCapacity
            visible: feedRoot.feedModel.showImages
                && feedRoot.feedModel.viewMode !== "compact"
                && sourceIndex >= 0 && sourceIndex < visibleLimit
                // List suppresses artwork below its authored 260 px admission
                // floor. Keep the Edit proxy honest there too: a selected child
                // may never float over a row whose image is not actually painted.
                && (gridMode || body.width >= 260.0)
            enabled: false
            readonly property real gridCardWidth: Math.max(1.0,
                (body.width - feedRoot.gridSpacing * Math.max(0, feedRoot.gridColumns - 1))
                    / Math.max(1, feedRoot.gridColumns))
            readonly property real gridCardHeight: feedRoot.renderedGridCellHeight
            readonly property real gridCanonicalWidth: Math.max(1.0, gridCardWidth - 14.0)
            readonly property real gridCanonicalHeight: Math.max(
                1.0, feedRoot.gridCellHeight * 0.50
            )
            readonly property real listCanonicalSize: Math.min(
                54.0, Math.max(1.0, feedRoot.listRowHeight - 6.0)
            )
            width: gridMode
                ? Math.max(24.0, Math.min(
                    Math.max(24.0, gridCardWidth - 14.0),
                    gridCanonicalWidth * feedRoot.childWidthScale("artwork")
                ))
                : Math.max(18.0, Math.min(
                    body.width * 0.42,
                    listCanonicalSize * feedRoot.childWidthScale("artwork")
                ))
            height: gridMode
                ? Math.max(24.0, Math.min(
                    Math.max(24.0, gridCardHeight - 33.0),
                    gridCanonicalHeight * feedRoot.childHeightScale("artwork")
                ))
                : Math.max(18.0, Math.min(
                    Math.max(18.0, feedRoot.listRowHeight - 6.0),
                    listCanonicalSize * feedRoot.childHeightScale("artwork")
                ))
            readonly property real hostWidth: gridMode ? gridCardWidth : body.width
            readonly property real hostHeight: gridMode
                ? gridCardHeight : feedRoot.listRowHeight
            readonly property real margin: gridMode ? 7.0 : 3.0
            readonly property int logicalColumn: gridMode
                ? sourceIndex % Math.max(1, feedRoot.gridColumns) : 0
            readonly property int visualColumn: gridMode && feedRoot.headerFlipped
                ? Math.max(0, feedRoot.gridColumns - 1 - logicalColumn)
                : logicalColumn
            readonly property int hostRow: gridMode
                ? Math.floor(sourceIndex / Math.max(1, feedRoot.gridColumns))
                : sourceIndex
            readonly property real hostX: gridMode
                ? visualColumn * (gridCardWidth + feedRoot.gridSpacing) : 0.0
            readonly property real hostY: gridMode
                ? hostRow * (gridCardHeight + feedRoot.gridSpacing)
                : hostRow * (feedRoot.listRowHeight + feedRoot.listSpacing)
            readonly property real authoredLocalX: feedRoot.headerFlipped
                ? hostWidth - margin - width : margin
            readonly property real localMaxY: gridMode
                ? Math.max(margin, hostHeight - 26.0 - height)
                : Math.max(margin, hostHeight - margin - height)
            x: hostX + Math.max(margin, Math.min(
                hostWidth - margin - width,
                authoredLocalX + feedRoot.semanticArtworkOffsetX()
            ))
            y: hostY + Math.max(margin, Math.min(
                localMaxY,
                margin + feedRoot.childOffsetY("artwork")
            ))
        }

        ShadowedText {
            textFormat: Text.PlainText
            anchors.centerIn: parent
            visible: feedRoot.feedModel.viewState === "loading" ||
                     feedRoot.feedModel.viewState === "empty" ||
                     feedRoot.feedModel.viewState === "error" ||
                     feedRoot.feedModel.viewState === "missing"
            text: feedRoot.feedModel.viewState === "loading" ? "LOADING FEED…"
                : feedRoot.feedModel.viewState === "empty" ? "NO FEED ITEMS"
                : feedRoot.feedModel.viewState === "missing" ? "CONFIGURE FEED IN SETTINGS"
                : "FEED UNAVAILABLE"
            color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                           feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.72)
            font.family: feedRoot.feedModel.fontFamily
            font.pixelSize: Math.max(10.0, feedRoot.feedModel.fontSize - 1.0)
            shadowEnabled: feedRoot.feedModel.textShadowEnabled
            shadowColor: feedRoot.feedModel.textShadowColor
            shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
            shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
        }
    }

    ShadowedText {
        id: footer
        textFormat: Text.PlainText
        objectName: "feedOverflowSummary"
        x: feedRoot.childOffsetX("overflow")
        y: feedRoot.layoutHeight - feedRoot.footerHeight + feedRoot.childOffsetY("overflow")
        width: Math.max(0.0, Math.min(feedRoot.layoutWidth - x,
            feedRoot.layoutWidth * feedRoot.childWidthScale("overflow")))
        height: Math.max(0.0, Math.min(feedRoot.layoutHeight - y,
            feedRoot.footerHeight * feedRoot.childHeightScale("overflow")))
        verticalAlignment: Text.AlignVCenter
        visible: feedRoot.feedModel.viewState === "ready"
            && (feedRoot.feedModel.statusText.length > 0 || feedRoot.overflowCount > 0)
        text: {
            const overflow = feedRoot.overflowCount > 0 ? "+" + feedRoot.overflowCount + " MORE" : ""
            if (feedRoot.feedModel.statusText.length > 0 && overflow.length > 0)
                return feedRoot.feedModel.statusText + "  ·  " + overflow
            return feedRoot.feedModel.statusText.length > 0 ? feedRoot.feedModel.statusText : overflow
        }
        color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                       feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.58)
        font.family: feedRoot.feedModel.fontFamily
        font.pixelSize: Math.max(8.0, feedRoot.feedModel.fontSize - 4.0)
        horizontalAlignment: feedRoot.headerFlipped ? Text.AlignLeft : Text.AlignRight
        shadowEnabled: feedRoot.feedModel.textShadowEnabled
        shadowColor: feedRoot.feedModel.textShadowColor
        shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
        shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
    }
}
