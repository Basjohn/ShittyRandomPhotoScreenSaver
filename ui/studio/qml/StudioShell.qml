// Mode-neutral Studio shell. Everything mode-specific arrives through `studio`
// (StudioBridge): workspaces, scene objects, inspector rows, values and fixtures.
// Edits call plain bridge slots; the viewport pixels are drawn by the production
// renderer under the `viewportSlot` item.
import QtQuick
import QtQuick.Controls.Basic as C

Rectangle {
    id: shell
    objectName: "studioShell"
    focus: true

    readonly property var t: studio.theme
    function tc(name, fallback) { return (t && t[name]) ? t[name] : fallback }
    readonly property color cBg: tc("bg", "#0b0d14")
    readonly property color cPanel: tc("panel", "#121621")
    readonly property color cRaised: tc("panelRaised", "#181d2b")
    readonly property color cOutline: tc("outline", "#7a6248")
    readonly property color cOutlineSoft: tc("outlineSoft", "#3a3128")
    readonly property color cAccent: tc("accent", "#9a7cff")
    readonly property color cAccentSoft: tc("accentSoft", "#2c2350")
    readonly property color cText: tc("text", "#f0f0f0")
    readonly property color cDim: tc("textDim", "#b8b8c0")
    readonly property color cDisabled: tc("textDisabled", "#73737a")
    readonly property color cInput: tc("input", "#1f1f1f")
    readonly property color cTrack: tc("track", "#2a2f3d")
    readonly property color cFocus: tc("focus", "#ffffffb4")
    readonly property color cDanger: tc("danger", "#e0605a")
    readonly property color cViewport: tc("viewportBg", "#05060a")
    readonly property color cHeader: tc("header", "#101010")
    readonly property color cAccentText: tc("accentText", "#ffffff")
    readonly property color cTrace1: tc("trace1", "#9a7cff")
    readonly property color cTrace2: tc("trace2", "#b8b8c0")
    readonly property color cTrace3: tc("trace3", "#6aa9d9")
    readonly property int unit: 8
    readonly property int fontBase: 13

    color: cBg

    Keys.onPressed: function(event) {
        if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_Z) {
            if (event.modifiers & Qt.ShiftModifier) studio.redo(); else studio.undo();
            event.accepted = true
        } else if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_Y) {
            studio.redo(); event.accepted = true
        } else if (event.key === Qt.Key_Space && !(event.modifiers & Qt.ControlModifier)) {
            studio.togglePlay(); event.accepted = true
        }
    }

    function fmt(value, decimals, units) {
        if (value === undefined || value === null) return "–"
        return Number(value).toFixed(decimals) + (units || "")
    }

    // ------------------------------------------------------------------ primitives
    component FocusRing: Rectangle {
        anchors.fill: parent
        anchors.margins: -3
        radius: 6
        color: "transparent"
        border.width: 2
        border.color: shell.cFocus
    }

    component StudioButton: Rectangle {
        id: btn
        property string text: ""
        property string tip: ""
        property bool primary: false
        property bool checked: false
        property bool enabledState: true
        property int textSize: shell.fontBase
        signal clicked()
        implicitWidth: Math.max(34, label.implicitWidth + 22)
        implicitHeight: 30
        radius: 5
        opacity: enabledState ? 1.0 : 0.45
        color: checked ? shell.cAccentSoft : (mouse.containsMouse && enabledState ? shell.cRaised : shell.cPanel)
        border.width: 1
        border.color: checked || primary ? shell.cAccent : shell.cOutlineSoft
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: text || tip
        Text {
            id: label
            anchors.centerIn: parent
            text: btn.text
            color: btn.checked ? shell.cText : (btn.primary ? shell.cAccent : shell.cText)
            font.pixelSize: btn.textSize
            font.bold: btn.checked
        }
        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: if (btn.enabledState) { btn.forceActiveFocus(); btn.clicked() }
        }
        Keys.onReturnPressed: if (enabledState) clicked()
        Keys.onSpacePressed: if (enabledState) clicked()
        FocusRing { visible: btn.activeFocus }
        C.ToolTip.visible: mouse.containsMouse && btn.tip !== ""
        C.ToolTip.text: btn.tip
        C.ToolTip.delay: 500
    }

    component Chip: Rectangle {
        id: chip
        property string text: ""
        property bool selected: false
        signal picked()
        implicitWidth: chipLabel.implicitWidth + 20
        implicitHeight: 26
        radius: 13
        color: selected ? shell.cAccentSoft : (chipMouse.containsMouse ? shell.cRaised : "transparent")
        border.width: selected ? 2 : 1
        border.color: selected ? shell.cAccent : shell.cOutlineSoft
        activeFocusOnTab: true
        Accessible.role: Accessible.RadioButton
        Accessible.name: text
        Accessible.checked: selected
        Text {
            id: chipLabel
            anchors.centerIn: parent
            text: chip.text
            color: shell.cText
            font.pixelSize: shell.fontBase - 1
            font.bold: chip.selected
        }
        MouseArea { id: chipMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: { chip.forceActiveFocus(); chip.picked() } }
        Keys.onReturnPressed: picked()
        Keys.onSpacePressed: picked()
        FocusRing { visible: chip.activeFocus; radius: 15 }
    }

    // A compact slider whose shown value follows the bridge except while it is being dragged.
    component ValueSlider: Item {
        id: vs
        property string propId: ""
        property string label: ""
        property int endpoint: 0
        property real from: 0
        property real to: 1
        property real value: 0
        property real ghost: NaN          // the other endpoint of a quiet/peak pair, drawn as a marker
        property bool integer: false
        property int decimals: 2
        property real dragValue: 0
        readonly property bool dragging: area.pressed
        readonly property real shown: dragging ? dragValue : value
        function frac(v) { return to > from ? Math.max(0, Math.min(1, (v - from) / (to - from))) : 0 }
        function valueAt(x) {
            var v = from + Math.max(0, Math.min(1, (x - 7) / Math.max(1, width - 14))) * (to - from)
            return integer ? Math.round(v) : v
        }
        function step(sign, coarse) {
            var s = integer ? 1 : (to - from) / (coarse ? 10 : 100)
            studio.commitValue(propId, endpoint, Math.max(from, Math.min(to, value + sign * s)))
        }
        implicitHeight: 22
        activeFocusOnTab: true
        Accessible.role: Accessible.Slider
        Accessible.name: label
        Rectangle {                        // track
            anchors.verticalCenter: parent.verticalCenter
            x: 7; width: parent.width - 14; height: 4; radius: 2
            color: shell.cTrack
            Rectangle { width: parent.width * vs.frac(vs.shown); height: parent.height; radius: 2; color: shell.cAccent }
        }
        Rectangle {                        // ghost of the other endpoint
            visible: !isNaN(vs.ghost)
            x: 7 + (vs.width - 14) * vs.frac(vs.ghost) - 1
            anchors.verticalCenter: parent.verticalCenter
            width: 2; height: 12; color: shell.cOutline
        }
        Rectangle {                        // handle
            x: 7 + (vs.width - 14) * vs.frac(vs.shown) - width / 2
            anchors.verticalCenter: parent.verticalCenter
            width: 14; height: 14; radius: 7
            color: vs.dragging ? shell.cText : shell.cRaised
            border.width: 2
            border.color: vs.activeFocus ? shell.cFocus : shell.cAccent
        }
        MouseArea {
            id: area
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onPressed: function(mouse) {
                vs.forceActiveFocus()
                vs.dragValue = vs.valueAt(mouse.x)
                studio.beginEdit(vs.propId, vs.label)
                studio.previewValue(vs.propId, vs.endpoint, vs.dragValue)
            }
            onPositionChanged: function(mouse) {
                if (!pressed) return
                vs.dragValue = vs.valueAt(mouse.x)
                studio.previewValue(vs.propId, vs.endpoint, vs.dragValue)
            }
            onReleased: studio.endEdit()
            onCanceled: studio.cancelEdit()
        }
        Keys.onLeftPressed: function(e) { step(-1, e.modifiers & Qt.ShiftModifier); e.accepted = true }
        Keys.onRightPressed: function(e) { step(1, e.modifiers & Qt.ShiftModifier); e.accepted = true }
        Keys.onEscapePressed: if (dragging) studio.cancelEdit()
    }

    // Exact entry: shows the value; editing commits on Enter / focus loss.
    component NumberField: Rectangle {
        id: nf
        property string propId: ""
        property int endpoint: 0
        property string display: ""
        implicitWidth: 64
        implicitHeight: 24
        radius: 4
        color: shell.cInput
        border.width: 1
        border.color: input.activeFocus ? shell.cAccent : shell.cOutlineSoft
        TextInput {
            id: input
            anchors.fill: parent
            anchors.margins: 4
            horizontalAlignment: TextInput.AlignRight
            verticalAlignment: TextInput.AlignVCenter
            color: shell.cText
            font.pixelSize: shell.fontBase - 1
            selectByMouse: true
            text: nf.display
            activeFocusOnTab: true
            Accessible.name: "Exact value"
            onEditingFinished: if (text !== nf.display) studio.commitText(nf.propId, nf.endpoint, text)
            Keys.onEscapePressed: { text = nf.display; focus = false }
        }
        Binding { target: input; property: "text"; value: nf.display; when: !input.activeFocus }
    }

    component RowLabel: Text {
        property string tip: ""
        color: shell.cDim
        font.pixelSize: shell.fontBase - 1
        elide: Text.ElideRight
        width: 118
        verticalAlignment: Text.AlignVCenter
        MouseArea { id: tipArea; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.RightButton
                    onClicked: studio.resetProperty(parent.propId) }
        property string propId: ""
        C.ToolTip.visible: tipArea.containsMouse && tip !== ""
        C.ToolTip.text: tip + (tip !== "" ? "\nRight-click: reset to the value the Studio opened with." : "")
        C.ToolTip.delay: 600
    }

    // A live trace of named measured signals (0..1), newest at the right. Repaints only on new data.
    component SignalTrace: Rectangle {
        id: trace
        property var channels: []
        implicitHeight: 56
        radius: 4
        color: shell.cViewport
        border.width: 1; border.color: shell.cOutlineSoft
        readonly property var colours: [shell.cTrace1, shell.cTrace2, shell.cTrace3]
        Canvas {
            id: canvas
            anchors.fill: parent; anchors.margins: 4
            onPaint: {
                var ctx = getContext("2d"); ctx.reset()
                var traces = studio.traces
                for (var c = 0; c < trace.channels.length; ++c) {
                    var values = traces[trace.channels[c]] || []
                    if (values.length < 2) continue
                    ctx.strokeStyle = trace.colours[c % trace.colours.length]
                    ctx.lineWidth = c === 0 ? 1.8 : 1.2
                    ctx.beginPath()
                    var n = 180
                    for (var i = 0; i < values.length; ++i) {
                        var x = width * (n - values.length + i) / (n - 1)
                        var y = height - 1 - values[i] * (height - 2)
                        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
                    }
                    ctx.stroke()
                }
            }
            Connections { target: studio; function onMeasurementsChanged() { canvas.requestPaint() } }
        }
        Row {
            anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 6
            spacing: 10
            Repeater {
                model: trace.channels
                delegate: Text { text: "— " + modelData; color: trace.colours[index % trace.colours.length]
                                 font.pixelSize: shell.fontBase - 3 }
            }
        }
        Accessible.name: "Live trace: " + channels.join(", ")
    }

    // ------------------------------------------------------------------- rows
    component ScalarRow: Row {
        property var row
        spacing: 8
        height: 28
        RowLabel { text: row.label; tip: row.tooltip; propId: row.id; height: parent.height }
        ValueSlider {
            width: parent.width - 118 - 72 - 16; anchors.verticalCenter: parent.verticalCenter
            propId: row.id; label: row.label; from: row.min; to: row.max; integer: row.integer
            value: studio.values[row.id] !== undefined ? studio.values[row.id] : row.min
        }
        NumberField { propId: row.id; anchors.verticalCenter: parent.verticalCenter
                      display: shell.fmt(studio.values[row.id], row.decimals, "") }
    }

    // Two response endpoints of ONE quantity: pick Quiet or Peak, edit that one, see the other as a ghost.
    component QuietPeakRow: Column {
        id: qp
        property var row
        property int endpoint: 0
        readonly property var pair: studio.values[row.id] || [row.min, row.min]
        spacing: 2
        Row {
            spacing: 8
            height: 28
            RowLabel { text: row.label; tip: row.tooltip + (row.tooltip ? "\n" : "") + "Quiet: " + row.quietMeaning
                       + " · Peak: " + row.peakMeaning; propId: row.id; height: parent.height }
            Row {
                spacing: 0
                anchors.verticalCenter: parent.verticalCenter
                Repeater {
                    model: ["Quiet", "Peak"]
                    delegate: Rectangle {
                        width: 46; height: 22
                        radius: 4
                        color: qp.endpoint === index ? shell.cAccentSoft : "transparent"
                        border.width: 1
                        border.color: qp.endpoint === index ? shell.cAccent : shell.cOutlineSoft
                        activeFocusOnTab: true
                        Accessible.role: Accessible.RadioButton
                        Accessible.name: modelData
                        Text { anchors.centerIn: parent; text: modelData; color: shell.cText
                               font.pixelSize: shell.fontBase - 2; font.bold: qp.endpoint === index }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                    onClicked: qp.endpoint = index }
                        Keys.onSpacePressed: qp.endpoint = index
                        FocusRing { visible: parent.activeFocus }
                    }
                }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: shell.fmt(qp.pair[0], row.decimals, "") + " → " + shell.fmt(qp.pair[1], row.decimals, row.units)
                color: shell.cDim; font.pixelSize: shell.fontBase - 2
            }
        }
        Row {
            spacing: 8
            height: 26
            x: 126
            ValueSlider {
                width: qp.width - 126 - 72 - 16; anchors.verticalCenter: parent.verticalCenter
                propId: row.id; label: row.label + (qp.endpoint ? " (Peak)" : " (Quiet)")
                endpoint: qp.endpoint; from: row.min; to: row.max; integer: row.integer
                value: qp.pair[qp.endpoint]; ghost: qp.pair[1 - qp.endpoint]
            }
            NumberField { propId: row.id; endpoint: qp.endpoint; anchors.verticalCenter: parent.verticalCenter
                          display: shell.fmt(qp.pair[qp.endpoint], row.decimals, "") }
        }
    }

    component SwitchRow: Row {
        property var row
        readonly property bool on: studio.values[row.id] === true
        spacing: 8
        height: 28
        RowLabel { text: row.label; tip: row.tooltip; propId: row.id; height: parent.height }
        Rectangle {
            id: track
            anchors.verticalCenter: parent.verticalCenter
            width: 40; height: 20; radius: 10
            color: on ? shell.cAccent : shell.cTrack
            border.width: 1; border.color: shell.cOutlineSoft
            activeFocusOnTab: true
            Accessible.role: Accessible.CheckBox
            Accessible.name: row.label
            Accessible.checked: on
            Rectangle { width: 16; height: 16; radius: 8; y: 2; x: on ? 22 : 2; color: shell.cText
                        Behavior on x { NumberAnimation { duration: 120 } } }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: studio.commitValue(row.id, 0, !on) }
            Keys.onSpacePressed: studio.commitValue(row.id, 0, !on)
            FocusRing { visible: track.activeFocus; radius: 12 }
        }
        Text { anchors.verticalCenter: parent.verticalCenter; text: on ? "ON" : "OFF"; color: shell.cDim
               font.pixelSize: shell.fontBase - 2 }
    }

    // Choices get their own full-width row under the label: chips wrap freely and never overlap.
    component ChoiceRow: Column {
        id: choiceRow
        property var row
        readonly property int current: row.choices.indexOf(studio.values[row.id])
        readonly property string note: row.notes && current >= 0 && current < row.notes.length ? row.notes[current] : ""
        spacing: 4
        topPadding: 2
        bottomPadding: 4
        RowLabel { text: row.label; tip: row.tooltip; propId: row.id; height: 20; width: choiceRow.width }
        Flow {
            width: choiceRow.width
            spacing: 6
            Repeater {
                model: row.choices
                delegate: Chip {
                    text: modelData; selected: studio.values[row.id] === modelData
                    onPicked: studio.commitValue(row.id, 0, modelData)
                    HoverHandler { id: chipHover }
                    C.ToolTip.visible: chipHover.hovered && row.notes && index < row.notes.length
                    C.ToolTip.text: row.notes && index < row.notes.length ? row.notes[index] : ""
                    C.ToolTip.delay: 400
                }
            }
        }
        Text {
            visible: choiceRow.note !== ""
            width: choiceRow.width
            wrapMode: Text.Wrap
            text: choiceRow.note
            color: shell.cDim
            font.pixelSize: shell.fontBase - 2
        }
    }

    component CountRow: Row {
        property var row
        spacing: 8
        height: 30
        RowLabel { text: row.label; tip: row.tooltip; propId: row.id; height: parent.height }
        Row {
            spacing: 6
            anchors.verticalCenter: parent.verticalCenter
            Repeater {
                model: Math.round(row.max - row.min) + 1
                delegate: Chip { text: String(Math.round(row.min) + index); width: 34
                                 selected: Math.round(studio.values[row.id]) === Math.round(row.min) + index
                                 onPicked: studio.commitValue(row.id, 0, Math.round(row.min) + index) }
            }
        }
    }

    component ColourRow: Row {
        property var row
        spacing: 8
        height: 30
        RowLabel { text: row.label; tip: row.tooltip; propId: row.id; height: parent.height }
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 40; height: 22; radius: 4
            color: studio.values[row.id] || "#000000"
            border.width: 1; border.color: shell.cOutline
        }
        NumberField { implicitWidth: 84; propId: row.id; anchors.verticalCenter: parent.verticalCenter
                      display: studio.values[row.id] || "" }
    }

    // ------------------------------------------------------------------- layout
    Column {
        anchors.fill: parent
        spacing: 0

        // Header ---------------------------------------------------------------------
        Rectangle {
            id: header
            width: parent.width; height: 52
            color: shell.cHeader
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: shell.cOutlineSoft }
            Row {
                anchors.left: parent.left; anchors.leftMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                spacing: 14
                Text { text: "SRPSS"; color: shell.cAccent; font.pixelSize: 18; font.bold: true }
                Rectangle { width: 1; height: 22; color: shell.cOutlineSoft; anchors.verticalCenter: parent.verticalCenter }
                Text { text: "Studio"; color: shell.cText; font.pixelSize: 18; anchors.verticalCenter: parent.verticalCenter }
                // Mode switcher: every registered Studio mode (one shell, one save path per mode).
                C.ComboBox {
                    id: modeBox
                    anchors.verticalCenter: parent.verticalCenter
                    width: 190; height: 30
                    model: studio.modes
                    textRole: "title"
                    enabled: studio.modes.length > 1
                    currentIndex: {
                        for (var i = 0; i < studio.modes.length; ++i) if (studio.modes[i].id === studio.modeId) return i
                        return 0
                    }
                    onActivated: function(index) { studio.switchMode(studio.modes[index].id) }
                    background: Rectangle { radius: 5; color: shell.cRaised; border.width: 1
                                            border.color: modeBox.activeFocus ? shell.cFocus : shell.cOutline }
                    contentItem: Text { leftPadding: 10; text: modeBox.displayText; color: shell.cText
                                        font.pixelSize: shell.fontBase + 1; verticalAlignment: Text.AlignVCenter }
                    indicator: Text { x: modeBox.width - width - 10; anchors.verticalCenter: parent.verticalCenter
                                      text: modeBox.enabled ? "▾" : ""; color: shell.cDim }
                    delegate: C.ItemDelegate {
                        width: modeBox.width
                        contentItem: Text { text: modelData.title; color: shell.cText; font.pixelSize: shell.fontBase }
                        background: Rectangle { color: highlighted ? shell.cAccentSoft : shell.cRaised }
                        highlighted: modeBox.highlightedIndex === index
                    }
                    popup.background: Rectangle { color: shell.cRaised; border.color: shell.cOutline; radius: 5 }
                    C.ToolTip.visible: hovered
                    C.ToolTip.text: studio.modes.length > 1 ? "Switch the Studio to another visualizer mode"
                                    : "Visualizer mode being edited (more 3D modes will join the Studio)"
                    C.ToolTip.delay: 500
                }
            }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8
                Rectangle {
                    height: 30; width: presetText.implicitWidth + 28; radius: 5
                    color: shell.cRaised; border.width: 1; border.color: shell.cOutline
                    Row {
                        anchors.centerIn: parent; spacing: 8
                        Text { id: presetText; text: studio.presetLabel; color: shell.cText; font.pixelSize: shell.fontBase }
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: studio.dirty
                    text: "● Modified"
                    color: shell.cAccent; font.pixelSize: shell.fontBase - 1; font.bold: true
                    Accessible.name: "Modified since the Studio opened"
                }
                StudioButton { text: "Undo"; enabledState: studio.canUndo
                               tip: studio.canUndo ? "Undo " + studio.undoText + " (Ctrl+Z)" : "Nothing to undo"
                               onClicked: studio.undo() }
                StudioButton { text: "Redo"; enabledState: studio.canRedo
                               tip: studio.canRedo ? "Redo " + studio.redoText + " (Ctrl+Y)" : "Nothing to redo"
                               onClicked: studio.redo() }
                StudioButton { text: "Revert"; enabledState: studio.dirty
                               tip: "Restore everything to the state the Studio opened with (undoable)"
                               onClicked: studio.revertAll() }
                StudioButton { text: "Save Preset As…"; tip: "Save the current Custom settings as a preset file"
                               onClicked: studio.savePresetAs() }
                StudioButton { text: "Close"; primary: true
                               tip: "Close the Studio and return to Settings (edits are already saved to Custom)"
                               onClicked: studio.requestClose() }
            }
        }

        // Workspace tabs ------------------------------------------------------------------
        Item {
            width: parent.width; height: 44
            Row {
                anchors.centerIn: parent
                spacing: 6
                Repeater {
                    model: studio.workspaces
                    delegate: Rectangle {
                        id: tab
                        readonly property bool current: studio.workspace === modelData.id
                        width: 170; height: 34; radius: 6
                        color: current ? shell.cAccentSoft : (tabMouse.containsMouse ? shell.cRaised : shell.cPanel)
                        border.width: current ? 2 : 1
                        border.color: current ? shell.cAccent : shell.cOutlineSoft
                        activeFocusOnTab: true
                        Accessible.role: Accessible.PageTab
                        Accessible.name: modelData.title
                        Row {
                            anchors.centerIn: parent
                            spacing: 8
                            Text { text: modelData.icon || ""; visible: text !== ""; color: tab.current ? shell.cAccent : shell.cDim
                                   font.pixelSize: shell.fontBase + 5; anchors.verticalCenter: parent.verticalCenter }
                            Text { text: modelData.title; color: shell.cText; anchors.verticalCenter: parent.verticalCenter
                                   font.pixelSize: shell.fontBase + 1; font.bold: tab.current }
                        }
                        MouseArea { id: tabMouse; anchors.fill: parent; hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor; onClicked: studio.setWorkspace(modelData.id) }
                        Keys.onSpacePressed: studio.setWorkspace(modelData.id)
                        FocusRing { visible: tab.activeFocus }
                    }
                }
            }
        }

        // Main row: objects | viewport | inspector -------------------------------------------
        Item {
            id: mainRow
            width: parent.width
            height: parent.height - header.height - 44
            // The viewport keeps visual priority (~60-70% of the width at desktop sizes).
            readonly property int leftW: Math.max(160, Math.min(220, width * 0.13))
            readonly property int rightW: Math.max(320, Math.min(400, width * 0.22))

            // Scene objects -------------------------------------------------------------------
            Rectangle {
                id: objectsPanel
                x: 10; y: 0
                width: mainRow.leftW; height: parent.height - 10
                radius: 8; color: shell.cPanel
                border.width: 1; border.color: shell.cOutline
                Column {
                    anchors.fill: parent; anchors.margins: 12
                    spacing: 8
                    Text { text: studio.objectNoun + "s"; color: shell.cText; font.pixelSize: shell.fontBase + 1
                           font.bold: true }
                    Repeater {
                        model: studio.objects
                        delegate: Rectangle {
                            id: obj
                            readonly property bool selected: studio.selectedObject === modelData.id
                            width: parent.width; height: 36; radius: 6
                            color: selected ? shell.cAccentSoft : (objMouse.containsMouse ? shell.cRaised : "transparent")
                            border.width: selected ? 2 : 1
                            border.color: selected ? shell.cAccent : shell.cOutlineSoft
                            opacity: modelData.visible ? 1.0 : 0.5
                            activeFocusOnTab: true
                            Accessible.role: Accessible.ListItem
                            Accessible.name: modelData.label + (modelData.visible ? "" : " (hidden by count)")
                            Row {
                                anchors.verticalCenter: parent.verticalCenter
                                x: 10; spacing: 10
                                Rectangle { width: 16; height: 16; radius: 3; color: modelData.swatch
                                            border.width: 1; border.color: shell.cOutline
                                            anchors.verticalCenter: parent.verticalCenter }
                                Text { text: modelData.label; color: shell.cText; font.pixelSize: shell.fontBase
                                       font.bold: obj.selected; anchors.verticalCenter: parent.verticalCenter }
                            }
                            MouseArea { id: objMouse; anchors.fill: parent; hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor; onClicked: studio.selectObject(modelData.id) }
                            Rectangle {      // visibility eye
                                id: eye
                                visible: modelData.toggleable
                                anchors.right: parent.right; anchors.rightMargin: 6
                                anchors.verticalCenter: parent.verticalCenter
                                width: 26; height: 22; radius: 4
                                color: eyeMouse.containsMouse ? shell.cRaised : "transparent"
                                Text { anchors.centerIn: parent; text: modelData.visible ? "◉" : "◌"
                                       color: modelData.visible ? shell.cText : shell.cDim; font.pixelSize: shell.fontBase + 5 }
                                MouseArea { id: eyeMouse; anchors.fill: parent; hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: studio.setObjectVisible(modelData.id, !modelData.visible) }
                                C.ToolTip.visible: eyeMouse.containsMouse
                                C.ToolTip.text: (modelData.visible ? "Hide" : "Show") + " (" + studio.objectNoun
                                                + " Count shows the first N)" + (modelData.note ? " · " + modelData.note : "")
                                C.ToolTip.delay: 400
                            }
                            Keys.onSpacePressed: studio.selectObject(modelData.id)
                            FocusRing { visible: obj.activeFocus }
                        }
                    }
                    StudioButton {
                        width: parent.width
                        text: "+  Add " + studio.objectNoun
                        enabledState: studio.canAddObject
                        tip: studio.canAddObject ? "Show one more " + studio.objectNoun.toLowerCase()
                                                 : "All " + studio.objectNoun.toLowerCase() + "s are shown"
                        onClicked: studio.addObject()
                    }
                }
            }

            // Viewport column ----------------------------------------------------------------
            Item {
                id: viewportColumn
                x: objectsPanel.x + objectsPanel.width + 10
                width: parent.width - mainRow.leftW - mainRow.rightW - 40
                height: parent.height - 10

                Rectangle {
                    id: viewportFrame
                    width: parent.width
                    height: parent.height - (responseDock.visible ? responseDock.height + 10 : 0)
                    radius: 8
                    color: shell.cViewport
                    border.width: 1; border.color: shell.cOutline

                    // Toolbar
                    Row {
                        id: toolbar
                        x: 12; y: 10
                        spacing: 8
                        z: 2
                        StudioButton { text: studio.playing ? "❚❚" : "▶"; width: 36; primary: true; textSize: 16
                                       tip: (studio.playing ? "Pause" : "Play") + " the preview (Space)"
                                       onClicked: studio.togglePlay() }
                        C.ComboBox {
                            id: fixtureBox
                            width: 230; height: 30
                            model: studio.fixtures
                            textRole: "label"
                            valueRole: "id"
                            currentIndex: {
                                for (var i = 0; i < studio.fixtures.length; ++i)
                                    if (studio.fixtures[i].id === studio.fixtureId) return i
                                return -1
                            }
                            displayText: currentIndex >= 0 ? studio.fixtures[currentIndex].label : "Choose input"
                            onActivated: function(index) { studio.selectFixture(studio.fixtures[index].id) }
                            delegate: C.ItemDelegate {
                                width: fixtureBox.width
                                contentItem: Text {
                                    text: modelData.label + (modelData.kind === "recorded"
                                          ? (modelData.status === "loading" ? "  · analysing…"
                                             : modelData.status === "error" ? "  · failed" : "  · recorded")
                                          : modelData.kind === "synthetic" ? "  · synthetic" : "  · reference")
                                    color: shell.cText; font.pixelSize: shell.fontBase - 1
                                }
                                background: Rectangle { color: highlighted ? shell.cAccentSoft : shell.cRaised }
                                highlighted: fixtureBox.highlightedIndex === index
                            }
                            background: Rectangle { radius: 5; color: shell.cPanel; border.width: 1
                                                    border.color: fixtureBox.activeFocus ? shell.cAccent : shell.cOutlineSoft }
                            contentItem: Text { leftPadding: 10; text: fixtureBox.displayText; color: shell.cText
                                                font.pixelSize: shell.fontBase; verticalAlignment: Text.AlignVCenter
                                                elide: Text.ElideRight }
                            popup.background: Rectangle { color: shell.cRaised; border.color: shell.cOutline; radius: 5 }
                            C.ToolTip.visible: hovered
                            C.ToolTip.text: "Preview input: held references, synthetic tests, or recorded music"
                            C.ToolTip.delay: 600
                        }
                        Repeater {            // the mode's held reference states (e.g. Quiet / Mid / Peak)
                            model: studio.fixtures.filter(function(f) { return f.kind === "reference" })
                            delegate: Chip {
                                text: modelData.label
                                selected: studio.fixtureId === modelData.id
                                anchors.verticalCenter: parent.verticalCenter
                                onPicked: studio.selectFixture(modelData.id)
                            }
                        }
                    }
                    Row {
                        anchors.right: parent.right; anchors.rightMargin: 12; y: 10
                        spacing: 8; z: 2
                        Repeater {
                            model: studio.framings
                            delegate: Chip {
                                text: modelData.label
                                selected: studio.framingId === modelData.id
                                anchors.verticalCenter: parent.verticalCenter
                                onPicked: studio.selectFraming(modelData.id)
                                C.ToolTip.visible: hovered_ && modelData.description !== ""
                                C.ToolTip.text: modelData.description
                                C.ToolTip.delay: 500
                                property bool hovered_: false
                            }
                        }
                        StudioButton { text: "✓"; width: 34; textSize: 16; enabledState: studio.viewModified
                                       tip: "Keep View: save the previewed lens (FOV); the orbit saves only when the "
                                            + "preset's camera checkbox is on; dolly and pan stay previews"
                                       onClicked: studio.keepView() }
                        StudioButton { text: "⟲"; width: 34; textSize: 18; enabledState: studio.viewModified
                                       tip: "Reset View: back to the saved camera (or double-click the scene)"
                                       onClicked: studio.resetCamera() }
                    }

                    // The production scene is drawn under this slot by the Studio viewport item.
                    Item {
                        id: viewportSlot
                        objectName: "viewportSlot"
                        x: 1; y: 50
                        width: parent.width - 2
                        height: parent.height - 50 - scrubBar.height
                        clip: false
                        // Set by the shell host: where the letterboxed presented frame (the live card's
                        // world extent, production aperture) sits inside this slot.
                        property real frameX: 0
                        property real frameY: 0
                        property real frameWidth: width
                        property real frameHeight: height
                        Rectangle {
                            x: viewportSlot.frameX - 1; y: viewportSlot.frameY - 1
                            width: viewportSlot.frameWidth + 2; height: viewportSlot.frameHeight + 2
                            color: "transparent"; border.width: 1; border.color: shell.cOutlineSoft
                            visible: viewportSlot.frameWidth < viewportSlot.width - 2
                                     || viewportSlot.frameHeight < viewportSlot.height - 2
                        }

                        // Navigation: drag = orbit, middle/right drag = pan, wheel = zoom (lens),
                        // Shift+wheel = dolly, double-click = back to the saved camera.
                        MouseArea {
                            id: orbitArea
                            anchors.fill: parent
                            acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
                            property real lastX: 0
                            property real lastY: 0
                            property bool panning: false
                            cursorShape: pressed ? (panning ? Qt.SizeAllCursor : Qt.ClosedHandCursor) : Qt.OpenHandCursor
                            onPressed: function(m) {
                                lastX = m.x; lastY = m.y; shell.forceActiveFocus()
                                panning = m.button !== Qt.LeftButton
                            }
                            onPositionChanged: function(m) {
                                if (!pressed) return
                                if (panning) studio.panBy(m.x - lastX, m.y - lastY, viewportSlot.frameWidth, viewportSlot.frameHeight)
                                else studio.orbitBy(m.x - lastX, m.y - lastY)
                                lastX = m.x; lastY = m.y
                            }
                            onReleased: if (!panning) studio.endOrbit()
                            onDoubleClicked: studio.resetCamera()
                            onWheel: function(w) {
                                studio.zoomBy(w.angleDelta.y / 120.0, (w.modifiers & Qt.ShiftModifier) !== 0)
                                w.accepted = true
                            }
                        }
                        // Live view readout (bottom-left of the presented frame)
                        Rectangle {
                            x: viewportSlot.frameX + 8
                            y: viewportSlot.frameY + viewportSlot.frameHeight - height - 8
                            width: readout.implicitWidth + 16; height: 24; radius: 4
                            color: "#99000000"
                            visible: studio.viewReadout.length > 0
                            Row {
                                id: readout
                                anchors.centerIn: parent
                                spacing: 10
                                Repeater {
                                    model: studio.viewReadout
                                    delegate: Text {
                                        text: modelData.label + " " + Number(modelData.value).toFixed(modelData.units === "°" ? 1 : 2)
                                              + modelData.units
                                        color: modelData.changed ? shell.cAccent : "#e8e8e8"
                                        font.pixelSize: shell.fontBase - 3
                                    }
                                }
                                Text { text: studio.viewModified ? "· preview" : "· saved camera"; color: "#bbbbbb"
                                       font.pixelSize: shell.fontBase - 3 }
                            }
                        }
                        Rectangle {
                            visible: studio.viewportStatus !== "live"
                            anchors.centerIn: parent
                            width: Math.min(parent.width - 40, statusText.implicitWidth + 40)
                            height: statusText.implicitHeight + 24
                            radius: 6
                            color: "#cc0b0d14"
                            border.width: 1
                            border.color: studio.viewportStatus === "error" ? shell.cDanger : shell.cOutline
                            Text {
                                id: statusText
                                anchors.centerIn: parent
                                width: Math.min(implicitWidth, parent.parent.width - 80)
                                wrapMode: Text.Wrap
                                horizontalAlignment: Text.AlignHCenter
                                color: studio.viewportStatus === "error" ? shell.cDanger : shell.cText
                                font.pixelSize: shell.fontBase
                                text: studio.viewportStatus === "error"
                                      ? "Preview failed — the scene could not render.\n" + studio.viewportError
                                      : "Preparing the production scene…"
                            }
                        }
                    }

                    // Scrub / time bar
                    Rectangle {
                        id: scrubBar
                        anchors.bottom: parent.bottom
                        width: parent.width; height: 48
                        color: "transparent"
                        Rectangle { width: parent.width; height: 1; color: shell.cOutlineSoft }
                        Row {
                            anchors.fill: parent; anchors.margins: 10
                            spacing: 10
                            Item {
                                id: scrub
                                width: parent.width - timeText.width - loopBtn.width - 20
                                height: parent.height
                                activeFocusOnTab: true
                                Accessible.role: Accessible.Slider
                                Accessible.name: "Preview time"
                                readonly property real frac: studio.duration > 0 ? studio.time / studio.duration : 0
                                // Input energy over the whole preview input: a waveform scrub track.
                                Canvas {
                                    id: trackCanvas
                                    anchors.fill: parent
                                    onPaint: {
                                        var ctx = getContext("2d"); ctx.reset()
                                        var levels = studio.timeline, n = levels.length
                                        if (!n) return
                                        var mid = height / 2, w = width / n
                                        for (var i = 0; i < n; ++i) {
                                            var h = Math.max(1, levels[i] * (height - 6) / 2)
                                            ctx.fillStyle = (i / n) <= scrub.frac ? shell.cAccent : shell.cTrack
                                            ctx.fillRect(i * w, mid - h, Math.max(1, w - 1), 2 * h)
                                        }
                                    }
                                    Connections { target: studio
                                                  function onTransportChanged() { trackCanvas.requestPaint() }
                                                  function onTimeChanged() { trackCanvas.requestPaint() } }
                                    Component.onCompleted: requestPaint()
                                }
                                Rectangle { x: parent.width * scrub.frac - 1; anchors.verticalCenter: parent.verticalCenter
                                            width: 3; height: 18; color: scrub.activeFocus ? shell.cFocus : shell.cText }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    function at(x) { return Math.max(0, Math.min(1, x / width)) * studio.duration }
                                    onPressed: function(m) { scrub.forceActiveFocus(); studio.seek(at(m.x)) }
                                    onPositionChanged: function(m) { if (pressed) studio.seek(at(m.x)) }
                                }
                                Keys.onLeftPressed: studio.seek(studio.time - 0.5)
                                Keys.onRightPressed: studio.seek(studio.time + 0.5)
                            }
                            Text { id: timeText; anchors.verticalCenter: parent.verticalCenter; width: 92
                                   text: studio.time.toFixed(2) + " / " + studio.duration.toFixed(1) + " s"
                                   color: shell.cDim; font.pixelSize: shell.fontBase - 1 }
                            StudioButton { id: loopBtn; text: "Loop"; checked: studio.loop
                                           anchors.verticalCenter: parent.verticalCenter
                                           tip: "Repeat the preview input"; onClicked: studio.setLoop(!studio.loop) }
                        }
                    }

                    // Transient notices (clamps, rejected values, camera policy)
                    Rectangle {
                        visible: studio.message !== ""
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.bottom: scrubBar.top; anchors.bottomMargin: 10
                        width: Math.min(parent.width - 40, noticeText.implicitWidth + 60); height: 32; radius: 6
                        color: shell.cRaised; border.width: 1; border.color: shell.cOutline
                        z: 3
                        Text { id: noticeText; anchors.verticalCenter: parent.verticalCenter; x: 12
                               text: studio.message; color: shell.cText; font.pixelSize: shell.fontBase - 1 }
                        Text { anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
                               text: "✕"; color: shell.cDim
                               MouseArea { anchors.fill: parent; anchors.margins: -6; onClicked: studio.dismissMessage() } }
                    }
                }
            }

            // Response editor (Reactivity): target -> source mix with live input -> transfer curve -> range.
            Rectangle {
                id: responseDock
                parent: viewportColumn
                visible: studio.workspace === "reactivity" && studio.response.targets !== undefined
                anchors.bottom: parent.bottom
                width: parent.width
                height: 250
                radius: 8
                color: shell.cPanel
                border.width: 1; border.color: shell.cOutline
                readonly property var targets: studio.response.targets || []
                readonly property var sources: studio.response.sources || []
                readonly property var target: {
                    for (var i = 0; i < targets.length; ++i) if (targets[i].id === studio.selectedTarget) return targets[i]
                    return targets.length ? targets[0] : null
                }
                function sourceLabel(id) {
                    for (var i = 0; i < sources.length; ++i) if (sources[i].id === id) return sources[i].label
                    return id
                }
                function cellFor(sourceId) {
                    if (!target) return null
                    for (var i = 0; i < target.cells.length; ++i) if (target.cells[i].source === sourceId) return target.cells[i]
                    return null
                }

                Row {
                    anchors.fill: parent; anchors.margins: 12
                    spacing: 14

                    // Targets, with their live drive
                    Column {
                        width: 170; height: parent.height
                        spacing: 4
                        Text { text: "Targets"; color: shell.cText; font.pixelSize: shell.fontBase; font.bold: true }
                        C.ScrollView {
                            width: parent.width; height: parent.height - 24
                            clip: true
                            Column {
                                width: 166
                                spacing: 3
                                Repeater {
                                    model: responseDock.targets
                                    delegate: Rectangle {
                                        id: targetItem
                                        readonly property bool current: responseDock.target && responseDock.target.id === modelData.id
                                        readonly property real drive: studio.measurements.targets
                                                                      ? (studio.measurements.targets[modelData.id] || 0) : 0
                                        width: parent.width; height: 26; radius: 5
                                        color: current ? shell.cAccentSoft : (tMouse.containsMouse ? shell.cRaised : "transparent")
                                        border.width: current ? 2 : 0
                                        border.color: shell.cAccent
                                        activeFocusOnTab: true
                                        Accessible.role: Accessible.ListItem
                                        Accessible.name: modelData.label
                                        Text { x: 8; anchors.verticalCenter: parent.verticalCenter; text: modelData.label
                                               color: shell.cText; font.pixelSize: shell.fontBase - 1; font.bold: targetItem.current
                                               width: parent.width - 52; elide: Text.ElideRight }
                                        Rectangle { anchors.right: parent.right; anchors.rightMargin: 6
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    width: 36; height: 5; radius: 2; color: shell.cTrack
                                                    Rectangle { width: parent.width * Math.min(1, targetItem.drive)
                                                                height: parent.height; radius: 2; color: shell.cAccent } }
                                        MouseArea { id: tMouse; anchors.fill: parent; hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor; onClicked: studio.selectTarget(modelData.id) }
                                        Keys.onSpacePressed: studio.selectTarget(modelData.id)
                                        FocusRing { visible: targetItem.activeFocus }
                                        C.ToolTip.visible: tMouse.containsMouse
                                        C.ToolTip.text: modelData.description + "\nBar: live drive (measured)"
                                        C.ToolTip.delay: 500
                                    }
                                }
                            }
                        }
                    }

                    // Source mix: one gain per source over its measured live input
                    Column {
                        id: mixColumn
                        width: parent.width - 170 - 330 - 28
                        spacing: 6
                        Text { text: responseDock.target ? responseDock.target.label + " — Source Mix" : ""
                               color: shell.cText; font.pixelSize: shell.fontBase + 1; font.bold: true }
                        Text { text: responseDock.target ? responseDock.target.description : ""
                               color: shell.cDim; font.pixelSize: shell.fontBase - 2; width: parent.width; elide: Text.ElideRight }
                        Repeater {
                            model: responseDock.target ? responseDock.target.cells : []
                            delegate: Row {
                                id: mixRow
                                readonly property real input: studio.measurements.sources
                                                              ? (studio.measurements.sources[modelData.source] || 0) : 0
                                readonly property bool chosen: studio.selectedSource === modelData.source
                                spacing: 8
                                height: 28
                                Rectangle {
                                    width: 92; height: 24; radius: 4
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: mixRow.chosen ? shell.cAccentSoft : "transparent"
                                    border.width: 1; border.color: mixRow.chosen ? shell.cAccent : shell.cOutlineSoft
                                    activeFocusOnTab: true
                                    Accessible.role: Accessible.RadioButton
                                    Accessible.name: responseDock.sourceLabel(modelData.source)
                                    Text { anchors.centerIn: parent; text: responseDock.sourceLabel(modelData.source)
                                           color: shell.cText; font.pixelSize: shell.fontBase - 2; font.bold: mixRow.chosen }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                onClicked: studio.selectSource(modelData.source) }
                                    Keys.onSpacePressed: studio.selectSource(modelData.source)
                                    FocusRing { visible: parent.activeFocus }
                                }
                                Item {
                                    width: mixColumn.width - 92 - 64 - 60 - 24; height: 24
                                    anchors.verticalCenter: parent.verticalCenter
                                    // measured live input, drawn under the gain slider
                                    Rectangle { x: 7; y: 18; height: 3; radius: 1; color: shell.cTrace3; opacity: .85
                                                width: (parent.width - 14) * Math.min(1, mixRow.input) }
                                    ValueSlider {
                                        anchors.fill: parent
                                        propId: modelData.gain; label: responseDock.sourceLabel(modelData.source) + " gain"
                                        from: studio.response.gainMin; to: studio.response.gainMax
                                        value: studio.values[modelData.gain] !== undefined ? studio.values[modelData.gain] : 0
                                    }
                                }
                                NumberField { propId: modelData.gain; anchors.verticalCenter: parent.verticalCenter
                                              display: shell.fmt(studio.values[modelData.gain], 2, "") }
                                Text { anchors.verticalCenter: parent.verticalCenter; width: 60
                                       text: "curve " + shell.fmt(studio.values[modelData.power], 2, "")
                                       color: shell.cDim; font.pixelSize: shell.fontBase - 2 }
                            }
                        }
                        Text { text: "Gain per source; the thin bar is that source's measured live input. "
                                     + "A source moving while the target bar stays flat is diagnostic."
                               color: shell.cDim; font.pixelSize: shell.fontBase - 3; width: parent.width; wrapMode: Text.Wrap }
                    }

                    // Transfer curve for the chosen source, then the target's quiet/peak endpoints
                    Column {
                        width: 330
                        spacing: 6
                        Text { text: "Response Curve — " + responseDock.sourceLabel(studio.selectedSource)
                               color: shell.cText; font.pixelSize: shell.fontBase + 1; font.bold: true }
                        Rectangle {
                            id: curveBox
                            width: parent.width; height: 92; radius: 4
                            color: shell.cViewport; border.width: 1; border.color: shell.cOutlineSoft
                            readonly property var cell: responseDock.cellFor(studio.selectedSource)
                            readonly property real gain: cell && studio.values[cell.gain] !== undefined ? studio.values[cell.gain] : 0
                            readonly property real power: cell && studio.values[cell.power] !== undefined ? studio.values[cell.power] : 1
                            readonly property real live: studio.measurements.sources
                                                         ? (studio.measurements.sources[studio.selectedSource] || 0) : 0
                            property real dragPower: 1
                            readonly property real shownPower: curveDrag.pressed ? dragPower : power
                            Canvas {
                                id: curveCanvas
                                anchors.fill: parent; anchors.margins: 6
                                onPaint: {
                                    var ctx = getContext("2d"); ctx.reset()
                                    ctx.strokeStyle = shell.cOutlineSoft; ctx.lineWidth = 1
                                    ctx.strokeRect(0, 0, width, height)
                                    ctx.strokeStyle = shell.cAccent; ctx.lineWidth = 2; ctx.beginPath()
                                    for (var i = 0; i <= 64; ++i) {
                                        var x = i / 64, y = Math.min(1, curveBox.gain * Math.pow(x, curveBox.shownPower))
                                        var px = x * width, py = height - y * height
                                        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py)
                                    }
                                    ctx.stroke()
                                    var lx = curveBox.live, ly = Math.min(1, curveBox.gain * Math.pow(lx, curveBox.shownPower))
                                    ctx.fillStyle = shell.cTrace3
                                    ctx.beginPath(); ctx.arc(lx * width, height - ly * height, 4, 0, 2 * Math.PI); ctx.fill()
                                }
                                Connections { target: studio
                                              function onValuesChanged() { curveCanvas.requestPaint() }
                                              function onMeasurementsChanged() { curveCanvas.requestPaint() }
                                              function onResponseChanged() { curveCanvas.requestPaint() } }
                                Connections { target: curveBox; function onDragPowerChanged() { curveCanvas.requestPaint() } }
                            }
                            MouseArea {
                                id: curveDrag
                                anchors.fill: parent
                                cursorShape: Qt.SizeVerCursor
                                enabled: curveBox.cell !== null && curveBox.gain > 0
                                function powerAt(y) {
                                    var v = Math.max(0.02, Math.min(0.98, 1 - (y - 6) / (height - 12)))
                                    var ratio = Math.min(0.999, v / Math.max(curveBox.gain, 1e-3))
                                    var p = Math.log(Math.max(ratio, 1e-3)) / Math.log(0.5)
                                    return Math.max(studio.response.powerMin, Math.min(studio.response.powerMax, p))
                                }
                                onPressed: function(m) {
                                    curveBox.dragPower = powerAt(m.y)
                                    studio.beginEdit(curveBox.cell.power, "Response Curve")
                                    studio.previewValue(curveBox.cell.power, 0, curveBox.dragPower)
                                }
                                onPositionChanged: function(m) {
                                    if (!pressed) return
                                    curveBox.dragPower = powerAt(m.y)
                                    studio.previewValue(curveBox.cell.power, 0, curveBox.dragPower)
                                }
                                onReleased: studio.endEdit()
                            }
                            Text { anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 6
                                   text: "gain " + curveBox.gain.toFixed(2) + " · curve " + curveBox.shownPower.toFixed(2)
                                   color: shell.cDim; font.pixelSize: shell.fontBase - 3 }
                            C.ToolTip.visible: curveDrag.containsMouse
                            C.ToolTip.text: "Drag up/down to bend the curve (exact power below). Dot: live input → output."
                        }
                        Row {
                            spacing: 6
                            Repeater {
                                model: studio.response.presets || []
                                delegate: Chip {
                                    text: modelData.label
                                    selected: curveBox.cell !== null && Math.abs(curveBox.power - modelData.power) < 1e-3
                                    onPicked: if (curveBox.cell) studio.commitValue(curveBox.cell.power, 0, modelData.power)
                                }
                            }
                            NumberField { propId: curveBox.cell ? curveBox.cell.power : ""; implicitWidth: 54
                                          display: shell.fmt(curveBox.power, 2, "") }
                        }
                        Loader {
                            width: parent.width
                            active: studio.targetRange.id !== undefined
                            property var rowData: studio.targetRange
                            sourceComponent: quietPeakDelegate
                        }
                        Text { text: studio.response.timingNote + " (Timing, in the inspector)"
                               color: shell.cDim; font.pixelSize: shell.fontBase - 3; width: parent.width; wrapMode: Text.Wrap }
                    }
                }
            }

            // Inspector ------------------------------------------------------------------------
            Rectangle {
                id: inspectorPanel
                x: viewportColumn.x + viewportColumn.width + 10
                width: mainRow.rightW; height: parent.height - 10
                radius: 8; color: shell.cPanel
                border.width: 1; border.color: shell.cOutline
                C.ScrollView {
                    id: inspectorScroll
                    anchors.fill: parent; anchors.margins: 12
                    clip: true
                    contentWidth: availableWidth
                    Column {
                        width: inspectorScroll.availableWidth
                        spacing: 14
                        Repeater {
                            model: studio.inspector
                            delegate: Column {
                                id: group
                                property bool open: modelData.open === true
                                width: parent.width
                                spacing: 6
                                Rectangle {
                                    width: parent.width; height: 30; radius: 5
                                    color: groupMouse.containsMouse ? shell.cRaised : "transparent"
                                    border.width: 1; border.color: shell.cOutlineSoft
                                    activeFocusOnTab: true
                                    Accessible.role: Accessible.Button
                                    Accessible.name: modelData.title
                                    Text { x: 10; anchors.verticalCenter: parent.verticalCenter
                                           text: (group.open ? "▾  " : "▸  ") + (modelData.icon ? modelData.icon + "  " : "")
                                                 + modelData.title
                                           color: shell.cText; font.pixelSize: shell.fontBase; font.bold: true }
                                    MouseArea { id: groupMouse; anchors.fill: parent; hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor; onClicked: group.open = !group.open }
                                    Keys.onSpacePressed: group.open = !group.open
                                    FocusRing { visible: parent.activeFocus }
                                }
                                SignalTrace {
                                    visible: group.open && modelData.traces.length > 0
                                    width: parent.width
                                    channels: modelData.traces
                                }
                                Column {
                                    visible: group.open
                                    width: parent.width
                                    spacing: 4
                                    Repeater {
                                        model: modelData.rows
                                        delegate: Loader {
                                            objectName: "inspectorRow"
                                            width: parent.width
                                            height: item ? item.implicitHeight || item.height : 0
                                            property var rowData: modelData
                                            sourceComponent: {
                                                switch (modelData.instrument) {
                                                case "quiet_peak": return quietPeakDelegate
                                                case "switch": return switchDelegate
                                                case "choice": return choiceDelegate
                                                case "count": return countDelegate
                                                case "colour": return colourDelegate
                                                default: return scalarDelegate
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
        }
    }

    Component { id: scalarDelegate; ScalarRow { width: parent ? parent.width : 0; row: rowData } }
    Component { id: quietPeakDelegate; QuietPeakRow { width: parent ? parent.width : 0; row: rowData } }
    Component { id: switchDelegate; SwitchRow { width: parent ? parent.width : 0; row: rowData } }
    Component { id: choiceDelegate; ChoiceRow { width: parent ? parent.width : 0; row: rowData } }
    Component { id: countDelegate; CountRow { width: parent ? parent.width : 0; row: rowData } }
    Component { id: colourDelegate; ColourRow { width: parent ? parent.width : 0; row: rowData } }
}
