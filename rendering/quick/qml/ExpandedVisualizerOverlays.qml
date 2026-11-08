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
// track's identity, and playback resuming (paused -> playing: Now Playing shows again, as on a track change; operator,
// 8 Nov), and with Now Playing's Show On Hover the pointer arriving where it is placed (a HoverHandler edge; it holds
// while the pointer rests and fades after it leaves). Nothing else reveals an overlay; nothing runs at rest.
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
    // The Media card's transport bar look (MediaPresentationModel.transportBarLook: one JSON object of plain values,
    // colour names; a string, so nothing here holds a reference into the model), or ``fallback`` without a model.
    readonly property var mediaBarLook: {
        const text = mediaModel ? mediaModel.transportBarLook : undefined
        return typeof text === "string" && text.length > 0 ? JSON.parse(text) : ({})
    }
    function mediaLook(name, fallback) {
        const value = mediaBarLook[name]
        return value === undefined || value === null ? fallback : value
    }
    // Fullscreen Edit: an overlay's (or a part's) geometry changed; only emitted while editing.
    signal editGeometryChanged()
    // The Volume OSD's placement over the expanded card (``volume_osd``) depends on the safe area and on the OSD being
    // in its lane: Python (the scene controller) re-places it on these edges only.
    signal volumeOsdPlacementChanged()
    onSafeInsetChanged: volumeOsdPlacementChanged()
    onSafeWidthChanged: volumeOsdPlacementChanged()
    onSafeHeightChanged: volumeOsdPlacementChanged()
    Connections {
        target: overlays.osdHost
        function onChildrenChanged() { overlays.volumeOsdPlacementChanged() }
    }
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
    // The Media model's own playback state (the one the Visualizer binds); its paused -> playing edge is an event.
    readonly property string livePlaybackState: mediaModel ? String(mediaModel.playbackState).toLowerCase() : ""
    property string seenPlaybackState: ""

    function enter() {
        if (entered || !revealOpen)
            return
        entered = true
        if (presetName.length > 0 || editing)
            presetSlot.reveal()
        if (liveTrackKey.length > 0 || editing)
            nowPlayingSlot.reveal()
    }

    Component.onCompleted: {
        seenPlaybackState = livePlaybackState
        enter()
    }
    onLivePlaybackStateChanged: {
        const previous = seenPlaybackState
        seenPlaybackState = livePlaybackState
        // Playback resumed: Now Playing shows again with its gentle fade (one-shot from this edge, latest wins, the
        // same bounded window as a track change). Already up (Always Show, or still showing) it stays as it is.
        if (entered && previous === "paused" && livePlaybackState === "playing" && liveTrackKey.length > 0)
            nowPlayingSlot.resume()
    }
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
        // A set text width replaces the natural one (the name elides in it); a set height is at least one line and
        // gives the name as many lines as fit (it wraps, then elides). Unset, it is one line at its natural width.
        readonly property real lineHeight: Math.max(1.0, Math.ceil(presetMetrics.height))
        readonly property real boxWidth: setTextWidth > 0.0
            ? Math.round(Math.min(maxBoxWidth, Math.max(minimumTextWidth, setTextWidth))) : 0.0
        readonly property real boxHeight: setTextHeight > 0.0
            ? Math.round(Math.min(maxBoxHeight, Math.max(lineHeight, setTextHeight))) : 0.0
        readonly property int lineCount: boxHeight > 0.0 ? Math.max(1, Math.floor((boxHeight + 0.5) / lineHeight)) : 1
        naturalWidth: boxWidth > 0.0 ? boxWidth : Math.min(Math.ceil(presetText.implicitWidth), maxContentWidth)
        naturalHeight: boxHeight > 0.0 ? boxHeight : Math.ceil(presetText.implicitHeight)
        property string contentText: ""
        onSwapContent: contentText = overlays.presetName.length > 0 || !overlays.editing
            ? overlays.presetName : overlays.editPresetPlaceholder

        FontMetrics {
            id: presetMetrics
            font: presetText.effectiveFont
        }
        ShadowedText {
            id: presetText
            objectName: "expandedOverlayPresetText"
            width: presetSlot.naturalWidth
            height: presetSlot.boxHeight > 0.0 ? presetSlot.boxHeight : implicitHeight
            text: presetSlot.contentText
            font.family: overlays.fontFamily
            font.pixelSize: Math.max(1, Math.round(presetSlot.fontSize))
            font.weight: Font.DemiBold
            color: presetSlot.textColor
            elide: Text.ElideRight
            wrap: presetSlot.lineCount > 1
            breakLongWords: true
            maximumLineCount: presetSlot.lineCount
            verticalAlignment: Text.AlignVCenter
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
        naturalWidth: artWidth + gap + textBlock.width
        naturalHeight: Math.max(artHeight, textBlock.height)

        readonly property bool controlsShown: options.mediaControls === true
        // Media Controls: the Media card's transport bar, small. The card's bar is 2.15 x its font size tall under a
        // title of 1.12 x that size in points (1.12 x 4/3 px): bar / title = 2.15 / 1.4933 = 1.44. Here the bar keeps
        // that ratio to Now Playing's artist line (0.74 x the title), the line it sits under, so it is the card's bar
        // in proportion but smaller than the text block's headline. Compact: segments twice as wide as the bar is tall
        // (the card's run the card's width), which keeps the card's glyph box (half the bar's height).
        readonly property real controlsHeight: Math.max(16.0, Math.round(fontSize * 0.74 * 1.44))
        readonly property real controlsWidth: Math.round(controlsHeight * 6.0) + 2.0
        // The bar's size against the Media card's own bar (its outline, radius and shadow scale by this).
        readonly property real controlsFactor: controlsHeight / Math.max(
            38.0, overlays.mediaLook("fontSize", 17.0) * 2.15)
        function factor(raw) {
            const value = Number(raw)
            return isFinite(value) && value > 0 ? Math.max(0.5, Math.min(3.0, value)) : 1.0
        }
        // Square artwork as tall as the text beside it (with Media Controls too), never smaller than its own size,
        // times its own size factor (Fullscreen Edit sizes the artwork apart from the text; it stays beside it). Its
        // width and height factors (Fullscreen Edit's side handles) make the frame non-square; the image crops into it.
        readonly property real artworkScale: factor(options.artworkScale)
        readonly property real artworkWidthFactor: factor(options.artworkWidth)
        readonly property real artworkHeightFactor: factor(options.artworkHeight)
        // The text block's height with a one-line title (Media Controls included): what the artwork's size follows,
        // so a set text height (more title lines) never resizes the artwork.
        readonly property real titleLineHeight: Math.max(1.0, Math.ceil(titleMetrics.height))
        readonly property real naturalTextHeight: titleLineHeight + textColumn.spacing + Math.ceil(artistText.implicitHeight)
            + (controlsShown ? 2.0 * textColumn.spacing + controlsSpacer.height + controlsHeight : 0.0)
        readonly property real artBase: Math.max(Math.round(fontSize * 3.1),
                                                 Math.ceil(boxHeight > 0.0 ? naturalTextHeight : textColumn.height))
        readonly property real artWidth: Math.round(artBase * artworkScale * artworkWidthFactor)
        readonly property real artHeight: Math.round(artBase * artworkScale * artworkHeightFactor)
        readonly property real gap: Math.round(fontSize * 0.55)
        readonly property real textWidthLimit: Math.max(48.0, maxContentWidth - artWidth - gap)
        // The text block: a set width replaces the natural one (every line elides in it; never narrower than the
        // Media Controls); a set height is at least the natural block and gives the title the extra lines that fit
        // (it wraps, then elides), the block centred in it. Unset, it is today's block.
        readonly property real naturalTextWidth: Math.min(textWidthLimit,
            Math.ceil(Math.max(titleText.implicitWidth, artistText.implicitWidth, controlsShown ? controlsWidth : 0.0)))
        readonly property real boxWidth: setTextWidth > 0.0
            ? Math.round(Math.min(Math.max(1.0, maxBoxWidth - artWidth - gap),
                                  Math.max(minimumTextWidth, controlsShown ? controlsWidth : 0.0, setTextWidth)))
            : 0.0
        readonly property real boxHeight: setTextHeight > 0.0
            ? Math.round(Math.min(maxBoxHeight, Math.max(naturalTextHeight, setTextHeight))) : 0.0
        readonly property int titleLines: boxHeight > 0.0
            ? 1 + Math.max(0, Math.floor((boxHeight - naturalTextHeight + 0.5) / titleLineHeight)) : 1
        readonly property bool playing: !!overlays.mediaModel
            && String(overlays.mediaModel.playbackState).toLowerCase() === "playing"

        // ---- Its parts as children of the block (Fullscreen Edit's child editing; operator, 8 Nov: "I should be able
        // to move every element around in that block and change it"). ``childGeometry`` is ordinary Edit's CUSTOM
        // child_geometry carrier (``now_playing.child_geometry``): per part, a size factor of its own drawn size and an
        // offset from where today's layout puts it. ``{}`` (the default) is today's layout exactly. The block's own size
        // never follows its parts (ordinary Edit never grows a parent for a child edit): every natural size above is the
        // authored one. A part grows from its top-left (the child editor's contract) and stays inside the block, card
        // padding included (ordinary Edit contains a child in its parent).
        readonly property var childGeometry: options.childGeometry ? options.childGeometry : ({})
        // Offsets are fractions of a square of ``CHILD_NORMALIZATION_EMS`` (10) ems of this overlay's font, so a part
        // keeps its place under the block's scale and the font size, and never moves with a track's text length.
        readonly property real childNormalizationWidth: Math.max(1.0, fontSize * 10.0)
        readonly property real childNormalizationHeight: childNormalizationWidth
        function childNumber(roleId, key, fallback) {
            const record = childGeometry[roleId]
            const value = record ? Number(record[key]) : NaN
            return isFinite(value) ? value : fallback
        }
        function childWidthScale(roleId) { return Math.max(0.01, childNumber(roleId, "width_scale", 1.0)) }
        function childHeightScale(roleId) { return Math.max(0.01, childNumber(roleId, "height_scale", 1.0)) }
        function childOffsetX(roleId) { return childNumber(roleId, "x_offset", 0.0) * childNormalizationWidth }
        function childOffsetY(roleId) { return childNumber(roleId, "y_offset", 0.0) * childNormalizationHeight }
        // In the content's coordinates (``body``): the block is the slot, so a part may use the card's padding too.
        function containX(x, extent) { return Math.max(-padding, Math.min(naturalWidth + padding - extent, x)) }
        function containY(y, extent) { return Math.max(-padding, Math.min(naturalHeight + padding - extent, y)) }
        // Where the text column's origin sits in the content's coordinates (the text parts' authored places are in it).
        readonly property real columnX: textBlock.x
        readonly property real columnY: textBlock.y + textColumn.y
        // Ordinary Edit's editable-child declaration (OverlayWidget.customEditableChildRoles): Fullscreen Edit's frame
        // for Now Playing resolves this slot as its presentation, so the one child editor draws each part's frame,
        // move area and handles when the block is selected and its child lock is open. Stable items only (rebuilding
        // the list would retire a live gesture); the live normalisation box is read from ``normalizationTarget``.
        readonly property var customEditableChildRoles: [
            {"roleId": "artwork", "target": artFrame, "normalizationTarget": nowPlayingSlot,
             "geometryDependencies": [textBlock]},
            {"roleId": "title", "target": titleText, "normalizationTarget": nowPlayingSlot,
             "geometryDependencies": [textBlock, textColumn]},
            {"roleId": "artist", "target": artistText, "normalizationTarget": nowPlayingSlot,
             "geometryDependencies": [textBlock, textColumn]},
            {"roleId": "controls", "target": controls, "normalizationTarget": nowPlayingSlot,
             "geometryDependencies": [textBlock, textColumn]}
        ]
        readonly property var customEditableChildRequirementTarget: null

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
            // A part of the block (``artwork``): today's place beside the text, moved and sized by its child record
            // (the frame resizes freely; the image crops into it, ordinary Edit's freeform artwork frame).
            readonly property real authoredX: nowPlayingSlot.rightSide ? nowPlayingSlot.naturalWidth - nowPlayingSlot.artWidth
                                                                      : 0.0
            readonly property real authoredY: (nowPlayingSlot.naturalHeight - nowPlayingSlot.artHeight) / 2.0
            width: Math.round(nowPlayingSlot.artWidth * nowPlayingSlot.childWidthScale("artwork"))
            height: Math.round(nowPlayingSlot.artHeight * nowPlayingSlot.childHeightScale("artwork"))
            x: nowPlayingSlot.containX(authoredX + nowPlayingSlot.childOffsetX("artwork"), width)
            y: nowPlayingSlot.containY(authoredY + nowPlayingSlot.childOffsetY("artwork"), height)
            readonly property real imageInset: Math.max(0.75, overlays.borderWidth * 0.65)
            onXChanged: overlays.noteEditGeometry()
            onYChanged: overlays.noteEditGeometry()
            onWidthChanged: overlays.noteEditGeometry()
            onHeightChanged: overlays.noteEditGeometry()

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
                width: Math.round(Math.min(parent.width, parent.height) * 0.42)
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

        FontMetrics {
            id: titleMetrics
            font: titleText.effectiveFont
        }
        // The text block (Fullscreen Edit's Now Playing frame): the column at its natural size or in a set box.
        Item {
            id: textBlock
            objectName: "expandedOverlayNowPlayingText"
            x: nowPlayingSlot.rightSide ? 0.0 : nowPlayingSlot.artWidth + nowPlayingSlot.gap
            y: (parent.height - height) / 2.0
            width: nowPlayingSlot.boxWidth > 0.0 ? nowPlayingSlot.boxWidth : nowPlayingSlot.naturalTextWidth
            height: nowPlayingSlot.boxHeight > 0.0 ? nowPlayingSlot.boxHeight : textColumn.height
            onXChanged: overlays.noteEditGeometry()
            onYChanged: overlays.noteEditGeometry()
            onWidthChanged: overlays.noteEditGeometry()
            onHeightChanged: overlays.noteEditGeometry()

            // The rows at their natural spacing; a set box height (Fullscreen Edit's side handles) gives the title the
            // extra lines that fit and spreads what is left between the rows (title to artist, artist to the Media
            // Controls), so the artist and the controls follow the box's edge as the title does: the block fills its
            // box, never a stale gap above and below it (Media's own content extent likewise widens its metadata
            // spacing with the box's height).
            Item {
                id: textColumn
                y: (parent.height - height) / 2.0
                width: textBlock.width
                readonly property real spacing: Math.round(nowPlayingSlot.fontSize * 0.12)
                readonly property real naturalHeight: titleText.height + spacing + artistText.height
                    + (nowPlayingSlot.controlsShown ? 2.0 * spacing + controlsSpacer.height + nowPlayingSlot.controlsHeight
                       : 0.0)
                readonly property real slack: nowPlayingSlot.boxHeight > 0.0
                    ? Math.max(0.0, nowPlayingSlot.boxHeight - naturalHeight) : 0.0
                readonly property real gapExtra: slack / (nowPlayingSlot.controlsShown ? 2.0 : 1.0)
                height: naturalHeight + slack

                ShadowedText {
                    id: titleText
                    objectName: "expandedOverlayTitle"
                    // A part of the block (``title``): scaled whole (its layout keeps today's size) and moved, kept
                    // inside the block.
                    readonly property real partScale: nowPlayingSlot.childWidthScale("title")
                    transform: [
                        Scale { id: titleScale; xScale: titleText.partScale; yScale: titleText.partScale },
                        Translate {
                            id: titleShift
                            x: nowPlayingSlot.containX(
                                   nowPlayingSlot.columnX + titleText.x + nowPlayingSlot.childOffsetX("title"),
                                   titleText.width * titleText.partScale) - nowPlayingSlot.columnX - titleText.x
                            y: nowPlayingSlot.containY(nowPlayingSlot.columnY + nowPlayingSlot.childOffsetY("title"),
                                                       titleText.height * titleText.partScale) - nowPlayingSlot.columnY
                        }
                    ]
                    // The child editor maps through these applied transform values (never the transform list).
                    readonly property string customEditMappingDependency: [titleScale.xScale, titleScale.yScale,
                                                                          titleShift.x, titleShift.y].join(",")
                    // As wide as its text draws (up to the box, where it elides or wraps), on its side of the box: the
                    // part's frame is the line itself, so it can move across the box (the pixels are today's).
                    width: Math.min(Math.ceil(implicitWidth), textColumn.width)
                    x: nowPlayingSlot.rightSide ? textColumn.width - width : 0.0
                    text: nowPlayingSlot.contentTitle
                    font.family: overlays.fontFamily
                    font.pixelSize: Math.max(1, Math.round(nowPlayingSlot.fontSize))
                    font.weight: Font.DemiBold
                    color: nowPlayingSlot.textColor
                    elide: Text.ElideRight
                    wrap: nowPlayingSlot.titleLines > 1
                    breakLongWords: true
                    maximumLineCount: nowPlayingSlot.titleLines
                    horizontalAlignment: nowPlayingSlot.rightSide ? Text.AlignRight : Text.AlignLeft
                    shadowSoft: true
                    shadowColor: overlays.textShadowColor
                    shadowOffsetX: 0.0
                    shadowOffsetY: overlays.textShadowOffset
                }
                ShadowedText {
                    id: artistText
                    objectName: "expandedOverlayArtist"
                    y: titleText.height + textColumn.spacing + textColumn.gapExtra
                    // A part of the block (``artist``): scaled whole and moved from its row, kept inside the block.
                    readonly property real partScale: nowPlayingSlot.childWidthScale("artist")
                    transform: [
                        Scale { id: artistScale; xScale: artistText.partScale; yScale: artistText.partScale },
                        Translate {
                            id: artistShift
                            x: nowPlayingSlot.containX(
                                   nowPlayingSlot.columnX + artistText.x + nowPlayingSlot.childOffsetX("artist"),
                                   artistText.width * artistText.partScale) - nowPlayingSlot.columnX - artistText.x
                            y: nowPlayingSlot.containY(
                                   nowPlayingSlot.columnY + artistText.y + nowPlayingSlot.childOffsetY("artist"),
                                   artistText.height * artistText.partScale) - nowPlayingSlot.columnY - artistText.y
                        }
                    ]
                    readonly property string customEditMappingDependency: [artistScale.xScale, artistScale.yScale,
                                                                          artistShift.x, artistShift.y].join(",")
                    x: nowPlayingSlot.rightSide ? textColumn.width - width : 0.0
                    width: Math.min(Math.ceil(implicitWidth), textColumn.width)
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
                // Media Controls (default off): a small version of the Media card's own transport bar (the one
                // MediaTransportBar, its look from the Media model), on the Media card's own transport owner.
                Item {
                    id: controlsSpacer
                    y: artistText.y + artistText.height + textColumn.spacing
                    width: textColumn.width
                    height: Math.round(nowPlayingSlot.fontSize * 0.25)
                    visible: nowPlayingSlot.controlsShown
                }
                MediaTransportBar {
                    id: controls
                    objectName: "expandedOverlayMediaControls"
                    readonly property var model: overlays.mediaModel
                    visible: nowPlayingSlot.controlsShown
                    // A part of the block (``controls``): today's row under the artist, sized on each axis and moved
                    // by its child record (as the Media card's transport controls), kept inside the block.
                    readonly property real authoredX: nowPlayingSlot.rightSide
                        ? textColumn.width - nowPlayingSlot.controlsWidth : 0.0
                    readonly property real authoredY: controlsSpacer.y + controlsSpacer.height + textColumn.spacing
                        + textColumn.gapExtra
                    x: nowPlayingSlot.containX(nowPlayingSlot.columnX + authoredX + nowPlayingSlot.childOffsetX("controls"),
                                               width) - nowPlayingSlot.columnX
                    y: nowPlayingSlot.containY(nowPlayingSlot.columnY + authoredY + nowPlayingSlot.childOffsetY("controls"),
                                               height) - nowPlayingSlot.columnY
                    width: Math.round(nowPlayingSlot.controlsWidth * nowPlayingSlot.childWidthScale("controls"))
                    height: Math.round(nowPlayingSlot.controlsHeight * nowPlayingSlot.childHeightScale("controls"))
                    // The card's bar, scaled as one: its outline, radius and shadow by the same factor as its height
                    // (its own drawn height: a part sized taller keeps the card's proportions).
                    readonly property real drawnFactor: nowPlayingSlot.controlsFactor
                        * Math.min(nowPlayingSlot.childWidthScale("controls"), nowPlayingSlot.childHeightScale("controls"))
                    radius: 12.0 * drawnFactor
                    border.width: Math.max(1.0, 1.5 * drawnFactor)
                    border.color: overlays.mediaLook("borderColor", "#ffffffff")

                    canPrevious: !!model && model.canPrevious === true
                    canPlayPause: !!model && model.canPlayPause === true
                    canNext: !!model && model.canNext === true
                    interactionEnabled: nowPlayingSlot.interactive
                    playing: nowPlayingSlot.playing
                    surfaceColor: overlays.mediaLook("surfaceColor", "#b3101010")
                    iconColor: overlays.mediaLook("iconColor", "#ffffffff")
                    separatorColor: overlays.mediaLook("separatorColor", "#66ffffff")
                    separatorWidth: 1.0
                    shadowEnabled: overlays.mediaLook("shadowEnabled", false) === true
                    shadowColor: overlays.mediaLook("shadowColor", "#00000000")
                    shadowBlur: Number(overlays.mediaLook("shadowBlur", 0.0)) * drawnFactor
                    shadowOffsetX: Number(overlays.mediaLook("shadowOffsetX", 0.0)) * drawnFactor
                    shadowOffsetY: Number(overlays.mediaLook("shadowOffsetY", 0.0)) * drawnFactor
                    // Over the Visualizer, whose double-click cycles its mode: each segment holds its own presses.
                    exclusivePress: true
                    materialObjectName: "expandedOverlayMediaControlsMaterial"
                    transportObjectName: "expandedOverlayTransportControls"
                    previousObjectName: "expandedOverlayTransport_previous"
                    playPauseObjectName: "expandedOverlayTransport_play"
                    nextObjectName: "expandedOverlayTransport_next"
                    onTransportRequested: function(key) { overlays.transportRequested(key) }
                }
            }
        }
    }

    // ------------------------------------------------------------------------------- Show On Hover (Now Playing)
    // Operator, 8 Nov: "the media section should optionally refade in if hovered over where it was positioned.
    // Without timers or polling." With the option on, the pointer arriving where Now Playing is placed (its slot's
    // rectangle, kept while it is faded out) fades it back in and holds it; leaving starts the reveal's own hold and
    // fade-out. Driven by this HoverHandler's hovered edges only: no Timer, no polling, nothing per frame. The region
    // is an empty item above the slots: its handler is passive (blocking: false) and nothing here takes a press, so
    // clicks, the wheel, the Media Controls' own hover and every gesture reach what lies under it. Off (the
    // default), while Fullscreen Edit is open (Edit holds the overlays itself) or with no track, it does nothing.
    readonly property bool nowPlayingHoverReveal: nowPlayingOptions.hoverReveal === true
    Item {
        id: nowPlayingHoverRegion
        objectName: "expandedOverlayNowPlayingHoverRegion"
        x: nowPlayingSlot.x
        y: nowPlayingSlot.y
        width: nowPlayingSlot.width
        height: nowPlayingSlot.height
        z: 2
        HoverHandler {
            id: nowPlayingHover
            objectName: "expandedOverlayNowPlayingHover"
            enabled: overlays.nowPlayingHoverReveal && !overlays.editing
            blocking: false
        }
    }
    readonly property bool nowPlayingHoverActive: nowPlayingHover.hovered && nowPlayingHoverReveal && !editing
        && entered && liveTrackKey.length > 0
    onNowPlayingHoverActiveChanged: {
        if (nowPlayingHoverActive)
            nowPlayingSlot.hoverEnter()
        else
            nowPlayingSlot.hoverExit(liveTrackKey.length > 0)
    }
}
