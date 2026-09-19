import QtQuick

OverlayWidget {
    id: redditRoot
    objectName: "redditPresentation"

    // Whole-widget CUSTOM resize remains one uniform retained transform. Child
    // roles below are additive authored-relative geometry only; provider/cache
    // cadence and the Settings-owned font remain untouched.
    uniformScaleTransform: true

    required property var redditModel
    signal openPostRequested(string url)
    signal refreshRequested()

    readonly property real cExtentW: redditModel.contentExtentWidth
    readonly property real cExtentH: redditModel.contentExtentHeight
    readonly property real naturalRowHeight: Math.max(28.0, redditModel.fontSize * 1.55)
    readonly property real baseRowSpacing: 4.0
    readonly property var childGeometry: redditModel.customChildGeometry
    readonly property real childPlacementEpsilon: 0.0001

    function childRecord(roleId) {
        return childGeometry ? childGeometry[roleId] : null
    }
    function childWidthScale(roleId) {
        const value = childRecord(roleId)
        return value && value.width_scale !== undefined ? Number(value.width_scale) : 1.0
    }
    function childHeightScale(roleId) {
        const value = childRecord(roleId)
        return value && value.height_scale !== undefined ? Number(value.height_scale) : 1.0
    }
    function childOffsetX(roleId) {
        const value = childRecord(roleId)
        return (value && value.x_offset !== undefined ? Number(value.x_offset) : 0.0)
            * childNormalizationWidth
    }
    function childOffsetY(roleId) {
        const value = childRecord(roleId)
        return (value && value.y_offset !== undefined ? Number(value.y_offset) : 0.0)
            * childNormalizationHeight
    }
    function childAlignment(roleId, authored) {
        const value = childRecord(roleId)
        return value && value.alignment !== undefined ? String(value.alignment) : authored
    }
    function childAnchor(roleId) {
        const value = childRecord(roleId)
        return value && value.anchor !== undefined ? String(value.anchor) : ""
    }

    readonly property real canonicalPreferredWidth: Math.max(
        600.0,
        headerFrame.implicitWidth
            + (refreshTarget.visible ? refreshTarget.implicitWidth + 10.0 : 0.0)
            + redditRoot.shellInset
    )
    readonly property real canonicalAuthoredHeight: Math.max(
        60.0,
        headerFrame.implicitHeight
            + baseRowSpacing
            + Math.max(1, redditModel.postLimit) * naturalRowHeight
            + Math.max(0, redditModel.postLimit - 1) * baseRowSpacing
            + redditRoot.shellInset
    )
    readonly property real childNormalizationWidth: canonicalPreferredWidth
    readonly property real childNormalizationHeight: canonicalAuthoredHeight

    readonly property int heldPostCount: postRepeater.count
    readonly property real postRowWidthScale: childWidthScale("post_rows")
    readonly property real postRowHeightScale: childHeightScale("post_rows")
    readonly property real postRowsXOffset: childOffsetX("post_rows")
    readonly property real postRowsYOffset: childOffsetY("post_rows")
    readonly property real effectiveBaseRowHeight: naturalRowHeight * postRowHeightScale
    readonly property bool postVerticalGeometryActive:
        Math.abs(postRowHeightScale - 1.0) > childPlacementEpsilon
        || Math.abs(postRowsYOffset) > childPlacementEpsilon
    readonly property real chromeHeight: headerArea.height
        + (statusArea.visible ? statusArea.height + baseRowSpacing : 0.0)
        + redditRoot.shellInset
    // The repeated rail remains attached to the authored top flow. Positive
    // shared Y placement consumes rail budget instead of asking the parent to
    // grow. This preserves the long-standing outer-Y contract: parent height is
    // still the sole authority that reveals/hides rows.
    readonly property real layoutHeightForRows: cExtentH > 0.0
        ? cExtentH : canonicalAuthoredHeight
    readonly property real postRailBudget: Math.max(
        0.0,
        layoutHeightForRows - chromeHeight - Math.max(0.0, postRowsYOffset)
    )
    readonly property int effectiveVisibleCount: {
        var held = Math.max(0, heldPostCount)
        if (held === 0)
            return 0
        if (cExtentH <= 0.0 && !postVerticalGeometryActive)
            return Math.min(held, redditModel.postLimit)
        var fit = Math.floor(postRailBudget / (effectiveBaseRowHeight + baseRowSpacing))
        return Math.max(1, Math.min(held, fit))
    }
    // Once count caps, outer-Y growth still becomes row breathing room. Shared
    // row height is the authored minimum for that calculation, never a second
    // post-count setting.
    readonly property real extentRowHeight: {
        if ((cExtentH <= 0.0 && !postVerticalGeometryActive) || effectiveVisibleCount <= 0)
            return effectiveBaseRowHeight
        var gaps = Math.max(0, effectiveVisibleCount - 1)
        return Math.max(
            effectiveBaseRowHeight,
            (postRailBudget - gaps * baseRowSpacing) / effectiveVisibleCount
        )
    }
    readonly property real extentSeparatorThickness: cExtentH > 0.0
        ? Math.max(1.0, Math.min(4.0, extentRowHeight / Math.max(1.0, naturalRowHeight)))
        : 1.0

    preferredContentWidth: cExtentW > 0.0 ? cExtentW : canonicalPreferredWidth
    preferredContentHeight: cExtentH > 0.0 ? cExtentH : canonicalAuthoredHeight

    customEditableChildRoles: {
        const roles = []
        const normW = childNormalizationWidth
        const normH = childNormalizationHeight
        roles.push({
            "roleId": "header",
            "target": headerFrame,
            "normalizationWidth": normW,
            "normalizationHeight": normH,
            "semanticCornerInsetX": 0.0,
            "semanticCornerInsetY": 0.0
        })
        if (refreshTarget.visible) {
            roles.push({
                "roleId": "refresh",
                "target": refreshTarget,
                "normalizationWidth": normW,
                "normalizationHeight": normH
            })
        }
        if (redditModel.viewState === "ready" && effectiveVisibleCount > 0) {
            roles.push({
                "roleId": "post_rows",
                "target": customPostRowRoleTarget,
                "collisionIgnoreRoleIds": ["post_time", "post_titles", "post_separators"],
                "normalizationWidth": normW,
                "normalizationHeight": normH
            })
            roles.push({
                "roleId": "post_time",
                "target": customPostTimeRoleTarget,
                "collisionIgnoreRoleIds": ["post_rows"],
                "normalizationWidth": normW,
                "normalizationHeight": normH
            })
            roles.push({
                "roleId": "post_titles",
                "target": customPostTitleRoleTarget,
                "collisionIgnoreRoleIds": ["post_rows"],
                "normalizationWidth": normW,
                "normalizationHeight": normH
            })
            if (redditModel.showSeparators && effectiveVisibleCount > 1) {
                roles.push({
                    "roleId": "post_separators",
                    "target": customPostSeparatorRoleTarget,
                    "occupiedTarget": customPostSeparatorOccupiedTarget,
                    "collisionIgnoreRoleIds": ["post_rows"],
                    "normalizationWidth": normW,
                    "normalizationHeight": normH
                })
            }
        }
        return roles
    }

    Column {
        id: contentColumn
        objectName: "redditContent"
        anchors.fill: parent
        spacing: redditRoot.baseRowSpacing

        Item {
            id: headerArea
            objectName: "redditHeaderArea"
            width: parent.width
            height: headerFrame.implicitHeight

            BrandedHeader {
                id: headerFrame
                frameObjectName: "redditHeaderFrame"
                logoObjectName: "redditHeaderLogo"
                textObjectName: "redditSubredditLabel"
                readonly property string customAnchor: redditRoot.childAnchor("header")
                readonly property real customScale: redditRoot.childWidthScale("header")
                property real customEditPlacementCompensationX: customAnchor.length > 0
                    ? x - redditRoot.childOffsetX("header") : 0.0
                property real customEditPlacementCompensationY: customAnchor.length > 0
                    ? y - redditRoot.childOffsetY("header") : 0.0
                transformOrigin: Item.TopLeft
                scale: customScale
                x: customAnchor.endsWith("right")
                    ? headerArea.width - width * scale
                    : (customAnchor.endsWith("left") ? 0.0 : redditRoot.childOffsetX("header"))
                y: customAnchor.startsWith("bottom")
                    ? headerArea.height - height * scale
                    : (customAnchor.startsWith("top") ? 0.0 : redditRoot.childOffsetY("header"))
                contentReversed: redditRoot.childAlignment("header", "left") === "right"
                label: redditRoot.redditModel.subredditText
                logoSource: redditRoot.redditModel.logoSource
                interactionEnabled: redditRoot.redditModel.interactionEnabled
                fillColor: redditRoot.redditModel.headerFillColor
                borderColor: redditRoot.redditModel.headerBorderColor
                borderWidth: redditRoot.scaleAwareHeaderStrokeWidth(redditRoot.redditModel.headerBorderWidth)
                textColor: redditRoot.redditModel.headerTextColor
                fontFamily: redditRoot.redditModel.fontFamily
                textShadowEnabled: redditRoot.redditModel.textShadowEnabled
                textShadowColor: redditRoot.redditModel.textShadowColor
                textShadowOffsetX: redditRoot.redditModel.textShadowOffsetX
                textShadowOffsetY: redditRoot.redditModel.textShadowOffsetY
                shadowEnabled: redditRoot.cardShadowEnabled
                shadowColor: Qt.rgba(redditRoot.cardShadowColor.r, redditRoot.cardShadowColor.g,
                                     redditRoot.cardShadowColor.b, redditRoot.cardShadowColor.a * 0.45)
                shadowBlur: Math.max(2.0, Math.min(6.0, redditRoot.cardShadowBlur * 0.25))
                shadowOffsetX: redditRoot.cardShadowOffsetX * 1.15
                shadowOffsetY: redditRoot.cardShadowOffsetY * 1.15
                onActivated: redditRoot.openPostRequested(redditRoot.redditModel.subredditUrl)
            }

            Item {
                id: refreshTarget
                objectName: "redditRefreshTarget"
                readonly property real implicitWidth: Math.max(24.0, refreshGlyph.implicitWidth + 4.0)
                visible: redditRoot.redditModel.showRefreshSpiral
                width: implicitWidth * redditRoot.childWidthScale("refresh")
                height: headerArea.height * redditRoot.childHeightScale("refresh")
                x: headerArea.width - width + redditRoot.childOffsetX("refresh")
                y: (headerArea.height - height) / 2.0 + redditRoot.childOffsetY("refresh")

                ShadowedText {
                    id: refreshGlyph
                    objectName: "redditRefreshGlyph"
                    anchors.fill: parent
                    horizontalAlignment: Text.AlignHCenter
                    text: redditRoot.redditModel.refreshing ? "◌" : "↻"
                    opacity: 0.7
                    color: redditRoot.redditModel.textColor
                    font.family: redditRoot.redditModel.fontFamily
                    font.pointSize: redditRoot.redditModel.fontSize
                    font.bold: true
                    verticalAlignment: Text.AlignVCenter
                    shadowEnabled: redditRoot.redditModel.textShadowEnabled
                    shadowColor: redditRoot.redditModel.textShadowColor
                    shadowOffsetX: redditRoot.redditModel.textShadowOffsetX
                    shadowOffsetY: redditRoot.redditModel.textShadowOffsetY
                    TapHandler {
                        enabled: redditRoot.redditModel.interactionEnabled
                        acceptedButtons: Qt.LeftButton
                        onTapped: redditRoot.refreshRequested()
                    }
                }
            }
        }

        Item {
            id: statusArea
            objectName: "redditStatusArea"
            width: parent.width
            height: visible ? Math.max(36.0, statusText.implicitHeight + 8.0) : 0.0
            visible: redditRoot.redditModel.viewState !== "ready"

            ShadowedText {
                id: statusText
                anchors.fill: parent
                text: {
                    if (redditRoot.redditModel.viewState === "missing") return "Subreddit required"
                    if (redditRoot.redditModel.viewState === "error") return redditRoot.redditModel.errorText
                    if (redditRoot.redditModel.viewState === "empty") return "No posts available"
                    return "Loading Reddit…"
                }
                color: redditRoot.redditModel.textColor
                font.family: redditRoot.redditModel.fontFamily
                font.pointSize: redditRoot.redditModel.fontSize * 0.78
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                wrap: true
                shadowEnabled: redditRoot.redditModel.textShadowEnabled
                shadowColor: redditRoot.redditModel.textShadowColor
                shadowOffsetX: redditRoot.redditModel.textShadowOffsetX
                shadowOffsetY: redditRoot.redditModel.textShadowOffsetY
            }
        }

        Repeater {
            id: postRepeater
            objectName: "redditPostRepeater"
            model: redditRoot.redditModel.rowModel

            delegate: Item {
                id: postRow
                required property string postIdentity
                required property string postTitle
                required property string postAge
                required property string postUrl
                required property int index

                readonly property real canonicalAgeWidth: Math.max(88.0, redditRoot.redditModel.fontSize * 5.55)
                readonly property real canonicalTitleX: canonicalAgeWidth + 4.0
                objectName: "redditPostRow_" + index
                width: contentColumn.width * redditRoot.postRowWidthScale
                x: redditRoot.postRowsXOffset
                visible: index < redditRoot.effectiveVisibleCount
                height: visible ? redditRoot.extentRowHeight : 0.0
                transform: Translate { y: redditRoot.postRowsYOffset }

                Item {
                    id: ageText
                    objectName: "redditPostAge_" + postRow.index
                    x: redditRoot.childOffsetX("post_time")
                    y: (parent.height - height) / 2.0 + redditRoot.childOffsetY("post_time")
                    width: postRow.canonicalAgeWidth * redditRoot.childWidthScale("post_time")
                    height: parent.height * redditRoot.childHeightScale("post_time")

                    readonly property string valueText: {
                        const raw = String(postRow.postAge || "").trim()
                        return raw.toUpperCase().endsWith(" AGO") ? raw.slice(0, -4).trim() : raw
                    }

                    ShadowedText {
                        id: ageValueText
                        objectName: "redditPostAgeValue_" + postRow.index
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.max(49.0, parent.width * 0.58)
                        height: parent.height
                        text: ageText.valueText
                        color: redditRoot.redditModel.ageColor
                        font.family: redditRoot.redditModel.fontFamily
                        font.pointSize: redditRoot.redditModel.ageFontSize * redditRoot.childHeightScale("post_time")
                        font.bold: true
                        horizontalAlignment: Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        shadowEnabled: redditRoot.redditModel.textShadowEnabled
                        shadowColor: redditRoot.redditModel.textShadowColor
                        shadowOffsetX: redditRoot.redditModel.textShadowOffsetX
                        shadowOffsetY: redditRoot.redditModel.textShadowOffsetY
                    }

                    ShadowedText {
                        id: ageAgoText
                        objectName: "redditPostAgeAgo_" + postRow.index
                        anchors.right: parent.right
                        anchors.rightMargin: 17.0
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.max(30.0, parent.width * 0.36)
                        height: parent.height
                        text: "AGO"
                        color: redditRoot.redditModel.ageColor
                        font.family: redditRoot.redditModel.fontFamily
                        font.pointSize: redditRoot.redditModel.ageFontSize * redditRoot.childHeightScale("post_time")
                        font.bold: true
                        horizontalAlignment: Text.AlignRight
                        verticalAlignment: Text.AlignVCenter
                        shadowEnabled: redditRoot.redditModel.textShadowEnabled
                        shadowColor: redditRoot.redditModel.textShadowColor
                        shadowOffsetX: redditRoot.redditModel.textShadowOffsetX
                        shadowOffsetY: redditRoot.redditModel.textShadowOffsetY
                    }
                }

                ShadowedText {
                    id: titleText
                    objectName: "redditPostTitle_" + postRow.index
                    readonly property real authoredBaseX: postRow.canonicalTitleX
                    x: authoredBaseX + redditRoot.childOffsetX("post_titles")
                    y: (parent.height - height) / 2.0 + redditRoot.childOffsetY("post_titles")
                    width: Math.max(24.0, parent.width - authoredBaseX)
                        * redditRoot.childWidthScale("post_titles")
                    height: parent.height * redditRoot.childHeightScale("post_titles")
                    text: postRow.postTitle
                    color: redditRoot.redditModel.textColor
                    font.family: redditRoot.redditModel.fontFamily
                    font.pointSize: redditRoot.redditModel.fontSize * redditRoot.childHeightScale("post_titles")
                    font.weight: Font.DemiBold
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    shadowEnabled: redditRoot.redditModel.textShadowEnabled
                    shadowColor: redditRoot.redditModel.textShadowColor
                    shadowOffsetX: redditRoot.redditModel.textShadowOffsetX
                    shadowOffsetY: redditRoot.redditModel.textShadowOffsetY
                }

                Rectangle {
                    id: postSeparator
                    objectName: "redditPostSeparator_" + postRow.index
                    visible: redditRoot.redditModel.showSeparators
                        && postRow.index < redditRoot.effectiveVisibleCount - 1
                    x: redditRoot.childOffsetX("post_separators")
                    y: parent.height - height + redditRoot.childOffsetY("post_separators")
                    width: parent.width * redditRoot.childWidthScale("post_separators")
                    height: redditRoot.scaleAwareStrokeWidth(redditRoot.extentSeparatorThickness)
                        * redditRoot.childHeightScale("post_separators")
                    color: redditRoot.redditModel.separatorColor
                }

                TapHandler {
                    enabled: redditRoot.redditModel.interactionEnabled
                    acceptedButtons: Qt.LeftButton
                    onTapped: redditRoot.openPostRequested(postRow.postUrl)
                }
            }
        }
    }

    // One representative edit surface per repeated semantic role. Delegates all
    // consume the same geometry record, so persistence/edit cost is independent
    // of post count and never uses post identity/index as a key.
    Item {
        id: customPostRowRoleTarget
        objectName: "redditCustomPostRowRoleTarget"
        visible: redditModel.viewState === "ready" && effectiveVisibleCount > 0
        enabled: false
        x: redditRoot.postRowsXOffset
        y: headerArea.height + baseRowSpacing + redditRoot.postRowsYOffset
        width: contentColumn.width * redditRoot.postRowWidthScale
        height: redditRoot.extentRowHeight
    }
    Item {
        id: customPostTimeRoleTarget
        objectName: "redditCustomPostTimeRoleTarget"
        visible: customPostRowRoleTarget.visible
        enabled: false
        x: customPostRowRoleTarget.x + redditRoot.childOffsetX("post_time")
        y: customPostRowRoleTarget.y
            + (customPostRowRoleTarget.height - height) / 2.0
            + redditRoot.childOffsetY("post_time")
        width: Math.max(88.0, redditRoot.redditModel.fontSize * 5.55)
            * redditRoot.childWidthScale("post_time")
        height: customPostRowRoleTarget.height * redditRoot.childHeightScale("post_time")
    }
    Item {
        id: customPostTitleRoleTarget
        objectName: "redditCustomPostTitleRoleTarget"
        visible: customPostRowRoleTarget.visible
        enabled: false
        readonly property real authoredBaseX: customPostRowRoleTarget.x
            + Math.max(88.0, redditRoot.redditModel.fontSize * 5.55) + 4.0
        x: authoredBaseX + redditRoot.childOffsetX("post_titles")
        y: customPostRowRoleTarget.y
            + (customPostRowRoleTarget.height - height) / 2.0
            + redditRoot.childOffsetY("post_titles")
        width: Math.max(24.0, customPostRowRoleTarget.x + customPostRowRoleTarget.width - authoredBaseX)
            * redditRoot.childWidthScale("post_titles")
        height: customPostRowRoleTarget.height * redditRoot.childHeightScale("post_titles")
    }
    Item {
        id: customPostSeparatorOccupiedTarget
        objectName: "redditCustomPostSeparatorOccupiedTarget"
        visible: customPostRowRoleTarget.visible && redditModel.showSeparators && effectiveVisibleCount > 1
        enabled: false
        x: customPostRowRoleTarget.x + redditRoot.childOffsetX("post_separators")
        y: customPostRowRoleTarget.y + customPostRowRoleTarget.height - height
            + redditRoot.childOffsetY("post_separators")
        width: customPostRowRoleTarget.width * redditRoot.childWidthScale("post_separators")
        height: redditRoot.scaleAwareStrokeWidth(redditRoot.extentSeparatorThickness)
            * redditRoot.childHeightScale("post_separators")
    }
    Item {
        id: customPostSeparatorRoleTarget
        objectName: "redditCustomPostSeparatorRoleTarget"
        visible: customPostSeparatorOccupiedTarget.visible
        enabled: false
        readonly property real occupiedHeight: customPostSeparatorOccupiedTarget.height
        x: customPostSeparatorOccupiedTarget.x
        y: customPostSeparatorOccupiedTarget.y - (height - occupiedHeight) / 2.0
        width: customPostSeparatorOccupiedTarget.width
        height: 6.0 * redditRoot.childHeightScale("post_separators")
    }
}
