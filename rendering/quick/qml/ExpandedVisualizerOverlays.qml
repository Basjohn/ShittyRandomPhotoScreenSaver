import QtQuick
import QtQuick.Effects
import "MediaArtworkRule.js" as ArtworkRule

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
// geometry changes are reported through editGeometryChanged (Python re-reads the Edit frames: the preset toast and
// Now Playing's block, whose parts are its children for ordinary Edit's child editor). When Edit ends they return to
// their authored visibility with a fade.
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
    // The expanded card's frame border (the safe area is inset by it) and the overlays' own cards' chrome (the widget
    // cards': 1D.2 keeps it whatever frame a display style draws).
    property real borderWidth: 4.0
    property real cardBorderWidth: borderWidth
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
    // The Seek Bar's seeks (plan 1B.7g): Python routes them to the Media card's own seek owner.
    signal seekRequested(real fraction)
    // The Media card's seek bar look (MediaPresentationModel.seekBarLook: its progress colours, shadow, glow, height).
    readonly property var mediaSeekLook: {
        const text = mediaModel ? mediaModel.seekBarLook : undefined
        return typeof text === "string" && text.length > 0 ? JSON.parse(text) : ({})
    }
    function seekLook(name, fallback) {
        const value = mediaSeekLook[name]
        return value === undefined || value === null ? fallback : value
    }
    // The Media card's artwork frame look (MediaPresentationModel.artworkLook: border colour and stroke, Rounded
    // Artwork; plan 1B.7d): Now Playing's artwork follows the Media widget's artwork settings, not the card chrome.
    readonly property var mediaArtLook: {
        const text = mediaModel ? mediaModel.artworkLook : undefined
        return typeof text === "string" && text.length > 0 ? JSON.parse(text) : ({})
    }
    function artLook(name, fallback) {
        const value = mediaArtLook[name]
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
        ? String(mediaModel.artist) + "\u001f" + String(mediaModel.title) + "\u001f"
          + (mediaModel.album !== undefined ? String(mediaModel.album) : "") : ""
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
            presetSlot.holdForEdit(presetSlot.contentText !== (presetName.length > 0
                ? presetName : editPresetPlaceholder))
            nowPlayingSlot.holdForEdit(nowPlayingSlot.contentKey !== liveTrackKey
                || (liveTrackKey.length === 0 && nowPlayingSlot.contentTitle !== editTitlePlaceholder))
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
        // The block is its content box: the artwork beside the text group (plan 1C.3).
        naturalWidth: blockWidth
        naturalHeight: blockHeight

        // Orientation follows the side of the display the block lies on (accepted 10 Nov; restored by plan 1C.3 after
        // 1B.7c had tied it to the anchor corner): on the left half the artwork is on the left and the text is
        // left-aligned beside it; on the right half the block is mirrored. The block's centre decides (at the exact
        // midpoint: the left), so a block moved across the midpoint flips. Top and bottom never change it: the text
        // sits beside the artwork, centred on it, wherever the block is placed vertically. The block's width never
        // depends on its side, so there is no placement/orientation loop. The text group's alignment record (its flip
        // glyph in Fullscreen Edit, the ``metadata`` role's ``alignment_flip``; it also carries
        // ``semantic_corner_anchor``, as Media's header) is the explicit override on top (it mirrors the block where it
        // is); the artist line flips its own text alignment on top of that (Media's orientedChildAlignment). The Media
        // card's app-volume rail follows its side of the display the same way.
        readonly property bool positionRight: !!stage && stage.width > 0.0 ? x + width * 0.5 > stage.width * 0.5
                                                                         : rightSide
        function childAlignment(roleId) {
            const record = childGeometry[roleId]
            return record && record.alignment !== undefined ? String(record.alignment) : "left"
        }
        function childAnchor(roleId) {
            const record = childGeometry[roleId]
            return record && record.anchor !== undefined && record.anchor !== null ? String(record.anchor) : ""
        }
        readonly property bool contentRightSide: positionRight !== (childAlignment("metadata") === "right")
        function textRight(roleId) {
            return roleId === "metadata" ? contentRightSide : (childAlignment(roleId) === "right") !== contentRightSide
        }
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
        // The one-line text stack supplies a stable artwork baseline independent of wrapping and track changes.
        readonly property real titleLineHeight: Math.max(1.0, Math.ceil(titleMetrics.height))
        readonly property real naturalTextHeight: titleLineHeight + textColumn.spacing + Math.ceil(artistMetrics.height)
            + (albumShown ? textColumn.spacing + Math.ceil(albumMetrics.height) : 0.0)
            + (seekShown ? 2.0 * textColumn.spacing + seekHeight : 0.0)
            + (controlsShown ? 2.0 * textColumn.spacing + controlsSpacer.height + controlsHeight : 0.0)
        // The same stack with the album row reserved whenever the Media widget shows albums (its option, never the
        // current track's text): the artwork's and the block's geometry never change from one track to the next.
        readonly property bool albumRowReserved: !!overlays.mediaModel && overlays.mediaModel.showAlbum === true
        readonly property real stackHeight: titleLineHeight + textColumn.spacing + Math.ceil(artistMetrics.height)
            + (albumRowReserved ? textColumn.spacing + Math.ceil(albumMetrics.height) : 0.0)
            + (seekShown ? 2.0 * textColumn.spacing + seekHeight : 0.0)
            + (controlsShown ? 2.0 * textColumn.spacing + controlsSpacer.height + controlsHeight : 0.0)
        // Seek Bar (plan 1B.7g, default off): the Media card's seek bar (MediaSeekBar.qml, its look from the Media
        // model) under the metadata, the card's seek height in proportion to Now Playing's controls.
        readonly property bool seekShown: options.seekBar === true
        readonly property real seekHeight: Math.max(2.0, Math.round(Number(overlays.seekLook("height", 6.0))
                                                                     * controlsFactor))
        // The natural artwork: a square as tall as the natural block (at least 3.1 ems, at least the text stack).
        readonly property real artBase: Math.max(Math.round(fontSize * 3.1), Math.ceil(stackHeight))
        readonly property real gap: Math.round(fontSize * 0.55)
        // The natural metadata width: the half-screen cap applies to the unedited layout; the screen's capacity is the
        // final constraint, so long titles fit instead of crossing the edge.
        // (Whole pixels, so a block stored at its first edit draws exactly the natural block it was.)
        readonly property real textWidthLimit: Math.max(48.0, Math.floor(
            Math.min(maxBoxWidth - artBase - gap, maxContentWidth - artBase - gap)))
        readonly property real naturalTextWidth: Math.min(textWidthLimit,
            Math.ceil(Math.max(titleText.implicitWidth, artistText.implicitWidth,
                              albumShown ? albumText.implicitWidth : 0.0, controlsShown ? controlsWidth : 0.0)))
        // ---- The block's content box (plan 1C.3; the operator: "X/Y artwork should adjust, media does this well").
        // Its side handles are ordinary Edit's content box, as the Media card's content extent: they give or take the
        // block's width and height, and the artwork reflows inside it by the Media card's one artwork rule
        // (MediaArtworkRule.js) with Now Playing's own spec: the artwork is as tall as the block; its width is its
        // natural width plus the rule's share of the width given since the block's base (or minus it, taken), never
        // under the artwork role's own minimum (0.4 of its natural size), leaving the text its room, and at most 16:9
        // (Now Playing may go landscape; the Media card's spec keeps its artwork never wider than tall). The text group
        // takes the rest of the width and elides in it. A corner or the wheel scales the whole block (``scale``). The
        // artwork child record multiplies on top, as on Media.
        // Stored in ems of the block's font (0 = natural): ``text_width`` is the block's width beyond its natural
        // artwork column (the artwork's natural side and the gap), ``text_height`` its height (at least the text
        // stack), and ``base_width`` the block's width (same unit) at the first edit gesture on it, stored once by
        // Fullscreen Edit with the block's height at that instant (lead, 12 Nov). At that instant the share is zero,
        // so the first sample of any gesture moves nothing; from then on the artwork follows the stored geometry only,
        // never the current track's text. Never edited (no base): the natural block, hugging its text beside a natural
        // artwork.
        readonly property real artMaxAspect: 16.0 / 9.0
        readonly property real artFloor: Math.round(artBase * 0.4)
        readonly property real textRoom: Math.max(minimumTextWidth, controlsShown ? controlsWidth : 0.0)
        readonly property real setBaseWidth: {
            const value = Number(options.baseWidth)
            return isFinite(value) && value > 0 ? value * fontSize : 0.0
        }
        // The text's room never exceeds the room it had at the base (so the first sample of a gesture changes nothing).
        readonly property real artRoom: setBaseWidth > 0.0 ? Math.min(textRoom, setBaseWidth) : textRoom
        readonly property real boxWidth: setTextWidth > 0.0
            ? Math.round(Math.min(maxBoxWidth, Math.max(artFloor + gap + artRoom, setTextWidth + artBase + gap)))
            : 0.0
        readonly property real boxHeight: setTextHeight > 0.0
            ? Math.round(Math.min(maxBoxHeight, Math.max(stackHeight, setTextHeight))) : 0.0
        readonly property real blockHeight: boxHeight > 0.0 ? boxHeight : artBase
        // The width given since the base (none without a stored width and base).
        readonly property real artExtraWidth: boxWidth > 0.0 && setBaseWidth > 0.0
            ? boxWidth - (setBaseWidth + artBase + gap) : 0.0
        readonly property real artWidth: Math.round(ArtworkRule.authoredWidth(
            ArtworkRule.provisionalWidth(artBase, artExtraWidth,
                                         (boxWidth > 0.0 ? boxWidth : artBase + gap + artRoom) - gap, artRoom, artFloor),
            blockHeight, artMaxAspect))
        readonly property real artHeight: Math.round(blockHeight)
        readonly property real naturalBlockWidth: artWidth + gap + naturalTextWidth
        readonly property real blockWidth: boxWidth > 0.0 ? boxWidth : naturalBlockWidth
        // The text group's column: the block's width beside the artwork.
        readonly property real textColumnWidth: Math.max(1.0, blockWidth - artWidth - gap)
        // Extra block height never manufactures gaps between the metadata rows; it gives a genuinely wrapping
        // title/artist more lines, otherwise the group stays naturally grouped and centred on the artwork.
        readonly property int metadataLines: boxHeight > 0.0
            ? 1 + Math.max(0, Math.floor((boxHeight - stackHeight + 0.5)
                                       / (titleLineHeight + artistMetrics.height + (albumShown ? albumMetrics.height : 0)))) : 1
        readonly property int titleLines: metadataLines
        readonly property bool albumShown: !!overlays.mediaModel && overlays.mediaModel.showAlbum === true
            && contentAlbum.length > 0
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
            {"roleId": "metadata", "target": textGroup, "normalizationTarget": nowPlayingSlot,
             "geometryDependencies": [textBlock, textColumn]},
            {"roleId": "artist", "target": artistText, "normalizationTarget": nowPlayingSlot,
             "geometryDependencies": [textBlock, textColumn, textGroup]},
            {"roleId": "controls", "target": controls, "normalizationTarget": nowPlayingSlot,
             "geometryDependencies": [textBlock, textColumn]},
            {"roleId": "seek_bar", "target": seekBar, "normalizationTarget": nowPlayingSlot,
             "geometryDependencies": [textBlock, textColumn, textGroup]}
        ]
        readonly property var customEditableChildRequirementTarget: null

        // The latched track (swapped only while the content is invisible, so text and artwork always belong together).
        property string contentKey: ""
        property string contentTitle: ""
        property string contentArtist: ""
        property string contentAlbum: ""
        onSwapContent: {
            const model = overlays.mediaModel
            contentKey = overlays.liveTrackKey
            const placeholder = contentKey.length === 0 && overlays.editing
            contentTitle = placeholder ? overlays.editTitlePlaceholder : (model ? String(model.title) : "")
            contentArtist = placeholder ? overlays.editArtistPlaceholder : (model ? String(model.artist) : "")
            contentAlbum = !placeholder && model && model.album !== undefined ? String(model.album) : ""
        }
        // Identity fence: the model's artwork is shown only for the latched track, never under another's text.
        readonly property string artSource: contentKey.length > 0 && contentKey === overlays.liveTrackKey
            && !!overlays.mediaModel ? String(overlays.mediaModel.artworkSource) : ""

        Item {
            id: artFrame
            objectName: "expandedOverlayArtwork"
            // A part of the block (``artwork``): today's place beside the text, moved and sized by its child record
            // (the frame resizes freely; the image crops into it, ordinary Edit's freeform artwork frame).
            readonly property real authoredX: nowPlayingSlot.contentRightSide ? nowPlayingSlot.naturalWidth - nowPlayingSlot.artWidth
                                                                      : 0.0
            readonly property real authoredY: (nowPlayingSlot.naturalHeight - nowPlayingSlot.artHeight) / 2.0
            width: Math.round(nowPlayingSlot.artWidth * nowPlayingSlot.childWidthScale("artwork"))
            height: Math.round(nowPlayingSlot.artHeight * nowPlayingSlot.childHeightScale("artwork"))
            x: nowPlayingSlot.containX(authoredX + nowPlayingSlot.childOffsetX("artwork"), width)
            y: nowPlayingSlot.containY(authoredY + nowPlayingSlot.childOffsetY("artwork"), height)
            // The Media card's artwork frame (MediaPresentation.qml's artworkFrame): its border colour, its stroke (a
            // painted stroke never below 1.5 px), Rounded Artwork's radius of an eighth of the short side, the image
            // inset concentric with the stroke.
            readonly property bool rounded: overlays.artLook("rounded", true) === true
            readonly property real strokeWidth: {
                const width = Number(overlays.artLook("borderWidth", 2.75))
                return isFinite(width) && width > 0.0 ? Math.max(1.5, width) : 0.0
            }
            readonly property color strokeColor: overlays.artLook("borderColor", "#ffffffff")
            readonly property real radius: rounded ? Math.min(width, height) / 8.0 : 0.0
            readonly property real imageInset: Math.max(0.75, strokeWidth * 0.65)
            onXChanged: overlays.noteEditGeometry()
            onYChanged: overlays.noteEditGeometry()
            onWidthChanged: overlays.noteEditGeometry()
            onHeightChanged: overlays.noteEditGeometry()

            RectangularShadow {
                anchors.fill: parent
                radius: artFrame.radius
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
                radius: artFrame.radius
                color: overlays.cardColor
            }
            Canvas {
                id: noteGlyph
                anchors.centerIn: parent
                width: Math.round(Math.min(parent.width, parent.height) * 0.42)
                height: width
                readonly property color ink: Qt.rgba(artFrame.strokeColor.r, artFrame.strokeColor.g,
                                                     artFrame.strokeColor.b, 0.55)
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
                layer.enabled: artFrame.rounded
                layer.effect: MultiEffect {
                    maskEnabled: true
                    maskSource: artworkMask
                }
            }
            Rectangle {
                id: artworkMask
                anchors.fill: artwork
                radius: Math.max(0.0, artFrame.radius - artFrame.imageInset)
                visible: false
                layer.enabled: true
            }
            // The Media card's artwork border: its colour and stroke, Rounded Artwork's radius.
            Rectangle {
                objectName: "expandedOverlayArtworkBorder"
                anchors.fill: parent
                radius: artFrame.radius
                color: "transparent"
                border.width: artFrame.strokeWidth
                border.color: artFrame.strokeColor
            }
        }

        FontMetrics {
            id: titleMetrics
            font: titleText.effectiveFont
        }
        FontMetrics { id: artistMetrics; font: artistText.effectiveFont }
        FontMetrics { id: albumMetrics; font: albumText.effectiveFont }
        // The complete metadata/controls group follows the inward side of the artwork at each corner.
        // A separate Fullscreen Edit child override remains an offset from these live authored rails.
        Item {
            id: textBlock
            objectName: "expandedOverlayNowPlayingText"
            x: nowPlayingSlot.contentRightSide ? 0.0 : nowPlayingSlot.artWidth + nowPlayingSlot.gap
            y: (parent.height - height) / 2.0
            // The block's width beside the artwork (the Media rule's rest); as tall as its stack, centred on the artwork.
            width: nowPlayingSlot.textColumnWidth
            height: textColumn.height
            onXChanged: overlays.noteEditGeometry()
            onYChanged: overlays.noteEditGeometry()
            onWidthChanged: overlays.noteEditGeometry()
            onHeightChanged: overlays.noteEditGeometry()

            // One compact vertical metadata stack (as on Media). Artwork and the full group are independently
            // centred across their combined height. Unused room never distributes metadata like a stretched
            // column; only actual wrapping or explicit per-child edits should alter row positions.
            Item {
                id: textColumn
                y: (parent.height - height) / 2.0
                width: textBlock.width
                readonly property real spacing: Math.round(nowPlayingSlot.fontSize * 0.12)
                readonly property real naturalHeight: titleText.height + spacing + artistText.height
                    + (nowPlayingSlot.albumShown ? spacing + albumText.height : 0.0)
                    + (nowPlayingSlot.seekShown ? 2.0 * spacing + nowPlayingSlot.seekHeight : 0.0)
                    + (nowPlayingSlot.controlsShown ? 2.0 * spacing + controlsSpacer.height + nowPlayingSlot.controlsHeight
                       : 0.0)
                // The metadata rows' bottom, and below them the Seek Bar's row (the Media card's order: metadata, seek,
                // transport).
                readonly property real metadataBottom: nowPlayingSlot.albumShown ? albumText.y + albumText.height
                                                                                : artistText.y + artistText.height
                readonly property real seekRowY: metadataBottom + 2.0 * spacing
                readonly property real rowsBottom: nowPlayingSlot.seekShown ? seekRowY + nowPlayingSlot.seekHeight
                                                                            : metadataBottom
                height: naturalHeight

                // The text group (``metadata``, the Media card's role; plan 1C.3, operator 11 Nov: "one group box for all
                // the text metadata with one easy-to-reach handle"): the title, artist and album lines in one box that
                // moves and scales as one (its child record: offset, uniform scale, the flip glyph's alignment and its
                // semantic corner anchor), as the Media card's metadata block. Its frame is the whole group (its
                // widest line, up to the column, where lines elide or wrap; its rows' height), on the block's side of
                // the column, so it can be moved across the column's free room; never under the artwork, inside the
                // block at every anchor. Its
                // alignment record is the explicit flip on top of the block's side; the artist line keeps its own part
                // inside the group (the Media card's ``artist`` role), the title and album have none (Media has none).
                Item {
                    id: textGroup
                    objectName: "expandedOverlayNowPlayingMetadata"
                    width: Math.min(textColumn.width, Math.ceil(Math.max(
                        titleText.implicitWidth, artistText.implicitWidth,
                        nowPlayingSlot.albumShown ? albumText.implicitWidth : 0.0, 1.0)))
                    height: textColumn.metadataBottom
                    x: nowPlayingSlot.contentRightSide ? textColumn.width - width : 0.0
                    // Where the group's origin sits in the block's coordinates before its own record moves it.
                    readonly property real originX: nowPlayingSlot.columnX + textGroup.x
                    readonly property real partScale: nowPlayingSlot.childWidthScale("metadata")
                    // The group's semantic corner anchor (``semantic_corner_anchor``, as the Media card's header): a
                    // move that ends snapped into one of the block's corners pins it there, so the block's resizes
                    // keep it in that corner; a free move detaches it (the child editor clears the anchor).
                    readonly property string customAnchor: nowPlayingSlot.childAnchor("metadata")
                    readonly property real drawnWidth: textGroup.width * textGroup.partScale
                    readonly property real drawnHeight: textGroup.height * textGroup.partScale
                    // Where its offset alone puts it; a pinned group's difference is folded into the offset once when a
                    // move detaches it (the child editor's placement compensation), so it never jumps.
                    readonly property real offsetShiftX: nowPlayingSlot.containX(
                        textGroup.originX + nowPlayingSlot.childOffsetX("metadata"), drawnWidth) - textGroup.originX
                    readonly property real offsetShiftY: nowPlayingSlot.containY(
                        nowPlayingSlot.columnY + nowPlayingSlot.childOffsetY("metadata"), drawnHeight)
                        - nowPlayingSlot.columnY
                    readonly property real customEditPlacementCompensationX:
                        customAnchor.length > 0 ? groupShift.x - offsetShiftX : 0.0
                    readonly property real customEditPlacementCompensationY:
                        customAnchor.length > 0 ? groupShift.y - offsetShiftY : 0.0
                    transform: [
                        Scale { id: groupScale; xScale: textGroup.partScale; yScale: textGroup.partScale },
                        Translate {
                            id: groupShift
                            // Pinned: the containment's own corner (the block's frame, its card padding included).
                            x: nowPlayingSlot.containX(textGroup.customAnchor.endsWith("right") ? Infinity
                                                       : textGroup.customAnchor.endsWith("left") ? -Infinity
                                                       : textGroup.originX + nowPlayingSlot.childOffsetX("metadata"),
                                                       textGroup.drawnWidth)
                               - textGroup.originX
                            y: nowPlayingSlot.containY(textGroup.customAnchor.startsWith("bottom") ? Infinity
                                                       : textGroup.customAnchor.startsWith("top") ? -Infinity
                                                       : nowPlayingSlot.columnY + nowPlayingSlot.childOffsetY("metadata"),
                                                       textGroup.drawnHeight)
                               - nowPlayingSlot.columnY
                        }
                    ]
                    // The child editor maps through these applied transform values (never the transform list).
                    readonly property string customEditMappingDependency: [groupScale.xScale, groupScale.yScale,
                                                                          groupShift.x, groupShift.y].join(",")
                    // The block's containment in the group's own coordinates (for the artist part inside it).
                    function containLocalX(x, extent) {
                        const origin = textGroup.originX + groupShift.x
                        return Math.max((-nowPlayingSlot.padding - origin) / partScale,
                                        Math.min((nowPlayingSlot.naturalWidth + nowPlayingSlot.padding - origin)
                                                 / partScale - extent, x))
                    }
                    function containLocalY(y, extent) {
                        const origin = nowPlayingSlot.columnY + groupShift.y
                        return Math.max((-nowPlayingSlot.padding - origin) / partScale,
                                        Math.min((nowPlayingSlot.naturalHeight + nowPlayingSlot.padding - origin)
                                                 / partScale - extent, y))
                    }
                    onXChanged: overlays.noteEditGeometry()
                    onYChanged: overlays.noteEditGeometry()
                    onWidthChanged: overlays.noteEditGeometry()
                    onHeightChanged: overlays.noteEditGeometry()

                    MediaMetadataText {
                        id: titleText
                        objectName: "expandedOverlayTitle"
                        // As wide as its text draws (up to the column, where it elides or wraps), on the group's side.
                        width: Math.min(Math.ceil(implicitWidth), textGroup.width)
                        x: nowPlayingSlot.textRight("metadata") ? textGroup.width - width : 0.0
                        text: nowPlayingSlot.contentTitle
                        font.family: overlays.fontFamily
                        font.pixelSize: Math.max(1, Math.round(nowPlayingSlot.fontSize))
                        font.weight: Font.DemiBold
                        color: nowPlayingSlot.textColor
                        maximumLineCount: nowPlayingSlot.titleLines
                        horizontalAlignment: nowPlayingSlot.textRight("metadata") ? Text.AlignRight : Text.AlignLeft
                        shadowSoft: true
                        shadowColor: overlays.textShadowColor
                        shadowOffsetX: 0.0
                        shadowOffsetY: overlays.textShadowOffset
                    }
                    MediaMetadataText {
                        id: artistText
                        objectName: "expandedOverlayArtist"
                        y: titleText.height + textColumn.spacing
                        // A part inside the group (``artist``, the Media card's role): scaled whole and moved from its
                        // row, on top of the group's own transform; kept inside the block.
                        readonly property real partScale: nowPlayingSlot.childWidthScale("artist")
                        transform: [
                            Scale { id: artistScale; xScale: artistText.partScale; yScale: artistText.partScale },
                            Translate {
                                id: artistShift
                                x: textGroup.containLocalX(artistText.x + nowPlayingSlot.childOffsetX("artist"),
                                                           artistText.width * artistText.partScale) - artistText.x
                                y: textGroup.containLocalY(artistText.y + nowPlayingSlot.childOffsetY("artist"),
                                                           artistText.height * artistText.partScale) - artistText.y
                            }
                        ]
                        readonly property string customEditMappingDependency: [
                            artistScale.xScale, artistScale.yScale, artistShift.x, artistShift.y,
                            groupScale.xScale, groupShift.x, groupShift.y].join(",")
                        x: nowPlayingSlot.textRight("artist") ? textGroup.width - width : 0.0
                        width: Math.min(Math.ceil(implicitWidth), textGroup.width)
                        text: nowPlayingSlot.contentArtist
                        maximumLineCount: nowPlayingSlot.metadataLines
                        font.family: overlays.fontFamily
                        font.pixelSize: Math.max(1, Math.round(nowPlayingSlot.fontSize * 0.74))
                        color: nowPlayingSlot.textColor
                        opacity: 0.88
                        elide: Text.ElideRight
                        horizontalAlignment: nowPlayingSlot.textRight("artist") ? Text.AlignRight : Text.AlignLeft
                        shadowSoft: true
                        shadowColor: overlays.textShadowColor
                        shadowOffsetX: 0.0
                        shadowOffsetY: overlays.textShadowOffset
                    }
                    MediaMetadataText {
                        id: albumText
                        objectName: "expandedOverlayAlbum"
                        visible: nowPlayingSlot.albumShown
                        x: nowPlayingSlot.textRight("metadata") ? textGroup.width - width : 0.0
                        y: artistText.y + artistText.height + textColumn.spacing
                        width: Math.min(Math.ceil(implicitWidth), textGroup.width)
                        height: visible ? implicitHeight : 0.0
                        text: nowPlayingSlot.contentAlbum
                        font.family: overlays.fontFamily
                        font.pixelSize: Math.max(1, Math.round(nowPlayingSlot.fontSize * 0.74 * 0.82))
                        font.italic: true
                        maximumLineCount: nowPlayingSlot.metadataLines
                        color: nowPlayingSlot.textColor
                        opacity: 0.75
                        horizontalAlignment: nowPlayingSlot.textRight("metadata") ? Text.AlignRight : Text.AlignLeft
                        shadowSoft: true
                        shadowColor: overlays.textShadowColor
                        shadowOffsetX: 0.0
                        shadowOffsetY: overlays.textShadowOffset
                    }
                }
                // Seek Bar (plan 1B.7g, default off): the Media card's one seek bar (MediaSeekBar.qml), its look the
                // Media model's (seekBarLook), its position the model's own timeline events (no timer here), its seeks
                // the Media card's seek owner. A part of the block (``seek_bar``, the Media card's role): the text box's
                // width by default, sized on each axis and moved by its child record, kept inside the block. Over the
                // Visualizer, whose double-click cycles its mode, it holds its own presses (exclusivePress).
                MediaSeekBar {
                    id: seekBar
                    objectName: "expandedOverlaySeekBar"
                    readonly property var model: overlays.mediaModel
                    visible: nowPlayingSlot.seekShown
                    // It follows the text group's width and horizontal place (plan 1C.3: the group moved or scaled, the
                    // bar spans it), on its own row under the metadata; its own record moves and sizes it on top.
                    x: nowPlayingSlot.containX(textGroup.originX + groupShift.x
                                               + nowPlayingSlot.childOffsetX("seek_bar"), width)
                       - nowPlayingSlot.columnX
                    y: nowPlayingSlot.containY(nowPlayingSlot.columnY + textColumn.seekRowY
                                               + nowPlayingSlot.childOffsetY("seek_bar"), height) - nowPlayingSlot.columnY
                    width: Math.max(1.0, Math.round(textGroup.drawnWidth * nowPlayingSlot.childWidthScale("seek_bar")))
                    height: Math.max(1.0, Math.round(nowPlayingSlot.seekHeight * nowPlayingSlot.childHeightScale("seek_bar")))
                    fraction: !!model && isFinite(Number(model.progressFraction)) ? Number(model.progressFraction) : 0.0
                    seekEnabled: nowPlayingSlot.interactive && !!model && model.canSeek === true
                    trackColor: overlays.seekLook("trackColor", "#4dffffff")
                    fillColor: overlays.seekLook("fillColor", "#ffffffff")
                    shadowEnabled: overlays.seekLook("shadowEnabled", false) === true
                    shadowColor: overlays.seekLook("shadowColor", "#00000000")
                    glowEnabled: overlays.seekLook("glowEnabled", false) === true
                    glowColor: overlays.seekLook("glowColor", "#00000000")
                    glowBaseHeight: nowPlayingSlot.seekHeight
                    exclusivePress: true
                    hoverWashObjectName: "expandedOverlaySeekHoverWash"
                    glowObjectName: "expandedOverlaySeekGlow"
                    fillObjectName: "expandedOverlaySeekFill"
                    seekAreaObjectName: "expandedOverlaySeekArea"
                    onSeekRequested: function(value) { overlays.seekRequested(value) }
                }
                // Media Controls (default off): a small version of the Media card's own transport bar (the one
                // MediaTransportBar, its look from the Media model), on the Media card's own transport owner.
                Item {
                    id: controlsSpacer
                    y: textColumn.rowsBottom + textColumn.spacing
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
                    readonly property real authoredX: nowPlayingSlot.contentRightSide
                        ? textColumn.width - nowPlayingSlot.controlsWidth : 0.0
                    readonly property real authoredY: controlsSpacer.y + controlsSpacer.height + textColumn.spacing
                       
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
                    floatingGlyphs: nowPlayingSlot.options.mediaControlsStyle === "floating"
                    border.width: floatingGlyphs ? 0.0 : Math.max(1.0, 1.5 * drawnFactor)
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
