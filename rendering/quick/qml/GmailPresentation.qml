import QtQuick

OverlayWidget {
    id: gmailRoot
    objectName: "gmailPresentation"

    required property var gmailModel
    property string activeActionIdentity: ""

    signal openInboxRequested()
    signal openMessageRequested(string messageId)
    signal refreshRequested()
    signal authRequested()
    signal actionRequested(string action, string messageId)

    function dispatchAction(action, messageId) {
        activeActionIdentity = ""
        actionRequested(action, messageId)
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
            height: Math.max(36.0, gmailRoot.gmailModel.headerLogoSize + 10.0)

            Rectangle {
                id: headerFrame
                objectName: "gmailHeaderFrame"
                anchors.left: parent.left
                width: Math.min(
                    parent.width - (refreshGlyph.visible ? refreshGlyph.width + 10.0 : 0.0),
                    headerRow.implicitWidth + 20.0
                )
                height: parent.height
                radius: 9.0
                color: "transparent"
                border.width: gmailRoot.gmailModel.showHeaderBorder ? 1.0 : 0.0
                border.color: gmailRoot.gmailModel.separatorColor

                Row {
                    id: headerRow
                    anchors.centerIn: parent
                    spacing: 8.0

                    Image {
                        id: gmailLogo
                        objectName: "gmailHeaderLogo"
                        source: gmailRoot.gmailModel.logoSource
                        width: gmailRoot.gmailModel.headerLogoSize
                        height: width
                        sourceSize.width: width * 2.0
                        sourceSize.height: height * 2.0
                        fillMode: Image.PreserveAspectFit
                        asynchronous: false
                        cache: true
                        opacity: gmailRoot.gmailModel.desaturateLogo ? 0.48 : 1.0
                    }

                    ShadowedText {
                        id: headerText
                        objectName: "gmailHeaderText"
                        text: gmailRoot.gmailModel.headerText
                        color: gmailRoot.gmailModel.textColor
                        font.family: gmailRoot.gmailModel.fontFamily
                        font.pointSize: gmailRoot.gmailModel.headerFontSize
                        font.bold: true
                        verticalAlignment: Text.AlignVCenter
                        shadowEnabled: gmailRoot.gmailModel.textShadowEnabled
                        shadowColor: gmailRoot.gmailModel.textShadowColor
                        shadowOffsetX: gmailRoot.gmailModel.textShadowOffsetX
                        shadowOffsetY: gmailRoot.gmailModel.textShadowOffsetY
                    }
                }

                TapHandler {
                    enabled: gmailRoot.gmailModel.interactionEnabled
                    acceptedButtons: Qt.LeftButton
                    onTapped: gmailRoot.openInboxRequested()
                }
            }

            ShadowedText {
                id: refreshGlyph
                objectName: "gmailRefreshGlyph"
                visible: gmailRoot.gmailModel.showRefreshSpiral
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: Math.max(24.0, implicitWidth + 4.0)
                height: parent.height
                text: gmailRoot.gmailModel.refreshing ? "◌" : "↻"
                color: gmailRoot.gmailModel.textColor
                font.family: gmailRoot.gmailModel.fontFamily
                font.pointSize: gmailRoot.gmailModel.fontSize
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
                readonly property bool menuOpen: gmailRoot.activeActionIdentity
                    === messageIdentity

                objectName: "gmailMessageRow_" + index
                width: contentColumn.width
                height: boundary.height + baseRowHeight
                    + (menuOpen ? actionMenu.height : 0.0)

                Rectangle {
                    id: boundary
                    objectName: "gmailBoundary_" + messageRow.index
                    anchors.top: parent.top
                    width: parent.width
                    height: visible ? gmailRoot.gmailModel.boundarySeparatorThickness : 0.0
                    visible: gmailRoot.gmailModel.showSeparators
                        && messageRow.boundaryBefore
                    color: gmailRoot.gmailModel.boundarySeparatorColor
                }

                Item {
                    id: rowContent
                    anchors.top: boundary.bottom
                    width: parent.width
                    height: messageRow.baseRowHeight

                    Image {
                        id: envelope
                        objectName: "gmailEnvelope_" + messageRow.index
                        visible: gmailRoot.gmailModel.showEnvelopeIcon
                        anchors.left: parent.left
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
                        anchors.left: envelope.right
                        anchors.leftMargin: envelope.visible ? 6.0 : 0.0
                        anchors.right: menuButton.left
                        anchors.rightMargin: 6.0
                        height: parent.height

                        ShadowedText {
                            id: timestampText
                            objectName: "gmailTimestamp_" + messageRow.index
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            width: messageRow.messageTimestamp.length > 0
                                ? Math.max(58.0, gmailRoot.gmailModel.fontSize * 4.8)
                                : 0.0
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
                            anchors.left: timestampText.right
                            anchors.right: parent.right
                            height: parent.height

                            ShadowedText {
                                id: senderText
                                objectName: "gmailSender_" + messageRow.index
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                width: messageRow.messageSender.length > 0
                                    ? parent.width * gmailRoot.gmailModel.senderSubjectRatio
                                    : 0.0
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
                                anchors.left: senderText.right
                                anchors.leftMargin: senderText.width > 0.0 ? 8.0 : 0.0
                                anchors.right: parent.right
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
                        anchors.right: parent.right
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
                            onTapped: gmailRoot.activeActionIdentity = messageRow.menuOpen
                                ? "" : messageRow.messageIdentity
                        }
                    }
                }

                Row {
                    id: actionMenu
                    objectName: "gmailActionMenu_" + messageRow.index
                    anchors.top: rowContent.bottom
                    width: parent.width
                    height: messageRow.menuOpen ? Math.max(
                        30.0, gmailRoot.gmailModel.fontSize * 1.7
                    ) : 0.0
                    visible: messageRow.menuOpen
                    spacing: 4.0

                    function actions() {
                        var values = [messageRow.messageUnread ? "mark_read" : "mark_unread"]
                        if (messageRow.archiveSupported)
                            values.push("archive")
                        values.push("spam")
                        values.push("trash")
                        return values
                    }

                    Repeater {
                        id: actionRepeater
                        model: actionMenu.actions()

                        delegate: Rectangle {
                            id: actionChip
                            required property string modelData
                            required property int index

                            objectName: "gmailAction_" + modelData + "_" + messageRow.index
                            width: Math.max(1.0, (
                                actionMenu.width
                                - actionMenu.spacing * Math.max(0, actionRepeater.count - 1)
                            ) / Math.max(1, actionRepeater.count))
                            height: actionMenu.height
                            radius: 5.0
                            color: "#dc2b2b2b"
                            border.width: 1.0
                            border.color: "#c89a9a9a"

                            ShadowedText {
                                anchors.fill: parent
                                text: {
                                    if (actionChip.modelData === "mark_read") return "Read"
                                    if (actionChip.modelData === "mark_unread") return "Unread"
                                    if (actionChip.modelData === "archive") return "Archive"
                                    if (actionChip.modelData === "spam") return "Spam"
                                    return "Delete"
                                }
                                color: gmailRoot.gmailModel.textColor
                                font.family: gmailRoot.gmailModel.fontFamily
                                font.pointSize: Math.max(8.0, gmailRoot.gmailModel.fontSize - 2.0)
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                                shadowEnabled: gmailRoot.gmailModel.textShadowEnabled
                                shadowColor: gmailRoot.gmailModel.textShadowColor
                                shadowOffsetX: gmailRoot.gmailModel.textShadowOffsetX
                                shadowOffsetY: gmailRoot.gmailModel.textShadowOffsetY
                            }

                            TapHandler {
                                enabled: gmailRoot.gmailModel.interactionEnabled
                                acceptedButtons: Qt.LeftButton
                                onTapped: gmailRoot.dispatchAction(
                                    actionChip.modelData, messageRow.messageId
                                )
                            }
                        }
                    }
                }

                Rectangle {
                    objectName: "gmailSeparator_" + messageRow.index
                    visible: gmailRoot.gmailModel.showSeparators
                        && messageRow.index < messageRepeater.count - 1
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: visible ? gmailRoot.gmailModel.separatorThickness : 0.0
                    color: gmailRoot.gmailModel.separatorColor
                }
            }
        }
    }
}
