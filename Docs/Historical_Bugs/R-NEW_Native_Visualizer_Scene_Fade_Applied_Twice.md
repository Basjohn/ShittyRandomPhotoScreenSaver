# R-NEW | The native Visualizer's scene fade was applied by Qt's composite, not by its shader

**Status:** fixed and proved 21 Nov 2026 (OpenGL owner replay, rule (a)).

The Visualizer's scene fade (the owner's authored first-appearance fade times the startup reveal gate) reached the
content through Qt's opacity on the card's presentation root. The Python render node draws raw GL, so it folds Qt's
inherited opacity into the shader's `u_fade` and the framebuffer rounds once. The native item drew the same frame at
the card's content fade alone into its RGBA8 surface, and Qt's composite then multiplied that surface by the inherited
opacity: two roundings, and, for a shader that uses `u_fade` inside its colour mix (Bubble, Spectrum), a different
formula. Every reveal (the first ~0.3 s of each activation, and every startup reveal) drew natively up to 2 levels
off the Python renderer over the whole card. It was silent in the product and cost the long-take investigations: 20
of Spline Curve's 27 long-take failures (cold-start inputs 0-25, all takes) were this class.

The fix gives the scene opacity one way to the content on both paths. The card's chrome fades in two layers of the
presentation root (`VisualizerPresentation.qml`, `sceneOpacity`) and its shadow in the display's shadow lane; the
content host between them carries none. The scene hands the root's `sceneOpacity` to the Visualizer item
(`QuickSceneController._project_visualizer_scene_opacity`, `VisualizerRenderItem.set_scene_opacity`), and both the
Python node and the native route fold it into the drawn content fade through one function
(`render_contract.scene_faded_snapshot`). The Python path's pixels are bit-identical before and after (548 of 548
frames, chrome included); the native frames change only in the reveal (inputs 0-27).

Proof (nightsolong_acousticsoft1, 5.5 s, display placement): Spline Curve failed 20 inputs (0-25) before and passes
after (worst ties 7, the steady figure); the scene fade forced to 1 on both paths passes too. Not this class: Bubble's
input 22 (its two 2-level pixels are identical with the fade folded; the fade value itself, not where it is applied)
and Spectrum's mode-switch frames (a content fade, never a Qt opacity). Evidence:
`native_core/scene_fade/20261121_*`; guard: `tests/test_visualizer_scene_fade_once.py`.
