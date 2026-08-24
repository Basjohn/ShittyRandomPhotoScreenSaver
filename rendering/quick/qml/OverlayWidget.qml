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
    opacity: fadeOpacity
    // Never clip the composed card/text shadows or their negative offsets.
    clip: false
    visible: opacity > 0.0

    default property alias content: card.content

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
