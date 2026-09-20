import QtQuick
import QtQuick.Effects

OverlayWidget {
    id: mediaRoot
    objectName: "mediaPresentation"


    // H9: CUSTOM wheel/corner resize is one uniform retained-presentation scale.
    // Header, metadata, artwork, progress and controls scale together from the
    // outer-rect / baseline-preferred ratio, so a resize no longer recentres or
    // respaces individual bands. Whole-widget CUSTOM resize remains purely
    // geometric; admitted child roles below may additionally own their normalized
    // presentation geometry while Settings retains all non-geometry styling.
    uniformScaleTransform: true

    required property var mediaModel
    property bool volumeWheelEnabled: true
    semanticDoubleClickEnabled: true
    signal refreshRequested()
    signal playPauseRequested()
    signal previousRequested()
    signal nextRequested()
    signal appVolumeLevelRequested(real level)
    signal appVolumeStepRequested(int direction)
    signal systemMuteToggleRequested()
    signal seekFractionRequested(real fraction)

    // Media projects the shared normalized child-geometry payload directly.
    // Track metadata remains one atomic crossfade block; every other visible
    // semantic region has its own role. No provider/runtime state enters this map.
    readonly property var childGeometry: mediaModel.customChildGeometry
    readonly property real childNormalizationWidth: canonicalPreferredCardWidth
    readonly property real childNormalizationHeight: canonicalPreferredHeight
    function childRecord(roleId) {
        return childGeometry ? childGeometry[roleId] : null
    }
    function childWidthScale(roleId) {
        const value = childRecord(roleId)
        return value && value.width_scale !== undefined ? Number(value.width_scale) : 1.0
    }
    function childHeightScale(roleId) {
        const value = childRecord(roleId)
        return value && value.height_scale !== undefined ? Number(value.height_scale) : 1.0
    }
    function childOffsetX(roleId) {
        const value = childRecord(roleId)
        return (value && value.x_offset !== undefined ? Number(value.x_offset) : 0.0)
            * (roleId === "volume_bar"
                ? volumeChildNormalizationWidth
                : childNormalizationWidth)
    }
    function childOffsetY(roleId) {
        const value = childRecord(roleId)
        return (value && value.y_offset !== undefined ? Number(value.y_offset) : 0.0)
            * childNormalizationHeight
    }
    function childAlignment(roleId, fallback) {
        const value = childRecord(roleId)
        return value && value.alignment !== undefined
            ? String(value.alignment) : String(fallback || "left")
    }
    // The existing header alignment record is the ONE widget orientation.
    // Header, artwork and metadata project their own semantic rails from it;
    // independent child text alignments remain independently editable.
    readonly property bool headerFlipped: childAlignment("header", "left") === "right"
    // Orientation relocates the whole authored lane. A separately editable
    // text alignment composes with that orientation, rather than cancelling it
    // by unconditionally returning its own authored-left default.
    function orientedChildAlignment(roleId, authored) {
        const locallyRight = childAlignment(roleId, authored) === "right"
        return locallyRight !== headerFlipped ? "right" : "left"
    }
    function childAnchor(roleId) {
        const value = childRecord(roleId)
        return value && value.anchor !== undefined ? String(value.anchor) : ""
    }

    // Stable retained semantic roles. Visibility is evaluated by the selected
    // Edit mapper, not by rebuilding this role list during content transitions.
    customEditableChildRoles: {
        const roles = []
        roles.push({
            "roleId": "header",
            "target": headerFrame,
            "geometryDependencies": [mediaColumn, headerSlot],
            "normalizationTarget": mediaRoot,
            "requirementTarget": null
        })
        roles.push({
            "roleId": "metadata",
            "target": trackMetadata,
            "geometryDependencies": [mediaColumn, mainBand, metadata],
            "collisionIgnoreRoleIds": ["artist"],
            "normalizationTarget": mediaRoot,
            "requirementTarget": null
        })
        roles.push({
            "roleId": "artist",
            "target": trackMetadata.artistEditTarget,
            "geometryDependencies": [mediaColumn, mainBand, metadata, trackMetadata],
            "collisionIgnoreRoleIds": ["metadata"],
            "normalizationTarget": mediaRoot,
            "requirementTarget": null
        })
        roles.push({
            "roleId": "playback_state",
            "target": playbackState,
            "geometryDependencies": [mediaColumn, mainBand, metadata],
            "normalizationTarget": mediaRoot,
            "requirementTarget": null
        })
        roles.push({
            "roleId": "artwork",
            "target": artworkFrame,
            "geometryDependencies": [mediaColumn, mainBand],
            "normalizationTarget": mediaRoot,
            "requirementTarget": null
        })
        roles.push({
            "roleId": "seek_bar",
            "target": progressTrack,
            "geometryDependencies": [mediaColumn, progressBand],
            // Seek-height changes reflow the retained controls slot below it.
            // Movement does not use this exception, so free placement still
            // cannot cross the controls surface.
            "resizeReflowRoleIds": ["transport_controls"],
            "resizeReflowAxes": ["vertical"],
            "normalizationTarget": mediaRoot,
            "requirementTarget": null
        })
        roles.push({
            "roleId": "volume_bar",
            "target": appVolumeTrack,
            "geometryDependencies": [appVolumeSlider],
            "containmentTarget": appVolumeSlider,

            // Existing volume CUSTOM offsets were normalized against the
            // former root+accessory baseline. Preserve those saved offsets;
            // its *legal containment* is now independently the lane itself.
            "normalizationTarget": mediaRoot,
            "normalizationWidthProperty": "volumeChildNormalizationWidth",
            "requirementTarget": null
        })
        roles.push({
            "roleId": "transport_controls",
            "target": controlsRow,
            "geometryDependencies": [mediaColumn, controlsBandSlot],
            "resizeReflowGate": controlsRow,
            "collisionIgnoreRoleIds": ["mute_button"],
            "normalizationTarget": mediaRoot,
            "requirementTarget": null
        })
        roles.push({
            "roleId": "mute_button",
            "target": systemMuteButton,
            "geometryDependencies": [mediaColumn, controlsBandSlot, controlsRow],
            "collisionIgnoreRoleIds": ["transport_controls"],
            "normalizationTarget": mediaRoot,
            "requirementTarget": null
        })
        for (let i = 0; i < roles.length; ++i) {
            if (roles[i].roleId !== "volume_bar") {
                roles[i].containmentTarget = mediaColumn

            }
        }
        return roles
    }
    // Every painted Media region above is now an editable semantic role. Keep
    // invisible authored-flow slots out of collision truth; selected-Edit exact
    // containment owns freely placed rectangles.
    customEditableChildObstacles: []
    customEditableChildRequirementTarget: null

    // Content-driven outer size (H option A). Width honours the historical
    // ordinary-card minimum footprint (600) and enlarges above it only when the
    // artwork + metadata genuinely require it. Height honours the historical
    // media floor of max(220, artwork_size + 60). Config-derived (no assigned
    // width/height dependency, no feedback). J refines exact dimensions.
    // Media's card keeps its accepted ordinary 600 px footprint; the optional
    // app-volume rail is a deliberate external accessory and therefore extends
    // the widget footprint instead of stealing 48 px from card content.
    readonly property real canonicalPreferredCardWidth: Math.max(
        600.0,
        mediaModel.artworkSize + 18.0 + Math.max(220.0, mediaModel.fontSize * 16.0)
            + mediaRoot.shellInset,
        headerFrame.implicitWidth + mediaRoot.shellInset
    )
    readonly property real canonicalPreferredHeight: Math.max(
        220.0, mediaModel.artworkSize + 60.0
    )
    readonly property real canonicalVolumeAccessoryExtent:
        mediaModel.appVolumeAvailable ? 48.0 : 0.0
    readonly property real volumeChildNormalizationWidth:
        canonicalPreferredCardWidth + canonicalVolumeAccessoryExtent
    readonly property real canonicalCardContentWidth: Math.max(
        1.0, canonicalPreferredCardWidth - mediaRoot.shellInset
    )
    // The 75% target is relative to the *live authored card*, not the
    // canonical 600 px reference. Parent X reflow must still enlarge/shrink
    // the seek bar. The canonical value remains its detached baseline/slot
    // reference; neither one is another outer-size authority.
    readonly property real canonicalProgressTrackWidth: Math.max(
        1.0, canonicalCardContentWidth * 0.75
    )
    readonly property real authoredCardContentWidth: Math.max(
        1.0, mediaRoot.authoredCardWidth - mediaRoot.shellInset
    )
    readonly property real authoredProgressTrackWidth: Math.max(
        1.0, canonicalProgressTrackWidth
            + (authoredCardContentWidth - canonicalCardContentWidth) * 0.75
    )
    readonly property real canonicalProgressTrackHeight: mediaModel.progressHeight
    readonly property real canonicalControlsHeight: Math.max(
        38.0, mediaRoot.mediaModel.fontSize * 2.15
    )
    // Child offsets are deltas from live authored rails, independently on X/Y.
    // An X-only edit must never freeze Y reflow (or vice versa), and changing
    // parent height must never cancel the Column's placement of essential rows.
    // An authored alignment flip controls which X rail is used; child Y edits
    // do not detach that horizontal relationship.
    readonly property real childPlacementEpsilon: 0.0001
    function childOnAuthoredRail(xOffset, yOffset) {
        return Math.abs(Number(xOffset || 0.0)) <= childPlacementEpsilon
            && Math.abs(Number(yOffset || 0.0)) <= childPlacementEpsilon
    }
    readonly property bool artworkOnAuthoredRail:
        Math.abs(Number(mediaModel.customArtworkXOffset || 0.0)) <= childPlacementEpsilon
    readonly property bool seekOnAuthoredRail:
        Math.abs(Number(mediaModel.customSeekXOffset || 0.0)) <= childPlacementEpsilon
    readonly property bool transportOnAuthoredRail:
        Math.abs(Number(mediaModel.customTransportXOffset || 0.0)) <= childPlacementEpsilon
    readonly property bool muteOnAuthoredRail: childOnAuthoredRail(
        mediaRoot.childOffsetX("mute_button"), mediaRoot.childOffsetY("mute_button")
    )
    readonly property real canonicalProgressBandHeight: canonicalProgressTrackHeight + 8.0
    readonly property real canonicalControlsBandY: canonicalPreferredHeight - canonicalControlsHeight
    readonly property real canonicalProgressBandY: canonicalPreferredHeight
        - canonicalProgressBandHeight
        - (mediaModel.controlsBandAvailable ? canonicalControlsHeight + 12.0 : 0.0)
    readonly property real canonicalSystemMuteHeight:
        (canonicalCardContentWidth < 210.0 ? 30.0 : 36.0) * 0.54675
    readonly property real canonicalSystemMuteWidth:
        (canonicalCardContentWidth < 210.0 ? 32.0 : 40.0) * 0.54675
    // Only the intrinsic Settings-authored artwork width is canonical.  The
    // actual on-card width/height remain derived from the live authored rails.
    readonly property real canonicalArtworkWidth:
        mediaModel.artworkSize * 0.85 * 0.85
    readonly property real canonicalVolumeTrackWidth: 18.0
    readonly property real canonicalVolumeTrackHeight: Math.max(
        1.0, canonicalPreferredHeight - 2.0 * mediaRoot.cardPadding - 12.0
    )
    // Use the very same authored outer Y extent as the card. The former
    // canonical-only height left the volume rail stranded when the parent
    // was stretched or compressed vertically.
    readonly property real authoredVolumeTrackHeight: Math.max(
        1.0, mediaRoot.authoredLayoutHeight - 2.0 * mediaRoot.cardPadding - 12.0
    )
    readonly property real customVolumeTrackWidth:
        canonicalVolumeTrackWidth * mediaModel.customVolumeWidthScale
    readonly property real customVolumeTrackHeight:
        authoredVolumeTrackHeight * mediaModel.customVolumeHeightScale
    // The existing 48 px accessory lane already fits the descriptor's full
    // 9.9..45 px volume-width range. Keep the lane fixed so a child drag cannot
    // steal width from the card or create a preferred-size feedback path.
    readonly property real volumeAccessoryExtent: canonicalVolumeAccessoryExtent
    readonly property real effectivePreferredWidth: mediaModel.contentExtentActive
        ? mediaModel.contentExtentWidth
        : canonicalPreferredCardWidth + canonicalVolumeAccessoryExtent
    readonly property real effectivePreferredHeight: mediaModel.contentExtentActive
        ? mediaModel.contentExtentHeight
        : canonicalPreferredHeight
    readonly property real sectionSpacing: mediaModel.contentExtentActive
        ? Math.max(
            7.0,
            Math.min(
                24.0,
                12.0 + (effectivePreferredHeight - canonicalPreferredHeight) * 0.045
            )
        )
        : 12.0
    readonly property real metadataSpacing: mediaModel.contentExtentActive
        ? Math.max(
            4.0,
            Math.min(
                14.0,
                7.0 + (effectivePreferredHeight - canonicalPreferredHeight) * 0.028
            )
        )
        : 7.0
    // Keep the external rail on the side with more remaining display space.
    // Comparing the retained outer-rect centre to the display centre is exactly
    // equivalent for a fixed-width widget, and stays event/binding driven: no
    // polling, timer, persisted side state, or second geometry owner. CUSTOM
    // movement inherits the same rule automatically as the retained x changes.
    readonly property bool appVolumeOnLeft:
        mediaModel.appVolumeAvailable
            && mediaRoot.parent !== null
            && (mediaRoot.x + mediaRoot.width / 2.0) > mediaRoot.parent.width / 2.0
    accessorySide: appVolumeOnLeft ? "left" : "right"
    accessoryExtent: volumeAccessoryExtent
    preferredContentWidth: effectivePreferredWidth
    preferredContentHeight: effectivePreferredHeight

    // CUSTOM children stay inside their actual card/accessory surfaces.
    // Outer Media resizing and the existing authored content policy alone own
    // parent extent; there is no child-driven second growth requirement.

    function appVolumeLevelAt(y, height) {
        if (height <= 0.0)
            return 0.0
        return Math.max(0.0, Math.min(1.0, 1.0 - y / height))
    }

    function seekFractionAt(x, width) {
        if (width <= 0.0)
            return 0.0
        return Math.max(0.0, Math.min(1.0, x / width))
    }

    readonly property int visibleSectionCount: 1
        + (mediaModel.showHeaderFrame ? 1 : 0)
        + (mediaModel.progressAvailable ? 1 : 0)
        + (mediaModel.controlsBandAvailable ? 1 : 0)

    TapHandler {
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: mediaRoot.refreshRequested()
    }

    // One event-driven wheel admission for the full Media footprint, including
    // the external volume rail. It reuses the existing app-volume runtime owner;
    // no polling/cadence is introduced. Python explicitly disables this owner
    // for the whole CUSTOM edit session so resize wheel has sole ownership.
    WheelHandler {
        target: null
        enabled: mediaRoot.volumeWheelEnabled
            && mediaRoot.mediaModel.interactionEnabled
            && mediaRoot.mediaModel.appVolumeAvailable
        onWheel: function(wheel) {
            if (wheel.angleDelta.y === 0)
                return
            mediaRoot.appVolumeStepRequested(wheel.angleDelta.y > 0 ? 1 : -1)
            wheel.accepted = true
        }
    }

    Column {
        id: mediaColumn
        objectName: "mediaContent"
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        spacing: mediaRoot.sectionSpacing
        // Presentation-only containment lock for CUSTOM content extents.
        // The authored band positions, outer content_extent and saved child
        // geometry remain unchanged; painting outside the real card is hidden.
        // The card's content has an unconditional legal paint boundary. The
        // separately mounted external-volume accessory has its own boundary.
        clip: true

        Item {
            id: headerSlot
            objectName: "mediaHeaderSlot"
            visible: mediaRoot.mediaModel.showHeaderFrame
            width: parent.width
            // Keep authored family flow stable. Free header placement is visual
            // child geometry; it must not become a second Column-height owner.
            height: visible ? headerFrame.implicitHeight : 0.0

            BrandedHeader {
                id: headerFrame
                frameObjectName: "mediaHeaderFrame"
                logoObjectName: "mediaHeaderLogo"
                textObjectName: "mediaHeaderText"
                visible: headerSlot.visible
                width: implicitWidth
                height: visible ? implicitHeight : 0.0
                transformOrigin: Item.TopLeft
                scale: mediaRoot.childWidthScale("header")
                readonly property string customAnchor: mediaRoot.childAnchor("header")
                property real customEditPlacementCompensationX: customAnchor.length > 0
                        || mediaRoot.headerFlipped
                    ? x - mediaRoot.childOffsetX("header") : 0.0
                property real customEditPlacementCompensationY: customAnchor.length > 0
                    ? y - mediaRoot.childOffsetY("header") : 0.0
                x: customAnchor.endsWith("right")
                    ? headerSlot.width - width * scale
                    : (customAnchor.endsWith("left")
                        ? 0.0
                        : (mediaRoot.headerFlipped
                            ? headerSlot.width - width * scale : 0.0)
                            + mediaRoot.childOffsetX("header"))
                y: customAnchor.startsWith("bottom")
                    ? mediaColumn.height - height * scale
                    : (customAnchor.startsWith("top")
                        ? 0.0 : mediaRoot.childOffsetY("header"))
                contentReversed: mediaRoot.childAlignment("header", "left") === "right"
                label: mediaRoot.mediaModel.providerName
                logoSource: mediaRoot.mediaModel.providerLogoSource
                fillColor: mediaRoot.mediaModel.headerFillColor
                borderColor: mediaRoot.mediaModel.headerBorderColor
                borderWidth: mediaRoot.scaleAwareHeaderStrokeWidth(mediaRoot.mediaModel.headerBorderWidth)
                textColor: mediaRoot.mediaModel.headerTextColor
                fontFamily: mediaRoot.mediaModel.fontFamily
                textShadowEnabled: mediaRoot.mediaModel.textShadowEnabled
                textShadowColor: mediaRoot.mediaModel.textShadowColor
                textShadowOffsetX: mediaRoot.mediaModel.textShadowOffsetX
                textShadowOffsetY: mediaRoot.mediaModel.textShadowOffsetY
                shadowEnabled: mediaRoot.mediaModel.surfaceShadowEnabled
                shadowColor: mediaRoot.mediaModel.surfaceShadowColor
                shadowBlur: mediaRoot.mediaModel.surfaceShadowBlur
                shadowOffsetX: mediaRoot.mediaModel.surfaceShadowOffsetX * 1.15
                shadowOffsetY: mediaRoot.mediaModel.surfaceShadowOffsetY * 1.15
            }
        }

        Item {
            id: mainBand
            objectName: "mediaMainBand"
            width: parent.width
            height: Math.max(
                1.0,
                parent.height
                    - headerSlot.height
                    - progressBand.height
                    - controlsBandSlot.height
                    - mediaColumn.spacing * (mediaRoot.visibleSectionCount - 1)
            )

            Item {
                id: metadata
                objectName: "mediaMetadata"
                // The authored metadata column is an independent layout
                // region, not a live by-product of the artwork child's edited
                // X/Y. If a first drag detaches artwork from its authored rail,
                // rebuilding metadata to full card width would immediately
                // overlap that artwork and feed a false collision into the SAME
                // gesture. Reserve the intrinsic artwork rail in both flip
                // orientations; actual artwork free placement belongs only to
                // its own child record and the shared collision admission.
                x: 2.0 + (mediaRoot.headerFlipped && artworkFrame.visible
                    ? artworkFrame.authoredArtworkWidth + 16.0 : 0.0)
                width: Math.max(
                    1.0,
                    artworkFrame.visible
                        ? (mediaRoot.headerFlipped
                            ? parent.width - x - 2.0
                            : parent.width - artworkFrame.authoredArtworkWidth - x - 18.0)
                        : parent.width - x
                )
                anchors.verticalCenter: parent.verticalCenter
                // Flow slots own the authored baseline explicitly, with no
                // second positioner/polish pass after the child editor clears
                // custom X/Y. Reset can be projected in the same QML evaluation.
                implicitHeight: trackMetadataSlot.height
                    + (playbackStateSlot.visible
                        ? mediaRoot.metadataSpacing + playbackStateSlot.height : 0.0)
                height: implicitHeight
                // Compact-Y text scales toward its CURRENT semantic rail:
                // unflipped is left-anchored and flipped is right-anchored.
                // A fixed left origin on the flipped card pulled the title and
                // artist inward after Reset -> Flip -> Save -> re-Edit -> Y shrink.
                transformOrigin: mediaRoot.headerFlipped ? Item.Right : Item.Left
                scale: implicitHeight > mainBand.height && implicitHeight > 0.0
                    ? Math.max(0.1, (mainBand.height - 2.0) / implicitHeight)
                    : 1.0

                // The Column positions only flow slots. Editable X/Y/scale
                // belong to the content INSIDE each slot, so a child reset
                // cannot fight the positioner's own Y assignment. Slot heights
                // describe authored text, never the offset of a freely moved
                // child; the existing shared editor owns only that offset.
                Item {
                    id: trackMetadataSlot
                    objectName: "mediaMetadataFlowSlot"
                    width: metadata.width
                    height: trackMetadata.implicitHeight

                    MediaMetadataColumn {
                        id: trackMetadata
                        objectName: "mediaTrackMetadata"
                        width: parent.width
                        mediaModel: mediaRoot.mediaModel
                        rowSpacing: mediaRoot.metadataSpacing
                        textAlignment: mediaRoot.orientedChildAlignment("metadata", "left")
                        artistOffsetX: mediaRoot.childOffsetX("artist")
                        artistOffsetY: mediaRoot.childOffsetY("artist")
                        artistScale: mediaRoot.childWidthScale("artist")
                        artistAlignment: mediaRoot.orientedChildAlignment(
                            "artist", mediaRoot.childAlignment("metadata", "left")
                        )
                        x: mediaRoot.childOffsetX("metadata")
                        y: mediaRoot.childOffsetY("metadata")
                        scale: mediaRoot.childWidthScale("metadata")
                        transformOrigin: Item.TopLeft
                    }
                }

                Item {
                    id: playbackStateSlot
                    objectName: "mediaPlaybackStateFlowSlot"
                    visible: mediaRoot.mediaModel.showPlaybackState
                        && mediaRoot.mediaModel.hasTrack
                    width: metadata.width
                    y: trackMetadataSlot.height + (visible ? mediaRoot.metadataSpacing : 0.0)
                    height: visible ? playbackState.implicitHeight : 0.0

                    ShadowedText {
                        id: playbackState
                        objectName: "mediaPlaybackState"
                        x: mediaRoot.childOffsetX("playback_state")
                        y: mediaRoot.childOffsetY("playback_state")
                        scale: mediaRoot.childWidthScale("playback_state")
                        transformOrigin: Item.TopLeft
                        width: parent.width
                        height: implicitHeight
                        text: mediaRoot.mediaModel.playbackState.toUpperCase()
                        horizontalAlignment: mediaRoot.orientedChildAlignment("playback_state", "left")
                            === "right" ? Text.AlignRight : Text.AlignLeft
                        color: mediaRoot.mediaModel.textColor
                        opacity: 0.62
                        font.family: mediaRoot.mediaModel.fontFamily
                        font.pointSize: mediaRoot.mediaModel.fontSize * 0.65
                        font.bold: true
                        shadowEnabled: mediaRoot.mediaModel.textShadowEnabled
                        shadowColor: mediaRoot.mediaModel.textShadowColor
                        shadowOffsetX: mediaRoot.mediaModel.textShadowOffsetX
                        shadowOffsetY: mediaRoot.mediaModel.textShadowOffsetY
                    }
                }
            }

            Rectangle {
                id: artworkFrame
                objectName: "mediaArtworkFrame"
                visible: mediaRoot.mediaModel.hasArtwork || mediaArtwork.transitionVisible
                // Keep the accepted top alignment and narrow right-hand rail, but
                // spend the *actual* free vertical space below the artwork.  The
                // seek band is not a global lower boundary: it only constrains the
                // artwork if its real horizontal rectangle could intersect this
                // right-hand column.  The full-width transport row remains the
                // normal hard lower boundary.
                // Positioner-owned `y` values are not synchronous during
                // content-extent changes. Derive the *same authored rails* from
                // their slot sizes/spacing, or a one-frame stale `y` can clamp
                // artwork to 1x1 and then freeze its edit target there.
                readonly property real mainRailTop:
                    (headerSlot.visible ? headerSlot.height + mediaColumn.spacing : 0.0)
                readonly property real mainRailBottom: mainRailTop + mainBand.height
                readonly property real progressRailTop: mainRailBottom
                    + (progressBand.visible ? mediaColumn.spacing : 0.0)
                readonly property real controlsRailTop: mainRailBottom
                    + (progressBand.visible
                        ? mediaColumn.spacing + progressBand.height : 0.0)
                    + (controlsBandSlot.visible ? mediaColumn.spacing : 0.0)
                readonly property real topInColumn: headerSlot.visible ? 0.0 : mainRailTop
                // Preserve the pre-child-editor authored X/Y artwork reflow.
                // Measurements come only from the existing card and Column
                // flow; they NEVER feed preferredContentWidth/Height.  The
                // provisional X below deliberately avoids a binding cycle:
                // the final width may be capped by available height, so using
                // artworkFrame.x in seek overlap would make width depend on
                // itself through bottomInColumn/referenceHeight.
                readonly property real baseArtworkWidth:
                    mediaRoot.canonicalArtworkWidth
                readonly property real extraHorizontalRoom:
                    mediaRoot.authoredCardWidth - mediaRoot.canonicalPreferredCardWidth
                readonly property real minimumMetadataRoom: Math.max(
                    180.0, mediaRoot.mediaModel.fontSize * 10.0
                )
                readonly property real provisionalArtworkWidth: Math.min(
                    Math.max(88.0, baseArtworkWidth + extraHorizontalRoom * 0.35),
                    Math.max(1.0, mediaRoot.authoredCardContentWidth - minimumMetadataRoom)
                )
                readonly property real provisionalArtworkX:
                    mediaRoot.authoredCardContentWidth - provisionalArtworkWidth
                readonly property real normalBottomInColumn: controlsBandSlot.visible
                    ? controlsRailTop - mediaColumn.spacing
                    : mediaColumn.height
                // The authored artwork reservation must observe only the
                // authored seek rail. Reading the EDITED seek target here makes
                // a seek move/resize change the artwork's reference size during
                // that same gesture, invalidating both live child mappings and
                // saved normalized offsets. Real off-rail seek/artwork collision
                // is owned separately by the shared edit collision surface.
                readonly property real authoredSeekX: mediaRoot.headerFlipped
                    ? Math.max(0.0, progressBand.width - 4.0
                        - mediaRoot.authoredProgressTrackWidth) : 2.0
                readonly property bool seekWouldIntersectArtwork: progressBand.visible
                    && (mediaRoot.headerFlipped
                        ? authoredSeekX < provisionalArtworkWidth + 2.0
                            && authoredSeekX + mediaRoot.authoredProgressTrackWidth > -2.0
                        : authoredSeekX + mediaRoot.authoredProgressTrackWidth
                            > provisionalArtworkX - 2.0)
                readonly property real bottomInColumn: seekWouldIntersectArtwork
                    ? progressRailTop - mediaColumn.spacing
                    : normalBottomInColumn
                readonly property real referenceHeight: Math.max(
                    1.0, bottomInColumn - topInColumn
                )
                readonly property real authoredArtworkWidth: Math.min(
                    provisionalArtworkWidth, referenceHeight
                )
                readonly property real artworkStrokeWidth: mediaRoot.scaleAwareStrokeWidth(
                    mediaRoot.mediaModel.artworkBorderWidth
                )
                readonly property real imageInset: Math.max(0.75, artworkStrokeWidth * 0.65)
                // Explicit ancestor invalidation for edit-only mapToItem chrome.
                // This is a cheap retained binding, not a cadence.
                property string customEditMappingDependency: [
                    mainBand.y, mediaColumn.y, mediaRoot.authoredCardX
                ].join("|")
                // Artwork frame geometry is freeform in CUSTOM. The source image
                // below remains PreserveAspectCrop, so the bitmap is never
                // distorted regardless of the rectangle the user draws.
                width: visible
                    ? authoredArtworkWidth
                        * mediaRoot.mediaModel.customArtworkWidthScale
                    : 0.0
                height: visible
                    ? referenceHeight
                        * mediaRoot.mediaModel.customArtworkHeightScale
                    : 0.0
                // Flipped-on-rail is a transient presentation displacement,
                // not an offset. The FIRST real child drag folds that displacement
                // into the existing authored-relative offset, then the artwork
                // detaches without a discontinuity. Crucially the baseline does
                // not depend on the offset it is computing, or the first pointer
                // sample jumps the artwork to the opposite edge of the card.
                readonly property real unflippedAuthoredX:
                    mediaRoot.authoredCardContentWidth - authoredArtworkWidth
                property real customEditPlacementCompensationX:
                    mediaRoot.headerFlipped && mediaRoot.artworkOnAuthoredRail
                        ? -unflippedAuthoredX : 0.0
                x: visible
                    ? (mediaRoot.headerFlipped && mediaRoot.artworkOnAuthoredRail
                        ? 0.0 : unflippedAuthoredX)
                        + mediaRoot.mediaModel.customArtworkXOffset
                            * mediaRoot.childNormalizationWidth
                    : 0.0
                y: visible
                    ? topInColumn - mainBand.y
                        + mediaRoot.mediaModel.customArtworkYOffset
                            * mediaRoot.canonicalPreferredHeight
                    : 0.0
                radius: mediaRoot.mediaModel.roundedArtwork
                    ? Math.min(width, height) / 8.0 : 0.0
                color: "transparent"
                clip: false

                // Artwork needs a little more separation than the card-level base
                // shadow: keep global direction, add 20% displacement, and use one
                // small cached rectangular blur instead of a broad layer effect.
                RectangularShadow {
                    anchors.fill: parent
                    visible: mediaRoot.mediaModel.surfaceShadowEnabled
                    color: mediaRoot.mediaModel.surfaceShadowColor
                    blur: mediaRoot.mediaModel.surfaceShadowBlur
                    radius: artworkFrame.radius
                    spread: 0.0
                    offset: Qt.vector2d(
                        mediaRoot.mediaModel.surfaceShadowOffsetX * 1.20,
                        mediaRoot.mediaModel.surfaceShadowOffsetY * 1.20
                    )
                    cached: true
                    z: -1
                }

                ArtworkFadeImage {
                    id: mediaArtwork
                    objectName: "mediaArtwork"
                    anchors.fill: parent
                    anchors.margins: artworkFrame.imageInset
                    source: mediaRoot.mediaModel.artworkSource
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                    // Provider-side smart crop removes baked-in Spotify video
                    // letterbox bands.  This retained mask then clips the live image
                    // to the actual non-square frame, preventing dark/transparent
                    // source corners from escaping outside the rounded border.
                    layer.enabled: mediaRoot.mediaModel.roundedArtwork
                    layer.effect: MultiEffect {
                        maskEnabled: true
                        maskSource: artworkMask
                    }
                }

                Rectangle {
                    id: artworkMask
                    anchors.fill: mediaArtwork
                    radius: Math.max(0.0, artworkFrame.radius - artworkFrame.imageInset)
                    visible: false
                    layer.enabled: true
                }

                Rectangle {
                    anchors.fill: parent
                    radius: artworkFrame.radius
                    color: "transparent"
                    border.width: artworkFrame.artworkStrokeWidth
                    border.color: mediaRoot.mediaModel.artworkBorderColor
                }
            }
        }

        Item {
            id: progressBand
            objectName: "mediaProgressBand"
            visible: mediaRoot.mediaModel.progressAvailable
            width: parent.width
            // The band reserves the Settings-authored seek height, NEVER the
            // independently edited target's height or offset. A child resize
            // must not move the Column, artwork and transport underneath the
            // editor. The actual seek rectangle uses the shared collision and
            // always-on card-containment contracts, not a second flow owner.
            height: visible ? mediaRoot.canonicalProgressBandHeight : 0.0

            Rectangle {
                id: progressTrack
                objectName: "mediaProgressTrack"
                property string customEditMappingDependency: [
                    progressBand.y, mediaColumn.y, mediaRoot.authoredCardX
                ].join("|")
                readonly property real customEditAncestorReflowY:
                    progressBand.y - mediaRoot.canonicalProgressBandY
                // Horizontal flip selects the opposite live seek rail only when
                // X was not independently positioned. Y always follows the live
                // Column band and keeps the user's relative offset.
                readonly property real flippedAuthoredRailX:
                    mediaRoot.headerFlipped && mediaRoot.seekOnAuthoredRail
                        ? Math.max(0.0, progressBand.width - 4.0 - width) : 0.0
                property real customEditPlacementCompensationX: flippedAuthoredRailX
                property real customEditPlacementCompensationY: 0.0
                x: 2.0 + flippedAuthoredRailX
                    + mediaRoot.mediaModel.customSeekXOffset
                        * mediaRoot.childNormalizationWidth
                y: 4.0
                    + mediaRoot.mediaModel.customSeekYOffset
                        * mediaRoot.canonicalPreferredHeight
                width: mediaRoot.authoredProgressTrackWidth
                    * mediaRoot.mediaModel.customSeekWidthScale
                height: mediaRoot.canonicalProgressTrackHeight
                    * mediaRoot.mediaModel.customSeekHeightScale
                radius: height / 2.0
                color: mediaRoot.mediaModel.progressTrackColor

                Rectangle {
                    visible: mediaRoot.mediaModel.progressShadowEnabled
                    x: 0.0
                    y: 2.0
                    width: parent.width
                    height: parent.height
                    radius: parent.radius
                    color: mediaRoot.mediaModel.progressShadowColor
                    z: -2
                }

                RectangularShadow {
                    objectName: "mediaProgressGlow"
                    visible: mediaRoot.mediaModel.progressGlowEnabled
                        && progressFill.width > 0.0
                    anchors.fill: progressFill
                    blur: Math.max(9.0, mediaRoot.mediaModel.progressHeight * 2.0)
                    spread: Math.max(1.0, mediaRoot.mediaModel.progressHeight * 0.35)
                    radius: progressFill.radius
                    color: mediaRoot.mediaModel.progressGlowColor
                    offset: Qt.vector2d(0.0, 0.0)
                    cached: true
                    z: -1
                }

                Rectangle {
                    id: progressFill
                    objectName: "mediaProgressFill"
                    width: parent.width * Math.max(
                        0.0, Math.min(1.0, mediaRoot.mediaModel.progressFraction)
                    )
                    height: parent.height
                    radius: Math.min(width, height) / 2.0
                    color: mediaRoot.mediaModel.progressFillColor
                }

                MouseArea {
                    id: progressSeekArea
                    objectName: "mediaProgressSeekArea"
                    anchors.fill: parent
                    enabled: mediaRoot.mediaModel.interactionEnabled
                        && mediaRoot.mediaModel.canSeek
                    acceptedButtons: Qt.LeftButton
                    onReleased: function(mouse) {
                        mediaRoot.seekFractionRequested(
                            mediaRoot.seekFractionAt(mouse.x, width)
                        )
                    }
                }
            }
        }

        Item {
            id: controlsBandSlot
            objectName: "mediaControlsBandSlot"
            visible: mediaRoot.mediaModel.controlsBandAvailable
            width: parent.width
            // This flow slot never takes its height from a customized child.
            // The essential transport remains at the bottom in either header
            // orientation; child edits cannot move the whole parent or the band.
            height: visible ? mediaRoot.canonicalControlsHeight : 0.0

            Rectangle {
                id: controlsRow
                objectName: "mediaControlsRow"
                visible: controlsBandSlot.visible
                property string customEditMappingDependency: [
                    controlsBandSlot.y, mediaColumn.y, mediaRoot.authoredCardX
                ].join("|")
                property bool customEditReflowEnabled: true
                readonly property real customEditAncestorReflowY:
                    controlsBandSlot.y - mediaRoot.canonicalControlsBandY
                property real customEditPlacementCompensationX: 0.0
                property real customEditPlacementCompensationY: 0.0
                x: mediaRoot.mediaModel.customTransportXOffset
                    * mediaRoot.childNormalizationWidth
                y: mediaRoot.mediaModel.customTransportYOffset
                    * mediaRoot.canonicalPreferredHeight
                width: mediaRoot.authoredCardContentWidth
                    * mediaRoot.mediaModel.customTransportWidthScale
                height: mediaRoot.canonicalControlsHeight
                    * mediaRoot.mediaModel.customTransportHeightScale
                radius: 12.0
                color: mediaRoot.mediaModel.controlsSurfaceColor
                border.width: mediaRoot.scaleAwareStrokeWidth(1.5)
                border.color: mediaRoot.mediaModel.controlsBorderColor
                clip: false

                // Transport bar uses the same global direction with 15% more
                // displacement and a deliberately small cached blur.
                RectangularShadow {
                    anchors.fill: parent
                    visible: mediaRoot.mediaModel.surfaceShadowEnabled
                    color: mediaRoot.mediaModel.surfaceShadowColor
                    blur: mediaRoot.mediaModel.surfaceShadowBlur
                    radius: parent.radius
                    spread: 0.0
                    offset: Qt.vector2d(
                        mediaRoot.mediaModel.surfaceShadowOffsetX * 1.15,
                        mediaRoot.mediaModel.surfaceShadowOffsetY * 1.15
                    )
                    cached: true
                    z: -1
                }

                Row {
                    id: transportGroup
                    objectName: "mediaTransportControls"
                    visible: mediaRoot.mediaModel.controlsAvailable
                    x: 0.0
                    y: 0.0
                    width: Math.max(
                        1.0,
                        parent.width
                            - (systemMuteButton.visible && mediaRoot.muteOnAuthoredRail
                                ? systemMuteButton.width + 8.0 : 0.0)
                    )
                    height: parent.height

                    Item {
                        id: previousButton
                        objectName: "mediaPreviousButton"
                        width: (parent.width - 2.0) / 3.0
                        height: parent.height
                        opacity: mediaRoot.mediaModel.canPrevious
                            ? (mediaRoot.mediaModel.interactionEnabled ? 1.0 : 0.68)
                            : 0.25
                        scale: previousTap.pressed ? 1.08 : 1.0

                        Text {
                            anchors.centerIn: parent
                            text: "←"
                            color: mediaRoot.mediaModel.controlsIconColor
                            font.family: mediaRoot.mediaModel.fontFamily
                            font.pointSize: mediaRoot.mediaModel.fontSize
                                * mediaRoot.mediaModel.customTransportHeightScale
                            font.bold: true
                        }

                        TapHandler {
                            id: previousTap
                            enabled: mediaRoot.mediaModel.interactionEnabled
                                && mediaRoot.mediaModel.canPrevious
                            acceptedButtons: Qt.LeftButton
                            onTapped: mediaRoot.previousRequested()
                        }
                    }

                    Rectangle {
                        width: mediaRoot.scaleAwareStrokeWidth(1.0)
                        height: parent.height * 0.7
                        y: (parent.height - height) / 2.0
                        color: mediaRoot.mediaModel.controlsSeparatorColor
                    }

                    Item {
                        id: playPauseButton
                        objectName: "mediaPlayPauseButton"
                        width: (parent.width - 2.0) / 3.0
                        height: parent.height
                        opacity: mediaRoot.mediaModel.canPlayPause
                            ? (mediaRoot.mediaModel.interactionEnabled ? 1.0 : 0.68)
                            : 0.25
                        scale: playPauseTap.pressed ? 1.08 : 1.0

                        Text {
                            anchors.centerIn: parent
                            text: mediaRoot.mediaModel.playbackState === "playing" ? "||" : "▶"
                            color: mediaRoot.mediaModel.controlsIconColor
                            font.family: mediaRoot.mediaModel.fontFamily
                            font.pointSize: mediaRoot.mediaModel.fontSize * 0.9
                                * mediaRoot.mediaModel.customTransportHeightScale
                            font.bold: true
                        }

                        TapHandler {
                            id: playPauseTap
                            enabled: mediaRoot.mediaModel.interactionEnabled
                                && mediaRoot.mediaModel.canPlayPause
                            acceptedButtons: Qt.LeftButton
                            onTapped: mediaRoot.playPauseRequested()
                        }
                    }

                    Rectangle {
                        width: mediaRoot.scaleAwareStrokeWidth(1.0)
                        height: parent.height * 0.7
                        y: (parent.height - height) / 2.0
                        color: mediaRoot.mediaModel.controlsSeparatorColor
                    }

                    Item {
                        id: nextButton
                        objectName: "mediaNextButton"
                        width: (parent.width - 2.0) / 3.0
                        height: parent.height
                        opacity: mediaRoot.mediaModel.canNext
                            ? (mediaRoot.mediaModel.interactionEnabled ? 1.0 : 0.68)
                            : 0.25
                        scale: nextTap.pressed ? 1.08 : 1.0

                        Text {
                            anchors.centerIn: parent
                            text: "→"
                            color: mediaRoot.mediaModel.controlsIconColor
                            font.family: mediaRoot.mediaModel.fontFamily
                            font.pointSize: mediaRoot.mediaModel.fontSize
                                * mediaRoot.mediaModel.customTransportHeightScale
                            font.bold: true
                        }

                        TapHandler {
                            id: nextTap
                            enabled: mediaRoot.mediaModel.interactionEnabled
                                && mediaRoot.mediaModel.canNext
                            acceptedButtons: Qt.LeftButton
                            onTapped: mediaRoot.nextRequested()
                        }
                    }
                }

                Rectangle {
                    id: systemMuteButton
                    objectName: "mediaSystemMuteButton"
                    visible: mediaRoot.mediaModel.systemMuteAvailable
                    // The mute control is an intrinsic-shape child. When the
                    // non-uniform control bar becomes too narrow/short it shrinks
                    // through one common factor; it never inherits independent X/Y
                    // transport scales and therefore cannot become a squashed pill.
                    readonly property real requestedCustomScale:
                        mediaRoot.childWidthScale("mute_button")
                    readonly property real fitScale: Math.max(
                        0.01,
                        Math.min(
                            requestedCustomScale,
                            parent.height * 0.92 / Math.max(
                                1.0, mediaRoot.canonicalSystemMuteHeight
                            ),
                            parent.width * 0.28 / Math.max(
                                1.0, mediaRoot.canonicalSystemMuteWidth
                            )
                        )
                    )
                    height: mediaRoot.canonicalSystemMuteHeight * fitScale
                    width: mediaRoot.canonicalSystemMuteWidth * fitScale
                    anchors.verticalCenter: parent.verticalCenter
                    // The transport bar's optical center sits just above its
                    // geometric center. Keep this presentation-only correction
                    // separate from CUSTOM's authored X/Y offset.
                    anchors.verticalCenterOffset: -2.0
                    anchors.right: parent.right
                    anchors.rightMargin: 4.0
                    transform: Translate {
                        id: mutePaintTranslation
                        x: mediaRoot.childOffsetX("mute_button")
                        y: mediaRoot.childOffsetY("mute_button")
                    }
                    // Read the applied translation after Qt updates its binding.
                    // The non-bindable QQuickItem.transform list is never read.
                    readonly property string customEditMappingDependency: [
                        mutePaintTranslation.x, mutePaintTranslation.y
                    ].join("|")
                    radius: Math.max(8.0, Math.min(12.0, height * 0.32))
                    border.width: mediaRoot.scaleAwareStrokeWidth(1.25)
                    border.color: mediaRoot.mediaModel.controlsBorderColor
                    scale: systemMuteTap.pressed ? 1.06 : 1.0
                    property real feedbackOpacity: 0.0
                    gradient: Gradient {
                        GradientStop {
                            position: 0.0
                            color: Qt.rgba(
                                mediaRoot.mediaModel.systemMuteBackgroundColor.r,
                                mediaRoot.mediaModel.systemMuteBackgroundColor.g,
                                mediaRoot.mediaModel.systemMuteBackgroundColor.b,
                                Math.min(
                                    1.0,
                                    mediaRoot.mediaModel.systemMuteBackgroundColor.a * 0.95
                                        + 30.0 / 255.0
                                )
                            )
                        }
                        GradientStop {
                            position: 1.0
                            color: Qt.rgba(
                                mediaRoot.mediaModel.systemMuteBackgroundColor.r,
                                mediaRoot.mediaModel.systemMuteBackgroundColor.g,
                                mediaRoot.mediaModel.systemMuteBackgroundColor.b,
                                mediaRoot.mediaModel.systemMuteBackgroundColor.a * 0.85
                            )
                        }
                    }

                    Canvas {
                        id: systemMuteIcon
                        objectName: "mediaSystemMuteIcon"
                        anchors.centerIn: parent
                        width: Math.min(parent.width, parent.height) * 0.64
                        height: width
                        property bool muted: mediaRoot.mediaModel.systemMuted
                        property color iconColor: mediaRoot.mediaModel.systemMuteIconColor
                        onMutedChanged: requestPaint()
                        onIconColorChanged: requestPaint()
                        onWidthChanged: requestPaint()
                        onHeightChanged: requestPaint()
                        onPaint: {
                            var context = getContext("2d")
                            context.reset()
                            context.fillStyle = iconColor
                            context.strokeStyle = iconColor
                            context.lineCap = "round"
                            context.lineWidth = Math.max(1.2, width * 0.045)
                            context.beginPath()
                            context.moveTo(width * 0.18, height * 0.42)
                            context.lineTo(width * 0.32, height * 0.42)
                            context.lineTo(width * 0.48, height * 0.27)
                            context.lineTo(width * 0.48, height * 0.73)
                            context.lineTo(width * 0.32, height * 0.58)
                            context.lineTo(width * 0.18, height * 0.58)
                            context.closePath()
                            context.fill()
                            if (muted) {
                                context.beginPath()
                                context.moveTo(width * 0.48, height * 0.28)
                                context.lineTo(width * 0.78, height * 0.72)
                                context.stroke()
                            } else {
                                context.beginPath()
                                context.arc(
                                    width * 0.44, height * 0.5, width * 0.22,
                                    -0.68, 0.68
                                )
                                context.stroke()
                                context.beginPath()
                                context.arc(
                                    width * 0.44, height * 0.5, width * 0.36,
                                    -0.68, 0.68
                                )
                                context.stroke()
                            }
                        }
                    }

                    Rectangle {
                        anchors.fill: parent
                        radius: parent.radius
                        color: "white"
                        opacity: parent.feedbackOpacity
                    }

                    SequentialAnimation {
                        id: systemMuteFeedback
                        NumberAnimation {
                            target: systemMuteButton
                            property: "feedbackOpacity"
                            from: 0.47
                            to: 0.0
                            duration: 350
                            easing.type: Easing.OutCubic
                        }
                    }

                    TapHandler {
                        id: systemMuteTap
                        enabled: mediaRoot.mediaModel.interactionEnabled
                        acceptedButtons: Qt.LeftButton
                        onTapped: {
                            systemMuteFeedback.restart()
                            mediaRoot.systemMuteToggleRequested()
                        }
                    }
                }
            }
        }
    }

    accessoryContent: [
        Item {
                id: appVolumeSlider
                objectName: "mediaAppVolumeSlider"
                visible: mediaRoot.mediaModel.appVolumeAvailable
                anchors.fill: parent
                // The external accessory has its own paint containment; card
                // children never use this lane for geometry or clipping.
                clip: true

            Rectangle {
                id: appVolumeTrack
                objectName: "mediaAppVolumeTrack"
                visible: appVolumeSlider.visible
                property string customEditMappingDependency: [
                    mediaRoot.appVolumeOnLeft ? 1 : 0,
                    appVolumeSlider.x, appVolumeSlider.y
                ].join("|")
                // Bound the actual item, not merely the accessory's paint. The
                // shared Edit role maps this item, so its proxy follows the
                // visible track when either parent axis is changed.
                readonly property real requestedTrackX:
                    (parent.width - mediaRoot.canonicalVolumeTrackWidth) / 2.0
                    + mediaRoot.mediaModel.customVolumeXOffset
                        * (mediaRoot.canonicalPreferredCardWidth
                            + mediaRoot.canonicalVolumeAccessoryExtent)
                readonly property real requestedTrackY: mediaRoot.cardPadding + 6.0
                    + mediaRoot.mediaModel.customVolumeYOffset
                        * mediaRoot.canonicalPreferredHeight
                x: Math.max(0.0, Math.min(requestedTrackX, Math.max(0.0, parent.width - width)))
                y: Math.max(0.0, Math.min(requestedTrackY, Math.max(0.0, parent.height - height)))
                // A parent shrink can clamp an older saved offset. Rebasing on
                // the first REAL child move prevents the offset from jumping
                // back to its old, now-illegal value. Zero-motion clicks do not
                // write or change the saved geometry. This is an existing
                // gesture-local placement seam, not a second persisted owner.
                readonly property real customEditPlacementCompensationX: x - requestedTrackX
                readonly property real customEditPlacementCompensationY: y - requestedTrackY
                width: mediaRoot.customVolumeTrackWidth
                height: mediaRoot.customVolumeTrackHeight
                radius: width / 2.0
                color: mediaRoot.mediaModel.appVolumeTrackColor
                border.width: mediaRoot.scaleAwareStrokeWidth(2.5)
                border.color: mediaRoot.mediaModel.appVolumeBorderColor
                clip: false
    
                // Volume track keeps the same global direction with a subtle 5%
                // extra displacement and the same small cached blur.
                RectangularShadow {
                    anchors.fill: parent
                    visible: mediaRoot.mediaModel.surfaceShadowEnabled
                    color: mediaRoot.mediaModel.surfaceShadowColor
                    blur: mediaRoot.mediaModel.surfaceShadowBlur
                    radius: parent.radius
                    spread: 0.0
                    offset: Qt.vector2d(
                        mediaRoot.mediaModel.surfaceShadowOffsetX * 1.05,
                        mediaRoot.mediaModel.surfaceShadowOffsetY * 1.05
                    )
                    cached: true
                    z: -1
                }
    
                Rectangle {
                    objectName: "mediaAppVolumeFill"
                    width: parent.width
                    readonly property real normalizedLevel: Math.max(
                        0.0, Math.min(1.0, mediaRoot.mediaModel.appVolumeLevel)
                    )
                    height: normalizedLevel <= 0.0
                        ? 0.0
                        : Math.min(parent.height, Math.max(2.0, parent.height * normalizedLevel))
                    y: (parent.height - height) / 2.0
                    radius: width / 2.0
                    color: mediaRoot.mediaModel.appVolumeFillColor
                    border.width: height > 0.0
                        ? mediaRoot.scaleAwareStrokeWidth(2.5) : 0.0
                    border.color: mediaRoot.mediaModel.appVolumeBorderColor
                }
    
                MouseArea {
                    anchors.fill: parent
                    enabled: mediaRoot.mediaModel.interactionEnabled
                    acceptedButtons: Qt.LeftButton
                    onPressed: function(mouse) {
                        mediaRoot.appVolumeLevelRequested(
                            mediaRoot.appVolumeLevelAt(mouse.y, height)
                        )
                    }
                    onPositionChanged: function(mouse) {
                        if (pressed) {
                            mediaRoot.appVolumeLevelRequested(
                                mediaRoot.appVolumeLevelAt(mouse.y, height)
                            )
                        }
                    }
                }
            }
        }
    ]

}
