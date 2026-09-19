import QtQuick

OverlayWidget {
    id: redditRoot
    objectName: "redditPresentation"


    // H9: CUSTOM wheel/corner resize is one uniform retained-presentation scale.
    // The whole authored card (header, rows, spacing, chrome) scales together
    // from the outer-rect / baseline-preferred ratio, so rows can no longer
    // escape a shrunk card. CUSTOM resize is purely geometric here; font size
    // stays Settings-owned (no per-value payload scaling).
    uniformScaleTransform: true

    required property var redditModel
    signal openPostRequested(string url)
    signal refreshRequested()

    // Content-driven outer size (H option A). Width honours the historical
    // ordinary-card minimum footprint (BaseOverlayWidget.DEFAULT_CARD_MIN_WIDTH =
    // 600) and only enlarges above it when the intrinsic header content genuinely
    // requires it - never shrinking below the authored floor. Height is content
    // driven. Intrinsic sources only (no width<->preferredWidth feedback). J
    // refines parity.
    // CUSTOM content-extent box (0 = none). Vertical drives the effective visible
    // post count then row/separator spread; horizontal relaxes width truncation.
    // The `limit` setting stays the SSOT default when no extent is active.
    readonly property real cExtentW: redditModel.contentExtentWidth
    readonly property real cExtentH: redditModel.contentExtentHeight
    readonly property real naturalRowHeight: Math.max(28.0, redditModel.fontSize * 1.55)
    readonly property real baseRowSpacing: 4.0
    readonly property real flippedTitleAgeGap: 4.0
    readonly property real ageValueAgoGap: 4.0
    readonly property var childGeometry: redditModel.customChildGeometry
    // Header alignment is the existing widget-wide semantic flip intent.
    // Project structural rails, NEVER mirror glyphs or text alignment.
    readonly property bool headerFlipped: childAlignment("header", "left") === "right"

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
    readonly property real chromeHeight: headerArea.height
        + (statusArea.visible ? statusArea.height + baseRowSpacing : 0.0)
        + redditRoot.shellInset
    readonly property real postRailBudget: Math.max(0.0, cExtentH - chromeHeight)
    readonly property int effectiveVisibleCount: {
        var held = Math.max(0, heldPostCount)
        if (held === 0)
            return 0
        if (cExtentH <= 0.0)
            return Math.min(held, redditModel.postLimit)   // SSOT default count
        var fit = Math.floor(postRailBudget / (naturalRowHeight + baseRowSpacing))
        return Math.max(1, Math.min(held, fit))            // CUSTOM: 1..held (<=cache cap)
    }
    // Rows grow to fill the box once the count caps (past-limit vertical padding).
    readonly property real extentRowHeight: {
        if (cExtentH <= 0.0 || effectiveVisibleCount <= 0)
            return naturalRowHeight
        var gaps = Math.max(0, effectiveVisibleCount - 1)
        return Math.max(
            naturalRowHeight,
            (postRailBudget - gaps * baseRowSpacing) / effectiveVisibleCount
        )
    }
    readonly property real extentSeparatorThickness: cExtentH > 0.0
        ? Math.max(1.0, Math.min(4.0, extentRowHeight / naturalRowHeight))
        : 1.0

    // A preferred width must use *intrinsic authored* inputs only.  The live
    // refresh glyph width belongs to a header-bounded edit target, and reading
    // it here creates a cycle: preferred width -> authored card/header width
    // -> refresh target width -> glyph width -> preferred width.  The existing
    // canonical width already includes the intrinsic (unclamped) refresh slot.
    // Parent side-reflow remains owned solely by content_extent.
    preferredContentWidth: cExtentW > 0.0
        ? cExtentW : canonicalPreferredWidth
    preferredContentHeight: cExtentH > 0.0
        ? cExtentH
        : Math.max(60.0, contentColumn.childrenRect.height) + redditRoot.shellInset

    customEditableChildRoles: {
        const roles = []
        const normW = childNormalizationWidth
        const normH = childNormalizationHeight
        roles.push({
            "roleId": "header",
            "target": headerFrame,
            // A semantic header relocation follows the already-admitted
            // parent rail; it is not a new content-size requirement.
            "allowParentGrowth": false,
            "normalizationWidth": normW,
            "normalizationHeight": normH,
            "semanticCornerInsetX": 0.0,
            "semanticCornerInsetY": 0.0
        })
        if (refreshTarget.visible) {
            roles.push({
                "roleId": "refresh",
                "target": refreshTarget,
                "allowParentGrowth": false,
                "normalizationWidth": normW,
                "normalizationHeight": normH
            })
        }
        return roles
    }

    Column {
        id: contentColumn
        objectName: "redditContent"
        anchors.fill: parent
        spacing: 4.0

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
                property real customEditPlacementCompensationX:
                    customAnchor.length > 0 || redditRoot.headerFlipped
                        ? x - redditRoot.childOffsetX("header") : 0.0
                property real customEditPlacementCompensationY: customAnchor.length > 0
                    ? y - redditRoot.childOffsetY("header") : 0.0
                transformOrigin: Item.TopLeft
                scale: customScale
                x: customAnchor.endsWith("right")
                    ? headerArea.width - width * scale
                    : (customAnchor.endsWith("left") ? 0.0
                        : (redditRoot.headerFlipped ? headerArea.width - width * scale : 0.0)
                            + redditRoot.childOffsetX("header"))
                y: customAnchor.startsWith("bottom")
                    ? headerArea.height - height * scale
                    : (customAnchor.startsWith("top") ? 0.0 : redditRoot.childOffsetY("header"))
                contentReversed: redditRoot.headerFlipped
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
                x: (redditRoot.headerFlipped ? 0.0 : headerArea.width - width)
                    + redditRoot.childOffsetX("refresh")
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
                    if (redditRoot.redditModel.viewState === "missing")
                        return "Subreddit required"
                    if (redditRoot.redditModel.viewState === "error")
                        return redditRoot.redditModel.errorText
                    if (redditRoot.redditModel.viewState === "empty")
                        return "No posts available"
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

                objectName: "redditPostRow_" + index
                width: contentColumn.width
                visible: index < redditRoot.effectiveVisibleCount
                height: visible ? redditRoot.extentRowHeight : 0.0

                Item {
                    id: ageText
                    objectName: "redditPostAge_" + postRow.index
                    // Keep the timestamp on the *same* end rail for every row.
                    // Following each title's intrinsic width made short titles
                    // pull 01HR/AGO towards the middle, while long titles pushed
                    // them to the edge. The title elides against this stable
                    // rail; the two timestamp glyphs stay adjacent.
                    x: redditRoot.headerFlipped ? parent.width - width : 0.0
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.max(88.0, ageValueText.width
                        + redditRoot.ageValueAgoGap + ageAgoText.width)
                    height: parent.height

                    readonly property string valueText: {
                        const raw = String(postRow.postAge || "").trim()
                        return raw.toUpperCase().endsWith(" AGO")
                            ? raw.slice(0, -4).trim()
                            : raw
                    }

                    ShadowedText {
                        id: ageValueText
                        objectName: "redditPostAgeValue_" + postRow.index
                        x: 0.0
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.max(49.0, implicitWidth)
                        height: parent.height
                        text: ageText.valueText
                        color: redditRoot.redditModel.ageColor
                        font.family: redditRoot.redditModel.fontFamily
                        font.pointSize: redditRoot.redditModel.ageFontSize
                        font.bold: true
                        // Fixed left edge guarantees the first digit aligns
                        // vertically across 03D/02HR/etc. The sub-column itself
                        // occupies the visual centre of the time field.
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
                        // Flipped reading order is POST TITLE | 01HR | AGO.
                        // Never mirror the actual text/glyphs.
                        x: redditRoot.headerFlipped
                            ? ageValueText.width + redditRoot.ageValueAgoGap
                            : parent.width - width
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.max(30.0, implicitWidth)
                        height: parent.height
                        text: "AGO"
                        color: redditRoot.redditModel.ageColor
                        font.family: redditRoot.redditModel.fontFamily
                        font.pointSize: redditRoot.redditModel.ageFontSize
                        font.bold: true
                        horizontalAlignment: redditRoot.headerFlipped
                            ? Text.AlignLeft : Text.AlignRight
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
                    x: redditRoot.headerFlipped ? 0.0 : ageText.width + 4.0
                    width: Math.max(1.0, redditRoot.headerFlipped
                        ? parent.width - ageText.width - redditRoot.flippedTitleAgeGap
                        : parent.width - ageText.width - 4.0)
                    anchors.verticalCenter: parent.verticalCenter
                    // Post text remains left-aligned in both arrangements. The
                    // timestamp occupies the opposite fixed-width semantic rail.
                    horizontalAlignment: Text.AlignLeft
                    height: parent.height
                    text: postRow.postTitle
                    color: redditRoot.redditModel.textColor
                    font.family: redditRoot.redditModel.fontFamily
                    font.pointSize: redditRoot.redditModel.fontSize
                    font.weight: Font.DemiBold
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    shadowEnabled: redditRoot.redditModel.textShadowEnabled
                    shadowColor: redditRoot.redditModel.textShadowColor
                    shadowOffsetX: redditRoot.redditModel.textShadowOffsetX
                    shadowOffsetY: redditRoot.redditModel.textShadowOffsetY
                }

                Rectangle {
                    objectName: "redditPostSeparator_" + postRow.index
                    visible: redditRoot.redditModel.showSeparators
                        && postRow.index < redditRoot.effectiveVisibleCount - 1
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: redditRoot.scaleAwareStrokeWidth(
                        redditRoot.extentSeparatorThickness
                    )
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
}
