import QtQuick

// G2 presentation contract. Currently instantiated only by isolated Qt tests:
// shared Steam source/lease, verified article actions, and safe artwork admission
// are required before enabling the existing steam_progress product slot.
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

    function childRecord(roleId) {
        return childGeometry ? childGeometry[roleId] : null
    }
    function childWidthScale(roleId) {
        const record = childRecord(roleId)
        return record && record.width_scale !== undefined
            ? Number(record.width_scale) : 1.0
    }
    function childHeightScale(roleId) {
        const record = childRecord(roleId)
        return record && record.height_scale !== undefined
            ? Number(record.height_scale) : 1.0
    }
    function childOffsetX(roleId) {
        const record = childRecord(roleId)
        return (record && record.x_offset !== undefined ? Number(record.x_offset) : 0.0)
            * childNormalizationWidth
    }
    function childOffsetY(roleId) {
        const record = childRecord(roleId)
        return (record && record.y_offset !== undefined ? Number(record.y_offset) : 0.0)
            * childNormalizationHeight
    }
    function childAlignment(roleId, defaultValue) {
        const record = childRecord(roleId)
        return record && record.alignment !== undefined
            ? String(record.alignment) : defaultValue
    }

    // These objects and roles are NEVER built from accepted story rows, a
    // visible-count change, or a resizing extent. The shared CUSTOM owner may
    // move/scale each semantic group, not independently persist story slots.
    customEditableChildRoles: [
        {
            "roleId": "header", "normalizationTarget": followsRoot,
            "normalizationWidthProperty": "childNormalizationWidth",
            "normalizationHeightProperty": "childNormalizationHeight",
            "target": header,
            "semanticCornerInsetX": 14.0, "semanticCornerInsetY": 12.0,
            "semanticInsetUsesUniformCard": true
        },
        {
            "roleId": "refresh", "normalizationTarget": followsRoot,
            "normalizationWidthProperty": "childNormalizationWidth",
            "normalizationHeightProperty": "childNormalizationHeight",
            "target": refreshGlyph
        },
        {
            "roleId": "story_tiles", "normalizationTarget": followsRoot,
            "normalizationWidthProperty": "childNormalizationWidth",
            "normalizationHeightProperty": "childNormalizationHeight",
            "target": storyGroup
        },
        {
            "roleId": "overflow_summary", "normalizationTarget": followsRoot,
            "normalizationWidthProperty": "childNormalizationWidth",
            "normalizationHeightProperty": "childNormalizationHeight",
            "target": overflowSummary
        }
    ]

    BrandedHeader {
        id: header
        frameObjectName: "followedHeaderFrame"
        objectName: "followedHeader"
        label: "GAMES YOU FOLLOW"
        logoSource: followedModel.steamLogo // Existing packaged logo, not remote news art.
        fillColor: followedModel.tileColor
        borderColor: followsRoot.followedModel.accentColor
        textColor: followsRoot.followedModel.primaryColor
        fontFamily: followsRoot.followedModel.fontFamily
        x: childAlignment("header", "left") === "right"
            ? parent.width - width - 12.0 + childOffsetX("header")
            : 12.0 + childOffsetX("header")
        y: 12.0 + childOffsetY("header")
        scale: Math.min(childWidthScale("header"), childHeightScale("header"))
        transformOrigin: Item.TopLeft
        interactionEnabled: false
    }

    // Reserved stable target for the future accepted *source-owned* refresh
    // action. No pointer event is admitted, and it never queries the source.
    Item {
        id: refreshGlyph
        objectName: "followedRefreshTarget"
        visible: false
        x: parent.width - 40.0 + childOffsetX("refresh")
        y: 14.0 + childOffsetY("refresh")
        width: 26.0 * childWidthScale("refresh")
        height: 26.0 * childHeightScale("refresh")
    }

    Item {
        id: storyGroup
        objectName: "followedStoryGroup"
        x: 14.0 + childOffsetX("story_tiles")
        y: 72.0 + childOffsetY("story_tiles")
        width: Math.max(0.0, (parent.width - 28.0) * childWidthScale("story_tiles"))
        height: Math.max(0.0, (parent.height - 120.0) * childHeightScale("story_tiles"))
        clip: true
        visible: followedModel.selectedStoryCount > 0

        // Entire tiles hide when the independent X/Y card/group space cannot
        // hold them. Capacity never affects selected source rows, followed IDs,
        // cache, refresh timing or outer widget preferred size.
        readonly property int columnsFit: Math.max(0,
            Math.floor((width + 8.0) / 188.0))
        readonly property int rowsFit: Math.max(0,
            Math.floor((height + 8.0) / 100.0))
        readonly property int columns: Math.max(1,
            Math.min(followedModel.layoutColumns, columnsFit))
        readonly property int visibleCapacity: columnsFit === 0 || rowsFit === 0
            ? 0 : Math.min(8, followedModel.selectedStoryCount,
                followedModel.visibleStoryCount, columns * rowsFit)
        readonly property real tileWidth: columns > 0
            ? Math.max(0.0, (width - (columns - 1) * 8.0) / columns) : 0.0
        readonly property real tileHeight: 92.0

        Repeater {
            id: stableStories
            objectName: "followedStableStories"
            model: followedModel.storyRows // Fixed eight slots; never a varying array or modelReset.
            delegate: Rectangle {
                id: tile
                objectName: "followedStoryTile" + storySlot
                visible: storyFilled && storySlot < storyGroup.visibleCapacity
                x: (storySlot % storyGroup.columns) * (storyGroup.tileWidth + 8.0)
                y: Math.floor(storySlot / storyGroup.columns) * 100.0
                width: storyGroup.tileWidth
                height: storyGroup.tileHeight
                radius: 7.0
                color: followedModel.tileColor
                border.color: followedModel.accentColor
                border.width: 1.0
                // Deliberately no MouseArea, external URL, image downloader,
                // hover timer, per-delegate CUSTOM identity or source action.
                Text {
                    objectName: "followedStoryHeadline" + storySlot
                    x: 10.0
                    y: 8.0
                    width: Math.max(0.0, parent.width - 20.0)
                    height: 46.0
                    text: storyTitle
                    textFormat: Text.PlainText
                    color: followedModel.primaryColor
                    font.family: followedModel.fontFamily
                    font.pixelSize: followedModel.fontSize
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                    clip: true
                }
                Text {
                    objectName: "followedStorySource" + storySlot
                    x: 10.0
                    y: 66.0
                    width: Math.max(0.0, parent.width - 20.0)
                    height: 18.0
                    text: storySource + "  ·  " + storyPublished
                    textFormat: Text.PlainText
                    color: followedModel.accentColor
                    font.pixelSize: 11
                    elide: Text.ElideRight
                    clip: true
                }
            }
        }
    }

    Text {
        id: overflowSummary
        objectName: "followedOverflowSummary"
        readonly property int omitted: Math.max(0,
            followedModel.selectedStoryCount - storyGroup.visibleCapacity)
        visible: omitted > 0 || followedModel.selectedStoryCount === 0
        x: 14.0 + childOffsetX("overflow_summary")
        y: parent.height - 37.0 + childOffsetY("overflow_summary")
        width: Math.max(0, (parent.width - 28.0) * childWidthScale("overflow_summary"))
        height: 22.0 * childHeightScale("overflow_summary")
        text: omitted > 0 ? "+" + omitted + " more updates"
            : followedModel.statusLabel
        color: followedModel.primaryColor
        font.family: followedModel.fontFamily
        font.pixelSize: 12
        elide: Text.ElideRight
        horizontalAlignment: childAlignment("overflow_summary", "left") === "right"
            ? Text.AlignRight : Text.AlignLeft
        clip: true
    }
}
