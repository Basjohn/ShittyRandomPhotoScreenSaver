import QtQuick

// Shared retained refresh presentation. Provider/runtime work owns only BUSY/IDLE;
// this glyph joins the display's one short transition epoch on each state edge.
// No animation, timer, or cadence owner lives in this component.
Item {
    id: refreshStateGlyph

    property bool busy: false
    property var transitionClock: null
    property bool hovered: false
    property bool canActivate: true
    property color glyphColor: "white"
    property string fontFamily: ""
    property bool bold: false
    property real restOpacity: 0.7
    property bool shadowEnabled: false
    property color shadowColor: "transparent"
    property real shadowOffsetX: 0.0
    property real shadowOffsetY: 0.0

    property bool _initialized: false
    property bool _currentBusy: false
    property bool _outgoingBusy: false
    property int _transitionEpoch: -1
    property real _joinPhase: 1.0

    function stateGlyph(value) {
        return value ? "◌" : "↻"
    }

    function beginEdge(nextBusy) {
        _outgoingBusy = _currentBusy
        _currentBusy = nextBusy
        if (transitionClock === null || transitionClock === undefined
                || transitionClock.begin === undefined) {
            _transitionEpoch = -1
            _joinPhase = 1.0
            return
        }
        const edge = transitionClock.begin()
        _transitionEpoch = Number(edge.epoch)
        _joinPhase = Math.max(0.0, Math.min(1.0, Number(edge.phase)))
    }

    readonly property real transitionProgress: {
        if (!_initialized || _transitionEpoch < 0
                || transitionClock === null || transitionClock === undefined
                || Number(transitionClock.epoch) !== _transitionEpoch)
            return 1.0
        const phase = Math.max(0.0, Math.min(1.0, Number(transitionClock.phase)))
        const remaining = 1.0 - _joinPhase
        if (remaining <= 0.000001)
            return 1.0
        return Math.max(0.0, Math.min(1.0, (phase - _joinPhase) / remaining))
    }
    readonly property real presentationOpacity:
        hovered && canActivate ? 1.0 : restOpacity

    Component.onCompleted: {
        _currentBusy = busy
        _outgoingBusy = busy
        _initialized = true
    }
    onBusyChanged: {
        if (_initialized && busy !== _currentBusy)
            beginEdge(busy)
    }

    ShadowedText {
        anchors.fill: parent
        text: refreshStateGlyph.stateGlyph(refreshStateGlyph._outgoingBusy)
        textFormat: Text.PlainText
        opacity: refreshStateGlyph.presentationOpacity
            * (1.0 - refreshStateGlyph.transitionProgress)
        color: refreshStateGlyph.hovered && refreshStateGlyph.canActivate
            ? "white" : refreshStateGlyph.glyphColor
        font.family: refreshStateGlyph.fontFamily
        font.pixelSize: Math.min(parent.width, parent.height) * 0.72
        font.bold: refreshStateGlyph.bold
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        shadowEnabled: refreshStateGlyph.shadowEnabled
        shadowColor: refreshStateGlyph.shadowColor
        shadowOffsetX: refreshStateGlyph.shadowOffsetX
        shadowOffsetY: refreshStateGlyph.shadowOffsetY
    }

    ShadowedText {
        anchors.fill: parent
        text: refreshStateGlyph.stateGlyph(refreshStateGlyph._currentBusy)
        textFormat: Text.PlainText
        opacity: refreshStateGlyph.presentationOpacity
            * refreshStateGlyph.transitionProgress
        color: refreshStateGlyph.hovered && refreshStateGlyph.canActivate
            ? "white" : refreshStateGlyph.glyphColor
        font.family: refreshStateGlyph.fontFamily
        font.pixelSize: Math.min(parent.width, parent.height) * 0.72
        font.bold: refreshStateGlyph.bold
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        shadowEnabled: refreshStateGlyph.shadowEnabled
        shadowColor: refreshStateGlyph.shadowColor
        shadowOffsetX: refreshStateGlyph.shadowOffsetX
        shadowOffsetY: refreshStateGlyph.shadowOffsetY
    }
}
