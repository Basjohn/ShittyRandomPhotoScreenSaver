import QtQuick

// Presentation only. The existing CUSTOM session alone admits and executes actions.
// No model/geometry state, no polling, no runtime clocks.
Item {
    id: chrome
    property bool admitted: false
    property bool hovered: false
    property bool canRestore: false
    property bool canRotate: false
    property bool canLock: false
    property bool canTransferLeft: false
    property bool canTransferRight: false
    readonly property color buttonSurface: "#d51b1e23"
    readonly property color buttonBorder: "#c0777d86"
    readonly property color buttonInk: "#f2f4f7"
    signal actionRequested(string action)
    // One event-triggered animation clock while a glyph is hovered; nothing
    // schedules or polls when a pointer is absent. Zero extra windows/threads.
    property string activeTip: ""
    property real tipX: 0
    property real tipY: 0
    property real delayedTipProgress: 0.0
    function hideTip(text) {
        if (activeTip !== text) return
        tipReveal.stop()
        activeTip = ""
        delayedTipProgress = 0
    }
    onCanTransferLeftChanged: if (!canTransferLeft) hideTip("MOVE TO PREVIOUS DISPLAY")
    onCanTransferRightChanged: if (!canTransferRight) hideTip("MOVE TO NEXT DISPLAY")
    // Restart per distinct glyph, so sliding from Lock to Close never inherits
    // Lock's completed hover delay. This is event-driven animation, no Timer.
    NumberAnimation {
        id: tipReveal
        target: chrome
        property: "delayedTipProgress"
        from: 0.0
        to: 1.0
        duration: 1800
        easing.type: Easing.Linear
    }
    onHoveredChanged: if (!hovered) {
        tipReveal.stop()
        activeTip = ""
        delayedTipProgress = 0.0
    }

    visible: admitted
    enabled: visible && hovered && opacity > 0.05
    opacity: admitted && hovered ? 0.94 : 0.0
    Behavior on opacity {
        NumberAnimation { duration: chrome.hovered ? 700 : 1200; easing.type: Easing.InOutSine }
    }

    // The lock is always present for a widget with editable child roles:
    // selection of the parent is NOT a visibility prerequisite.
    Row {
        id: actions
        // Consistent action lane across ordinary and visualizer widget cards.
        // Keep the lane inside the card, clear of its outside header chrome.
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.leftMargin: 10  // 2 px farther inside the actual card
        anchors.bottomMargin: 8
        spacing: 5
        Repeater {
            // Stable delegate identities: eligibility changes without rebuilding
            // the Repeater model or losing native QObject/action hit targets.
            model: ["lock", "restore", "rotate", "close"]
            delegate: Rectangle {
                required property string modelData
                readonly property string actionKind: modelData
                readonly property string tipText: actionKind === "lock" ? "TOGGLE CHILD LOCK"
                    : actionKind === "restore" ? "RESTORE WIDGET SIZE"
                    : actionKind === "rotate" ? "ROTATE WIDGET CONTENT"
                    : "CLOSE & DISABLE WIDGET"
                readonly property bool eligible: actionKind === "lock" ? chrome.canLock
                    : actionKind === "restore" ? chrome.canRestore
                    : actionKind === "rotate" ? chrome.canRotate : true
                objectName: "hoverEditGlyph-" + actionKind
                visible: eligible
                width: visible ? 24 : 0
                height: 24
                radius: 12
                color: chrome.buttonSurface
                border.width: 1
                border.color: chrome.buttonBorder
                z: 10
                Text {
                    anchors.centerIn: parent
                    visible: actionKind !== "lock" && actionKind !== "close"
                    text: (actionKind === "restore" ? "↶" : "↻")
                    // Increase the close X artwork, not its 24px button/hitbox.
                    font.pixelSize: actionKind === "restore" ? 17 : 15
                    anchors.verticalCenterOffset: 0
                    font.bold: true
                    color: "#f2f4f7"
                }
                // Draw a centred, larger X independent of font baseline and DPI.
                Canvas {
                    anchors.centerIn: parent
                    width: 20
                    height: 20
                    visible: actionKind === "close"
                    onPaint: {
                        const ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        ctx.strokeStyle = "#f2f4f7"
                        ctx.lineWidth = 2.3
                        ctx.lineCap = "round"
                        ctx.beginPath()
                        ctx.moveTo(5.38, 5.38)
                        ctx.lineTo(14.62, 14.62)
                        ctx.moveTo(14.62, 5.38)
                        ctx.lineTo(5.38, 14.62)
                        ctx.stroke()
                    }
                }
                // Match the established Edit chrome's actual padlock silhouette,
                // rather than using an OS-dependent coloured emoji or a square.
                Canvas {
                    anchors.centerIn: parent
                    width: 20
                    height: 20
                    visible: actionKind === "lock"
                    onPaint: {
                        const ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        ctx.save()
                        ctx.translate(10, 10)
                        ctx.scale(0.855, 0.855)
                        ctx.translate(-10, -10)
                        ctx.strokeStyle = "#f2f4f7"
                        ctx.lineWidth = 1.6
                        ctx.beginPath()
                        ctx.moveTo(5.5, 9.5)
                        ctx.lineTo(5.5, 6)
                        ctx.bezierCurveTo(5.5, 1.7, 14.5, 1.7, 14.5, 6)
                        ctx.lineTo(14.5, 9.5)
                        ctx.stroke()
                        ctx.fillStyle = "#f2f4f7"
                        ctx.fillRect(4, 9, 12, 9)
                        ctx.restore()
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    enabled: chrome.enabled && parent.visible
                    onEntered: {
                        chrome.activeTip = String(tipText)
                        chrome.tipX = actions.x + parent.x + parent.width / 2
                        chrome.tipY = actions.y
                        tipReveal.restart()
                    }
                    onExited: {
                        chrome.hideTip(String(tipText))
                    }
                    cursorShape: Qt.PointingHandCursor
                    propagateComposedEvents: false
                    onPressed: function(mouse) { mouse.accepted = true }
                    onClicked: function(mouse) {
                        mouse.accepted = true
                        chrome.actionRequested(String(actionKind))
                    }
                }
            }
        }
    }

    Repeater {
        // Absent on ordinary/single-display cards, retained during hover fades.
        model: chrome.canTransferLeft || chrome.canTransferRight ? [-1, 1] : []
        delegate: Rectangle {
            required property int modelData
            readonly property string actionKind: modelData < 0 ? "transfer_left" : "transfer_right"
            readonly property string tipText: modelData < 0 ? "MOVE TO PREVIOUS DISPLAY" : "MOVE TO NEXT DISPLAY"
            objectName: "hoverEditGlyph-" + actionKind
            visible: modelData < 0 ? chrome.canTransferLeft : chrome.canTransferRight
            width: 24
            height: 24
            radius: width / 2
            x: modelData < 0 ? 8 : Math.max(8, chrome.width - width - 8)
            y: Math.max(8, (chrome.height - height) / 2)
            color: chrome.buttonSurface
            border.width: 1
            border.color: chrome.buttonBorder
            Canvas {
                anchors.centerIn: parent
                width: 20
                height: 20
                onPaint: {
                    const ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    ctx.save()
                    if (modelData < 0) { ctx.translate(20, 0); ctx.scale(-1, 1) }
                    ctx.strokeStyle = chrome.buttonInk
                    ctx.lineWidth = 1.8
                    ctx.lineCap = "round"
                    ctx.lineJoin = "round"
                    ctx.beginPath()
                    ctx.moveTo(4, 10)
                    ctx.lineTo(16, 10)
                    ctx.moveTo(11, 5)
                    ctx.lineTo(16, 10)
                    ctx.lineTo(11, 15)
                    ctx.stroke()
                    ctx.restore()
                }
            }
            MouseArea {
                anchors.fill: parent
                enabled: chrome.enabled && parent.visible
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                propagateComposedEvents: false
                onEntered: {
                    chrome.activeTip = tipText
                    chrome.tipX = parent.x + parent.width / 2
                    chrome.tipY = parent.y
                    tipReveal.restart()
                }
                onExited: {
                    chrome.hideTip(tipText)
                }
                onPressed: function(mouse) { mouse.accepted = true }
                onClicked: function(mouse) {
                    mouse.accepted = true
                    chrome.actionRequested(actionKind)
                }
            }
        }
    }

    // Compact, themed glyph-only tooltip. The first 1000+ ms are invisible:
    // an existing QML animation driver handles the hover edge, not a Timer or
    // a Python worker. No hitbox ever covers the glyph row.
    Rectangle {
        id: glyphTip
        z: 50
        enabled: false
        visible: opacity > 0.0 && chrome.activeTip.length > 0
        opacity: Math.max(0.0, Math.min(1.0, (chrome.delayedTipProgress - 0.56) / 0.44))
        x: Math.max(4, Math.min(chrome.width - width - 4, chrome.tipX - width / 2))
        y: Math.max(3, chrome.tipY - height - 7)
        width: Math.min(190, caption.implicitWidth + 18)
        height: caption.implicitHeight + 12
        radius: 7
        color: "#e51d2634"
        border.width: 1
        border.color: "#bdc38e88"
        Text {
            id: caption
            anchors.centerIn: parent
            text: chrome.activeTip
            color: "#f6f6f8"
            font.pixelSize: 11
            font.weight: Font.Medium
        }
    }
}
