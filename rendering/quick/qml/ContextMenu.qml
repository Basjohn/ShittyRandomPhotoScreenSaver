import QtQuick
import QtQuick.Effects

Item {
    id: menuRoot
    objectName: "retainedContextMenu"

    required property var contextMenuModel
    property bool shadowEnabled: true
    property color shadowColor: "#c4000000"
    property real shadowBlur: 18.0
    property real shadowOffsetX: 4.0
    property real shadowOffsetY: 4.0
    property real shadowExtendLeft: 0.0
    property real shadowExtendTop: 0.0
    property real shadowExtendRight: 0.0
    property real shadowExtendBottom: 0.0
    property color surfaceColor: "#f21b1d24"
    property color borderColor: "#d8f3ff"
    property color textColor: "#f6f8ff"
    property color selectedSurfaceColor: "#4f77b9e8"
    property color separatorColor: "#59778a"
    property color indicatorBorderColor: "#b9eaff"
    property color indicatorFillColor: "#82cdff"
    property color arrowColor: "#d8f3ff"
    property color submenuSurfaceColor: "#f21b1d24"
    property color submenuBorderColor: "#d8f3ff"
    property color submenuTextColor: "#f6f8ff"
    property color submenuSelectedSurfaceColor: "#4f77b9e8"
    property color submenuCheckedTextColor: "#b9eaff"
    property color submenuCheckedSurfaceColor: "#334e718b"
    property color submenuIndicatorBorderColor: "#b9eaff"
    property color submenuIndicatorFillColor: "#82cdff"
    readonly property real shadowBaseLeft: Math.max(0.0, -shadowOffsetX)
    readonly property real shadowBaseTop: Math.max(0.0, -shadowOffsetY)
    readonly property real shadowBaseRight: Math.max(0.0, shadowOffsetX)
    readonly property real shadowBaseBottom: Math.max(0.0, shadowOffsetY)
    property int activeSubmenuIndex: -1
    readonly property real menuWidth: 292.0
    readonly property real menuHeight: menuColumn.implicitHeight + 16.0

    anchors.fill: parent
    visible: contextMenuModel !== null && contextMenuModel.menuVisible
    enabled: visible

    // Click-outside-to-dismiss scrim. It must NOT dismiss on the very press that
    // opened the menu: that opening press flips menuVisible true (from the Python
    // input owner), which makes this scrim visible, and the same event is then
    // delivered here - self-dismissing the menu before it is ever seen. Arm the
    // scrim only AFTER the opening event completes (deferred via Qt.callLater, not
    // a polling timer), so only a genuinely subsequent press dismisses.
    MouseArea {
        id: dismissScrim
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        enabled: false
        onPressed: menuRoot.contextMenuModel.dismiss()
    }

    // Context-menu shadow is intentionally inside the menu's z=300 scene plane:
    // it therefore paints above widgets/Visualizer/edit chrome, but below the
    // menu surface itself. Direction/Extra Offset use one-sided geometry exactly
    // like ordinary Card shadows; RectangularShadow.offset remains zero.
    RectangularShadow {
        id: menuShadow
        objectName: "retainedContextMenuShadow"
        x: menuSurface.x - menuRoot.shadowBaseLeft - menuRoot.shadowExtendLeft
        y: menuSurface.y - menuRoot.shadowBaseTop - menuRoot.shadowExtendTop
        width: menuSurface.width
            + menuRoot.shadowBaseLeft + menuRoot.shadowBaseRight
            + menuRoot.shadowExtendLeft + menuRoot.shadowExtendRight
        height: menuSurface.height
            + menuRoot.shadowBaseTop + menuRoot.shadowBaseBottom
            + menuRoot.shadowExtendTop + menuRoot.shadowExtendBottom
        visible: menuRoot.visible && menuRoot.shadowEnabled
        color: menuRoot.shadowColor
        blur: menuRoot.shadowBlur
        radius: menuSurface.radius
        offset: Qt.vector2d(0.0, 0.0)
        cached: true
        enabled: false
        z: 1
    }

    // Palette values are generation-scoped Widget Theme projections. The QML
    // defaults below are only fail-safe mirrors of accepted Default Dark pixels.
    Rectangle {
        id: menuSurface
        objectName: "retainedContextMenuSurface"
        z: 2
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
        color: menuRoot.surfaceColor
        radius: 10.0
        border.color: menuRoot.borderColor
        border.width: 3.0

        Column {
            id: menuColumn
            x: 6.0
            y: 8.0
            width: parent.width - 12.0

            Repeater {
                id: menuRepeater
                model: menuRoot.contextMenuModel
                    ? menuRoot.contextMenuModel.entries
                    : []

                delegate: Item {
                    id: menuRow
                    required property var modelData
                    required property int index
                    width: menuColumn.width
                    height: modelData.kind === "separator" ? 7.0 : 38.0

                    function dismissSubmenuIfPointerLeftPath() {
                        if (menuRoot.activeSubmenuIndex !== menuRow.index)
                            return
                        // One event-turn defer lets a single pointer move transfer hover
                        // ownership between the parent row and its overlapping submenu.
                        // This is event-driven grace, not a timer/polling lifetime owner.
                        Qt.callLater(function() {
                            if (menuRoot.activeSubmenuIndex === menuRow.index
                                    && !rowHover.hovered
                                    && !submenuCorridorHover.hovered
                                    && !submenuSurfaceHover.hovered)
                                menuRoot.activeSubmenuIndex = -1
                        })
                    }

                    Rectangle {
                        anchors.centerIn: parent
                        width: parent.width - 24.0
                        height: 1.0
                        color: menuRoot.separatorColor
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
                        color: rowHover.hovered ? menuRoot.selectedSurfaceColor : "transparent"
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
                            border.color: menuRoot.indicatorBorderColor
                            visible: menuRow.modelData.kind === "toggle"
                                || menuRow.modelData.kind === "choice"

                            Rectangle {
                                anchors.centerIn: parent
                                width: 10.0
                                height: 10.0
                                radius: 5.0
                                color: menuRoot.indicatorFillColor
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
                            color: menuRoot.textColor
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
                            color: menuRoot.arrowColor
                            font.pixelSize: 16
                            visible: menuRow.modelData.kind === "submenu"
                        }

                        HoverHandler {
                            id: rowHover
                            enabled: menuRow.modelData.enabled
                            onHoveredChanged: {
                                if (hovered) {
                                    if (menuRow.modelData.kind === "submenu")
                                        menuRoot.activeSubmenuIndex = menuRow.index
                                    else if (menuRoot.activeSubmenuIndex !== -1)
                                        menuRoot.activeSubmenuIndex = -1
                                    return
                                }
                                if (menuRow.modelData.kind === "submenu")
                                    menuRow.dismissSubmenuIfPointerLeftPath()
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

                    // Narrow transparent ownership bridge between the parent row
                    // and its submenu. It is event-driven pointer geometry, not a
                    // timer: the submenu stays open only while the cursor is on the
                    // parent, this short crossing corridor, or the submenu itself.
                    Item {
                        id: submenuPointerCorridor
                        readonly property real overlap: 5.0
                        visible: menuRow.modelData.kind === "submenu"
                            && menuRoot.activeSubmenuIndex === menuRow.index
                        x: submenuSurface.x >= 0.0
                            ? rowSurface.x + rowSurface.width - overlap
                            : submenuSurface.x + submenuSurface.width - overlap
                        width: submenuSurface.x >= 0.0
                            ? Math.max(0.0, submenuSurface.x - x + overlap)
                            : Math.max(0.0, rowSurface.x - x + overlap)
                        y: Math.min(rowSurface.y, submenuSurface.y)
                        height: Math.max(
                            rowSurface.y + rowSurface.height,
                            submenuSurface.y + submenuSurface.height
                        ) - y
                        z: 19

                        HoverHandler {
                            id: submenuCorridorHover
                            enabled: submenuPointerCorridor.visible
                            onHoveredChanged: {
                                if (!hovered)
                                    menuRow.dismissSubmenuIfPointerLeftPath()
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
                        color: menuRoot.submenuSurfaceColor
                        radius: 8.0
                        border.color: menuRoot.submenuBorderColor
                        border.width: 3.0
                        visible: menuRow.modelData.kind === "submenu"
                            && menuRoot.activeSubmenuIndex === menuRow.index
                        z: 20

                        HoverHandler {
                            id: submenuSurfaceHover
                            enabled: submenuSurface.visible
                            onHoveredChanged: {
                                if (!hovered)
                                    menuRow.dismissSubmenuIfPointerLeftPath()
                            }
                        }

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
                                        ? menuRoot.submenuSelectedSurfaceColor
                                        : (modelData.checked ? menuRoot.submenuCheckedSurfaceColor : "transparent")
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
                                        border.color: menuRoot.submenuIndicatorBorderColor

                                        Rectangle {
                                            anchors.centerIn: parent
                                            width: 9.0
                                            height: 9.0
                                            radius: 4.5
                                            color: menuRoot.submenuIndicatorFillColor
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
                                            ? menuRoot.submenuCheckedTextColor
                                            : menuRoot.submenuTextColor
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
            if (!visible) {
                menuRoot.activeSubmenuIndex = -1
                dismissScrim.enabled = false
            } else {
                // Defer arming past the opening event's delivery so the press
                // that opened the menu cannot immediately dismiss it.
                dismissScrim.enabled = false
                Qt.callLater(function() {
                    if (menuRoot.contextMenuModel && menuRoot.contextMenuModel.menuVisible)
                        dismissScrim.enabled = true
                })
            }
        }
    }
}
