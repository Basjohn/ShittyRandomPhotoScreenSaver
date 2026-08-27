import QtQuick

Item {
    id: menuRoot
    objectName: "retainedContextMenu"

    required property var contextMenuModel
    property int activeSubmenuIndex: -1
    readonly property real menuWidth: 292.0
    readonly property real menuHeight: menuColumn.implicitHeight + 16.0

    anchors.fill: parent
    visible: contextMenuModel !== null && contextMenuModel.menuVisible
    enabled: visible

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        onPressed: menuRoot.contextMenuModel.dismiss()
    }

    Rectangle {
        id: menuSurface
        objectName: "retainedContextMenuSurface"
        width: menuRoot.menuWidth
        height: menuRoot.menuHeight
        x: Math.max(
            4.0,
            Math.min(
                menuRoot.contextMenuModel ? menuRoot.contextMenuModel.anchorX : 0.0,
                menuRoot.width - width - 4.0
            )
        )
        y: Math.max(
            4.0,
            Math.min(
                menuRoot.contextMenuModel ? menuRoot.contextMenuModel.anchorY : 0.0,
                menuRoot.height - height - 4.0
            )
        )
        color: "#f21b1d24"
        radius: 10.0
        border.color: "#d8f3ff"
        border.width: 3.0

        Column {
            id: menuColumn
            x: 6.0
            y: 8.0
            width: parent.width - 12.0

            Repeater {
                model: menuRoot.contextMenuModel
                    ? menuRoot.contextMenuModel.entries
                    : []

                delegate: Item {
                    id: menuRow
                    required property var modelData
                    required property int index
                    width: menuColumn.width
                    height: modelData.kind === "separator" ? 7.0 : 38.0

                    Rectangle {
                        anchors.centerIn: parent
                        width: parent.width - 24.0
                        height: 1.0
                        color: "#59778a"
                        visible: menuRow.modelData.kind === "separator"
                    }

                    Rectangle {
                        id: rowSurface
                        anchors.fill: parent
                        anchors.leftMargin: 5.0
                        anchors.rightMargin: 5.0
                        anchors.topMargin: 3.0
                        anchors.bottomMargin: 3.0
                        radius: 6.0
                        color: rowHover.hovered ? "#4f77b9e8" : "transparent"
                        opacity: menuRow.modelData.enabled ? 1.0 : 0.45
                        visible: menuRow.modelData.kind !== "separator"

                        Rectangle {
                            id: indicator
                            width: 20.0
                            height: 20.0
                            radius: 10.0
                            x: 8.0
                            anchors.verticalCenter: parent.verticalCenter
                            color: "transparent"
                            border.width: 2.0
                            border.color: "#b9eaff"
                            visible: menuRow.modelData.kind === "toggle"
                                || menuRow.modelData.kind === "choice"

                            Rectangle {
                                anchors.centerIn: parent
                                width: 10.0
                                height: 10.0
                                radius: 5.0
                                color: "#82cdff"
                                visible: menuRow.modelData.checked
                            }
                        }

                        Text {
                            anchors.left: indicator.visible ? indicator.right : parent.left
                            anchors.leftMargin: indicator.visible ? 10.0 : 10.0
                            anchors.right: submenuArrow.left
                            anchors.rightMargin: 8.0
                            anchors.verticalCenter: parent.verticalCenter
                            text: menuRow.modelData.label
                            color: "#f6f8ff"
                            elide: Text.ElideRight
                            font.family: "Jost"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }

                        Text {
                            id: submenuArrow
                            anchors.right: parent.right
                            anchors.rightMargin: 10.0
                            anchors.verticalCenter: parent.verticalCenter
                            text: "▸"
                            color: "#d8f3ff"
                            font.pixelSize: 16
                            visible: menuRow.modelData.kind === "submenu"
                        }

                        HoverHandler {
                            id: rowHover
                            enabled: menuRow.modelData.enabled
                            onHoveredChanged: {
                                if (hovered && menuRow.modelData.kind === "submenu")
                                    menuRoot.activeSubmenuIndex = menuRow.index
                            }
                        }

                        TapHandler {
                            enabled: menuRow.modelData.enabled
                            acceptedButtons: Qt.LeftButton
                            onTapped: {
                                if (menuRow.modelData.kind === "submenu") {
                                    menuRoot.activeSubmenuIndex = menuRow.index
                                    return
                                }
                                menuRoot.contextMenuModel.requestAction(
                                    menuRow.modelData.actionId,
                                    menuRow.modelData.payload,
                                    menuRow.modelData.kind === "toggle"
                                        ? !menuRow.modelData.checked
                                        : true
                                )
                            }
                        }
                    }

                    Rectangle {
                        id: submenuSurface
                        objectName: "retainedContextSubmenu"
                        x: menuSurface.x + menuSurface.width + width <= menuRoot.width
                            ? menuRow.width - 2.0
                            : -width + 2.0
                        y: Math.max(
                            4.0 - menuSurface.y - menuColumn.y - menuRow.y,
                            Math.min(
                                0.0,
                                menuRoot.height - 4.0
                                    - menuSurface.y - menuColumn.y - menuRow.y
                                    - height
                            )
                        )
                        width: 244.0
                        height: submenuColumn.implicitHeight + 12.0
                        color: "#f21b1d24"
                        radius: 8.0
                        border.color: "#d8f3ff"
                        border.width: 3.0
                        visible: menuRow.modelData.kind === "submenu"
                            && menuRoot.activeSubmenuIndex === menuRow.index
                        z: 20

                        Column {
                            id: submenuColumn
                            x: 4.0
                            y: 6.0
                            width: parent.width - 8.0

                            Repeater {
                                model: menuRow.modelData.children

                                delegate: Rectangle {
                                    id: submenuRow
                                    required property var modelData
                                    width: submenuColumn.width
                                    height: 34.0
                                    radius: 4.0
                                    color: submenuHover.hovered
                                        ? "#4f77b9e8"
                                        : (modelData.checked ? "#334e718b" : "transparent")
                                    opacity: modelData.enabled ? 1.0 : 0.45

                                    Rectangle {
                                        id: submenuIndicator
                                        width: 18.0
                                        height: 18.0
                                        radius: 9.0
                                        x: 6.0
                                        anchors.verticalCenter: parent.verticalCenter
                                        color: "transparent"
                                        border.width: 2.0
                                        border.color: "#b9eaff"

                                        Rectangle {
                                            anchors.centerIn: parent
                                            width: 9.0
                                            height: 9.0
                                            radius: 4.5
                                            color: "#82cdff"
                                            visible: submenuRow.modelData.checked
                                        }
                                    }

                                    Text {
                                        anchors.left: submenuIndicator.right
                                        anchors.leftMargin: 9.0
                                        anchors.right: parent.right
                                        anchors.rightMargin: 8.0
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: submenuRow.modelData.label
                                        color: submenuRow.modelData.checked
                                            ? "#b9eaff"
                                            : "#f6f8ff"
                                        elide: Text.ElideRight
                                        font.family: "Jost"
                                        font.pixelSize: 13
                                        font.weight: submenuRow.modelData.checked
                                            ? Font.Bold
                                            : Font.DemiBold
                                    }

                                    HoverHandler {
                                        id: submenuHover
                                        enabled: submenuRow.modelData.enabled
                                    }

                                    TapHandler {
                                        enabled: submenuRow.modelData.enabled
                                        acceptedButtons: Qt.LeftButton
                                        onTapped: menuRoot.contextMenuModel.requestAction(
                                            submenuRow.modelData.actionId,
                                            submenuRow.modelData.payload,
                                            true
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Connections {
        target: menuRoot.contextMenuModel

        function onVisibilityChanged(visible) {
            if (!visible)
                menuRoot.activeSubmenuIndex = -1
        }
    }
}
