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
    // Reserve enough *painted* space between AGO and the title even when the
    // whole retained card is uniformly scaled down. Neither the internal
    // 01HR/AGO separation nor the stable timestamp rail changes.
    // The scale is a projection of the outer rect, never an input to the
    // preferred-size authority; this cannot feed a card-size cycle.
    readonly property real titleAgeGap: Math.max(
        8.0, 9.0 / Math.max(0.2, redditRoot.presentationScale)
    )
    readonly property real ageValueAgoGap: 2.0
    readonly property var childGeometry: redditModel.customChildGeometry
    // Header alignment is the existing widget-wide semantic flip intent.
    // Project structural rails, NEVER mirror glyphs or text alignment.
    readonly property bool headerFlipped: childAlignment("header", "left") === "right"
    // One widget-wide semantic order; no per-post data or position is stored.
    readonly property var visualColumnOrder: {
        const saved = redditModel.customColumnOrder
        return saved && saved.length === 3 ? saved
            : (headerFlipped ? ["title", "age", "ago"] : ["age", "ago", "title"])
    }
    customColumnRailSpecs: {
        // No repeated-row descriptor lookup in ordinary playback.
        if (!redditRoot.customLayoutInputBlocked) return []
        const order = redditRoot.visualColumnOrder
        const first = postRepeater.count > 0 ? postRepeater.itemAt(0) : null
        if (!first || !first.visible || !first.columnTargets)
            return []
        const targets = first.columnTargets
        return order.map(function(role) { return {"roleId": role, "target": targets[role]} })
    }


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
    // Loading/empty post delegates must NOT become the authored size authority.
    // Otherwise starting Edit before the provider publishes rows captures a
    // tiny 600x88 card; Restore Size later collapses a full ready-state card
    // back to that provisional height. Keep the post-limit authored reference
    // stable across provider changes, while preserving explicit CUSTOM extents.
    preferredContentHeight: cExtentH > 0.0
        ? cExtentH
        : Math.max(canonicalAuthoredHeight,
                   contentColumn.childrenRect.height + redditRoot.shellInset)

    // Stable retained semantic roles. Visibility is evaluated by the selected
    // Edit mapper, not by rebuilding this role list during content transitions.
    customEditableChildRoles: {
        const roles = []
        roles.push({
            "roleId": "header",
            "target": headerFrame,
            // A semantic header relocation follows the already-admitted
            // parent rail; it is not a new content-size requirement.

            "normalizationTarget": redditRoot,
            "semanticCornerInsetX": 0.0,
            "semanticCornerInsetY": 0.0
        })
        roles.push({
            "roleId": "refresh",
            "target": refreshTarget,

            "normalizationTarget": redditRoot
        })
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
                readonly property bool canActivate: visible
                    && redditRoot.redditModel.interactionEnabled
                    && !redditRoot.customLayoutInputBlocked
                visible: redditRoot.redditModel.showRefreshSpiral
                width: implicitWidth * redditRoot.childWidthScale("refresh")
                height: headerArea.height * redditRoot.childHeightScale("refresh")
                x: (redditRoot.headerFlipped ? 0.0 : headerArea.width - width)
                    + redditRoot.childOffsetX("refresh")
                y: (headerArea.height - height) / 2.0 + redditRoot.childOffsetY("refresh")

                // Retain the authored click box, glyph position and font size.
                // A paint-only hover frame follows the semantic header border.
                Rectangle {
                    objectName: "redditRefreshHoverFrame"
                    anchors.fill: parent
                    radius: 6.0
                    color: "transparent"
                    border.color: refreshHover.hovered && refreshTarget.canActivate
                        ? "white" : redditRoot.redditModel.headerBorderColor
                    border.width: refreshHover.hovered && refreshTarget.canActivate
                        ? redditRoot.scaleAwareChildStrokeWidth(1.5, Math.min(
                            redditRoot.childWidthScale("refresh"),
                            redditRoot.childHeightScale("refresh"))) : 0.0
                }
                HoverHandler {
                    id: refreshHover
                    enabled: refreshTarget.canActivate
                    blocking: false
                    cursorShape: Qt.PointingHandCursor
                }
                ShadowedText {
                    id: refreshGlyph
                    objectName: "redditRefreshGlyph"
                    anchors.fill: parent
                    horizontalAlignment: Text.AlignHCenter
                    text: redditRoot.redditModel.refreshing ? "◌" : "↻"
                    opacity: 0.7
                    color: refreshHover.hovered && refreshTarget.canActivate
                        ? "white" : redditRoot.redditModel.textColor
                    font.family: redditRoot.redditModel.fontFamily
                    font.pointSize: redditRoot.redditModel.fontSize
                    font.bold: true
                    verticalAlignment: Text.AlignVCenter
                    shadowEnabled: redditRoot.redditModel.textShadowEnabled
                    shadowColor: redditRoot.redditModel.textShadowColor
                    shadowOffsetX: redditRoot.redditModel.textShadowOffsetX
                    shadowOffsetY: redditRoot.redditModel.textShadowOffsetY
                }
                TapHandler {
                    enabled: refreshTarget.canActivate
                    acceptedButtons: Qt.LeftButton
                    onTapped: redditRoot.refreshRequested()
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
                readonly property var columnTargets: ({"age": ageValueText,
                                                       "ago": ageAgoText,
                                                       "title": titleText})
                readonly property real ageRailWidth: ageValueText.width
                readonly property real agoRailWidth: ageAgoText.width
                readonly property real semanticGapTotal: {
                    const order = redditRoot.visualColumnOrder
                    return postRow.columnGap(order[0], order[1])
                        + postRow.columnGap(order[1], order[2])
                }
                function columnGap(left, right) {
                    return (left === "age" && right === "ago")
                        || (left === "ago" && right === "age")
                        ? redditRoot.ageValueAgoGap : redditRoot.titleAgeGap
                }
                function columnWidth(role) {
                    if (role === "age") return ageRailWidth
                    if (role === "ago") return agoRailWidth
                    return Math.max(1.0, width - ageRailWidth - agoRailWidth - semanticGapTotal)
                }
                function columnX(role) {
                    const order = redditRoot.visualColumnOrder
                    let left = 0.0
                    for (let i = 0; i < order.length; ++i) {
                        if (order[i] === role) return left
                        left += columnWidth(order[i])
                        if (i < order.length - 1) left += columnGap(order[i], order[i + 1])
                    }
                    return 0.0
                }

                width: contentColumn.width
                visible: index < redditRoot.effectiveVisibleCount
                height: visible ? redditRoot.extentRowHeight : 0.0
                readonly property bool canActivate: visible
                    && redditRoot.redditModel.interactionEnabled
                    && postUrl.length > 0
                    && !redditRoot.customLayoutInputBlocked

                Rectangle {
                    objectName: "redditPostHoverFrame_" + postRow.index
                    anchors.fill: parent
                    anchors.margins: 2.0
                    radius: 4.0
                    color: postHover.hovered && postRow.canActivate
                        ? Qt.rgba(redditRoot.redditModel.textColor.r,
                                  redditRoot.redditModel.textColor.g,
                                  redditRoot.redditModel.textColor.b, 0.065)
                        : "transparent"
                    // Text-dense repeated rows advertise clickability through the
                    // surface plus title emphasis, never a stroke cutting through
                    // compact timestamp/title rails.
                    border.width: 0.0
                }
                HoverHandler {
                    id: postHover
                    enabled: postRow.canActivate
                    blocking: false
                    cursorShape: Qt.PointingHandCursor
                }

                Item {
                    id: ageText
                    objectName: "redditPostAge_" + postRow.index
                    // Keep the timestamp on the *same* end rail for every row.
                    // Following each title's intrinsic width made short titles
                    // pull 01HR/AGO towards the middle, while long titles pushed
                    // them to the edge. The title elides against this stable
                    // rail; the two timestamp glyphs stay adjacent.
                    // The age wrapper retains its compact authored width when
                    // AGE and AGO are adjacent. It spans both rails only after
                    // an explicit semantic split (AGE | TITLE | AGO).
                    x: Math.min(postRow.columnX("age"), postRow.columnX("ago"))
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.max(postRow.columnX("age") + postRow.ageRailWidth,
                        postRow.columnX("ago") + postRow.agoRailWidth) - x
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
                        x: postRow.columnX("age") - ageText.x
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.max(44.0, redditRoot.redditModel.ageFontSize * 4.4)
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
                        x: postRow.columnX("ago") - ageText.x
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
                    x: postRow.columnX("title")
                    // One variable-width title rail follows the same discrete
                    // semantic permutation on EVERY row, including after reflow.
                    width: postRow.columnWidth("title")
                    anchors.verticalCenter: parent.verticalCenter
                    // Post text remains left-aligned in both arrangements. The
                    // timestamp occupies the opposite fixed-width semantic rail.
                    horizontalAlignment: Text.AlignLeft
                    height: parent.height
                    text: postRow.postTitle
                    color: postHover.hovered && postRow.canActivate
                        ? "white" : redditRoot.redditModel.textColor
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
                    color: postHover.hovered && postRow.canActivate
                        ? "white" : redditRoot.redditModel.separatorColor
                }

                TapHandler {
                    enabled: postRow.canActivate
                    acceptedButtons: Qt.LeftButton
                    onTapped: redditRoot.openPostRequested(postRow.postUrl)
                }
            }
        }
    }
}
