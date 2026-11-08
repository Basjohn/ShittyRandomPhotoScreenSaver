import QtQuick
import QtQuick.Effects

// The Expanded Visualizer's full-display overlays (plan 01 §G, milestone M3b): the preset's name and Now Playing
// (Artist, Song and Artwork), each fading in and out gently on its own event.
//
// VisualizerPresentation.qml loads this only while the display-wide card is drawn (and the displays are on), so on
// every other display, and at any other time, none of it exists: no item, binding, animation or Media subscription.
// It lives inside the Visualizer card, so it fades with the card's own fade-through and the startup reveal, and
// paints below the card's controls (z), the OSD lane and the context menu.
//
// Sources, never a second one: the preset's display name (title-cased by Python at the activation edge), and the
// Media model the Visualizer's playback truth already binds (MediaPresentationModel: one coherent snapshot of
// title, artist and artwork, and the one artwork image provider). Media Controls emit transportRequested; Python
// routes it to the Media card's own transport owner.
//
// Events: entering the full display (once the startup reveal has opened), a preset announcement, a change of the
// track's identity. Nothing else reveals an overlay; nothing runs at rest.
//
// Fullscreen Edit (M3c): while ``editing`` (the Edit session is open on this display's overlays) both overlays show
// and hold, with a quiet placeholder where there is no preset name or track yet, so each can be grabbed; their
// geometry changes are reported through editGeometryChanged (Python re-reads the Edit frames: the preset toast, the
// Now Playing text block and its artwork). When Edit ends they return to their authored visibility with a fade.
Item {
    id: overlays
    objectName: "expandedVisualizerOverlays"

    // ---- inputs (VisualizerPresentation.qml binds them; the card's chrome is the one card-chrome owner's)
    property var config: ({})
    property string presetName: ""
    property int presetSerial: 0
    property var mediaModel: null
    // The OSD's foreground lane: a showing OSD keeps priority over an overlay beneath it.
    property Item osdHost: null
    // The generation's startup reveal has opened (a restore before reveal waits for it).
    property bool revealOpen: true
    property bool inputAdmitted: false
    // Fullscreen Edit is open on these overlays (M3c).
    property bool editing: false
    // The left edge of the column the card's right-hand controls occupy (the collapse glyph, its tip and the 3D hint
    // at the top; Reset Camera, the preset steps and their tips at the bottom). An overlay reaching into it keeps
    // clear of them vertically (the reserves below).
    property real rightControlsLeft: width
    property color borderColor: "#ffffffff"
    property real borderWidth: 4.0
    property real cornerRadius: 8.0
    property color cardColor: "#4c232323"
    property string surfaceMaterial: "normal"
    property var surfaceBackdrop: null
    property bool cardShadowEnabled: true
    property color cardShadowColor: "#96000000"
    property real cardShadowBlur: 18.0
    property real cardShadowOffsetX: 0.0
    property real cardShadowOffsetY: 4.0
    // How far down (top right) and up (bottom right) the card's own controls reach from its edges.
    property real topRightReserve: 0.0
    property real bottomRightReserve: 0.0

    signal transportRequested(string key)
    // Fullscreen Edit: an overlay's (or a part's) geometry changed; only emitted while editing.
    signal editGeometryChanged()
    function noteEditGeometry() {
        if (editing)
            editGeometryChanged()
    }

    // ---- options (Settings: Visualizers -> Fullscreen Mode; widgets.spotify_visualizer.fullscreen_overlays)
    readonly property var presetOptions: config && config.preset ? config.preset : ({})
    readonly property var nowPlayingOptions: config && config.nowPlaying ? config.nowPlaying : ({})
    readonly property string fontFamily: config && config.fontFamily ? String(config.fontFamily) : "Inter"
    readonly property real fontSize: config && Number(config.fontSize) > 0 ? Number(config.fontSize) : 30.0
    readonly property color cardTextColor: config && config.cardTextColor ? config.cardTextColor : "#ffffffff"

    // ---- the safe area: the card's interior, inset by its border and a margin that grows with the display
    readonly property real safeInset: Math.round(Math.max(24.0, Math.min(width, height) * 0.025)) + borderWidth
    readonly property real safeWidth: Math.max(0.0, width - 2.0 * safeInset)
    readonly property real safeHeight: Math.max(0.0, height - 2.0 * safeInset)
    readonly property real stackGap: Math.round(Math.max(10.0, fontSize * 0.45))

    // ---- legibility: a soft shadow under the white text (the bright-area black switch is a recorded follow-up)
    readonly property color textShadowColor: "#d9000000"
    readonly property real textShadowOffset: 5.0

    property int revealCounter: 0
    function nextRevealOrder() {
        revealCounter += 1
        return revealCounter
    }

    // A showing overlay in the same corner as ``slot`` (it would have to make room).
    function cornerPeerShowing(slot) {
        const peers = [presetSlot, nowPlayingSlot]
        for (let i = 0; i < peers.length; ++i) {
            const peer = peers[i]
            if (peer !== slot && peer.corner === slot.corner && peer.shown && peer.presence > 0.001)
                return true
        }
        return false
    }

    // Whether a showing OSD overlaps ``slot`` (reads the OSD roots' geometry and fade, so it updates on their edges).
    function osdCovers(slot) {
        const host = osdHost
        if (!host || !slot)
            return false
        const left = slot.x, top = slot.y, right = slot.x + slot.width, bottom = slot.y + slot.height
        const roots = host.children
        for (let i = 0; i < roots.length; ++i) {
            const osd = roots[i]
            if (!osd.visible || osd.opacity <= 0.0 || osd.width <= 0.0 || osd.height <= 0.0)
                continue
            const osdX = osd.x, osdY = osd.y   // read, so a moved OSD re-evaluates the binding
            const rect = overlays.mapFromItem(osd, 0, 0, osd.width, osd.height)
            if (rect.x < right && left < rect.x + rect.width && rect.y < bottom && top < rect.y + rect.height)
                return true
        }
        return false
    }

    // Stacking: two overlays in one corner stack without overlapping, the newer nearer the corner's edge.
    function stackShiftFor(slot, peer) {
        return peer.corner === slot.corner && peer.shown && peer.order > slot.order ? peer.height + stackGap : 0.0
    }

    // ---- events
    readonly property string liveTrackKey: mediaModel && mediaModel.hasTrack
        ? String(mediaModel.artist) + "\u001f" + String(mediaModel.title) : ""
    property bool entered: false

    function enter() {
        if (entered || !revealOpen)
            return
        entered = true
        if (presetName.length > 0 || editing)
            presetSlot.reveal()
        if (liveTrackKey.length > 0 || editing)
            nowPlayingSlot.reveal()
    }

    Component.onCompleted: enter()
    onRevealOpenChanged: enter()
    onPresetSerialChanged: {
        if (entered && (presetName.length > 0 || editing))
            presetSlot.reveal()
    }
    onLiveTrackKeyChanged: {
        if (!entered)
            return
        if (liveTrackKey.length > 0 || editing)
            nowPlayingSlot.reveal()
        else
            nowPlayingSlot.conceal()
    }
    onEditingChanged: {
        if (!entered)
            return
        if (editing) {
            presetSlot.reveal()
            nowPlayingSlot.reveal()
            noteEditGeometry()
        } else {
            presetSlot.endEdit(presetName.length > 0)
            nowPlayingSlot.endEdit(liveTrackKey.length > 0)
        }
    }

    // Fullscreen Edit's placeholders where there is nothing to show yet (Title Case, quiet).
    readonly property string editPresetPlaceholder: "Preset Name"
    readonly property string editTitlePlaceholder: "Track Title"
    readonly property string editArtistPlaceholder: "Artist"

    // ------------------------------------------------------------------------------------------ preset toast
    ExpandedOverlaySlot {
        id: presetSlot
        objectName: "expandedOverlayPreset"
        stage: overlays
        options: overlays.presetOptions
        defaultCorner: "top_left"
        fadeInMs: 700
        holdMs: 2600
        fadeOutMs: 1400
        swapOutMs: 420
        swapInMs: 560
        stackShift: overlays.stackShiftFor(presetSlot, nowPlayingSlot)
        naturalWidth: Math.min(Math.ceil(presetText.implicitWidth), maxContentWidth)
        naturalHeight: Math.ceil(presetText.implicitHeight)
        property string contentText: ""
        onSwapContent: contentText = overlays.presetName.length > 0 || !overlays.editing
            ? overlays.presetName : overlays.editPresetPlaceholder

        ShadowedText {
            id: presetText
            objectName: "expandedOverlayPresetText"
            width: presetSlot.naturalWidth
            text: presetSlot.contentText
            font.family: overlays.fontFamily
            font.pixelSize: Math.max(1, Math.round(presetSlot.fontSize))
            font.weight: Font.DemiBold
            color: presetSlot.textColor
            elide: Text.ElideRight
            horizontalAlignment: presetSlot.rightSide ? Text.AlignRight : Text.AlignLeft
            shadowSoft: true
            shadowColor: overlays.textShadowColor
            shadowOffsetX: 0.0
            shadowOffsetY: overlays.textShadowOffset
        }
    }

    // ------------------------------------------------------------------------------------------- Now Playing
    ExpandedOverlaySlot {
        id: nowPlayingSlot
        objectName: "expandedOverlayNowPlaying"
        stage: overlays
        options: overlays.nowPlayingOptions
        defaultCorner: "bottom_left"
        // Very gentle (operator, 8 Nov).
        fadeInMs: 1300
        holdMs: 5200
        fadeOutMs: 2000
        swapOutMs: 700
        swapInMs: 900
        stackShift: overlays.stackShiftFor(nowPlayingSlot, presetSlot)
        naturalWidth: artSize + gap + textColumn.width
        naturalHeight: Math.max(artSize, textColumn.height)

        readonly property bool controlsShown: options.mediaControls === true
        // Square artwork as tall as the text beside it (with Media Controls too), never smaller than its own size,
        // times its own size factor (Fullscreen Edit sizes the artwork apart from the text; it stays beside it).
        readonly property real artworkScale: {
            const value = Number(options.artworkScale)
            return isFinite(value) && value > 0 ? Math.max(0.5, Math.min(3.0, value)) : 1.0
        }
        readonly property real artSize: Math.round(Math.max(Math.round(fontSize * 3.1), Math.ceil(textColumn.height))
                                                   * artworkScale)
        readonly property real gap: Math.round(fontSize * 0.55)
        readonly property real textWidthLimit: Math.max(48.0, maxContentWidth - artSize - gap)
        readonly property bool playing: !!overlays.mediaModel
            && String(overlays.mediaModel.playbackState).toLowerCase() === "playing"

        // The latched track (swapped only while the content is invisible, so text and artwork always belong together).
        property string contentKey: ""
        property string contentTitle: ""
        property string contentArtist: ""
        onSwapContent: {
            const model = overlays.mediaModel
            contentKey = overlays.liveTrackKey
            const placeholder = contentKey.length === 0 && overlays.editing
            contentTitle = placeholder ? overlays.editTitlePlaceholder : (model ? String(model.title) : "")
            contentArtist = placeholder ? overlays.editArtistPlaceholder : (model ? String(model.artist) : "")
        }
        // Identity fence: the model's artwork is shown only for the latched track, never under another's text.
        readonly property string artSource: contentKey.length > 0 && contentKey === overlays.liveTrackKey
            && !!overlays.mediaModel ? String(overlays.mediaModel.artworkSource) : ""

        Item {
            id: artFrame
            objectName: "expandedOverlayArtwork"
            width: nowPlayingSlot.artSize
            height: nowPlayingSlot.artSize
            x: nowPlayingSlot.rightSide ? parent.width - width : 0.0
            y: (parent.height - height) / 2.0
            readonly property real imageInset: Math.max(0.75, overlays.borderWidth * 0.65)
            onXChanged: overlays.noteEditGeometry()
            onYChanged: overlays.noteEditGeometry()
            onWidthChanged: overlays.noteEditGeometry()

            RectangularShadow {
                anchors.fill: parent
                radius: overlays.cornerRadius
                color: "#73000000"
                blur: 14.0
                offset: Qt.vector2d(0.0, 3.0)
                cached: true
                z: -1
            }
            // Missing artwork: the theme's own geometry (the card surface with a quiet note), under the image.
            Rectangle {
                objectName: "expandedOverlayArtworkFallback"
                anchors.fill: parent
                radius: overlays.cornerRadius
                color: overlays.cardColor
            }
            Canvas {
                id: noteGlyph
                anchors.centerIn: parent
                width: Math.round(parent.width * 0.42)
                height: width
                readonly property color ink: Qt.rgba(overlays.borderColor.r, overlays.borderColor.g,
                                                     overlays.borderColor.b, 0.55)
                onInkChanged: requestPaint()
                onWidthChanged: requestPaint()
                onPaint: {
                    const ctx = getContext("2d")
                    ctx.reset()
                    const s = width
                    ctx.strokeStyle = ink
                    ctx.fillStyle = ink
                    ctx.lineWidth = Math.max(1.5, s * 0.075)
                    ctx.lineCap = "round"
                    ctx.lineJoin = "round"
                    ctx.beginPath()
                    ctx.moveTo(s * 0.36, s * 0.74)
                    ctx.lineTo(s * 0.36, s * 0.16)
                    ctx.lineTo(s * 0.86, s * 0.06)
                    ctx.lineTo(s * 0.86, s * 0.64)
                    ctx.stroke()
                    ctx.beginPath()
                    ctx.ellipse(s * 0.10, s * 0.64, s * 0.28, s * 0.22)
                    ctx.ellipse(s * 0.60, s * 0.54, s * 0.28, s * 0.22)
                    ctx.fill()
                }
            }
            ArtworkFadeImage {
                id: artwork
                objectName: "expandedOverlayArtworkImage"
                anchors.fill: parent
                anchors.margins: artFrame.imageInset
                source: nowPlayingSlot.artSource
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: true
                // Rounded containment (Contracts: rounded artwork frames): a concentric mask, the outline on top.
                layer.enabled: overlays.cornerRadius > 0.0
                layer.effect: MultiEffect {
                    maskEnabled: true
                    maskSource: artworkMask
                }
            }
            Rectangle {
                id: artworkMask
                anchors.fill: artwork
                radius: Math.max(0.0, overlays.cornerRadius - artFrame.imageInset)
                visible: false
                layer.enabled: true
            }
            // The themed card border: colour, the shared Card Border Width and the card radius.
            Rectangle {
                objectName: "expandedOverlayArtworkBorder"
                anchors.fill: parent
                radius: overlays.cornerRadius
                color: "transparent"
                border.width: overlays.borderWidth
                border.color: overlays.borderColor
            }
        }

        Column {
            id: textColumn
            objectName: "expandedOverlayNowPlayingText"
            x: nowPlayingSlot.rightSide ? 0.0 : nowPlayingSlot.artSize + nowPlayingSlot.gap
            y: (parent.height - height) / 2.0
            width: Math.min(nowPlayingSlot.textWidthLimit,
                            Math.ceil(Math.max(titleText.implicitWidth, artistText.implicitWidth,
                                               controls.visible ? controls.width : 0.0)))
            spacing: Math.round(nowPlayingSlot.fontSize * 0.12)
            onXChanged: overlays.noteEditGeometry()
            onYChanged: overlays.noteEditGeometry()
            onWidthChanged: overlays.noteEditGeometry()
            onHeightChanged: overlays.noteEditGeometry()

            ShadowedText {
                id: titleText
                objectName: "expandedOverlayTitle"
                width: textColumn.width
                text: nowPlayingSlot.contentTitle
                font.family: overlays.fontFamily
                font.pixelSize: Math.max(1, Math.round(nowPlayingSlot.fontSize))
                font.weight: Font.DemiBold
                color: nowPlayingSlot.textColor
                elide: Text.ElideRight
                horizontalAlignment: nowPlayingSlot.rightSide ? Text.AlignRight : Text.AlignLeft
                shadowSoft: true
                shadowColor: overlays.textShadowColor
                shadowOffsetX: 0.0
                shadowOffsetY: overlays.textShadowOffset
            }
            ShadowedText {
                id: artistText
                objectName: "expandedOverlayArtist"
                width: textColumn.width
                text: nowPlayingSlot.contentArtist
                font.family: overlays.fontFamily
                font.pixelSize: Math.max(1, Math.round(nowPlayingSlot.fontSize * 0.74))
                color: nowPlayingSlot.textColor
                opacity: 0.88
                elide: Text.ElideRight
                horizontalAlignment: nowPlayingSlot.rightSide ? Text.AlignRight : Text.AlignLeft
                shadowSoft: true
                shadowColor: overlays.textShadowColor
                shadowOffsetX: 0.0
                shadowOffsetY: overlays.textShadowOffset
            }
            // Media Controls (default off): previous / play-pause / next on the Media card's own transport owner.
            Item {
                width: textColumn.width
                height: controls.visible ? Math.round(nowPlayingSlot.fontSize * 0.25) : 0.0
                visible: controls.visible
            }
            Row {
                id: controls
                objectName: "expandedOverlayMediaControls"
                visible: nowPlayingSlot.controlsShown
                x: nowPlayingSlot.rightSide ? textColumn.width - width : 0.0
                spacing: Math.round(nowPlayingSlot.fontSize * 0.35)

                Repeater {
                    model: ["previous", "play", "next"]
                    delegate: Rectangle {
                        id: control
                        required property string modelData
                        objectName: "expandedOverlayTransport_" + modelData
                        readonly property var model: overlays.mediaModel
                        readonly property bool available: !!model && (modelData === "previous" ? model.canPrevious
                            : modelData === "next" ? model.canNext : model.canPlayPause)
                        width: Math.round(nowPlayingSlot.fontSize * 1.3)
                        height: width
                        radius: width / 2.0
                        // The card's in-card control look (Reset Camera, the preset steps).
                        color: "#bb20262c"
                        border.width: 1
                        border.color: "#c2ffffff"
                        opacity: !available ? 0.35 : (tap.enabled ? 1.0 : 0.68)
                        scale: tap.pressed ? 1.10 : (tap.containsMouse && tap.enabled ? 1.06 : 1.0)

                        MediaTransportGlyph {
                            anchors.centerIn: parent
                            width: Math.round(control.width * 0.52)
                            kind: control.modelData === "play" ? (nowPlayingSlot.playing ? "pause" : "play")
                                                               : control.modelData
                            glyphColor: "#ffffffff"
                        }
                        MouseArea {
                            id: tap
                            anchors.fill: parent
                            enabled: nowPlayingSlot.interactive && control.available
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            propagateComposedEvents: false
                            onPressed: function(mouse) { mouse.accepted = true }
                            // An in-card control consumes every press of its own, a double-click's second included.
                            readonly property bool consumesDoubleClick: true   // QuickDisplayWindow._double_click_owned_by_control
                            onDoubleClicked: function(mouse) { mouse.accepted = true }
                            onClicked: function(mouse) {
                                mouse.accepted = true
                                overlays.transportRequested(control.modelData)
                            }
                        }
                    }
                }
            }
        }
    }
}
