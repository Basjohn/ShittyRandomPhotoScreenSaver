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

    // The optional two-axis content-reflow affordance is an *inside-corner*
    // bridge between the two admitted blue side strips. It is not external
    // chrome: the visible diagonal sits in the small corner wedge that the
    // side strips intentionally leave free. Availability is still resolved
    // only from retained edit geometry (peer frames + local edit chrome).
    // There is no polling/collision timer; bindings re-evaluate only when the
    // selected/edit geometry actually changes.
    function rectanglesOverlap(ax, ay, aw, ah, bx, by, bw, bh) {
        return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by
    }

    function contentCornerLocalRect(frame, corner) {
        const size = 20.0
        const leftSide = String(corner).endsWith("left")
        const topSide = String(corner).startsWith("top_")
        return {
            x: leftSide ? 0.0 : Math.max(0.0, frame.width - size),
            y: topSide ? 0.0 : Math.max(0.0, frame.height - size),
            width: size,
            height: size
        }
    }

    function contentCornerHitRect(frame, corner) {
        const local = contentCornerLocalRect(frame, corner)
        return {
            x: frame.x + local.x,
            y: frame.y + local.y,
            width: local.width,
            height: local.height
        }
    }

    function contentCornerAvailable(frame, corner) {
        // The side strips themselves need 20 px of corner breathing room. Tiny
        // frames therefore do not admit this secondary gesture at all.
        if (frame.width < 40.0 || frame.height < 40.0)
            return false

        const candidate = contentCornerHitRect(frame, corner)
        if (candidate.x < 0 || candidate.y < 0
                || candidate.x + candidate.width > customLayoutOverlay.width
                || candidate.y + candidate.height > customLayoutOverlay.height)
            return false

        // If another widget actually occupies this inside-corner wedge, suppress
        // the affordance. Only the selected widget instantiates these checks, so
        // this remains edit-event/geometry-driven rather than an idle scanner.
        const peerMargin = 8.0
        for (let i = 0; i < editFrameRepeater.count; ++i) {
            const peer = editFrameRepeater.itemAt(i)
            if (!peer || peer === frame)
                continue
            if (rectanglesOverlap(
                        candidate.x, candidate.y, candidate.width, candidate.height,
                        peer.x - peerMargin, peer.y - peerMargin,
                        peer.width + peerMargin * 2.0,
                        peer.height + peerMargin * 2.0))
                return false
        }
        return true
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
            height: 3
            color: "#aa5ea8ff"
        }
    }

    Repeater {
        id: editFrameRepeater
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
            required property bool sizeResetCapable
            required property bool contentRotationCapable
            required property bool selectedForChildEdit
            required property var presentationItem
            required property real resizeScale
            required property bool canTransferLeft
            required property bool canTransferRight
            required property var contentExtentAxes

            // Content-extent side edges for ordinary list/feed widgets, derived
            // from the family's declared axes. Empty for the viewport-capable
            // Visualizer (its edges come from the branch above) and for uniform
            // widgets. Horizontal -> left/right, vertical -> top/bottom.
            readonly property var contentExtentEdges: {
                if (editFrame.viewportResizeCapable)
                    return []
                var axes = editFrame.contentExtentAxes || []
                var edges = []
                if (axes.indexOf("horizontal") >= 0) {
                    edges.push("left")
                    edges.push("right")
                }
                if (axes.indexOf("vertical") >= 0) {
                    edges.push("top")
                    edges.push("bottom")
                }
                return edges
            }
            readonly property bool twoAxisContentExtentCapable: {
                if (editFrame.viewportResizeCapable)
                    return false
                var axes = editFrame.contentExtentAxes || []
                return axes.indexOf("horizontal") >= 0
                    && axes.indexOf("vertical") >= 0
            }

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
                // One consistent edit-chrome close slot: proper top-right,
                // independent of family header/refresh layout. Keep it above
                // widget content so an underlying refresh/click target can never
                // receive the same press.
                x: Math.max(1.0, editFrame.width - width - 10.0)
                y: Math.max(1.0, Math.min(10.0, editFrame.height - height - 1.0))
                z: 80
                antialiasing: true
                color: customLayoutOverlay.closeButtonColor
                border.width: 1
                border.color: customLayoutOverlay.closeButtonBorderColor

                // Crisp, perfectly-centred X drawn from two rotated bars. The
                // "×" glyph sits high in its font metrics and reads off-centre in
                // a small circle, which is what looked deformed before.
                Item {
                    anchors.centerIn: parent
                    width: closeControl.width * 0.484
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
                    // Explicitly consume the full pointer sequence. Some widgets
                    // have live refresh/action targets beneath this top-right
                    // edit-chrome slot; close must never click through to them.
                    propagateComposedEvents: false
                    onPressed: function(mouse) { mouse.accepted = true }
                    onClicked: function(mouse) {
                        mouse.accepted = true
                        customLayoutOverlay.sessionModel.closeItem(editFrame.index)
                    }
                }
            }

            Rectangle {
                id: rotateContentControl
                objectName: "customLayoutRotateContent-" + editFrame.widgetId
                visible: editFrame.contentRotationCapable
                width: 22
                height: 22
                radius: width / 2
                // Keep the turn action in the lower-right edit-chrome slot,
                // inset from the viewport edge/corner resize handles so the
                // two gestures never compete for the same pointer region.
                x: Math.max(1.0, editFrame.width - width - 10.0)
                y: Math.max(1.0, editFrame.height - height - 10.0)
                z: 40
                antialiasing: true
                color: customLayoutOverlay.closeButtonColor
                border.width: 1
                border.color: customLayoutOverlay.closeButtonBorderColor

                Text {
                    anchors.centerIn: parent
                    text: "↻"
                    color: customLayoutOverlay.closeButtonGlyphColor
                    font.pixelSize: 15
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: customLayoutOverlay.sessionModel.rotateContent(editFrame.index)
                }
            }

            Rectangle {
                id: restoreSizeControl
                objectName: "customLayoutRestoreSize-" + editFrame.widgetId
                visible: editFrame.sizeResetCapable
                width: 22
                height: 22
                radius: width / 2
                x: 10
                y: Math.max(1.0, editFrame.height - height - 10.0)
                z: 40
                antialiasing: true
                color: customLayoutOverlay.closeButtonColor
                border.width: 1
                border.color: customLayoutOverlay.closeButtonBorderColor

                // Restore-size glyph. Keep this a real glyph, not hand-drawn
                // chrome, and deliberately distinct from the widget refresh ↺.
                Text {
                    anchors.centerIn: parent
                    text: "↶"
                    color: customLayoutOverlay.closeButtonGlyphColor
                    font.pixelSize: 15
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: customLayoutOverlay.sessionModel.restoreSize(editFrame.index)
                }
            }

            MouseArea {
                id: moveArea
                anchors.fill: parent
                // Keep the move zone clear of the top-right close control so its
                // full circle stays clickable at every size.
                anchors.topMargin: Math.max(32.0, closeControl.y + closeControl.height + 2.0)
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                property real pressOffsetX: 0
                property real pressOffsetY: 0

                onPressed: function(mouse) {
                    customLayoutOverlay.sessionModel.selectItem(editFrame.index)
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
                    customLayoutOverlay.sessionModel.selectItem(editFrame.index)
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
                    z: 50
                    width: 14
                    height: 14
                    radius: 3
                    x: leftSide ? -width / 2 : editFrame.width - width / 2
                    y: topSide ? -height / 2 : editFrame.height - height / 2
                    // Visualizer corners are a distinct two-axis viewport-extent
                    // gesture; use a deeper blue than the one-axis side strips so
                    // the edit affordance communicates the semantic difference.
                    color: editFrame.viewportResizeCapable ? "#e73b7fbe" : "#fff4f4f4"
                    border.width: 1
                    border.color: editFrame.viewportResizeCapable ? "#ff0b2a46" : "#ff222222"

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: parent.leftSide === parent.topSide
                                     ? Qt.SizeFDiagCursor
                                     : Qt.SizeBDiagCursor

                        function overlayPoint(mouse) {
                            return mapToItem(customLayoutOverlay, mouse.x, mouse.y)
                        }

                        onPressed: function(mouse) {
                            customLayoutOverlay.sessionModel.selectItem(editFrame.index)
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

            // One-axis logical edge handles. Visualizer edges change viewport
            // extent; admitted ordinary edges change content_extent. Existing
            // square corners/wheel keep their established uniform-scale meaning;
            // the selected-parent diagonal affordance below is the distinct
            // ordinary two-axis content-reflow gesture. QML emits semantic ids
            // and Python owns all geometry/aspect math.
            Repeater {
                model: editFrame.viewportResizeCapable
                       ? ["left", "right", "top", "bottom"]
                       : editFrame.contentExtentEdges

                delegate: Rectangle {
                    required property string modelData
                    property string edge: modelData
                    property bool horizontalEdge: edge === "left" || edge === "right"
                    // Inset the strips so they never sit on top of the corner
                    // handles or the close control.
                    property int edgeInset: 20
                    property int edgeThickness: 10

                    objectName: "customLayoutViewportEdge-" + editFrame.widgetId + "-" + edge
                    z: 20
                    // Visualizer viewport edges keep the bright blue; ordinary
                    // content-extent side edges use a modestly darker blue so the
                    // two semantics read differently in edit mode.
                    color: editFrame.viewportResizeCapable ? "#c85ec8ff" : "#c83a78c8"
                    border.width: 1
                    border.color: editFrame.viewportResizeCapable ? "#ff10324b" : "#ff0a2038"
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
                            customLayoutOverlay.sessionModel.selectItem(editFrame.index)
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

            // Focused editable-child chrome. Only the globally selected parent
            // loads this layer, and only families that expose descriptor-backed
            // retained targets through OverlayWidget.customEditableChildRoles
            // produce handles. Drawn child corners are deliberately smaller than
            // outer handles while each keeps a larger invisible hit box. QML
            // observes target geometry; Python owns normalized factors/persistence.
            Loader {
                id: childRoleLoader
                anchors.fill: parent
                active: editFrame.selectedForChildEdit
                        && editFrame.presentationItem !== null
                        && editFrame.presentationItem.customEditableChildRoles.length > 0
                z: 60

                sourceComponent: Component {
                    Item {
                        id: childRoleLayer
                        anchors.fill: parent
                        opacity: 0.0

                        NumberAnimation on opacity {
                            from: 0.0
                            to: 1.0
                            duration: 110
                            easing.type: Easing.OutCubic
                            running: true
                        }

                        function overlapsEditRect(candidate) {
                            if (!candidate || !childRoleRepeater)
                                return false
                            const handleMargin = 8.0
                            for (let i = 0; i < childRoleRepeater.count; ++i) {
                                const roleFrame = childRoleRepeater.itemAt(i)
                                if (!roleFrame || !roleFrame.visible)
                                    continue
                                if (customLayoutOverlay.rectanglesOverlap(
                                            candidate.x, candidate.y,
                                            candidate.width, candidate.height,
                                            roleFrame.x - handleMargin,
                                            roleFrame.y - handleMargin,
                                            roleFrame.width + handleMargin * 2.0,
                                            roleFrame.height + handleMargin * 2.0))
                                    return true
                            }
                            return false
                        }

                        Repeater {
                            id: childRoleRepeater
                            model: editFrame.presentationItem !== null
                                ? editFrame.presentationItem.customEditableChildRoles
                                : []

                            delegate: Item {
                                id: childRoleFrame
                                required property var modelData
                                readonly property string roleId: String(modelData.roleId || "")
                                readonly property var targetItem: modelData.target || null
                                // Optional retained family layout object that
                                // publishes one family-wide logical minimum.
                                // Keep the object reference stable in the role
                                // list so drag-time size changes update these two
                                // bindings without rebuilding the Repeater model.
                                readonly property var requirementTarget:
                                    modelData.requirementTarget || null
                                readonly property real requiredContentWidth:
                                    requirementTarget !== null
                                        ? Number(requirementTarget.requiredContentWidth || 0.0)
                                        : 0.0
                                readonly property real requiredContentHeight:
                                    requirementTarget !== null
                                        ? Number(requirementTarget.requiredContentHeight || 0.0)
                                        : 0.0
                                readonly property bool targetReady: targetItem !== null
                                    && targetItem.visible
                                    && targetItem.width > 1.0
                                    && targetItem.height > 1.0
                                // Explicit dependencies keep mapToItem bindings
                                // fresh through ordinary QML reflow and outer
                                // uniform transforms without polling.
                                readonly property real mappingDependency: targetReady
                                    ? targetItem.x + targetItem.y + targetItem.width
                                        + targetItem.height + editFrame.width + editFrame.height
                                    : 0.0
                                readonly property point mappedTopLeft: {
                                    const dependency = mappingDependency
                                    return targetReady
                                        ? targetItem.mapToItem(editFrame, 0.0, 0.0)
                                        : Qt.point(0.0, 0.0)
                                }
                                readonly property point mappedBottomRight: {
                                    const dependency = mappingDependency
                                    return targetReady
                                        ? targetItem.mapToItem(
                                            editFrame, targetItem.width, targetItem.height
                                        )
                                        : Qt.point(0.0, 0.0)
                                }

                                objectName: "customLayoutChildRole-"
                                            + editFrame.widgetId + "-" + roleId
                                visible: targetReady && roleId.length > 0
                                x: Math.min(mappedTopLeft.x, mappedBottomRight.x)
                                y: Math.min(mappedTopLeft.y, mappedBottomRight.y)
                                width: Math.abs(mappedBottomRight.x - mappedTopLeft.x)
                                height: Math.abs(mappedBottomRight.y - mappedTopLeft.y)

                                Rectangle {
                                    anchors.fill: parent
                                    color: "transparent"
                                    border.width: 1
                                    border.color: "#a85f9fd7"
                                    radius: 2
                                }

                                Repeater {
                                    model: customLayoutOverlay.sessionModel
                                        ? customLayoutOverlay.sessionModel.childResizeHandles(
                                            editFrame.index, childRoleFrame.roleId
                                        )
                                        : []

                                    delegate: Item {
                                        required property string modelData
                                        property string corner: modelData
                                        property bool leftSide: corner.endsWith("left")
                                        property bool topSide: corner.startsWith("top_")
                                        width: 16
                                        height: 16
                                        x: leftSide ? -width / 2.0 : childRoleFrame.width - width / 2.0
                                        y: topSide ? -height / 2.0 : childRoleFrame.height - height / 2.0

                                        Rectangle {
                                            anchors.centerIn: parent
                                            width: 8
                                            height: 8
                                            radius: 2
                                            color: "#e078b7e8"
                                            border.width: 1
                                            border.color: "#ff14344d"
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: parent.leftSide === parent.topSide
                                                ? Qt.SizeFDiagCursor
                                                : Qt.SizeBDiagCursor

                                            function overlayPoint(mouse) {
                                                return mapToItem(
                                                    customLayoutOverlay, mouse.x, mouse.y
                                                )
                                            }

                                            onPressed: function(mouse) {
                                                mouse.accepted = true
                                                const point = overlayPoint(mouse)
                                                customLayoutOverlay.sessionModel.beginChildResize(
                                                    editFrame.index,
                                                    childRoleFrame.roleId,
                                                    parent.corner,
                                                    point.x,
                                                    point.y,
                                                    childRoleFrame.width,
                                                    childRoleFrame.height
                                                )
                                            }
                                            onPositionChanged: function(mouse) {
                                                if (!pressed)
                                                    return
                                                const point = overlayPoint(mouse)
                                                customLayoutOverlay.sessionModel.resizeChild(
                                                    editFrame.index,
                                                    childRoleFrame.roleId,
                                                    parent.corner,
                                                    point.x,
                                                    point.y,
                                                    false
                                                )
                                            }
                                            onReleased: function(mouse) {
                                                const point = overlayPoint(mouse)
                                                customLayoutOverlay.sessionModel.resizeChild(
                                                    editFrame.index,
                                                    childRoleFrame.roleId,
                                                    parent.corner,
                                                    point.x,
                                                    point.y,
                                                    true
                                                )
                                                // Let retained family bindings settle the final
                                                // child size first, then admit growth once through
                                                // the existing Python content_extent owner. This is
                                                // one event per completed gesture, never a timer or
                                                // drag-cadence geometry feedback loop.
                                                Qt.callLater(function() {
                                                    if (!customLayoutOverlay.sessionModel)
                                                        return
                                                    customLayoutOverlay.sessionModel.ensureChildContentExtent(
                                                        editFrame.index,
                                                        childRoleFrame.requiredContentWidth,
                                                        childRoleFrame.requiredContentHeight
                                                    )
                                                })
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Optional two-axis ordinary content reflow. This is deliberately a
            // different affordance from the white square corners: square/wheel
            // retain uniform whole-widget scale, while these lighter-blue
            // diagonals adjust logical content width + height together. The line
            // bridges the two blue side-strip endpoints *inside* the selected
            // card; it is not external edit chrome. Only the globally selected
            // parent loads the layer, which is also the selection primitive
            // future editable-child handles will reuse.
            Loader {
                id: contentCornerLoader
                anchors.fill: parent
                active: editFrame.selectedForChildEdit
                        && editFrame.resizable
                        && editFrame.twoAxisContentExtentCapable
                z: 30

                sourceComponent: Component {
                    Item {
                        id: contentCornerLayer
                        anchors.fill: parent
                        opacity: 0.0

                        NumberAnimation on opacity {
                            from: 0.0
                            to: 1.0
                            duration: 110
                            easing.type: Easing.OutCubic
                            running: true
                        }

                        function localChromeClear(corner) {
                            const candidate = customLayoutOverlay.contentCornerLocalRect(
                                editFrame, corner
                            )
                            const controls = [
                                closeControl,
                                restoreSizeControl,
                                rotateContentControl,
                                transferLeftControl,
                                transferRightControl
                            ]
                            for (let i = 0; i < controls.length; ++i) {
                                const control = controls[i]
                                if (!control || !control.visible)
                                    continue
                                if (customLayoutOverlay.rectanglesOverlap(
                                            candidate.x, candidate.y,
                                            candidate.width, candidate.height,
                                            control.x, control.y,
                                            control.width, control.height))
                                    return false
                            }
                            const childLayer = childRoleLoader.item
                            if (childLayer && childLayer.overlapsEditRect(candidate))
                                return false
                            return true
                        }

                        Repeater {
                            model: ["top_left", "top_right", "bottom_left", "bottom_right"]

                            delegate: Item {
                                required property string modelData
                                property string corner: modelData
                                property bool leftSide: corner.endsWith("left")
                                property bool topSide: corner.startsWith("top_")
                                property bool available:
                                    customLayoutOverlay.contentCornerAvailable(editFrame, corner)
                                    && contentCornerLayer.localChromeClear(corner)

                                objectName: "customLayoutContentCorner-"
                                            + editFrame.widgetId + "-" + corner
                                width: 20
                                height: 20
                                x: leftSide ? 0.0 : Math.max(0.0, editFrame.width - width)
                                y: topSide ? 0.0 : Math.max(0.0, editFrame.height - height)
                                opacity: available ? 1.0 : 0.0
                                enabled: available

                                Rectangle {
                                    anchors.centerIn: parent
                                    width: 18
                                    height: 3
                                    radius: 1.5
                                    antialiasing: true
                                    color: "#dc6aa8e8"
                                    rotation: parent.leftSide === parent.topSide ? 45 : -45
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: parent.leftSide === parent.topSide
                                                 ? Qt.SizeFDiagCursor
                                                 : Qt.SizeBDiagCursor

                                    function overlayPoint(mouse) {
                                        return mapToItem(customLayoutOverlay, mouse.x, mouse.y)
                                    }

                                    onPressed: function(mouse) {
                                        customLayoutOverlay.sessionModel.selectItem(editFrame.index)
                                        const point = overlayPoint(mouse)
                                        customLayoutOverlay.sessionModel.beginResize(
                                            editFrame.index,
                                            "content_" + parent.corner,
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
                                            "content_" + parent.corner,
                                            point.x,
                                            point.y,
                                            false
                                        )
                                    }
                                    onReleased: function(mouse) {
                                        const point = overlayPoint(mouse)
                                        customLayoutOverlay.sessionModel.resizeItem(
                                            editFrame.index,
                                            "content_" + parent.corner,
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
        }
    }
}
