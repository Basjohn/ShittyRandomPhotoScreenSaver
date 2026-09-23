import QtQuick
import QtQuick.Effects

OverlayWidget {
    id: abandonmentRoot
    objectName: "abandonmentIssuesPresentation"


    required property var abandonmentModel
    semanticDoubleClickEnabled: abandonmentModel.interactionEnabled
    signal refreshRequested()
    signal settingsRequested(string target)
    signal storeRequested()

    readonly property real authoredWidth: abandonmentModel.authoredWidth
    readonly property real authoredHeight: abandonmentModel.authoredHeight
    readonly property real baseAuthoredWidth: abandonmentModel.baseAuthoredWidth
    readonly property real baseAuthoredHeight: abandonmentModel.baseAuthoredHeight
    readonly property real extraContentWidth: Math.max(0.0, authoredWidth - baseAuthoredWidth)
    readonly property real extraContentHeight: Math.max(0.0, authoredHeight - baseAuthoredHeight)
    uniformScaleTransform: true

    // One existing Header alignment is the card orientation. Only the
    // positions of whole semantic regions change; never mirror image/text pixels.
    readonly property bool headerFlipped:
        abandonmentModel.customHeaderAlignment === "right"
    readonly property real flippedTextX:
        baseAuthoredWidth - canonicalTextLeft - canonicalTextWidth
    readonly property real flippedArtworkX:
        baseAuthoredWidth - 17.0 - (canonicalArtworkWidth + 13.0)
    function textRailX(onAuthoredRail) {
        return headerFlipped && onAuthoredRail ? flippedTextX : canonicalTextLeft
    }
    function textRailShift(onAuthoredRail) {
        return textRailX(onAuthoredRail) - canonicalTextLeft
    }
    function artworkTextReflow(onAuthoredRail) {
        return onAuthoredRail && !headerFlipped ? artworkLayoutWidthDelta : 0.0
    }
    readonly property bool artworkFollowsFlippedRight:
        headerFlipped && artworkOnAuthoredRail
            && Math.abs(abandonmentModel.customArtworkWidthScale - 1.0)
                <= childReflowPlacementEpsilon
    readonly property real flippedArtworkParentReflowX:
        artworkFollowsFlippedRight ? extraContentWidth : 0.0

    // Dense CUSTOM child roles deliberately use stable authored baselines.
    // Outer content_extent may grow around them, but must never become a new
    // baseline that compounds the next child drag. Individual blocks can move
    // as neighbours grow while only their own handle changes their dimensions.
    readonly property bool canonicalPortraitArtwork:
        abandonmentModel.artworkShape === "portrait"
    readonly property real canonicalArtworkWidth: canonicalPortraitArtwork
        ? abandonmentModel.artworkSize
        : Math.min(238.0, abandonmentModel.artworkSize * 1.45)
    readonly property real canonicalArtworkHeight: canonicalPortraitArtwork
        ? abandonmentModel.artworkSize * 1.4
        : Math.max(78.0, abandonmentModel.artworkSize * 0.66)
    readonly property real canonicalArtworkY: canonicalPortraitArtwork ? 76.0 : 82.0
    readonly property real canonicalTextLeft: abandonmentModel.showArtwork
        ? 22.0 + canonicalArtworkWidth + 24.0 : 24.0
    readonly property real canonicalTextWidth: Math.max(
        150.0, baseAuthoredWidth - 22.0 - canonicalTextLeft
    )
    readonly property real headerSafeInsetX: 18.0
    readonly property real headerSafeInsetY: 14.0
    readonly property real canonicalBacklogWidth: 135.0
    readonly property real canonicalBacklogHeight: 30.0
    readonly property real canonicalGameNameWidth: canonicalTextWidth
    readonly property real canonicalGameNameHeight: 46.0
    readonly property real canonicalFlavourWidth: canonicalTextWidth
    readonly property real canonicalFlavourHeight: 34.0
    readonly property real canonicalLastVisitWidth: Math.min(300.0, canonicalTextWidth)
    readonly property real canonicalLastVisitHeight: 54.0
    readonly property real canonicalShelfWidth: Math.max(
        110.0, (canonicalTextWidth - 12.0) * 0.5
    )
    readonly property real canonicalShelfHeight: 25.0
    readonly property real canonicalShelfGap: 6.0
    readonly property real childReflowPlacementEpsilon: 0.0001

    function childAxisOnAuthoredResizeRail(offset, scale, scalableExtent, normalizationExtent) {
        const normalizedOffset = Number(offset || 0.0)
        const resizeCompensation = Number(scalableExtent || 0.0)
            * (1.0 - Number(scale || 1.0))
            / Math.max(1.0, Number(normalizationExtent || 1.0))
        // A right/bottom resize leaves the authored anchor offset at zero. A
        // left/top resize must persist exactly the opposite-edge compensation.
        // Both are still authored-rail *resize* state, not free placement.
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

    // A role that has been explicitly moved is no longer part of the authored
    // reflow rail. This is the key separation between family-authored layout and
    // user-authored placement: resizing an on-rail role may push downstream
    // siblings, while an off-rail role is collision-admitted instead of silently
    // dragging unrelated children around. These bindings are pure retained data
    // and add no runtime cadence outside Edit.
    // Placement-capable roles can now resize from any truthful edge/corner.
    // Left/top resize therefore creates normalized X/Y compensation while still
    // remaining on the family's authored reflow rail. Accept both zero-offset
    // right/bottom resize and exact opposite-edge compensation; only a genuine
    // free-move displacement detaches the role from authored sibling reflow.
    readonly property bool artworkOnAuthoredRail: childOnAuthoredResizeRail(
        abandonmentModel.customArtworkXOffset, abandonmentModel.customArtworkYOffset,
        abandonmentModel.customArtworkWidthScale, abandonmentModel.customArtworkHeightScale,
        canonicalArtworkWidth, canonicalArtworkHeight
    )
    readonly property bool backlogOnAuthoredRail: childOnAuthoredResizeRail(
        abandonmentModel.customBacklogXOffset, abandonmentModel.customBacklogYOffset,
        abandonmentModel.customBacklogWidthScale, abandonmentModel.customBacklogHeightScale,
        canonicalBacklogWidth, canonicalBacklogHeight
    )
    readonly property bool gameNameOnAuthoredRail: childOnAuthoredResizeRail(
        abandonmentModel.customGameNameXOffset, abandonmentModel.customGameNameYOffset,
        abandonmentModel.customGameNameWidthScale, abandonmentModel.customGameNameHeightScale,
        canonicalGameNameWidth, canonicalGameNameHeight
    )
    readonly property bool flavourOnAuthoredRail: childOnAuthoredResizeRail(
        abandonmentModel.customFlavourXOffset, abandonmentModel.customFlavourYOffset,
        abandonmentModel.customFlavourWidthScale, abandonmentModel.customFlavourHeightScale,
        canonicalFlavourWidth, canonicalFlavourHeight
    )
    readonly property bool lastVisitOnAuthoredRail: childOnAuthoredResizeRail(
        abandonmentModel.customLastVisitXOffset, abandonmentModel.customLastVisitYOffset,
        abandonmentModel.customLastVisitWidthScale, abandonmentModel.customLastVisitHeightScale,
        canonicalLastVisitWidth, canonicalLastVisitHeight
    )
    readonly property real shelfGroupScalableWidth:
        ledgerGroupFrame.columnCount * canonicalShelfWidth
    readonly property real shelfGroupScalableHeight:
        ledgerGroupFrame.rowCount * canonicalShelfHeight
    readonly property bool shelfGroupOnAuthoredRail: childOnAuthoredResizeRail(
        abandonmentModel.customShelfGroupXOffset, abandonmentModel.customShelfGroupYOffset,
        abandonmentModel.customShelfGroupWidthScale, abandonmentModel.customShelfGroupHeightScale,
        shelfGroupScalableWidth, shelfGroupScalableHeight
    )
    readonly property real artworkLayoutWidthDelta: artworkOnAuthoredRail
        ? canonicalArtworkWidth * (abandonmentModel.customArtworkWidthScale - 1.0)
        : 0.0
    readonly property real backlogLayoutHeightDelta: backlogOnAuthoredRail
        ? canonicalBacklogHeight * (abandonmentModel.customBacklogHeightScale - 1.0)
        : 0.0
    // Horizontal parent reflow is family-authored motion, not placement. Keep
    // BACKLOG on the live right rail only while it is still authored *and* its
    // own width is canonical. A horizontal child resize must not feed admitted
    // parent growth back into the same child's X position. The first real free
    // move folds any live parent displacement into child_geometry through the
    // existing placement-compensation hook; after detachment, later parent
    // resize closes space around the placed child instead of dragging it.
    readonly property bool backlogFollowsParentRightRail:
        backlogOnAuthoredRail
            && Math.abs(abandonmentModel.customBacklogWidthScale - 1.0)
                <= childReflowPlacementEpsilon
    readonly property real backlogParentReflowX: backlogFollowsParentRightRail
        ? extraContentWidth : 0.0
    readonly property real gameNameLayoutHeightDelta: gameNameOnAuthoredRail
        ? canonicalGameNameHeight * (abandonmentModel.customGameNameHeightScale - 1.0)
        : 0.0
    readonly property real flavourLayoutHeightDelta: flavourOnAuthoredRail
        ? canonicalFlavourHeight * (abandonmentModel.customFlavourHeightScale - 1.0)
        : 0.0
    readonly property real lastVisitLayoutHeightDelta: lastVisitOnAuthoredRail
        ? canonicalLastVisitHeight * (abandonmentModel.customLastVisitHeightScale - 1.0)
        : 0.0

    // Signed on-rail deltas drive internal reflow in both directions so
    // shrinking a child can reclaim space. Once a role is explicitly moved off
    // its authored rail, its size stops displacing unrelated siblings and the
    // edit-only collision gate becomes the authority for separation instead.

    // Stable retained semantic roles. Visibility is evaluated by the selected
    // Edit mapper, not by rebuilding this role list during content transitions.
    customEditableChildRoles: {
        const roles = []
        roles.push({
            "roleId": "header",
            "normalizationTarget": abandonmentRoot,
            "normalizationWidthProperty": "baseAuthoredWidth",
            "normalizationHeightProperty": "baseAuthoredHeight",
            "target": headerFrame,
            "geometryDependencies": [authoredCanvas],
            // Keep the role list independent of live parent dimensions.
            // The shared child frame projects this authored inset into the
            // current uniform/letterboxed edit-frame coordinate space at use.
            "semanticCornerInsetX": abandonmentRoot.headerSafeInsetX,
            "semanticCornerInsetY": abandonmentRoot.headerSafeInsetY,
            "semanticInsetUsesUniformCard": true,
            "requirementTarget": null
        })
        roles.push({
            "roleId": "artwork",
            "normalizationTarget": abandonmentRoot,
            "normalizationWidthProperty": "baseAuthoredWidth",
            "normalizationHeightProperty": "baseAuthoredHeight",
            "target": artworkFrame,
            "occupiedTarget": artworkShelf,
            "geometryDependencies": [authoredCanvas, archiveContent, normalContent, artworkShelf],
            "resizeReflowRoleIds": ["game_name", "flavour_text", "last_visit", "shelf_group"],
            "resizeReflowAxes": ["horizontal"],
            "resizeReflowGate": artworkFrame,
            "requirementTarget": null
        })
        roles.push({
            "roleId": "backlog_block",
            "normalizationTarget": abandonmentRoot,
            "normalizationWidthProperty": "baseAuthoredWidth",
            "normalizationHeightProperty": "baseAuthoredHeight",
            "target": archiveTab,
            "geometryDependencies": [authoredCanvas, archiveContent],
            "resizeReflowRoleIds": ["artwork", "game_name", "flavour_text", "last_visit", "shelf_group"],
            "resizeReflowAxes": ["vertical"],
            "resizeReflowGate": archiveTab,
            "requirementTarget": null
        })
        roles.push({
            "roleId": "game_name",
            "normalizationTarget": abandonmentRoot,
            "normalizationWidthProperty": "baseAuthoredWidth",
            "normalizationHeightProperty": "baseAuthoredHeight",
            "target": gameTitle,
            "geometryDependencies": [authoredCanvas, archiveContent, normalContent],
            "resizeReflowRoleIds": ["flavour_text", "last_visit", "shelf_group"],
            "resizeReflowAxes": ["vertical"],
            "resizeReflowGate": gameTitle,
            "requirementTarget": null
        })
        roles.push({
            "roleId": "flavour_text",
            "normalizationTarget": abandonmentRoot,
            "normalizationWidthProperty": "baseAuthoredWidth",
            "normalizationHeightProperty": "baseAuthoredHeight",
            "target": flavourText,
            "geometryDependencies": [authoredCanvas, archiveContent, normalContent],
            "resizeReflowRoleIds": ["last_visit", "shelf_group"],
            "resizeReflowAxes": ["vertical"],
            "resizeReflowGate": flavourText,
            "requirementTarget": null
        })
        roles.push({
            "roleId": "last_visit",
            "normalizationTarget": abandonmentRoot,
            "normalizationWidthProperty": "baseAuthoredWidth",
            "normalizationHeightProperty": "baseAuthoredHeight",
            "target": ageStamp,
            "geometryDependencies": [authoredCanvas, archiveContent, normalContent],
            "resizeReflowRoleIds": ["shelf_group"],
            "resizeReflowAxes": ["vertical"],
            "resizeReflowGate": ageStamp,
            "requirementTarget": null
        })
        roles.push({
            "roleId": "shelf_group",
            "normalizationTarget": abandonmentRoot,
            "normalizationWidthProperty": "baseAuthoredWidth",
            "normalizationHeightProperty": "baseAuthoredHeight",
            "target": ledgerGroupFrame,
            "geometryDependencies": [authoredCanvas, archiveContent, normalContent],
            "resizeReflowGate": ledgerGroupFrame,
            "requirementTarget": null
        })
        return roles
    }
    // Non-editable chrome remains selected-Edit-only collision truth. The header
    // itself is now a descriptor-backed role and therefore participates as a
    // normal child collision surface instead of a fixed obstacle.
    customEditableChildObstacles: [connectionInfo]
    customEditableChildRequirementTarget: null

    // Rotation fades only data that actually changes. Archive chrome, shelves,
    // separators, labels (including LAST VISIT), and artwork framing remain stable;
    // artwork owns its independent readiness-gated crossfade.
    property real dynamicContentOpacity: 1.0

    // Content-driven outer size (H option A): this card is a self-contained
    // authored canvas, so its preferred content size is the authored dimension
    // directly (no shell inset - it draws its own frame). Size only; Python owns
    // anchor/clamp/outer rect.
    preferredContentWidth: abandonmentRoot.authoredWidth
    preferredContentHeight: abandonmentRoot.authoredHeight

    // No child-driven parent growth or passive child requirement computation.
    TapHandler {
        enabled: abandonmentRoot.abandonmentModel.interactionEnabled
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: abandonmentRoot.refreshRequested()
    }

    Connections {
        target: abandonmentRoot.abandonmentModel

        function onContentTransitionRequested() {
            archiveTransition.restart()
        }
    }

    Item {
        id: authoredCanvas
        objectName: "abandonmentAuthoredCanvas"
        width: abandonmentRoot.authoredWidth
        height: abandonmentRoot.authoredHeight
        transformOrigin: Item.TopLeft

        BrandedHeader {
            id: headerFrame
            frameObjectName: "abandonmentHeaderFrame"
            logoObjectName: "abandonmentSteamLogo"
            textObjectName: "abandonmentHeaderText"
            property real customEditPlacementCompensationX:
                (abandonmentRoot.abandonmentModel.customHeaderAnchor.length > 0
                    || abandonmentRoot.headerFlipped)
                    ? x - (abandonmentRoot.headerSafeInsetX
                        + abandonmentRoot.abandonmentModel.customHeaderXOffset
                            * abandonmentRoot.baseAuthoredWidth)
                    : 0.0
            property real customEditPlacementCompensationY:
                abandonmentRoot.abandonmentModel.customHeaderAnchor.length > 0
                    ? y - (abandonmentRoot.headerSafeInsetY
                        + abandonmentRoot.abandonmentModel.customHeaderYOffset
                            * abandonmentRoot.baseAuthoredHeight)
                    : 0.0
            transformOrigin: Item.TopLeft
            scale: abandonmentRoot.abandonmentModel.customHeaderWidthScale
            x: (abandonmentRoot.abandonmentModel.customHeaderAnchor.endsWith("right")
                    || (abandonmentRoot.headerFlipped
                        && !abandonmentRoot.abandonmentModel.customHeaderAnchor.endsWith("left")))
                ? abandonmentRoot.authoredWidth - abandonmentRoot.headerSafeInsetX
                    - width * scale
                : (abandonmentRoot.abandonmentModel.customHeaderAnchor.endsWith("left")
                    ? abandonmentRoot.headerSafeInsetX
                    : abandonmentRoot.headerSafeInsetX
                        + abandonmentRoot.abandonmentModel.customHeaderXOffset
                            * abandonmentRoot.baseAuthoredWidth)
            y: abandonmentRoot.abandonmentModel.customHeaderAnchor.startsWith("bottom")
                ? abandonmentRoot.authoredHeight - abandonmentRoot.headerSafeInsetY
                    - height * scale
                : (abandonmentRoot.abandonmentModel.customHeaderAnchor.startsWith("top")
                    ? abandonmentRoot.headerSafeInsetY
                    : abandonmentRoot.headerSafeInsetY
                        + abandonmentRoot.abandonmentModel.customHeaderYOffset
                            * abandonmentRoot.baseAuthoredHeight)
            contentReversed: abandonmentRoot.abandonmentModel.customHeaderAlignment === "right"
            label: abandonmentRoot.abandonmentModel.headerText
            logoSource: abandonmentRoot.abandonmentModel.logoSource
            fillColor: abandonmentRoot.abandonmentModel.headerFillColor
            borderColor: abandonmentRoot.abandonmentModel.headerBorderColor
            borderWidth: abandonmentRoot.scaleAwareHeaderStrokeWidthForScale(
                abandonmentRoot.abandonmentModel.headerBorderWidth,
                abandonmentRoot.presentationScale
            )
            textColor: abandonmentRoot.abandonmentModel.headerTextColor
            fontFamily: abandonmentRoot.abandonmentModel.fontFamily
            textShadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
            textShadowColor: abandonmentRoot.abandonmentModel.textShadowColor
            textShadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
            textShadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
            shadowEnabled: abandonmentRoot.cardShadowEnabled
            shadowColor: Qt.rgba(
                abandonmentRoot.cardShadowColor.r, abandonmentRoot.cardShadowColor.g,
                abandonmentRoot.cardShadowColor.b, abandonmentRoot.cardShadowColor.a * 0.45
            )
            shadowBlur: Math.max(2.0, Math.min(6.0, abandonmentRoot.cardShadowBlur * 0.25))
            shadowOffsetX: abandonmentRoot.cardShadowOffsetX * 1.15
            shadowOffsetY: abandonmentRoot.cardShadowOffsetY * 1.15
        }

        Rectangle {
            id: connectionInfo
            objectName: "abandonmentConnectionInfo"
            visible: abandonmentRoot.abandonmentModel.showConnectionInfo
            x: abandonmentRoot.headerFlipped
                ? abandonmentRoot.baseAuthoredWidth - 318.0 - width : 318.0
            y: 17.0
            width: 18.0
            height: 18.0
            radius: 9.0
            color: abandonmentRoot.abandonmentModel.steamInfoSurfaceColor
            border.color: abandonmentRoot.abandonmentModel.steamInfoBorderColor
            border.width: abandonmentRoot.scaleAwareStrokeWidthForScale(
                1.0, abandonmentRoot.presentationScale
            )
            z: 5

            Text {
                anchors.fill: parent
                text: "i"
                color: abandonmentRoot.abandonmentModel.steamInfoTextColor
                font.family: abandonmentRoot.abandonmentModel.fontFamily
                font.pixelSize: 12.0
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            HoverHandler {
                id: infoHover
                cursorShape: Qt.PointingHandCursor
                enabled: abandonmentRoot.abandonmentModel.interactionEnabled
            }

            TapHandler {
                enabled: abandonmentRoot.abandonmentModel.interactionEnabled
                acceptedButtons: Qt.LeftButton
                onTapped: abandonmentRoot.settingsRequested(
                    abandonmentRoot.abandonmentModel.connectionInfoTarget
                )
            }
        }

        Rectangle {
            id: infoTip
            objectName: "abandonmentConnectionInfoTip"
            visible: connectionInfo.visible && infoHover.hovered
            x: connectionInfo.x
            y: connectionInfo.y + connectionInfo.height + 5.0
            width: 276.0
            height: infoTipText.implicitHeight + 14.0
            radius: 6.0
            color: abandonmentRoot.abandonmentModel.steamTooltipSurfaceColor
            border.color: abandonmentRoot.abandonmentModel.steamTooltipBorderColor
            border.width: abandonmentRoot.scaleAwareStrokeWidthForScale(
                1.0, abandonmentRoot.presentationScale
            )
            z: 10

            Text {
                id: infoTipText
                anchors.fill: parent
                anchors.margins: 7.0
                text: abandonmentRoot.abandonmentModel.connectionInfoTooltip
                color: abandonmentRoot.abandonmentModel.steamTooltipTextColor
                font.family: abandonmentRoot.abandonmentModel.fontFamily
                font.pixelSize: 12.0
                wrapMode: Text.WordWrap
                verticalAlignment: Text.AlignVCenter
            }
        }

        Item {
            id: archiveContent
            objectName: "abandonmentArchiveContent"
            anchors.fill: parent

            SequentialAnimation {
                id: archiveTransition

                // archive shell itself never disappears during a game rotation.

                NumberAnimation {
                    target: abandonmentRoot
                    property: "dynamicContentOpacity"
                    to: 0.0
                    duration: 160
                    easing.type: Easing.InOutQuad
                }
                ScriptAction {
                    script: abandonmentRoot.abandonmentModel.commitPendingPresentation()
                }
                NumberAnimation {
                    target: abandonmentRoot
                    property: "dynamicContentOpacity"
                    to: 1.0
                    duration: 240
                    easing.type: Easing.InOutQuad
                }
            }

            Rectangle {
                id: archiveTab
                objectName: "abandonmentArchiveTab"
                property bool customEditReflowEnabled: abandonmentRoot.backlogOnAuthoredRail
                property real customEditPlacementCompensationX:
                    abandonmentRoot.headerFlipped && abandonmentRoot.backlogOnAuthoredRail
                        ? 18.0 - (abandonmentRoot.baseAuthoredWidth
                            - abandonmentRoot.canonicalBacklogWidth - 18.0)
                        : abandonmentRoot.backlogParentReflowX
                property real customEditPlacementCompensationY: 0.0
                // The authored BACKLOG rail follows horizontal parent content extent
                // only while still authored. Once freely moved, its normalized
                // placement is stable and a later right-edge parent shrink closes
                // the gap instead of pushing BACKLOG through the left boundary.
                x: (abandonmentRoot.headerFlipped && abandonmentRoot.backlogOnAuthoredRail
                        ? 18.0
                        : abandonmentRoot.baseAuthoredWidth
                            - abandonmentRoot.canonicalBacklogWidth - 18.0
                            + abandonmentRoot.backlogParentReflowX)
                    + abandonmentRoot.abandonmentModel.customBacklogXOffset
                        * abandonmentRoot.baseAuthoredWidth
                y: 19.0
                    + abandonmentRoot.abandonmentModel.customBacklogYOffset
                        * abandonmentRoot.baseAuthoredHeight
                width: abandonmentRoot.canonicalBacklogWidth
                    * abandonmentRoot.abandonmentModel.customBacklogWidthScale
                height: abandonmentRoot.canonicalBacklogHeight
                    * abandonmentRoot.abandonmentModel.customBacklogHeightScale
                radius: 6.0
                color: Qt.rgba(
                    abandonmentRoot.abandonmentModel.accentColor.r,
                    abandonmentRoot.abandonmentModel.accentColor.g,
                    abandonmentRoot.abandonmentModel.accentColor.b,
                    0.36
                )
                border.color: Qt.rgba(
                    abandonmentRoot.abandonmentModel.accentColor.r,
                    abandonmentRoot.abandonmentModel.accentColor.g,
                    abandonmentRoot.abandonmentModel.accentColor.b,
                    0.80
                )
                border.width: abandonmentRoot.scaleAwareStrokeWidthForScale(
                    1.0, abandonmentRoot.presentationScale
                )

                ShadowedText {
                    anchors.fill: parent
                    anchors.leftMargin: 10.0
                    anchors.rightMargin: 10.0
                    text: abandonmentRoot.abandonmentModel.statusText.length > 0
                        ? abandonmentRoot.abandonmentModel.statusText
                        : "CURATED SHELF"
                    // The archive/Backlog BLOCK carries the distinctive accent
                    // through its fill/border. Keep the label on the resolved
                    // theme text semantic so pale/low-contrast accents cannot
                    // make BACKLOG text disappear into its own accent surface.
                    color: abandonmentRoot.abandonmentModel.textColor
                    font.family: abandonmentRoot.abandonmentModel.fontFamily
                    font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 0.66
                        * abandonmentRoot.abandonmentModel.customBacklogHeightScale
                    font.bold: true
                    horizontalAlignment:
                        abandonmentRoot.abandonmentModel.customBacklogAlignment === "right"
                            ? Text.AlignRight : Text.AlignLeft
                    verticalAlignment: Text.AlignVCenter
                    fontSizeMode: Text.HorizontalFit
                    minimumPointSize: Math.max(5.0, 6.0
                        * abandonmentRoot.abandonmentModel.customBacklogHeightScale)
                    shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                    shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                    shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                    shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                }
            }

            Item {
                id: normalContent
                objectName: "abandonmentNormalContent"
                visible: abandonmentRoot.abandonmentModel.viewState !== "connect_required"
                anchors.fill: parent

                readonly property real artworkWidth:
                    abandonmentRoot.canonicalArtworkWidth
                        * abandonmentRoot.abandonmentModel.customArtworkWidthScale
                readonly property real artworkHeight:
                    abandonmentRoot.canonicalArtworkHeight
                        * abandonmentRoot.abandonmentModel.customArtworkHeightScale
                readonly property real artworkY:
                    abandonmentRoot.canonicalArtworkY
                        + abandonmentRoot.backlogLayoutHeightDelta
                readonly property real textLeft:
                    abandonmentRoot.canonicalTextLeft
                        + (abandonmentRoot.abandonmentModel.showArtwork
                            ? abandonmentRoot.artworkLayoutWidthDelta : 0.0)
                readonly property real textWidth: abandonmentRoot.canonicalTextWidth

                Item {
                    id: artworkShelf
                    objectName: "abandonmentArtworkShelf"
                    visible: abandonmentRoot.abandonmentModel.showArtwork
                    x: (abandonmentRoot.headerFlipped && abandonmentRoot.artworkOnAuthoredRail
                            ? abandonmentRoot.flippedArtworkX
                                + abandonmentRoot.flippedArtworkParentReflowX
                            : 17.0)
                        + abandonmentRoot.abandonmentModel.customArtworkXOffset
                            * abandonmentRoot.baseAuthoredWidth
                    y: abandonmentRoot.canonicalArtworkY - 4.0
                        + (abandonmentRoot.artworkOnAuthoredRail
                            ? abandonmentRoot.backlogLayoutHeightDelta : 0.0)
                        + abandonmentRoot.abandonmentModel.customArtworkYOffset
                            * abandonmentRoot.baseAuthoredHeight
                    width: normalContent.artworkWidth + 13.0
                    height: normalContent.artworkHeight + 13.0

                    RectangularShadow {
                        anchors.fill: shelfBackground
                        color: "#76000000"
                        blur: 8.0
                        radius: shelfBackground.radius
                        offset: Qt.vector2d(2.0, 3.0)
                        cached: true
                    }

                    Rectangle {
                        id: shelfBackground
                        objectName: "abandonmentArtworkShelfBackground"
                        anchors.fill: parent
                        radius: 8.0
                        gradient: Gradient {
                            GradientStop {
                                position: 0.0
                                color: abandonmentRoot.abandonmentModel.steamArtworkGradientStartColor
                            }
                            GradientStop { position: 0.22; color: abandonmentRoot.abandonmentModel.steamArtworkGradientMiddleColor }
                            GradientStop { position: 1.0; color: abandonmentRoot.abandonmentModel.steamArtworkGradientEndColor }
                        }
                    }

                    Item {
                        id: artworkFrame
                        objectName: "abandonmentArtworkFrame"
                        property bool customEditReflowEnabled: abandonmentRoot.artworkOnAuthoredRail
                        property real customEditPlacementCompensationX:
                            abandonmentRoot.headerFlipped && abandonmentRoot.artworkOnAuthoredRail
                                ? abandonmentRoot.flippedArtworkX - 17.0
                                    + abandonmentRoot.flippedArtworkParentReflowX : 0.0
                        property real customEditPlacementCompensationY:
                            abandonmentRoot.artworkOnAuthoredRail
                                ? abandonmentRoot.backlogLayoutHeightDelta : 0.0
                        readonly property real artworkStrokeWidth:
                            abandonmentRoot.scaleAwareStrokeWidthForScale(
                                2.25, abandonmentRoot.presentationScale
                            )
                        readonly property real imageInset: Math.max(1.0, artworkStrokeWidth)
                        x: 5.0
                        y: 4.0
                        width: normalContent.artworkWidth
                        height: normalContent.artworkHeight
                        clip: true

                        Rectangle {
                            id: artworkBorder
                            anchors.fill: parent
                            radius: 8.0
                            color: abandonmentRoot.abandonmentModel.steamArtworkSurfaceColor
                        }

                        // Keep the decorative stripe node count stable while CUSTOM
                        // artwork is dragged. Spacing stretches with the freeform
                        // frame, but delegate creation remains authored-baseline work
                        // rather than pointer-sample churn.
                        readonly property int stripeCount: Math.max(
                            1,
                            Math.ceil((abandonmentRoot.canonicalArtworkWidth
                                + abandonmentRoot.canonicalArtworkHeight) / 12.0)
                        )
                        readonly property real stripeStep:
                            (artworkFrame.width + artworkFrame.height) / stripeCount

                        Repeater {
                            model: artworkFrame.stripeCount
                            delegate: Rectangle {
                                required property int index
                                x: index * artworkFrame.stripeStep - artworkFrame.height
                                y: artworkFrame.height
                                width: artworkFrame.height * 1.45
                                height: abandonmentRoot.scaleAwareStrokeWidthForScale(
                                    1.0, abandonmentRoot.presentationScale
                                )
                                rotation: -45.0
                                transformOrigin: Item.Left
                                color: abandonmentRoot.abandonmentModel.steamArtworkStripeColor
                            }
                        }

                        ArtworkFadeImage {
                            id: abandonmentArtworkImage
                            objectName: "abandonmentArtworkImage"
                            anchors.fill: parent
                            anchors.margins: artworkFrame.imageInset
                            source: abandonmentRoot.abandonmentModel.artworkSource
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                            // Artwork remains independent from the text/value
                            // rotation fade: keep the accepted texture visible until
                            // the replacement is Ready, then crossfade normally.
                            layer.enabled: true
                            layer.effect: MultiEffect {
                                maskEnabled: true
                                maskSource: artworkMask
                            }
                        }

                        Rectangle {
                            id: artworkMask
                            anchors.fill: abandonmentArtworkImage
                            radius: Math.max(0.0, 8.0 - artworkFrame.imageInset)
                            visible: false
                            layer.enabled: true
                        }

                        HoverHandler {
                            id: artworkHover
                            cursorShape: Qt.PointingHandCursor
                            enabled: abandonmentRoot.abandonmentModel.interactionEnabled
                                && abandonmentRoot.abandonmentModel.appid > 0
                                && abandonmentRoot.abandonmentModel.artworkSource.length > 0
                        }

                        TapHandler {
                            enabled: abandonmentRoot.abandonmentModel.interactionEnabled
                                && abandonmentRoot.abandonmentModel.appid > 0
                                && abandonmentRoot.abandonmentModel.artworkSource.length > 0
                            acceptedButtons: Qt.LeftButton
                            onTapped: abandonmentRoot.storeRequested()
                        }
                    }

                    // Sibling of the clipped artwork content: preserve the full
                    // 2.25px semantic outline just like Achievement Pulse.
                    Rectangle {
                        id: artworkHoverBorder
                        objectName: "abandonmentArtworkHoverBorder"
                        x: artworkFrame.x
                        y: artworkFrame.y
                        width: artworkFrame.width
                        height: artworkFrame.height
                        radius: 8.0
                        color: "transparent"
                        border.color: artworkHover.hovered
                            ? "white" : abandonmentRoot.abandonmentModel.steamArtworkBorderColor
                        border.width: artworkFrame.artworkStrokeWidth
                        antialiasing: true
                        z: 4
                    }
                }

                ShadowedText {
                    id: gameTitle
                    objectName: "abandonmentGameTitle"
                    property bool customEditReflowEnabled: abandonmentRoot.gameNameOnAuthoredRail
                    property real customEditPlacementCompensationX:
                        abandonmentRoot.textRailShift(abandonmentRoot.gameNameOnAuthoredRail)
                            + abandonmentRoot.artworkTextReflow(abandonmentRoot.gameNameOnAuthoredRail)
                    property real customEditPlacementCompensationY:
                        abandonmentRoot.gameNameOnAuthoredRail
                            ? abandonmentRoot.backlogLayoutHeightDelta : 0.0
                    x: abandonmentRoot.textRailX(abandonmentRoot.gameNameOnAuthoredRail)
                        + abandonmentRoot.artworkTextReflow(abandonmentRoot.gameNameOnAuthoredRail)
                        + abandonmentRoot.abandonmentModel.customGameNameXOffset
                            * abandonmentRoot.baseAuthoredWidth
                    y: 74.0
                        + (abandonmentRoot.gameNameOnAuthoredRail
                            ? abandonmentRoot.backlogLayoutHeightDelta : 0.0)
                        + abandonmentRoot.abandonmentModel.customGameNameYOffset
                            * abandonmentRoot.baseAuthoredHeight
                    width: abandonmentRoot.canonicalGameNameWidth
                        * abandonmentRoot.abandonmentModel.customGameNameWidthScale
                    height: abandonmentRoot.canonicalGameNameHeight
                        * abandonmentRoot.abandonmentModel.customGameNameHeightScale
                    text: abandonmentRoot.abandonmentModel.title
                    opacity: abandonmentRoot.dynamicContentOpacity
                    color: abandonmentRoot.abandonmentModel.textColor
                    font.family: abandonmentRoot.abandonmentModel.fontFamily
                    font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 1.45
                        * abandonmentRoot.abandonmentModel.customGameNameHeightScale
                    font.bold: true
                    horizontalAlignment: abandonmentRoot.abandonmentModel.customGameNameAlignment === "right"
                        ? Text.AlignRight : Text.AlignLeft
                    verticalAlignment: Text.AlignVCenter
                    wrap: true
                    maximumLineCount: 2
                    fontSizeMode: Text.Fit
                    minimumPointSize: abandonmentRoot.abandonmentModel.fontSize * 0.58
                        * abandonmentRoot.abandonmentModel.customGameNameHeightScale
                    // Dense CUSTOM widths must preserve the title rather than
                    // silently amputating it. Fit may shrink first and use a
                    // second line when the resized role has enough height.
                    elide: Text.ElideNone
                    shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                    shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                    shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                    shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                }

                ShadowedText {
                    id: flavourText
                    objectName: "abandonmentRediscoveryText"
                    property bool customEditReflowEnabled: abandonmentRoot.flavourOnAuthoredRail
                    property real customEditPlacementCompensationX:
                        abandonmentRoot.textRailShift(abandonmentRoot.flavourOnAuthoredRail)
                            + abandonmentRoot.artworkTextReflow(abandonmentRoot.flavourOnAuthoredRail)
                    property real customEditPlacementCompensationY:
                        abandonmentRoot.flavourOnAuthoredRail
                            ? abandonmentRoot.backlogLayoutHeightDelta
                                + abandonmentRoot.gameNameLayoutHeightDelta
                            : 0.0
                    x: abandonmentRoot.textRailX(abandonmentRoot.flavourOnAuthoredRail)
                        + abandonmentRoot.artworkTextReflow(abandonmentRoot.flavourOnAuthoredRail)
                        + abandonmentRoot.abandonmentModel.customFlavourXOffset
                            * abandonmentRoot.baseAuthoredWidth
                    y: 119.0
                        + (abandonmentRoot.flavourOnAuthoredRail
                            ? abandonmentRoot.backlogLayoutHeightDelta
                                + abandonmentRoot.gameNameLayoutHeightDelta
                            : 0.0)
                        + abandonmentRoot.abandonmentModel.customFlavourYOffset
                            * abandonmentRoot.baseAuthoredHeight
                    width: abandonmentRoot.canonicalFlavourWidth
                        * abandonmentRoot.abandonmentModel.customFlavourWidthScale
                    height: abandonmentRoot.canonicalFlavourHeight
                        * abandonmentRoot.abandonmentModel.customFlavourHeightScale
                    text: abandonmentRoot.abandonmentModel.subtitle
                    opacity: abandonmentRoot.dynamicContentOpacity
                    color: Qt.rgba(
                        abandonmentRoot.abandonmentModel.textColor.r,
                        abandonmentRoot.abandonmentModel.textColor.g,
                        abandonmentRoot.abandonmentModel.textColor.b,
                        Math.max(0.47, abandonmentRoot.abandonmentModel.textColor.a * 0.72)
                    )
                    font.family: abandonmentRoot.abandonmentModel.fontFamily
                    font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 0.88
                        * abandonmentRoot.abandonmentModel.customFlavourHeightScale
                    font.bold: true
                    horizontalAlignment: abandonmentRoot.abandonmentModel.customFlavourAlignment === "right"
                        ? Text.AlignRight : Text.AlignLeft
                    verticalAlignment: Text.AlignVCenter
                    wrap: true
                    maximumLineCount: 2
                    fontSizeMode: Text.Fit
                    minimumPointSize: 6.0
                    elide: Text.ElideNone
                    shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                    shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                    shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                    shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                }

                Rectangle {
                    id: ageStamp
                    objectName: "abandonmentAgeStamp"
                    property bool customEditReflowEnabled: abandonmentRoot.lastVisitOnAuthoredRail
                    property real customEditPlacementCompensationX:
                        abandonmentRoot.textRailShift(abandonmentRoot.lastVisitOnAuthoredRail)
                            + abandonmentRoot.artworkTextReflow(abandonmentRoot.lastVisitOnAuthoredRail)
                    property real customEditPlacementCompensationY:
                        abandonmentRoot.lastVisitOnAuthoredRail
                            ? abandonmentRoot.backlogLayoutHeightDelta
                                + abandonmentRoot.gameNameLayoutHeightDelta
                                + abandonmentRoot.flavourLayoutHeightDelta
                            : 0.0
                    x: abandonmentRoot.textRailX(abandonmentRoot.lastVisitOnAuthoredRail)
                        + abandonmentRoot.artworkTextReflow(abandonmentRoot.lastVisitOnAuthoredRail)
                        + abandonmentRoot.abandonmentModel.customLastVisitXOffset
                            * abandonmentRoot.baseAuthoredWidth
                    y: 160.0
                        + (abandonmentRoot.lastVisitOnAuthoredRail
                            ? abandonmentRoot.backlogLayoutHeightDelta
                                + abandonmentRoot.gameNameLayoutHeightDelta
                                + abandonmentRoot.flavourLayoutHeightDelta
                            : 0.0)
                        + abandonmentRoot.abandonmentModel.customLastVisitYOffset
                            * abandonmentRoot.baseAuthoredHeight
                    width: abandonmentRoot.canonicalLastVisitWidth
                        * abandonmentRoot.abandonmentModel.customLastVisitWidthScale
                    height: abandonmentRoot.canonicalLastVisitHeight
                        * abandonmentRoot.abandonmentModel.customLastVisitHeightScale
                    radius: 6.0
                    color: abandonmentRoot.abandonmentModel.steamMetricSurfaceColor
                    border.color: abandonmentRoot.abandonmentModel.steamMetricBorderColor
                    readonly property real childStrokeScale: Math.min(
                        abandonmentRoot.abandonmentModel.customLastVisitWidthScale,
                        abandonmentRoot.abandonmentModel.customLastVisitHeightScale)
                    border.width: abandonmentRoot.scaleAwareChildStrokeWidth(2.0, childStrokeScale)

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 4.0
                        radius: 4.0
                        color: "transparent"
                        border.color: abandonmentRoot.abandonmentModel.steamMetricInnerBorderColor
                        border.width: abandonmentRoot.scaleAwareChildStrokeWidth(
                            1.0, parent.childStrokeScale)
                    }

                    ShadowedText {
                        x: abandonmentRoot.abandonmentModel.customLastVisitAlignment === "left"
                            ? 11.0 : parent.width - 11.0 - parent.width * 0.36
                        width: parent.width * 0.36
                        height: parent.height
                        text: abandonmentRoot.abandonmentModel.metricLabel.toUpperCase()
                        color: Qt.rgba(
                            abandonmentRoot.abandonmentModel.textColor.r,
                            abandonmentRoot.abandonmentModel.textColor.g,
                            abandonmentRoot.abandonmentModel.textColor.b,
                            0.75
                        )
                        font.family: abandonmentRoot.abandonmentModel.fontFamily
                        font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 0.68
                            * abandonmentRoot.abandonmentModel.customLastVisitHeightScale
                        font.bold: true
                        horizontalAlignment:
                            abandonmentRoot.abandonmentModel.customLastVisitAlignment === "left"
                                ? Text.AlignLeft : Text.AlignRight
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                        shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                        shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                        shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                    }

                    ShadowedText {
                        x: abandonmentRoot.abandonmentModel.customLastVisitAlignment === "left"
                            ? parent.width * 0.40 : 7.0
                        width: parent.width * 0.56 - 7.0
                        height: parent.height
                        text: abandonmentRoot.abandonmentModel.metricValue
                        opacity: abandonmentRoot.dynamicContentOpacity
                        color: abandonmentRoot.abandonmentModel.textColor
                        font.family: abandonmentRoot.abandonmentModel.fontFamily
                        font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 0.95
                            * abandonmentRoot.abandonmentModel.customLastVisitHeightScale
                        font.bold: true
                        horizontalAlignment:
                            abandonmentRoot.abandonmentModel.customLastVisitAlignment === "left"
                                ? Text.AlignRight : Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                        fontSizeMode: Text.HorizontalFit
                        minimumPointSize: 7.0
                        shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                        shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                        shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                        shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                    }
                }

                Item {
                    id: ledgerGroupFrame
                    objectName: "abandonmentLedgerGroup"
                    readonly property int rowCount: Math.max(1, Math.ceil(ledgerRepeater.count / 2.0))
                    readonly property int columnCount: Math.max(1, Math.min(2, ledgerRepeater.count))
                    readonly property real canonicalWidth: columnCount
                        * abandonmentRoot.canonicalShelfWidth
                        + Math.max(0, columnCount - 1) * 12.0
                    readonly property real canonicalHeight: rowCount
                        * abandonmentRoot.canonicalShelfHeight
                        + Math.max(0, rowCount - 1) * abandonmentRoot.canonicalShelfGap
                    readonly property real shelfWidth: abandonmentRoot.canonicalShelfWidth
                        * abandonmentRoot.abandonmentModel.customShelfGroupWidthScale
                    readonly property real shelfHeight: abandonmentRoot.canonicalShelfHeight
                        * abandonmentRoot.abandonmentModel.customShelfGroupHeightScale
                    property bool customEditReflowEnabled: abandonmentRoot.shelfGroupOnAuthoredRail
                    property real customEditPlacementCompensationX:
                        abandonmentRoot.textRailShift(abandonmentRoot.shelfGroupOnAuthoredRail)
                            + abandonmentRoot.artworkTextReflow(abandonmentRoot.shelfGroupOnAuthoredRail)
                    property real customEditPlacementCompensationY:
                        abandonmentRoot.shelfGroupOnAuthoredRail
                            ? abandonmentRoot.backlogLayoutHeightDelta
                                + abandonmentRoot.gameNameLayoutHeightDelta
                                + abandonmentRoot.flavourLayoutHeightDelta
                                + abandonmentRoot.lastVisitLayoutHeightDelta
                            : 0.0
                    visible: ledgerRepeater.count > 0
                    x: abandonmentRoot.textRailX(abandonmentRoot.shelfGroupOnAuthoredRail)
                        + abandonmentRoot.artworkTextReflow(abandonmentRoot.shelfGroupOnAuthoredRail)
                        + abandonmentRoot.abandonmentModel.customShelfGroupXOffset
                            * abandonmentRoot.baseAuthoredWidth
                    y: 226.0
                        + (abandonmentRoot.shelfGroupOnAuthoredRail
                            ? abandonmentRoot.backlogLayoutHeightDelta
                                + abandonmentRoot.gameNameLayoutHeightDelta
                                + abandonmentRoot.flavourLayoutHeightDelta
                                + abandonmentRoot.lastVisitLayoutHeightDelta
                            : 0.0)
                        + abandonmentRoot.abandonmentModel.customShelfGroupYOffset
                            * abandonmentRoot.baseAuthoredHeight
                    width: columnCount * shelfWidth
                        + Math.max(0, columnCount - 1) * 12.0
                    height: rowCount * shelfHeight
                        + Math.max(0, rowCount - 1) * abandonmentRoot.canonicalShelfGap

                    Repeater {
                        id: ledgerRepeater
                        model: abandonmentRoot.abandonmentModel.fieldModel

                        delegate: Item {
                            required property string fieldId
                            required property string fieldLabel
                            required property string fieldValue
                            required property int index
                            objectName: "abandonmentLedgerShelf_" + fieldId
                            readonly property int row: Math.floor(index / 2)
                            readonly property int column: index % 2
                            x: column * (ledgerGroupFrame.shelfWidth + 12.0)
                            y: row * (ledgerGroupFrame.shelfHeight
                                + abandonmentRoot.canonicalShelfGap)
                            width: ledgerGroupFrame.shelfWidth
                            height: ledgerGroupFrame.shelfHeight

                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: abandonmentRoot.scaleAwareStrokeWidthForScale(
                                    1.0, abandonmentRoot.presentationScale
                                )
                                color: abandonmentRoot.abandonmentModel.steamMetricSeparatorColor
                            }

                            Rectangle {
                                x: abandonmentRoot.abandonmentModel.customShelfGroupAlignment === "left"
                                    ? 0.0 : Math.max(0.0, parent.width - width)
                                anchors.verticalCenter: parent.verticalCenter
                                width: 4.0
                                height: 4.0
                                radius: 2.0
                                color: Qt.rgba(
                                    abandonmentRoot.abandonmentModel.accentColor.r,
                                    abandonmentRoot.abandonmentModel.accentColor.g,
                                    abandonmentRoot.abandonmentModel.accentColor.b,
                                    0.76
                                )
                            }

                            ShadowedText {
                                x: abandonmentRoot.abandonmentModel.customShelfGroupAlignment === "left"
                                    ? 9.0
                                    : 9.0 + (parent.width - 13.0) * 0.47
                                width: (parent.width - 13.0) * 0.53
                                height: parent.height
                                text: fieldLabel.toUpperCase()
                                color: Qt.rgba(
                                    abandonmentRoot.abandonmentModel.textColor.r,
                                    abandonmentRoot.abandonmentModel.textColor.g,
                                    abandonmentRoot.abandonmentModel.textColor.b,
                                    Math.max(0.47, abandonmentRoot.abandonmentModel.textColor.a * 0.72)
                                )
                                font.family: abandonmentRoot.abandonmentModel.fontFamily
                                font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 0.68
                                    * abandonmentRoot.abandonmentModel.customShelfGroupHeightScale
                                font.bold: true
                                horizontalAlignment:
                                    abandonmentRoot.abandonmentModel.customShelfGroupAlignment === "left"
                                        ? Text.AlignLeft : Text.AlignRight
                                verticalAlignment: Text.AlignVCenter
                                fontSizeMode: Text.HorizontalFit
                                minimumPointSize: 6.0
                                elide: Text.ElideRight
                                shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                                shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                                shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                                shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                            }

                            ShadowedText {
                                x: abandonmentRoot.abandonmentModel.customShelfGroupAlignment === "left"
                                    ? 9.0 + (parent.width - 13.0) * 0.55 : 9.0
                                width: (parent.width - 13.0) * 0.45
                                height: parent.height
                                text: fieldValue.toUpperCase()
                                opacity: abandonmentRoot.dynamicContentOpacity
                                color: abandonmentRoot.abandonmentModel.textColor
                                font.family: abandonmentRoot.abandonmentModel.fontFamily
                                font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 0.68
                                    * abandonmentRoot.abandonmentModel.customShelfGroupHeightScale
                                font.bold: true
                                horizontalAlignment:
                                    abandonmentRoot.abandonmentModel.customShelfGroupAlignment === "left"
                                        ? Text.AlignRight : Text.AlignLeft
                                verticalAlignment: Text.AlignVCenter
                                fontSizeMode: Text.HorizontalFit
                                minimumPointSize: 6.0
                                elide: Text.ElideRight
                                shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                                shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                                shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                                shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                            }
                        }
                    }
                }

            }

            Item {
                id: connectRequired
                objectName: "abandonmentConnectRequired"
                visible: abandonmentRoot.abandonmentModel.viewState === "connect_required"
                x: 74.0 + abandonmentRoot.extraContentWidth * 0.5
                y: 122.0 + abandonmentRoot.extraContentHeight * 0.5
                width: 412.0
                height: 66.0

                Row {
                    anchors.horizontalCenter: parent.horizontalCenter
                    height: 38.0

                    ShadowedText {
                        width: 90.0
                        height: parent.height
                        text: abandonmentRoot.abandonmentModel.actionLabel
                        color: abandonmentRoot.abandonmentModel.accentColor
                        font.family: abandonmentRoot.abandonmentModel.fontFamily
                        font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 1.12
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                        shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                        shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                        shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY

                        TapHandler {
                            enabled: abandonmentRoot.abandonmentModel.interactionEnabled
                            acceptedButtons: Qt.LeftButton
                            onTapped: abandonmentRoot.settingsRequested(
                                abandonmentRoot.abandonmentModel.settingsTarget
                            )
                        }
                    }

                    ShadowedText {
                        width: implicitWidth
                        height: parent.height
                        text: abandonmentRoot.abandonmentModel.actionText.replace(
                            abandonmentRoot.abandonmentModel.actionLabel,
                            ""
                        )
                        color: abandonmentRoot.abandonmentModel.textColor
                        font.family: abandonmentRoot.abandonmentModel.fontFamily
                        font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 1.12
                        font.bold: true
                        verticalAlignment: Text.AlignVCenter
                        shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                        shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                        shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                        shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                    }
                }

                ShadowedText {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 24.0
                    text: abandonmentRoot.abandonmentModel.statusText
                    color: abandonmentRoot.abandonmentModel.textColor
                    font.family: abandonmentRoot.abandonmentModel.fontFamily
                    font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 0.82
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                    shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                    shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                    shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                }
            }
        }
    }
}
