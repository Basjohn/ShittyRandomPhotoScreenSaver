// Crisp vector icons for the Studio shell (24x24 stroke paths, drawn with Qt Quick Shapes).
// Names are mode-neutral; a mode refers to them by name (e.g. workspace / group icons).
import QtQuick
import QtQuick.Shapes

Item {
    id: icon
    property string name: ""
    property color color: "white"
    property real stroke: 1.8
    property bool filled: false
    implicitWidth: 18
    implicitHeight: 18

    readonly property var paths: ({
        "play": "M7 5 L19 12 L7 19 Z",
        "pause": "M8 5 L8 19 M16 5 L16 19",
        "eye": "M2 12 C5 6 19 6 22 12 C19 18 5 18 2 12 Z M12 9 A3 3 0 1 0 12.01 9",
        "eye-off": "M2 12 C5 6 19 6 22 12 C19 18 5 18 2 12 Z M4 20 L20 4",
        "check": "M5 12.5 L10 17.5 L19 7",
        "reset": "M4 12 A8 8 0 1 0 7 5.8 M4 4 L4 9 L9 9",
        "plus": "M12 5 L12 19 M5 12 L19 12",
        "minus": "M5 12 L19 12",
        "wave": "M2 12 C5 4 8 4 11 12 C14 20 17 20 20 12 L22 12",
        "bars": "M5 20 L5 12 M10 20 L10 6 M15 20 L15 10 M20 20 L20 15",
        "palette": "M12 3 A9 9 0 1 0 12 21 C14 21 14 18 13 17 C12 15.5 13.5 14 15 14 L17 14 A4 4 0 0 0 21 10 C21 6 17 3 12 3 Z M7.5 11 A1 1 0 1 0 7.51 11 M10 7 A1 1 0 1 0 10.01 7 M15 7.5 A1 1 0 1 0 15.01 7.5",
        "cube": "M12 2.5 L20.5 7 L20.5 17 L12 21.5 L3.5 17 L3.5 7 Z M3.5 7 L12 11.5 L20.5 7 M12 11.5 L12 21.5",
        "camera": "M3 7 L7 7 L9 4.5 L15 4.5 L17 7 L21 7 L21 19 L3 19 Z M12 10 A3.5 3.5 0 1 0 12.01 10",
        "loop": "M17 3 L21 7 L17 11 M3 11 L3 9 A2 2 0 0 1 5 7 L21 7 M7 21 L3 17 L7 13 M21 13 L21 15 A2 2 0 0 1 19 17 L3 17",
        "bolt": "M13 2 L4 14 L11 14 L10 22 L20 9 L13 9 Z",
        "height": "M12 3 L12 21 M8 7 L12 3 L16 7 M8 17 L12 21 L16 17",
        "roll": "M20 12 A8 8 0 1 1 17.7 6.3 M20 3 L20 8 L15 8",
        "clock": "M12 3 A9 9 0 1 0 12.01 3 M12 7 L12 12 L16 14",
        "grid": "M3 3 L21 3 L21 21 L3 21 Z M3 9 L21 9 M3 15 L21 15 M9 3 L9 21 M15 3 L15 21",
        "drop": "M12 3 C16 9 19 12 19 15 A7 7 0 0 1 5 15 C5 12 8 9 12 3 Z",
        "gradient": "M3 8 L21 8 L21 16 L3 16 Z M8 8 L8 16 M13 8 L13 16 M18 8 L18 16",
        "sparkle": "M12 3 L13.8 10.2 L21 12 L13.8 13.8 L12 21 L10.2 13.8 L3 12 L10.2 10.2 Z",
        "dots": "M5 15 A1.5 1.5 0 1 0 5.01 15 M10 9 A1.5 1.5 0 1 0 10.01 9 M15 14 A1.5 1.5 0 1 0 15.01 14 M19 7 A1.5 1.5 0 1 0 19.01 7",
        "strand": "M4 20 C8 14 6 9 10 6 C13 4 16 6 20 3",
        "cloud": "M7 18 A4 4 0 0 1 7 10 A6 6 0 0 1 18 9 A4.5 4.5 0 0 1 18 18 Z",
        "floor": "M2 16 L22 16 M5 20 L19 20 M8 12 L16 12",
        "sun": "M12 8 A4 4 0 1 0 12.01 8 M12 2 L12 4 M12 20 L12 22 M2 12 L4 12 M20 12 L22 12 M4.9 4.9 L6.3 6.3 M17.7 17.7 L19.1 19.1 M4.9 19.1 L6.3 17.7 M17.7 6.3 L19.1 4.9",
        "view": "M3 9 L3 3 L9 3 M15 3 L21 3 L21 9 M21 15 L21 21 L15 21 M9 21 L3 21 L3 15",
        "ribbons": "M2 9 C6 4 10 14 14 9 C17 5 20 8 22 9 M2 15 C6 10 10 20 14 15 C17 11 20 14 22 15",
        "flow": "M3 12 L19 12 M14 7 L19 12 L14 17",
        "colour": "M12 3 A9 9 0 1 0 12.01 3 M12 3 L12 21",
        "material": "M4 6 L20 6 L20 18 L4 18 Z M4 6 L20 18",
        "copy": "M8 8 L20 8 L20 20 L8 20 Z M4 16 L4 4 L16 4",
        "edit": "M4 20 L4 16 L15 5 L19 9 L8 20 Z M13 7 L17 11",
        "chevron-down": "M6 9 L12 15 L18 9",
        "chevron-right": "M9 6 L15 12 L9 18",
        "close": "M6 6 L18 18 M18 6 L6 18",
        "undo": "M9 14 L4 9 L9 4 M4 9 L15 9 A5 5 0 0 1 15 19 L11 19",
        "redo": "M15 14 L20 9 L15 4 M20 9 L9 9 A5 5 0 0 0 9 19 L13 19",
        "save": "M5 3 L16 3 L21 8 L21 21 L5 21 Z M8 3 L8 9 L15 9 L15 3 M8 21 L8 14 L16 14 L16 21",
        "lens": "M12 3 A9 9 0 1 0 12.01 3 M12 8 A4 4 0 1 0 12.01 8",
        "width": "M3 12 L21 12 M7 8 L3 12 L7 16 M17 8 L21 12 L17 16",
        "move": "M12 3 L12 21 M3 12 L21 12 M9 6 L12 3 L15 6 M9 18 L12 21 L15 18 M6 9 L3 12 L6 15 M18 9 L21 12 L18 15",
        "help": "M12 3 A9 9 0 1 0 12.01 3 M9.5 9.5 A2.5 2.5 0 1 1 12 12 L12 14 M12 17 L12 17.2"
    })

    // The path is authored on a 24x24 grid and scaled by the ShapePath, so the item's geometry is the icon's
    // own size (layouts and overlap checks see exactly what is drawn).
    Shape {
        id: shape
        readonly property real unit: Math.min(icon.width, icon.height) / 24
        x: (icon.width - 24 * unit) / 2; y: (icon.height - 24 * unit) / 2
        width: 24 * unit; height: 24 * unit
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            scale: Qt.size(shape.unit, shape.unit)
            strokeColor: icon.color
            strokeWidth: icon.stroke
            fillColor: icon.filled ? icon.color : "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: icon.paths[icon.name] || "" }
        }
    }
}
