import QtQuick

// One retained, display-local edit layer. Python's CustomLayoutSession remains
// the only working geometry/enabled/removal authority; this item renders model
// roles and emits semantic move/X requests back through that model.
Item {
    id: customLayoutOverlay
    objectName: "customLayoutOverlay"

    property bool editActive: false
    property var sessionModel: null
    property int gridStep: 24
    property int gridGutter: 24
    property var verticalGuides: []
    property var horizontalGuides: []

    visible: editActive
    enabled: editActive
    clip: false

    function isCenterGuide(kind) {
        return kind === "display_center" || kind === "peer_center"
    }

    Repeater {
        model: customLayoutOverlay.editActive
               ? Math.floor(customLayoutOverlay.width / customLayoutOverlay.gridStep) + 1
               : 0
        delegate: Rectangle {
            required property int index
            x: index * customLayoutOverlay.gridStep
            width: 1
            height: customLayoutOverlay.height
            color: index % 4 === 0 ? "#3affffff" : "#1cffffff"
        }
    }

    Repeater {
        model: customLayoutOverlay.editActive
               ? Math.floor(customLayoutOverlay.height / customLayoutOverlay.gridStep) + 1
               : 0
        delegate: Rectangle {
            required property int index
            y: index * customLayoutOverlay.gridStep
            width: customLayoutOverlay.width
            height: 1
            color: index % 4 === 0 ? "#3affffff" : "#1cffffff"
        }
    }

    Rectangle {
        objectName: "customLayoutSafeGutter"
        anchors.fill: parent
        anchors.margins: customLayoutOverlay.gridGutter
        color: "transparent"
        border.width: 1
        border.color: "#74b46eff"
    }

    Repeater {
        model: customLayoutOverlay.verticalGuides
        delegate: Rectangle {
            required property var modelData
            objectName: "customLayoutVerticalGuide"
            property string guideKind: String(modelData.kind)
            x: Number(modelData.position)
            width: 3
            height: customLayoutOverlay.height
            color: customLayoutOverlay.isCenterGuide(guideKind) ? "#ffff3b30" : "#ebb46eff"
        }
    }

    Repeater {
        model: customLayoutOverlay.horizontalGuides
        delegate: Rectangle {
            required property var modelData
            objectName: "customLayoutHorizontalGuide"
            property string guideKind: String(modelData.kind)
            y: Number(modelData.position)
            width: customLayoutOverlay.width
            height: 3
            color: customLayoutOverlay.isCenterGuide(guideKind) ? "#ffff3b30" : "#ebb46eff"
        }
    }

    Repeater {
        model: customLayoutOverlay.sessionModel
        delegate: Item {
            id: editFrame
            required property int index
            required property string widgetId
            required property real geometryX
            required property real geometryY
            required property real geometryWidth
            required property real geometryHeight
            required property bool duplicate
            required property bool resizable

            objectName: "customLayoutEditFrame-" + widgetId
            x: geometryX
            y: geometryY
            width: geometryWidth
            height: geometryHeight

            Rectangle {
                anchors.fill: parent
                color: "transparent"
                border.width: 2
                border.color: "#fff4f4f4"
            }

            Rectangle {
                id: closeControl
                objectName: "customLayoutClose-" + editFrame.widgetId
                width: 24
                height: 24
                radius: 12
                x: editFrame.width - width - 4
                y: 4
                color: "#e6a51d1d"
                border.width: 1
                border.color: "white"

                Text {
                    anchors.centerIn: parent
                    text: "×"
                    color: "white"
                    font.pixelSize: 18
                    font.bold: true
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: customLayoutOverlay.sessionModel.closeItem(editFrame.index)
                }
            }

            MouseArea {
                id: moveArea
                anchors.fill: parent
                anchors.topMargin: 28
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                property real pressOffsetX: 0
                property real pressOffsetY: 0

                onPressed: function(mouse) {
                    const point = moveArea.mapToItem(customLayoutOverlay, mouse.x, mouse.y)
                    pressOffsetX = point.x - editFrame.x
                    pressOffsetY = point.y - editFrame.y
                }
                onPositionChanged: function(mouse) {
                    if (!pressed)
                        return
                    const point = moveArea.mapToItem(customLayoutOverlay, mouse.x, mouse.y)
                    customLayoutOverlay.sessionModel.moveItem(
                        editFrame.index,
                        point.x - pressOffsetX,
                        point.y - pressOffsetY,
                        point.x,
                        point.y
                    )
                }
                onWheel: function(wheel) {
                    if (!editFrame.resizable)
                        return
                    wheel.accepted = customLayoutOverlay.sessionModel.resizeWheel(
                        editFrame.index,
                        wheel.angleDelta.y
                    )
                }
            }

            Repeater {
                model: editFrame.resizable
                       ? ["top_left", "top_right", "bottom_left", "bottom_right"]
                       : []

                delegate: Rectangle {
                    required property string modelData
                    property string corner: modelData
                    property bool leftSide: corner.endsWith("left")
                    property bool topSide: corner.startsWith("top")

                    objectName: "customLayoutResize-" + editFrame.widgetId + "-" + corner
                    width: 14
                    height: 14
                    radius: 3
                    x: leftSide ? -width / 2 : editFrame.width - width / 2
                    y: topSide ? -height / 2 : editFrame.height - height / 2
                    color: "#fff4f4f4"
                    border.width: 1
                    border.color: "#ff222222"

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: parent.leftSide === parent.topSide
                                     ? Qt.SizeFDiagCursor
                                     : Qt.SizeBDiagCursor

                        function overlayPoint(mouse) {
                            return mapToItem(customLayoutOverlay, mouse.x, mouse.y)
                        }

                        onPressed: function(mouse) {
                            const point = overlayPoint(mouse)
                            customLayoutOverlay.sessionModel.beginResize(
                                editFrame.index,
                                parent.corner,
                                point.x,
                                point.y
                            )
                        }
                        onPositionChanged: function(mouse) {
                            if (!pressed)
                                return
                            const point = overlayPoint(mouse)
                            customLayoutOverlay.sessionModel.resizeItem(
                                editFrame.index,
                                parent.corner,
                                point.x,
                                point.y,
                                false
                            )
                        }
                        onReleased: function(mouse) {
                            const point = overlayPoint(mouse)
                            customLayoutOverlay.sessionModel.resizeItem(
                                editFrame.index,
                                parent.corner,
                                point.x,
                                point.y,
                                true
                            )
                        }
                    }
                }
            }
        }
    }
}
