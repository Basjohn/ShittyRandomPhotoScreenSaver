import QtQuick
import QtQuick.Effects

OverlayWidget {
    id: achievementRoot
    objectName: "achievementPulsePresentation"

    required property var achievementModel
    semanticDoubleClickEnabled: achievementModel.interactionEnabled
    signal refreshRequested()
    signal settingsRequested(string target)

    readonly property real authoredWidth: achievementModel.authoredWidth
    readonly property real authoredHeight: achievementModel.authoredHeight
    readonly property real contentScale: Math.max(
        0.05,
        Math.min(width / authoredWidth, height / authoredHeight)
    )

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

    TapHandler {
        enabled: achievementRoot.achievementModel.interactionEnabled
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: achievementRoot.refreshRequested()
    }

    Item {
        id: authoredCanvas
        objectName: "achievementAuthoredCanvas"
        width: achievementRoot.authoredWidth
        height: achievementRoot.authoredHeight
        // OverlayWidget now owns the whole-card uniform transform.  Keep this
        // authored content at canonical coordinates inside that transformed
        // shell; a second local scale/centering pass would recreate the visible
        // top/bottom bands that parity is removing.
        x: 0.0
        y: 0.0
        scale: 1.0
        transformOrigin: Item.TopLeft

        BrandedHeader {
            id: headerFrame
            frameObjectName: "achievementHeaderFrame"
            logoObjectName: "achievementSteamLogo"
            textObjectName: "achievementHeaderText"
            x: 18.0
            y: 14.0
            label: achievementRoot.achievementModel.headerText
            logoSource: achievementRoot.achievementModel.logoSource
            fillColor: achievementRoot.achievementModel.headerFillColor
            borderColor: achievementRoot.achievementModel.headerBorderColor
            borderWidth: achievementRoot.scaleAwareStrokeWidthForScale(
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
            x: 300.0
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

            readonly property bool verticalArtwork:
                achievementRoot.achievementModel.showArtwork
                && (achievementRoot.achievementModel.artworkShape === "square"
                    || achievementRoot.achievementModel.artworkShape === "portrait")
            readonly property real artworkWidth: verticalArtwork
                ? achievementRoot.achievementModel.squareArtworkSize : 180.0
            readonly property real artworkHeight:
                achievementRoot.achievementModel.artworkShape === "portrait"
                    ? artworkWidth * 1.4
                    : (verticalArtwork ? artworkWidth : 86.0)
            // The vertical artwork/metric rail is centered over the third
            // supporting-field column (PREVIOUSLY in the default composition).
            // Keep this relationship mathematical so future size changes cannot
            // drift the cover back toward the outer edge.
            readonly property real thirdFieldColumnCenter: 18.0 + 2.0 * 191.0 + 182.0 / 2.0
            readonly property real artworkX: verticalArtwork
                ? thirdFieldColumnCenter - artworkWidth / 2.0 : 402.0
            readonly property real titleWidth: !achievementRoot.achievementModel.showArtwork
                ? 564.0 : (verticalArtwork ? artworkX - 32.0 : 370.0)

            Item {
                id: artworkFrame
                objectName: "achievementArtworkFrame"
                visible: achievementRoot.achievementModel.showArtwork
                x: normalContent.artworkX
                y: 14.0
                width: normalContent.artworkWidth
                height: normalContent.artworkHeight

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
                    anchors.margins: 2.0
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
                    radius: 5.0
                    visible: false
                    layer.enabled: true
                }

                // Keep the outline on top of the image, matching the sane Steam
                // artwork-frame contract used by Abandonment Issues.  Painting
                // the border under an inset image made Pulse's edge look washed
                // and inconsistently transparent.
                Rectangle {
                    objectName: "achievementArtworkBorder"
                    anchors.fill: parent
                    radius: 7.0
                    color: "transparent"
                    border.color: achievementRoot.achievementModel.steamArtworkBorderColor
                    border.width: achievementRoot.scaleAwareStrokeWidthForScale(
                        2.0, achievementRoot.contentScale
                    )
                }
            }

            ShadowedText {
                id: gameTitle
                objectName: "achievementGameTitle"
                x: 18.0
                y: 62.0
                width: normalContent.titleWidth
                height: 34.0
                text: achievementRoot.achievementModel.title
                color: achievementRoot.achievementModel.textColor
                font.family: achievementRoot.achievementModel.fontFamily
                font.pointSize: achievementRoot.achievementModel.fontSize + 5.0
                font.bold: true
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                shadowColor: achievementRoot.achievementModel.textShadowColor
                shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
            }

            ShadowedText {
                objectName: "achievementSubtitle"
                // The legacy presenter treated the latest-unlock stack as the
                // subtitle area's content, rather than painting both layers.
                visible: text.length > 0 && unlockRepeater.count === 0
                x: 18.0
                y: 100.0
                width: normalContent.titleWidth
                height: 88.0
                text: achievementRoot.achievementModel.subtitle
                color: achievementRoot.achievementModel.textColor
                font.family: achievementRoot.achievementModel.fontFamily
                font.pointSize: achievementRoot.achievementModel.fontSize * 0.78
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
                    x: 18.0
                    y: index === 0 ? 100.0 : 130.0 + (index - 1) * 14.0
                    // The first, larger unlock owns the full title rail.  The
                    // recent-achievement badge begins below it and therefore must
                    // not steal horizontal/vertical space from that first line.
                    // Smaller lines stop just before the badge only when it is
                    // actually present, avoiding text painting underneath it.
                    width: index === 0 || !latestArtworkFrame.visible
                        ? normalContent.titleWidth
                        : Math.min(
                            normalContent.titleWidth,
                            Math.max(0.0, latestArtworkFrame.x - 24.0)
                        )
                    height: index === 0 ? 26.0 : 13.0
                    text: unlockText
                    color: achievementRoot.achievementModel.textColor
                    font.family: achievementRoot.achievementModel.fontFamily
                    font.pointSize: index === 0
                        ? achievementRoot.achievementModel.fontSize * 0.72
                        : achievementRoot.achievementModel.fontSize * 0.48
                    font.bold: index === 0
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                    shadowColor: achievementRoot.achievementModel.textShadowColor
                    shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                    shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
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
                // not to the game-cover rail.  Its top starts immediately below
                // the large first unlock line; no extra line spacing is reserved.
                x: 130.0
                y: 130.0
                width: 40.0
                height: 40.0

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
                        1.0, achievementRoot.contentScale
                    )
                    z: 2
                }
            }

            ShadowedText {
                id: metricText
                objectName: "achievementMetric"
                visible: achievementRoot.achievementModel.metricValue.length > 0
                x: normalContent.verticalArtwork
                    ? normalContent.artworkX - 10.0 : 392.0
                y: normalContent.verticalArtwork
                    ? 14.0 + normalContent.artworkHeight + 6.0 : 108.0
                width: normalContent.verticalArtwork
                    ? normalContent.artworkWidth + 20.0 : 200.0
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

            Repeater {
                id: fieldRepeater
                model: achievementRoot.achievementModel.fieldModel

                delegate: Item {
                    required property string fieldId
                    required property string fieldLabel
                    required property string fieldValue
                    required property int index
                    objectName: "achievementField_" + fieldId
                    readonly property int compactRow: Math.floor(index / 3)
                    readonly property int column: index % 3
                    readonly property int railStride:
                        achievementRoot.achievementModel.doubleCapsules ? 2 : 1
                    readonly property int railCount: Math.max(
                        1,
                        Math.ceil(fieldRepeater.count / 3) * railStride
                    )
                    readonly property real railStep:
                        achievementRoot.achievementModel.capsuleHeight
                        + achievementRoot.achievementModel.capsuleGap
                    readonly property real firstRailY:
                        authoredCanvas.height - 16.0
                        - achievementRoot.achievementModel.capsuleHeight
                        - (railCount - 1) * railStep
                    x: 18.0 + column * 191.0
                    y: firstRailY + compactRow * railStride * railStep
                    width: 182.0
                    height: achievementRoot.achievementModel.doubleCapsules
                        ? achievementRoot.achievementModel.capsuleHeight * 2.0
                            + achievementRoot.achievementModel.capsuleGap
                        : achievementRoot.achievementModel.capsuleHeight

                    AchievementCapsule {
                        anchors.fill: parent
                        fieldId: parent.fieldId
                        fieldLabel: parent.fieldLabel
                        fieldValue: parent.fieldValue
                        doubled: achievementRoot.achievementModel.doubleCapsules
                        capsuleHeight: achievementRoot.achievementModel.capsuleHeight
                        capsuleGap: achievementRoot.achievementModel.capsuleGap
                        capsuleFontSize: achievementRoot.achievementModel.capsuleFontSize
                        fontFamily: achievementRoot.achievementModel.fontFamily
                        fillColor: achievementRoot.achievementModel.capsuleFillColor
                        borderColor: achievementRoot.achievementModel.capsuleBorderColor
                        textColor: achievementRoot.achievementModel.textColor
                        textShadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                        textShadowColor: achievementRoot.achievementModel.textShadowColor
                        textShadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                        textShadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
                    }
                }
            }
        }

        Item {
            id: connectRequired
            objectName: "achievementConnectRequired"
            visible: achievementRoot.achievementModel.viewState === "connect_required"
            x: 44.0
            y: 76.0
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
