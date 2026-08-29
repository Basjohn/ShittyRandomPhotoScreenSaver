import QtQuick

// One retained ordinary-widget presentation root, assigned an explicit display
// rectangle by the per-display presentation host. `fadeOpacity` is the
// whole-widget authored fade and maps to root opacity, independent of the
// card/text/shadow alphas beneath it. Callers compose shell primitives
// (ShadowedText, Separator, rows) into `content`. This is a thin presentation
// shell that composes shared E3 primitives; it holds no model, service, settings
// or QWidget reference.
Item {
    id: overlayWidget
    objectName: "overlayWidget"

    property real fadeOpacity: 1.0
    property bool workingVisible: true
    property bool semanticDoubleClickEnabled: false
    opacity: fadeOpacity
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
    property alias cardShadowEnabled: card.shadowEnabled
    property alias cardShadowColor: card.shadowColor
    property alias cardShadowBlur: card.shadowBlur
    property alias cardShadowOffsetX: card.shadowOffsetX
    property alias cardShadowOffsetY: card.shadowOffsetY
    property alias cardShadowSpread: card.shadowSpread

    OverlayCard {
        id: card
        objectName: "overlayWidgetCard"
        anchors.fill: parent
    }
}
