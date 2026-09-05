import QtQuick

// One retained, display-local edit layer. Python's CustomLayoutSession remains
// the only working geometry/enabled/removal authority; this item renders model
// roles and emits semantic move/X requests back through that model.
Item {
    id: customLayoutOverlay
    objectName: "customLayoutOverlay"

    property bool editActive: false
    property var sessionModel: null
    property var verticalGuides: []
    property var horizontalGuides: []

    // Theme-coloured edit-mode close (X) control. Default Dark = black circle,
    // white X, tiny white outline. Phase 1c binds these to the resolved Widget
    // Theme palette; the defaults here are the Default Dark appearance.
    property color closeButtonColor: "#000000"
    property color closeButtonBorderColor: "#ffffff"
    property color closeButtonGlyphColor: "#ffffff"
    // Discrete Visualizer display-hop controls reuse the resolved menu/theme
    // palette. They are intentionally separate from drag transfer so native
    // QQuickWindow pointer grabs are not the only way to change ownership.
    property color transferButtonColor: "#f21b1d24"
    property color transferButtonHoverColor: "#4f77b9e8"
    property color transferButtonBorderColor: "#d8f3ff"
    property color transferButtonGlyphColor: "#d8f3ff"

    visible: editActive
    enabled: editActive
    clip: false

    Repeater {
        model: customLayoutOverlay.verticalGuides
        delegate: Rectangle {
            required property var modelData
            objectName: "customLayoutVerticalGuide"
            property string guideKind: String(modelData.kind)
            x: Number(modelData.position)
            width: 2
            height: customLayoutOverlay.height
            color: "#aa5ea8ff"
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
            height: 2
            color: "#aa5ea8ff"
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
            required property bool viewportResizeCapable
            required property real resizeScale
            required property bool canTransferLeft
            required property bool canTransferRight

            // Gmail/Reddit establish the shared branded-header row at an authored
            // 32 px centreline (14 px card inset + 18 px half-height).  The edit
            // overlay lives outside the widget's retained transform, so project
            // the session-owned absolute CUSTOM scale here to keep the X on that
            // same row for every widget, including families with no refresh glyph.
            readonly property real editChromeHeaderCenterY: 32.0 * Math.max(0.05, resizeScale)

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
                width: 22
                height: 22
                radius: width / 2
                // Keep the established right-side slot (immediately left of a
                // refresh accessory where present), but align its centre to the
                // shared header/logo/refresh row at the current CUSTOM scale.
                x: editFrame.width - width - 34
                y: Math.max(
                    1.0,
                    Math.min(
                        Math.max(1.0, editFrame.height - height - 1.0),
                        editFrame.editChromeHeaderCenterY - height / 2.0
                    )
                )
                antialiasing: true
                color: customLayoutOverlay.closeButtonColor
                border.width: 1
                border.color: customLayoutOverlay.closeButtonBorderColor

                // Crisp, perfectly-centred X drawn from two rotated bars. The
                // "×" glyph sits high in its font metrics and reads off-centre in
                // a small circle, which is what looked deformed before.
                Item {
                    anchors.centerIn: parent
                    width: closeControl.width * 0.44
                    height: width
                    Rectangle {
                        anchors.centerIn: parent
                        width: parent.width
                        height: 2
                        radius: 1
                        antialiasing: true
                        color: customLayoutOverlay.closeButtonGlyphColor
                        rotation: 45
                    }
                    Rectangle {
                        anchors.centerIn: parent
                        width: parent.width
                        height: 2
                        radius: 1
                        antialiasing: true
                        color: customLayoutOverlay.closeButtonGlyphColor
                        rotation: -45
                    }
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
                // Keep the move zone clear of the scale-aware header-row close
                // control so its full circle stays clickable at every size.
                anchors.topMargin: Math.max(32.0, closeControl.y + closeControl.height + 2.0)
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                property real pressOffsetX: 0
                property real pressOffsetY: 0

                onPressed: function(mouse) {
                    customLayoutOverlay.sessionModel.finishMove()
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
                onReleased: customLayoutOverlay.sessionModel.finishMove()
                onCanceled: customLayoutOverlay.sessionModel.finishMove()
                onWheel: function(wheel) {
                    if (!editFrame.resizable)
                        return
                    wheel.accepted = customLayoutOverlay.sessionModel.resizeWheel(
                        editFrame.index,
                        wheel.angleDelta.y
                    )
                }
            }

            Rectangle {
                id: transferLeftControl
                objectName: "customLayoutTransferLeft-" + editFrame.widgetId
                visible: editFrame.widgetId === "spotify_visualizer" && editFrame.canTransferLeft
                width: 28
                height: 28
                radius: width / 2
                x: 8
                y: Math.max(8, (editFrame.height - height) / 2)
                z: 30
                antialiasing: true
                color: transferLeftMouse.containsMouse
                    ? customLayoutOverlay.transferButtonHoverColor
                    : customLayoutOverlay.transferButtonColor
                border.width: 1
                border.color: customLayoutOverlay.transferButtonBorderColor

                Item {
                    anchors.centerIn: parent
                    width: 10
                    height: 14
                    Rectangle {
                        width: 9
                        height: 2
                        radius: 1
                        color: customLayoutOverlay.transferButtonGlyphColor
                        antialiasing: true
                        rotation: -45
                        x: -1
                        y: 3
                    }
                    Rectangle {
                        width: 9
                        height: 2
                        radius: 1
                        color: customLayoutOverlay.transferButtonGlyphColor
                        antialiasing: true
                        rotation: 45
                        x: -1
                        y: 9
                    }
                }

                MouseArea {
                    id: transferLeftMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: customLayoutOverlay.sessionModel.transferItem(editFrame.index, "left")
                }
            }

            Rectangle {
                id: transferRightControl
                objectName: "customLayoutTransferRight-" + editFrame.widgetId
                visible: editFrame.widgetId === "spotify_visualizer" && editFrame.canTransferRight
                width: 28
                height: 28
                radius: width / 2
                x: Math.max(8, editFrame.width - width - 8)
                y: Math.max(8, (editFrame.height - height) / 2)
                z: 30
                antialiasing: true
                color: transferRightMouse.containsMouse
                    ? customLayoutOverlay.transferButtonHoverColor
                    : customLayoutOverlay.transferButtonColor
                border.width: 1
                border.color: customLayoutOverlay.transferButtonBorderColor

                Item {
                    anchors.centerIn: parent
                    width: 10
                    height: 14
                    Rectangle {
                        width: 9
                        height: 2
                        radius: 1
                        color: customLayoutOverlay.transferButtonGlyphColor
                        antialiasing: true
                        rotation: 45
                        x: 2
                        y: 3
                    }
                    Rectangle {
                        width: 9
                        height: 2
                        radius: 1
                        color: customLayoutOverlay.transferButtonGlyphColor
                        antialiasing: true
                        rotation: -45
                        x: 2
                        y: 9
                    }
                }

                MouseArea {
                    id: transferRightMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: customLayoutOverlay.sessionModel.transferItem(editFrame.index, "right")
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

            // Viewport-extent edge handles. Distinct from the uniform corner
            // handles above: left/right change viewport width only, top/bottom
            // change viewport height only, at constant uniform scale. Only the
            // viewport-resize-capable visualizer shows these; QML emits the
            // semantic edge id and Python owns all geometry/aspect math.
            Repeater {
                model: editFrame.viewportResizeCapable
                       ? ["left", "right", "top", "bottom"]
                       : []

                delegate: Rectangle {
                    required property string modelData
                    property string edge: modelData
                    property bool horizontalEdge: edge === "left" || edge === "right"
                    // Inset the strips so they never sit on top of the corner
                    // handles or the close control.
                    property int edgeInset: 20
                    property int edgeThickness: 10

                    objectName: "customLayoutViewportEdge-" + editFrame.widgetId + "-" + edge
                    color: "#c85ec8ff"
                    border.width: 1
                    border.color: "#ff10324b"
                    radius: 2

                    width: horizontalEdge
                           ? edgeThickness
                           : Math.max(0, editFrame.width - (2 * edgeInset))
                    height: horizontalEdge
                            ? Math.max(0, editFrame.height - (2 * edgeInset))
                            : edgeThickness
                    x: edge === "left"
                       ? -edgeThickness / 2
                       : (edge === "right"
                          ? editFrame.width - edgeThickness / 2
                          : edgeInset)
                    y: edge === "top"
                       ? -edgeThickness / 2
                       : (edge === "bottom"
                          ? editFrame.height - edgeThickness / 2
                          : edgeInset)

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: parent.horizontalEdge
                                     ? Qt.SizeHorCursor
                                     : Qt.SizeVerCursor

                        function overlayPoint(mouse) {
                            return mapToItem(customLayoutOverlay, mouse.x, mouse.y)
                        }

                        onPressed: function(mouse) {
                            const point = overlayPoint(mouse)
                            customLayoutOverlay.sessionModel.beginResize(
                                editFrame.index,
                                parent.edge,
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
                                parent.edge,
                                point.x,
                                point.y,
                                false
                            )
                        }
                        onReleased: function(mouse) {
                            const point = overlayPoint(mouse)
                            customLayoutOverlay.sessionModel.resizeItem(
                                editFrame.index,
                                parent.edge,
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
