import QtQuick

OverlayWidget {
    id: gmailRoot
    objectName: "gmailPresentation"


    required property var gmailModel
    semanticDoubleClickEnabled: gmailModel.interactionEnabled
    // CUSTOM resize uses the same retained whole-card scale as Reddit/Media.
    // Fixed row/header minima are authored at baseline and therefore shrink
    // with the presentation instead of escaping a smaller outer rectangle.
    uniformScaleTransform: true
    property string activeActionIdentity: ""
    property string activeActionMessageId: ""
    property bool activeActionUnread: false
    property bool activeActionArchiveSupported: false
    property real actionPopupX: 0.0
    property real actionPopupY: 0.0
    readonly property real committedContentHeight: gmailModel.contentHeight

    // Content-driven outer size (H option A): Gmail is a fixed-width list card;
    // its preferred width is the authored width setting (via the model) and its
    // height is the model-computed content height. Both are size-only model
    // reports independent of the assigned width - no width<->preferredWidth
    // feedback. J refines exact insets against eyes-on parity.
    // Gmail model width is already the authored outer-card width.  Height is
    // row/content-derived and excludes the shell inset, so only height needs
    // compensation for recreation containment.  Adding shellInset to width
    // lies to CUSTOM about the editable outer rect and breaks alignment.
    // CUSTOM content-extent box (0 = none). Vertical drives the effective visible
    // email count then row/separator spread; horizontal widens the card so more
    // sender/subject text shows before width-elide. `limit` stays the SSOT
    // default visible count when no extent is active.
    readonly property real cExtentW: gmailModel.contentExtentWidth
    readonly property real cExtentH: gmailModel.contentExtentHeight
    readonly property real naturalRowHeight: Math.max(28.0, gmailModel.fontSize * 1.65)
    readonly property real baseRowSpacing: 4.0
    readonly property var childGeometry: gmailModel.customChildGeometry
    // Header alignment is the existing widget-wide semantic flip intent.
    // Project structural rails, NEVER mirror glyphs or text alignment.
    readonly property bool headerFlipped: childAlignment("header", "left") === "right"
    readonly property var visualColumnOrder: {
        const saved = gmailModel.customColumnOrder
        return saved && saved.length === 3 ? saved
            : (headerFlipped ? ["sender", "subject", "timestamp"]
                             : ["timestamp", "sender", "subject"])
    }
    customColumnRailSpecs: {
        // No repeated-row descriptor lookup in ordinary playback.
        if (!gmailRoot.customLayoutInputBlocked) return []
        const order = gmailRoot.visualColumnOrder
        const first = messageRepeater.count > 0 ? messageRepeater.itemAt(0) : null
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
        gmailModel.contentWidth,
        headerFrame.implicitWidth
            + (refreshTarget.visible ? refreshTarget.implicitWidth + 10.0 : 0.0)
            + gmailRoot.shellInset
    )
    readonly property real canonicalAuthoredHeight: Math.max(
        60.0,
        headerFrame.implicitHeight
            + baseRowSpacing
            + Math.max(1, gmailModel.emailLimit) * naturalRowHeight
            + Math.max(0, gmailModel.emailLimit - 1) * baseRowSpacing
            + gmailRoot.shellInset
    )
    readonly property real childNormalizationWidth: canonicalPreferredWidth
    readonly property real childNormalizationHeight: canonicalAuthoredHeight


    readonly property int heldEmailCount: messageRepeater.count
    readonly property real chromeHeight: headerArea.height
        + (statusArea.visible ? statusArea.height + baseRowSpacing : 0.0)
        + gmailRoot.shellInset
    readonly property real emailRailBudget: Math.max(0.0, cExtentH - chromeHeight)
    readonly property int effectiveVisibleCount: {
        var held = Math.max(0, heldEmailCount)
        if (held === 0)
            return 0
        if (cExtentH <= 0.0)
            return Math.min(held, gmailModel.emailLimit)   // SSOT default count
        var fit = Math.floor(emailRailBudget / (naturalRowHeight + baseRowSpacing))
        return Math.max(1, Math.min(held, fit))            // CUSTOM: 1..held (<=cap)
    }
    // Rows grow to fill the box once the count caps (past-limit vertical padding).
    readonly property real extentRowHeight: {
        if (cExtentH <= 0.0 || effectiveVisibleCount <= 0)
            return naturalRowHeight
        var gaps = Math.max(0, effectiveVisibleCount - 1)
        return Math.max(
            naturalRowHeight,
            (emailRailBudget - gaps * baseRowSpacing) / effectiveVisibleCount
        )
    }
    // Separator thicknesses stay the authored settings by default and scale up
    // with the row spread in CUSTOM (setting = default, extent = override).
    readonly property real extentSeparatorScale: cExtentH > 0.0
        ? Math.max(1.0, Math.min(2.5, extentRowHeight / naturalRowHeight))
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
        : gmailModel.contentHeight + gmailRoot.shellInset

    signal openInboxRequested()
    signal openMessageRequested(string messageId)
    signal refreshRequested()
    signal authRequested()
    signal actionMenuPointerGesture()
    signal actionRequested(string action, string messageId)

    function dispatchAction(action, messageId) {
        // Arm the shared same-gesture click-through guard before dismissing the
        // retained popup. The action may overlap another Gmail row, and Quick
        // TapHandlers use passive grabs, so that row can otherwise see this same
        // release after the menu action has already fired.
        actionMenuPointerGesture()
        dismissActionMenu()
        actionRequested(action, messageId)
    }

    function dismissActionMenu() {
        activeActionIdentity = ""
        activeActionMessageId = ""
    }

    function toggleActionMenu(identity, messageId, unread, archiveSupported, anchor) {
        if (activeActionIdentity === identity) {
            dismissActionMenu()
            return
        }
        var mapped = anchor.mapToItem(actionPopup.parent, 0.0, anchor.height)
        activeActionIdentity = identity
        activeActionMessageId = messageId
        activeActionUnread = unread
        activeActionArchiveSupported = archiveSupported
        actionPopupX = Math.max(0.0, Math.min(
            mapped.x + anchor.width - actionPopup.width,
            actionPopup.parent.width - actionPopup.width
        ))
        actionPopupY = mapped.y
    }

    // Exact width of a full DD/MM/YYYY date at the timestamp render font
    // (fontSize-5). Measured once and reused by every row so the fixed date
    // column always fits the longest date - old-dated rows show the whole date
    // instead of eliding, and the sender left edge stays aligned on every row.
    TextMetrics {
        id: dateMetrics
        font.family: gmailRoot.gmailModel.fontFamily
        font.pointSize: gmailRoot.gmailModel.timestampFontSize
        text: "00/00/0000"
    }

    Connections {
        target: gmailRoot.gmailModel

        function onStateChanged() {
            if (!gmailRoot.gmailModel.interactionEnabled
                    || !gmailRoot.gmailModel.showThreeDotMenu
                    || (gmailRoot.activeActionMessageId.length > 0
                        && !gmailRoot.gmailModel.ownsMessage(
                            gmailRoot.activeActionMessageId
                        ))) {
                gmailRoot.dismissActionMenu()
            }
        }
    }

    Item {
        id: blankRefreshArea
        objectName: "gmailBlankRefreshArea"
        anchors.fill: parent
        z: -10

        TapHandler {
            enabled: gmailRoot.gmailModel.interactionEnabled
            acceptedButtons: Qt.LeftButton
            onDoubleTapped: gmailRoot.refreshRequested()
        }
    }

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
        return roles
    }

    Column {
        id: contentColumn
        objectName: "gmailContent"
        anchors.fill: parent
        spacing: 4.0

        Item {
            id: headerArea
            objectName: "gmailHeaderArea"
            width: parent.width
            height: headerFrame.implicitHeight

            BrandedHeader {
                id: headerFrame
                frameObjectName: "gmailHeaderFrame"
                logoObjectName: "gmailHeaderLogo"
                textObjectName: "gmailHeaderText"
                readonly property string customAnchor: gmailRoot.childAnchor("header")
                readonly property real customScale: gmailRoot.childWidthScale("header")
                property real customEditPlacementCompensationX:
                    customAnchor.length > 0 || gmailRoot.headerFlipped
                        ? x - gmailRoot.childOffsetX("header") : 0.0
                property real customEditPlacementCompensationY: customAnchor.length > 0
                    ? y - gmailRoot.childOffsetY("header") : 0.0
                transformOrigin: Item.TopLeft
                scale: customScale
                x: customAnchor.endsWith("right")
                    ? headerArea.width - width * scale
                    : (customAnchor.endsWith("left") ? 0.0
                        : (gmailRoot.headerFlipped ? headerArea.width - width * scale : 0.0)
                            + gmailRoot.childOffsetX("header"))
                y: customAnchor.startsWith("bottom")
                    ? headerArea.height - height * scale
                    : (customAnchor.startsWith("top") ? 0.0 : gmailRoot.childOffsetY("header"))
                contentReversed: gmailRoot.headerFlipped
                label: gmailRoot.gmailModel.headerText
                logoSource: gmailRoot.gmailModel.logoSource
                logoDesaturated: gmailRoot.gmailModel.desaturateLogo
                interactionEnabled: gmailRoot.gmailModel.interactionEnabled
                fillColor: gmailRoot.gmailModel.headerFillColor
                borderColor: gmailRoot.gmailModel.headerBorderColor
                borderWidth: gmailRoot.scaleAwareHeaderStrokeWidth(
                    gmailRoot.gmailModel.showHeaderBorder
                        ? gmailRoot.gmailModel.headerBorderWidth : 0.0
                )
                textColor: gmailRoot.gmailModel.headerTextColor
                fontFamily: gmailRoot.gmailModel.fontFamily
                textShadowEnabled: gmailRoot.gmailModel.textShadowEnabled
                textShadowColor: gmailRoot.gmailModel.textShadowColor
                textShadowOffsetX: gmailRoot.gmailModel.textShadowOffsetX
                textShadowOffsetY: gmailRoot.gmailModel.textShadowOffsetY
                shadowEnabled: gmailRoot.cardShadowEnabled
                shadowColor: Qt.rgba(
                    gmailRoot.cardShadowColor.r, gmailRoot.cardShadowColor.g,
                    gmailRoot.cardShadowColor.b, gmailRoot.cardShadowColor.a * 0.45
                )
                shadowBlur: Math.max(2.0, Math.min(6.0, gmailRoot.cardShadowBlur * 0.25))
                shadowOffsetX: gmailRoot.cardShadowOffsetX * 1.15
                shadowOffsetY: gmailRoot.cardShadowOffsetY * 1.15
                onActivated: gmailRoot.openInboxRequested()
            }

            Item {
                id: refreshTarget
                objectName: "gmailRefreshTarget"
                // The glyph and shadow must stay inside their bounded edit
                // target, not merely rely on the outer card to conceal escape.
                clip: true
                readonly property real implicitWidth: Math.max(24.0, refreshGlyph.implicitWidth + 4.0)
                visible: gmailRoot.gmailModel.showRefreshSpiral
                // Saved offsets are REQUESTS, not permission to escape the
                // header's actual bounded accessory slot. Keep the edit target
                // and painted glyph in exactly the same admitted rectangle.
                width: Math.min(Math.max(1.0, headerArea.width),
                    implicitWidth * gmailRoot.childWidthScale("refresh"))
                height: Math.min(Math.max(1.0, headerArea.height),
                    headerArea.height * gmailRoot.childHeightScale("refresh"))
                x: Math.max(0.0, Math.min(headerArea.width - width,
                    (gmailRoot.headerFlipped ? 0.0 : headerArea.width - width)
                        + gmailRoot.childOffsetX("refresh")))
                y: Math.max(0.0, Math.min(headerArea.height - height,
                    (headerArea.height - height) / 2.0 + gmailRoot.childOffsetY("refresh")))

                ShadowedText {
                    id: refreshGlyph
                    objectName: "gmailRefreshGlyph"
                    anchors.fill: parent
                    text: gmailRoot.gmailModel.refreshing ? "◌" : "↻"
                    opacity: 0.7
                    color: gmailRoot.gmailModel.textColor
                    font.family: gmailRoot.gmailModel.fontFamily
                    font.pointSize: gmailRoot.gmailModel.fontSize
                        * gmailRoot.childHeightScale("refresh")
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    shadowEnabled: gmailRoot.gmailModel.textShadowEnabled
                    shadowColor: gmailRoot.gmailModel.textShadowColor
                    shadowOffsetX: gmailRoot.gmailModel.textShadowOffsetX
                    shadowOffsetY: gmailRoot.gmailModel.textShadowOffsetY

                    TapHandler {
                        enabled: gmailRoot.gmailModel.interactionEnabled
                        acceptedButtons: Qt.LeftButton
                        onTapped: gmailRoot.refreshRequested()
                    }
                }
            }
        }

        Item {
            id: statusArea
            objectName: "gmailStatusArea"
            width: parent.width
            height: visible ? Math.max(42.0, statusText.implicitHeight + 10.0) : 0.0
            visible: gmailRoot.gmailModel.viewState !== "ready"

            ShadowedText {
                id: statusText
                objectName: "gmailStatusText"
                anchors.fill: parent
                text: {
                    if (gmailRoot.gmailModel.viewState === "error") {
                        return gmailRoot.gmailModel.errorText.toLowerCase().indexOf("auth") >= 0
                            ? "Gmail not connected. Tap to authenticate."
                            : "Gmail unavailable. Tap to retry."
                    }
                    if (gmailRoot.gmailModel.viewState === "empty")
                        return "No unread emails"
                    return "Loading Gmail…"
                }
                color: gmailRoot.gmailModel.textColor
                font.family: gmailRoot.gmailModel.fontFamily
                font.pointSize: gmailRoot.gmailModel.fontSize
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                wrap: true
                shadowEnabled: gmailRoot.gmailModel.textShadowEnabled
                shadowColor: gmailRoot.gmailModel.textShadowColor
                shadowOffsetX: gmailRoot.gmailModel.textShadowOffsetX
                shadowOffsetY: gmailRoot.gmailModel.textShadowOffsetY
            }

            TapHandler {
                enabled: gmailRoot.gmailModel.interactionEnabled
                    && gmailRoot.gmailModel.viewState === "error"
                acceptedButtons: Qt.LeftButton
                onTapped: {
                    if (gmailRoot.gmailModel.errorText.toLowerCase().indexOf("auth") >= 0)
                        gmailRoot.authRequested()
                    else
                        gmailRoot.refreshRequested()
                }
            }
        }

        Repeater {
            id: messageRepeater
            objectName: "gmailMessageRepeater"
            model: gmailRoot.gmailModel.rowModel

            delegate: Item {
                id: messageRow
                required property string messageIdentity
                required property string messageId
                required property string messageSender
                required property string messageSubject
                required property string messageTimestamp
                required property bool messageUnread
                required property int messageCount
                required property bool archiveSupported
                required property bool boundaryBefore
                required property int index

                readonly property real baseRowHeight: Math.max(
                    28.0, gmailRoot.gmailModel.fontSize * 1.65
                )
                objectName: "gmailMessageRow_" + index
                    readonly property var columnTargets: ({"timestamp": timestampText,
                        "sender": senderText, "subject": subjectText})

                width: contentColumn.width
                visible: index < gmailRoot.effectiveVisibleCount
                height: visible ? boundary.height + gmailRoot.extentRowHeight : 0.0

                Rectangle {
                    id: boundary
                    objectName: "gmailBoundary_" + messageRow.index
                    anchors.top: parent.top
                    width: parent.width
                    height: visible ? gmailRoot.scaleAwareStrokeWidth(
                        gmailRoot.gmailModel.boundarySeparatorThickness
                            * gmailRoot.extentSeparatorScale
                    ) : 0.0
                    visible: gmailRoot.gmailModel.showSeparators
                        && messageRow.boundaryBefore
                        && messageRow.index < gmailRoot.effectiveVisibleCount
                    color: gmailRoot.gmailModel.boundarySeparatorColor
                }

                Item {
                    id: rowContent
                    anchors.top: boundary.bottom
                    width: parent.width
                    height: gmailRoot.extentRowHeight

                    Image {
                        id: envelope
                        objectName: "gmailEnvelope_" + messageRow.index
                        visible: gmailRoot.gmailModel.showEnvelopeIcon
                        x: gmailRoot.headerFlipped ? parent.width - width : 0.0
                        anchors.verticalCenter: parent.verticalCenter
                        width: visible ? 16.0 : 0.0
                        height: 16.0
                        source: messageRow.messageUnread
                            ? gmailRoot.gmailModel.unreadEnvelopeSource
                            : gmailRoot.gmailModel.readEnvelopeSource
                        sourceSize.width: 32
                        sourceSize.height: 32
                        fillMode: Image.PreserveAspectFit
                        cache: true
                    }

                    Item {
                        id: openArea
                        // Explicit semantic rails avoid carrying a stale pair
                        // of opposite anchors across repeated flip/resize/reset.
                        // Both orientations reserve exactly the same space.
                        readonly property real semanticGap: 8.0
                        readonly property real stampWidth: Math.max(52.0, dateMetrics.width + 6.0)
                        readonly property real senderWidth: Math.max(1.0,
                            (width - stampWidth - semanticGap * 2.0)
                                * gmailRoot.gmailModel.senderSubjectRatio)
                        readonly property real subjectWidth: Math.max(1.0,
                            width - stampWidth - senderWidth - semanticGap * 2.0)
                        function columnWidth(role) {
                            if (role === "timestamp") return stampWidth
                            if (role === "sender") return senderWidth
                            return subjectWidth
                        }
                        function columnX(role) {
                            const order = gmailRoot.visualColumnOrder
                            let left = 0.0
                            for (let i = 0; i < order.length; ++i) {
                                if (order[i] === role) return left
                                left += columnWidth(order[i]) + semanticGap
                            }
                            return 0.0
                        }
                        readonly property real envelopeGap: envelope.visible ? 6.0 : 0.0
                        x: gmailRoot.headerFlipped
                            ? menuButton.width + 6.0 : envelope.width + envelopeGap
                        width: Math.max(1.0, parent.width - menuButton.width
                            - envelope.width - envelopeGap - 6.0)
                        height: parent.height

                        ShadowedText {
                            id: timestampText
                            objectName: "gmailTimestamp_" + messageRow.index
                            x: openArea.columnX("timestamp")
                            anchors.verticalCenter: parent.verticalCenter
                            horizontalAlignment: gmailRoot.headerFlipped
                                ? Text.AlignRight : Text.AlignLeft
                            // Fixed column sized to the widest date (measured, not
                            // guessed) so full dates never elide; kept constant across
                            // rows to align the sender edge.
                            width: openArea.stampWidth
                            height: parent.height
                            text: messageRow.messageTimestamp
                            color: gmailRoot.gmailModel.timestampColor
                            font.family: gmailRoot.gmailModel.fontFamily
                            font.pointSize: gmailRoot.gmailModel.timestampFontSize
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                            shadowEnabled: gmailRoot.gmailModel.textShadowEnabled
                            shadowColor: gmailRoot.gmailModel.textShadowColor
                            shadowOffsetX: gmailRoot.gmailModel.textShadowOffsetX
                            shadowOffsetY: gmailRoot.gmailModel.textShadowOffsetY
                        }

                        Item {
                            id: messageTextArea
                            // Text remains in reading order on the *opposite*
                            // side of the timestamp. Width cannot inherit a
                            // stale anchor when the header flip reverses twice.
                            x: 0.0
                            width: parent.width
                            height: parent.height

                            ShadowedText {
                                id: senderText
                                objectName: "gmailSender_" + messageRow.index
                                x: openArea.columnX("sender")
                                anchors.verticalCenter: parent.verticalCenter
                                width: openArea.senderWidth
                                height: parent.height
                                text: messageRow.messageSender
                                    + (messageRow.messageCount > 1
                                        ? " (" + messageRow.messageCount + ")" : "")
                                color: messageRow.messageUnread
                                    ? gmailRoot.gmailModel.senderColor
                                    : gmailRoot.gmailModel.readSenderColor
                                font.family: gmailRoot.gmailModel.fontFamily
                                font.pointSize: gmailRoot.gmailModel.fontSize
                                font.weight: messageRow.messageUnread ? Font.Bold : Font.DemiBold
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                                shadowEnabled: gmailRoot.gmailModel.textShadowEnabled
                                shadowColor: gmailRoot.gmailModel.textShadowColor
                                shadowOffsetX: gmailRoot.gmailModel.textShadowOffsetX
                                shadowOffsetY: gmailRoot.gmailModel.textShadowOffsetY
                            }

                            ShadowedText {
                                id: subjectText
                                objectName: "gmailSubject_" + messageRow.index
                                x: openArea.columnX("subject")
                                width: openArea.subjectWidth
                                anchors.verticalCenter: parent.verticalCenter
                                height: parent.height
                                text: messageRow.messageSubject
                                color: messageRow.messageUnread
                                    ? gmailRoot.gmailModel.textColor
                                    : gmailRoot.gmailModel.readSubjectColor
                                font.family: gmailRoot.gmailModel.fontFamily
                                font.pointSize: gmailRoot.gmailModel.fontSize
                                font.weight: messageRow.messageUnread ? Font.DemiBold : Font.Normal
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                                shadowEnabled: gmailRoot.gmailModel.textShadowEnabled
                                shadowColor: gmailRoot.gmailModel.textShadowColor
                                shadowOffsetX: gmailRoot.gmailModel.textShadowOffsetX
                                shadowOffsetY: gmailRoot.gmailModel.textShadowOffsetY
                            }
                        }

                        TapHandler {
                            enabled: gmailRoot.gmailModel.interactionEnabled
                            acceptedButtons: Qt.LeftButton
                            onTapped: gmailRoot.openMessageRequested(messageRow.messageId)
                        }
                    }

                    Item {
                        id: menuButton
                        objectName: "gmailMenuButton_" + messageRow.index
                        visible: gmailRoot.gmailModel.showThreeDotMenu
                        x: gmailRoot.headerFlipped ? 0.0 : parent.width - width
                        width: visible ? 24.0 : 0.0
                        height: parent.height

                        ShadowedText {
                            anchors.fill: parent
                            text: "⋮"
                            color: gmailRoot.gmailModel.timestampColor
                            font.family: gmailRoot.gmailModel.fontFamily
                            font.pointSize: gmailRoot.gmailModel.fontSize + 2.0
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            shadowEnabled: gmailRoot.gmailModel.textShadowEnabled
                            shadowColor: gmailRoot.gmailModel.textShadowColor
                            shadowOffsetX: gmailRoot.gmailModel.textShadowOffsetX
                            shadowOffsetY: gmailRoot.gmailModel.textShadowOffsetY
                        }

                        TapHandler {
                            enabled: gmailRoot.gmailModel.interactionEnabled
                            acceptedButtons: Qt.LeftButton
                            onTapped: gmailRoot.toggleActionMenu(
                                messageRow.messageIdentity,
                                messageRow.messageId,
                                messageRow.messageUnread,
                                messageRow.archiveSupported,
                                menuButton
                            )
                        }
                    }
                }

                Rectangle {
                    objectName: "gmailSeparator_" + messageRow.index
                    visible: gmailRoot.gmailModel.showSeparators
                        && messageRow.index < gmailRoot.effectiveVisibleCount - 1
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: visible ? gmailRoot.scaleAwareStrokeWidth(
                        gmailRoot.gmailModel.separatorThickness
                            * gmailRoot.extentSeparatorScale
                    ) : 0.0
                    color: gmailRoot.gmailModel.separatorColor
                }
            }
        }
    }

    Item {
        id: actionDismissLayer
        objectName: "gmailActionDismissLayer"
        anchors.fill: parent
        visible: gmailRoot.activeActionIdentity.length > 0
        z: 90

        TapHandler {
            acceptedButtons: Qt.LeftButton
            onTapped: {
                // Dismissing the overlay is still a pointer gesture over live
                // Gmail content; guard it for the same passive-grab reason as
                // action activation so dismissal cannot open a covered row.
                gmailRoot.actionMenuPointerGesture()
                gmailRoot.dismissActionMenu()
            }
        }
    }

    Rectangle {
        id: actionPopup
        objectName: "gmailActionPopup"
        visible: gmailRoot.activeActionIdentity.length > 0
        x: gmailRoot.actionPopupX
        y: Math.max(0.0, Math.min(
            gmailRoot.actionPopupY,
            parent.height - height
        ))
        width: Math.min(190.0, parent.width)
        height: popupColumn.implicitHeight + 8.0
        radius: 6.0
        color: gmailRoot.gmailModel.actionPopupSurfaceColor
        border.width: gmailRoot.scaleAwareStrokeWidth(2.0)
        border.color: gmailRoot.gmailModel.actionPopupBorderColor
        z: 100

        function actions() {
            var values = [gmailRoot.activeActionUnread ? "mark_read" : "mark_unread"]
            if (gmailRoot.activeActionArchiveSupported)
                values.push("archive")
            values.push("spam")
            values.push("trash")
            return values
        }

        Column {
            id: popupColumn
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 4.0
            spacing: 1.0

            Repeater {
                id: popupActionRepeater
                model: actionPopup.actions()

                delegate: Rectangle {
                    id: popupAction
                    required property string modelData
                    required property int index

                    objectName: "gmailAction_" + modelData
                    width: popupColumn.width
                    height: Math.max(30.0, gmailRoot.gmailModel.fontSize * 1.8)
                    radius: 3.0
                    color: actionHover.hovered
                        ? gmailRoot.gmailModel.actionPopupHoverColor : "transparent"

                    Row {
                        anchors.fill: parent
                        anchors.leftMargin: 8.0
                        anchors.rightMargin: 8.0
                        spacing: 8.0

                        Image {
                            objectName: "gmailActionIcon_" + popupAction.modelData
                            anchors.verticalCenter: parent.verticalCenter
                            width: 16.0
                            height: 16.0
                            source: gmailRoot.gmailModel.actionIconSource(
                                popupAction.modelData
                            )
                            sourceSize.width: 32
                            sourceSize.height: 32
                            fillMode: Image.PreserveAspectFit
                            cache: true
                        }

                        Text {
                            width: parent.width - 24.0
                            height: parent.height
                            text: {
                                if (popupAction.modelData === "mark_read") return "Mark as Read"
                                if (popupAction.modelData === "mark_unread") return "Mark as Unread"
                                if (popupAction.modelData === "archive") return "Archive"
                                if (popupAction.modelData === "spam") return "Mark as Spam"
                                return "Delete"
                            }
                            color: gmailRoot.gmailModel.actionPopupTextColor
                            font.family: gmailRoot.gmailModel.fontFamily
                            font.pixelSize: 12.0
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }
                    }

                    HoverHandler {
                        id: actionHover
                        enabled: gmailRoot.gmailModel.interactionEnabled
                    }

                    TapHandler {
                        enabled: gmailRoot.gmailModel.interactionEnabled
                        acceptedButtons: Qt.LeftButton
                        onTapped: gmailRoot.dispatchAction(
                            popupAction.modelData,
                            gmailRoot.activeActionMessageId
                        )
                    }
                }
            }
        }
    }
}
