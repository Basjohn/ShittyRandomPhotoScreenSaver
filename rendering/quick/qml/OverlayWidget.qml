import QtQuick

// One retained ordinary-widget presentation root, assigned an explicit display
// rectangle by the per-display presentation host. `fadeOpacity` is the
// family-authored lifecycle fade; `startupRevealOpacity` is an independent
// generation gate. Multiplying them prevents a family-local fade request (Steam
// in particular) from punching through before the coordinated startup reveal.
// Callers compose shell primitives
// (ShadowedText, Separator, rows) into `content`. This is a thin presentation
// shell that composes shared E3 primitives; it holds no model, service, settings
// or QWidget reference.
Item {
    id: overlayWidget
    objectName: "overlayWidget"

    property real fadeOpacity: 1.0
    property real startupRevealOpacity: 1.0
    property bool workingVisible: true
    property bool semanticDoubleClickEnabled: false
    opacity: fadeOpacity * startupRevealOpacity
    // Never clip the composed card/text shadows or their negative offsets.
    clip: false
    visible: workingVisible && opacity > 0.0

    default property alias content: card.content

    // Content-driven outer geometry (H option A): each family binds its stable
    // *preferred* content size here from its intrinsic QML content (text implicit
    // sizes, fixed dimensions), NOT from this item's assigned width/height. The
    // display owner reads these as size only and remains the sole outer-rect /
    // anchor / clamp authority; QML never anchors itself. Deriving preferred size
    // from the assigned width would create a width<->preferredWidth feedback
    // loop, so families must derive it from intrinsic content plus card.shellInset.
    // A value of 0 means the family has not yet declared a real preferred size.
    property real preferredContentWidth: 0.0
    property real preferredContentHeight: 0.0

    // Emitted (size only) whenever the declared preferred content size changes,
    // so the owner can re-anchor without polling or per-frame callbacks.
    signal preferredContentSizeChanged(real width, real height)
    onPreferredContentWidthChanged: overlayWidget.preferredContentSizeChanged(
        overlayWidget.preferredContentWidth, overlayWidget.preferredContentHeight
    )
    onPreferredContentHeightChanged: overlayWidget.preferredContentSizeChanged(
        overlayWidget.preferredContentWidth, overlayWidget.preferredContentHeight
    )

    // H9 uniform CUSTOM resize (opt-in). When a family enables this, the whole
    // authored presentation - card shell plus every composed primitive - is laid
    // out ONCE at its content-driven baseline size and scaled as a single
    // coordinate relationship, so text, spacing, row heights, artwork, chrome,
    // borders/shadows and pointer/hit geometry enlarge/shrink together. This is
    // the one real retained-presentation scale: the factor is DERIVED from the
    // ratio of the Python-assigned outer rect to the family's own baseline
    // preferred content size, so there is no QML->Python size feedback, no second
    // geometry owner, and Python/session remains the sole outer-rect authority.
    // `Math.min` keeps the scale uniform (never distorts a single axis); if an
    // axis clamp changes the outer aspect the presentation letterboxes centred
    // rather than stretching. Families that do not opt in keep the historical
    // fill behaviour at scale 1, so this shared change is inert for them.
    property bool uniformScaleTransform: false

    readonly property real presentationScale: (
        overlayWidget.uniformScaleTransform
            && overlayWidget.preferredContentWidth > 0.0
            && overlayWidget.preferredContentHeight > 0.0
            && overlayWidget.width > 0.0
            && overlayWidget.height > 0.0
    )
        ? Math.min(
            overlayWidget.width / overlayWidget.preferredContentWidth,
            overlayWidget.height / overlayWidget.preferredContentHeight
        )
        : 1.0

    // Expose the shell inset so families compute preferred size consistently.
    readonly property real shellInset: card.shellInset

    // The common card shell is forwarded so the whole ordinary-widget shell
    // stays a single retained component with explicit presentation properties.
    property alias cardShellEnabled: card.shellEnabled
    property alias cardBackgroundColor: card.backgroundColor
    property alias cardBorderColor: card.borderColor
    property alias cardBorderWidth: card.borderWidth
    property alias cardCornerRadius: card.cornerRadius
    property alias cardPadding: card.padding
    // Production ordinary cards project their shadow into the display-level
    // underlay so no widget shadow can overpaint another widget's content.
    // Direct primitive/smoke hosts may leave this false and keep the local
    // fallback shadow; production host adoption flips it true atomically.
    property bool externalCardShadow: false
    property bool cardShadowEnabled: true
    property color cardShadowColor: "#96000000"
    property real cardShadowBlur: 18.0
    property real cardShadowOffsetX: 0.0
    property real cardShadowOffsetY: 4.0
    property real cardShadowSpread: 0.0
    property real cardShadowExtendLeft: 0.0
    property real cardShadowExtendTop: 0.0
    property real cardShadowExtendRight: 0.0
    property real cardShadowExtendBottom: 0.0

    // Visual card bounds in this root's coordinate system after the optional
    // whole-card uniform transform. The external underlay binds these values so
    // letterboxed CUSTOM geometry still shadows the actual rendered card, not
    // the larger assigned outer rectangle.
    readonly property real cardShadowVisualWidth: authoredRoot.width * presentationScale
    readonly property real cardShadowVisualHeight: authoredRoot.height * presentationScale
    readonly property real cardShadowVisualX: (width - cardShadowVisualWidth) / 2.0
    readonly property real cardShadowVisualY: (height - cardShadowVisualHeight) / 2.0

    Item {
        id: authoredRoot
        objectName: "overlayAuthoredRoot"
        // Uniform-scale families lay out at their fixed baseline content size and
        // scale as a whole; every other family fills the assigned rect exactly
        // (historical behaviour). `anchors.centerIn` only sets position, so the
        // non-transform case is identical to the former `card` fill.
        width: (overlayWidget.uniformScaleTransform
            && overlayWidget.preferredContentWidth > 0.0)
            ? overlayWidget.preferredContentWidth
            : overlayWidget.width
        height: (overlayWidget.uniformScaleTransform
            && overlayWidget.preferredContentHeight > 0.0)
            ? overlayWidget.preferredContentHeight
            : overlayWidget.height
        anchors.centerIn: parent
        transformOrigin: Item.Center
        scale: overlayWidget.presentationScale
        clip: false

        OverlayCard {
            id: card
            objectName: "overlayWidgetCard"
            anchors.fill: parent
            shadowEnabled: overlayWidget.cardShadowEnabled && !overlayWidget.externalCardShadow
            shadowColor: overlayWidget.cardShadowColor
            shadowBlur: overlayWidget.cardShadowBlur
            shadowOffsetX: overlayWidget.cardShadowOffsetX
            shadowOffsetY: overlayWidget.cardShadowOffsetY
            shadowSpread: overlayWidget.cardShadowSpread
            shadowExtendLeft: overlayWidget.cardShadowExtendLeft
            shadowExtendTop: overlayWidget.cardShadowExtendTop
            shadowExtendRight: overlayWidget.cardShadowExtendRight
            shadowExtendBottom: overlayWidget.cardShadowExtendBottom
        }
    }
}
