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

    // Gmail retains the authored fixed-width/list-population contract. CUSTOM
    // child geometry is additive and normalized against one stable authored box;
    // repeated message roles share one record regardless of message count.
    readonly property real cExtentW: gmailModel.contentExtentWidth
    readonly property real cExtentH: gmailModel.contentExtentHeight
    readonly property real naturalRowHeight: Math.max(28.0, gmailModel.fontSize * 1.65)
    readonly property real baseRowSpacing: 4.0
    readonly property var childGeometry: gmailModel.customChildGeometry
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
    readonly property real messageRowWidthScale: childWidthScale("message_rows")
    readonly property real messageRowHeightScale: childHeightScale("message_rows")
    readonly property real messageRowsXOffset: childOffsetX("message_rows")
    readonly property real messageRowsYOffset: childOffsetY("message_rows")
    readonly property real effectiveBaseRowHeight: naturalRowHeight * messageRowHeightScale
    readonly property bool messageVerticalGeometryActive:
        Math.abs(messageRowHeightScale - 1.0) > childPlacementEpsilon
        || Math.abs(messageRowsYOffset) > childPlacementEpsilon
    readonly property real chromeHeight: headerArea.height
        + (statusArea.visible ? statusArea.height + baseRowSpacing : 0.0)
        + gmailRoot.shellInset
    // The repeated rail remains attached to the authored top flow. Moving the
    // shared rail downward consumes available list height; it never becomes a
    // second population authority and never requests parent growth on its own.
    readonly property real layoutHeightForRows: cExtentH > 0.0
        ? cExtentH : canonicalAuthoredHeight
    readonly property real emailRailBudget: Math.max(
        0.0,
        layoutHeightForRows - chromeHeight - Math.max(0.0, messageRowsYOffset)
    )
    readonly property int effectiveVisibleCount: {
        var held = Math.max(0, heldEmailCount)
        if (held === 0)
            return 0
        if (cExtentH <= 0.0 && !messageVerticalGeometryActive)
            return Math.min(held, gmailModel.emailLimit)
        var fit = Math.floor(emailRailBudget / (effectiveBaseRowHeight + baseRowSpacing))
        return Math.max(1, Math.min(held, fit))
    }
    // Once visible count caps, spare outer-Y extent remains row breathing room.
    // Shared row height can raise/lower density, but outer Y still decides count.
    readonly property real extentRowHeight: {
        if ((cExtentH <= 0.0 && !messageVerticalGeometryActive) || effectiveVisibleCount <= 0)
            return effectiveBaseRowHeight
        var gaps = Math.max(0, effectiveVisibleCount - 1)
        return Math.max(
            effectiveBaseRowHeight,
            (emailRailBudget - gaps * baseRowSpacing) / effectiveVisibleCount
        )
    }
    readonly property real extentSeparatorScale: cExtentH > 0.0
        ? Math.max(1.0, Math.min(2.5, extentRowHeight / Math.max(1.0, naturalRowHeight)))
        : 1.0
    readonly property bool hasVisibleBoundarySeparator: {
        if (!gmailModel.showSeparators || effectiveVisibleCount <= 0)
            return false
        for (let i = 0; i < effectiveVisibleCount; ++i) {
            const row = messageRepeater.itemAt(i)
            if (row && row.boundaryBefore)
                return true
        }
        return false
    }

    preferredContentWidth: cExtentW > 0.0 ? cExtentW : canonicalPreferredWidth
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
        if (gmailModel.viewState === "ready" && effectiveVisibleCount > 0) {
            const nestedRoles = [
                "envelopes", "timestamps", "senders", "subjects",
                "message_actions", "message_separators", "boundary_separators"
            ]
            roles.push({
                "roleId": "message_rows",
                "target": customMessageRowRoleTarget,
                "collisionIgnoreRoleIds": nestedRoles,
                "normalizationWidth": normW,
                "normalizationHeight": normH
            })
            if (customEnvelopeRoleTarget.visible) {
                roles.push({
                    "roleId": "envelopes",
                    "target": customEnvelopeRoleTarget,
                    "collisionIgnoreRoleIds": ["message_rows"],
                    "normalizationWidth": normW,
                    "normalizationHeight": normH
                })
            }
            roles.push({
                "roleId": "timestamps",
                "target": customTimestampRoleTarget,
                "collisionIgnoreRoleIds": ["message_rows"],
                "normalizationWidth": normW,
                "normalizationHeight": normH
            })
            if (customSenderRoleTarget.visible) {
                roles.push({
                    "roleId": "senders",
                    "target": customSenderRoleTarget,
                    "collisionIgnoreRoleIds": ["message_rows"],
                    "normalizationWidth": normW,
                    "normalizationHeight": normH
                })
            }
            if (customSubjectRoleTarget.visible) {
                roles.push({
                    "roleId": "subjects",
                    "target": customSubjectRoleTarget,
                    "collisionIgnoreRoleIds": ["message_rows"],
                    "normalizationWidth": normW,
                    "normalizationHeight": normH
                })
            }
            if (customMessageActionRoleTarget.visible) {
                roles.push({
                    "roleId": "message_actions",
                    "target": customMessageActionRoleTarget,
                    "collisionIgnoreRoleIds": ["message_rows"],
                    "normalizationWidth": normW,
                    "normalizationHeight": normH
                })
            }
            if (customMessageSeparatorRoleTarget.visible) {
                roles.push({
                    "roleId": "message_separators",
                    "target": customMessageSeparatorRoleTarget,
                    "occupiedTarget": customMessageSeparatorOccupiedTarget,
                    "collisionIgnoreRoleIds": ["message_rows"],
                    "normalizationWidth": normW,
                    "normalizationHeight": normH
                })
            }
            if (customBoundarySeparatorRoleTarget.visible) {
                roles.push({
                    "roleId": "boundary_separators",
                    "target": customBoundarySeparatorRoleTarget,
                    "occupiedTarget": customBoundarySeparatorOccupiedTarget,
                    "collisionIgnoreRoleIds": ["message_rows"],
                    "normalizationWidth": normW,
                    "normalizationHeight": normH
                })
            }
        }
        return roles
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
                property real customEditPlacementCompensationX: customAnchor.length > 0
                    ? x - gmailRoot.childOffsetX("header") : 0.0
                property real customEditPlacementCompensationY: customAnchor.length > 0
                    ? y - gmailRoot.childOffsetY("header") : 0.0
                transformOrigin: Item.TopLeft
                scale: customScale
                x: customAnchor.endsWith("right")
                    ? headerArea.width - width * scale
                    : (customAnchor.endsWith("left") ? 0.0 : gmailRoot.childOffsetX("header"))
                y: customAnchor.startsWith("bottom")
                    ? headerArea.height - height * scale
                    : (customAnchor.startsWith("top") ? 0.0 : gmailRoot.childOffsetY("header"))
                contentReversed: gmailRoot.childAlignment("header", "left") === "right"
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
                readonly property real implicitWidth: Math.max(24.0, refreshGlyph.implicitWidth + 4.0)
                visible: gmailRoot.gmailModel.showRefreshSpiral
                width: implicitWidth * gmailRoot.childWidthScale("refresh")
                height: headerArea.height * gmailRoot.childHeightScale("refresh")
                x: headerArea.width - width + gmailRoot.childOffsetX("refresh")
                y: (headerArea.height - height) / 2.0 + gmailRoot.childOffsetY("refresh")

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

                readonly property real authoredBoundaryHeight:
                    gmailRoot.gmailModel.showSeparators && boundaryBefore
                        ? gmailRoot.scaleAwareStrokeWidth(
                            gmailRoot.gmailModel.boundarySeparatorThickness
                                * gmailRoot.extentSeparatorScale
                        )
                        : 0.0
                readonly property real authoredEnvelopeWidth:
                    gmailRoot.gmailModel.showEnvelopeIcon ? 16.0 : 0.0
                readonly property real authoredEnvelopeGap:
                    gmailRoot.gmailModel.showEnvelopeIcon ? 6.0 : 0.0
                readonly property real authoredMenuWidth:
                    gmailRoot.gmailModel.showThreeDotMenu ? 24.0 : 0.0
                readonly property real authoredOpenX: authoredEnvelopeWidth + authoredEnvelopeGap
                readonly property real authoredOpenRightInset: authoredMenuWidth + 6.0
                readonly property real authoredOpenWidth: Math.max(
                    24.0, width - authoredOpenX - authoredOpenRightInset
                )
                readonly property real authoredTimestampWidth: messageTimestamp.length > 0
                    ? Math.max(52.0, dateMetrics.width + 6.0) : 0.0
                readonly property real authoredTimestampGap: messageTimestamp.length > 0 ? 8.0 : 0.0
                readonly property real authoredTextX:
                    authoredOpenX + authoredTimestampWidth + authoredTimestampGap
                readonly property real authoredTextWidth: Math.max(
                    24.0, width - authoredTextX - authoredOpenRightInset
                )
                readonly property real authoredSenderWidth: messageSender.length > 0
                    ? authoredTextWidth * gmailRoot.gmailModel.senderSubjectRatio : 0.0
                readonly property real authoredSubjectGap: authoredSenderWidth > 0.0 ? 8.0 : 0.0
                readonly property real authoredSubjectX:
                    authoredTextX + authoredSenderWidth + authoredSubjectGap
                readonly property real authoredSubjectWidth: Math.max(
                    0.0, width - authoredSubjectX - authoredOpenRightInset
                )

                objectName: "gmailMessageRow_" + index
                width: contentColumn.width * gmailRoot.messageRowWidthScale
                x: gmailRoot.messageRowsXOffset
                visible: index < gmailRoot.effectiveVisibleCount
                height: visible ? authoredBoundaryHeight + gmailRoot.extentRowHeight : 0.0
                transform: Translate { y: gmailRoot.messageRowsYOffset }

                Rectangle {
                    id: boundary
                    objectName: "gmailBoundary_" + messageRow.index
                    visible: gmailRoot.gmailModel.showSeparators
                        && messageRow.boundaryBefore
                        && messageRow.index < gmailRoot.effectiveVisibleCount
                    x: gmailRoot.childOffsetX("boundary_separators")
                    y: gmailRoot.childOffsetY("boundary_separators")
                    width: parent.width * gmailRoot.childWidthScale("boundary_separators")
                    height: visible
                        ? messageRow.authoredBoundaryHeight
                            * gmailRoot.childHeightScale("boundary_separators")
                        : 0.0
                    color: gmailRoot.gmailModel.boundarySeparatorColor
                }

                Item {
                    id: rowContent
                    x: 0.0
                    y: messageRow.authoredBoundaryHeight
                    width: parent.width
                    height: gmailRoot.extentRowHeight

                    Image {
                        id: envelope
                        objectName: "gmailEnvelope_" + messageRow.index
                        visible: gmailRoot.gmailModel.showEnvelopeIcon
                        x: gmailRoot.childOffsetX("envelopes")
                        y: (parent.height - height) / 2.0 + gmailRoot.childOffsetY("envelopes")
                        width: visible ? 16.0 * gmailRoot.childWidthScale("envelopes") : 0.0
                        height: visible ? 16.0 * gmailRoot.childHeightScale("envelopes") : 0.0
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
                        x: messageRow.authoredOpenX
                        width: messageRow.authoredOpenWidth
                        height: parent.height

                        TapHandler {
                            enabled: gmailRoot.gmailModel.interactionEnabled
                            acceptedButtons: Qt.LeftButton
                            onTapped: gmailRoot.openMessageRequested(messageRow.messageId)
                        }
                    }

                    ShadowedText {
                        id: timestampText
                        objectName: "gmailTimestamp_" + messageRow.index
                        x: messageRow.authoredOpenX + gmailRoot.childOffsetX("timestamps")
                        y: (parent.height - height) / 2.0 + gmailRoot.childOffsetY("timestamps")
                        width: messageRow.authoredTimestampWidth
                            * gmailRoot.childWidthScale("timestamps")
                        height: parent.height * gmailRoot.childHeightScale("timestamps")
                        text: messageRow.messageTimestamp
                        color: gmailRoot.gmailModel.timestampColor
                        font.family: gmailRoot.gmailModel.fontFamily
                        font.pointSize: gmailRoot.gmailModel.timestampFontSize
                            * gmailRoot.childHeightScale("timestamps")
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        shadowEnabled: gmailRoot.gmailModel.textShadowEnabled
                        shadowColor: gmailRoot.gmailModel.textShadowColor
                        shadowOffsetX: gmailRoot.gmailModel.textShadowOffsetX
                        shadowOffsetY: gmailRoot.gmailModel.textShadowOffsetY
                    }

                    ShadowedText {
                        id: senderText
                        objectName: "gmailSender_" + messageRow.index
                        visible: gmailRoot.gmailModel.showSender
                        x: messageRow.authoredTextX + gmailRoot.childOffsetX("senders")
                        y: (parent.height - height) / 2.0 + gmailRoot.childOffsetY("senders")
                        width: visible
                            ? messageRow.authoredSenderWidth * gmailRoot.childWidthScale("senders")
                            : 0.0
                        height: parent.height * gmailRoot.childHeightScale("senders")
                        text: messageRow.messageSender
                            + (messageRow.messageCount > 1
                                ? " (" + messageRow.messageCount + ")" : "")
                        color: messageRow.messageUnread
                            ? gmailRoot.gmailModel.senderColor
                            : gmailRoot.gmailModel.readSenderColor
                        font.family: gmailRoot.gmailModel.fontFamily
                        font.pointSize: gmailRoot.gmailModel.fontSize
                            * gmailRoot.childHeightScale("senders")
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
                        visible: gmailRoot.gmailModel.showSubject
                        x: messageRow.authoredSubjectX + gmailRoot.childOffsetX("subjects")
                        y: (parent.height - height) / 2.0 + gmailRoot.childOffsetY("subjects")
                        width: visible
                            ? messageRow.authoredSubjectWidth * gmailRoot.childWidthScale("subjects")
                            : 0.0
                        height: parent.height * gmailRoot.childHeightScale("subjects")
                        text: messageRow.messageSubject
                        color: messageRow.messageUnread
                            ? gmailRoot.gmailModel.textColor
                            : gmailRoot.gmailModel.readSubjectColor
                        font.family: gmailRoot.gmailModel.fontFamily
                        font.pointSize: gmailRoot.gmailModel.fontSize
                            * gmailRoot.childHeightScale("subjects")
                        font.weight: messageRow.messageUnread ? Font.DemiBold : Font.Normal
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        shadowEnabled: gmailRoot.gmailModel.textShadowEnabled
                        shadowColor: gmailRoot.gmailModel.textShadowColor
                        shadowOffsetX: gmailRoot.gmailModel.textShadowOffsetX
                        shadowOffsetY: gmailRoot.gmailModel.textShadowOffsetY
                    }

                    Item {
                        id: menuButton
                        objectName: "gmailMenuButton_" + messageRow.index
                        visible: gmailRoot.gmailModel.showThreeDotMenu
                        x: parent.width - 24.0 + gmailRoot.childOffsetX("message_actions")
                        y: (parent.height - height) / 2.0
                            + gmailRoot.childOffsetY("message_actions")
                        width: visible ? 24.0 * gmailRoot.childWidthScale("message_actions") : 0.0
                        height: parent.height * gmailRoot.childHeightScale("message_actions")

                        ShadowedText {
                            anchors.fill: parent
                            text: "⋮"
                            color: gmailRoot.gmailModel.timestampColor
                            font.family: gmailRoot.gmailModel.fontFamily
                            font.pointSize: (gmailRoot.gmailModel.fontSize + 2.0)
                                * gmailRoot.childHeightScale("message_actions")
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
                    id: messageSeparator
                    objectName: "gmailSeparator_" + messageRow.index
                    visible: gmailRoot.gmailModel.showSeparators
                        && messageRow.index < gmailRoot.effectiveVisibleCount - 1
                    x: gmailRoot.childOffsetX("message_separators")
                    y: parent.height - height + gmailRoot.childOffsetY("message_separators")
                    width: parent.width * gmailRoot.childWidthScale("message_separators")
                    height: visible ? gmailRoot.scaleAwareStrokeWidth(
                        gmailRoot.gmailModel.separatorThickness
                            * gmailRoot.extentSeparatorScale
                    ) * gmailRoot.childHeightScale("message_separators") : 0.0
                    color: gmailRoot.gmailModel.separatorColor
                }
            }
        }
    }

    // Representative edit surfaces for repeated semantic roles. Every delegate
    // consumes the same retained geometry record, so edit/persistence cost is
    // constant with mailbox size and never keys geometry by message identity.
    Item {
        id: customMessageRowRoleTarget
        objectName: "gmailCustomMessageRowRoleTarget"
        visible: gmailModel.viewState === "ready" && effectiveVisibleCount > 0
        enabled: false
        x: gmailRoot.messageRowsXOffset
        y: headerArea.height + baseRowSpacing + gmailRoot.messageRowsYOffset
        width: contentColumn.width * gmailRoot.messageRowWidthScale
        height: gmailRoot.extentRowHeight
    }
    Item {
        id: customEnvelopeRoleTarget
        objectName: "gmailCustomEnvelopeRoleTarget"
        visible: customMessageRowRoleTarget.visible && gmailModel.showEnvelopeIcon
        enabled: false
        x: customMessageRowRoleTarget.x + gmailRoot.childOffsetX("envelopes")
        y: customMessageRowRoleTarget.y
            + (customMessageRowRoleTarget.height - height) / 2.0
            + gmailRoot.childOffsetY("envelopes")
        width: 16.0 * gmailRoot.childWidthScale("envelopes")
        height: 16.0 * gmailRoot.childHeightScale("envelopes")
    }
    Item {
        id: customTimestampRoleTarget
        objectName: "gmailCustomTimestampRoleTarget"
        visible: customMessageRowRoleTarget.visible
        enabled: false
        readonly property real authoredOpenX: gmailModel.showEnvelopeIcon ? 22.0 : 0.0
        readonly property real authoredWidth: Math.max(52.0, dateMetrics.width + 6.0)
        x: customMessageRowRoleTarget.x + authoredOpenX
            + gmailRoot.childOffsetX("timestamps")
        y: customMessageRowRoleTarget.y
            + (customMessageRowRoleTarget.height - height) / 2.0
            + gmailRoot.childOffsetY("timestamps")
        width: authoredWidth * gmailRoot.childWidthScale("timestamps")
        height: customMessageRowRoleTarget.height * gmailRoot.childHeightScale("timestamps")
    }
    Item {
        id: customSenderRoleTarget
        objectName: "gmailCustomSenderRoleTarget"
        visible: customMessageRowRoleTarget.visible && gmailModel.showSender
        enabled: false
        readonly property real authoredMenuInset: gmailModel.showThreeDotMenu ? 30.0 : 6.0
        readonly property real authoredTextX: customTimestampRoleTarget.authoredOpenX
            + customTimestampRoleTarget.authoredWidth + 8.0
        readonly property real authoredTextWidth: Math.max(
            24.0, customMessageRowRoleTarget.width - authoredTextX - authoredMenuInset
        )
        readonly property real authoredWidth: authoredTextWidth * gmailModel.senderSubjectRatio
        x: customMessageRowRoleTarget.x + authoredTextX + gmailRoot.childOffsetX("senders")
        y: customMessageRowRoleTarget.y
            + (customMessageRowRoleTarget.height - height) / 2.0
            + gmailRoot.childOffsetY("senders")
        width: authoredWidth * gmailRoot.childWidthScale("senders")
        height: customMessageRowRoleTarget.height * gmailRoot.childHeightScale("senders")
    }
    Item {
        id: customSubjectRoleTarget
        objectName: "gmailCustomSubjectRoleTarget"
        visible: customMessageRowRoleTarget.visible && gmailModel.showSubject
        enabled: false
        readonly property real authoredMenuInset: gmailModel.showThreeDotMenu ? 30.0 : 6.0
        readonly property real authoredX: customSenderRoleTarget.authoredTextX
            + customSenderRoleTarget.authoredWidth
            + (customSenderRoleTarget.authoredWidth > 0.0 ? 8.0 : 0.0)
        readonly property real authoredWidth: Math.max(
            0.0, customMessageRowRoleTarget.width - authoredX - authoredMenuInset
        )
        x: customMessageRowRoleTarget.x + authoredX + gmailRoot.childOffsetX("subjects")
        y: customMessageRowRoleTarget.y
            + (customMessageRowRoleTarget.height - height) / 2.0
            + gmailRoot.childOffsetY("subjects")
        width: authoredWidth * gmailRoot.childWidthScale("subjects")
        height: customMessageRowRoleTarget.height * gmailRoot.childHeightScale("subjects")
    }
    Item {
        id: customMessageActionRoleTarget
        objectName: "gmailCustomMessageActionRoleTarget"
        visible: customMessageRowRoleTarget.visible && gmailModel.showThreeDotMenu
        enabled: false
        x: customMessageRowRoleTarget.x + customMessageRowRoleTarget.width - 24.0
            + gmailRoot.childOffsetX("message_actions")
        y: customMessageRowRoleTarget.y
            + (customMessageRowRoleTarget.height - height) / 2.0
            + gmailRoot.childOffsetY("message_actions")
        width: 24.0 * gmailRoot.childWidthScale("message_actions")
        height: customMessageRowRoleTarget.height * gmailRoot.childHeightScale("message_actions")
    }
    Item {
        id: customMessageSeparatorOccupiedTarget
        objectName: "gmailCustomMessageSeparatorOccupiedTarget"
        visible: customMessageRowRoleTarget.visible
            && gmailModel.showSeparators && effectiveVisibleCount > 1
        enabled: false
        x: customMessageRowRoleTarget.x + gmailRoot.childOffsetX("message_separators")
        y: customMessageRowRoleTarget.y + customMessageRowRoleTarget.height - height
            + gmailRoot.childOffsetY("message_separators")
        width: customMessageRowRoleTarget.width * gmailRoot.childWidthScale("message_separators")
        height: gmailRoot.scaleAwareStrokeWidth(
            gmailModel.separatorThickness * gmailRoot.extentSeparatorScale
        ) * gmailRoot.childHeightScale("message_separators")
    }
    Item {
        id: customMessageSeparatorRoleTarget
        objectName: "gmailCustomMessageSeparatorRoleTarget"
        visible: customMessageSeparatorOccupiedTarget.visible
        enabled: false
        readonly property real occupiedHeight: customMessageSeparatorOccupiedTarget.height
        x: customMessageSeparatorOccupiedTarget.x
        y: customMessageSeparatorOccupiedTarget.y - (height - occupiedHeight) / 2.0
        width: customMessageSeparatorOccupiedTarget.width
        height: 6.0 * gmailRoot.childHeightScale("message_separators")
    }
    Item {
        id: customBoundarySeparatorOccupiedTarget
        objectName: "gmailCustomBoundarySeparatorOccupiedTarget"
        visible: customMessageRowRoleTarget.visible && gmailRoot.hasVisibleBoundarySeparator
        enabled: false
        x: customMessageRowRoleTarget.x + gmailRoot.childOffsetX("boundary_separators")
        y: customMessageRowRoleTarget.y + gmailRoot.childOffsetY("boundary_separators")
        width: customMessageRowRoleTarget.width * gmailRoot.childWidthScale("boundary_separators")
        height: gmailRoot.scaleAwareStrokeWidth(
            gmailModel.boundarySeparatorThickness * gmailRoot.extentSeparatorScale
        ) * gmailRoot.childHeightScale("boundary_separators")
    }
    Item {
        id: customBoundarySeparatorRoleTarget
        objectName: "gmailCustomBoundarySeparatorRoleTarget"
        visible: customBoundarySeparatorOccupiedTarget.visible
        enabled: false
        readonly property real occupiedHeight: customBoundarySeparatorOccupiedTarget.height
        x: customBoundarySeparatorOccupiedTarget.x
        y: customBoundarySeparatorOccupiedTarget.y - (height - occupiedHeight) / 2.0
        width: customBoundarySeparatorOccupiedTarget.width
        height: 6.0 * gmailRoot.childHeightScale("boundary_separators")
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
