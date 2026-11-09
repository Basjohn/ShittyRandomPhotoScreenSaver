// Mode-neutral Studio shell. Everything mode-specific arrives through `studio`
// (StudioBridge): workspaces, scene objects, inspector rows, values and fixtures.
// Edits call plain bridge slots; the viewport pixels are drawn by the production
// renderer under the `viewportSlot` item.
import QtQuick
import QtQuick.Controls.Basic as C
import SRPSS.StudioChrome 1.0

Rectangle {
    id: shell
    objectName: "studioShell"
    focus: true

    readonly property var t: studio.theme
    // What the active mode's viewport supports (adapter-declared): viewport / camera / handles.
    readonly property var caps: studio.capabilities
    function endpointValue(id, endpoint) {
        var v = studio.values[id]
        if (v === undefined) return 0
        return (typeof v === "object" && v !== null && v.length !== undefined) ? Number(v[endpoint]) : Number(v)
    }
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
    // Instrument wells (trace cards, the response curve, the transport bar) and the inks checked on them
    // (ui/studio/theme.py): the viewport tone on a dark theme, the theme's input surface on a light one.
    readonly property color cWell: tc("well", cViewport)
    readonly property color cWellText: tc("wellText", cText)
    readonly property color cWellDim: tc("wellDim", cDim)
    readonly property color cWellTrace1: tc("wellTrace1", cTrace1)
    readonly property color cWellTrace2: tc("wellTrace2", cTrace2)
    readonly property color cWellTrace3: tc("wellTrace3", cTrace3)
    readonly property int unit: 8
    // Viewport toolbar state (preview only, never saved): overlays hidden; viewport expanded over the panels.
    property bool overlaysHidden: false
    property bool viewportExpanded: false
    readonly property int fontBase: 13
    // Glow semantics (mock): every highlight is the theme accent at a few strengths, never a fixed colour.
    function accentA(alpha) { return Qt.rgba(cAccent.r, cAccent.g, cAccent.b, alpha) }
    readonly property color cGlow: accentA(0.38)
    readonly property color cGlowSoft: accentA(0.16)
    readonly property color cPanelTop: Qt.lighter(cPanel, 1.18)

    // Window chrome as Settings draws it (ui/studio/theme.py): the native backdrop mode of the active theme, the
    // title bar roles, the forged edge, and Settings' panel cast scaled to the Studio's gutters.
    readonly property bool translucent: tc("backdrop", "off") !== "off"
    readonly property color cWindow: tc("windowSurface", cBg)
    readonly property color cTitlebar: tc("titlebar", cHeader)
    readonly property color cTitleText: tc("titlebarText", cText)
    readonly property color cTitleHover: tc("titlebarHover", cRaised)
    readonly property color cTitlePressed: tc("titlebarPressed", cRaised)
    readonly property color cCloseHover: tc("closeHover", "#e81123")
    readonly property real panelAlpha: Number(tc("panelAlpha", "1"))
    function withAlpha(c, a) { return Qt.rgba(c.r, c.g, c.b, c.a * a) }
    readonly property color cPanelFill: withAlpha(cPanel, panelAlpha)
    readonly property color cPanelFillTop: withAlpha(cPanelTop, panelAlpha)
    readonly property color cShadow: tc("shadow", "#5a000000")
    readonly property real shadowX: Number(tc("shadowX", "3"))
    readonly property real shadowY: Number(tc("shadowY", "4"))
    // Card and section borders: one painted path (StudioFrame) or one Quick ring, never QSS-like segments.
    readonly property real cardBorder: 1.5
    readonly property bool maximized: studio.windowMaximized === true

    color: "transparent"
    // The window surface: the theme's own window role (translucent under Glass/Acrylic); Normal keeps the
    // opaque lit gradient.
    Rectangle {
        anchors.fill: parent
        color: shell.cWindow
        gradient: shell.translucent ? null : windowGradient
        Gradient {
            id: windowGradient
            GradientStop { position: 0.0; color: Qt.lighter(shell.cBg, 1.35) }
            GradientStop { position: 0.45; color: shell.cBg }
            GradientStop { position: 1.0; color: Qt.darker(shell.cBg, 1.2) }
        }
    }

    Keys.onPressed: function(event) {
        if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_Z) {
            if (event.modifiers & Qt.ShiftModifier) studio.redo(); else studio.undo();
            event.accepted = true
        } else if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_Y) {
            studio.redo(); event.accepted = true
        } else if (event.key === Qt.Key_Space && !(event.modifiers & Qt.ControlModifier)) {
            studio.togglePlay(); event.accepted = true
        } else if (event.key === Qt.Key_F11) {
            viewportExpanded = !viewportExpanded; event.accepted = true
        } else if (event.key === Qt.Key_F1 || event.key === Qt.Key_Question) {
            helpOverlay.open = !helpOverlay.open; event.accepted = true
        } else if (event.key === Qt.Key_B && !(event.modifiers & Qt.ControlModifier) && shell.caps.brush === true) {
            studio.setBrushActive(!(studio.brushState.active === true)); event.accepted = true
        } else if (event.key === Qt.Key_Escape && studio.brushState.painting === true) {
            studio.brushCancel(); event.accepted = true          // Esc drops the stroke being painted
        } else if (event.key === Qt.Key_Escape && helpOverlay.open) {
            helpOverlay.open = false; event.accepted = true
        } else if (event.key === Qt.Key_Escape) {
            // Esc leaves the Studio (every edit is already saved); open popups and drags take Esc first.
            Qt.callLater(studio.requestCloseFrom, "escape"); event.accepted = true   // never tear down inside the handler
        }
    }

    // A theme colour with full alpha (backings that must hide the scene behind them).
    function opaque(c) { return Qt.rgba(c.r, c.g, c.b, 1.0) }

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

    // A soft accent halo around a selected / active element (mock's glowing selection).
    component SelectionGlow: Rectangle {
        property real spread: 3
        anchors.fill: parent
        anchors.margins: -spread
        radius: (parent.radius || 0) + spread
        color: "transparent"
        border.width: spread
        border.color: shell.cGlowSoft
        z: -1
        Rectangle { anchors.fill: parent; anchors.margins: parent.spread - 1; radius: parent.radius - parent.spread + 1
                    color: "transparent"; border.width: 1; border.color: shell.cGlow }
    }

    // Panel finish: a lit top edge fading down, and a faint accent rim.
    component PanelRim: Rectangle {
        anchors.fill: parent
        anchors.margins: -1
        radius: (parent.radius || 0) + 1
        color: "transparent"
        border.width: 1
        border.color: shell.accentA(0.22)
        z: -1
    }

    component StudioButton: Rectangle {
        id: btn
        property string text: ""
        property string tip: ""
        property bool primary: false
        property bool checked: false
        property bool enabledState: true
        property int textSize: shell.fontBase
        property string icon: ""
        property int iconSize: 18
        signal clicked()
        implicitWidth: Math.max(34, (icon !== "" ? iconSize + (text !== "" ? 8 : 0) : 0) + label.implicitWidth + 22)
        implicitHeight: 30
        radius: 5
        opacity: enabledState ? 1.0 : 0.45
        color: checked ? shell.cAccentSoft : (mouse.containsMouse && enabledState ? shell.cRaised : shell.cPanel)
        border.width: 1
        border.color: checked || primary ? shell.cAccent : shell.cOutlineSoft
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: text || tip
        Row {
            anchors.centerIn: parent
            spacing: 8
            StudioIcon { visible: btn.icon !== ""; name: btn.icon; width: btn.iconSize; height: btn.iconSize
                         anchors.verticalCenter: parent.verticalCenter
                         color: btn.primary ? shell.cAccent : shell.cText; filled: btn.icon === "play" }
            Text {
                id: label
                visible: text !== ""
                anchors.verticalCenter: parent.verticalCenter
                text: btn.text
                color: btn.checked ? shell.cText : (btn.primary ? shell.cAccent : shell.cText)
                font.pixelSize: btn.textSize
                font.bold: btn.checked
            }
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
        SelectionGlow { visible: btn.checked || (btn.primary && mouse.containsMouse && btn.enabledState); spread: 2 }
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
        SelectionGlow { visible: chip.selected; spread: 2 }
        FocusRing { visible: chip.activeFocus; radius: 15 }
    }

    // A compact slider whose shown value follows the bridge except while it is being dragged.
    component ValueSlider: Item {
        id: vs
        objectName: "valueSlider"
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
        // An edit the preview follows only on release (the engine re-analyses it once, when the drag ends).
        property bool releaseOnly: false
        // A tool setting (the brush's radius, strength...): set on the bridge directly, never a saved edit.
        property string toolName: ""
        readonly property bool dragging: area.pressed
        readonly property real shown: dragging ? dragValue : value
        function frac(v) { return to > from ? Math.max(0, Math.min(1, (v - from) / (to - from))) : 0 }
        function valueAt(x) {
            var v = from + Math.max(0, Math.min(1, (x - 7) / Math.max(1, width - 14))) * (to - from)
            return integer ? Math.round(v) : v
        }
        function step(sign, coarse) {
            var s = integer ? 1 : (to - from) / (coarse ? 10 : 100)
            var next = Math.max(from, Math.min(to, value + sign * s))
            if (toolName !== "") studio.setBrushValue(toolName, next)
            else studio.commitValue(propId, endpoint, next)
        }
        implicitHeight: 22
        activeFocusOnTab: true
        Accessible.role: Accessible.Slider
        Accessible.name: label
        Rectangle {                        // track, filled with the accent up to the value
            anchors.verticalCenter: parent.verticalCenter
            x: 7; width: parent.width - 14; height: 6; radius: 3
            color: shell.cTrack
            Rectangle {
                width: Math.max(parent.height, parent.width * vs.frac(vs.shown)); height: parent.height; radius: 3
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: Qt.darker(shell.cAccent, 1.7) }
                    GradientStop { position: 1.0; color: shell.cAccent }
                }
            }
        }
        Rectangle {                        // ghost of the other endpoint
            visible: !isNaN(vs.ghost)
            x: 7 + (vs.width - 14) * vs.frac(vs.ghost) - 1
            anchors.verticalCenter: parent.verticalCenter
            width: 2; height: 12; color: shell.cOutline
        }
        Rectangle {                        // knob halo while hovered / dragged
            x: 7 + (vs.width - 14) * vs.frac(vs.shown) - width / 2
            anchors.verticalCenter: parent.verticalCenter
            width: 26; height: 26; radius: 13
            color: shell.cGlowSoft
            visible: vs.dragging || area.containsMouse
        }
        Rectangle {                        // handle
            x: 7 + (vs.width - 14) * vs.frac(vs.shown) - width / 2
            anchors.verticalCenter: parent.verticalCenter
            width: 16; height: 16; radius: 8
            color: vs.dragging ? shell.cText : Qt.lighter(shell.cRaised, 1.4)
            border.width: 2
            border.color: vs.activeFocus ? shell.cFocus : shell.cAccent
        }
        Text {                             // a held edit says so while it is dragged
            objectName: "releaseHint"
            visible: vs.dragging && vs.releaseOnly
            anchors.right: parent.right; anchors.rightMargin: 7
            anchors.bottom: parent.top; anchors.bottomMargin: -4
            text: "Updates On Release"
            color: shell.cDim; font.pixelSize: shell.fontBase - 3
        }
        MouseArea {
            id: area
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            // The panel scrolls (a Flickable): without this, any vertical wobble past the drag threshold hands the
            // press to the scroll view mid-drag and the slider lets go (operator, 6 Nov: "snap out of being dragged").
            preventStealing: true
            onPressed: function(mouse) {
                vs.forceActiveFocus()
                vs.dragValue = vs.valueAt(mouse.x)
                if (vs.toolName !== "") { studio.setBrushValue(vs.toolName, vs.dragValue); return }
                studio.beginEdit(vs.propId, vs.label)
                studio.previewValue(vs.propId, vs.endpoint, vs.dragValue)
            }
            onPositionChanged: function(mouse) {
                if (!pressed) return
                vs.dragValue = vs.valueAt(mouse.x)
                if (vs.toolName !== "") { studio.setBrushValue(vs.toolName, vs.dragValue); return }
                studio.previewValue(vs.propId, vs.endpoint, vs.dragValue)
            }
            onReleased: if (vs.toolName === "") studio.endEdit()
            onCanceled: if (vs.toolName === "") studio.cancelEdit()
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
        Connections {
            target: studio
            function onRevealed(id, endpoint) {
                if (id !== nf.propId || endpoint !== nf.endpoint) return
                input.forceActiveFocus(); input.selectAll()
                Qt.callLater(function() {
                    var scroll = nf.parent
                    while (scroll && scroll.objectName !== "inspectorScroll") scroll = scroll.parent
                    if (!scroll) return
                    var flick = scroll.contentItem
                    var p = nf.mapToItem(flick.contentItem, 0, 0)
                    flick.contentY = Math.max(0, Math.min(flick.contentHeight - flick.height, p.y - 80))
                })
            }
        }
    }

    // One line that never overflows: elided to its width, the full text on hover when it is cut.
    component HintText: Text {
        id: hint
        objectName: "hintText"
        property string full: text
        elide: Text.ElideRight
        maximumLineCount: 1
        color: shell.cDim
        font.pixelSize: shell.fontBase - 3
        MouseArea { id: hintArea; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton }
        C.ToolTip.visible: hintArea.containsMouse && hint.truncated
        C.ToolTip.text: hint.full
        C.ToolTip.delay: 300
    }

    component RowLabel: Text {
        id: rowLabel
        property string tip: ""
        property string icon: ""          // a canonical glyph before the label (mock), when the row has one
        leftPadding: icon !== "" ? 22 : 0
        color: shell.cDim
        font.pixelSize: shell.fontBase - 1
        elide: Text.ElideRight
        width: 118
        verticalAlignment: Text.AlignVCenter
        StudioIcon { visible: rowLabel.icon !== ""; name: rowLabel.icon; width: 15; height: 15; stroke: 1.6
                     color: shell.cDim; anchors.verticalCenter: parent.verticalCenter }
        MouseArea { id: tipArea; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.RightButton
                    onClicked: studio.resetProperty(parent.propId) }
        property string propId: ""
        C.ToolTip.visible: tipArea.containsMouse && (tip !== "" || truncated)
        C.ToolTip.text: (truncated ? text + (tip !== "" ? "\n" : "") : "") + tip
                        + (tip !== "" ? "\nRight-click: reset to the value the Studio opened with." : "")
        C.ToolTip.delay: 600
    }

    // A live trace of named measured signals (0..1), newest at the right. Repaints only on new data.
    component SignalTrace: Rectangle {
        id: trace
        property var channels: []
        objectName: "signalTrace"
        implicitHeight: 56
        radius: 4
        color: shell.cWell
        border.width: shell.cardBorder; border.color: shell.cOutlineSoft
        readonly property var colours: [shell.cWellTrace1, shell.cWellTrace2, shell.cWellTrace3]
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


    // ------------------------------------------------------------- colour helpers (display sRGB)
    function hexToRgb(h) {
        h = String(h).replace("#", "")
        if (h.length === 8) h = h.slice(2)
        return [parseInt(h.slice(0, 2), 16) / 255, parseInt(h.slice(2, 4), 16) / 255, parseInt(h.slice(4, 6), 16) / 255]
    }
    function rgbToHex(c) {
        function two(v) { var s = Math.round(Math.max(0, Math.min(1, v)) * 255).toString(16); return s.length < 2 ? "0" + s : s }
        return "#" + two(c[0]) + two(c[1]) + two(c[2])
    }
    function rgbToHsv(c) {
        var mx = Math.max(c[0], c[1], c[2]), mn = Math.min(c[0], c[1], c[2]), d = mx - mn, h = 0
        if (d > 1e-6) {
            if (mx === c[0]) h = ((c[1] - c[2]) / d) % 6
            else if (mx === c[1]) h = (c[2] - c[0]) / d + 2
            else h = (c[0] - c[1]) / d + 4
            h /= 6; if (h < 0) h += 1
        }
        return [h, mx > 0 ? d / mx : 0, mx]
    }
    function hsvToRgb(h, sat, v) {
        var i = Math.floor(h * 6), f = h * 6 - i, p = v * (1 - sat), q = v * (1 - f * sat), t = v * (1 - (1 - f) * sat)
        switch (((i % 6) + 6) % 6) {
        case 0: return [v, t, p]; case 1: return [q, v, p]; case 2: return [p, v, t]
        case 3: return [p, q, v]; case 4: return [t, p, v]; default: return [v, p, q]
        }
    }

    // A display-space HSV picker. `changed` previews while dragging, `picked` commits on release / Enter.
    component ColourPicker: Column {
        id: picker
        property string hex: "#808080"
        signal changed(string hex)
        signal picked(string hex)
        property var hsv: shell.rgbToHsv(shell.hexToRgb(hex))
        onHexChanged: if (!svArea.pressed && !hueArea.pressed) hsv = shell.rgbToHsv(shell.hexToRgb(hex))
        function current() { return shell.rgbToHex(shell.hsvToRgb(hsv[0], hsv[1], hsv[2])) }
        spacing: 6
        Row {
            spacing: 8
            Rectangle {
                id: sv
                width: Math.max(120, picker.width - 116); height: 108; radius: 4
                border.width: 1; border.color: shell.cOutlineSoft
                color: shell.rgbToHex(shell.hsvToRgb(picker.hsv[0], 1, 1))
                Rectangle { anchors.fill: parent; radius: 4
                            gradient: Gradient { orientation: Gradient.Horizontal
                                                 GradientStop { position: 0; color: "#ffffffff" }
                                                 GradientStop { position: 1; color: "#00ffffff" } } }
                Rectangle { anchors.fill: parent; radius: 4
                            gradient: Gradient { GradientStop { position: 0; color: "#00000000" }
                                                 GradientStop { position: 1; color: "#ff000000" } } }
                Rectangle { x: picker.hsv[1] * sv.width - 6; y: (1 - picker.hsv[2]) * sv.height - 6
                            width: 12; height: 12; radius: 6; color: "transparent"; border.width: 2; border.color: "white" }
                MouseArea {
                    id: svArea
                    anchors.fill: parent
                    preventStealing: true                  // a drag holds until release, even in a scrolling panel
                    function pick(m) {
                        picker.hsv = [picker.hsv[0], Math.max(0, Math.min(1, m.x / width)), Math.max(0, Math.min(1, 1 - m.y / height))]
                        picker.changed(picker.current())
                    }
                    onPressed: function(m) { pick(m) }
                    onPositionChanged: function(m) { if (pressed) pick(m) }
                    onReleased: picker.picked(picker.current())
                }
            }
            Rectangle {
                id: hueBar
                width: 16; height: 108; radius: 3
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#ff0000" } GradientStop { position: 0.17; color: "#ffff00" }
                    GradientStop { position: 0.33; color: "#00ff00" } GradientStop { position: 0.5; color: "#00ffff" }
                    GradientStop { position: 0.67; color: "#0000ff" } GradientStop { position: 0.83; color: "#ff00ff" }
                    GradientStop { position: 1.0; color: "#ff0000" }
                }
                Rectangle { y: picker.hsv[0] * hueBar.height - 2; width: hueBar.width; height: 4; color: "white" }
                MouseArea {
                    id: hueArea
                    anchors.fill: parent
                    preventStealing: true
                    function pick(m) {
                        picker.hsv = [Math.max(0, Math.min(0.999, m.y / height)), picker.hsv[1], picker.hsv[2]]
                        picker.changed(picker.current())
                    }
                    onPressed: function(m) { pick(m) }
                    onPositionChanged: function(m) { if (pressed) pick(m) }
                    onReleased: picker.picked(picker.current())
                }
            }
            Column {
                spacing: 6
                Rectangle { width: 46; height: 30; radius: 4; color: picker.current(); border.width: 1; border.color: shell.cOutline }
                Rectangle {
                    width: 76; height: 24; radius: 4; color: shell.cInput; border.width: 1
                    border.color: hexInput.activeFocus ? shell.cAccent : shell.cOutlineSoft
                    TextInput { id: hexInput; anchors.fill: parent; anchors.margins: 4; color: shell.cText
                                font.pixelSize: shell.fontBase - 1; selectByMouse: true; text: picker.current()
                                Accessible.name: "Hex colour"
                                onAccepted: if (/^#?[0-9a-fA-F]{6}$/.test(text)) picker.picked(text.charAt(0) === "#" ? text : "#" + text) }
                }
            }
        }
    }

    // Ordered colour nodes on a strip: drag to move, click to pick a colour, double-click to add.
    component GradientRow: Column {
        id: gr
        objectName: "gradientRow"
        property var row
        readonly property var nodes: studio.values[row.id] || []
        property int selected: -1
        property var working: null        // nodes during a drag/pick (display), else null
        readonly property var shown: working || nodes
        function payload(list) {
            var out = []
            for (var i = 0; i < list.length; ++i) out.push({"pos": list[i].pos, "hex": list[i].hex, "from": list[i].from})
            return JSON.stringify(out)
        }
        function tagged() {
            var out = []
            for (var i = 0; i < nodes.length; ++i) out.push({"pos": nodes[i].pos, "hex": nodes[i].hex, "from": i})
            return out
        }
        spacing: 6
        Row {
            spacing: 8
            RowLabel { text: row.label; icon: row.icon || ""; tip: row.tooltip; propId: row.id; height: 22; width: 118 }
            Text { anchors.verticalCenter: parent.verticalCenter; text: gr.shown.length + " / " + Math.round(row.max) + " nodes"
                   color: shell.cDim; font.pixelSize: shell.fontBase - 2 }
        }
        Item {
            id: strip
            width: gr.width; height: 34
            Canvas {
                id: stripCanvas
                anchors.fill: parent
                anchors.topMargin: 4; anchors.bottomMargin: 8
                onPaint: {
                    var ctx = getContext("2d"); ctx.reset()
                    var list = gr.shown
                    if (!list.length) return
                    var g = ctx.createLinearGradient(0, 0, width, 0)
                    for (var i = 0; i < list.length; ++i) g.addColorStop(Math.max(0, Math.min(1, list[i].pos)), list[i].hex)
                    ctx.fillStyle = g
                    ctx.fillRect(0, 0, width, height)
                    ctx.strokeStyle = shell.cOutline; ctx.lineWidth = 1; ctx.strokeRect(0.5, 0.5, width - 1, height - 1)
                }
                Connections { target: gr; function onShownChanged() { stripCanvas.requestPaint() } }
                Component.onCompleted: requestPaint()
            }
            MouseArea {
                anchors.fill: parent
                onDoubleClicked: function(m) {
                    if (gr.nodes.length >= row.max) return
                    var list = gr.tagged(), pos = m.x / width, hex = list.length ? list[0].hex : "#808080"
                    for (var i = 0; i < list.length; ++i) if (list[i].pos <= pos) hex = list[i].hex
                    list.push({"pos": pos, "hex": hex, "from": -1})
                    list.sort(function(a, b) { return a.pos - b.pos })
                    studio.commitGradient(row.id, gr.payload(list))
                }
            }
            Repeater {
                model: gr.shown
                delegate: Rectangle {
                    id: node
                    x: modelData.pos * (strip.width - 14)
                    y: 0
                    width: 14; height: 30; radius: 3
                    color: modelData.hex
                    border.width: gr.selected === index ? 3 : 1.5
                    border.color: gr.selected === index ? shell.cFocus : "white"
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Slider
                    Accessible.name: row.label + " node " + (index + 1)
                    MouseArea {
                        anchors.fill: parent
                        anchors.margins: -4
                        cursorShape: Qt.SizeHorCursor
                        preventStealing: true
                        property real startX: 0
                        property bool moved: false
                        onPressed: function(m) { gr.selected = index; startX = node.x; moved = false
                                                 gr.working = gr.tagged(); node.forceActiveFocus() }
                        onPositionChanged: function(m) {
                            if (!pressed) return
                            var list = gr.tagged()
                            var p = Math.max(0, Math.min(1, (node.x + m.x - 7) / (strip.width - 14)))
                            var lo = index > 0 ? list[index - 1].pos + 0.001 : 0
                            var hi = index < list.length - 1 ? list[index + 1].pos - 0.001 : 1
                            list[index].pos = Math.max(lo, Math.min(hi, p))
                            moved = true
                            gr.working = list
                            studio.previewGradient(row.id, gr.payload(list))
                        }
                        onReleased: {
                            if (moved) studio.commitGradient(row.id, gr.payload(gr.working))
                            gr.working = null
                        }
                    }
                    Keys.onDeletePressed: if (gr.nodes.length > row.min) {
                        var list = gr.tagged(); list.splice(index, 1); gr.selected = -1
                        studio.commitGradient(row.id, gr.payload(list))
                    }
                    FocusRing { visible: node.activeFocus }
                }
            }
        }
        HintText {
            visible: gr.selected < 0
            text: "Click a node to colour it · drag to move · double-click the strip to add"
            width: gr.width
        }
        Column {
            visible: gr.selected >= 0 && gr.selected < gr.nodes.length
            spacing: 6
            ColourPicker {
                width: gr.width
                hex: gr.selected >= 0 && gr.selected < gr.nodes.length ? gr.nodes[gr.selected].hex : "#808080"
                onChanged: function(h) {
                    var list = gr.tagged(); list[gr.selected].hex = h; gr.working = list
                    studio.previewGradient(row.id, gr.payload(list))
                }
                onPicked: function(h) {
                    var list = gr.tagged(); list[gr.selected].hex = h; gr.working = null
                    studio.commitGradient(row.id, gr.payload(list))
                }
            }
            Row {
                spacing: 8
                StudioButton { text: "Remove Node"; icon: "minus"; iconSize: 14; enabledState: gr.nodes.length > row.min
                               tip: "Remove this node (Delete)"
                               onClicked: { var list = gr.tagged(); list.splice(gr.selected, 1); gr.selected = -1
                                            studio.commitGradient(row.id, gr.payload(list)) } }
                StudioButton { text: "Done"; onClicked: gr.selected = -1 }
            }
        }
    }

    // Reversible starting points for a group (e.g. materials): one tile = one undoable edit.
    component PresetTiles: Flow {
        id: tiles
        property var presets: []
        property string group: ""
        // Tiles keep the preview's 3:2 shape: at most three per row in a narrow inspector.
        readonly property int perRow: Math.max(1, Math.min(tiles.presets.length, Math.floor((tiles.width + spacing) / 96)))
        spacing: 8
        Repeater {
            model: tiles.presets
            delegate: Rectangle {
                id: tile
                readonly property bool active: studio.activePresets[tiles.group] === modelData.id
                width: Math.floor((tiles.width - tiles.spacing * (tiles.perRow - 1)) / tiles.perRow)
                height: swatch.height + 32; radius: 6
                color: tileMouse.containsMouse ? shell.cRaised : shell.cPanel
                border.width: active ? shell.cardBorder + 1 : shell.cardBorder
                border.color: active ? shell.cAccent : shell.cOutlineSoft
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: modelData.label
                Rectangle {
                    id: swatch
                    x: 6; y: 6; width: parent.width - 12; height: Math.round(width / 1.5); radius: 4
                    clip: true
                    readonly property string preview: studio.presetPreviews[tiles.group + "/" + modelData.id] || ""
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: modelData.swatch[0] || shell.cTrack }
                        GradientStop { position: 1; color: modelData.swatch[1] || shell.cTrack }
                    }
                    Rectangle { anchors.fill: parent; radius: 4; visible: swatch.preview === ""
                                gradient: Gradient { GradientStop { position: 0; color: "#55ffffff" }
                                                     GradientStop { position: .5; color: "#00ffffff" } } }
                    Image {          // the mode's own renderer, drawn once per starting point (cached)
                        objectName: "presetPreview"
                        anchors.fill: parent
                        visible: swatch.preview !== ""
                        source: swatch.preview
                        fillMode: Image.PreserveAspectCrop
                        smooth: true; mipmap: true
                    }
                    Canvas {         // soft vignette over the render (theme base colour), like the mock's tiles
                        anchors.fill: parent
                        visible: swatch.preview !== ""
                        onPaint: {
                            var ctx = getContext("2d"); ctx.reset()
                            var g = ctx.createRadialGradient(width / 2, height / 2, Math.min(width, height) * 0.3,
                                                             width / 2, height / 2, Math.max(width, height) * 0.72)
                            g.addColorStop(0, Qt.rgba(shell.cBg.r, shell.cBg.g, shell.cBg.b, 0))
                            g.addColorStop(1, Qt.rgba(shell.cBg.r, shell.cBg.g, shell.cBg.b, 0.78))
                            ctx.fillStyle = g; ctx.fillRect(0, 0, width, height)
                            var top = ctx.createLinearGradient(0, 0, 0, height)
                            top.addColorStop(0, shell.accentA(0.10)); top.addColorStop(0.5, shell.accentA(0))
                            ctx.fillStyle = top; ctx.fillRect(0, 0, width, height)
                        }
                    }
                }
                SelectionGlow { visible: tile.active; spread: 3 }
                Text { anchors.horizontalCenter: parent.horizontalCenter; y: swatch.height + 10; text: modelData.label
                       color: shell.cText; font.pixelSize: shell.fontBase - 2; font.bold: tile.active }
                MouseArea { id: tileMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: studio.applyPreset(tiles.group, modelData.id) }
                Keys.onSpacePressed: studio.applyPreset(tiles.group, modelData.id)
                FocusRing { visible: tile.activeFocus }
                C.ToolTip.visible: tileMouse.containsMouse
                C.ToolTip.text: modelData.description + "\nApplies to the real values as one edit; Undo reverts it."
                C.ToolTip.delay: 400
            }
        }
    }

    // Birth -> sustain -> tip fade over a real lifetime (quiet or peak endpoint), with draggable boundaries.
    component LifecycleTimeline: Column {
        id: life
        property var spec: ({})
        property int endpoint: 0
        readonly property var total: studio.values[spec.total ? spec.total.id : ""] || [0, 0]
        readonly property var fade: spec.fade && spec.fade.id ? (studio.values[spec.fade.id] || [0, 0]) : null
        readonly property var peel: spec.peel && spec.peel.id ? (studio.values[spec.peel.id] || [0, 0]) : null
        readonly property real maxT: spec.total ? spec.total.max : 1
        readonly property real t: total[endpoint]
        readonly property real f: fade ? fade[endpoint] : 0
        readonly property real pl: peel ? Math.min(peel[endpoint], t) : 0
        spacing: 4
        Row {
            spacing: 8
            Text { text: life.spec.label || "Lifetime"; color: shell.cText; font.pixelSize: shell.fontBase - 1; font.bold: true
                   anchors.verticalCenter: parent.verticalCenter }
            Repeater {
                model: ["Quiet", "Peak"]
                delegate: Chip { text: modelData; selected: life.endpoint === index; onPicked: life.endpoint = index }
            }
            HintText { anchors.verticalCenter: parent.verticalCenter; font.pixelSize: shell.fontBase - 2
                       width: Math.max(40, life.width - x)
                       text: life.t.toFixed(2) + " s" + (life.fade ? " · fade " + Math.round(life.f * 100) + "%" : "")
                             + (life.peel ? " · peel " + life.pl.toFixed(2) + " s" : "") }
        }
        Item {
            id: lane
            objectName: "lifecycleLane"
            width: life.width; height: life.peel !== null ? 62 : 44
            property bool dragging: false
            property real frozenScale: 1
            // Axis: a little past the longest lifetime/peel of either endpoint; frozen while dragging so the
            // grip stays under the pointer.
            readonly property real liveScale: 1.25 * Math.max(0.1, life.total[0], life.total[1],
                                                              life.peel ? life.peel[0] : 0, life.peel ? life.peel[1] : 0)
            readonly property real scaleT: dragging ? frozenScale : liveScale
            readonly property real fadeStart: life.t * (1 - life.f)
            function px(seconds) { return 8 + (width - 16) * Math.max(0, Math.min(1, seconds / scaleT)) }
            // Lifetime lane: sustain then tip fade
            Rectangle { x: 8; y: 8; width: lane.width - 16; height: 10; radius: 5; color: shell.cTrack }
            Rectangle { x: lane.px(0); y: 8; width: Math.max(0, lane.px(lane.fadeStart) - lane.px(0)); height: 10; radius: 5
                        color: shell.cAccent }
            Rectangle { x: lane.px(lane.fadeStart); y: 8; width: Math.max(0, lane.px(life.t) - lane.px(lane.fadeStart)); height: 10
                        gradient: Gradient { orientation: Gradient.Horizontal
                                             GradientStop { position: 0; color: shell.cAccent }
                                             GradientStop { position: 1; color: "transparent" } } }
            Text { readonly property real room: lane.px(lane.fadeStart) - lane.px(0)
                   visible: room > implicitWidth + 6
                   x: lane.px(0) + (room - implicitWidth) / 2; y: 20; text: "sustain"; color: shell.cDim; font.pixelSize: shell.fontBase - 3 }
            Text { readonly property real room: lane.px(life.t) - lane.px(lane.fadeStart)
                   visible: life.fade !== null && room > implicitWidth + 6
                   x: lane.px(lane.fadeStart) + (room - implicitWidth) / 2; y: 20; text: "tip fade"; color: shell.cDim
                   font.pixelSize: shell.fontBase - 3 }
            Rectangle {     // the other endpoint's lifetime, for reference
                x: lane.px(life.total[1 - life.endpoint]) - 1; y: 4; width: 2; height: 18; radius: 1
                color: shell.cDim; opacity: .7
            }
            // Peel lane: how long a strand takes to detach (runs alongside the lifetime)
            Rectangle { visible: life.peel !== null; x: 8; y: 38; width: lane.width - 16; height: 6; radius: 3; color: shell.cTrack }
            Rectangle { visible: life.peel !== null; x: lane.px(0); y: 38; width: Math.max(0, lane.px(life.pl) - lane.px(0)); height: 6
                        radius: 3; color: shell.cTrace3 }
            Text { visible: life.peel !== null; x: Math.min(lane.width - implicitWidth, lane.px(life.pl) + 10); y: 34
                   text: "peel"; color: shell.cDim; font.pixelSize: shell.fontBase - 3 }
            Text { x: 8; y: lane.height - 12; text: "0 s"; color: shell.cDim; font.pixelSize: shell.fontBase - 4 }
            Text { x: lane.width - 8 - implicitWidth; y: lane.height - 12; text: lane.scaleT.toFixed(1) + " s"; color: shell.cDim
                   font.pixelSize: shell.fontBase - 4 }
            // Drag grips: lifetime end, fade start, peel
            Repeater {
                model: [{"key": "total", "show": true, "y": 3}, {"key": "fade", "show": life.fade !== null, "y": 3},
                        {"key": "peel", "show": life.peel !== null, "y": 33}]
                delegate: Rectangle {
                    id: grip
                    objectName: "lifecycleGrip"
                    property string key: modelData.key
                    visible: modelData.show
                    readonly property real at: modelData.key === "total" ? lane.px(life.t)
                                               : modelData.key === "fade" ? lane.px(lane.fadeStart) : lane.px(life.pl)
                    readonly property var prop: modelData.key === "total" ? life.spec.total
                                                : modelData.key === "fade" ? life.spec.fade : life.spec.peel
                    x: at - 5; y: modelData.y; width: 10; height: modelData.key === "peel" ? 16 : 20; radius: 3
                    color: gripMouse.pressed ? shell.cAccent : shell.cText; border.width: 1; border.color: shell.cOutline
                    function valueAt(x) {
                        var seconds = (x - 8) / Math.max(1, lane.width - 16) * lane.scaleT
                        if (modelData.key === "fade") return Math.max(0, Math.min(1, 1 - seconds / Math.max(1e-6, life.t)))
                        return seconds
                    }
                    MouseArea {
                        id: gripMouse
                        anchors.fill: parent; anchors.margins: -5
                        hoverEnabled: true
                        preventStealing: true
                        cursorShape: Qt.SizeHorCursor
                        onPressed: { lane.frozenScale = lane.liveScale; lane.dragging = true
                                     studio.beginEdit(grip.prop.id, grip.prop.label) }
                        onPositionChanged: function(m) {
                            if (pressed) studio.previewValue(grip.prop.id, life.endpoint, grip.valueAt(grip.x + m.x))
                        }
                        onReleased: { lane.dragging = false; studio.endEdit() }
                    }
                    C.ToolTip.visible: gripMouse.containsMouse && !gripMouse.pressed
                    C.ToolTip.text: (grip.prop ? grip.prop.label : "") + " (" + (life.endpoint ? "Peak" : "Quiet") + ") — drag"
                    C.ToolTip.delay: 500
                }
            }
        }
    }

    // Schematic diagrams of real values above a group (never a render).
    component SchematicCard: Rectangle {
        id: card
        property var spec: ({})
        function v(role, idx) {
            var id = spec.roles ? spec.roles[role] : undefined
            var x = id !== undefined ? studio.values[id] : undefined
            if (x === undefined) return 0
            if (typeof x === "object" && x !== null && x.length !== undefined) return Number(x[idx === undefined ? card.endpoint : idx])
            return x
        }
        function paletteRgb(t) {
            var id = spec.roles ? spec.roles["palette"] : undefined
            var nodes = id ? studio.values[id] : undefined
            if (!nodes || nodes.length === undefined || nodes.length === 0) return shell.hexToRgb(shell.cAccent.toString())
            var lo = nodes[0], hi = nodes[nodes.length - 1]
            for (var i = 0; i < nodes.length; ++i) {
                if (nodes[i].pos <= t) lo = nodes[i]
                if (nodes[i].pos >= t) { hi = nodes[i]; break }
            }
            var a = shell.hexToRgb(lo.hex), b = shell.hexToRgb(hi.hex)
            var f = hi.pos > lo.pos ? (t - lo.pos) / (hi.pos - lo.pos) : 0
            return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f]
        }
        function paletteAt(t, alpha) { var c = paletteRgb(t); return Qt.rgba(c[0], c[1], c[2], alpha) }
        function mixWhite(c, k) { k = Math.max(0, Math.min(1, k)); return [c[0] + (1 - c[0]) * k, c[1] + (1 - c[1]) * k, c[2] + (1 - c[2]) * k] }
        function caption(roles) {
            var out = []
            for (var i = 0; i < roles.length; ++i) {
                var label = spec.labels ? spec.labels[roles[i]] : roles[i]
                var x = card.v(roles[i])
                out.push((label || roles[i]).toLowerCase() + " " + (Math.abs(x) < 0.1 ? x.toFixed(3) : x.toFixed(2)))
            }
            return out.join(" · ")
        }
        function hex(role) { var id = spec.roles ? spec.roles[role] : undefined; return id ? (studio.values[id] || "#808080") : "#808080" }
        // A rendered card (the mode's renderer, once per commit) replaces the diagram once it arrives.
        readonly property string render: card.spec.rendered ? (studio.previews["card/" + card.spec.group] || "") : ""
        readonly property int endpoint: card.spec.rendered ? (studio.cardEndpoints[card.spec.group] || 0) : 1
        implicitHeight: card.spec.rendered ? Math.round(cardImage.height) + 52 : 128
        radius: 6
        color: shell.cViewport
        border.width: shell.cardBorder; border.color: shell.cOutlineSoft
        Text { x: 8; y: 6; text: card.spec.title || ""; color: shell.cDim; font.pixelSize: shell.fontBase - 2 }
        Row {
            visible: card.spec.rendered === true
            anchors.right: parent.right; anchors.rightMargin: 6; y: 3
            spacing: 4
            Repeater {
                model: ["Quiet", "Peak"]
                delegate: Chip { text: modelData; selected: card.endpoint === index; implicitHeight: 20
                                 onPicked: studio.setCardEndpoint(card.spec.group, index) }
            }
        }
        Image {
            id: cardImage
            objectName: "cardRender"
            visible: card.render !== ""
            x: 6; y: 28; width: card.width - 12
            // The render keeps its own shape (no crop of the crop): height follows the image's aspect.
            height: implicitWidth > 0 ? width * implicitHeight / implicitWidth : Math.round(width * 0.42)
            source: card.render
            fillMode: Image.PreserveAspectFit
            smooth: true; mipmap: true
        }
        HintText {
            visible: card.render !== ""
            x: 8; anchors.bottom: parent.bottom; anchors.bottomMargin: 4; width: parent.width - 16
            text: (card.endpoint ? "Peak" : "Quiet") + " lane · rendered by the visualizer · "
                  + (card.spec.kind === "falloff" ? card.caption(["density", "height", "clearance"])
                     : card.spec.kind === "reflection" ? card.caption(["brightness", "reflection"])
                     : card.caption(Object.keys(card.spec.roles || {})))     // a render-only card: its own roles
        }
        Canvas {
            id: diagram
            visible: card.render === ""
            anchors.fill: parent; anchors.margins: 8; anchors.topMargin: 22
            onPaint: {
                var ctx = getContext("2d"); ctx.reset()
                var w = width, h = height
                if (card.spec.kind === "falloff") {
                    var on = card.v("enabled") !== false
                    var density = card.v("density", 1), height_ = Math.max(0.1, card.v("height", 1))
                    var clear = card.v("clearance", 1), soft = Math.max(0.1, card.v("softness", 1))
                    var floorY = h - 12, ry = floorY * 0.42
                    var bg = ctx.createLinearGradient(0, 0, 0, floorY)
                    bg.addColorStop(0, "#04050a"); bg.addColorStop(1, "#0b0d18")
                    ctx.fillStyle = bg; ctx.fillRect(0, 0, w, floorY)
                    if (on) {
                        // Soft volume: deterministic puffs, denser near the ground (ground diffusion = how high
                        // it reaches), parted around the subject line by the displacement role.
                        var tone = [0.55 + 0.25 * shell.cAccent.r, 0.55 + 0.2 * shell.cAccent.g, 0.75 + 0.2 * shell.cAccent.b]
                        var seed = 7
                        function rnd() { seed = (seed * 16807) % 2147483647; return seed / 2147483647 }
                        for (var i = 0; i < 46; ++i) {
                            var px = rnd() * w, alt = Math.pow(rnd(), 1.6) * 4.0
                            var py = floorY - alt / 4.0 * floorY
                            var r = (14 + rnd() * 26) * (0.6 + 0.4 * soft)
                            var a = Math.min(0.55, density * 6 * Math.exp(-alt / height_))
                            var parted = Math.abs(py - (ry + Math.sin(px / w * 9.42) * 8))
                            a *= Math.min(1, parted / (6 + clear * 26))
                            var rg = ctx.createRadialGradient(px, py, 0, px, py, r)
                            rg.addColorStop(0, Qt.rgba(tone[0], tone[1], tone[2], a))
                            rg.addColorStop(1, Qt.rgba(tone[0], tone[1], tone[2], 0))
                            ctx.fillStyle = rg; ctx.fillRect(px - r, py - r, 2 * r, 2 * r)
                        }
                    }
                    ctx.strokeStyle = shell.cAccent; ctx.lineWidth = 2; ctx.beginPath()
                    for (var x = 0; x <= w; x += 4) { var yy = ry + Math.sin(x / w * 9.42) * 8; if (x === 0) ctx.moveTo(x, yy); else ctx.lineTo(x, yy) }
                    ctx.stroke()
                    ctx.fillStyle = "#1a1c24"; ctx.fillRect(0, floorY, w, h - floorY)
                    ctx.fillStyle = shell.cDim; ctx.font = "10px sans-serif"
                    ctx.fillText(on ? card.caption(["density", "height", "clearance"]) : "atmosphere off", 4, h - 1)
                } else if (card.spec.kind === "reflection") {
                    var tint = shell.hexToRgb(card.hex("tint")), b = card.v("brightness", 1) / 3
                    var refl = Math.min(1, card.v("reflection", 1) / 8), wet = card.v("wetness", 1), streak = card.v("streak", 1)
                    var horizon = h * 0.35
                    var lum = Math.min(1, card.v("brightness", 1) / 6) * 0.35
                    var floorGrad = ctx.createLinearGradient(0, horizon, 0, h)
                    floorGrad.addColorStop(0, Qt.rgba(tint[0] * lum, tint[1] * lum, tint[2] * lum, 1))
                    floorGrad.addColorStop(1, Qt.rgba(tint[0] * lum * 0.3, tint[1] * lum * 0.3, tint[2] * lum * 0.3, 1))
                    ctx.fillStyle = floorGrad; ctx.fillRect(0, horizon, w, h - horizon)
                    var cols = [0.15, 0.32, 0.5, 0.68, 0.85]
                    for (var i = 0; i < cols.length; ++i) {
                        var gx = cols[i] * w, len = (h - horizon) * (0.25 + 0.75 * streak)
                        var gg = ctx.createLinearGradient(0, horizon, 0, horizon + len)
                        gg.addColorStop(0, Qt.rgba(shell.cAccent.r, shell.cAccent.g, shell.cAccent.b, 0.25 + 0.6 * refl)); gg.addColorStop(1, "rgba(0,0,0,0)")
                        ctx.fillStyle = gg; ctx.fillRect(gx - 4 - wet * 4, horizon, 8 + wet * 8, len)
                    }
                    ctx.strokeStyle = shell.cAccent; ctx.lineWidth = 2; ctx.beginPath()
                    for (var x2 = 0; x2 <= w; x2 += 4) { var y2 = horizon - 14 + Math.sin(x2 / w * 9) * 8; if (x2 === 0) ctx.moveTo(x2, y2); else ctx.lineTo(x2, y2) }
                    ctx.stroke()
                    ctx.fillStyle = shell.cDim; ctx.font = "10px sans-serif"
                    ctx.fillText(card.caption(["brightness", "reflection", "streak"]), 4, h - 1)
                } else if (card.spec.kind === "particles" || card.spec.kind === "strands") {
                    var floorP = h - 12
                    var back = ctx.createLinearGradient(0, 0, 0, floorP)
                    back.addColorStop(0, "#03040a"); back.addColorStop(1, "#0a0c16")
                    ctx.fillStyle = back; ctx.fillRect(0, 0, w, floorP)
                    function waveY(x) { return floorP * 0.66 + Math.sin(x / w * 9.42) * floorP * 0.12 }
                    // the carrier the emitters sit on, in the palette's own colours
                    ctx.lineWidth = 2
                    for (var xw = 0; xw < w; xw += 3) {
                        ctx.strokeStyle = card.paletteAt(xw / w, 0.55)
                        ctx.beginPath(); ctx.moveTo(xw, waveY(xw)); ctx.lineTo(xw + 3, waveY(xw + 3)); ctx.stroke()
                    }
                    var seedP = 11
                    function rndP() { seedP = (seedP * 16807) % 2147483647; return seedP / 2147483647 }
                    if (card.v("enabled") !== false && card.spec.kind === "particles") {
                        var n = Math.min(160, Math.round(card.v("count") * 2.5))
                        var lifeP = Math.max(0.2, card.v("lifetime")), drift = card.v("drift"), rise = card.v("rise")
                        var size = card.v("size"), glowP = card.v("glow"), whiteP = card.v("white")
                        var spanF = Math.max(0.1, Math.min(1, card.v("span") / 128))
                        for (var k = 0; k < n; ++k) {
                            var ex = w * (0.5 + (rndP() - 0.5) * spanF), age = rndP(), tt = age * lifeP
                            var ppx = ex + (rndP() - 0.5) * 2 * drift * tt * 6
                            var ppy = waveY(ex) - rise * tt * 14 - rndP() * 4
                            var fade = Math.pow(1 - age, 1.5)
                            var rad = 0.6 + size * 0.3
                            var col = card.mixWhite(card.paletteRgb(ex / w), whiteP)
                            var halo = ctx.createRadialGradient(ppx, ppy, 0, ppx, ppy, rad * (2 + glowP * 3))
                            halo.addColorStop(0, Qt.rgba(col[0], col[1], col[2], 0.35 * fade))
                            halo.addColorStop(1, Qt.rgba(col[0], col[1], col[2], 0))
                            ctx.fillStyle = halo
                            ctx.fillRect(ppx - rad * 5 - glowP * 3 * rad, ppy - rad * 5 - glowP * 3 * rad,
                                         2 * (rad * 5 + glowP * 3 * rad), 2 * (rad * 5 + glowP * 3 * rad))
                            ctx.fillStyle = Qt.rgba(col[0], col[1], col[2], fade)
                            ctx.beginPath(); ctx.arc(ppx, ppy, rad, 0, 6.283); ctx.fill()
                        }
                    } else if (card.v("enabled") !== false) {
                        var strands = Math.max(1, Math.round(card.v("count") * 3))
                        var len = card.v("length"), reach = card.v("reach"), widthS = card.v("width")
                        var beads = Math.round(card.v("beads")), glowS = card.v("glow")
                        for (var j = 0; j < strands; ++j) {
                            var sx = w * (0.12 + 0.76 * (j + 0.5) / strands), sy = waveY(sx)
                            var tall = floorP * Math.min(0.62, 0.05 * len) * (0.7 + 0.3 * rndP())
                            var side = (rndP() - 0.5) * reach * w * 0.06
                            var colS = card.paletteRgb(sx / w)
                            ctx.save()
                            ctx.shadowColor = Qt.rgba(colS[0], colS[1], colS[2], 0.8)
                            ctx.shadowBlur = 2 + glowS * 4
                            ctx.strokeStyle = Qt.rgba(colS[0], colS[1], colS[2], 0.9)
                            ctx.lineWidth = Math.max(0.6, widthS * 1.1)
                            ctx.beginPath(); ctx.moveTo(sx, sy)
                            ctx.bezierCurveTo(sx + side * 0.2, sy - tall * 0.4, sx + side, sy - tall * 0.7, sx + side * 1.4, sy - tall)
                            ctx.stroke()
                            ctx.restore()
                            for (var b2 = 1; b2 <= beads; ++b2) {
                                var f2 = b2 / (beads + 1)
                                var bx = sx + side * 1.4 * f2 * f2, by = sy - tall * f2
                                ctx.fillStyle = Qt.rgba(1, 1, 1, 0.85)
                                ctx.beginPath(); ctx.arc(bx, by, 1.2 + widthS * 0.4, 0, 6.283); ctx.fill()
                            }
                        }
                    }
                    ctx.fillStyle = "#1a1c24"; ctx.fillRect(0, floorP, w, h - floorP)
                    ctx.fillStyle = shell.cDim; ctx.font = "10px sans-serif"
                    ctx.fillText(card.v("enabled") === false ? "off"
                                 : card.caption(card.spec.kind === "particles" ? ["count", "lifetime", "size"]
                                                                              : ["count", "length", "reach"]), 4, h - 1)
                } else if (card.spec.kind === "exposure") {
                    var e = card.v("exposure"), bq = card.v("bloom", 0), bp = card.v("bloom", 1)
                    ctx.strokeStyle = shell.cOutlineSoft; ctx.strokeRect(0.5, 0.5, w - 1, h - 12)
                    ctx.strokeStyle = shell.cAccent; ctx.lineWidth = 2; ctx.beginPath()
                    var clipped = false
                    for (var i2 = 0; i2 <= 60; ++i2) {
                        var xi = i2 / 60, out = 1 - Math.exp(-xi * 2.2 * e)
                        if (out > 0.97) clipped = true
                        var px = xi * w, py = (h - 12) * (1 - Math.min(1, out))
                        if (i2 === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py)
                    }
                    ctx.stroke()
                    ctx.fillStyle = Qt.rgba(1, 1, 1, 0.08 + 0.4 * bp); ctx.beginPath(); ctx.arc(w * 0.82, (h - 12) * 0.3, 6 + bp * 20, 0, 6.283); ctx.fill()
                    ctx.fillStyle = clipped ? shell.cDanger : shell.cDim; ctx.font = "10px sans-serif"
                    ctx.fillText("exposure " + e.toFixed(2) + " · bloom " + bq.toFixed(2) + "→" + bp.toFixed(2)
                                 + (clipped ? " · highlights clip" : ""), 4, h - 1)
                }
            }
            Connections { target: studio; function onValuesChanged() { diagram.requestPaint() } }
            Component.onCompleted: requestPaint()
        }
        Accessible.name: (spec.title || "") + " schematic"
    }

    // A dashboard panel's title bar (mock): accent icon, title, a dim subtitle after a dash.
    component PanelHeader: Item {
        property string icon: ""
        property string title: ""
        property string subtitle: ""
        width: parent ? parent.width : 0
        height: 40
        Row {
            x: 14; anchors.verticalCenter: parent.verticalCenter
            spacing: 10
            StudioIcon { name: parent.parent.icon; visible: parent.parent.icon !== ""; width: 20; height: 20
                         color: shell.cAccent; anchors.verticalCenter: parent.verticalCenter }
            Text { id: headerTitle; text: parent.parent.title; color: shell.cText; font.pixelSize: shell.fontBase + 2
                   font.bold: true; anchors.verticalCenter: parent.verticalCenter
                   width: Math.min(implicitWidth, parent.parent.width - 60); elide: Text.ElideRight }
            Text { visible: parent.parent.subtitle !== ""; text: "–  " + parent.parent.subtitle; color: shell.cDim
                   font.pixelSize: shell.fontBase + 1; anchors.verticalCenter: parent.verticalCenter
                   width: Math.max(0, Math.min(implicitWidth, parent.parent.width - headerTitle.width - 70))
                   elide: Text.ElideRight }
        }
        Rectangle { anchors.bottom: parent.bottom; x: 1; width: parent.width - 2; height: 1; color: shell.cOutlineSoft }
    }

    // One collapsible inspector group: header, live traces, card, starting-point tiles, lifetime and rows.
    component InspectorGroup: Column {
        id: group
        objectName: "inspectorGroup"
        property var groupData: ({})
        property bool open: groupData.open === true
        spacing: 6
        Rectangle {
            width: parent.width; height: 30; radius: 6
            color: groupMouse.containsMouse ? shell.cRaised : shell.accentA(0.05)
            border.width: shell.cardBorder; border.color: shell.cOutlineSoft
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: group.groupData.title || ""
            Row {
                x: 8; anchors.verticalCenter: parent.verticalCenter
                spacing: 8
                StudioIcon { name: group.open ? "chevron-down" : "chevron-right"; color: shell.cDim
                             width: 14; height: 14; anchors.verticalCenter: parent.verticalCenter }
                StudioIcon { name: group.groupData.icon || ""; visible: (group.groupData.icon || "") !== ""
                             color: shell.cAccent; width: 16; height: 16; anchors.verticalCenter: parent.verticalCenter }
                Text { text: group.groupData.title || ""; color: shell.cText; font.pixelSize: shell.fontBase
                       font.bold: true; anchors.verticalCenter: parent.verticalCenter }
            }
            MouseArea { id: groupMouse; anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor; onClicked: group.open = !group.open }
            Row {               // a per-object group steps through the scene objects (mock: "Ribbon 1  < >")
                objectName: "objectStepper"
                visible: group.groupData.objectScoped === true && studio.objects.length > 1
                anchors.right: parent.right; anchors.rightMargin: 4; anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                StudioButton { objectName: "previousObject"; icon: "chevron-left"; iconSize: 14; width: 24; height: 22
                               tip: "Previous " + (studio.objectNoun || "object"); onClicked: studio.stepObject(-1) }
                StudioButton { objectName: "nextObject"; icon: "chevron-right"; iconSize: 14; width: 24; height: 22
                               tip: "Next " + (studio.objectNoun || "object"); onClicked: studio.stepObject(1) }
            }
            Keys.onSpacePressed: group.open = !group.open
            FocusRing { visible: parent.activeFocus }
        }
        SignalTrace {
            visible: group.open && (group.groupData.traces || []).length > 0
            width: parent.width
            channels: group.groupData.traces || []
        }
        SchematicCard {
            visible: group.open && group.groupData.card !== undefined && group.groupData.card.kind !== undefined
            width: parent.width
            height: visible ? implicitHeight : 0
            spec: group.groupData.card || ({})
        }
        PresetTiles {
            visible: group.open && (group.groupData.presets || []).length > 0
            width: parent.width
            presets: group.groupData.presets || []
            group: group.groupData.group || ""
        }
        LifecycleTimeline {
            visible: group.open && group.groupData.lifecycle !== undefined && group.groupData.lifecycle.total !== undefined
            width: parent.width
            spec: group.groupData.lifecycle || ({})
        }
        Column {
            visible: group.open
            width: parent.width
            spacing: 4
            Repeater {
                model: group.groupData.rows || []
                delegate: Loader {
                    objectName: "inspectorRow"
                    width: parent.width
                    // A row whose Settings condition does not hold is hidden, as in Settings.
                    visible: studio.conditionHidden[modelData.id] !== true
                    height: visible && item ? item.implicitHeight || item.height : 0
                    property var rowData: modelData
                    sourceComponent: {
                        switch (modelData.instrument) {
                        case "quiet_peak": return quietPeakDelegate
                        case "switch": return switchDelegate
                        case "choice": return choiceDelegate
                        case "count": return countDelegate
                        case "colour": return colourDelegate
                        case "gradient": return gradientDelegate
                        default: return scalarDelegate
                        }
                    }
                }
            }
        }
        Flow {              // structural edits of the group's list values (e.g. Add Node)
            visible: group.open && (group.groupData.actions || []).length > 0
            width: parent.width
            spacing: 6
            Repeater {
                model: group.groupData.actions || []
                delegate: StudioButton { objectName: "groupAction"; text: modelData.label; icon: modelData.icon
                                         iconSize: 14; height: 26; textSize: shell.fontBase - 1
                                         enabledState: modelData.enabled; tip: modelData.tooltip
                                         onClicked: studio.runAction(modelData.id) }
            }
        }
    }

    // ------------------------------------------------------------------- rows
    component ScalarRow: Row {
        id: scalarRow
        property var row
        readonly property var rowActions: row.actions || []
        spacing: 8
        height: 28
        RowLabel { text: row.label; icon: row.icon || ""; tip: row.tooltip; propId: row.id; height: parent.height }
        ValueSlider {
            id: scalarSlider
            width: parent.width - 118 - 72 - 16 - scalarRow.rowActions.length * 30
            anchors.verticalCenter: parent.verticalCenter
            propId: row.id; label: row.label; from: row.min; to: row.max; integer: row.integer
            releaseOnly: row.releaseOnly === true
            value: studio.values[row.id] !== undefined ? studio.values[row.id] : row.min
        }
        // While dragged the readout follows the slider at once (the scene follows at the next frame).
        NumberField { propId: row.id; anchors.verticalCenter: parent.verticalCenter
                      display: shell.fmt(scalarSlider.dragging ? scalarSlider.dragValue : studio.values[row.id],
                                         row.decimals, "") }
        Repeater {          // structural edits of this element (remove a node, reorder a lane)
            model: scalarRow.rowActions
            delegate: StudioButton { objectName: "rowAction"; icon: modelData.icon; iconSize: 14; width: 22
                                     height: 22; anchors.verticalCenter: parent.verticalCenter
                                     enabledState: modelData.enabled; tip: modelData.label
                                     + (modelData.tooltip !== "" ? "
" + modelData.tooltip : "")
                                     onClicked: studio.runAction(modelData.id) }
        }
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
            RowLabel { text: row.label; icon: row.icon || ""; tip: row.tooltip + (row.tooltip ? "\n" : "") + "Quiet: " + row.quietMeaning
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
                id: qpSlider
                width: qp.width - 126 - 72 - 16; anchors.verticalCenter: parent.verticalCenter
                propId: row.id; label: row.label + (qp.endpoint ? " (Peak)" : " (Quiet)")
                endpoint: qp.endpoint; from: row.min; to: row.max; integer: row.integer
                releaseOnly: row.releaseOnly === true
                value: qp.pair[qp.endpoint]; ghost: qp.pair[1 - qp.endpoint]
            }
            NumberField { propId: row.id; endpoint: qp.endpoint; anchors.verticalCenter: parent.verticalCenter
                          display: shell.fmt(qpSlider.dragging ? qpSlider.dragValue : qp.pair[qp.endpoint],
                                             row.decimals, "") }
        }
    }

    // An Item, not a Row: a Row positions every visible child in sequence and ignores their x, which pushed the click
    // area past the end of the text (the 6 Nov "Tilt Shift is unclickable": no switch row could be clicked).
    component SwitchRow: Item {
        id: switchRow
        property var row
        readonly property bool on: studio.values[row.id] === true
        implicitHeight: 20
        height: 20
        Rectangle {
            id: track
            objectName: "checkBox"
            anchors.verticalCenter: parent.verticalCenter
            width: 20; height: 20; radius: 5
            color: on ? shell.cAccent : "transparent"
            border.width: on ? 0 : 1.5; border.color: shell.cOutline
            activeFocusOnTab: true
            Accessible.role: Accessible.CheckBox
            Accessible.name: row.label
            Accessible.checked: on
            StudioIcon { anchors.centerIn: parent; visible: switchRow.on; name: "check"; width: 14; height: 14
                         stroke: 2.4; color: shell.cAccentText }
            Keys.onSpacePressed: studio.commitValue(row.id, 0, !on)
            FocusRing { visible: track.activeFocus; radius: 7 }
        }
        Text { x: 30; anchors.verticalCenter: parent.verticalCenter; text: row.label; color: shell.cText
               font.pixelSize: shell.fontBase - 1; width: switchRow.width - 30; elide: Text.ElideRight }
        MouseArea { objectName: "switchHit"; anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    onClicked: studio.commitValue(row.id, 0, !switchRow.on)
                    C.ToolTip.visible: containsMouse && row.tooltip !== ""
                    C.ToolTip.text: row.tooltip
                    C.ToolTip.delay: 600 }
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
        RowLabel { text: row.label; icon: row.icon || ""; tip: row.tooltip; propId: row.id; height: 20; width: choiceRow.width }
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
        RowLabel { text: row.label; icon: row.icon || ""; tip: row.tooltip; propId: row.id; height: parent.height }
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

    component ColourRow: Column {
        id: colourRow
        property var row
        property bool picking: false
        spacing: 4
        Row {
            spacing: 8
            height: 30
            RowLabel { text: row.label; icon: row.icon || ""; tip: row.tooltip; propId: row.id; height: parent.height }
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 40; height: 22; radius: 4
                color: studio.values[row.id] || "#000000"
                border.width: colourRow.picking ? 2 : 1; border.color: colourRow.picking ? shell.cFocus : shell.cOutline
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: row.label + " colour"
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: colourRow.picking = !colourRow.picking }
                Keys.onSpacePressed: colourRow.picking = !colourRow.picking
            }
            NumberField { implicitWidth: 84; propId: row.id; anchors.verticalCenter: parent.verticalCenter
                          display: studio.values[row.id] || "" }
        }
        ColourPicker {
            width: colourRow.width
            visible: colourRow.picking
            hex: studio.values[row.id] || "#808080"
            onChanged: function(h) { studio.previewColour(row.id, h) }
            onPicked: function(h) { studio.previewColour(row.id, h); studio.endEdit() }
        }
    }

    // ---------------------------------------------------------------- title bar
    // Settings' custom title bar (ui/settings_dialog.py CustomTitleBar): the window title and minimise / maximise /
    // close, on the theme's title bar roles. Dragging moves the window through the system (Windows snap and
    // Aero snap included); double-click maximises; the window edges resize it.
    Rectangle {
        id: titleBar
        objectName: "studioTitleBar"
        width: parent.width; height: 40
        color: shell.cTitlebar
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton
            onPressed: studio.startWindowMove()
            onDoubleClicked: studio.toggleMaximize()
        }
        Row {
            anchors.left: parent.left; anchors.leftMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10
            StudioIcon { name: "wave"; width: 24; height: 24; stroke: 2.2; color: shell.cAccent
                         anchors.verticalCenter: parent.verticalCenter }
            Text { objectName: "titleBarLabel"; text: "SRPSS STUDIO"; color: shell.cTitleText
                   font.family: "Jost"; font.pixelSize: 19; font.bold: true; font.letterSpacing: 0.5
                   anchors.verticalCenter: parent.verticalCenter }
        }
        Row {
            anchors.right: parent.right; anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10
            Repeater {
                model: [{"id": "minimize", "glyph": "−", "tip": "Minimise"},
                        {"id": "maximize", "glyph": shell.maximized ? "❐" : "□",
                         "tip": shell.maximized ? "Restore" : "Maximise"},
                        {"id": "close", "glyph": "×", "tip": "Close the Studio and return to Settings"}]
                delegate: Rectangle {
                    objectName: "titleBarButton"
                    property string action: modelData.id
                    width: 40; height: 30; radius: 4
                    color: buttonMouse.pressed ? (action === "close" ? shell.cCloseHover : shell.cTitlePressed)
                           : buttonMouse.containsMouse ? (action === "close" ? shell.cCloseHover : shell.cTitleHover)
                           : "transparent"
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.tip
                    Text { anchors.centerIn: parent; text: modelData.glyph; color: shell.cTitleText
                           font.pixelSize: action === "close" ? 18 : 16; font.bold: true }
                    MouseArea {
                        id: buttonMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            if (parent.action === "minimize") studio.minimizeWindow()
                            else if (parent.action === "maximize") studio.toggleMaximize()
                            else Qt.callLater(studio.requestCloseFrom, "title bar close")
                        }
                    }
                    C.ToolTip.visible: buttonMouse.containsMouse
                    C.ToolTip.text: modelData.tip
                    C.ToolTip.delay: 600
                }
            }
        }
    }

    // ------------------------------------------------------------------- layout
    Column {
        anchors.fill: parent
        anchors.topMargin: titleBar.height
        spacing: 0

        // Header ---------------------------------------------------------------------
        Rectangle {
            id: header
            color: shell.translucent ? shell.withAlpha(shell.cHeader, shell.panelAlpha) : shell.cHeader
            readonly property bool wrapped: modeHeader.width + presetActions.width + 44 > width
            width: parent.width; height: wrapped ? 96 : 56
            gradient: shell.translucent ? null : headerGradient
            Gradient {
                id: headerGradient
                GradientStop { position: 0.0; color: Qt.lighter(shell.cHeader, 1.3) }
                GradientStop { position: 1.0; color: shell.cHeader }
            }
            Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: shell.cOutlineSoft }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: shell.cOutlineSoft }
            Row {
                id: modeHeader
                anchors.left: parent.left; anchors.leftMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: header.wrapped ? -22 : 0
                spacing: 12
                Text { objectName: "studioTitle"; text: studio.title; color: shell.cText; font.pixelSize: 19
                       visible: studio.modes.length <= 1; anchors.verticalCenter: parent.verticalCenter }
                // Mode switcher: every registered Studio mode (one shell, one save path per mode).
                C.ComboBox {
                    id: modeBox
                    objectName: "studioModePicker"
                    visible: studio.modes.length > 1
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
                id: presetActions
                anchors.right: parent.right; anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: header.wrapped ? 22 : 0
                spacing: 8
                // Preset picker: opens a list of the mode's presets; only an explicit pick switches.
                Rectangle {
                    id: presetPill
                    objectName: "presetPill"
                    readonly property bool interactive: studio.presets.length > 0
                    height: 34
                    width: Math.min(presetText.implicitWidth + 52,
                                    Math.max(100, header.width - 28 - headerButtons.width - presetActions.spacing))
                    radius: 6
                    color: pillMouse.containsMouse && interactive ? Qt.lighter(shell.cRaised, 1.15) : shell.cRaised
                    border.width: presetMenu.opened ? 2 : 1
                    border.color: presetMenu.opened ? shell.cAccent : shell.cOutline
                    activeFocusOnTab: interactive
                    Accessible.role: Accessible.ComboBox
                    Accessible.name: "Preset: " + studio.presetLabel
                    Row {
                        anchors.centerIn: parent; spacing: 10
                        Text { id: presetText; text: studio.presetLabel; color: shell.cText; font.pixelSize: shell.fontBase + 1
                               width: Math.min(implicitWidth, presetPill.width - 52); elide: Text.ElideRight
                               anchors.verticalCenter: parent.verticalCenter }
                        StudioIcon { name: "chevron-down"; width: 14; height: 14; color: shell.cDim; visible: presetPill.interactive
                                     anchors.verticalCenter: parent.verticalCenter }
                    }
                    MouseArea { id: pillMouse; anchors.fill: parent; hoverEnabled: true
                                cursorShape: presetPill.interactive ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: if (presetPill.interactive) presetMenu.open() }
                    Keys.onSpacePressed: if (interactive) presetMenu.open()
                    Keys.onReturnPressed: if (interactive) presetMenu.open()
                    Keys.onDownPressed: if (interactive) presetMenu.open()
                    FocusRing { visible: presetPill.activeFocus }
                    C.ToolTip.visible: pillMouse.containsMouse && !presetMenu.opened
                    C.ToolTip.text: "Choose the preset to edit. Save writes the selected preset; unsaved edits are "
                                    + "settled before switching."
                    C.ToolTip.delay: 600
                    C.Popup {
                        id: presetMenu
                        objectName: "presetMenu"
                        y: presetPill.height + 6
                        x: presetPill.width - width
                        width: Math.max(presetPill.width, 280)
                        padding: 6
                        modal: false
                        focus: true
                        closePolicy: C.Popup.CloseOnEscape | C.Popup.CloseOnPressOutside
                        background: Rectangle { radius: 8; color: shell.cRaised; border.width: 1; border.color: shell.cOutline
                                                SelectionGlow { spread: 2 } }
                        onOpened: presetList.forceActiveFocus()
                        readonly property bool onCustom: {
                            for (var i = 0; i < studio.presets.length; ++i)
                                if (studio.presets[i].current) return studio.presets[i].custom
                            return true
                        }
                        contentItem: Column {
                          spacing: 4
                          ListView {
                            id: presetList
                            objectName: "presetList"
                            width: presetMenu.availableWidth
                            implicitHeight: Math.min(contentHeight, 420)
                            height: implicitHeight
                            clip: true
                            model: studio.presets
                            currentIndex: {
                                for (var i = 0; i < studio.presets.length; ++i) if (studio.presets[i].current) return i
                                return 0
                            }
                            keyNavigationEnabled: true
                            Keys.onReturnPressed: { presetMenu.close(); Qt.callLater(studio.selectPreset, studio.presets[currentIndex].index) }
                            Keys.onSpacePressed: { presetMenu.close(); Qt.callLater(studio.selectPreset, studio.presets[currentIndex].index) }
                            delegate: Rectangle {
                                objectName: "presetItem"
                                width: presetList.width; height: 32; radius: 6
                                color: ListView.isCurrentItem || itemMouse.containsMouse ? shell.cAccentSoft : "transparent"
                                Row {
                                    x: 8; anchors.verticalCenter: parent.verticalCenter; spacing: 10
                                    StudioIcon { name: "check"; width: 14; height: 14; color: shell.cAccent
                                                 opacity: modelData.current ? 1 : 0; anchors.verticalCenter: parent.verticalCenter }
                                    Text { text: modelData.label; color: shell.cText; font.pixelSize: shell.fontBase
                                           font.bold: modelData.current; anchors.verticalCenter: parent.verticalCenter }
                                }
                                MouseArea { id: itemMouse; anchors.fill: parent; hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: { presetMenu.close(); Qt.callLater(studio.selectPreset, modelData.index) } }
                            }
                          }
                          // The rest of Settings' preset row: the same actions, offered where they apply.
                          Rectangle { width: presetMenu.availableWidth; height: 1; color: shell.cOutline }
                          Repeater {
                            model: [
                              { key: "move", label: "Move To Custom", icon: "copy", shown: !presetMenu.onCustom,
                                tip: "Copy this curated preset into Custom and edit it there." },
                              { key: "into", label: "Save To " + studio.savePresetTarget, icon: "save",
                                shown: presetMenu.onCustom && studio.savePresetTarget !== "",
                                tip: "Write the settings you changed into " + studio.savePresetTarget
                                     + "'s own preset file (asks first; nothing else in the file changes)." },
                              { key: "save", label: "Save Preset As…", icon: "save", shown: presetMenu.onCustom,
                                tip: "Save the current Custom settings as a preset file." }
                            ]
                            delegate: Rectangle {
                                objectName: "presetAction"
                                property string actionKey: modelData.key
                                visible: modelData.shown
                                width: presetMenu.availableWidth; height: visible ? 30 : 0; radius: 6
                                color: actionMouse.containsMouse ? shell.cAccentSoft : "transparent"
                                Row {
                                    x: 8; anchors.verticalCenter: parent.verticalCenter; spacing: 10
                                    StudioIcon { name: modelData.icon; width: 14; height: 14; color: shell.cDim
                                                 anchors.verticalCenter: parent.verticalCenter }
                                    Text { text: modelData.label; color: shell.cText; font.pixelSize: shell.fontBase - 1
                                           anchors.verticalCenter: parent.verticalCenter }
                                }
                                MouseArea {
                                    id: actionMouse; anchors.fill: parent; hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        presetMenu.close()
                                        if (modelData.key === "move") Qt.callLater(studio.moveToCustom)
                                        else if (modelData.key === "into") Qt.callLater(studio.saveToPreset)
                                        else Qt.callLater(studio.savePresetAs)
                                    }
                                }
                                C.ToolTip.visible: actionMouse.containsMouse
                                C.ToolTip.text: modelData.tip
                                C.ToolTip.delay: 500
                            }
                          }
                          Rectangle {
                            objectName: "includeViewRow"
                            visible: studio.includeView >= 0 && presetMenu.onCustom
                            width: presetMenu.availableWidth; height: visible ? 30 : 0; radius: 6
                            color: viewMouse.containsMouse ? shell.cAccentSoft : "transparent"
                            Row {
                                x: 8; anchors.verticalCenter: parent.verticalCenter; spacing: 10
                                StudioIcon { name: "check"; width: 14; height: 14; color: shell.cAccent
                                             opacity: studio.includeView > 0 ? 1 : 0.15
                                             anchors.verticalCenter: parent.verticalCenter }
                                Text { text: "Include Camera View When Saving"; color: shell.cText
                                       font.pixelSize: shell.fontBase - 1; anchors.verticalCenter: parent.verticalCenter }
                            }
                            MouseArea { id: viewMouse; anchors.fill: parent; hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: studio.setIncludeView(!(studio.includeView > 0)) }
                            C.ToolTip.visible: viewMouse.containsMouse
                            C.ToolTip.text: "Save the current camera view into the preset (Settings' own choice)."
                            C.ToolTip.delay: 500
                          }
                        }
                    }
                }
                Row {
                    id: headerButtons
                    spacing: 8
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: studio.dirty
                        text: "● Modified"
                        color: shell.cAccent; font.pixelSize: shell.fontBase - 1; font.bold: true
                        Accessible.name: "Modified since the Studio opened"
                    }
                    StudioButton { icon: "undo"; iconSize: 18; width: 36; enabledState: studio.canUndo
                                   tip: studio.canUndo ? "Undo " + studio.undoText + " (Ctrl+Z)" : "Nothing to undo"
                                   onClicked: studio.undo() }
                    StudioButton { icon: "redo"; iconSize: 18; width: 36; enabledState: studio.canRedo
                                   tip: studio.canRedo ? "Redo " + studio.redoText + " (Ctrl+Y)" : "Nothing to redo"
                                   onClicked: studio.redo() }
                    StudioButton { icon: "reset"; iconSize: 18; width: 36; enabledState: studio.dirty
                                   tip: "Revert: restore everything to the state the Studio opened with (undoable)"
                                   onClicked: studio.revertAll() }
                    StudioButton { objectName: "helpButton"; icon: "help"; iconSize: 18; width: 34
                                   checked: helpOverlay.open
                                   tip: "How the Studio works: workspaces and gestures (F1)"
                                   onClicked: helpOverlay.open = !helpOverlay.open }
                    StudioButton { objectName: "saveCameraButton"; text: "Save Camera"
                                   enabledState: shell.caps.camera === true && studio.canSaveCamera
                                   tip: !shell.caps.camera ? "This visualizer has no camera"
                                        : studio.canSaveCamera ? "Save the current preview camera as this preset's starting camera"
                                                               : "Camera saving is not available for this store"
                                   onClicked: studio.saveCamera() }
                    StudioButton { objectName: "savePresetAsButton"; text: "Save Preset As…"; tip: "Save the current settings as a new preset file"
                                   onClicked: studio.savePresetAs() }
                    StudioButton { objectName: "saveCurrentButton"; text: "Save"; icon: "save"; enabledState: studio.canSave
                                   tip: studio.canSave ? "Save changes into the currently selected preset or Custom slot"
                                                       : "Saving is not available for this store"
                                   onClicked: studio.saveCurrent() }
                    StudioButton { objectName: "closeButton"; text: "Close"; primary: true
                                   tip: "Close the Studio and return to Settings; choose what to do with unsaved preset edits"
                                   onClicked: Qt.callLater(studio.requestCloseFrom, "close button") }
                }
            }
        }

        // Workspace tabs ------------------------------------------------------------------
        Item {
            width: parent.width; height: 52
            StudioFrame {                     // the segmented bar the tabs sit in, with its cast
                objectName: "tabStripFrame"
                x: (parent.width - tabRow.width - 8) / 2; y: (parent.height - 42) / 2
                width: tabRow.width + 8 + shell.shadowX; height: 42 + shell.shadowY
                radius: 9; strokeWidth: shell.cardBorder
                surfaceColor: shell.withAlpha(Qt.darker(shell.cPanel, 1.15), shell.panelAlpha)
                strokeColor: shell.cOutlineSoft
                shadowColor: shell.cShadow; shadowX: shell.shadowX; shadowY: shell.shadowY
            }
            Row {
                id: tabRow
                anchors.centerIn: parent
                spacing: 2
                Repeater {
                    model: studio.workspaces
                    delegate: Rectangle {
                        id: tab
                        readonly property bool current: studio.workspace === modelData.id
                        width: 196; height: 34; radius: 7
                        color: current ? shell.cAccentSoft : (tabMouse.containsMouse ? shell.cRaised : "transparent")
                        gradient: current ? currentTabFill : null
                        border.width: current ? 1 : 0
                        border.color: shell.cAccent
                        SelectionGlow { visible: tab.current; spread: 2 }
                        activeFocusOnTab: true
                        Accessible.role: Accessible.PageTab
                        Accessible.name: modelData.title
                        Row {
                            anchors.centerIn: parent
                            spacing: 8
                            StudioIcon { name: modelData.icon || ""; visible: modelData.icon !== ""; width: 18; height: 18
                                         color: tab.current ? shell.cAccent : shell.cDim; anchors.verticalCenter: parent.verticalCenter }
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
            height: parent.height - header.height - 52
            // Dashboard (mock): ribbon list | wide viewport across the top, the workspace's panels underneath.
            // A mode without scene objects has no list: the viewport takes its width.
            readonly property bool objectsShown: !shell.viewportExpanded && shell.caps.objects !== false
            readonly property int leftW: objectsShown ? Math.max(160, Math.min(240, width * 0.15)) : 0
            readonly property int topH: shell.viewportExpanded ? height - 10 : Math.max(200, Math.round(height * 0.56))

            // Scene objects -------------------------------------------------------------------
            StudioFrame {                     // the panel's surface, one-path border and cast (the panel clips)
                objectName: "panelFrame"
                visible: objectsPanel.visible
                x: objectsPanel.x; y: objectsPanel.y
                width: objectsPanel.width + shell.shadowX; height: objectsPanel.height + shell.shadowY
                radius: 10; strokeWidth: shell.cardBorder
                surfaceColor: shell.cPanelFill; surfaceTopColor: shell.cPanelFillTop; strokeColor: shell.cOutline
                shadowColor: shell.cShadow; shadowX: shell.shadowX; shadowY: shell.shadowY
            }
            Rectangle {
                id: objectsPanel
                objectName: "objectsPanel"
                x: 10; y: 0
                visible: mainRow.objectsShown
                width: mainRow.leftW; height: mainRow.topH
                radius: 10; color: "transparent"
                clip: true
                PanelRim {}
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
                            width: parent.width; height: 38; radius: 7
                            color: selected ? shell.cAccentSoft : (objMouse.containsMouse ? shell.cRaised : "transparent")
                            border.width: selected ? 2 : 1
                            border.color: selected ? shell.cAccent : shell.cOutlineSoft
                            SelectionGlow { visible: obj.selected; spread: 3 }
                            opacity: modelData.visible ? 1.0 : 0.5
                            activeFocusOnTab: true
                            Accessible.role: Accessible.ListItem
                            Accessible.name: modelData.label + (modelData.visible ? "" : " (hidden by count)")
                            Row {
                                anchors.verticalCenter: parent.verticalCenter
                                x: 10; spacing: 10
                                Rectangle { width: 18; height: 18; radius: 4; color: modelData.swatch
                                            border.width: 1; border.color: Qt.lighter(modelData.swatch, 1.4)
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
                                StudioIcon { anchors.centerIn: parent; width: 18; height: 18
                                             name: modelData.visible ? "eye" : "eye-off"
                                             color: modelData.visible ? shell.cText : shell.cDim }
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
                        icon: "plus"
                        text: "Add " + studio.objectNoun
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
                x: mainRow.objectsShown ? objectsPanel.x + objectsPanel.width + 10 : 10
                width: mainRow.objectsShown ? parent.width - mainRow.leftW - 30 : parent.width - 20
                height: mainRow.topH

                Item {
                    id: viewportFrame
                    objectName: "viewportFrame"
                    // The frame reaches `inset` px past the column so the slot keeps its place and size (the scene's
                    // pixels never change), while every slot corner lies inside the frame's rounded outline: the
                    // border, drawn above the scene, covers the slot's square corners.
                    readonly property real radius: 10
                    readonly property real inset: 3
                    x: -2; y: -2
                    width: parent.width + 4
                    height: parent.height + 4
                    StudioFrame {                 // surface and cast, under the scene
                        objectName: "viewportFrameSurface"
                        z: -2
                        width: parent.width + shell.shadowX; height: parent.height + shell.shadowY
                        radius: viewportFrame.radius; strokeWidth: shell.cardBorder
                        surfaceColor: shell.cViewport; strokeColor: shell.cOutline
                        shadowColor: shell.cShadow; shadowX: shell.shadowX; shadowY: shell.shadowY
                    }
                    StudioFrame {                 // the border alone, over the scene: the rounded corners
                        objectName: "viewportFrameBorder"
                        z: 1
                        anchors.fill: parent
                        radius: viewportFrame.radius; strokeWidth: shell.cardBorder
                        strokeColor: shell.cOutline; strokeOnly: true
                    }

                    // Toolbar groups sit on opaque themed backings (mock): the scene never shows through a chip.
                    Rectangle {
                        id: toolbarLeft
                        objectName: "toolbarBacking"
                        x: 10; y: 8; z: 2
                        width: toolbar.width + 8; height: toolbar.height + 8
                        radius: 8; color: shell.opaque(shell.cPanel)
                        border.width: shell.cardBorder; border.color: shell.cOutlineSoft
                        Row {
                            id: toolbar
                            x: 4; y: 4
                            spacing: 8
                            z: 2
                            StudioButton { icon: studio.playing ? "pause" : "play"; iconSize: 20; width: 40; primary: true
                                           tip: (studio.playing ? "Pause" : "Play") + " the preview (Space)"
                                           onClicked: studio.togglePlay() }
                            C.ComboBox {
                                id: fixtureBox
                                objectName: "fixtureBox"
                                width: 230; height: 30
                                model: studio.fixtures
                                textRole: "label"
                                valueRole: "id"
                                currentIndex: {
                                    for (var i = 0; i < studio.fixtures.length; ++i)
                                        if (studio.fixtures[i].id === studio.fixtureId) return i
                                    return -1
                                }
                                // A recorded clip asked for and still analysing is named at once (the preview stays
                                // on the previous source until it lands).
                                displayText: studio.pendingFixture !== "" ? studio.pendingFixture + "  · analysing…"
                                             : currentIndex >= 0 ? studio.fixtures[currentIndex].label : "Choose input"
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
                    }
                    Rectangle {            // what the preview waits for (an analysis, a replay); fades in and out
                        id: busyChip
                        objectName: "previewBusy"
                        property string shownText: ""
                        x: 10; y: toolbarLeft.y + toolbarLeft.height + 6; z: 2
                        width: busyText.implicitWidth + 20; height: busyText.implicitHeight + 10
                        radius: 6; color: shell.opaque(shell.cPanel)
                        border.width: shell.cardBorder; border.color: shell.cOutlineSoft
                        opacity: studio.previewBusy !== "" ? 1 : 0     // at 0 it is not drawn
                        Behavior on opacity { NumberAnimation { duration: 180 } }
                        Component.onCompleted: shownText = studio.previewBusy
                        Connections { target: studio
                                      function onBusyChanged() { if (studio.previewBusy !== "") busyChip.shownText = studio.previewBusy } }
                        Text { id: busyText; anchors.centerIn: parent; text: busyChip.shownText
                               color: shell.cText; font.pixelSize: shell.fontBase - 1 }
                    }
                    Rectangle {
                        objectName: "toolbarBacking"
                        anchors.right: parent.right; anchors.rightMargin: 10; y: 8; z: 2
                        width: toolbarRight.width + 8; height: toolbarRight.height + 8
                        radius: 8; color: shell.opaque(shell.cPanel)
                        border.width: shell.cardBorder; border.color: shell.cOutlineSoft
                        Row {
                            id: toolbarRight
                            x: 4; y: 4
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
                            StudioButton { icon: "check"; iconSize: 20; width: 36; enabledState: studio.viewModified
                                           objectName: "keepViewButton"; visible: shell.caps.camera === true
                                           tip: "Keep View: save the previewed lens (FOV); the orbit saves only when the "
                                                + "preset's camera checkbox is on; dolly and pan stay previews"
                                           onClicked: studio.keepView() }
                            Rectangle { width: 1; height: 24; color: shell.cOutlineSoft; anchors.verticalCenter: parent.verticalCenter }
                            StudioButton { icon: shell.overlaysHidden ? "eye-off" : "eye"; iconSize: 20; width: 36
                                           objectName: "overlaysButton"; visible: shell.caps.handles === true
                                           checked: !shell.overlaysHidden
                                           tip: shell.overlaysHidden ? "Show the handles and outline over the scene"
                                                                     : "Hide the handles and outline: see the scene alone"
                                           onClicked: shell.overlaysHidden = !shell.overlaysHidden }
                            StudioButton { icon: "brush"; iconSize: 20; width: 36; objectName: "brushButton"
                                           visible: shell.caps.brush === true
                                           checked: studio.brushState.active === true
                                           tip: studio.brushState.active === true
                                                ? "Stop painting: drag the scene to orbit again (B)"
                                                : "Paint " + (studio.brushState.label || "") + ": drag on the scene to "
                                                  + "raise, lower, flatten or flood the land (B); right-drag still pans"
                                           onClicked: studio.setBrushActive(!(studio.brushState.active === true)) }
                            StudioButton { icon: "camera"; iconSize: 20; width: 36; objectName: "copyFrameButton"
                                           tip: "Copy Frame: the scene as rendered (no handles) to the clipboard"
                                           onClicked: studio.copyFrame() }
                            StudioButton { icon: "frame"; iconSize: 20; width: 36; enabledState: studio.viewModified
                                           objectName: "resetViewButton"; visible: shell.caps.camera === true
                                           tip: "Frame The Card: back to the saved camera, as the live card shows it "
                                                + "(or double-click the scene)"
                                           onClicked: studio.resetCamera() }
                            StudioButton { icon: shell.viewportExpanded ? "collapse" : "expand"; iconSize: 20; width: 36
                                           objectName: "expandViewportButton"; checked: shell.viewportExpanded
                                           tip: shell.viewportExpanded ? "Show the panels again (F11)"
                                                                       : "Expand the viewport over the panels (F11)"
                                           onClicked: shell.viewportExpanded = !shell.viewportExpanded }
                        }
                    }

                    // The production scene is drawn under this slot by the Studio viewport item.
                    Item {
                        id: viewportSlot
                        objectName: "viewportSlot"
                        x: viewportFrame.inset; y: viewportFrame.inset
                        width: parent.width - 2 * viewportFrame.inset
                        // The scene ends where the (opaque) scrub bar starts: no part of the frame hides under it.
                        height: parent.height - 2 * viewportFrame.inset - scrubBar.height
                        clip: true
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
                            objectName: "orbitArea"
                            // Only a mode that declares a camera navigates; 2D modes have no orbit/zoom/pan.
                            enabled: shell.caps.camera === true
                            visible: enabled
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
                        // Direct manipulation: the selected object's outline + handles, projected through
                        // the production camera (presented-frame pixels -> slot via frameX/frameY).
                        Item {
                            id: handleLayer
                            objectName: "handleLayer"
                            visible: shell.caps.handles === true && !shell.overlaysHidden
                            x: viewportSlot.frameX; y: viewportSlot.frameY
                            width: viewportSlot.frameWidth; height: viewportSlot.frameHeight
                            readonly property var outline: studio.handles.outline || []
                            readonly property var items: studio.handles.handles || []
                            Canvas {
                                id: outlineCanvas
                                anchors.fill: parent
                                onPaint: {
                                    var ctx = getContext("2d"); ctx.reset()
                                    var pts = handleLayer.outline
                                    if (pts.length < 2) return
                                    ctx.lineJoin = "round"
                                    ctx.strokeStyle = "#66000000"; ctx.lineWidth = 5
                                    ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1])
                                    for (var i = 1; i < pts.length; ++i) ctx.lineTo(pts[i][0], pts[i][1])
                                    ctx.stroke()
                                    ctx.strokeStyle = shell.cAccent; ctx.lineWidth = 2; ctx.setLineDash([6, 4])
                                    ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1])
                                    for (var j = 1; j < pts.length; ++j) ctx.lineTo(pts[j][0], pts[j][1])
                                    ctx.stroke()
                                }
                                Connections { target: handleLayer; function onOutlineChanged() { outlineCanvas.requestPaint() } }
                            }
                            Repeater {
                                model: handleLayer.items
                                delegate: Item {
                                    id: handle
                                    objectName: "sceneHandle"
                                    property string handleId: modelData.id
                                    x: modelData.x - 13; y: modelData.y - 13
                                    width: 26; height: 26
                                    property bool dragging: false
                                    readonly property bool combined: modelData.axis === "xy"
                                    z: combined ? 2 : 1
                                    Item {          // combined move gizmo: a crosshair with four arrowheads
                                        visible: handle.combined
                                        anchors.centerIn: parent
                                        width: 104; height: 104
                                        opacity: hMouse.containsMouse || handle.dragging ? 1 : .85
                                        Rectangle { anchors.centerIn: parent; width: parent.width - 10; height: 2; color: "#f0ffffff" }
                                        Rectangle { anchors.centerIn: parent; width: 2; height: parent.height - 10; color: "#f0ffffff" }
                                        Repeater {
                                            model: [[-1, 0, 180], [1, 0, 0], [0, -1, -90], [0, 1, 90]]
                                            delegate: StudioIcon {
                                                width: 16; height: 16; stroke: 2.6; color: "#f0ffffff"; name: "chevron-right"
                                                rotation: modelData[2]
                                                x: 52 - 8 + modelData[0] * 46; y: 52 - 8 + modelData[1] * 46
                                            }
                                        }
                                    }
                                    Item {          // drag-axis guide with arrowheads (like a gizmo)
                                        visible: modelData.span === undefined && !handle.combined
                                        anchors.centerIn: parent
                                        width: modelData.axis === "x" ? 84 : 14
                                        height: modelData.axis === "x" ? 14 : 84
                                        opacity: hMouse.containsMouse || handle.dragging ? 1 : .7
                                        Rectangle { anchors.centerIn: parent; color: "#e6ffffff"
                                                    width: modelData.axis === "x" ? parent.width - 8 : 2
                                                    height: modelData.axis === "x" ? 2 : parent.height - 8 }
                                        StudioIcon { width: 14; height: 14; stroke: 2.4; color: "#e6ffffff"
                                                     name: modelData.axis === "x" ? "chevron-right" : "chevron-down"
                                                     rotation: 180
                                                     x: modelData.axis === "x" ? -2 : 0; y: modelData.axis === "x" ? 0 : -2 }
                                        StudioIcon { width: 14; height: 14; stroke: 2.4; color: "#e6ffffff"
                                                     name: modelData.axis === "x" ? "chevron-right" : "chevron-down"
                                                     x: modelData.axis === "x" ? parent.width - 12 : 0
                                                     y: modelData.axis === "x" ? 0 : parent.height - 12 }
                                    }
                                    Item {          // width bracket: handle (sheet edge) down to the spine
                                        visible: modelData.span !== undefined
                                        x: handle.width / 2 - 6; y: handle.height / 2
                                        width: 12; height: modelData.span || 0
                                        Rectangle { x: 5; width: 2; height: parent.height; color: shell.cAccent }
                                        Rectangle { y: parent.height - 1; width: 12; height: 2; color: shell.cAccent }
                                    }
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: (handle.combined ? 6 : 0) + (handle.dragging || hMouse.containsMouse ? 22 : 18)
                                        height: width
                                        radius: modelData.shape === "diamond" ? 2 : width / 2
                                        rotation: modelData.shape === "diamond" ? 45 : 0
                                        color: handle.dragging ? shell.cAccent : "#e6ffffff"
                                        border.width: 2; border.color: shell.cAccent
                                    }
                                    StudioIcon {
                                        anchors.centerIn: parent; width: 12; height: 12; stroke: 2.6
                                        name: handle.combined ? "move" : (modelData.axis === "x" ? "flow" : "height")
                                        color: handle.dragging ? "white" : shell.cAccent
                                        rotation: 0
                                    }
                                    Rectangle {      // label (live value while hovered / dragged)
                                        x: modelData.id === "width" ? -width - 4 : (modelData.axis === "x" ? 50 : (handle.combined ? 30 : 26))
                                        y: modelData.axis === "x" ? 2 : (handle.combined ? 22 : -10)
                                        opacity: hMouse.containsMouse || handle.dragging ? 1 : .8
                                        width: hText.implicitWidth + 12; height: 22; radius: 4
                                        color: "#cc000000"
                                        Text { id: hText; anchors.centerIn: parent; color: "white"; font.pixelSize: shell.fontBase - 2
                                               text: modelData.label + (hMouse.containsMouse || handle.dragging
                                                     ? (handle.combined
                                                        ? "  ↔ " + Number(shell.endpointValue(modelData.property, modelData.endpoint)).toFixed(2)
                                                          + "  ↕ " + Number(shell.endpointValue(modelData.propertyY, modelData.endpoint)).toFixed(2)
                                                        : "  " + Number(shell.endpointValue(modelData.property, modelData.endpoint)).toFixed(3))
                                                     : "") }
                                    }
                                    MouseArea {
                                        id: hMouse
                                        anchors.fill: parent
                                        anchors.margins: handle.combined ? -6 : 0
                                        hoverEnabled: true
                                        preventStealing: true
                                        cursorShape: handle.combined ? Qt.SizeAllCursor
                                                     : (modelData.axis === "x" ? Qt.SizeHorCursor : Qt.SizeVerCursor)
                                        property real startValue: 0
                                        property real startValueY: 0
                                        property real startX: 0
                                        property real startY: 0
                                        onPressed: function(m) {
                                            var p = mapToItem(handleLayer, m.x, m.y)
                                            startX = p.x; startY = p.y
                                            startValue = shell.endpointValue(modelData.property, modelData.endpoint)
                                            if (handle.combined)
                                                startValueY = shell.endpointValue(modelData.propertyY, modelData.endpoint)
                                            handle.dragging = true
                                            studio.beginEdit(modelData.property, modelData.label)
                                        }
                                        onPositionChanged: function(m) {
                                            if (!pressed) return
                                            var p = mapToItem(handleLayer, m.x, m.y)
                                            if (handle.combined) {      // one gesture: x -> property, y -> propertyY
                                                studio.previewValue(modelData.property, modelData.endpoint,
                                                                    startValue + (p.x - startX) * modelData.perPixel)
                                                studio.previewValue(modelData.propertyY, modelData.endpoint,
                                                                    startValueY + (p.y - startY) * modelData.perPixelY)
                                                return
                                            }
                                            var delta = modelData.axis === "x" ? p.x - startX : p.y - startY     // screen pixels (perPixel is per screen px)
                                            studio.previewValue(modelData.property, modelData.endpoint,
                                                                startValue + delta * modelData.perPixel)
                                        }
                                        onReleased: { handle.dragging = false; studio.endEdit() }
                                        onDoubleClicked: studio.revealProperty(modelData.property, modelData.endpoint)
                                    }
                                    C.ToolTip.visible: hMouse.containsMouse && !handle.dragging
                                    // A handle may carry its own words (the mode knows what it moves).
                                    C.ToolTip.text: modelData.tooltip !== undefined ? modelData.tooltip
                                                    : handle.combined
                                                    ? "Move: drag left/right to slide the wave, up/down to change its height (one edit; Undo reverts)"
                                                    : modelData.label + " — drag to edit (Undo reverts); double-click to type an exact value"
                                    C.ToolTip.delay: 600
                                }
                            }
                        }

                        // The shared brush: strokes land on the scene's ground (presented-frame pixels); the
                        // footprint follows the pointer. Left button paints; right / middle still pan, wheel zooms.
                        Item {
                            id: brushLayer
                            objectName: "brushLayer"
                            visible: shell.caps.brush === true && studio.brushState.active === true
                            x: viewportSlot.frameX; y: viewportSlot.frameY
                            width: viewportSlot.frameWidth; height: viewportSlot.frameHeight
                            readonly property var rings: studio.brushCursor
                            Canvas {
                                id: brushCanvas
                                anchors.fill: parent
                                onPaint: {
                                    var ctx = getContext("2d"); ctx.reset()
                                    var rings = brushLayer.rings || []
                                    for (var r = 0; r < rings.length; ++r) {
                                        var pts = rings[r]
                                        if (pts.length < 2) continue
                                        for (var pass = 0; pass < 2; ++pass) {
                                            ctx.strokeStyle = pass === 0 ? "#80000000" : (r === 0 ? shell.cAccent : "#e6ffffff")
                                            ctx.lineWidth = pass === 0 ? 4 : 1.6
                                            ctx.setLineDash(r === 0 || pass === 0 ? [] : [5, 4])
                                            ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1])
                                            for (var i = 1; i < pts.length; ++i) ctx.lineTo(pts[i][0], pts[i][1])
                                            ctx.stroke()
                                        }
                                    }
                                }
                                Connections { target: brushLayer; function onRingsChanged() { brushCanvas.requestPaint() } }
                            }
                            MouseArea {
                                id: brushArea
                                objectName: "brushArea"
                                anchors.fill: parent
                                enabled: brushLayer.visible
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton
                                preventStealing: true
                                cursorShape: Qt.CrossCursor
                                onPressed: function(m) { shell.forceActiveFocus(); studio.brushPress(m.x, m.y) }
                                onPositionChanged: function(m) {
                                    if (pressed) studio.brushMove(m.x, m.y)
                                    else studio.brushHover(m.x, m.y)
                                }
                                onReleased: studio.brushRelease()
                                onCanceled: studio.brushCancel()
                                onExited: studio.brushLeave()
                                onWheel: function(w) {
                                    studio.zoomBy(w.angleDelta.y / 120.0, (w.modifiers & Qt.ShiftModifier) !== 0)
                                    w.accepted = true
                                }
                            }
                        }
                        Rectangle {
                            id: brushPanel
                            objectName: "brushPanel"
                            visible: brushLayer.visible
                            x: 10; y: 56; z: 3
                            width: 286; height: brushColumn.implicitHeight + 20
                            radius: 8; color: shell.opaque(shell.cPanel)
                            border.width: shell.cardBorder; border.color: shell.cOutlineSoft
                            MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons
                                        onWheel: function(w) { w.accepted = true } }      // the panel is not the scene
                            Column {
                                id: brushColumn
                                x: 10; y: 10; width: parent.width - 20
                                spacing: 8
                                Text { text: (studio.brushState.label || "") + " Brush"; color: shell.cText
                                       font.pixelSize: shell.fontBase; font.bold: true }
                                Flow {
                                    width: parent.width; spacing: 6
                                    Repeater {
                                        model: studio.brushState.modes || []
                                        delegate: Chip {
                                            objectName: "brushMode"
                                            text: modelData
                                            selected: studio.brushState.mode === modelData
                                            onPicked: studio.setBrushValue("mode", modelData)
                                        }
                                    }
                                }
                                Repeater {
                                    model: [
                                        { name: "radius", label: "Radius", from: 0.03, to: 0.35,
                                          tip: "The brush size, as a share of the terrain grid's side." },
                                        { name: "strength", label: "Strength", from: 0.01, to: 1.0,
                                          tip: "How much a stroke changes the land per brush-width it travels. Low values build up gently; Flatten snaps to its height only at 100%." },
                                        { name: "falloff", label: "Falloff", from: 0.0, to: 1.0,
                                          tip: "How soft the brush edge is: 0 is a hard disc, higher values ease out over a wider rim (the dashed ring is the flat core)." },
                                        { name: "flatten_height", label: "Flatten Height", from: 0.0, to: 1.0,
                                          tip: "The height Flatten moves land toward." }
                                    ]
                                    delegate: Row {
                                        objectName: "brushSetting"
                                        spacing: 8; height: 24
                                        visible: modelData.name !== "flatten_height" || studio.brushState.mode === "Flatten"
                                        Text { width: 92; text: modelData.label; color: shell.cDim; elide: Text.ElideRight
                                               font.pixelSize: shell.fontBase - 1; anchors.verticalCenter: parent.verticalCenter
                                               C.ToolTip.visible: tipMouse.containsMouse; C.ToolTip.text: modelData.tip
                                               C.ToolTip.delay: 500
                                               MouseArea { id: tipMouse; anchors.fill: parent; hoverEnabled: true
                                                           acceptedButtons: Qt.NoButton } }
                                        ValueSlider {
                                            id: brushSlider
                                            width: brushColumn.width - 92 - 44 - 16
                                            anchors.verticalCenter: parent.verticalCenter
                                            toolName: modelData.name; label: modelData.label
                                            from: modelData.from; to: modelData.to
                                            value: Number(studio.brushState[modelData.name] || 0)
                                        }
                                        Text { width: 44; horizontalAlignment: Text.AlignRight
                                               anchors.verticalCenter: parent.verticalCenter
                                               color: shell.cText; font.pixelSize: shell.fontBase - 1
                                               text: Math.round(100 * (brushSlider.dragging ? brushSlider.dragValue
                                                                       : Number(studio.brushState[modelData.name] || 0))) + "%" }
                                    }
                                }
                                HintText { width: parent.width; wrapMode: Text.Wrap
                                           text: "One stroke is one edit; Undo takes it back." }
                            }
                        }

                        // Live view readout (bottom-left of the presented frame)
                        Rectangle {
                            x: viewportSlot.frameX + 8
                            y: viewportSlot.frameY + viewportSlot.frameHeight - height - 8
                            width: readout.implicitWidth + 16; height: 24; radius: 4
                            color: "#99000000"
                            visible: shell.caps.camera === true && studio.viewReadout.length > 0
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
                            visible: studio.viewportStatus !== "live" && studio.viewportStatus !== "none"
                            anchors.centerIn: parent
                            width: Math.min(parent.width - 40, statusText.implicitWidth + 40)
                            height: statusText.implicitHeight + 24
                            radius: 6
                            color: "#cc0b0d14"
                            border.width: shell.cardBorder
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

                    Text {           // inspector-only modes (no live preview declared)
                        objectName: "noPreviewNote"
                        visible: shell.caps.viewport !== true
                        x: viewportSlot.x + (viewportSlot.width - width) / 2
                        y: viewportSlot.y + (viewportSlot.height - height) / 2
                        width: Math.min(420, viewportSlot.width - 40)
                        wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter
                        color: shell.cDim; font.pixelSize: shell.fontBase
                        text: "This mode has no live preview here. Edits still save to the visualizer; "
                              + "the signal traces show how the preview input drives it."
                    }

                    // Scrub / time bar
                    Rectangle {
                        id: scrubBar
                        objectName: "scrubBar"
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: viewportFrame.inset; x: viewportFrame.inset
                        width: parent.width - 2 * viewportFrame.inset; height: 48
                        radius: viewportFrame.radius - viewportFrame.inset      // concentric with the frame
                        color: shell.opaque(shell.cWell)
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
                                            var played = (i / n) <= scrub.frac
                                            if (played) {         // a soft halo under the played part
                                                ctx.fillStyle = shell.accentA(0.18)
                                                ctx.fillRect(i * w - 1, mid - h - 2, Math.max(1, w + 1), 2 * h + 4)
                                            }
                                            ctx.fillStyle = played ? shell.cAccent : shell.cTrack
                                            ctx.fillRect(i * w, mid - h, Math.max(1, w - 1), 2 * h)
                                        }
                                    }
                                    Connections { target: studio
                                                  function onTransportChanged() { trackCanvas.requestPaint() }
                                                  function onTimeChanged() { trackCanvas.requestPaint() } }
                                    Component.onCompleted: requestPaint()
                                }
                                Rectangle { x: parent.width * scrub.frac - 1; anchors.verticalCenter: parent.verticalCenter
                                            width: 3; height: 18; color: scrub.activeFocus ? shell.cFocus : shell.cWellText }
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
                            Text { id: timeText; objectName: "transportTime"
                                   anchors.verticalCenter: parent.verticalCenter; width: 92
                                   text: studio.time.toFixed(2) + " / " + studio.duration.toFixed(1) + " s"
                                   color: shell.cWellDim; font.pixelSize: shell.fontBase - 1 }
                            StudioButton { id: loopBtn; icon: "loop"; iconSize: 18; width: 38; checked: studio.loop
                                           anchors.verticalCenter: parent.verticalCenter
                                           tip: "Repeat the preview input"; onClicked: studio.setLoop(!studio.loop) }
                        }
                    }

                    // Transient notices (clamps, rejected values, camera policy)
                    Rectangle {
                        visible: studio.message !== ""
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.bottom: scrubBar.top; anchors.bottomMargin: 10
                        width: Math.min(parent.width - 40, noticeText.implicitWidth + 60
                                        + (noticeAction.visible ? noticeAction.implicitWidth + 10 : 0)); height: 32; radius: 6
                        color: shell.cRaised; border.width: 1; border.color: shell.cOutline
                        z: 3
                        Text { id: noticeText; anchors.verticalCenter: parent.verticalCenter; x: 12
                               width: Math.min(implicitWidth, parent.width - 60
                                               - (noticeAction.visible ? noticeAction.implicitWidth + 10 : 0))
                               elide: Text.ElideRight
                               text: studio.message; color: shell.cText; font.pixelSize: shell.fontBase - 1 }
                        // A notice may offer one action (e.g. Retry a failed analysis).
                        StudioButton { id: noticeAction; objectName: "noticeAction"; visible: studio.messageAction !== ""
                                       text: studio.messageAction; height: 24; textSize: shell.fontBase - 1
                                       anchors.verticalCenter: parent.verticalCenter
                                       anchors.left: noticeText.right; anchors.leftMargin: 10
                                       onClicked: studio.runMessageAction() }
                        Text { anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
                               text: "✕"; color: shell.cDim
                               MouseArea { anchors.fill: parent; anchors.margins: -6; onClicked: studio.dismissMessage() } }
                    }
                }
            }

            // Response editor (Reactivity): target -> source mix with live input -> transfer curve -> range.
            StudioFrame {                     // the dock's surface, one-path border and cast (the dock clips)
                objectName: "panelFrame"
                parent: bottomArea
                // Under the dock, by z: both are reparented into bottomArea, so their sibling order is not their
                // declaration order (the frame landed last and its fill covered the whole editor, which read as a
                // ghosted, empty panel).
                z: -1
                visible: responseDock.visible
                x: responseDock.x; y: responseDock.y
                width: responseDock.width + shell.shadowX; height: responseDock.height + shell.shadowY
                radius: 10; strokeWidth: shell.cardBorder
                surfaceColor: shell.cPanelFill; surfaceTopColor: shell.cPanelFillTop; strokeColor: shell.cOutline
                shadowColor: shell.cShadow; shadowX: shell.shadowX; shadowY: shell.shadowY
            }
            Rectangle {
                id: responseDock
                parent: bottomArea
                visible: bottomArea.responseIndex >= 0 && studio.response.targets !== undefined
                x: bottomArea.columnX(Math.max(0, bottomArea.responseIndex))
                width: bottomArea.columnWidth(Math.max(0, bottomArea.responseIndex))
                height: bottomArea.height
                readonly property bool expanded: true
                objectName: "responseDock"
                clip: true
                radius: 10
                color: "transparent"
                PanelHeader {
                    id: dockTitle
                    icon: bottomArea.responseIndex >= 0 ? bottomArea.columns[bottomArea.responseIndex].icon : ""
                    title: bottomArea.responseIndex >= 0 ? bottomArea.columns[bottomArea.responseIndex].title : ""
                    subtitle: bottomArea.responseIndex >= 0 ? bottomArea.columns[bottomArea.responseIndex].subtitle : ""
                }
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

                // Narrow windows: the editor keeps its working width and scrolls sideways (never squeezes/overlaps).
                // Short windows: it keeps its height too and scrolls down, as every dashboard panel scrolls on its
                // own (at the default window on a 1440p / 150% screen its Range row was cut off, out of reach).
                Flickable {
                    id: dockFlick
                    objectName: "responseScroll"
                    anchors.fill: parent; anchors.margins: 12; anchors.topMargin: dockTitle.height + 8
                    anchors.bottomMargin: contentWidth > width ? 18 : 12
                    clip: true
                    contentWidth: Math.max(width, 820)
                    contentHeight: Math.max(height, mixColumn.implicitHeight, curveColumn.implicitHeight)
                    flickableDirection: Flickable.AutoFlickIfNeeded
                    boundsBehavior: Flickable.StopAtBounds
                    interactive: contentWidth > width || contentHeight > height
                    C.ScrollBar.horizontal: C.ScrollBar { policy: dockFlick.contentWidth > dockFlick.width
                                                                  ? C.ScrollBar.AlwaysOn : C.ScrollBar.AlwaysOff }
                    // In the dock's right margin, beside the editor: never over its fields.
                    C.ScrollBar.vertical: C.ScrollBar {
                        objectName: "responseScrollVertical"
                        parent: responseDock
                        x: dockFlick.x + dockFlick.width + 2; y: dockFlick.y; width: 8; height: dockFlick.height
                        policy: dockFlick.contentHeight > dockFlick.height ? C.ScrollBar.AlwaysOn : C.ScrollBar.AlwaysOff }
                Row {
                    width: dockFlick.contentWidth; height: dockFlick.contentHeight
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
                                        C.ToolTip.text: modelData.description + "\nBar: where the live drive sits in this Range (empty = Quiet, full = Peak)"
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
                        HintText { text: responseDock.target ? responseDock.target.description : ""
                                   font.pixelSize: shell.fontBase - 2; width: parent.width }
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
                        id: curveColumn
                        width: 330
                        spacing: 6
                        Text { text: "Response Curve — " + responseDock.sourceLabel(studio.selectedSource)
                               color: shell.cText; font.pixelSize: shell.fontBase + 1; font.bold: true }
                        Rectangle {
                            id: curveBox
                            width: parent.width; height: 92; radius: 4
                            color: shell.cWell; border.width: shell.cardBorder; border.color: shell.cOutlineSoft
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
                                    ctx.fillStyle = shell.cWellTrace3
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
                                preventStealing: true          // the dock scrolls sideways when narrow
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
                                   color: shell.cWellDim; font.pixelSize: shell.fontBase - 3 }
                            C.ToolTip.visible: curveDrag.containsMouse
                            C.ToolTip.text: "Drag up/down to bend the curve (exact power below). Dot: live input → output."
                        }
                        Row {
                            spacing: 6
                            Repeater {
                                model: studio.response.presets || []
                                delegate: Rectangle {
                                    id: shapeTile
                                    objectName: "curveShapeTile"
                                    readonly property bool selected: curveBox.cell !== null
                                                                     && Math.abs(curveBox.power - modelData.power) < 1e-3
                                    width: 54; height: 50; radius: 6
                                    color: selected ? shell.cAccentSoft : (shapeMouse.containsMouse ? shell.cRaised : "transparent")
                                    border.width: selected ? 2 : 1
                                    border.color: selected ? shell.cAccent : shell.cOutlineSoft
                                    activeFocusOnTab: true
                                    Accessible.role: Accessible.RadioButton
                                    Accessible.name: modelData.label
                                    Accessible.checked: selected
                                    Canvas {         // the curve this shape applies: output = input ^ power
                                        x: 9; y: 5; width: parent.width - 18; height: 26
                                        property real power: modelData.power
                                        property color ink: shapeTile.selected ? shell.cAccent : shell.cDim
                                        onInkChanged: requestPaint()
                                        onPaint: {
                                            var ctx = getContext("2d"); ctx.reset()
                                            ctx.strokeStyle = ink; ctx.lineWidth = 1.6; ctx.lineCap = "round"
                                            ctx.beginPath()
                                            for (var i = 0; i <= 24; ++i) {
                                                var t = i / 24, v = Math.pow(t, power)
                                                var px = t * width, py = height - 1 - v * (height - 2)
                                                if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py)
                                            }
                                            ctx.stroke()
                                        }
                                    }
                                    Text { anchors.horizontalCenter: parent.horizontalCenter; y: 33
                                           text: modelData.label; color: shell.cText; font.pixelSize: shell.fontBase - 3
                                           font.bold: shapeTile.selected }
                                    MouseArea { id: shapeMouse; anchors.fill: parent; hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: { shapeTile.forceActiveFocus()
                                                             if (curveBox.cell) studio.commitValue(curveBox.cell.power, 0, modelData.power) } }
                                    Keys.onSpacePressed: if (curveBox.cell) studio.commitValue(curveBox.cell.power, 0, modelData.power)
                                    Keys.onReturnPressed: if (curveBox.cell) studio.commitValue(curveBox.cell.power, 0, modelData.power)
                                    FocusRing { visible: shapeTile.activeFocus }
                                    C.ToolTip.visible: shapeMouse.containsMouse
                                    C.ToolTip.text: modelData.label + ": response curve " + modelData.power.toFixed(2)
                                    C.ToolTip.delay: 500
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
                        Text { text: studio.response.timingNote + " (Timing panel)"
                               color: shell.cDim; font.pixelSize: shell.fontBase - 3; width: parent.width; wrapMode: Text.Wrap }
                    }
                }
                }
            }

            // Dashboard panels under the viewport (mock): the workspace's groups side by side, each panel scrolling
            // on its own; the response editor fills its own panel. Geometry comes from the panels' weights.
            Item {
                id: bottomArea
                objectName: "dashboardPanels"
                visible: !shell.viewportExpanded
                x: 10; y: mainRow.topH + 10
                width: parent.width - 20; height: parent.height - mainRow.topH - 20
                readonly property var columns: studio.inspectorColumns
                readonly property real gap: 10
                readonly property real totalWeight: {
                    var w = 0
                    for (var i = 0; i < columns.length; ++i) w += columns[i].weight
                    return Math.max(1e-6, w)
                }
                function columnX(index) {
                    var x = 0, usable = width - gap * Math.max(0, columns.length - 1)
                    for (var i = 0; i < index; ++i) x += usable * columns[i].weight / totalWeight + gap
                    return x
                }
                function columnWidth(index) {
                    var usable = width - gap * Math.max(0, columns.length - 1)
                    return index < columns.length ? usable * columns[index].weight / totalWeight : 0
                }
                readonly property int responseIndex: {
                    for (var i = 0; i < columns.length; ++i) if (columns[i].kind === "response") return i
                    return -1
                }
                Repeater {
                    model: bottomArea.columns
                    delegate: Rectangle {
                        id: panel
                        objectName: "dashboardPanel"
                        readonly property var column: modelData
                        visible: column.kind === "groups"
                        x: bottomArea.columnX(index); width: bottomArea.columnWidth(index); height: bottomArea.height
                        radius: 10; color: "transparent"
                        StudioFrame {         // surface, one-path border and cast, under the panel's content
                            objectName: "panelFrame"
                            z: -2
                            width: parent.width + shell.shadowX; height: parent.height + shell.shadowY
                            radius: 10; strokeWidth: shell.cardBorder
                            surfaceColor: shell.cPanelFill; surfaceTopColor: shell.cPanelFillTop; strokeColor: shell.cOutline
                            shadowColor: shell.cShadow; shadowX: shell.shadowX; shadowY: shell.shadowY
                        }
                        PanelRim {}
                        PanelHeader { id: panelHeader; icon: panel.column.icon; title: panel.column.title
                                      subtitle: panel.column.subtitle }
                        C.ScrollView {
                            id: inspectorScroll
                            objectName: "inspectorScroll"
                            anchors.fill: parent; anchors.margins: 12; anchors.topMargin: panelHeader.height + 8
                            clip: true
                            contentWidth: availableWidth
                            Column {
                                width: inspectorScroll.availableWidth
                                spacing: 12
                                Repeater {
                                    model: panel.column.groups
                                    delegate: InspectorGroup { width: parent.width; groupData: modelData }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Help overlay: what each workspace is for and the gestures this mode supports (from its capabilities).
    Rectangle {
        id: helpOverlay
        objectName: "helpOverlay"
        property bool open: false
        anchors.fill: parent
        visible: open
        z: 100
        color: "#b3000000"
        MouseArea { anchors.fill: parent; onClicked: helpOverlay.open = false; onWheel: function(w) { w.accepted = true } }
        readonly property var gestures: {
            var out = []
            if (shell.caps.camera === true) {
                out.push(["view", "Drag the preview", "Orbit the camera (saved only with the preset's camera checkbox)"])
                out.push(["lens", "Mouse wheel", "Zoom the lens; Shift+wheel moves the camera closer or further"])
                out.push(["flow", "Middle or right drag", "Pan the view (a preview only)"])
                out.push(["reset", "Double-click the preview", "Back to the saved camera; the tick button keeps the view"])
            }
            if (shell.caps.handles === true)
                out.push(["move", "Handles (Composition)", "Drag the crosshair or a handle to edit the selected "
                          + studio.objectNoun.toLowerCase() + " in place; double-click a handle to type a value"])
            out.push(["bars", "Quiet / Peak", "Most values have a quiet and a peak end: the music moves between them"])
            out.push(["height", "Sliders and fields", "Drag, use arrow keys, or type an exact value; right-click a "
                      + "label to reset it"])
            out.push(["undo", "Undo / Redo", "Every change is one named step (Ctrl+Z / Ctrl+Y); edits save to Custom"])
            out.push(["play", "Space", "Play or pause the preview input; drag the waveform bar to scrub"])
            return out
        }
        Rectangle {
            anchors.centerIn: parent
            width: Math.min(parent.width - 48, 680)
            height: Math.min(parent.height - 48, helpColumn.implicitHeight + 48)
            radius: 10
            color: shell.cPanel
            border.width: shell.cardBorder; border.color: shell.cOutline
            MouseArea { anchors.fill: parent }       // clicks inside do not close
            C.ScrollView {
                id: helpScroll
                anchors.fill: parent; anchors.margins: 24
                clip: true
                contentWidth: availableWidth
                Column {
                    id: helpColumn
                    width: helpScroll.availableWidth
                    spacing: 10
                    Row {
                        spacing: 10
                        StudioIcon { name: "help"; width: 22; height: 22; color: shell.cAccent }
                        Text { text: "How the " + studio.title + " Works"; color: shell.cText
                               font.pixelSize: shell.fontBase + 4; font.bold: true }
                    }
                    Text { width: parent.width; wrapMode: Text.Wrap; color: shell.cDim; font.pixelSize: shell.fontBase
                           text: "Pick a workspace, select an object on the left and shape it on the right. The preview "
                                 + "is the real visualizer, driven by the input chosen above it." }
                    Text { text: "Workspaces"; color: shell.cText; font.bold: true; font.pixelSize: shell.fontBase + 1
                           topPadding: 6 }
                    Repeater {
                        model: studio.workspaces
                        delegate: Row {
                            spacing: 12
                            width: helpColumn.width
                            StudioIcon { name: modelData.icon || ""; width: 18; height: 18; color: shell.cAccent }
                            Text { text: modelData.title; width: 110; color: shell.cText; font.bold: true
                                   font.pixelSize: shell.fontBase }
                            Text { width: parent.width - 150; wrapMode: Text.Wrap; color: shell.cDim
                                   font.pixelSize: shell.fontBase; text: modelData.help || "" }
                        }
                    }
                    Text { text: "Gestures"; color: shell.cText; font.bold: true; font.pixelSize: shell.fontBase + 1
                           topPadding: 6 }
                    Repeater {
                        model: helpOverlay.gestures
                        delegate: Row {
                            objectName: "helpGesture"
                            spacing: 12
                            width: helpColumn.width
                            StudioIcon { name: modelData[0]; width: 18; height: 18; color: shell.cAccent }
                            Text { text: modelData[1]; width: 160; color: shell.cText; font.pixelSize: shell.fontBase
                                   wrapMode: Text.Wrap }
                            Text { width: parent.width - 200; wrapMode: Text.Wrap; color: shell.cDim
                                   font.pixelSize: shell.fontBase; text: modelData[2] }
                        }
                    }
                    Text { text: "Hover any control for its explanation. Esc or F1 closes this help."
                           color: shell.cDim; font.pixelSize: shell.fontBase - 1; topPadding: 6 }
                }
            }
            StudioButton { anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10
                           icon: "close"; iconSize: 16; width: 30; height: 28; tip: "Close help (Esc)"
                           onClicked: helpOverlay.open = false }
        }
    }

    // The forged rounded window edge, painted by Settings' own painter over everything (its corner caps make the
    // rectangular window read as rounded), then the resize edges a frameless window needs.
    StudioWindowEdge {
        objectName: "studioWindowEdge"
        anchors.fill: parent
        z: 1000
        maximized: shell.maximized
        outerBorder: shell.tc("outerBorder", shell.cOutline)
        forgedEdge: shell.tc("forgedEdge", shell.cHeader)
    }
    Repeater {
        // Every side and corner: the Qt edges it resizes (through the system) and its cursor.
        model: shell.maximized ? [] : [
            {"edges": Qt.LeftEdge, "cursor": Qt.SizeHorCursor}, {"edges": Qt.RightEdge, "cursor": Qt.SizeHorCursor},
            {"edges": Qt.TopEdge, "cursor": Qt.SizeVerCursor}, {"edges": Qt.BottomEdge, "cursor": Qt.SizeVerCursor},
            {"edges": Qt.TopEdge | Qt.LeftEdge, "cursor": Qt.SizeFDiagCursor},
            {"edges": Qt.BottomEdge | Qt.RightEdge, "cursor": Qt.SizeFDiagCursor},
            {"edges": Qt.TopEdge | Qt.RightEdge, "cursor": Qt.SizeBDiagCursor},
            {"edges": Qt.BottomEdge | Qt.LeftEdge, "cursor": Qt.SizeBDiagCursor}]
        delegate: MouseArea {
            objectName: "resizeEdge"
            readonly property int grip: 5
            readonly property int corner: 14
            readonly property bool onLeft: (modelData.edges & Qt.LeftEdge) !== 0
            readonly property bool onRight: (modelData.edges & Qt.RightEdge) !== 0
            readonly property bool onTop: (modelData.edges & Qt.TopEdge) !== 0
            readonly property bool onBottom: (modelData.edges & Qt.BottomEdge) !== 0
            readonly property bool isCorner: (onLeft || onRight) && (onTop || onBottom)
            z: 1001
            x: onRight ? shell.width - (isCorner ? corner : grip) : (onLeft ? 0 : corner)
            y: onBottom ? shell.height - (isCorner ? corner : grip) : (onTop ? 0 : corner)
            width: isCorner ? corner : (onLeft || onRight ? grip : shell.width - 2 * corner)
            height: isCorner ? corner : (onTop || onBottom ? grip : shell.height - 2 * corner)
            cursorShape: modelData.cursor
            acceptedButtons: Qt.LeftButton
            onPressed: studio.startWindowResize(modelData.edges)
        }
    }

    Gradient {
        id: currentTabFill
        GradientStop { position: 0.0; color: Qt.lighter(shell.cAccentSoft, 1.35) }
        GradientStop { position: 1.0; color: shell.cAccentSoft }
    }

    Component { id: scalarDelegate; ScalarRow { width: parent ? parent.width : 0; row: rowData } }
    Component { id: quietPeakDelegate; QuietPeakRow { width: parent ? parent.width : 0; row: rowData } }
    Component { id: switchDelegate; SwitchRow { width: parent ? parent.width : 0; row: rowData } }
    Component { id: choiceDelegate; ChoiceRow { width: parent ? parent.width : 0; row: rowData } }
    Component { id: countDelegate; CountRow { width: parent ? parent.width : 0; row: rowData } }
    Component { id: colourDelegate; ColourRow { width: parent ? parent.width : 0; row: rowData } }
    Component { id: gradientDelegate; GradientRow { width: parent ? parent.width : 0; row: rowData } }
}
