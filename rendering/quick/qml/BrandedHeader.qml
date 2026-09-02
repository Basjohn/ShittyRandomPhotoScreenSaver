import QtQuick
import QtQuick.Effects

// Shared branded header pill used by ordinary and Steam-authored widgets.
// Geometry is intentionally fixed in authored pixels and therefore follows the
// owning widget's single retained scale transform.  The pill expands to its full
// logo + label width; header labels are never elided or clipped.
Item {
    id: header
    objectName: "brandedHeader"

    property string frameObjectName: "brandedHeaderFrame"
    property string logoObjectName: "brandedHeaderLogo"
    property string textObjectName: "brandedHeaderText"

    property string label: ""
    property url logoSource: ""
    property bool logoDesaturated: false
    property bool interactionEnabled: false

    property color fillColor: "transparent"
    property color borderColor: "white"
    property real borderWidth: 1.0
    property color textColor: "white"
    property string fontFamily: "Inter"
    // Media established the accepted baseline: 20 pt family text * 0.82.
    // Keep the branded header itself family-invariant; whole-widget scaling owns
    // enlargement/shrinkage rather than per-widget font-size quirks.
    property real fontPointSize: 16.4

    property bool textShadowEnabled: true
    property color textShadowColor: "#54000000"
    property real textShadowOffsetX: 2.0
    property real textShadowOffsetY: 2.0

    property bool shadowEnabled: true
    property color shadowColor: "#55000000"
    property real shadowBlur: 4.5
    property real shadowOffsetX: 4.6
    property real shadowOffsetY: 4.6

    signal activated()

    readonly property real horizontalPadding: 10.0
    readonly property real verticalPadding: 5.0
    readonly property real logoSize: 25.0
    readonly property real contentGap: 8.0
    readonly property real cornerRadius: 9.0

    readonly property real shadowExtendLeft: Math.max(0.0, -shadowOffsetX)
    readonly property real shadowExtendTop: Math.max(0.0, -shadowOffsetY)
    readonly property real shadowExtendRight: Math.max(0.0, shadowOffsetX)
    readonly property real shadowExtendBottom: Math.max(0.0, shadowOffsetY)

    implicitWidth: headerRow.implicitWidth + horizontalPadding * 2.0
    implicitHeight: Math.max(36.0, headerRow.implicitHeight + verticalPadding * 2.0)
    width: implicitWidth
    height: implicitHeight
    clip: false

    // Extension shadow: preserve shadow coverage at the opposite/top-left edge
    // instead of translating the entire shadow surface.  This mirrors the outer
    // card shadow contract while using the modest Media transport-bar profile.
    RectangularShadow {
        objectName: "brandedHeaderShadow"
        x: -header.shadowExtendLeft
        y: -header.shadowExtendTop
        width: header.width + header.shadowExtendLeft + header.shadowExtendRight
        height: header.height + header.shadowExtendTop + header.shadowExtendBottom
        visible: header.shadowEnabled
        color: header.shadowColor
        blur: header.shadowBlur
        radius: header.cornerRadius
        spread: 0.0
        offset: Qt.vector2d(0.0, 0.0)
        cached: true
        z: -1
    }

    Rectangle {
        id: frame
        objectName: header.frameObjectName
        anchors.fill: parent
        radius: header.cornerRadius
        color: header.fillColor
        border.color: header.borderColor
        border.width: header.borderWidth
        clip: false
    }

    Row {
        id: headerRow
        anchors.centerIn: parent
        spacing: header.contentGap

        Item {
            id: logoBox
            objectName: header.logoObjectName
            visible: header.logoSource.toString().length > 0
            width: visible ? header.logoSize : 0.0
            height: visible ? header.logoSize : 0.0

            // One retained layer effect owns both optional Gmail desaturation and
            // the logo's small directional shadow.  This avoids the old Gmail-only
            // effect path and avoids stacking a second effect just for the shadow.
            // When neither treatment is needed the image renders directly.
            Image {
                id: logoImage
                objectName: "brandedHeaderLogoImage"
                anchors.fill: parent
                source: header.logoSource
                sourceSize.width: Math.round(header.logoSize * 2.0)
                sourceSize.height: Math.round(header.logoSize * 2.0)
                fillMode: Image.PreserveAspectFit
                asynchronous: false
                cache: true
                layer.enabled: header.logoDesaturated || header.textShadowEnabled
                layer.effect: MultiEffect {
                    saturation: header.logoDesaturated ? -1.0 : 0.0
                    shadowEnabled: header.textShadowEnabled
                    shadowColor: header.textShadowColor
                    shadowOpacity: 1.0
                    shadowBlur: 0.0
                    shadowHorizontalOffset: header.textShadowOffsetX
                    shadowVerticalOffset: header.textShadowOffsetY
                    autoPaddingEnabled: true
                }
            }
        }

        ShadowedText {
            id: labelText
            objectName: header.textObjectName
            anchors.verticalCenter: parent.verticalCenter
            // Header labels are presentation chrome, not content metadata: one
            // shared all-caps language regardless of provider/source casing.
            text: header.label.toUpperCase()
            color: header.textColor
            font.family: header.fontFamily
            font.pointSize: header.fontPointSize
            font.bold: true
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideNone
            shadowEnabled: header.textShadowEnabled
            shadowColor: header.textShadowColor
            shadowOffsetX: header.textShadowOffsetX
            shadowOffsetY: header.textShadowOffsetY
        }
    }

    TapHandler {
        enabled: header.interactionEnabled
        acceptedButtons: Qt.LeftButton
        onTapped: header.activated()
    }
}
