import QtQuick

// One card's surface material (Docs/Architecture/Card_Surface_Materials.md). It samples
// the display's one shared SurfaceBackdropSource through this card's rounded shape and
// draws nothing else: no capture, blur pass, layer or timer of its own. Loaded only
// while the card's material is not Normal; until the backdrop's first refresh (texture
// alpha 0) it paints exactly the Normal fill.
ShaderEffect {
    id: surface
    objectName: "materialSurface"

    property var backdrop: null
    property string material: "acrylic"
    property real cornerRadius: 8.0
    property real contentInset: 8.0
    property real borderWidth: 0.0
    property color normalColor: "#b3101010"
    property color tintColor: "#b3101010"
    property color textColor: "#ffffffff"

    // Presentation constants per material (one shader, different uniforms):
    //   blurTint        = (blur level 0 light .. 1 heavy, tint opacity at theme alpha 0, at 1, saturation)
    //   lightNoise      = (luminosity pull toward the tint, grain, haze toward white, smoke darkening)
    //   glassLegibility = (edge highlight, refraction px, legibility shift, contrast floor)
    readonly property var parameters: ({
        "acrylic": [Qt.vector4d(1.0, 0.42, 0.70, 1.35), Qt.vector4d(0.30, 0.030, 0.0, 0.0),
                    Qt.vector4d(0.0, 0.0, 0.10, 3.0)],
        "glass": [Qt.vector4d(0.0, 0.05, 0.28, 1.15), Qt.vector4d(0.0, 0.0, 0.0, 0.0),
                  Qt.vector4d(0.20, 5.0, 0.14, 3.0)],
        "frosted": [Qt.vector4d(1.0, 0.20, 0.42, 0.80), Qt.vector4d(0.0, 0.045, 0.22, 0.0),
                    Qt.vector4d(0.05, 0.0, 0.10, 3.0)],
        "mica": [Qt.vector4d(1.0, 0.72, 0.86, 0.70), Qt.vector4d(0.45, 0.0, 0.0, 0.0),
                 Qt.vector4d(0.0, 0.0, 0.06, 3.0)],
        "smoked": [Qt.vector4d(0.45, 0.35, 0.58, 0.55), Qt.vector4d(0.0, 0.012, 0.0, 0.45),
                   Qt.vector4d(0.06, 0.0, 0.08, 3.0)]
    })
    readonly property var resolvedParameters: parameters[material] || parameters["acrylic"]

    // Shader inputs (names match surface_material.frag's uniform block).
    readonly property var source: backdrop
    readonly property vector2d itemSize: Qt.vector2d(width, height)
    readonly property vector4d blurTint: resolvedParameters[0]
    readonly property vector4d lightNoise: resolvedParameters[1]
    readonly property vector4d glassLegibility: resolvedParameters[2]

    blending: true
    vertexShader: "shaders/surface_material.vert.qsb"
    fragmentShader: "shaders/surface_material.frag.qsb"
}
