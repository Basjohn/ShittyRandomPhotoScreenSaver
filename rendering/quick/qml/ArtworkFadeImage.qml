import QtQuick

// Mandatory retained artwork primitive for dynamic artwork surfaces.
//
// Artwork changes fade through the existing frame/background instead of swapping
// one texture visibly. The two short NumberAnimations are event-driven and only
// run while a source changes; there is no polling timer or steady-state cadence.
// A single Image node remains resident, so the idle presentation cost is the same
// image texture/node class the family would otherwise own.
Item {
    id: fadeImage

    property string source: ""
    property int fillMode: Image.PreserveAspectCrop
    property bool asynchronous: true
    property bool cache: true
    property int fadeOutDuration: 140
    property int fadeInDuration: 240

    readonly property int status: image.status
    readonly property bool transitionVisible:
        _displayedSource.length > 0
        || _pendingSource.length > 0
        || fadeOut.running
        || fadeIn.running

    property string _displayedSource: ""
    property string _pendingSource: ""
    property bool _componentReady: false

    function _beginFadeInIfReady() {
        if (!_componentReady
                || _displayedSource.length === 0
                || _displayedSource !== _pendingSource
                || fadeOut.running
                || image.status !== Image.Ready) {
            return
        }
        fadeIn.stop()
        fadeIn.from = image.opacity
        fadeIn.to = 1.0
        fadeIn.restart()
    }

    function _commitPendingSource() {
        fadeOut.stop()
        fadeIn.stop()
        _displayedSource = _pendingSource
        image.opacity = 0.0
        if (_displayedSource.length === 0)
            return

        // Source/status binding settles on the next event turn. Qt.callLater is
        // a one-shot event deferral, not a recurring timer/poller.
        Qt.callLater(function() {
            fadeImage._beginFadeInIfReady()
        })
    }

    function _requestSource(value) {
        _pendingSource = String(value || "")
        if (!_componentReady)
            return

        if (_pendingSource === _displayedSource) {
            _beginFadeInIfReady()
            return
        }

        fadeIn.stop()
        if (_displayedSource.length > 0 && image.opacity > 0.001) {
            fadeOut.stop()
            fadeOut.from = image.opacity
            fadeOut.to = 0.0
            fadeOut.restart()
        } else {
            _commitPendingSource()
        }
    }

    onSourceChanged: _requestSource(source)
    Component.onCompleted: {
        _componentReady = true
        _requestSource(source)
    }

    Image {
        id: image
        anchors.fill: parent
        source: fadeImage._displayedSource
        fillMode: fadeImage.fillMode
        asynchronous: fadeImage.asynchronous
        cache: fadeImage.cache
        opacity: 0.0

        onStatusChanged: {
            if (status === Image.Ready)
                fadeImage._beginFadeInIfReady()
        }
    }

    NumberAnimation {
        id: fadeOut
        target: image
        property: "opacity"
        duration: fadeImage.fadeOutDuration
        easing.type: Easing.InOutQuad
        onFinished: fadeImage._commitPendingSource()
    }

    NumberAnimation {
        id: fadeIn
        target: image
        property: "opacity"
        duration: fadeImage.fadeInDuration
        easing.type: Easing.InOutQuad
    }
}
