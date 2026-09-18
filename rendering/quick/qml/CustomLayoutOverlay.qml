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

    // Empty-background double-click is an explicit Edit command: commit through
    // the same Python Save authority as Enter/context-menu Save. This surface is
    // behind every edit frame, so clicks on a widget/handle never trigger it.
    // Native runtime double-click semantics remain blocked for the whole CUSTOM
    // transaction, preventing the slideshow transition/next-image action.
    MouseArea {
        id: customLayoutBackgroundSaveArea
        objectName: "customLayoutBackgroundSaveArea"
        anchors.fill: parent
        z: 0
        acceptedButtons: Qt.LeftButton
        propagateComposedEvents: false
        onDoubleClicked: function(mouse) {
            mouse.accepted = true
            if (customLayoutOverlay.sessionModel)
                customLayoutOverlay.sessionModel.requestSave()
        }
    }

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
            // Qt may project a Python None role as QML `undefined` rather than
            // `null` (Visualizer intentionally has no editable-child presentation).
            // Keep one lifecycle-safe gate so parent edit gestures never dereference
            // an absent child presentation before their own gesture can begin.
            readonly property bool hasPresentationItem:
                presentationItem !== null && presentationItem !== undefined
            required property int childStateRevision
            required property bool childCollisionEnabled
            required property real resizeScale
            required property bool canTransferLeft
            required property bool canTransferRight
            required property var contentExtentAxes

            // Session-local edit chrome preference. A newly selected parent always
            // starts with its parent glyph controls visible; the attached wedge
            // can hide/show them without persisting anything into CUSTOM state.
            property bool parentGlyphControlsHidden: false
            property real parentGlyphControlsOpacity: parentGlyphControlsHidden ? 0.0 : 1.0
            readonly property real controlsWedgeLeftSpace: Math.max(0.0, editFrame.x)
            readonly property real controlsWedgeRightSpace: Math.max(
                0.0, customLayoutOverlay.width - (editFrame.x + editFrame.width)
            )
            readonly property real controlsWedgeTopSpace: Math.max(0.0, editFrame.y)
            readonly property real controlsWedgeBottomSpace: Math.max(
                0.0, customLayoutOverlay.height - (editFrame.y + editFrame.height)
            )
            // Attach the session-local control tab to the side with the most free
            // display space. Left/right tabs are vertical (including their label);
            // top/bottom tabs are horizontal. This keeps the tab feeling like an
            // extension of the selected edit frame rather than a floating button.
            readonly property string controlsWedgeSide: {
                const horizontalMax = Math.max(controlsWedgeLeftSpace, controlsWedgeRightSpace)
                const verticalMax = Math.max(controlsWedgeTopSpace, controlsWedgeBottomSpace)
                if (horizontalMax >= verticalMax)
                    return controlsWedgeRightSpace >= controlsWedgeLeftSpace ? "right" : "left"
                return controlsWedgeBottomSpace >= controlsWedgeTopSpace ? "bottom" : "top"
            }
            readonly property bool controlsWedgeVertical:
                controlsWedgeSide === "left" || controlsWedgeSide === "right"
            onSelectedForChildEditChanged: {
                if (selectedForChildEdit)
                    parentGlyphControlsHidden = false
            }
            Behavior on parentGlyphControlsOpacity {
                NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
            }

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

            function syncChildRequirementNow() {
                // While the selected-parent child layer exists it is the most
                // accurate edit-only observer: it can combine the family's
                // retained authored/reflow requirement with the *actual mapped*
                // occupied rectangles of freely placed children. This prevents a
                // saved placement in an already-expanded parent from being eaten
                // by a later parent resize without forcing every family to
                // duplicate placement-bound math. Outside child editing, retain
                // the old family requirement fallback and no geometry scan exists.
                if (childRoleLoader.active && childRoleLoader.item !== null) {
                    childRoleLoader.item.syncRequirementNow()
                    return
                }
                if (!customLayoutOverlay.sessionModel
                        || !editFrame.hasPresentationItem)
                    return
                const requirement = editFrame.presentationItem.customEditableChildRequirementTarget
                if (requirement === null || requirement === undefined) {
                    customLayoutOverlay.sessionModel.clearChildContentExtent(editFrame.index)
                    return
                }
                const requiredWidth = Number(requirement.requiredContentWidth || 0.0)
                const requiredHeight = Number(requirement.requiredContentHeight || 0.0)
                if (requiredWidth <= 0.0 || requiredHeight <= 0.0) {
                    customLayoutOverlay.sessionModel.clearChildContentExtent(editFrame.index)
                    return
                }
                customLayoutOverlay.sessionModel.ensureChildContentExtent(
                    editFrame.index, requiredWidth, requiredHeight
                )
            }

            objectName: "customLayoutEditFrame-" + widgetId
            z: 10
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
                opacity: editFrame.parentGlyphControlsOpacity
                enabled: !editFrame.parentGlyphControlsHidden && opacity > 0.05
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
                opacity: editFrame.parentGlyphControlsOpacity
                enabled: !editFrame.parentGlyphControlsHidden && opacity > 0.05
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
                opacity: editFrame.parentGlyphControlsOpacity
                enabled: !editFrame.parentGlyphControlsHidden && opacity > 0.05
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

            Rectangle {
                id: parentGlyphControlWedge
                objectName: "customLayoutParentGlyphToggle-" + editFrame.widgetId
                visible: editFrame.selectedForChildEdit
                width: editFrame.controlsWedgeVertical ? 22 : 104
                height: editFrame.controlsWedgeVertical ? 104 : 22
                radius: 6
                x: editFrame.controlsWedgeSide === "right"
                    ? editFrame.width - 3.0
                    : (editFrame.controlsWedgeSide === "left"
                        ? -width + 3.0
                        : Math.max(2.0, (editFrame.width - width) / 2.0))
                y: editFrame.controlsWedgeSide === "bottom"
                    ? editFrame.height - 3.0
                    : (editFrame.controlsWedgeSide === "top"
                        ? -height + 3.0
                        : Math.max(2.0, (editFrame.height - height) / 2.0))
                z: 90
                antialiasing: true
                color: parentGlyphControlWedgeMouse.containsMouse
                    ? customLayoutOverlay.transferButtonHoverColor
                    : customLayoutOverlay.transferButtonColor
                border.width: 1
                border.color: customLayoutOverlay.transferButtonBorderColor

                // The deliberate overlap makes the tab read as part of the
                // selected edit frame rather than as a floating widget button.
                Rectangle {
                    width: editFrame.controlsWedgeVertical
                        ? 5 : Math.max(2.0, parent.width - 4.0)
                    height: editFrame.controlsWedgeVertical
                        ? Math.max(2.0, parent.height - 4.0) : 5
                    x: editFrame.controlsWedgeSide === "right"
                        ? -2.0
                        : (editFrame.controlsWedgeSide === "left"
                            ? parent.width - 3.0 : 2.0)
                    y: editFrame.controlsWedgeSide === "bottom"
                        ? -2.0
                        : (editFrame.controlsWedgeSide === "top"
                            ? parent.height - 3.0 : 2.0)
                    radius: 2
                    color: parent.color
                    border.width: 0
                }

                Text {
                    anchors.centerIn: parent
                    text: editFrame.parentGlyphControlsHidden
                        ? "SHOW CONTROLS" : "HIDE CONTROLS"
                    color: customLayoutOverlay.transferButtonGlyphColor
                    font.pixelSize: 9
                    font.bold: true
                    rotation: editFrame.controlsWedgeSide === "right"
                        ? 90
                        : (editFrame.controlsWedgeSide === "left" ? -90 : 0)
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                MouseArea {
                    id: parentGlyphControlWedgeMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    propagateComposedEvents: false
                    onPressed: function(mouse) { mouse.accepted = true }
                    onClicked: function(mouse) {
                        mouse.accepted = true
                        editFrame.parentGlyphControlsHidden =
                            !editFrame.parentGlyphControlsHidden
                    }
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
                    editFrame.syncChildRequirementNow()
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
                opacity: editFrame.parentGlyphControlsOpacity
                enabled: !editFrame.parentGlyphControlsHidden && opacity > 0.05
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
                opacity: editFrame.parentGlyphControlsOpacity
                enabled: !editFrame.parentGlyphControlsHidden && opacity > 0.05
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
                            // Close the observer/callLater race before any parent
                            // resize gesture takes ownership. The retained family
                            // is the current truth for child occupancy, so publish
                            // that floor synchronously at the gesture boundary.
                            editFrame.syncChildRequirementNow()
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
                            editFrame.syncChildRequirementNow()
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
                        && editFrame.hasPresentationItem
                        && ((editFrame.presentationItem.customEditableChildRoles || []).length > 0
                            || editFrame.presentationItem.customEditableChildRequirementTarget !== null)
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

                        property var childVerticalGuides: []
                        property var childHorizontalGuides: []

                        Repeater {
                            model: childRoleLayer.childVerticalGuides
                            delegate: Rectangle {
                                required property var modelData
                                readonly property bool semantic:
                                    String(modelData.kind || "").indexOf("semantic-margin-") === 0
                                objectName: "customLayoutChildVerticalGuide"
                                x: Number(modelData.position)
                                width: semantic ? 3 : 2
                                height: childRoleLayer.height
                                color: semantic ? "#dc8bc8ff" : "#b45ea8ff"
                                z: 1
                            }
                        }

                        Repeater {
                            model: childRoleLayer.childHorizontalGuides
                            delegate: Rectangle {
                                required property var modelData
                                readonly property bool semantic:
                                    String(modelData.kind || "").indexOf("semantic-margin-") === 0
                                objectName: "customLayoutChildHorizontalGuide"
                                y: Number(modelData.position)
                                width: childRoleLayer.width
                                height: semantic ? 3 : 2
                                color: semantic ? "#dc8bc8ff" : "#b45ea8ff"
                                z: 1
                            }
                        }

                        // One family-wide retained requirement, observed only
                        // while this parent is selected for child editing. Changes
                        // are coalesced to the next QML turn so one retained reflow
                        // cannot publish width + height as two outer grows. This is
                        // event-driven edit work, never a timer/poller. Gesture
                        // handlers also queue this after each accepted sample so
                        // parent growth follows the pointer instead of landing as a
                        // delayed release-time jump.
                        readonly property var requirementTarget:
                            editFrame.hasPresentationItem
                                ? editFrame.presentationItem.customEditableChildRequirementTarget
                                : null
                        readonly property real requiredContentWidth:
                            requirementTarget !== null
                                ? Number(requirementTarget.requiredContentWidth || 0.0)
                                : 0.0
                        readonly property real requiredContentHeight:
                            requirementTarget !== null
                                ? Number(requirementTarget.requiredContentHeight || 0.0)
                                : 0.0
                        property bool requirementSyncQueued: false

                        function aggregateRequiredContentSize() {
                            // Family targets remain the authority for authored
                            // reflow/size requirements. Placement is different:
                            // because roles may move anywhere inside the real
                            // parent, the selected Edit layer can cheaply derive
                            // the exact occupied right/bottom edge from the retained
                            // targets it already owns. No scene-wide scan, timer or
                            // normal-runtime observer is introduced.
                            let width = Math.max(0.0, requiredContentWidth)
                            let height = Math.max(0.0, requiredContentHeight)
                            const scale = Math.max(1.0e-6, editFrame.resizeScale)
                            if (childRoleRepeater) {
                                for (let i = 0; i < childRoleRepeater.count; ++i) {
                                    const frame = childRoleRepeater.itemAt(i)
                                    if (!frame || !frame.visible)
                                        continue
                                    width = Math.max(
                                        width,
                                        Math.max(frame.occupiedWidth,
                                                 frame.occupiedX + frame.occupiedWidth) / scale
                                    )
                                    height = Math.max(
                                        height,
                                        Math.max(frame.occupiedHeight,
                                                 frame.occupiedY + frame.occupiedHeight) / scale
                                    )
                                }
                            }
                            return Qt.size(width, height)
                        }

                        function syncRequirementNow() {
                            if (!customLayoutOverlay.sessionModel)
                                return false
                            // A queued callback from an old selection/loader must
                            // never resurrect that item's transient floor after the
                            // layer has been retired.
                            if (!editFrame.selectedForChildEdit
                                    || !childRoleLoader.active
                                    || childRoleLoader.item !== childRoleLayer)
                                return false
                            const aggregate = aggregateRequiredContentSize()
                            if (aggregate.width <= 0.0 || aggregate.height <= 0.0)
                                return customLayoutOverlay.sessionModel.clearChildContentExtent(
                                    editFrame.index
                                )
                            return customLayoutOverlay.sessionModel.ensureChildContentExtent(
                                editFrame.index,
                                aggregate.width,
                                aggregate.height
                            )
                        }

                        function scheduleRequirementSync() {
                            if (requirementSyncQueued
                                    || !customLayoutOverlay.sessionModel)
                                return
                            requirementSyncQueued = true
                            const layer = childRoleLayer
                            Qt.callLater(function() {
                                // QML object lifetime may end between scheduling and
                                // the next turn (selection switch, slot load,
                                // Settings-driven role rebuild). A guarded reference
                                // makes that cancellation boring instead of logging a
                                // stale-object JS error or republishing old state.
                                if (!layer)
                                    return
                                layer.requirementSyncQueued = false
                                layer.syncRequirementNow()
                            })
                        }

                        function ensureImmediateChildOverflow(frame, candidateX, candidateY,
                                                              candidateWidth, candidateHeight) {
                            // Pointer-owned provisional containment. The retained
                            // family remains the exact logical requirement authority,
                            // but a child can cross the current right/bottom edge in
                            // the same event that changes its geometry. Grow the
                            // parent's existing logical box from that *actual painted*
                            // candidate before the next scene turn so the user never
                            // sees a release-time catch-up jump. This is edit-only and
                            // event-driven; the retained requirement immediately
                            // reconciles the conservative floor afterward.
                            if (!customLayoutOverlay.sessionModel
                                    || editFrame.resizeScale <= 0.0)
                                return false
                            const occupied = occupiedRectAt(
                                frame, candidateX, candidateY,
                                candidateWidth, candidateHeight
                            )
                            let candidateRight = occupied.x + occupied.width
                            let candidateBottom = occupied.y + occupied.height

                            // Resizing one authored-rail child can synchronously move
                            // other on-rail roles. Include those predicted secondary
                            // edges in the same pointer-owned growth request instead
                            // of waiting for the retained scene to reflow and then
                            // catching up one turn later. Movement passes zero size
                            // deltas, so this adds no special placement behavior.
                            if (frame.resizeReflowEnabled) {
                                const axes = frame.resizeReflowAxes || []
                                const roleIds = frame.resizeReflowRoleIds || []
                                const shiftX = axes.indexOf("horizontal") >= 0
                                    ? candidateWidth - frame.width : 0.0
                                const shiftY = axes.indexOf("vertical") >= 0
                                    ? candidateHeight - frame.height : 0.0
                                if (Math.abs(shiftX) > 0.001 || Math.abs(shiftY) > 0.001) {
                                    for (let i = 0; i < childRoleRepeater.count; ++i) {
                                        const peer = childRoleRepeater.itemAt(i)
                                        if (!peer || peer === frame || !peer.visible
                                                || !peer.resizeReflowEnabled
                                                || roleIds.indexOf(peer.roleId) < 0)
                                            continue
                                        candidateRight = Math.max(
                                            candidateRight,
                                            peer.occupiedX + shiftX + peer.occupiedWidth
                                        )
                                        candidateBottom = Math.max(
                                            candidateBottom,
                                            peer.occupiedY + shiftY + peer.occupiedHeight
                                        )
                                    }
                                }
                            }
                            if (candidateRight <= editFrame.width + 0.25
                                    && candidateBottom <= editFrame.height + 0.25)
                                return false
                            const aggregate = aggregateRequiredContentSize()
                            const requiredPhysicalWidth = Math.max(
                                aggregate.width * editFrame.resizeScale,
                                Math.max(occupied.width, candidateRight)
                            )
                            const requiredPhysicalHeight = Math.max(
                                aggregate.height * editFrame.resizeScale,
                                Math.max(occupied.height, candidateBottom)
                            )
                            return customLayoutOverlay.sessionModel.ensureChildContentExtent(
                                editFrame.index,
                                requiredPhysicalWidth / editFrame.resizeScale,
                                requiredPhysicalHeight / editFrame.resizeScale
                            )
                        }

                        onRequirementTargetChanged: scheduleRequirementSync()
                        onRequiredContentWidthChanged: scheduleRequirementSync()
                        onRequiredContentHeightChanged: scheduleRequirementSync()
                        Component.onCompleted: scheduleRequirementSync()
                        Component.onDestruction: {
                            // Selection retirement is owned in Python by stable
                            // session-item identity. This row-based hook is only the
                            // selected-parent fallback for Settings/role availability
                            // changes where the row is still authoritative. Never use
                            // a stale delegate row after selection/model teardown.
                            if (customLayoutOverlay.sessionModel
                                    && editFrame.selectedForChildEdit)
                                customLayoutOverlay.sessionModel.clearChildContentExtent(
                                    editFrame.index
                                )
                        }

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

                        function itemRectInFrame(item) {
                            if (!item || !item.visible || item.width <= 0.0 || item.height <= 0.0)
                                return null
                            const topLeft = item.mapToItem(editFrame, 0.0, 0.0)
                            const bottomRight = item.mapToItem(editFrame, item.width, item.height)
                            return {
                                "x": Math.min(topLeft.x, bottomRight.x),
                                "y": Math.min(topLeft.y, bottomRight.y),
                                "width": Math.abs(bottomRight.x - topLeft.x),
                                "height": Math.abs(bottomRight.y - topLeft.y)
                            }
                        }

                        function rangesOverlap(a0, a1, b0, b1) {
                            return a0 < b1 && a1 > b0
                        }

                        function overlapArea(a, b) {
                            if (!a || !b)
                                return 0.0
                            const width = Math.max(
                                0.0,
                                Math.min(a.x + a.width, b.x + b.width)
                                    - Math.max(a.x, b.x)
                            )
                            const height = Math.max(
                                0.0,
                                Math.min(a.y + a.height, b.y + b.height)
                                    - Math.max(a.y, b.y)
                            )
                            return width * height
                        }

                        function occupiedRectAt(frame, candidateX, candidateY,
                                                candidateWidth, candidateHeight) {
                            // Families may expose a slightly larger occupied target
                            // than the visible resize target (Artwork shelf/chrome).
                            // Preserve those authored insets while the child moves
                            // or resizes so collision/clipping is based on what is
                            // actually painted, not just the blue edit rectangle.
                            const leftExtra = frame.occupiedX - frame.x
                            const topExtra = frame.occupiedY - frame.y
                            const horizontalExtra = frame.occupiedWidth - frame.width
                            const verticalExtra = frame.occupiedHeight - frame.height
                            return {
                                "x": candidateX + leftExtra,
                                "y": candidateY + topExtra,
                                "width": Math.max(1.0, candidateWidth + horizontalExtra),
                                "height": Math.max(1.0, candidateHeight + verticalExtra)
                            }
                        }

                        function obstacleRects(frame, forResize, resizeAxis) {
                            const result = []
                            // Placement treats every other declared role as a hard
                            // peer. Resize does too unless the family explicitly names
                            // a peer that is synchronously reflowed by this role's size
                            // change. That narrow exception preserves authored rails
                            // without making "resize" a blanket permission to overlap.
                            // Families may make the reflow list dynamic (for example,
                            // empty it after a role has been freely moved off its
                            // authored rail). All of this exists only in selected Edit.
                            const reflowAxes = frame.resizeReflowAxes || []
                            const reflowPeers = forResize
                                    && frame.resizeReflowEnabled
                                    && reflowAxes.indexOf(String(resizeAxis || "")) >= 0
                                ? (frame.resizeReflowRoleIds || []) : []
                            if (editFrame.childCollisionEnabled) {
                                for (let i = 0; i < childRoleRepeater.count; ++i) {
                                    const peer = childRoleRepeater.itemAt(i)
                                    if (!peer || peer === frame || !peer.visible)
                                        continue
                                    if (forResize
                                            && reflowPeers.indexOf(peer.roleId) >= 0
                                            && peer.resizeReflowEnabled)
                                        continue
                                    result.push({
                                        "x": peer.occupiedX,
                                        "y": peer.occupiedY,
                                        "width": peer.occupiedWidth,
                                        "height": peer.occupiedHeight,
                                        "passThrough": true,
                                        "roleId": peer.roleId
                                    })
                                }
                            }
                            const presentation = editFrame.presentationItem
                            const obstacles = editFrame.hasPresentationItem
                                ? (presentation.customEditableChildObstacles || []) : []
                            for (let j = 0; j < obstacles.length; ++j) {
                                const spec = obstacles[j]
                                const target = spec && spec.target ? spec.target : spec
                                const exceptRoles = spec && spec.exceptRoles
                                    ? spec.exceptRoles : []
                                const hardResize = spec && spec.target
                                    ? spec.hardResize !== false : true
                                if (exceptRoles.indexOf(frame.roleId) >= 0
                                        || (forResize && !hardResize))
                                    continue
                                const obstacleRect = itemRectInFrame(target)
                                if (obstacleRect) {
                                    obstacleRect.passThrough = false
                                    result.push(obstacleRect)
                                }
                            }
                            return result
                        }

                        function snapCoordinate(value, candidates, threshold) {
                            let best = value
                            let bestDistance = threshold + 0.001
                            for (let i = 0; i < candidates.length; ++i) {
                                const distance = Math.abs(value - candidates[i])
                                if (distance <= threshold && distance < bestDistance) {
                                    best = candidates[i]
                                    bestDistance = distance
                                }
                            }
                            return best
                        }

                        function childGuideTargets(frame, horizontal) {
                            const result = []
                            const parentSize = horizontal ? editFrame.width : editFrame.height

                            // Semantic header corners get their family-authored safe
                            // inset as a distinct, stronger target. Ordinary roles keep
                            // the gentle generic parent/sibling hints below.
                            if (frame.semanticCornerAnchorCapable) {
                                const semanticInset = horizontal
                                    ? frame.semanticCornerInsetX : frame.semanticCornerInsetY
                                if (semanticInset >= 0.0 && parentSize > semanticInset * 2.0 + 1.0) {
                                    result.push({
                                        "position": semanticInset,
                                        "kind": "semantic-margin-start"
                                    })
                                    result.push({
                                        "position": parentSize - semanticInset,
                                        "kind": "semantic-margin-end"
                                    })
                                }
                            }

                            const inset = Math.max(8.0, Math.min(18.0, 10.0 * editFrame.resizeScale))
                            result.push({"position": 0.0, "kind": "parent-edge"})
                            result.push({"position": parentSize / 2.0, "kind": "parent-center"})
                            result.push({"position": parentSize, "kind": "parent-edge"})
                            if (parentSize > inset * 2.5) {
                                result.push({"position": inset, "kind": "parent-margin"})
                                result.push({"position": parentSize - inset, "kind": "parent-margin"})
                            }
                            for (let i = 0; i < childRoleRepeater.count; ++i) {
                                const peer = childRoleRepeater.itemAt(i)
                                if (!peer || peer === frame || !peer.visible)
                                    continue
                                const start = horizontal ? peer.x : peer.y
                                const size = horizontal ? peer.width : peer.height
                                result.push({"position": start, "kind": "sibling-edge"})
                                result.push({"position": start + size / 2.0, "kind": "sibling-center"})
                                result.push({"position": start + size, "kind": "sibling-edge"})
                            }
                            return result
                        }

                        function publishChildGuide(horizontal, target, kind) {
                            const payload = target === null ? [] : [{
                                "position": Number(target),
                                "kind": String(kind || "child")
                            }]
                            if (horizontal)
                                childHorizontalGuides = payload
                            else
                                childVerticalGuides = payload
                        }

                        function clearChildGuides(frame) {
                            childVerticalGuides = []
                            childHorizontalGuides = []
                            if (frame) {
                                frame.hasSnapX = false
                                frame.hasSnapY = false
                            }
                        }

                        function semanticSnapKind(kind) {
                            return String(kind || "").indexOf("semantic-margin-") === 0
                        }

                        function snapChildAxis(frame, desired, horizontal) {
                            const size = horizontal ? frame.width : frame.height
                            const active = horizontal ? frame.hasSnapX : frame.hasSnapY
                            const activeTarget = horizontal ? frame.snapXTarget : frame.snapYTarget
                            const activeFeature = horizontal ? frame.snapXFeature : frame.snapYFeature
                            const activeKind = horizontal ? frame.snapXKind : frame.snapYKind
                            const releaseDistance = semanticSnapKind(activeKind) ? 28.0 : 11.0
                            if (active
                                    && Math.abs(desired + activeFeature - activeTarget)
                                        <= releaseDistance) {
                                publishChildGuide(!horizontal, activeTarget, activeKind)
                                return activeTarget - activeFeature
                            }

                            if (horizontal)
                                frame.hasSnapX = false
                            else
                                frame.hasSnapY = false

                            const targets = childGuideTargets(frame, horizontal)
                            let bestDistance = Number.POSITIVE_INFINITY
                            let bestTarget = 0.0
                            let bestFeature = 0.0
                            let bestKind = ""
                            let found = false

                            // Headers deliberately prefer their semantic margin rail
                            // anywhere inside the larger acquire zone. Only the matching
                            // outside edge participates: left/top -> feature 0,
                            // right/bottom -> feature size.
                            for (let t = 0; t < targets.length; ++t) {
                                const kind = String(targets[t].kind || "")
                                if (!semanticSnapKind(kind))
                                    continue
                                const feature = kind.endsWith("start") ? 0.0 : size
                                const target = Number(targets[t].position)
                                const distance = Math.abs(desired + feature - target)
                                if (distance <= 18.0 && distance < bestDistance) {
                                    bestDistance = distance
                                    bestTarget = target
                                    bestFeature = feature
                                    bestKind = kind
                                    found = true
                                }
                            }

                            if (!found) {
                                const features = [0.0, size / 2.0, size]
                                bestDistance = 6.001
                                for (let f = 0; f < features.length; ++f) {
                                    const feature = features[f]
                                    for (let t = 0; t < targets.length; ++t) {
                                        const kind = String(targets[t].kind || "child")
                                        if (semanticSnapKind(kind))
                                            continue
                                        const target = Number(targets[t].position)
                                        const distance = Math.abs(desired + feature - target)
                                        if (distance <= 6.0 && distance < bestDistance) {
                                            bestDistance = distance
                                            bestTarget = target
                                            bestFeature = feature
                                            bestKind = kind
                                            found = true
                                        }
                                    }
                                }
                            }

                            if (!found) {
                                publishChildGuide(!horizontal, null, "")
                                return desired
                            }
                            if (horizontal) {
                                frame.hasSnapX = true
                                frame.snapXTarget = bestTarget
                                frame.snapXFeature = bestFeature
                                frame.snapXKind = bestKind
                            } else {
                                frame.hasSnapY = true
                                frame.snapYTarget = bestTarget
                                frame.snapYFeature = bestFeature
                                frame.snapYKind = bestKind
                            }
                            publishChildGuide(!horizontal, bestTarget, bestKind)
                            return bestTarget - bestFeature
                        }

                        function semanticCornerFromSnaps(frame) {
                            if (!frame.semanticCornerAnchorCapable
                                    || !frame.hasSnapX || !frame.hasSnapY
                                    || !semanticSnapKind(frame.snapXKind)
                                    || !semanticSnapKind(frame.snapYKind))
                                return ""
                            const horizontal = frame.snapXKind.endsWith("start")
                                ? "left" : "right"
                            const vertical = frame.snapYKind.endsWith("start")
                                ? "top" : "bottom"
                            return vertical + "_" + horizontal
                        }

                        function validateChildGuides(frame, x, y) {
                            if (frame.hasSnapX
                                    && Math.abs(x + frame.snapXFeature - frame.snapXTarget) > 1.0) {
                                frame.hasSnapX = false
                                childVerticalGuides = []
                            }
                            if (frame.hasSnapY
                                    && Math.abs(y + frame.snapYFeature - frame.snapYTarget) > 1.0) {
                                frame.hasSnapY = false
                                childHorizontalGuides = []
                            }
                        }

                        function childMoveCandidateDeepensOverlap(
                                candidate, baseline, obstacles, ignoredObstacle) {
                            for (let i = 0; i < obstacles.length; ++i) {
                                const obstacle = obstacles[i]
                                if (obstacle === ignoredObstacle)
                                    continue
                                if (overlapArea(candidate, obstacle)
                                        > overlapArea(baseline, obstacle) + 0.01)
                                    return true
                            }
                            return false
                        }

                        function tryChildPeerPassX(
                                frame, current, candidate, obstacle, obstacles,
                                movingRight, minX, maxX) {
                            if (!obstacle.passThrough)
                                return null
                            // A small amount of deliberate pressure beyond the hard
                            // collision edge signals intent to cross another editable
                            // child. The peer itself never moves and fixed obstacles
                            // never participate. This keeps persistence single-role.
                            const resistance = 14.0
                            const penetration = movingRight
                                ? candidate.x + candidate.width - obstacle.x
                                : obstacle.x + obstacle.width - candidate.x
                            if (penetration < resistance)
                                return null
                            const leftExtra = frame.occupiedX - frame.x
                            const passX = movingRight
                                ? obstacle.x + obstacle.width - leftExtra
                                : obstacle.x - frame.occupiedWidth - leftExtra
                            if (passX < minX - 0.01 || passX > maxX + 0.01)
                                return null
                            const passCandidate = occupiedRectAt(
                                frame, passX, frame.y, frame.width, frame.height
                            )
                            if (overlapArea(passCandidate, obstacle) > 0.01
                                    || childMoveCandidateDeepensOverlap(
                                        passCandidate, current, obstacles, obstacle))
                                return null
                            return {"coordinate": passX, "rect": passCandidate}
                        }

                        function tryChildPeerPassY(
                                frame, current, candidate, obstacle, obstacles,
                                movingDown, minY, maxY, admittedX) {
                            if (!obstacle.passThrough)
                                return null
                            const resistance = 14.0
                            const penetration = movingDown
                                ? candidate.y + candidate.height - obstacle.y
                                : obstacle.y + obstacle.height - candidate.y
                            if (penetration < resistance)
                                return null
                            const topExtra = frame.occupiedY - frame.y
                            const passY = movingDown
                                ? obstacle.y + obstacle.height - topExtra
                                : obstacle.y - frame.occupiedHeight - topExtra
                            if (passY < minY - 0.01 || passY > maxY + 0.01)
                                return null
                            const passCandidate = occupiedRectAt(
                                frame, admittedX, passY, frame.width, frame.height
                            )
                            if (overlapArea(passCandidate, obstacle) > 0.01
                                    || childMoveCandidateDeepensOverlap(
                                        passCandidate, current, obstacles, obstacle))
                                return null
                            return {"coordinate": passY, "rect": passCandidate}
                        }

                        function admitChildMove(frame, desiredX, desiredY) {
                            // Placement uses the entire *real* parent. Padding is
                            // not a boundary. The role's occupied painted rectangle
                            // is clipped to the parent edge; edges/centre are merely
                            // mild magnetic hints.
                            const leftExtra = frame.occupiedX - frame.x
                            const topExtra = frame.occupiedY - frame.y
                            const minX = -leftExtra
                            const minY = -topExtra
                            const maxX = Math.max(
                                minX,
                                editFrame.width - leftExtra - frame.occupiedWidth
                            )
                            const maxY = Math.max(
                                minY,
                                editFrame.height - topExtra - frame.occupiedHeight
                            )
                            let x = Math.max(minX, Math.min(maxX, desiredX))
                            let y = Math.max(minY, Math.min(maxY, desiredY))
                            x = snapChildAxis(frame, x, true)
                            y = snapChildAxis(frame, y, false)

                            const obstacles = obstacleRects(frame, false, "")
                            const current = occupiedRectAt(
                                frame, frame.x, frame.y, frame.width, frame.height
                            )

                            // Sweep X first. This clamps at the peer boundary rather
                            // than teleporting back to the gesture origin. Existing
                            // overlaps are intentionally ignored so a user can drag
                            // an old/bad layout *out* of collision.
                            let candidate = occupiedRectAt(
                                frame, x, frame.y, frame.width, frame.height
                            )
                            for (let i = 0; i < obstacles.length; ++i) {
                                const obstacle = obstacles[i]
                                const currentOverlap = overlapArea(current, obstacle)
                                if (currentOverlap > 0.0) {
                                    // Corrupt/legacy layouts may enter Edit already
                                    // overlapping. Keep them escapable, but never let
                                    // a fresh pointer sample deepen that overlap.
                                    if (overlapArea(candidate, obstacle)
                                            > currentOverlap + 0.01) {
                                        x = frame.x
                                        candidate = occupiedRectAt(
                                            frame, x, frame.y, frame.width, frame.height
                                        )
                                    }
                                    continue
                                }
                                if (!rangesOverlap(
                                        candidate.y, candidate.y + candidate.height,
                                        obstacle.y, obstacle.y + obstacle.height))
                                    continue
                                if (candidate.x > current.x
                                        && current.x + current.width <= obstacle.x
                                        && candidate.x + candidate.width > obstacle.x) {
                                    const pass = tryChildPeerPassX(
                                        frame, current, candidate, obstacle, obstacles,
                                        true, minX, maxX
                                    )
                                    if (pass !== null) {
                                        // Rebase the rest of this pointer gesture onto
                                        // the admitted far side. Without this transient
                                        // bias the fixed press origin would request the
                                        // old side again on the very next sample.
                                        frame.movePassBiasX += pass.coordinate - x
                                        x = pass.coordinate
                                        candidate = pass.rect
                                    } else {
                                        x -= candidate.x + candidate.width - obstacle.x
                                        candidate = occupiedRectAt(
                                            frame, x, frame.y, frame.width, frame.height
                                        )
                                    }
                                } else if (candidate.x < current.x
                                           && current.x >= obstacle.x + obstacle.width
                                           && candidate.x < obstacle.x + obstacle.width) {
                                    const pass = tryChildPeerPassX(
                                        frame, current, candidate, obstacle, obstacles,
                                        false, minX, maxX
                                    )
                                    if (pass !== null) {
                                        // Rebase the rest of this pointer gesture onto
                                        // the admitted far side. Without this transient
                                        // bias the fixed press origin would request the
                                        // old side again on the very next sample.
                                        frame.movePassBiasX += pass.coordinate - x
                                        x = pass.coordinate
                                        candidate = pass.rect
                                    } else {
                                        x += obstacle.x + obstacle.width - candidate.x
                                        candidate = occupiedRectAt(
                                            frame, x, frame.y, frame.width, frame.height
                                        )
                                    }
                                }
                            }

                            // Collision resolution can push against a peer that
                            // sits flush with the parent edge. Re-apply the real
                            // parent clip before admitting the second axis, then
                            // reject only an X move that would deepen an existing
                            // overlap. This keeps impossible narrow gaps boring
                            // instead of letting a collision correction escape the
                            // card or teleport the role.
                            x = Math.max(minX, Math.min(maxX, x))
                            candidate = occupiedRectAt(
                                frame, x, frame.y, frame.width, frame.height
                            )
                            for (let verifyX = 0; verifyX < obstacles.length; ++verifyX) {
                                const obstacle = obstacles[verifyX]
                                if (overlapArea(candidate, obstacle)
                                        > overlapArea(current, obstacle) + 0.01) {
                                    x = frame.x
                                    candidate = occupiedRectAt(
                                        frame, x, frame.y, frame.width, frame.height
                                    )
                                    break
                                }
                            }

                            // Then sweep Y with admitted X so diagonal movement
                            // naturally slides along a peer rather than crossing it.
                            candidate = occupiedRectAt(
                                frame, x, y, frame.width, frame.height
                            )
                            for (let j = 0; j < obstacles.length; ++j) {
                                const obstacle = obstacles[j]
                                const currentAtX = occupiedRectAt(
                                    frame, x, frame.y, frame.width, frame.height
                                )
                                const currentOverlap = overlapArea(currentAtX, obstacle)
                                if (currentOverlap > 0.0) {
                                    if (overlapArea(candidate, obstacle)
                                            > currentOverlap + 0.01) {
                                        y = frame.y
                                        candidate = occupiedRectAt(
                                            frame, x, y, frame.width, frame.height
                                        )
                                    }
                                    continue
                                }
                                if (!rangesOverlap(
                                        candidate.x, candidate.x + candidate.width,
                                        obstacle.x, obstacle.x + obstacle.width))
                                    continue
                                if (candidate.y > currentAtX.y
                                        && currentAtX.y + currentAtX.height <= obstacle.y
                                        && candidate.y + candidate.height > obstacle.y) {
                                    const pass = tryChildPeerPassY(
                                        frame, currentAtX, candidate, obstacle, obstacles,
                                        true, minY, maxY, x
                                    )
                                    if (pass !== null) {
                                        frame.movePassBiasY += pass.coordinate - y
                                        y = pass.coordinate
                                        candidate = pass.rect
                                    } else {
                                        y -= candidate.y + candidate.height - obstacle.y
                                        candidate = occupiedRectAt(
                                            frame, x, y, frame.width, frame.height
                                        )
                                    }
                                } else if (candidate.y < currentAtX.y
                                           && currentAtX.y >= obstacle.y + obstacle.height
                                           && candidate.y < obstacle.y + obstacle.height) {
                                    const pass = tryChildPeerPassY(
                                        frame, currentAtX, candidate, obstacle, obstacles,
                                        false, minY, maxY, x
                                    )
                                    if (pass !== null) {
                                        frame.movePassBiasY += pass.coordinate - y
                                        y = pass.coordinate
                                        candidate = pass.rect
                                    } else {
                                        y += obstacle.y + obstacle.height - candidate.y
                                        candidate = occupiedRectAt(
                                            frame, x, y, frame.width, frame.height
                                        )
                                    }
                                }
                            }

                            y = Math.max(minY, Math.min(maxY, y))
                            candidate = occupiedRectAt(
                                frame, x, y, frame.width, frame.height
                            )
                            const admittedXBaseline = occupiedRectAt(
                                frame, x, frame.y, frame.width, frame.height
                            )
                            for (let verifyY = 0; verifyY < obstacles.length; ++verifyY) {
                                const obstacle = obstacles[verifyY]
                                if (overlapArea(candidate, obstacle)
                                        > overlapArea(admittedXBaseline, obstacle) + 0.01) {
                                    y = frame.y
                                    break
                                }
                            }
                            validateChildGuides(frame, x, y)
                            return Qt.point(x, y)
                        }

                        function clampIndirectReflowShift(frame, axis, desiredShift, obstacles) {
                            // A direct resize may intentionally move one or more
                            // on-rail peers instead of colliding with their *current*
                            // rectangles. That exemption must not allow those moving
                            // peers to be pushed into a manually placed peer or fixed
                            // painted obstacle. Predict the family-declared same-axis
                            // translation and clamp that translation at the first hard
                            // surface. This stays entirely inside the selected Edit
                            // layer; normal CUSTOM presentation gets no collision pass.
                            if (!frame.resizeReflowEnabled || Math.abs(desiredShift) <= 0.001)
                                return desiredShift
                            const axes = frame.resizeReflowAxes || []
                            if (axes.indexOf(axis) < 0)
                                return desiredShift
                            const reflowRoleIds = frame.resizeReflowRoleIds || []
                            if (reflowRoleIds.length === 0)
                                return desiredShift

                            let allowed = desiredShift
                            for (let i = 0; i < childRoleRepeater.count; ++i) {
                                const peer = childRoleRepeater.itemAt(i)
                                if (!peer || peer === frame || !peer.visible
                                        || !peer.resizeReflowEnabled
                                        || reflowRoleIds.indexOf(peer.roleId) < 0)
                                    continue
                                const current = {
                                    "x": peer.occupiedX,
                                    "y": peer.occupiedY,
                                    "width": peer.occupiedWidth,
                                    "height": peer.occupiedHeight
                                }
                                for (let j = 0; j < obstacles.length; ++j) {
                                    const obstacle = obstacles[j]
                                    const initialOverlap = overlapArea(current, obstacle)
                                    let candidate = {
                                        "x": current.x + (axis === "horizontal" ? allowed : 0.0),
                                        "y": current.y + (axis === "vertical" ? allowed : 0.0),
                                        "width": current.width,
                                        "height": current.height
                                    }
                                    if (initialOverlap > 0.0) {
                                        // Legacy/corrupt overlap remains escapable.
                                        // A reflowing sibling may move out of it, but
                                        // an upstream resize may not make it deeper.
                                        if (overlapArea(candidate, obstacle)
                                                > initialOverlap + 0.01)
                                            allowed = 0.0
                                        continue
                                    }
                                    if (axis === "horizontal") {
                                        if (!rangesOverlap(
                                                current.y, current.y + current.height,
                                                obstacle.y, obstacle.y + obstacle.height))
                                            continue
                                        if (allowed > 0.0
                                                && current.x + current.width <= obstacle.x) {
                                            allowed = Math.min(
                                                allowed,
                                                obstacle.x - (current.x + current.width)
                                            )
                                        } else if (allowed < 0.0
                                                   && current.x >= obstacle.x + obstacle.width) {
                                            allowed = Math.max(
                                                allowed,
                                                obstacle.x + obstacle.width - current.x
                                            )
                                        }
                                    } else {
                                        if (!rangesOverlap(
                                                current.x, current.x + current.width,
                                                obstacle.x, obstacle.x + obstacle.width))
                                            continue
                                        if (allowed > 0.0
                                                && current.y + current.height <= obstacle.y) {
                                            allowed = Math.min(
                                                allowed,
                                                obstacle.y - (current.y + current.height)
                                            )
                                        } else if (allowed < 0.0
                                                   && current.y >= obstacle.y + obstacle.height) {
                                            allowed = Math.max(
                                                allowed,
                                                obstacle.y + obstacle.height - current.y
                                            )
                                        }
                                    }
                                }
                            }
                            return allowed
                        }

                        function admitChildResize(frame, handle,
                                                  pressX, pressY,
                                                  startX, startY,
                                                  startWidth, startHeight,
                                                  pointerX, pointerY) {
                            const handleId = String(handle)
                            const leftSide = handleId.endsWith("left")
                            const topSide = handleId === "top" || handleId.startsWith("top_")
                            const horizontalOnly = handleId === "left" || handleId === "right"
                            const verticalOnly = handleId === "top" || handleId === "bottom"
                            const dx = verticalOnly ? 0.0 : pointerX - pressX
                            const dy = horizontalOnly ? 0.0 : pointerY - pressY
                            let x = leftSide ? startX + dx : startX
                            let y = topSide ? startY + dy : startY
                            let width = Math.max(1.0, leftSide ? startWidth - dx : startWidth + dx)
                            let height = Math.max(1.0, topSide ? startHeight - dy : startHeight + dy)

                            // Left/top may never escape the real parent. Right/bottom
                            // are deliberately allowed to extend it; the retained
                            // family requirement then grows the parent live.
                            let occupied = occupiedRectAt(frame, x, y, width, height)
                            if (leftSide && occupied.x < 0.0) {
                                const correction = -occupied.x
                                x += correction
                                width = Math.max(1.0, width - correction)
                            }
                            occupied = occupiedRectAt(frame, x, y, width, height)
                            if (topSide && occupied.y < 0.0) {
                                const correction = -occupied.y
                                y += correction
                                height = Math.max(1.0, height - correction)
                            }

                            const startOccupied = occupiedRectAt(
                                frame, startX, startY, startWidth, startHeight
                            )
                            // Reflow exemptions are axis-specific. A peer that is
                            // translated vertically by this source is still a hard
                            // obstacle to the source's horizontal edge, and vice
                            // versa. This closes a subtle diagonal-resize loophole.
                            const horizontalObstacles = obstacleRects(
                                frame, true, "horizontal"
                            )
                            const verticalObstacles = obstacleRects(
                                frame, true, "vertical"
                            )

                            // Clamp the actively dragged horizontal edge against
                            // peers/obstacles. Existing overlap is not made worse,
                            // but remains escapable by shrinking/moving away.
                            for (let i = 0; i < horizontalObstacles.length; ++i) {
                                const obstacle = horizontalObstacles[i]
                                // Horizontal admission must be independent of the
                                // simultaneously dragged vertical edge.  Compare
                                // against the start-Y/start-height slice only;
                                // otherwise a diagonal drag can invent a Y overlap
                                // and falsely clamp X before the vertical pass gets
                                // its own turn.
                                const horizontalCandidate = occupiedRectAt(
                                    frame, x, startY, width, startHeight
                                )
                                const initialOverlap = overlapArea(startOccupied, obstacle)
                                if (initialOverlap > 0.0) {
                                    if (overlapArea(horizontalCandidate, obstacle)
                                            > initialOverlap + 0.01) {
                                        x = startX
                                        width = startWidth
                                    }
                                    continue
                                }
                                if (!rangesOverlap(
                                        horizontalCandidate.y,
                                        horizontalCandidate.y + horizontalCandidate.height,
                                        obstacle.y, obstacle.y + obstacle.height))
                                    continue
                                if (!leftSide
                                        && startOccupied.x + startOccupied.width <= obstacle.x
                                        && horizontalCandidate.x + horizontalCandidate.width > obstacle.x) {
                                    width = Math.max(
                                        1.0,
                                        width - (horizontalCandidate.x
                                                 + horizontalCandidate.width - obstacle.x)
                                    )
                                } else if (leftSide
                                           && startOccupied.x >= obstacle.x + obstacle.width
                                           && horizontalCandidate.x < obstacle.x + obstacle.width) {
                                    const correction = obstacle.x + obstacle.width
                                        - horizontalCandidate.x
                                    x += correction
                                    width = Math.max(1.0, width - correction)
                                }
                            }

                            // A same-axis family reflow can move *other* on-rail
                            // roles even though their current rectangles were exempt
                            // above. Clamp that indirect translation against every
                            // non-reflow peer/fixed obstacle before admitting Y.
                            const admittedWidthDelta = clampIndirectReflowShift(
                                frame, "horizontal", width - startWidth, horizontalObstacles
                            )
                            if (Math.abs(admittedWidthDelta - (width - startWidth)) > 0.001) {
                                width = Math.max(1.0, startWidth + admittedWidthDelta)
                                if (leftSide)
                                    x = startX + startWidth - width
                            }

                            // Then clamp the vertical edge using the already-admitted
                            // horizontal geometry, preserving smooth diagonal slides.
                            for (let j = 0; j < verticalObstacles.length; ++j) {
                                const obstacle = verticalObstacles[j]
                                occupied = occupiedRectAt(frame, x, y, width, height)
                                const horizontalBaseline = occupiedRectAt(
                                    frame, x, startY, width, startHeight
                                )
                                const baselineOverlap = overlapArea(horizontalBaseline, obstacle)
                                if (baselineOverlap > 0.0) {
                                    if (overlapArea(occupied, obstacle)
                                            > baselineOverlap + 0.01) {
                                        y = startY
                                        height = startHeight
                                    }
                                    continue
                                }
                                if (!rangesOverlap(
                                        occupied.x, occupied.x + occupied.width,
                                        obstacle.x, obstacle.x + obstacle.width))
                                    continue
                                if (!topSide
                                        && startOccupied.y + startOccupied.height <= obstacle.y
                                        && occupied.y + occupied.height > obstacle.y) {
                                    height = Math.max(
                                        1.0,
                                        height - (occupied.y + occupied.height - obstacle.y)
                                    )
                                } else if (topSide
                                           && startOccupied.y >= obstacle.y + obstacle.height
                                           && occupied.y < obstacle.y + obstacle.height) {
                                    const correction = obstacle.y + obstacle.height - occupied.y
                                    y += correction
                                    height = Math.max(1.0, height - correction)
                                }
                            }

                            const admittedHeightDelta = clampIndirectReflowShift(
                                frame, "vertical", height - startHeight, verticalObstacles
                            )
                            if (Math.abs(admittedHeightDelta - (height - startHeight)) > 0.001) {
                                height = Math.max(1.0, startHeight + admittedHeightDelta)
                                if (topSide)
                                    y = startY + startHeight - height
                            }

                            return Qt.point(
                                pressX + (leftSide ? x - startX : width - startWidth),
                                pressY + (topSide ? y - startY : height - startHeight)
                            )
                        }

                        function resizeCandidateForPointer(frame, handle, gesture, pointer) {
                            const handleId = String(handle)
                            const leftSide = handleId.endsWith("left")
                            const topSide = handleId === "top" || handleId.startsWith("top_")
                            const horizontalOnly = handleId === "left" || handleId === "right"
                            const verticalOnly = handleId === "top" || handleId === "bottom"
                            const dx = verticalOnly ? 0.0 : pointer.x - gesture.pressX
                            const dy = horizontalOnly ? 0.0 : pointer.y - gesture.pressY
                            const x = leftSide ? gesture.startX + dx : gesture.startX
                            const y = topSide ? gesture.startY + dy : gesture.startY
                            const width = Math.max(
                                1.0,
                                leftSide ? gesture.startWidth - dx : gesture.startWidth + dx
                            )
                            const height = Math.max(
                                1.0,
                                topSide ? gesture.startHeight - dy : gesture.startHeight + dy
                            )
                            return {
                                "x": x,
                                "y": y,
                                "width": width,
                                "height": height,
                                "leftSide": leftSide,
                                "topSide": topSide,
                                "horizontalActive": !verticalOnly,
                                "verticalActive": !horizontalOnly
                            }
                        }

                        function throttleChildAutoGrowth(frame, handle, gesture, admittedPointer) {
                            // Auto-growth should feel deliberate rather than letting a
                            // tiny child drag explode the whole parent. Once a dragged
                            // right/bottom edge reaches the parent boundary, require
                            // another 12 px of pointer travel for each 6 px containment
                            // expansion. The child is clamped to the same admitted step,
                            // so it never visibly outruns the parent. This is pure
                            // pointer-event state: no timer, poller or delayed task.
                            const pointerThreshold = 12.0
                            const growthStep = 6.0
                            let resultX = admittedPointer.x
                            let resultY = admittedPointer.y
                            let candidate = resizeCandidateForPointer(
                                frame, handle, gesture, Qt.point(resultX, resultY)
                            )
                            let occupied = occupiedRectAt(
                                frame, candidate.x, candidate.y,
                                candidate.width, candidate.height
                            )

                            if (candidate.horizontalActive && !candidate.leftSide
                                    && occupied.x + occupied.width > editFrame.width + 0.25) {
                                const rawTravel = admittedPointer.x - gesture.lastGrowthPointerX
                                const allowance = rawTravel >= pointerThreshold ? growthStep : 0.0
                                const excess = occupied.x + occupied.width
                                    - (editFrame.width + allowance)
                                if (excess > 0.0)
                                    resultX -= excess
                                if (allowance > 0.0)
                                    gesture.lastGrowthPointerX = admittedPointer.x
                            }

                            candidate = resizeCandidateForPointer(
                                frame, handle, gesture, Qt.point(resultX, resultY)
                            )
                            occupied = occupiedRectAt(
                                frame, candidate.x, candidate.y,
                                candidate.width, candidate.height
                            )
                            if (candidate.verticalActive && !candidate.topSide
                                    && occupied.y + occupied.height > editFrame.height + 0.25) {
                                const rawTravel = admittedPointer.y - gesture.lastGrowthPointerY
                                const allowance = rawTravel >= pointerThreshold ? growthStep : 0.0
                                const excess = occupied.y + occupied.height
                                    - (editFrame.height + allowance)
                                if (excess > 0.0)
                                    resultY -= excess
                                if (allowance > 0.0)
                                    gesture.lastGrowthPointerY = admittedPointer.y
                            }
                            return Qt.point(resultX, resultY)
                        }

                        function beginChildResizeGesture(frame, gesture, handle, point) {
                            clearChildGuides(frame)
                            gesture.pressX = point.x
                            gesture.pressY = point.y
                            gesture.startX = frame.x
                            gesture.startY = frame.y
                            gesture.startWidth = frame.width
                            gesture.startHeight = frame.height
                            gesture.lastGrowthPointerX = point.x
                            gesture.lastGrowthPointerY = point.y
                            return customLayoutOverlay.sessionModel.beginChildResize(
                                editFrame.index, frame.roleId, handle, point.x, point.y,
                                frame.width, frame.height,
                                frame.normalizationWidth, frame.normalizationHeight
                            )
                        }

                        function updateChildResizeGesture(frame, gesture, handle, point, finalize) {
                            const bounded = customLayoutOverlay.sessionModel.previewChildResize(
                                editFrame.index, frame.roleId, handle, point.x, point.y
                            )
                            if (!bounded.valid) {
                                if (finalize) {
                                    customLayoutOverlay.sessionModel.cancelChildGesture(editFrame.index)
                                    clearChildGuides(frame)
                                }
                                return false
                            }
                            let admitted = admitChildResize(
                                frame, handle,
                                gesture.pressX, gesture.pressY,
                                gesture.startX, gesture.startY,
                                gesture.startWidth, gesture.startHeight,
                                Number(bounded.x), Number(bounded.y)
                            )
                            admitted = throttleChildAutoGrowth(frame, handle, gesture, admitted)
                            const candidate = resizeCandidateForPointer(
                                frame, handle, gesture, admitted
                            )
                            ensureImmediateChildOverflow(
                                frame, candidate.x, candidate.y,
                                candidate.width, candidate.height
                            )
                            const changed = customLayoutOverlay.sessionModel.resizeChild(
                                editFrame.index, frame.roleId, handle,
                                admitted.x, admitted.y, finalize
                            )
                            if (finalize) {
                                if (changed)
                                    syncRequirementNow()
                                clearChildGuides(frame)
                            }
                            return true
                        }

                        function cancelChildResizeGesture(frame) {
                            if (customLayoutOverlay.sessionModel)
                                customLayoutOverlay.sessionModel.cancelChildGesture(editFrame.index)
                            clearChildGuides(frame)
                        }

                        Repeater {
                            id: childRoleRepeater
                            model: editFrame.hasPresentationItem
                                ? (editFrame.presentationItem.customEditableChildRoles || [])
                                : []
                            // A Settings/provider state change can remove the role
                            // that established the largest mapped containment floor
                            // while the family requirement object itself remains.
                            // Recompute exactly when the role set changes so that
                            // stale selected-Edit containment cannot survive until
                            // the next pointer gesture. No timer/poller is involved.
                            onCountChanged: childRoleLayer.scheduleRequirementSync()
                            onModelChanged: childRoleLayer.scheduleRequirementSync()

                            delegate: Item {
                                id: childRoleFrame
                                required property var modelData
                                readonly property string roleId: String(modelData.roleId || "")
                                readonly property var targetItem: modelData.target || null
                                readonly property var occupiedItem:
                                    modelData.occupiedTarget || targetItem
                                readonly property var geometryDependencies:
                                    modelData.geometryDependencies || []
                                readonly property var resizeReflowRoleIds:
                                    modelData.resizeReflowRoleIds || []
                                // Families declare only the axis on which an upstream
                                // child resize translates those peers. The shared
                                // editor uses that semantic declaration to predict
                                // secondary collisions; it does not learn family
                                // anchor formulas or create another layout owner.
                                readonly property var resizeReflowAxes:
                                    modelData.resizeReflowAxes || []
                                // Some families reflow downstream peers only while
                                // this role remains on its authored rail. Keep that
                                // gate as a retained target property instead of
                                // rebuilding customEditableChildRoles when an X/Y
                                // offset changes mid-gesture; rebuilding the Repeater
                                // would destroy the active delegate and cancel the
                                // pointer stream after the first admitted sample.
                                readonly property var resizeReflowGate:
                                    modelData.resizeReflowGate || null
                                readonly property bool resizeReflowEnabled:
                                    resizeReflowGate === null
                                        ? true
                                        : Boolean(resizeReflowGate.customEditReflowEnabled)
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
                                readonly property real normalizationWidth: Math.max(
                                    1.0,
                                    Number(modelData.normalizationWidth
                                        || (editFrame.width / Math.max(1.0e-6, editFrame.resizeScale)))
                                )
                                readonly property real normalizationHeight: Math.max(
                                    1.0,
                                    Number(modelData.normalizationHeight
                                        || (editFrame.height / Math.max(1.0e-6, editFrame.resizeScale)))
                                )
                                readonly property bool movable:
                                    customLayoutOverlay.sessionModel !== null
                                        && customLayoutOverlay.sessionModel.childMovable(
                                            editFrame.index, roleId
                                        )
                                readonly property bool semanticCornerAnchorCapable:
                                    customLayoutOverlay.sessionModel !== null
                                        && customLayoutOverlay.sessionModel.childSemanticCornerAnchorCapable(
                                            editFrame.index, roleId
                                        )
                                readonly property string semanticAnchor: {
                                    const revision = editFrame.childStateRevision
                                    return semanticCornerAnchorCapable
                                            && customLayoutOverlay.sessionModel !== null
                                        ? customLayoutOverlay.sessionModel.childSemanticAnchor(
                                            editFrame.index, roleId
                                        )
                                        : ""
                                }
                                readonly property real semanticCornerInsetX: Math.max(
                                    0.0, Number(modelData.semanticCornerInsetX || 0.0)
                                )
                                readonly property real semanticCornerInsetY: Math.max(
                                    0.0, Number(modelData.semanticCornerInsetY || 0.0)
                                )
                                // Dense families may keep an on-rail role displaced
                                // by sibling reflow. When the user explicitly moves
                                // that role, Python folds this retained logical delta
                                // into the authored-relative offset exactly once so
                                // detaching from reflow cannot jump under the pointer.
                                // Families expose the values on the stable target item
                                // rather than rebuilding the role model mid-gesture.
                                readonly property real placementCompensationX:
                                    targetItem !== null
                                        ? Number(targetItem.customEditPlacementCompensationX || 0.0)
                                        : 0.0
                                readonly property real placementCompensationY:
                                    targetItem !== null
                                        ? Number(targetItem.customEditPlacementCompensationY || 0.0)
                                        : 0.0
                                readonly property bool targetReady: targetItem !== null
                                    && targetItem.visible
                                    && targetItem.width > 1.0
                                    && targetItem.height > 1.0

                                // mapToItem itself does not expose ancestor geometry
                                // as QML binding dependencies. Families therefore
                                // declare only object references to the few retained
                                // ancestors that can reflow a role. Reading their
                                // geometry here invalidates mapping event-by-event
                                // without rebuilding the role model or polling.
                                readonly property real mappingDependency: {
                                    let value = editFrame.width + editFrame.height
                                    if (targetItem !== null) {
                                        value += targetItem.x + targetItem.y
                                            + targetItem.width + targetItem.height
                                        value += Number(
                                            targetItem.customEditMappingDependency || 0.0
                                        )
                                    }
                                    if (occupiedItem !== null && occupiedItem !== targetItem) {
                                        value += occupiedItem.x + occupiedItem.y
                                            + occupiedItem.width + occupiedItem.height
                                        value += Number(
                                            occupiedItem.customEditMappingDependency || 0.0
                                        )
                                    }
                                    for (let i = 0; i < geometryDependencies.length; ++i) {
                                        const dependency = geometryDependencies[i]
                                        if (dependency)
                                            value += dependency.x + dependency.y
                                                + dependency.width + dependency.height
                                    }
                                    return value
                                }
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
                                readonly property point occupiedMappedTopLeft: {
                                    const dependency = mappingDependency
                                    return targetReady && occupiedItem !== null
                                        ? occupiedItem.mapToItem(editFrame, 0.0, 0.0)
                                        : mappedTopLeft
                                }
                                readonly property point occupiedMappedBottomRight: {
                                    const dependency = mappingDependency
                                    return targetReady && occupiedItem !== null
                                        ? occupiedItem.mapToItem(
                                            editFrame, occupiedItem.width, occupiedItem.height
                                        )
                                        : mappedBottomRight
                                }
                                readonly property real occupiedX: Math.min(
                                    occupiedMappedTopLeft.x, occupiedMappedBottomRight.x
                                )
                                readonly property real occupiedY: Math.min(
                                    occupiedMappedTopLeft.y, occupiedMappedBottomRight.y
                                )
                                readonly property real occupiedWidth: Math.abs(
                                    occupiedMappedBottomRight.x - occupiedMappedTopLeft.x
                                )
                                readonly property real occupiedHeight: Math.abs(
                                    occupiedMappedBottomRight.y - occupiedMappedTopLeft.y
                                )

                                property real moveStartX: 0.0
                                property real moveStartY: 0.0
                                property real movePressX: 0.0
                                property real movePressY: 0.0
                                // Gesture-local rebasing after a resisted peer pass.
                                // Python keeps one original move authority; this bias
                                // simply keeps subsequent raw pointer samples on the
                                // admitted far side instead of immediately requesting
                                // the pre-pass side again. It is never persisted.
                                property real movePassBiasX: 0.0
                                property real movePassBiasY: 0.0
                                property bool moveHadMotion: false
                                property bool hasSnapX: false
                                property bool hasSnapY: false
                                property real snapXTarget: 0.0
                                property real snapYTarget: 0.0
                                property real snapXFeature: 0.0
                                property real snapYFeature: 0.0
                                property string snapXKind: ""
                                property string snapYKind: ""

                                objectName: "customLayoutChildRole-"
                                            + editFrame.widgetId + "-" + roleId
                                visible: targetReady && roleId.length > 0
                                Component.onDestruction: {
                                    // Stable selection identity in Python owns focus
                                    // retirement. This delegate-level row call remains
                                    // only for a selected parent's Settings/visibility
                                    // role rebuild, where the row is still current.
                                    if (customLayoutOverlay.sessionModel
                                            && editFrame.selectedForChildEdit)
                                        customLayoutOverlay.sessionModel.cancelChildGesture(
                                            editFrame.index
                                        )
                                }
                                x: Math.min(mappedTopLeft.x, mappedBottomRight.x)
                                y: Math.min(mappedTopLeft.y, mappedBottomRight.y)
                                width: Math.abs(mappedBottomRight.x - mappedTopLeft.x)
                                height: Math.abs(mappedBottomRight.y - mappedTopLeft.y)

                                // Saved-slot application, Settings-driven role
                                // changes and retained ancestor reflow can move a
                                // target without a pointer handler running. Re-sync
                                // the selected parent's transient floor from those
                                // retained geometry notifications. callLater in the
                                // layer coalesces a burst; outside selected Edit this
                                // delegate does not exist.
                                onOccupiedXChanged: childRoleLayer.scheduleRequirementSync()
                                onOccupiedYChanged: childRoleLayer.scheduleRequirementSync()
                                onOccupiedWidthChanged: childRoleLayer.scheduleRequirementSync()
                                onOccupiedHeightChanged: childRoleLayer.scheduleRequirementSync()
                                onVisibleChanged: childRoleLayer.scheduleRequirementSync()

                                Rectangle {
                                    anchors.fill: parent
                                    z: 1
                                    color: "transparent"
                                    border.width: childRoleFrame.semanticAnchor.length > 0 ? 2 : 1
                                    border.color: childRoleFrame.semanticAnchor.length > 0
                                        ? "#dc8bc8ff" : "#a85f9fd7"
                                    radius: 2
                                }

                                MouseArea {
                                    id: childMoveArea
                                    anchors.fill: parent
                                    z: 0
                                    enabled: childRoleFrame.movable
                                    cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                                    propagateComposedEvents: false

                                    function overlayPoint(mouse) {
                                        return mapToItem(
                                            customLayoutOverlay, mouse.x, mouse.y
                                        )
                                    }

                                    onPressed: function(mouse) {
                                        mouse.accepted = true
                                        childRoleLayer.clearChildGuides(childRoleFrame)
                                        const point = overlayPoint(mouse)
                                        childRoleFrame.moveStartX = childRoleFrame.x
                                        childRoleFrame.moveStartY = childRoleFrame.y
                                        childRoleFrame.movePressX = point.x
                                        childRoleFrame.movePressY = point.y
                                        childRoleFrame.movePassBiasX = 0.0
                                        childRoleFrame.movePassBiasY = 0.0
                                        childRoleFrame.moveHadMotion = false
                                        if (!customLayoutOverlay.sessionModel.beginChildMove(
                                                    editFrame.index,
                                                    childRoleFrame.roleId,
                                                    point.x,
                                                    point.y,
                                                    childRoleFrame.normalizationWidth,
                                                    childRoleFrame.normalizationHeight,
                                                    childRoleFrame.placementCompensationX,
                                                    childRoleFrame.placementCompensationY)) {
                                            childRoleLayer.clearChildGuides(childRoleFrame)
                                            mouse.accepted = false
                                        }
                                    }
                                    onPositionChanged: function(mouse) {
                                        if (!pressed)
                                            return
                                        const point = overlayPoint(mouse)
                                        const desiredX = childRoleFrame.moveStartX
                                            + point.x - childRoleFrame.movePressX
                                            + childRoleFrame.movePassBiasX
                                        const desiredY = childRoleFrame.moveStartY
                                            + point.y - childRoleFrame.movePressY
                                            + childRoleFrame.movePassBiasY
                                        const admitted = childRoleLayer.admitChildMove(
                                            childRoleFrame, desiredX, desiredY
                                        )
                                        if (Math.abs(admitted.x - childRoleFrame.moveStartX) > 0.5
                                                || Math.abs(admitted.y - childRoleFrame.moveStartY) > 0.5)
                                            childRoleFrame.moveHadMotion = true
                                        const admittedPointerX = childRoleFrame.movePressX
                                            + admitted.x - childRoleFrame.moveStartX
                                        const admittedPointerY = childRoleFrame.movePressY
                                            + admitted.y - childRoleFrame.moveStartY
                                        childRoleLayer.ensureImmediateChildOverflow(
                                            childRoleFrame,
                                            admitted.x,
                                            admitted.y,
                                            childRoleFrame.width,
                                            childRoleFrame.height
                                        )
                                        customLayoutOverlay.sessionModel.moveChild(
                                            editFrame.index,
                                            childRoleFrame.roleId,
                                            admittedPointerX,
                                            admittedPointerY,
                                            false
                                        )
                                        // Retained occupied-rect change signals queue
                                        // one coalesced exact floor reconciliation.
                                        // Do not synchronously run the same scan a
                                        // second time on every pointer sample.
                                    }
                                    onReleased: function(mouse) {
                                        const point = overlayPoint(mouse)
                                        const desiredX = childRoleFrame.moveStartX
                                            + point.x - childRoleFrame.movePressX
                                            + childRoleFrame.movePassBiasX
                                        const desiredY = childRoleFrame.moveStartY
                                            + point.y - childRoleFrame.movePressY
                                            + childRoleFrame.movePassBiasY
                                        const admitted = childRoleLayer.admitChildMove(
                                            childRoleFrame, desiredX, desiredY
                                        )
                                        if (Math.abs(admitted.x - childRoleFrame.moveStartX) > 0.5
                                                || Math.abs(admitted.y - childRoleFrame.moveStartY) > 0.5)
                                            childRoleFrame.moveHadMotion = true
                                        childRoleLayer.ensureImmediateChildOverflow(
                                            childRoleFrame,
                                            admitted.x,
                                            admitted.y,
                                            childRoleFrame.width,
                                            childRoleFrame.height
                                        )
                                        const changed = customLayoutOverlay.sessionModel.moveChild(
                                            editFrame.index,
                                            childRoleFrame.roleId,
                                            childRoleFrame.movePressX
                                                + admitted.x - childRoleFrame.moveStartX,
                                            childRoleFrame.movePressY
                                                + admitted.y - childRoleFrame.moveStartY,
                                            true
                                        )
                                        if (changed)
                                            childRoleLayer.syncRequirementNow()
                                        if (childRoleFrame.moveHadMotion
                                                && childRoleFrame.semanticCornerAnchorCapable
                                                && customLayoutOverlay.sessionModel) {
                                            customLayoutOverlay.sessionModel.setChildSemanticAnchor(
                                                editFrame.index,
                                                childRoleFrame.roleId,
                                                childRoleLayer.semanticCornerFromSnaps(childRoleFrame)
                                            )
                                        }
                                        childRoleFrame.movePassBiasX = 0.0
                                        childRoleFrame.movePassBiasY = 0.0
                                        childRoleLayer.clearChildGuides(childRoleFrame)
                                    }
                                    onCanceled: {
                                        if (customLayoutOverlay.sessionModel)
                                            customLayoutOverlay.sessionModel.cancelChildGesture(
                                                editFrame.index
                                            )
                                        childRoleFrame.movePassBiasX = 0.0
                                        childRoleFrame.movePassBiasY = 0.0
                                        childRoleLayer.clearChildGuides(childRoleFrame)
                                    }
                                }

                                Rectangle {
                                    id: childAlignmentFlip
                                    objectName: "customLayoutChildAlignmentFlip-"
                                        + editFrame.widgetId + "-" + childRoleFrame.roleId
                                    visible: customLayoutOverlay.sessionModel !== null
                                        && customLayoutOverlay.sessionModel.childAlignmentFlippable(
                                            editFrame.index, childRoleFrame.roleId
                                        )
                                    width: 16
                                    height: 16
                                    radius: width / 2.0
                                    x: (childRoleFrame.width - width) / 2.0
                                    y: (childRoleFrame.height - height) / 2.0
                                    z: 4
                                    color: "#e01d2f42"
                                    border.width: 1
                                    border.color: "#d078b7e8"

                                    Text {
                                        anchors.centerIn: parent
                                        text: "↔"
                                        color: "#f0d8f3ff"
                                        font.pixelSize: 10
                                        font.bold: true
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        propagateComposedEvents: false
                                        onPressed: function(mouse) { mouse.accepted = true }
                                        onClicked: function(mouse) {
                                            mouse.accepted = true
                                            if (customLayoutOverlay.sessionModel)
                                                customLayoutOverlay.sessionModel.flipChildAlignment(
                                                    editFrame.index, childRoleFrame.roleId
                                                )
                                        }
                                    }
                                }

                                Repeater {
                                    model: {
                                        if (!customLayoutOverlay.sessionModel)
                                            return []
                                        const handles = customLayoutOverlay.sessionModel.childResizeHandles(
                                            editFrame.index, childRoleFrame.roleId
                                        )
                                        const anchor = childRoleFrame.semanticAnchor
                                        if (!anchor)
                                            return handles
                                        // While semantically corner-anchored, resize only
                                        // from the opposite corner so the snapped margin
                                        // itself stays fixed. A free drag detaches the
                                        // anchor and restores the normal four corners.
                                        if (anchor === "top_left")
                                            return ["bottom_right"]
                                        if (anchor === "top_right")
                                            return ["bottom_left"]
                                        if (anchor === "bottom_left")
                                            return ["top_right"]
                                        if (anchor === "bottom_right")
                                            return ["top_left"]
                                        return handles
                                    }

                                    delegate: Item {
                                        id: childResizeHandle
                                        required property string modelData
                                        property string corner: modelData
                                        property bool leftSide: corner.endsWith("left")
                                        property bool topSide: corner.startsWith("top_")
                                        property real pressX: 0.0
                                        property real pressY: 0.0
                                        property real startX: 0.0
                                        property real startY: 0.0
                                        property real startWidth: 0.0
                                        property real startHeight: 0.0
                                        property real lastGrowthPointerX: 0.0
                                        property real lastGrowthPointerY: 0.0
                                        z: 3
                                        width: 16
                                        height: 16
                                        x: leftSide ? -width / 2.0
                                                    : childRoleFrame.width - width / 2.0
                                        y: topSide ? -height / 2.0
                                                   : childRoleFrame.height - height / 2.0

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
                                            cursorShape: childResizeHandle.leftSide
                                                === childResizeHandle.topSide
                                                ? Qt.SizeFDiagCursor
                                                : Qt.SizeBDiagCursor
                                            propagateComposedEvents: false

                                            function overlayPoint(mouse) {
                                                return mapToItem(
                                                    customLayoutOverlay, mouse.x, mouse.y
                                                )
                                            }

                                            onPressed: function(mouse) {
                                                mouse.accepted = true
                                                const point = overlayPoint(mouse)
                                                if (!childRoleLayer.beginChildResizeGesture(
                                                            childRoleFrame, childResizeHandle,
                                                            childResizeHandle.corner, point))
                                                    mouse.accepted = false
                                            }
                                            onPositionChanged: function(mouse) {
                                                if (pressed)
                                                    childRoleLayer.updateChildResizeGesture(
                                                        childRoleFrame, childResizeHandle,
                                                        childResizeHandle.corner,
                                                        overlayPoint(mouse), false
                                                    )
                                            }
                                            onReleased: function(mouse) {
                                                childRoleLayer.updateChildResizeGesture(
                                                    childRoleFrame, childResizeHandle,
                                                    childResizeHandle.corner,
                                                    overlayPoint(mouse), true
                                                )
                                            }
                                            onCanceled: childRoleLayer.cancelChildResizeGesture(
                                                childRoleFrame
                                            )
                                        }
                                    }
                                }

                                // Invisible one-axis resize zones. They deliberately
                                // add no visual handle: the side cursor is the affordance.
                                // Placement-capable roles can use all truthful sides;
                                // size-only roles expose only the anchored right/bottom
                                // sides, and intrinsic/uniform roles stay corner-only.
                                Repeater {
                                    model: {
                                        if (!customLayoutOverlay.sessionModel)
                                            return []
                                        let edges = customLayoutOverlay.sessionModel.childResizeEdges(
                                            editFrame.index, childRoleFrame.roleId
                                        )
                                        const anchor = childRoleFrame.semanticAnchor
                                        if (!anchor)
                                            return edges
                                        if (anchor === "top_left")
                                            return edges.filter(function(edge) { return edge === "right" || edge === "bottom" })
                                        if (anchor === "top_right")
                                            return edges.filter(function(edge) { return edge === "left" || edge === "bottom" })
                                        if (anchor === "bottom_left")
                                            return edges.filter(function(edge) { return edge === "right" || edge === "top" })
                                        if (anchor === "bottom_right")
                                            return edges.filter(function(edge) { return edge === "left" || edge === "top" })
                                        return edges
                                    }

                                    delegate: Item {
                                        id: childResizeEdge
                                        required property string modelData
                                        property string edge: modelData
                                        property bool horizontalEdge: edge === "left" || edge === "right"
                                        property bool leftSide: edge === "left"
                                        property bool topSide: edge === "top"
                                        property real pressX: 0.0
                                        property real pressY: 0.0
                                        property real startX: 0.0
                                        property real startY: 0.0
                                        property real startWidth: 0.0
                                        property real startHeight: 0.0
                                        property real lastGrowthPointerX: 0.0
                                        property real lastGrowthPointerY: 0.0
                                        z: 2
                                        width: horizontalEdge ? 10.0 : Math.max(0.0, childRoleFrame.width - 20.0)
                                        height: horizontalEdge ? Math.max(0.0, childRoleFrame.height - 20.0) : 10.0
                                        x: edge === "left" ? -width / 2.0
                                           : (edge === "right" ? childRoleFrame.width - width / 2.0 : 10.0)
                                        y: edge === "top" ? -height / 2.0
                                           : (edge === "bottom" ? childRoleFrame.height - height / 2.0 : 10.0)

                                        MouseArea {
                                            objectName: "customLayoutChildResizeEdge-"
                                                + editFrame.widgetId + "-" + childRoleFrame.roleId
                                                + "-" + childResizeEdge.edge
                                            anchors.fill: parent
                                            cursorShape: childResizeEdge.horizontalEdge
                                                ? Qt.SizeHorCursor : Qt.SizeVerCursor
                                            propagateComposedEvents: false

                                            function overlayPoint(mouse) {
                                                return mapToItem(customLayoutOverlay, mouse.x, mouse.y)
                                            }

                                            onPressed: function(mouse) {
                                                mouse.accepted = true
                                                const point = overlayPoint(mouse)
                                                if (!childRoleLayer.beginChildResizeGesture(
                                                            childRoleFrame, childResizeEdge,
                                                            childResizeEdge.edge, point))
                                                    mouse.accepted = false
                                            }

                                            onPositionChanged: function(mouse) {
                                                if (pressed)
                                                    childRoleLayer.updateChildResizeGesture(
                                                        childRoleFrame, childResizeEdge,
                                                        childResizeEdge.edge,
                                                        overlayPoint(mouse), false
                                                    )
                                            }

                                            onReleased: function(mouse) {
                                                childRoleLayer.updateChildResizeGesture(
                                                    childRoleFrame, childResizeEdge,
                                                    childResizeEdge.edge,
                                                    overlayPoint(mouse), true
                                                )
                                            }

                                            onCanceled: childRoleLayer.cancelChildResizeGesture(
                                                childRoleFrame
                                            )
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
                                    // Connect the actual endpoints of the two 20 px-inset
                                    // side strips.  A sqrt(2) diagonal across this 20x20
                                    // wedge lands exactly on those strip centres instead
                                    // of floating as a decorative slash near the corner.
                                    width: Math.SQRT2 * parent.width
                                    height: 3
                                    radius: 1.5
                                    antialiasing: true
                                    color: "#dc6aa8e8"
                                    // Corner orientation is the mirror of the ordinary
                                    // square-resize cursor mapping: e.g. bottom-right must
                                    // run from the bottom-strip endpoint up to the
                                    // right-strip endpoint (/), not away from them (\).
                                    rotation: parent.leftSide === parent.topSide ? -45 : 45
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
                                        editFrame.syncChildRequirementNow()
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
