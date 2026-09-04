import QtQuick

// Display-local CUSTOM guide/grid underlay. This sits below retained widgets so
// centering guides and the stronger absolute-center cross never paint over
// authored content. Python remains the sole geometry/snap authority; this item
// is presentation-only and owns no cadence.
Item {
    id: guideUnderlay
    objectName: "customLayoutGuideUnderlay"

    property bool editActive: false
    property int gridStep: 24
    property int gridGutter: 24
    property var verticalCenterGuides: []
    property var horizontalCenterGuides: []

    visible: editActive
    enabled: false
    clip: false

    Repeater {
        model: guideUnderlay.editActive
               ? Math.floor(guideUnderlay.width / guideUnderlay.gridStep) + 1
               : 0
        delegate: Rectangle {
            required property int index
            x: index * guideUnderlay.gridStep
            width: 1
            height: guideUnderlay.height
            color: index % 4 === 0 ? "#3affffff" : "#1cffffff"
        }
    }

    Repeater {
        model: guideUnderlay.editActive
               ? Math.floor(guideUnderlay.height / guideUnderlay.gridStep) + 1
               : 0
        delegate: Rectangle {
            required property int index
            y: index * guideUnderlay.gridStep
            width: guideUnderlay.width
            height: 1
            color: index % 4 === 0 ? "#3affffff" : "#1cffffff"
        }
    }

    // The absolute display-centre cross is deliberately stronger than the grid
    // while remaining below every retained widget and edit-frame layer.
    Rectangle {
        objectName: "customLayoutAbsoluteCenterVertical"
        visible: guideUnderlay.editActive
        x: Math.round(guideUnderlay.width / 2.0)
        width: 2
        height: guideUnderlay.height
        color: "#70ffffff"
    }

    Rectangle {
        objectName: "customLayoutAbsoluteCenterHorizontal"
        visible: guideUnderlay.editActive
        y: Math.round(guideUnderlay.height / 2.0)
        width: guideUnderlay.width
        height: 2
        color: "#70ffffff"
    }

    Rectangle {
        objectName: "customLayoutSafeGutter"
        anchors.fill: parent
        anchors.margins: guideUnderlay.gridGutter
        color: "transparent"
        border.width: 1
        border.color: "#74b46eff"
    }

    // Active centering snaps are gentle purple and intentionally under widgets.
    Repeater {
        model: guideUnderlay.verticalCenterGuides
        delegate: Rectangle {
            required property var modelData
            objectName: "customLayoutVerticalCenterGuide"
            property string guideKind: String(modelData.kind)
            x: Number(modelData.position)
            width: 2
            height: guideUnderlay.height
            color: "#a8b46eff"
        }
    }

    Repeater {
        model: guideUnderlay.horizontalCenterGuides
        delegate: Rectangle {
            required property var modelData
            objectName: "customLayoutHorizontalCenterGuide"
            property string guideKind: String(modelData.kind)
            y: Number(modelData.position)
            width: guideUnderlay.width
            height: 2
            color: "#a8b46eff"
        }
    }
}
