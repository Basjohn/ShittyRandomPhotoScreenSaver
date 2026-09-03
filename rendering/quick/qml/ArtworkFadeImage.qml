import QtQuick

// Mandatory retained artwork primitive for dynamic artwork surfaces.
//
// Source replacement is a two-buffer, readiness-gated fade-in. The currently
// displayed texture stays untouched until the incoming Image reports Ready, so a
// provider/source change can never expose an empty frame while the next texture
// decodes. Rapid source churn is coalesced by replacing only the inactive buffer;
// the visible buffer remains stable. No Timer, polling loop or steady-state
// animation exists: work begins only from source/status events and stops after the
// short transition. The inactive Image has an empty source at idle, so it retains
// no second artwork texture between transitions.
Item {
    id: fadeImage

    property string source: ""
    property int fillMode: Image.PreserveAspectCrop
    property bool asynchronous: true
    property bool cache: true
    property int fadeOutDuration: 200
    property int fadeInDuration: 340

    property string _displayedSource: ""
    property string _pendingSource: ""
    property string _sourceA: ""
    property string _sourceB: ""
    property int _activeIndex: 0
    property bool _componentReady: false

    readonly property int status: _pendingSource.length > 0
        ? _inactiveImage().status
        : (_displayedSource.length > 0 ? _activeImage().status : Image.Null)
    readonly property bool transitionVisible:
        _displayedSource.length > 0
        || _pendingSource.length > 0
        || fadeIn.running
        || fadeOut.running

    function _activeImage() {
        return _activeIndex === 0 ? imageA : imageB
    }

    function _inactiveImage() {
        return _activeIndex === 0 ? imageB : imageA
    }

    function _inactiveIndex() {
        return _activeIndex === 0 ? 1 : 0
    }

    function _sourceFor(index) {
        return index === 0 ? _sourceA : _sourceB
    }

    function _setSource(index, value) {
        if (index === 0)
            _sourceA = value
        else
            _sourceB = value
    }

    function _cancelIncoming() {
        fadeIn.stop()
        const index = _inactiveIndex()
        const incoming = _inactiveImage()
        incoming.opacity = 0.0
        _setSource(index, "")
        _pendingSource = ""
    }

    function _beginFadeInIfReady() {
        if (!_componentReady || _pendingSource.length === 0 || fadeOut.running)
            return

        const index = _inactiveIndex()
        const incoming = _inactiveImage()
        if (_sourceFor(index) !== _pendingSource || incoming.status !== Image.Ready)
            return
        if (fadeIn.running && fadeIn.target === incoming)
            return
        if (fadeImage.fadeInDuration <= 0) {
            incoming.opacity = 1.0
            _commitIncoming()
            return
        }

        fadeIn.stop()
        fadeIn.target = incoming
        fadeIn.from = incoming.opacity
        fadeIn.to = 1.0
        fadeIn.restart()
    }

    function _commitIncoming() {
        if (_pendingSource.length === 0)
            return

        const oldIndex = _activeIndex
        const newIndex = _inactiveIndex()
        const oldImage = _activeImage()
        const incoming = _inactiveImage()
        if (_sourceFor(newIndex) !== _pendingSource || incoming.status !== Image.Ready)
            return

        // Incoming is fully opaque here. Retire the old texture only after the
        // replacement has covered it, then make the incoming buffer authoritative.
        incoming.opacity = 1.0
        oldImage.opacity = 0.0
        _setSource(oldIndex, "")
        _displayedSource = _pendingSource
        _pendingSource = ""
        _activeIndex = newIndex
    }

    function _clearDisplayed() {
        const oldIndex = _activeIndex
        const active = _activeImage()
        active.opacity = 0.0
        _setSource(oldIndex, "")
        _displayedSource = ""
    }

    // Raise a continuous-frame pacer demand while a fade runs, event-driven, so
    // the threaded scene renders the crossfade instead of only its first/last
    // frame. `typeof` guard keeps smoke hosts/tests that lack the context object
    // working. See rendering/quick/widget_frame_demand.py.
    function _demandFrames(anim, on) {
        if (typeof widgetFrameDemand !== 'undefined' && widgetFrameDemand)
            widgetFrameDemand.setAnimationActive(anim, on)
    }

    function _requestSource(value) {
        const requested = String(value || "")
        if (!_componentReady) {
            _pendingSource = requested
            return
        }

        if (requested === _displayedSource) {
            if (_pendingSource.length > 0)
                _cancelIncoming()
            if (fadeOut.running) {
                // A transient empty-source publication was withdrawn before the
                // visible texture retired. Recover opacity smoothly instead of
                // flashing the same artwork back to fully opaque.
                fadeOut.stop()
                const active = _activeImage()
                fadeIn.stop()
                fadeIn.target = active
                fadeIn.from = active.opacity
                fadeIn.to = 1.0
                fadeIn.restart()
            }
            return
        }

        // A newer non-empty source supersedes any in-flight incoming texture.
        // The active texture is never modified while the replacement decodes.
        if (requested.length > 0) {
            fadeOut.stop()
            fadeIn.stop()
            const index = _inactiveIndex()
            const incoming = _inactiveImage()
            incoming.opacity = 0.0
            _pendingSource = requested
            _setSource(index, requested)
            // Image.status is the sole readiness event. Do not sample status
            // synchronously here: a binding can still report Ready for the old
            // inactive source in the same turn that its URL is replaced.
            return
        }

        _cancelIncoming()
        if (_displayedSource.length === 0)
            return

        const active = _activeImage()
        fadeOut.stop()
        fadeOut.target = active
        fadeOut.from = active.opacity
        fadeOut.to = 0.0
        if (fadeImage.fadeOutDuration <= 0) {
            _clearDisplayed()
        } else {
            fadeOut.restart()
        }
    }

    onSourceChanged: _requestSource(source)
    Component.onCompleted: {
        _componentReady = true
        _requestSource(source)
    }

    Image {
        id: imageA
        anchors.fill: parent
        source: fadeImage._sourceA
        fillMode: fadeImage.fillMode
        asynchronous: fadeImage.asynchronous
        cache: fadeImage.cache
        opacity: 0.0

        onStatusChanged: {
            if (status === Image.Ready)
                fadeImage._beginFadeInIfReady()
        }
    }

    Image {
        id: imageB
        anchors.fill: parent
        source: fadeImage._sourceB
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
        id: fadeIn
        property: "opacity"
        duration: fadeImage.fadeInDuration
        easing.type: Easing.InOutQuad
        onFinished: fadeImage._commitIncoming()
        onRunningChanged: fadeImage._demandFrames(fadeIn, running)
    }

    NumberAnimation {
        id: fadeOut
        property: "opacity"
        duration: fadeImage.fadeOutDuration
        easing.type: Easing.InOutQuad
        onFinished: fadeImage._clearDisplayed()
        onRunningChanged: fadeImage._demandFrames(fadeOut, running)
    }
}
