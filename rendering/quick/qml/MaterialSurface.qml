import QtQuick
import "SurfaceContrast.js" as SurfaceContrast

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
    property real opacityAdjust: 0.0
    property real cornerRadius: 8.0
    property real contentInset: 8.0
    property real borderWidth: 0.0
    property color normalColor: "#b3101010"
    property color tintColor: "#b3101010"
    property color textColor: "#ffffffff"
    property color legibilityInk: Qt.rgba(textColor.r, textColor.g, textColor.b, textColor.a * 0.55)

    // One concentric panel carries the card's steady ink. The required reference
    // ratio is derived from that ink's actual colour/effective alpha at style edges;
    // the shader separately composes material density and enforces the linear-light
    // ink floor. No per-line rows or per-run plates sit on the card itself.
    readonly property real panelContrastFloor: SurfaceContrast.requiredReferenceContrast(textColor, legibilityInk)
    readonly property var contrastLimits: SurfaceContrast.limits(textColor, panelContrastFloor)
    readonly property vector4d panelLimits: Qt.vector4d(contrastLimits[0], contrastLimits[1],
                                                       contrastLimits[2], contrastLimits[3])
    // A child control without text (Media's volume track) passes false: no darker panel, no
    // floor, so its material and backdrop read through.
    property bool legibilityPanel: true

    // Presentation constants per material (one shader, different uniforms):
    //   blurTint        = (blur level 0 light .. 1 heavy, tint opacity at theme alpha 0, at 1, saturation)
    //   lightNoise      = (luminosity pull toward the tint, grain, haze toward white, smoke darkening)
    //   glassLegibility = (edge highlight, refraction px, panel density relief, ink contrast floor)
    readonly property var parameters: ({
        "acrylic": [Qt.vector4d(1.0, legibilityPanel ? 0.294 : 0.336, legibilityPanel ? 0.49 : 0.56, 1.35), Qt.vector4d(legibilityPanel ? 0.21 : 0.24, 0.030, 0.0, 0.0),
                    Qt.vector4d(0.0, 0.0, 0.30, surface.panelContrastFloor)],
        "glass": [Qt.vector4d(0.0, 0.05, 0.28, 1.15), Qt.vector4d(0.0, 0.0, 0.0, 0.0),
                  Qt.vector4d(0.20, legibilityPanel ? 4.5 : 5.0, 0.20, surface.panelContrastFloor)],
        "frosted": [Qt.vector4d(1.0, legibilityPanel ? 0.16 : 0.20, legibilityPanel ? 0.336 : 0.42, 0.80), Qt.vector4d(0.0, 0.045, legibilityPanel ? 0.176 : 0.22, 0.0),
                    Qt.vector4d(0.05, 0.0, 0.20, surface.panelContrastFloor)],
        "mica": [Qt.vector4d(1.0, legibilityPanel ? 0.504 : 0.576, legibilityPanel ? 0.602 : 0.688, 0.70), Qt.vector4d(legibilityPanel ? 0.315 : 0.36, 0.0, 0.0, 0.0),
                 Qt.vector4d(0.0, 0.0, 0.30, surface.panelContrastFloor)],
        "smoked": [Qt.vector4d(0.45, legibilityPanel ? 0.245 : 0.28, legibilityPanel ? 0.406 : 0.464, 0.55), Qt.vector4d(0.0, 0.012, 0.0, legibilityPanel ? 0.315 : 0.36),
                   Qt.vector4d(0.06, 0.0, 0.30, surface.panelContrastFloor)]
    })
    readonly property var resolvedParameters: parameters[material] || parameters["acrylic"]

    // Dark ink (light themes): the panel's furthest lift toward its anchor, the card's
    // Settings-variant shell density (never less than the reference ink needs over black).
    // Every theme: the composed panel over a black and a white backdrop, against which each
    // text run corrects its own ink (OverlayCard.surfaceInkSolution). Style edges only.
    readonly property real panelCeiling: SurfaceContrast.panelCeiling(material, resolvedParameters,
                                                                      tintColor, contrastLimits, opacityAdjust)
    readonly property var inkPoles: SurfaceContrast.inkPoles(resolvedParameters, tintColor, contrastLimits,
                                                            panelCeiling, opacityAdjust)
    // underlay: the fill the run sits on inside the card (transparent: the panel itself).
    function legibleInk(color, opacity, small, underlay) {
        return SurfaceContrast.legibleInk(color, opacity, inkPoles, small, panelLimits.y > 0.5, underlay)
    }

    // Shader inputs (names match surface_material.frag's uniform block).
    readonly property var source: backdrop
    readonly property vector2d itemSize: Qt.vector2d(width, height)
    readonly property vector4d blurTint: resolvedParameters[0]
    readonly property vector4d lightNoise: resolvedParameters[1]
    readonly property vector4d glassLegibility: legibilityPanel ? resolvedParameters[2]
        : Qt.vector4d(resolvedParameters[2].x, resolvedParameters[2].y, 0.0, 1.0)

    blending: true
    vertexShader: "shaders/surface_material.vert.qsb"
    fragmentShader: "shaders/surface_material.frag.qsb"
}
