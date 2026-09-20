import QtQuick
import QtQuick.Effects

OverlayWidget {
    id: achievementRoot
    objectName: "achievementPulsePresentation"


    required property var achievementModel
    semanticDoubleClickEnabled: achievementModel.interactionEnabled
    signal refreshRequested()
    signal settingsRequested(string target)
    signal storeRequested()

    readonly property real authoredWidth: achievementModel.authoredWidth
    readonly property real authoredHeight: achievementModel.authoredHeight
    readonly property real baseAuthoredWidth: achievementModel.baseAuthoredWidth
    readonly property real baseAuthoredHeight: achievementModel.baseAuthoredHeight
    readonly property real extraContentWidth: Math.max(0.0, authoredWidth - baseAuthoredWidth)
    // A reversed CUSTOM card can have a genuinely empty leading gutter after
    // its children were independently placed. Retain their authored coordinates
    // while trimming that gutter; do not scale the artwork/text or migrate any
    // role's saved normalized offsets when the outer left edge moves.
    readonly property real leadingTrim: headerFlipped && achievementModel.contentExtentActive
        ? Math.max(0.0, baseAuthoredWidth - authoredWidth) : 0.0
    // The ordinary authored baseline is still the Restore Size reference.
    // Only a reversed card with real visible leading clearance offers this
    // selected-Edit capability; non-reversed/custom-placed content stays guarded.
    readonly property real customLeadingTrimAllowance: headerFlipped && normalContent.visible
        ? Math.max(0.0, Math.min(
            headerFrame.visible ? headerFrame.x : baseAuthoredWidth,
            artworkFrame.visible ? artworkFrame.x : baseAuthoredWidth,
            metricText.visible ? metricText.x : baseAuthoredWidth,
            gameTitle.visible ? gameTitle.x : baseAuthoredWidth,
            achievementListFrame.visible ? achievementListFrame.x : baseAuthoredWidth,
            latestArtworkFrame.visible ? latestArtworkFrame.x : baseAuthoredWidth,
            progressPulse.visible ? progressPulse.x : baseAuthoredWidth,
            fieldGroupFrame.visible ? fieldGroupFrame.x : baseAuthoredWidth,
            connectionInfo.visible ? connectionInfo.x : baseAuthoredWidth
        ) - headerSafeInsetX) : 0.0
    readonly property real extraContentHeight: Math.max(0.0, authoredHeight - baseAuthoredHeight)
    readonly property real contentScale: Math.max(
        0.05,
        Math.min(width / authoredWidth, height / authoredHeight)
    )

    // Dense child editing follows the same authored-rail contract proven by
    // Abandonment Issues. Stable baselines are always derived from the base
    // authored canvas; parent content_extent and sibling reflow are never fed
    // back into the next child-size baseline.
    readonly property real headerSafeInsetX: 18.0
    readonly property real headerSafeInsetY: 14.0
    readonly property real canonicalGameNameX: 18.0
    readonly property real canonicalGameNameY: 62.0
    readonly property real canonicalGameNameHeight: 34.0
    readonly property real canonicalAchievementListX: 18.0
    readonly property real canonicalAchievementListY: 100.0
    readonly property real canonicalAchievementListHeight: 88.0
    readonly property real canonicalBadgeWidth: 40.0
    readonly property real canonicalBadgeHeight: 40.0
    readonly property real canonicalBadgeY: 130.0
    readonly property real canonicalProgressX: 51.0
    readonly property real canonicalProgressSize: 108.0
    readonly property real childReflowPlacementEpsilon: 0.0001
    readonly property bool canonicalVerticalArtwork:
        achievementModel.showArtwork
            && (achievementModel.artworkShape === "square"
                || achievementModel.artworkShape === "portrait")
    readonly property real canonicalArtworkWidth: canonicalVerticalArtwork
        ? achievementModel.squareArtworkSize : 180.0
    readonly property real canonicalArtworkHeight:
        achievementModel.artworkShape === "portrait"
            ? canonicalArtworkWidth * 1.4
            : (canonicalVerticalArtwork ? canonicalArtworkWidth : 86.0)
    readonly property real canonicalArtworkX: canonicalVerticalArtwork
        ? 491.0 - canonicalArtworkWidth / 2.0 : 402.0
    readonly property real canonicalArtworkY: 14.0
    readonly property real canonicalMetricY: canonicalVerticalArtwork
        ? canonicalArtworkY + canonicalArtworkHeight + 6.0 : 108.0
    readonly property real canonicalTitleWidth: !achievementModel.showArtwork
        ? Math.max(120.0, baseAuthoredWidth - 36.0)
        : Math.max(120.0, canonicalArtworkX - 32.0)

    // The Header alignment exchanges semantic regions without mirroring image
    // pixels or text glyphs. Text-role alignment follows the card orientation
    // unless that role is independently flipped relative to its parent.
    readonly property bool headerFlipped:
        achievementModel.customHeaderAlignment === "right"
    // The Header flip exchanges the entire card's authored left/right regions.
    // Each text-role flip is *relative* to that semantic orientation: without
    // this combination the frame moves right while its glyphs remain left.
    // The individual role can still be flipped independently in either header
    // orientation. No child record is implicitly written by the Header flip.
    readonly property bool gameNameFlipped:
        headerFlipped !== (achievementModel.customGameNameAlignment === "right")
    readonly property bool firstAchievementFlipped:
        headerFlipped !== (achievementModel.customFirstAchievementAlignment === "right")
    readonly property bool achievementListFlipped:
        headerFlipped !== (achievementModel.customAchievementListAlignment === "right")
    function semanticRailX(baseX, baseWidth, onAuthoredRail) {
        return headerFlipped && onAuthoredRail
            ? baseAuthoredWidth - baseX - baseWidth : baseX
    }
    function semanticRailShift(baseX, baseWidth, onAuthoredRail) {
        return semanticRailX(baseX, baseWidth, onAuthoredRail) - baseX
    }

    function childAxisOnAuthoredResizeRail(offset, scale, scalableExtent, normalizationExtent) {
        const normalizedOffset = Number(offset || 0.0)
        const resizeCompensation = Number(scalableExtent || 0.0)
            * (1.0 - Number(scale || 1.0))
            / Math.max(1.0, Number(normalizationExtent || 1.0))
        return Math.abs(normalizedOffset) <= childReflowPlacementEpsilon
            || Math.abs(normalizedOffset - resizeCompensation)
                <= childReflowPlacementEpsilon
    }

    function childOnAuthoredResizeRail(
            xOffset, yOffset, widthScale, heightScale,
            scalableWidth, scalableHeight) {
        return childAxisOnAuthoredResizeRail(
                    xOffset, widthScale, scalableWidth, baseAuthoredWidth)
            && childAxisOnAuthoredResizeRail(
                    yOffset, heightScale, scalableHeight, baseAuthoredHeight)
    }

    readonly property bool artworkOnAuthoredRail: childOnAuthoredResizeRail(
        achievementModel.customArtworkXOffset, achievementModel.customArtworkYOffset,
        achievementModel.customArtworkWidthScale, achievementModel.customArtworkHeightScale,
        canonicalArtworkWidth, canonicalArtworkHeight
    )
    readonly property bool badgeOnAuthoredRail: childOnAuthoredResizeRail(
        achievementModel.customBadgeXOffset, achievementModel.customBadgeYOffset,
        achievementModel.customBadgeWidthScale, achievementModel.customBadgeHeightScale,
        canonicalBadgeWidth, canonicalBadgeHeight
    )
    readonly property bool progressOnAuthoredRail: childOnAuthoredResizeRail(
        achievementModel.customProgressCircleXOffset, achievementModel.customProgressCircleYOffset,
        achievementModel.customProgressCircleScale, achievementModel.customProgressCircleScale,
        canonicalProgressSize, canonicalProgressSize
    )
    readonly property bool gameNameOnAuthoredRail: childOnAuthoredResizeRail(
        achievementModel.customGameNameXOffset, achievementModel.customGameNameYOffset,
        achievementModel.customGameNameWidthScale, achievementModel.customGameNameHeightScale,
        canonicalTitleWidth, canonicalGameNameHeight
    )
    readonly property bool achievementListOnAuthoredRail: childOnAuthoredResizeRail(
        achievementModel.customAchievementListXOffset, achievementModel.customAchievementListYOffset,
        achievementModel.customAchievementListWidthScale, achievementModel.customAchievementListHeightScale,
        canonicalTitleWidth, canonicalAchievementListHeight
    )
    readonly property bool firstAchievementOnAuthoredRail: childOnAuthoredResizeRail(
        achievementModel.customFirstAchievementXOffset,
        achievementModel.customFirstAchievementYOffset,
        achievementModel.customFirstAchievementWidthScale,
        achievementModel.customFirstAchievementHeightScale,
        canonicalTitleWidth, 26.0
    )
    readonly property bool fieldGroupOnAuthoredRail: childOnAuthoredResizeRail(
        achievementModel.customFieldGroupXOffset, achievementModel.customFieldGroupYOffset,
        achievementModel.customFieldGroupWidthScale, achievementModel.customFieldGroupHeightScale,
        fieldGroupFrame.canonicalWidth, fieldGroupFrame.canonicalHeight
    )

    readonly property real gameNameLayoutHeightDelta: gameNameOnAuthoredRail
        ? canonicalGameNameHeight * (achievementModel.customGameNameHeightScale - 1.0)
        : 0.0
    readonly property real progressLayoutWidthDelta: progressOnAuthoredRail
        ? canonicalProgressSize * (achievementModel.customProgressCircleScale - 1.0)
        : 0.0
    // Right/bottom parent rails stay live only for canonical-size authored roles.
    // This mirrors Abandonment's repaired BACKLOG rule and prevents child-driven
    // containment growth from translating the same child again.
    readonly property bool artworkFollowsParentRightRail: artworkOnAuthoredRail
        && Math.abs(achievementModel.customArtworkWidthScale - 1.0)
            <= childReflowPlacementEpsilon
    readonly property real artworkParentReflowX:
        artworkFollowsParentRightRail && !headerFlipped
            ? extraContentWidth : 0.0
    readonly property bool progressFollowsParentBottomRail: progressOnAuthoredRail
        && Math.abs(achievementModel.customProgressCircleScale - 1.0)
            <= childReflowPlacementEpsilon
    readonly property real progressParentReflowY: progressFollowsParentBottomRail
        ? extraContentHeight : 0.0
    readonly property bool fieldGroupFollowsParentBottomRail: fieldGroupOnAuthoredRail
        && Math.abs(achievementModel.customFieldGroupHeightScale - 1.0)
            <= childReflowPlacementEpsilon
    readonly property real fieldGroupParentReflowY: fieldGroupFollowsParentBottomRail
        ? extraContentHeight : 0.0

    // CUSTOM child editing is descriptor admission only. The shared overlay owns
    // handles, snapping/collision and gestures; this family supplies retained
    // targets, authored reflow relationships and one stable requirement surface.
    customEditableChildRoles: {
        const roles = []
        const normW = achievementRoot.baseAuthoredWidth
        const normH = achievementRoot.baseAuthoredHeight
        roles.push({
            "roleId": "header",
            "target": headerFrame,
            "geometryDependencies": [authoredCanvas],
            "normalizationWidth": normW,
            "normalizationHeight": normH,
            // Keep the role list independent of live parent dimensions.
            // The shared child frame projects this authored inset into the
            // current uniform/letterboxed edit-frame coordinate space at use.
            "semanticCornerInsetX": achievementRoot.headerSafeInsetX,
            "semanticCornerInsetY": achievementRoot.headerSafeInsetY,
            "semanticInsetUsesUniformCard": true,
            "requirementTarget": null
        })
        if (normalContent.visible && artworkFrame.visible) {
            roles.push({
                "roleId": "artwork",
                "target": artworkFrame,
                "occupiedTarget": artworkOccupiedFrame,
                "geometryDependencies": [authoredCanvas, normalContent, artworkOccupiedFrame],
                "normalizationWidth": normW,
                "normalizationHeight": normH,
                "requirementTarget": null
            })
        }
        if (normalContent.visible && gameTitle.visible) {
            roles.push({
                "roleId": "game_name",
                "target": gameTitle,
                "geometryDependencies": [authoredCanvas, normalContent],
                "resizeReflowRoleIds": ["achievement_list", "badge"],
                "resizeReflowAxes": ["vertical"],
                "resizeReflowGate": gameTitle,
                "normalizationWidth": normW,
                "normalizationHeight": normH,
                "requirementTarget": null
            })
        }
        if (normalContent.visible && achievementListFrame.visible
                && (achievementRoot.achievementModel.subtitle.length > 0
                    || unlockRepeater.count > 1)) {
            roles.push({
                "roleId": "achievement_list",
                "target": achievementListFrame,
                "geometryDependencies": [authoredCanvas, normalContent],
                "resizeReflowGate": achievementListFrame,
                "collisionIgnoreRoleIds": ["first_achievement"],
                "normalizationWidth": normW,
                "normalizationHeight": normH,
                "requirementTarget": null
            })
        }
        if (normalContent.visible && unlockRepeater.count > 0
                && unlockRepeater.itemAt(0) !== null) {
            roles.push({
                "roleId": "first_achievement",
                "target": unlockRepeater.itemAt(0),
                "geometryDependencies": [authoredCanvas, normalContent, achievementListFrame],
                "collisionIgnoreRoleIds": ["achievement_list"],
                "normalizationWidth": normW,
                "normalizationHeight": normH,
                "requirementTarget": null
            })
        }
        if (normalContent.visible && latestArtworkFrame.visible) {
            roles.push({
                "roleId": "badge",
                "target": latestArtworkFrame,
                "geometryDependencies": [authoredCanvas, normalContent, achievementListFrame],
                "resizeReflowGate": latestArtworkFrame,
                "normalizationWidth": normW,
                "normalizationHeight": normH,
                "requirementTarget": null
            })
        }
        if (normalContent.visible && progressPulse.visible) {
            roles.push({
                "roleId": "progress_circle",
                "target": progressPulse,
                "geometryDependencies": [authoredCanvas, normalContent],
                "resizeReflowRoleIds": ["field_group"],
                "resizeReflowAxes": ["horizontal"],
                "resizeReflowGate": progressPulse,
                "normalizationWidth": normW,
                "normalizationHeight": normH,
                "requirementTarget": null
            })
        }
        if (normalContent.visible && fieldGroupFrame.visible) {
            roles.push({
                "roleId": "field_group",
                "target": fieldGroupFrame,
                "geometryDependencies": [authoredCanvas, normalContent],
                "resizeReflowGate": fieldGroupFrame,
                "normalizationWidth": normW,
                "normalizationHeight": normH,
                "requirementTarget": null
            })
        }
        return roles
    }
    customEditableChildObstacles: [connectionInfo]
    customEditableChildRequirementTarget: null

    // Content-driven outer size (H option A): this card is a self-contained
    // authored canvas, so its preferred content size is the authored dimension
    // directly (no shell inset - it draws its own frame). Size only; Python owns
    // anchor/clamp/outer rect.
    preferredContentWidth: achievementRoot.authoredWidth
    preferredContentHeight: achievementRoot.authoredHeight

    // Achievement Pulse is an authored-aspect card.  Let the shared ordinary-
    // widget transform scale the complete card shell as one unit so a taller
    // committed CUSTOM rectangle leaves spare space *outside* the card rather
    // than stretching the shell around a shorter authored canvas.
    uniformScaleTransform: true

    // Child edits are card-contained; only outer handles change the parent size.
    TapHandler {
        enabled: achievementRoot.achievementModel.interactionEnabled
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: achievementRoot.refreshRequested()
    }

    Item {
        id: authoredCanvas
        objectName: "achievementAuthoredCanvas"
        width: Math.max(achievementRoot.authoredWidth, achievementRoot.baseAuthoredWidth)
        height: achievementRoot.authoredHeight
        // OverlayWidget now owns the whole-card uniform transform.  Keep this
        // authored content at canonical coordinates inside that transformed
        // shell; a second local scale/centering pass would recreate the visible
        // top/bottom bands that parity is removing.
        x: -achievementRoot.leadingTrim
        y: 0.0
        scale: 1.0
        transformOrigin: Item.TopLeft

        BrandedHeader {
            id: headerFrame
            frameObjectName: "achievementHeaderFrame"
            logoObjectName: "achievementSteamLogo"
            textObjectName: "achievementHeaderText"
            property real customEditPlacementCompensationX:
                (achievementRoot.achievementModel.customHeaderAnchor.length > 0
                    || achievementRoot.headerFlipped)
                    ? x - (achievementRoot.headerSafeInsetX
                        + achievementRoot.achievementModel.customHeaderXOffset
                            * achievementRoot.baseAuthoredWidth)
                    : 0.0
            property real customEditPlacementCompensationY:
                achievementRoot.achievementModel.customHeaderAnchor.length > 0
                    ? y - (achievementRoot.headerSafeInsetY
                        + achievementRoot.achievementModel.customHeaderYOffset
                            * achievementRoot.baseAuthoredHeight)
                    : 0.0
            transformOrigin: Item.TopLeft
            scale: achievementRoot.achievementModel.customHeaderWidthScale
            x: (achievementRoot.achievementModel.customHeaderAnchor.endsWith("right")
                    || (achievementRoot.headerFlipped
                        && !achievementRoot.achievementModel.customHeaderAnchor.endsWith("left")))
                ? authoredCanvas.width - achievementRoot.headerSafeInsetX
                    - width * scale
                : (achievementRoot.achievementModel.customHeaderAnchor.endsWith("left")
                    ? achievementRoot.headerSafeInsetX
                    : achievementRoot.headerSafeInsetX
                        + achievementRoot.achievementModel.customHeaderXOffset
                            * achievementRoot.baseAuthoredWidth)
            y: achievementRoot.achievementModel.customHeaderAnchor.startsWith("bottom")
                ? achievementRoot.authoredHeight - achievementRoot.headerSafeInsetY
                    - height * scale
                : (achievementRoot.achievementModel.customHeaderAnchor.startsWith("top")
                    ? achievementRoot.headerSafeInsetY
                    : achievementRoot.headerSafeInsetY
                        + achievementRoot.achievementModel.customHeaderYOffset
                            * achievementRoot.baseAuthoredHeight)
            contentReversed: achievementRoot.achievementModel.customHeaderAlignment === "right"
            label: achievementRoot.achievementModel.headerText
            logoSource: achievementRoot.achievementModel.logoSource
            fillColor: achievementRoot.achievementModel.headerFillColor
            borderColor: achievementRoot.achievementModel.headerBorderColor
            borderWidth: achievementRoot.scaleAwareHeaderStrokeWidthForScale(
                achievementRoot.achievementModel.headerBorderWidth,
                achievementRoot.contentScale
            )
            textColor: achievementRoot.achievementModel.headerTextColor
            fontFamily: achievementRoot.achievementModel.fontFamily
            textShadowEnabled: achievementRoot.achievementModel.textShadowEnabled
            textShadowColor: achievementRoot.achievementModel.textShadowColor
            textShadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
            textShadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
            shadowEnabled: achievementRoot.cardShadowEnabled
            shadowColor: Qt.rgba(
                achievementRoot.cardShadowColor.r, achievementRoot.cardShadowColor.g,
                achievementRoot.cardShadowColor.b, achievementRoot.cardShadowColor.a * 0.45
            )
            shadowBlur: Math.max(2.0, Math.min(6.0, achievementRoot.cardShadowBlur * 0.25))
            shadowOffsetX: achievementRoot.cardShadowOffsetX * 1.15
            shadowOffsetY: achievementRoot.cardShadowOffsetY * 1.15
        }

        Rectangle {
            id: connectionInfo
            objectName: "achievementConnectionInfo"
            visible: achievementRoot.achievementModel.showConnectionInfo
            x: achievementRoot.headerFlipped
                ? achievementRoot.baseAuthoredWidth - 300.0 - width : 300.0
            y: 14.0
            width: 18.0
            height: 18.0
            radius: 9.0
            color: achievementRoot.achievementModel.steamInfoSurfaceColor
            border.color: achievementRoot.achievementModel.steamInfoBorderColor
            border.width: achievementRoot.scaleAwareStrokeWidthForScale(
                1.0, achievementRoot.contentScale
            )
            z: 4

            Text {
                anchors.fill: parent
                text: "i"
                color: achievementRoot.achievementModel.steamInfoTextColor
                font.family: achievementRoot.achievementModel.fontFamily
                font.pixelSize: 12.0
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            HoverHandler {
                id: infoHover
                enabled: achievementRoot.achievementModel.interactionEnabled
            }

            TapHandler {
                enabled: achievementRoot.achievementModel.interactionEnabled
                acceptedButtons: Qt.LeftButton
                onTapped: achievementRoot.settingsRequested(
                    achievementRoot.achievementModel.connectionInfoTarget
                )
            }
        }

        Rectangle {
            id: infoTip
            objectName: "achievementConnectionInfoTip"
            visible: connectionInfo.visible && infoHover.hovered
            x: connectionInfo.x
            y: connectionInfo.y + connectionInfo.height + 5.0
            width: 276.0
            height: infoTipText.implicitHeight + 14.0
            radius: 6.0
            color: achievementRoot.achievementModel.steamTooltipSurfaceColor
            border.color: achievementRoot.achievementModel.steamTooltipBorderColor
            border.width: achievementRoot.scaleAwareStrokeWidthForScale(
                1.0, achievementRoot.contentScale
            )
            z: 10

            Text {
                id: infoTipText
                anchors.fill: parent
                anchors.margins: 7.0
                text: achievementRoot.achievementModel.connectionInfoTooltip
                color: achievementRoot.achievementModel.steamTooltipTextColor
                font.family: achievementRoot.achievementModel.fontFamily
                font.pixelSize: 12.0
                wrapMode: Text.WordWrap
                verticalAlignment: Text.AlignVCenter
            }
        }

        Item {
            id: normalContent
            objectName: "achievementNormalContent"
            visible: achievementRoot.achievementModel.viewState !== "connect_required"
            anchors.fill: parent

            readonly property real artworkWidth: achievementRoot.canonicalArtworkWidth
                * achievementRoot.achievementModel.customArtworkWidthScale
            readonly property real artworkHeight: achievementRoot.canonicalArtworkHeight
                * achievementRoot.achievementModel.customArtworkHeightScale
            readonly property real artworkX: achievementRoot.semanticRailX(
                    achievementRoot.canonicalArtworkX,
                    achievementRoot.canonicalArtworkWidth,
                    achievementRoot.artworkOnAuthoredRail)
                + achievementRoot.artworkParentReflowX
                + achievementRoot.achievementModel.customArtworkXOffset
                    * achievementRoot.baseAuthoredWidth
            readonly property real artworkY: achievementRoot.canonicalArtworkY
                + achievementRoot.achievementModel.customArtworkYOffset
                    * achievementRoot.baseAuthoredHeight
            readonly property real metricY: artworkY + artworkHeight + 6.0
            // The authored title/list column grows with its parent while the
            // artwork is still on the live right rail (or artwork is hidden).
            // Free-moving artwork never drags the text column along with it.
            // This is a projection of the parent extent, not a new layout owner.
            readonly property real titleParentReflowWidth:
                (!achievementRoot.achievementModel.showArtwork
                    || achievementRoot.artworkFollowsParentRightRail
                    || achievementRoot.headerFlipped)
                    ? achievementRoot.extraContentWidth : 0.0
            readonly property real titleWidth:
                achievementRoot.canonicalTitleWidth + titleParentReflowWidth


            Item {
                id: artworkFrame
                objectName: "achievementArtworkFrame"
                visible: achievementRoot.achievementModel.showArtwork
                property bool customEditReflowEnabled: achievementRoot.artworkOnAuthoredRail
                property real customEditPlacementCompensationX:
                    achievementRoot.semanticRailShift(
                        achievementRoot.canonicalArtworkX,
                        achievementRoot.canonicalArtworkWidth,
                        achievementRoot.artworkOnAuthoredRail)
                    + achievementRoot.artworkParentReflowX
                property real customEditPlacementCompensationY: 0.0
                x: normalContent.artworkX
                y: normalContent.artworkY
                width: normalContent.artworkWidth
                height: normalContent.artworkHeight
                readonly property real artworkStrokeWidth:
                    achievementRoot.scaleAwareStrokeWidthForScale(
                        2.25, achievementRoot.contentScale
                    )
                readonly property real imageInset: Math.max(2.0, artworkStrokeWidth)

                RectangularShadow {
                    anchors.fill: artworkBackground
                    color: "#76000000"
                    blur: 8.0
                    radius: artworkBackground.radius
                    offset: Qt.vector2d(2.0, 3.0)
                    cached: true
                }

                Rectangle {
                    id: artworkBackground
                    anchors.fill: parent
                    radius: 7.0
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: achievementRoot.achievementModel.steamArtworkGradientStartColor }
                        GradientStop { position: 1.0; color: achievementRoot.achievementModel.steamArtworkGradientEndColor }
                    }
                }

                ArtworkFadeImage {
                    id: artworkImage
                    objectName: "achievementArtworkImage"
                    anchors.fill: parent
                    anchors.margins: artworkFrame.imageInset
                    source: achievementRoot.achievementModel.artworkSource
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        maskEnabled: true
                        maskSource: artworkMask
                    }
                }

                Rectangle {
                    id: artworkMask
                    anchors.fill: artworkImage
                    radius: Math.max(0.0, artworkBackground.radius - artworkFrame.imageInset)
                    visible: false
                    layer.enabled: true
                }

                // Keep the outline on top of the image, matching the sane Steam
                // artwork-frame contract used by Abandonment Issues.  Painting
                // the border under an inset image made Pulse's edge look washed
                // and inconsistently transparent.
                Rectangle {
                    id: artworkBorder
                    objectName: "achievementArtworkBorder"
                    anchors.fill: parent
                    radius: 7.0
                    color: "transparent"
                    border.color: artworkHover.hovered
                        ? achievementRoot.achievementModel.accentColor
                        : achievementRoot.achievementModel.steamArtworkBorderColor
                    border.width: artworkFrame.artworkStrokeWidth
                }

                HoverHandler {
                    id: artworkHover
                    enabled: achievementRoot.achievementModel.interactionEnabled
                        && achievementRoot.achievementModel.appid > 0
                        && achievementRoot.achievementModel.artworkSource.length > 0
                }

                TapHandler {
                    enabled: achievementRoot.achievementModel.interactionEnabled
                        && achievementRoot.achievementModel.appid > 0
                        && achievementRoot.achievementModel.artworkSource.length > 0
                    acceptedButtons: Qt.LeftButton
                    onTapped: achievementRoot.storeRequested()
                }
            }

            ShadowedText {
                id: gameTitle
                objectName: "achievementGameTitle"
                property bool customEditReflowEnabled: achievementRoot.gameNameOnAuthoredRail
                property real customEditPlacementCompensationX:
                    achievementRoot.semanticRailShift(
                        achievementRoot.canonicalGameNameX, achievementRoot.canonicalTitleWidth,
                        achievementRoot.gameNameOnAuthoredRail)
                property real customEditPlacementCompensationY: 0.0
                x: achievementRoot.semanticRailX(
                        achievementRoot.canonicalGameNameX, achievementRoot.canonicalTitleWidth,
                        achievementRoot.gameNameOnAuthoredRail)
                    + achievementRoot.achievementModel.customGameNameXOffset
                        * achievementRoot.baseAuthoredWidth
                y: achievementRoot.canonicalGameNameY
                    + achievementRoot.achievementModel.customGameNameYOffset
                        * achievementRoot.baseAuthoredHeight
                width: (achievementRoot.gameNameOnAuthoredRail
                    ? normalContent.titleWidth : achievementRoot.canonicalTitleWidth)
                    * achievementRoot.achievementModel.customGameNameWidthScale
                height: achievementRoot.canonicalGameNameHeight
                    * achievementRoot.achievementModel.customGameNameHeightScale
                text: achievementRoot.achievementModel.title
                color: achievementRoot.achievementModel.textColor
                font.family: achievementRoot.achievementModel.fontFamily
                font.pointSize: (achievementRoot.achievementModel.fontSize + 5.0)
                    * achievementRoot.achievementModel.customGameNameHeightScale
                font.bold: true
                horizontalAlignment: achievementRoot.gameNameFlipped
                    ? Text.AlignRight : Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
                readonly property bool customGeometryActive:
                    Math.abs(achievementRoot.achievementModel.customGameNameWidthScale - 1.0)
                        > achievementRoot.childReflowPlacementEpsilon
                    || Math.abs(achievementRoot.achievementModel.customGameNameHeightScale - 1.0)
                        > achievementRoot.childReflowPlacementEpsilon
                // Preserve the authored title renderer exactly until the user
                // actually resizes this role. Fitting is editor geometry behavior,
                // not a normal-presentation restyle.
                fontSizeMode: customGeometryActive ? Text.Fit : Text.FixedSize
                minimumPointSize: Math.max(
                    8.0,
                    achievementRoot.achievementModel.fontSize * 0.58
                        * achievementRoot.achievementModel.customGameNameHeightScale
                )
                elide: customGeometryActive ? Text.ElideNone : Text.ElideRight
                shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                shadowColor: achievementRoot.achievementModel.textShadowColor
                shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
            }

            Item {
                id: achievementListFrame
                objectName: "achievementListGroup"
                property bool customEditReflowEnabled:
                    achievementRoot.achievementListOnAuthoredRail
                property real customEditPlacementCompensationX:
                    achievementRoot.semanticRailShift(
                        achievementRoot.canonicalAchievementListX, achievementRoot.canonicalTitleWidth,
                        achievementRoot.achievementListOnAuthoredRail)
                property real customEditPlacementCompensationY:
                    achievementRoot.achievementListOnAuthoredRail
                        ? achievementRoot.gameNameLayoutHeightDelta : 0.0
                visible: achievementRoot.achievementModel.subtitle.length > 0
                    || unlockRepeater.count > 0
                x: achievementRoot.semanticRailX(
                        achievementRoot.canonicalAchievementListX, achievementRoot.canonicalTitleWidth,
                        achievementRoot.achievementListOnAuthoredRail)
                    + achievementRoot.achievementModel.customAchievementListXOffset
                        * achievementRoot.baseAuthoredWidth
                y: achievementRoot.canonicalAchievementListY
                    + (achievementRoot.achievementListOnAuthoredRail
                        ? achievementRoot.gameNameLayoutHeightDelta : 0.0)
                    + achievementRoot.achievementModel.customAchievementListYOffset
                        * achievementRoot.baseAuthoredHeight
                width: (achievementRoot.achievementListOnAuthoredRail
                    ? normalContent.titleWidth : achievementRoot.canonicalTitleWidth)
                    * achievementRoot.achievementModel.customAchievementListWidthScale
                height: achievementRoot.canonicalAchievementListHeight
                    * achievementRoot.achievementModel.customAchievementListHeightScale

                ShadowedText {
                    objectName: "achievementSubtitle"
                    // The legacy presenter treated the latest-unlock stack as the
                    // subtitle area's content, rather than painting both layers.
                    visible: text.length > 0 && unlockRepeater.count === 0
                    anchors.fill: parent
                    text: achievementRoot.achievementModel.subtitle
                    color: achievementRoot.achievementModel.textColor
                    font.family: achievementRoot.achievementModel.fontFamily
                    font.pointSize: achievementRoot.achievementModel.fontSize * 0.78
                        * achievementRoot.achievementModel.customAchievementListHeightScale
                    horizontalAlignment: achievementRoot.achievementListFlipped
                        ? Text.AlignRight : Text.AlignLeft
                    verticalAlignment: Text.AlignTop
                    wrap: true
                    elide: Text.ElideRight
                    shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                    shadowColor: achievementRoot.achievementModel.textShadowColor
                    shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                    shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
                }

                Repeater {
                    id: unlockRepeater
                    model: achievementRoot.achievementModel.unlockModel

                    delegate: ShadowedText {
                        required property string unlockIdentity
                        required property string unlockText
                        required property int index
                        objectName: "achievementUnlock_" + index
                        // The first unlock has its own persisted role. Cancel
                        // only the remainder-list CUSTOM offset, not the authored
                        // game-name reflow, so the first line remains independent.
                        y: index === 0
                            ? (achievementRoot.achievementModel.customFirstAchievementYOffset
                                - achievementRoot.achievementModel.customAchievementListYOffset)
                                * achievementRoot.baseAuthoredHeight
                            : (30.0 + (index - 1) * 14.0)
                                * achievementRoot.achievementModel.customAchievementListHeightScale
                        // The first unlock retains its own independent child
                        // geometry. The smaller lines share one badge-clearance
                        // lane: on a right flip, START after the badge and end at
                        // the actual right edge of the editable list rectangle.
                        // Leaving x at zero and only changing Text.AlignRight
                        // would right-align within the old narrow left lane.
                        readonly property real badgeClearance: 6.0
                        x: index === 0
                            ? (achievementRoot.achievementModel.customFirstAchievementXOffset
                                - achievementRoot.achievementModel.customAchievementListXOffset)
                                * achievementRoot.baseAuthoredWidth
                            : latestArtworkFrame.visible && achievementRoot.achievementListFlipped
                                ? Math.min(achievementListFrame.width, Math.max(0.0,
                                    latestArtworkFrame.x + latestArtworkFrame.visualWidth
                                    - achievementListFrame.x + badgeClearance))
                                : 0.0
                        width: index === 0
                            ? (achievementRoot.firstAchievementOnAuthoredRail
                                ? normalContent.titleWidth : achievementRoot.canonicalTitleWidth)
                                * achievementRoot.achievementModel.customFirstAchievementWidthScale
                            : !latestArtworkFrame.visible
                                ? achievementListFrame.width
                                : achievementRoot.achievementListFlipped
                                    ? Math.max(0.0, achievementListFrame.width - x)
                                    : Math.min(achievementListFrame.width, Math.max(0.0,
                                        latestArtworkFrame.x - achievementListFrame.x - badgeClearance))
                        height: index === 0
                            ? 26.0 * achievementRoot.achievementModel.customFirstAchievementHeightScale
                            : 13.0 * achievementRoot.achievementModel.customAchievementListHeightScale
                        text: unlockText
                        color: achievementRoot.achievementModel.textColor
                        font.family: achievementRoot.achievementModel.fontFamily
                        font.pointSize: (index === 0
                            ? achievementRoot.achievementModel.fontSize * 0.72
                            : achievementRoot.achievementModel.fontSize * 0.48)
                            * (index === 0
                                ? achievementRoot.achievementModel.customFirstAchievementHeightScale
                                : achievementRoot.achievementModel.customAchievementListHeightScale)
                        font.bold: index === 0
                        horizontalAlignment:
                            (index === 0
                                ? achievementRoot.firstAchievementFlipped
                                : achievementRoot.achievementListFlipped)
                                ? Text.AlignRight : Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                        shadowColor: achievementRoot.achievementModel.textShadowColor
                        shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                        shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
                    }
                }
            }

            Item {
                id: latestArtworkFrame
                objectName: "achievementLatestArtworkFrame"
                visible: achievementRoot.achievementModel.showLatestArtwork
                    && (achievementRoot.achievementModel.latestArtworkSource.length > 0
                        || latestArtworkImage.transitionVisible)
                    && unlockRepeater.count > 0
                // Historical hierarchy: the badge belongs to the unlock stack,
                // not to the game-cover rail. Its top starts immediately below
                // the large first unlock line; no extra line spacing is reserved.
                // Keep the badge close to the smaller unlock text by default,
                // pushing it right only when an actual rendered line needs room.
                // This replaces the old fixed x=130 rail without coupling the
                // badge to the unrelated game-cover/artwork column.
                readonly property real baseRailX: 102.0
                readonly property real textClearance: 8.0
                property bool customEditReflowEnabled: achievementRoot.badgeOnAuthoredRail
                // Flipping the list also mirrors its uncustomized companion
                // badge inside the *live* list extent. An independently moved
                // badge keeps its own persisted position and is not reauthored.
                readonly property bool followsListFlip:
                    achievementRoot.achievementListFlipped
                        && achievementRoot.badgeOnAuthoredRail
                property real customEditPlacementCompensationX:
                    x - resolvedRailX()
                        - achievementRoot.achievementModel.customBadgeXOffset
                            * achievementRoot.baseAuthoredWidth
                property real customEditPlacementCompensationY:
                    achievementRoot.badgeOnAuthoredRail
                        ? achievementRoot.gameNameLayoutHeightDelta : 0.0
                function resolvedRailX() {
                    let required = baseRailX
                    for (let row = 1; row < unlockRepeater.count; ++row) {
                        const unlockItem = unlockRepeater.itemAt(row)
                        if (unlockItem !== null)
                            required = Math.max(
                                required,
                                // Only the intrinsic glyph width may set the
                                // authored badge clearance. On a right flip the
                                // row's live x itself depends on badge.x; reading
                                // it here would create a QML geometry feedback loop.
                                achievementRoot.canonicalAchievementListX
                                    + unlockItem.implicitWidth + textClearance
                            )
                    }
                    return Math.min(
                        required,
                        Math.max(18.0,
                            achievementRoot.canonicalTitleWidth - width)
                    )
                }
                x: (followsListFlip
                        ? achievementListFrame.x + achievementListFrame.width
                            - (resolvedRailX() - achievementRoot.canonicalAchievementListX)
                            - visualWidth
                        : achievementRoot.semanticRailX(
                            resolvedRailX(), achievementRoot.canonicalBadgeWidth,
                            achievementRoot.badgeOnAuthoredRail))
                    + achievementRoot.achievementModel.customBadgeXOffset
                        * achievementRoot.baseAuthoredWidth
                y: achievementRoot.canonicalBadgeY
                    + (achievementRoot.badgeOnAuthoredRail
                        ? achievementRoot.gameNameLayoutHeightDelta : 0.0)
                    + achievementRoot.achievementModel.customBadgeYOffset
                        * achievementRoot.baseAuthoredHeight
                width: achievementRoot.canonicalBadgeWidth
                height: achievementRoot.canonicalBadgeHeight
                scale: achievementRoot.achievementModel.customBadgeWidthScale
                transformOrigin: Item.TopLeft
                readonly property real visualWidth: width * scale
                readonly property real visualHeight: height * scale

                // The Steam achievement icon already contains its ornate frame.
                // Do not put it inside a second dark rounded panel/border: that
                // produced the post-migration black-box abomination around it.
                RectangularShadow {
                    anchors.fill: latestArtworkImage
                    color: "#76000000"
                    blur: 6.0
                    radius: 6.0
                    offset: Qt.vector2d(2.0, 2.0)
                    cached: true
                }

                ArtworkFadeImage {
                    id: latestArtworkImage
                    objectName: "achievementLatestArtworkImage"
                    anchors.fill: parent
                    anchors.margins: 1.0
                    source: achievementRoot.achievementModel.latestArtworkSource
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                }

                // Restore only the clean outer keyline from the old treatment.
                // The dark filled backing panel remains intentionally retired.
                Rectangle {
                    objectName: "achievementLatestArtworkBorder"
                    anchors.fill: parent
                    radius: 4.0
                    color: "transparent"
                    border.color: achievementRoot.achievementModel.steamArtworkBorderColor
                    border.width: achievementRoot.scaleAwareStrokeWidthForScale(
                        1.15, achievementRoot.contentScale
                    )
                    z: 2
                }
            }

            ShadowedText {
                id: metricText
                objectName: "achievementMetric"
                visible: achievementRoot.achievementModel.metricValue.length > 0
                x: normalContent.artworkX - 10.0
                y: normalContent.metricY
                width: normalContent.artworkWidth + 20.0
                height: 28.0
                text: achievementRoot.achievementModel.metricLabel
                    + ": " + achievementRoot.achievementModel.metricValue
                color: achievementRoot.achievementModel.textColor
                font.family: achievementRoot.achievementModel.fontFamily
                font.pointSize: achievementRoot.achievementModel.fontSize * 0.95
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                // R-38 contract: consume the deliberately wider metric rail by
                // fitting normal/high counts locally before exceptional elision.
                fontSizeMode: Text.HorizontalFit
                minimumPointSize: Math.max(8.0, achievementRoot.achievementModel.fontSize * 0.70)
                elide: Text.ElideRight
                shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                shadowColor: achievementRoot.achievementModel.textShadowColor
                shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
            }

            // Edit-only occupied geometry for the artwork role includes the
            // retained metric rail that follows the image. It paints nothing.
            Item {
                id: artworkOccupiedFrame
                objectName: "achievementArtworkOccupiedFrame"
                visible: artworkFrame.visible
                x: metricText.visible ? Math.min(artworkFrame.x, metricText.x) : artworkFrame.x
                y: metricText.visible ? Math.min(artworkFrame.y, metricText.y) : artworkFrame.y
                width: (metricText.visible
                    ? Math.max(artworkFrame.x + artworkFrame.width,
                        metricText.x + metricText.width)
                    : artworkFrame.x + artworkFrame.width) - x
                height: (metricText.visible
                    ? Math.max(artworkFrame.y + artworkFrame.height,
                        metricText.y + metricText.height)
                    : artworkFrame.y + artworkFrame.height) - y
            }

            Item {
                id: progressPulse
                objectName: "achievementProgressPulse"
                visible: achievementRoot.achievementModel.progressPulseEnabled
                    && achievementRoot.achievementModel.totalFieldEnabled
                    && achievementRoot.achievementModel.viewState === "content"
                property bool customEditReflowEnabled: achievementRoot.progressOnAuthoredRail
                property real customEditPlacementCompensationX:
                    achievementRoot.semanticRailShift(
                        achievementRoot.canonicalProgressX,
                        achievementRoot.canonicalProgressSize,
                        achievementRoot.progressOnAuthoredRail)
                property real customEditPlacementCompensationY:
                    achievementRoot.progressParentReflowY
                x: achievementRoot.semanticRailX(
                        achievementRoot.canonicalProgressX,
                        achievementRoot.canonicalProgressSize,
                        achievementRoot.progressOnAuthoredRail)
                    + achievementRoot.achievementModel.customProgressCircleXOffset
                        * achievementRoot.baseAuthoredWidth
                y: achievementRoot.baseAuthoredHeight
                    - achievementRoot.canonicalProgressSize - 20.0
                    + achievementRoot.progressParentReflowY
                    + achievementRoot.achievementModel.customProgressCircleYOffset
                        * achievementRoot.baseAuthoredHeight
                width: achievementRoot.canonicalProgressSize
                height: achievementRoot.canonicalProgressSize
                scale: achievementRoot.achievementModel.customProgressCircleScale
                transformOrigin: Item.TopLeft
                z: 2

                property real pulseLevel: 0.0
                readonly property real visualSize: width * scale
                // Apply the requested percentage reduction after HorizontalFit.
                // Changing only font.pointSize is not sufficient because fitted text
                // may already be below that ceiling.  This is presentation-only:
                // pulse/card geometry and the normalized Total value stay untouched.
                readonly property real progressTextVisualScale: 0.90
                readonly property real glowDistance: 19.0 + pulseLevel * 6.0
                readonly property real glowScale: Math.max(0.5, glowDistance / 12.0)

                function triggerPulse() {
                    if (!visible)
                        return
                    pulseAnimation.stop()
                    pulseAnimation.restart()
                }

                onVisibleChanged: {
                    if (!visible) {
                        pulseAnimation.stop()
                        pulseLevel = 0.0
                    }
                }

                Connections {
                    target: achievementRoot.achievementModel
                    function onProgressPulseRequested() {
                        progressPulse.triggerPulse()
                    }
                }

                SequentialAnimation {
                    id: pulseAnimation
                    NumberAnimation {
                        target: progressPulse
                        property: "pulseLevel"
                        to: 1.0
                        duration: 2000
                        easing.type: Easing.InOutQuad
                    }
                    NumberAnimation {
                        target: progressPulse
                        property: "pulseLevel"
                        to: 0.0
                        duration: 3000
                        easing.type: Easing.OutCubic
                    }
                }

                // Reuse the existing analytical widget-glow shader. This is a
                // single retained circle and is completely dormant at level 0;
                // no blur capture, timer, poller or extra runtime owner exists.
                ShaderEffect {
                    x: -progressPulse.glowDistance
                    y: -progressPulse.glowDistance
                    width: progressPulse.width + progressPulse.glowDistance * 2.0
                    height: progressPulse.height + progressPulse.glowDistance * 2.0
                    property vector2d effectSize: Qt.vector2d(
                        width / progressPulse.glowScale,
                        height / progressPulse.glowScale
                    )
                    property vector2d cardSize: Qt.vector2d(
                        progressPulse.width / progressPulse.glowScale,
                        progressPulse.height / progressPulse.glowScale
                    )
                    property real cornerRadius: progressPulse.width * 0.5 / progressPulse.glowScale
                    property color glowColor: achievementRoot.achievementModel.capsuleBorderColor
                    opacity: progressPulse.pulseLevel * 0.82
                    visible: opacity > 0.001
                    fragmentShader: "shaders/widget_glow.frag.qsb"
                }

                Rectangle {
                    anchors.fill: parent
                    radius: width * 0.5
                    color: Qt.rgba(
                        achievementRoot.achievementModel.capsuleFillColor.r,
                        achievementRoot.achievementModel.capsuleFillColor.g,
                        achievementRoot.achievementModel.capsuleFillColor.b,
                        achievementRoot.achievementModel.capsuleFillColor.a * 0.72
                    )
                    border.color: achievementRoot.achievementModel.capsuleBorderColor
                    border.width: achievementRoot.scaleAwareStrokeWidthForScale(
                        5.0, achievementRoot.contentScale
                    )
                }

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 7.0
                    radius: width * 0.5
                    color: "transparent"
                    border.color: Qt.rgba(
                        achievementRoot.achievementModel.capsuleBorderColor.r,
                        achievementRoot.achievementModel.capsuleBorderColor.g,
                        achievementRoot.achievementModel.capsuleBorderColor.b,
                        achievementRoot.achievementModel.capsuleBorderColor.a * 0.38
                    )
                    border.width: achievementRoot.scaleAwareStrokeWidthForScale(
                        1.0, achievementRoot.contentScale
                    )
                }

                Text {
                    anchors.fill: parent
                    text: achievementRoot.achievementModel.progressText
                    color: achievementRoot.achievementModel.capsuleBorderColor
                    opacity: progressPulse.pulseLevel * 0.16
                    scale: progressPulse.progressTextVisualScale * 1.11
                    font.family: achievementRoot.achievementModel.fontFamily
                    font.pointSize: achievementRoot.achievementModel.fontSize * 1.998
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    fontSizeMode: Text.HorizontalFit
                    minimumPointSize: 9.0
                    visible: opacity > 0.001
                }

                Text {
                    anchors.fill: parent
                    text: achievementRoot.achievementModel.progressText
                    color: achievementRoot.achievementModel.capsuleBorderColor
                    opacity: progressPulse.pulseLevel * 0.44
                    scale: progressPulse.progressTextVisualScale * 1.045
                    font.family: achievementRoot.achievementModel.fontFamily
                    font.pointSize: achievementRoot.achievementModel.fontSize * 1.998
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    fontSizeMode: Text.HorizontalFit
                    minimumPointSize: 9.0
                    visible: opacity > 0.001
                }

                ShadowedText {
                    anchors.fill: parent
                    anchors.margins: 13.0
                    text: achievementRoot.achievementModel.progressText
                    color: achievementRoot.achievementModel.textColor
                    scale: progressPulse.progressTextVisualScale
                    font.family: achievementRoot.achievementModel.fontFamily
                    font.pointSize: achievementRoot.achievementModel.fontSize * 1.998
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    fontSizeMode: Text.HorizontalFit
                    minimumPointSize: 9.0
                    elide: Text.ElideRight
                    shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                    shadowColor: achievementRoot.achievementModel.textShadowColor
                    shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                    shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
                }
            }

            Item {
                id: fieldGroupFrame
                objectName: "achievementFieldGroup"
                readonly property int columnCount: progressPulse.visible ? 2 : 3
                readonly property int railStride:
                    achievementRoot.achievementModel.shelfStyle
                        ? 1
                        : (achievementRoot.achievementModel.doubleCapsules ? 2 : 1)
                readonly property int railCount: Math.max(
                    1,
                    Math.ceil(fieldRepeater.count / columnCount) * railStride
                )
                readonly property real canonicalX: progressPulse.visible
                    ? achievementRoot.canonicalProgressX
                        + achievementRoot.canonicalProgressSize + 49.0
                    : 18.0
                readonly property real canonicalWidth: Math.max(
                    1.0,
                    achievementRoot.baseAuthoredWidth - canonicalX
                        - (progressPulse.visible ? 19.0 : 18.0)
                )
                readonly property real canonicalCapsuleHeight:
                    achievementRoot.achievementModel.capsuleHeight
                readonly property real canonicalGap:
                    achievementRoot.achievementModel.capsuleGap
                readonly property real canonicalHeight:
                    railCount * canonicalCapsuleHeight
                        + Math.max(0, railCount - 1) * canonicalGap
                readonly property real canonicalY:
                    achievementRoot.baseAuthoredHeight - 16.0 - canonicalHeight
                readonly property real capsuleHeight: canonicalCapsuleHeight
                    * achievementRoot.achievementModel.customFieldGroupHeightScale
                readonly property real capsuleGap: canonicalGap
                    * achievementRoot.achievementModel.customFieldGroupHeightScale
                readonly property real columnGap: 9.0
                    * achievementRoot.achievementModel.customFieldGroupWidthScale
                readonly property real columnWidth: Math.max(
                    1.0,
                    (width - columnGap * (columnCount - 1)) / columnCount
                )
                property bool customEditReflowEnabled:
                    achievementRoot.fieldGroupOnAuthoredRail
                property real customEditPlacementCompensationX:
                    achievementRoot.semanticRailShift(
                        canonicalX, canonicalWidth,
                        achievementRoot.fieldGroupOnAuthoredRail)
                    + (achievementRoot.fieldGroupOnAuthoredRail
                            && achievementRoot.progressOnAuthoredRail
                            && !achievementRoot.headerFlipped
                        ? achievementRoot.progressLayoutWidthDelta : 0.0)
                property real customEditPlacementCompensationY:
                    achievementRoot.fieldGroupParentReflowY
                visible: fieldRepeater.count > 0
                x: achievementRoot.semanticRailX(
                        canonicalX, canonicalWidth,
                        achievementRoot.fieldGroupOnAuthoredRail)
                    + (achievementRoot.fieldGroupOnAuthoredRail
                            && achievementRoot.progressOnAuthoredRail
                            && !achievementRoot.headerFlipped
                        ? achievementRoot.progressLayoutWidthDelta : 0.0)
                    + achievementRoot.achievementModel.customFieldGroupXOffset
                        * achievementRoot.baseAuthoredWidth
                y: canonicalY
                    + achievementRoot.fieldGroupParentReflowY
                    + achievementRoot.achievementModel.customFieldGroupYOffset
                        * achievementRoot.baseAuthoredHeight
                width: canonicalWidth
                    * achievementRoot.achievementModel.customFieldGroupWidthScale
                height: canonicalHeight
                    * achievementRoot.achievementModel.customFieldGroupHeightScale

                Repeater {
                    id: fieldRepeater
                    model: achievementRoot.achievementModel.fieldModel

                    delegate: Item {
                        required property string fieldId
                        required property string fieldLabel
                        required property string fieldValue
                        required property int index
                        objectName: "achievementField_" + fieldId
                        readonly property int compactRow:
                            Math.floor(index / fieldGroupFrame.columnCount)
                        readonly property int column:
                            index % fieldGroupFrame.columnCount
                        readonly property real railStep:
                            fieldGroupFrame.capsuleHeight + fieldGroupFrame.capsuleGap
                        x: column * (fieldGroupFrame.columnWidth + fieldGroupFrame.columnGap)
                        y: compactRow * fieldGroupFrame.railStride * railStep
                        width: fieldGroupFrame.columnWidth
                        height: achievementRoot.achievementModel.shelfStyle
                            ? fieldGroupFrame.capsuleHeight
                            : (achievementRoot.achievementModel.doubleCapsules
                                ? fieldGroupFrame.capsuleHeight * 2.0
                                    + fieldGroupFrame.capsuleGap
                                : fieldGroupFrame.capsuleHeight)

                        AchievementCapsule {
                            anchors.fill: parent
                            fieldId: parent.fieldId
                            fieldLabel: parent.fieldLabel
                            fieldValue: parent.fieldValue
                            doubled: achievementRoot.achievementModel.doubleCapsules
                            shelfStyle: achievementRoot.achievementModel.shelfStyle
                            capsuleHeight: fieldGroupFrame.capsuleHeight
                            capsuleGap: fieldGroupFrame.capsuleGap
                            capsuleFontSize:
                                achievementRoot.achievementModel.capsuleFontSize
                                    * achievementRoot.achievementModel.customFieldGroupHeightScale
                            fontFamily: achievementRoot.achievementModel.fontFamily
                            fillColor: achievementRoot.achievementModel.capsuleFillColor
                            borderColor: achievementRoot.achievementModel.capsuleBorderColor
                            shelfSeparatorColor: achievementRoot.achievementModel.steamMetricSeparatorColor
                            shelfAccentColor: achievementRoot.achievementModel.accentColor
                            textColor: achievementRoot.achievementModel.textColor
                            textShadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                            textShadowColor: achievementRoot.achievementModel.textShadowColor
                            textShadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                            textShadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
                        }
                    }
                }
            }
        }

        Item {
            id: connectRequired
            objectName: "achievementConnectRequired"
            visible: achievementRoot.achievementModel.viewState === "connect_required"
            x: 44.0 + Math.max(0.0,
                (authoredCanvas.width - achievementRoot.baseAuthoredWidth) * 0.5)
            y: 76.0 + Math.max(0.0,
                (authoredCanvas.height - achievementRoot.baseAuthoredHeight) * 0.5)
            width: 332.0
            height: 61.0

            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                height: 34.0

                ShadowedText {
                    width: 82.0
                    height: parent.height
                    text: achievementRoot.achievementModel.actionLabel
                    color: achievementRoot.achievementModel.accentColor
                    font.family: achievementRoot.achievementModel.fontFamily
                    font.pointSize: achievementRoot.achievementModel.fontSize
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                    shadowColor: achievementRoot.achievementModel.textShadowColor
                    shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                    shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY

                    TapHandler {
                        enabled: achievementRoot.achievementModel.interactionEnabled
                        acceptedButtons: Qt.LeftButton
                        onTapped: achievementRoot.settingsRequested(
                            achievementRoot.achievementModel.settingsTarget
                        )
                    }
                }

                ShadowedText {
                    width: implicitWidth
                    height: parent.height
                    text: achievementRoot.achievementModel.actionText.replace(
                        achievementRoot.achievementModel.actionLabel, ""
                    )
                    color: achievementRoot.achievementModel.textColor
                    font.family: achievementRoot.achievementModel.fontFamily
                    font.pointSize: achievementRoot.achievementModel.fontSize
                    verticalAlignment: Text.AlignVCenter
                    shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                    shadowColor: achievementRoot.achievementModel.textShadowColor
                    shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                    shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
                }
            }

            ShadowedText {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 24.0
                text: achievementRoot.achievementModel.statusText
                color: achievementRoot.achievementModel.textColor
                font.family: achievementRoot.achievementModel.fontFamily
                font.pointSize: achievementRoot.achievementModel.fontSize * 0.78
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                shadowColor: achievementRoot.achievementModel.textShadowColor
                shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
            }
        }
    }
}
