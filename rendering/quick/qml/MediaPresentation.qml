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

    // CUSTOM exposes only four deliberate Media child roles. The shared edit
    // overlay owns the smaller handles and Python/session owns normalized
    // factors/persistence; these retained targets never become geometry owners.
    customEditableChildRoles: {
        const roles = []
        const normW = mediaRoot.canonicalPreferredCardWidth
            + mediaRoot.canonicalVolumeAccessoryExtent
        const normH = mediaRoot.canonicalPreferredHeight
        if (artworkFrame.visible) {
            roles.push({
                "roleId": "artwork",
                "target": artworkFrame,
                "geometryDependencies": [mediaColumn, mainBand],
                "normalizationWidth": normW,
                "normalizationHeight": normH,
                "requirementTarget": customChildRequirement
            })
        }
        if (progressBand.visible) {
            roles.push({
                "roleId": "seek_bar",
                "target": progressTrack,
                "geometryDependencies": [mediaColumn, progressBand],
                // Seek-height changes reflow the retained controls slot below it.
                // Movement does not use this exception, so free placement still
                // cannot cross the controls surface.
                "resizeReflowRoleIds": ["transport_controls"],
                "resizeReflowAxes": ["vertical"],
                "normalizationWidth": normW,
                "normalizationHeight": normH,
                "requirementTarget": customChildRequirement
            })
        }
        if (appVolumeSlider.visible) {
            roles.push({
                "roleId": "volume_bar",
                "target": appVolumeTrack,
                "geometryDependencies": [appVolumeSlider],
                "normalizationWidth": normW,
                "normalizationHeight": normH,
                "requirementTarget": customChildRequirement
            })
        }
        if (controlsRow.visible) {
            roles.push({
                "roleId": "transport_controls",
                "target": controlsRow,
                "geometryDependencies": [mediaColumn, controlsBandSlot],
                "resizeReflowGate": controlsRow,
                "normalizationWidth": normW,
                "normalizationHeight": normH,
                "requirementTarget": customChildRequirement
            })
        }
        return roles
    }
    // Collision truth includes only painted non-role regions. Transport edits
    // own the complete controls surface, including the mute control; seek itself
    // is already an editable peer. Do not register invisible structural slots
    // such as progressBand as obstacles: once a child is freely placed, an empty
    // authored layout reservation must not become a second/ghost placement
    // authority. These rectangles are inspected only while the selected edit
    // layer exists.
    customEditableChildObstacles: [
        headerFrame,
        metadata
    ]
    customEditableChildRequirementTarget: customChildRequirement

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
    readonly property real canonicalCardContentWidth: Math.max(
        1.0, canonicalPreferredCardWidth - mediaRoot.shellInset
    )
    readonly property real canonicalProgressTrackWidth: Math.max(
        1.0,
        (canonicalCardContentWidth
            - 2.0 * Math.max(12.0, canonicalCardContentWidth * 0.08)) * 0.75
    )
    readonly property real canonicalProgressTrackHeight: mediaModel.progressHeight
    readonly property real canonicalControlsHeight: Math.max(
        38.0, mediaRoot.mediaModel.fontSize * 2.15
    )
    // Manual child placement is authored-relative, not relative to a
    // reflowing Column slot. Once seek/transport has a real X/Y offset, cancel
    // later ancestor-band movement in the retained target binding. The first real
    // move folds the current ancestor displacement into the same persisted offset
    // through the shared placement-compensation contract, so detachment is visual
    // no-op at the pointer. These are static bindings only; no edit/runtime cadence.
    readonly property real childPlacementEpsilon: 0.0001
    function childOnAuthoredRail(xOffset, yOffset) {
        return Math.abs(Number(xOffset || 0.0)) <= childPlacementEpsilon
            && Math.abs(Number(yOffset || 0.0)) <= childPlacementEpsilon
    }
    readonly property bool seekOnAuthoredRail: childOnAuthoredRail(
        mediaModel.customSeekXOffset, mediaModel.customSeekYOffset
    )
    readonly property bool transportOnAuthoredRail: childOnAuthoredRail(
        mediaModel.customTransportXOffset, mediaModel.customTransportYOffset
    )
    readonly property real canonicalProgressBandHeight: canonicalProgressTrackHeight + 8.0
    readonly property real canonicalControlsBandY: canonicalPreferredHeight - canonicalControlsHeight
    readonly property real canonicalProgressBandY: canonicalPreferredHeight
        - canonicalProgressBandHeight
        - (mediaModel.controlsBandAvailable ? canonicalControlsHeight + 12.0 : 0.0)
    readonly property real canonicalSystemMuteHeight:
        (canonicalCardContentWidth < 210.0 ? 30.0 : 36.0) * 0.75
    readonly property real canonicalSystemMuteWidth:
        (canonicalCardContentWidth < 210.0 ? 32.0 : 40.0) * 0.75
    readonly property real canonicalArtworkWidth: Math.max(
        1.0,
        Math.min(
            mediaRoot.mediaModel.artworkSize * 0.85 * 0.85,
            canonicalCardContentWidth
                - Math.max(180.0, mediaRoot.mediaModel.fontSize * 10.0)
        )
    )
    readonly property real canonicalArtworkHeight: Math.max(
        88.0,
        canonicalPreferredHeight
            - (mediaModel.controlsBandAvailable
                ? canonicalControlsHeight + 12.0 : 0.0)
    )
    readonly property real canonicalVolumeTrackWidth: 18.0
    readonly property real canonicalVolumeTrackHeight: Math.max(
        1.0, canonicalPreferredHeight - 2.0 * mediaRoot.cardPadding - 12.0
    )
    readonly property real customVolumeTrackWidth:
        canonicalVolumeTrackWidth * mediaModel.customVolumeWidthScale
    readonly property real customVolumeTrackHeight:
        canonicalVolumeTrackHeight * mediaModel.customVolumeHeightScale
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

    // Family-wide grow-only requirement is observed live while a child gesture
    // runs. It is built from stable authored baselines plus child geometry only,
    // so outer growth can never feed back into the child baseline.
    QtObject {
        id: customChildRequirement
        // Only visible/admitted roles contribute. Persisted geometry for a
        // temporarily absent seek/volume/transport role must not silently grow
        // the card while that child is not present.
        readonly property real artworkWidthExtra: artworkFrame.visible
            ? Math.max(0.0, artworkFrame.width - mediaRoot.canonicalArtworkWidth)
            : 0.0
        readonly property real artworkHeightExtra: artworkFrame.visible
            ? Math.max(0.0, artworkFrame.height - mediaRoot.canonicalArtworkHeight)
            : 0.0
        // Nested seek/transport contribute to family reflow only while they
        // remain on their authored rails. Once freely placed, their exact mapped
        // occupied rectangles are already owned by the selected Edit containment
        // floor; continuing to grow the family reservation from their size would
        // create a second invisible layout authority and empty-space inflation.
        readonly property real seekWidthExtra: progressBand.visible
                && mediaRoot.seekOnAuthoredRail
            ? Math.max(0.0, progressTrack.width - mediaRoot.canonicalProgressTrackWidth)
            : 0.0
        readonly property real seekHeightExtra: progressBand.visible
                && mediaRoot.seekOnAuthoredRail
            ? Math.max(0.0, progressTrack.height - mediaRoot.canonicalProgressTrackHeight)
            : 0.0
        readonly property real transportWidthExtra: controlsRow.visible
                && mediaRoot.transportOnAuthoredRail
            ? Math.max(0.0, controlsRow.width - mediaRoot.canonicalCardContentWidth)
            : 0.0
        readonly property real transportHeightExtra: controlsRow.visible
                && mediaRoot.transportOnAuthoredRail
            ? Math.max(0.0, controlsRow.height - mediaRoot.canonicalControlsHeight)
            : 0.0
        readonly property real accessoryHeightExtra: appVolumeSlider.visible
            ? Math.max(0.0, appVolumeTrack.height - mediaRoot.canonicalVolumeTrackHeight)
            : 0.0

        // Placement itself is not approximated here. The selected Edit layer
        // derives an exact transient floor from the mapped occupied role rects it
        // already owns. Keeping this family target size/reflow-only avoids the old
        // failure where any harmless positive move inflated the parent even while
        // the child still fit comfortably inside it.

        // Artwork occupies the right rail while seek occupies the left. If both
        // widen, preserving their accepted baseline separation requires both
        // positive deltas, not merely the larger one. Transport owns its own
        // full-width band and therefore competes by max rather than sum.
        readonly property real cardWidthExtra: Math.max(
            transportWidthExtra, artworkWidthExtra + seekWidthExtra
        )
        readonly property real cardHeightExtra:
            artworkHeightExtra + seekHeightExtra + transportHeightExtra
        readonly property real requiredContentWidth:
            mediaRoot.canonicalPreferredCardWidth
                + mediaRoot.canonicalVolumeAccessoryExtent
                + cardWidthExtra
        readonly property real requiredContentHeight: Math.max(
            mediaRoot.canonicalPreferredHeight + cardHeightExtra,
            mediaRoot.canonicalPreferredHeight + accessoryHeightExtra
        )
    }

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

        BrandedHeader {
            id: headerFrame
            frameObjectName: "mediaHeaderFrame"
            logoObjectName: "mediaHeaderLogo"
            textObjectName: "mediaHeaderText"
            visible: mediaRoot.mediaModel.showHeaderFrame
            width: implicitWidth
            height: visible ? implicitHeight : 0.0
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

        Item {
            id: mainBand
            objectName: "mediaMainBand"
            width: parent.width
            height: Math.max(
                1.0,
                parent.height
                    - headerFrame.height
                    - progressBand.height
                    - controlsBandSlot.height
                    - mediaColumn.spacing * (mediaRoot.visibleSectionCount - 1)
            )

            Column {
                id: metadata
                objectName: "mediaMetadata"
                anchors.left: parent.left
                anchors.leftMargin: 2.0
                anchors.right: artworkFrame.visible ? artworkFrame.left : parent.right
                anchors.rightMargin: artworkFrame.visible ? 18.0 : 0.0
                anchors.verticalCenter: parent.verticalCenter
                spacing: mediaRoot.metadataSpacing
                // Vertical compaction must never visually translate the metadata
                // lane away from its authored left edge.  Scaling around the
                // centre made title/artist appear to drift right during some
                // CUSTOM reflows even though the layout anchors were correct.
                transformOrigin: Item.Left
                scale: implicitHeight > mainBand.height && implicitHeight > 0.0
                    ? Math.max(0.1, (mainBand.height - 2.0) / implicitHeight)
                    : 1.0

                MediaMetadataColumn {
                    id: trackMetadata
                    width: metadata.width
                    mediaModel: mediaRoot.mediaModel
                    rowSpacing: mediaRoot.metadataSpacing
                }

                ShadowedText {
                    objectName: "mediaPlaybackState"
                    visible: mediaRoot.mediaModel.showPlaybackState
                        && mediaRoot.mediaModel.hasTrack
                    width: metadata.width
                    height: visible ? implicitHeight : 0.0
                    text: mediaRoot.mediaModel.playbackState.toUpperCase()
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
                readonly property real topInColumn: headerFrame.visible
                    ? headerFrame.y
                    : mainBand.y
                readonly property real artworkStrokeWidth: mediaRoot.scaleAwareStrokeWidth(
                    mediaRoot.mediaModel.artworkBorderWidth
                )
                readonly property real imageInset: Math.max(0.75, artworkStrokeWidth * 0.65)
                // Explicit ancestor invalidation for edit-only mapToItem chrome.
                // This is a cheap retained binding, not a cadence.
                property real customEditMappingDependency: mainBand.y + mediaColumn.y
                    + mediaRoot.authoredCardX
                // Artwork frame geometry is freeform in CUSTOM. The source image
                // below remains PreserveAspectCrop, so the bitmap is never
                // distorted regardless of the rectangle the user draws.
                width: visible
                    ? mediaRoot.canonicalArtworkWidth
                        * mediaRoot.mediaModel.customArtworkWidthScale
                    : 0.0
                height: visible
                    ? mediaRoot.canonicalArtworkHeight
                        * mediaRoot.mediaModel.customArtworkHeightScale
                    : 0.0
                // Stable authored X anchor: child width no longer implicitly
                // changes its own position. The bottom-left edit handle owns the
                // one compensating X offset needed to keep the right edge fixed.
                x: visible
                    ? mediaRoot.canonicalCardContentWidth
                        - mediaRoot.canonicalArtworkWidth
                        + mediaRoot.mediaModel.customArtworkXOffset
                            * (mediaRoot.canonicalPreferredCardWidth
                                + mediaRoot.canonicalVolumeAccessoryExtent)
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
            // This slot is authored-flow bookkeeping, not the free child's
            // geometry owner. While seek is on-rail it follows seek height so
            // downstream authored content reflows naturally. Once seek is moved
            // off-rail, keep only the canonical reservation; the selected Edit
            // containment floor owns the real placed rectangle.
            height: visible
                ? (mediaRoot.seekOnAuthoredRail
                    ? progressTrack.height + 8.0
                    : mediaRoot.canonicalProgressBandHeight)
                : 0.0

            Rectangle {
                id: progressTrack
                objectName: "mediaProgressTrack"
                property real customEditMappingDependency: progressBand.y + mediaColumn.y
                    + mediaRoot.authoredCardX
                readonly property real customEditAncestorReflowY:
                    progressBand.y - mediaRoot.canonicalProgressBandY
                property real customEditPlacementCompensationX: 0.0
                property real customEditPlacementCompensationY:
                    mediaRoot.seekOnAuthoredRail ? customEditAncestorReflowY : 0.0
                x: 2.0
                    + mediaRoot.mediaModel.customSeekXOffset
                        * (mediaRoot.canonicalPreferredCardWidth
                            + mediaRoot.canonicalVolumeAccessoryExtent)
                y: 4.0
                    + mediaRoot.mediaModel.customSeekYOffset
                        * mediaRoot.canonicalPreferredHeight
                    - (mediaRoot.seekOnAuthoredRail ? 0.0 : customEditAncestorReflowY)
                width: mediaRoot.canonicalProgressTrackWidth
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
            // As with progressBand, an off-rail transport is no longer an
            // authored-flow child. Preserve the canonical slot so family layout
            // remains stable while exact placement/containment owns the visual
            // rectangle in selected Edit.
            height: visible
                ? (mediaRoot.transportOnAuthoredRail
                    ? Math.max(mediaRoot.canonicalControlsHeight, controlsRow.height)
                    : mediaRoot.canonicalControlsHeight)
                : 0.0

            Rectangle {
                id: controlsRow
                objectName: "mediaControlsRow"
                visible: controlsBandSlot.visible
                property real customEditMappingDependency: controlsBandSlot.y + mediaColumn.y
                    + mediaRoot.authoredCardX
                property bool customEditReflowEnabled: mediaRoot.transportOnAuthoredRail
                readonly property real customEditAncestorReflowY:
                    controlsBandSlot.y - mediaRoot.canonicalControlsBandY
                property real customEditPlacementCompensationX: 0.0
                property real customEditPlacementCompensationY:
                    mediaRoot.transportOnAuthoredRail ? customEditAncestorReflowY : 0.0
                x: mediaRoot.mediaModel.customTransportXOffset
                    * (mediaRoot.canonicalPreferredCardWidth
                        + mediaRoot.canonicalVolumeAccessoryExtent)
                y: mediaRoot.mediaModel.customTransportYOffset
                    * mediaRoot.canonicalPreferredHeight
                    - (mediaRoot.transportOnAuthoredRail ? 0.0 : customEditAncestorReflowY)
                width: mediaRoot.canonicalCardContentWidth
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
                            - (systemMuteButton.visible ? systemMuteButton.width + 8.0 : 0.0)
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
                    height: Math.min(
                        parent.height * 0.92,
                        mediaRoot.canonicalSystemMuteHeight
                            * mediaRoot.mediaModel.customTransportHeightScale
                    )
                    width: Math.min(
                        parent.width * 0.28,
                        mediaRoot.canonicalSystemMuteWidth
                            * mediaRoot.mediaModel.customTransportWidthScale
                    )
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    anchors.rightMargin: 4.0
                    radius: Math.max(8.0, Math.min(12.0, height * 0.32))
                    border.width: mediaRoot.scaleAwareStrokeWidth(1.25)
                    border.color: mediaRoot.mediaModel.systemMuteBorderColor
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

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 3.0
                        radius: Math.max(1.0, parent.radius - 1.0)
                        color: "transparent"
                        border.width: mediaRoot.scaleAwareStrokeWidth(1.0)
                        border.color: mediaRoot.mediaModel.systemMuteInnerBorderColor
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
    
            Rectangle {
                id: appVolumeTrack
                objectName: "mediaAppVolumeTrack"
                visible: appVolumeSlider.visible
                property real customEditMappingDependency:
                    (mediaRoot.appVolumeOnLeft ? 1.0 : 0.0) + appVolumeSlider.x + appVolumeSlider.y
                x: (parent.width - mediaRoot.canonicalVolumeTrackWidth) / 2.0
                    + mediaRoot.mediaModel.customVolumeXOffset
                        * (mediaRoot.canonicalPreferredCardWidth
                            + mediaRoot.canonicalVolumeAccessoryExtent)
                y: mediaRoot.cardPadding + 6.0
                    + mediaRoot.mediaModel.customVolumeYOffset
                        * mediaRoot.canonicalPreferredHeight
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
