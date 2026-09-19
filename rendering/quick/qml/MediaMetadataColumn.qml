import QtQuick

// Event-driven Media Title/Artist/Album crossfade.
//
// Provider/model truth updates immediately. This presentation snapshots only the
// previous rendered strings, then crossfades old -> new text without a timer,
// provider delay or progress-driven cadence. Two tiny text columns exist only so
// track changes can overlap cleanly; steady state is static.
Item {
    id: metadataFade

    required property var mediaModel
    property real rowSpacing: 7.0
    property string textAlignment: "left"
    // One artist-line child record projects onto BOTH crossfade snapshots.
    // The Column still owns the authored row slot; moving the artist never
    // becomes another metadata layout, provider or persistence authority.
    property real artistOffsetX: 0.0
    property real artistOffsetY: 0.0
    property real artistScale: 1.0
    property string artistAlignment: textAlignment
    property alias artistEditTarget: currentArtistText

    property string _currentTitle: ""
    property string _currentArtist: ""
    property string _currentAlbum: ""
    property string _outgoingTitle: ""
    property string _outgoingArtist: ""
    property string _outgoingAlbum: ""
    property bool _componentReady: false
    property bool _outgoingVisible: false

    readonly property string sourceKey:
        String(mediaModel.title || "") + "\u001f"
        + String(mediaModel.artist || "") + "\u001f"
        + String(mediaModel.album || "")

    implicitHeight: Math.max(
        currentColumn.implicitHeight,
        _outgoingVisible ? outgoingColumn.implicitHeight : 0.0
    )
    height: implicitHeight

    function _syncWithoutAnimation() {
        _currentTitle = String(mediaModel.title || "")
        _currentArtist = String(mediaModel.artist || "")
        _currentAlbum = String(mediaModel.album || "")
        currentColumn.opacity = 1.0
        outgoingColumn.opacity = 0.0
        _outgoingVisible = false
    }

    function _beginMetadataCrossfade() {
        if (!_componentReady) {
            _syncWithoutAnimation()
            return
        }
        var nextTitle = String(mediaModel.title || "")
        var nextArtist = String(mediaModel.artist || "")
        var nextAlbum = String(mediaModel.album || "")
        if (nextTitle === _currentTitle
                && nextArtist === _currentArtist
                && nextAlbum === _currentAlbum) {
            return
        }

        _outgoingTitle = _currentTitle
        _outgoingArtist = _currentArtist
        _outgoingAlbum = _currentAlbum
        _currentTitle = nextTitle
        _currentArtist = nextArtist
        _currentAlbum = nextAlbum
        _outgoingVisible = _outgoingTitle.length > 0
            || _outgoingArtist.length > 0
            || _outgoingAlbum.length > 0

        metadataCrossfade.stop()
        outgoingColumn.opacity = _outgoingVisible ? 1.0 : 0.0
        currentColumn.opacity = 0.0
        metadataCrossfade.restart()
    }

    onSourceKeyChanged: _beginMetadataCrossfade()
    Component.onCompleted: {
        _syncWithoutAnimation()
        _componentReady = true
    }

    Column {
        id: currentColumn
        width: parent.width
        spacing: metadataFade.rowSpacing
        // Incoming metadata must paint above the outgoing snapshot so its fade-in
        // is visible immediately instead of being hidden under an opaque sibling.
        z: 1

        ShadowedText {
            objectName: "mediaTitle"
            width: currentColumn.width
            horizontalAlignment: metadataFade.textAlignment === "right"
                ? Text.AlignRight : Text.AlignLeft
            height: implicitHeight
            text: metadataFade._currentTitle
            color: metadataFade.mediaModel.textColor
            font.family: metadataFade.mediaModel.fontFamily
            font.pointSize: metadataFade.mediaModel.fontSize * 1.12
            font.bold: true
            wrap: false
            fontSizeMode: Text.HorizontalFit
            minimumPointSize: 6.0
            maximumLineCount: 1
            elide: Text.ElideRight
            shadowEnabled: metadataFade.mediaModel.textShadowEnabled
            shadowColor: metadataFade.mediaModel.textShadowColor
            shadowOffsetX: metadataFade.mediaModel.textShadowOffsetX
            shadowOffsetY: metadataFade.mediaModel.textShadowOffsetY
        }

        Item {
            id: currentArtistSlot
            width: currentColumn.width
            visible: metadataFade._currentArtist.length > 0
            height: visible ? currentArtistText.implicitHeight : 0.0

            ShadowedText {
                id: currentArtistText
                objectName: "mediaArtist"
                visible: currentArtistSlot.visible
                width: parent.width
                height: visible ? implicitHeight : 0.0
                transformOrigin: Item.TopLeft
                x: metadataFade.artistOffsetX
                y: metadataFade.artistOffsetY
                scale: metadataFade.artistScale
                horizontalAlignment: metadataFade.artistAlignment === "right"
                    ? Text.AlignRight : Text.AlignLeft
                text: metadataFade._currentArtist
                color: metadataFade.mediaModel.textColor
                opacity: 0.92
                font.family: metadataFade.mediaModel.fontFamily
                font.pointSize: metadataFade.mediaModel.fontSize
                font.bold: true
                wrap: false
                fontSizeMode: Text.HorizontalFit
                minimumPointSize: 6.0
                maximumLineCount: 1
                elide: Text.ElideRight
                shadowEnabled: metadataFade.mediaModel.textShadowEnabled
                shadowColor: metadataFade.mediaModel.textShadowColor
                shadowOffsetX: metadataFade.mediaModel.textShadowOffsetX
                shadowOffsetY: metadataFade.mediaModel.textShadowOffsetY
            }
        }

        ShadowedText {
            objectName: "mediaAlbum"
            visible: metadataFade.mediaModel.showAlbum && text.length > 0
            width: currentColumn.width
            horizontalAlignment: metadataFade.textAlignment === "right"
                ? Text.AlignRight : Text.AlignLeft
            height: visible ? implicitHeight : 0.0
            text: metadataFade._currentAlbum
            color: metadataFade.mediaModel.textColor
            opacity: 0.75
            font.family: metadataFade.mediaModel.fontFamily
            font.pointSize: metadataFade.mediaModel.fontSize * 0.82
            font.italic: true
            wrap: false
            fontSizeMode: Text.HorizontalFit
            minimumPointSize: 6.0
            maximumLineCount: 1
            elide: Text.ElideRight
            shadowEnabled: metadataFade.mediaModel.textShadowEnabled
            shadowColor: metadataFade.mediaModel.textShadowColor
            shadowOffsetX: metadataFade.mediaModel.textShadowOffsetX
            shadowOffsetY: metadataFade.mediaModel.textShadowOffsetY
        }
    }

    Column {
        id: outgoingColumn
        visible: metadataFade._outgoingVisible
        width: parent.width
        spacing: metadataFade.rowSpacing
        z: 0

        ShadowedText {
            width: outgoingColumn.width
            horizontalAlignment: metadataFade.textAlignment === "right"
                ? Text.AlignRight : Text.AlignLeft
            height: implicitHeight
            text: metadataFade._outgoingTitle
            color: metadataFade.mediaModel.textColor
            font.family: metadataFade.mediaModel.fontFamily
            font.pointSize: metadataFade.mediaModel.fontSize * 1.12
            font.bold: true
            wrap: false
            fontSizeMode: Text.HorizontalFit
            minimumPointSize: 6.0
            maximumLineCount: 1
            elide: Text.ElideRight
            shadowEnabled: metadataFade.mediaModel.textShadowEnabled
            shadowColor: metadataFade.mediaModel.textShadowColor
            shadowOffsetX: metadataFade.mediaModel.textShadowOffsetX
            shadowOffsetY: metadataFade.mediaModel.textShadowOffsetY
        }

        Item {
            id: outgoingArtistSlot
            width: outgoingColumn.width
            visible: metadataFade._outgoingArtist.length > 0
            height: visible ? outgoingArtistText.implicitHeight : 0.0

            ShadowedText {
                id: outgoingArtistText
                objectName: "mediaOutgoingArtist"
                visible: outgoingArtistSlot.visible
                width: parent.width
                height: visible ? implicitHeight : 0.0
                transformOrigin: Item.TopLeft
                x: metadataFade.artistOffsetX
                y: metadataFade.artistOffsetY
                scale: metadataFade.artistScale
                horizontalAlignment: metadataFade.artistAlignment === "right"
                    ? Text.AlignRight : Text.AlignLeft
                text: metadataFade._outgoingArtist
                color: metadataFade.mediaModel.textColor
                opacity: 0.92
                font.family: metadataFade.mediaModel.fontFamily
                font.pointSize: metadataFade.mediaModel.fontSize
                font.bold: true
                wrap: false
                fontSizeMode: Text.HorizontalFit
                minimumPointSize: 6.0
                maximumLineCount: 1
                elide: Text.ElideRight
                shadowEnabled: metadataFade.mediaModel.textShadowEnabled
                shadowColor: metadataFade.mediaModel.textShadowColor
                shadowOffsetX: metadataFade.mediaModel.textShadowOffsetX
                shadowOffsetY: metadataFade.mediaModel.textShadowOffsetY
            }
        }

        ShadowedText {
            visible: metadataFade.mediaModel.showAlbum && text.length > 0
            width: outgoingColumn.width
            horizontalAlignment: metadataFade.textAlignment === "right"
                ? Text.AlignRight : Text.AlignLeft
            height: visible ? implicitHeight : 0.0
            text: metadataFade._outgoingAlbum
            color: metadataFade.mediaModel.textColor
            opacity: 0.75
            font.family: metadataFade.mediaModel.fontFamily
            font.pointSize: metadataFade.mediaModel.fontSize * 0.82
            font.italic: true
            wrap: false
            fontSizeMode: Text.HorizontalFit
            minimumPointSize: 6.0
            maximumLineCount: 1
            elide: Text.ElideRight
            shadowEnabled: metadataFade.mediaModel.textShadowEnabled
            shadowColor: metadataFade.mediaModel.textShadowColor
            shadowOffsetX: metadataFade.mediaModel.textShadowOffsetX
            shadowOffsetY: metadataFade.mediaModel.textShadowOffsetY
        }
    }

    ParallelAnimation {
        id: metadataCrossfade
        NumberAnimation {
            target: outgoingColumn
            property: "opacity"
            from: 1.0
            to: 0.0
            duration: 240
            easing.type: Easing.InOutQuad
        }
        NumberAnimation {
            target: currentColumn
            property: "opacity"
            from: 0.0
            to: 1.0
            duration: 340
            easing.type: Easing.InOutQuad
        }
        onFinished: {
            outgoingColumn.opacity = 0.0
            metadataFade._outgoingVisible = false
            currentColumn.opacity = 1.0
        }
    }
}
