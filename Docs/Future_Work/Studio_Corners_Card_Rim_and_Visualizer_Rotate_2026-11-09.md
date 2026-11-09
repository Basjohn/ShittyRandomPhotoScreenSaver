# SRPSS | Studio corners, card material rim and Visualizer hover rotation

**Status:** new operator-reported repairs, source audited 9 November 2026 at `main` `9872ca18140c490ed018c42511803005fb3d8ed4`. **Admission:** operator-reported defects above noncritical polish, separate reversible checkpoints. **Contract owners:** `Current_Plan.md` §1A, `Docs/Architecture/Card_Surface_Materials.md`, `Docs/Architecture/Settings_Theme_Architecture.md`, `Docs/Reference/Visualizer_Studio.md`, `Docs/Future_Work/Expanded_Visualizer/01_Expanded_Visualizer_Implementation_Plan.md`.

These are three distinct tasks; no blanket geometry refactor, no material-density retuning, and no reimplementation of existing gesture/painting owners.

## UI-1. Studio exterior rounded corners: match the *visible* Settings dialogue improvement

**Operator report:** Studio's outer corners need the same visible improvement recently given to Settings.

**Important current-source finding:** `ui/studio/chrome.py::StudioWindowEdge` already calls `ui.settings_window_edge.paint_forged_window_edge`; `ui/studio/qml/StudioShell.qml` already places that item at `z:1000` and passes an outer border and forged edge colour. Therefore **do not create a second corner renderer or mark this fixed because the helper is already shared**. The remaining failure may involve actual native window material bleeding, Studio's edge colours/placement, DPR, or the distinction between decorative forged pixels and the rectangular native HWND. The Settings plan's item 1.9 still records **unresolved native Accent rounded silhouette clipping**; it must not be falsely marked resolved because its forged border looks rounded.

- [ ] Reproduce at the same normal/maximised state, DPI and dark/light theme on Settings and Studio, with normal opaque and active Glass/Acrylic material. Compare all four extreme corner pixels, the adjacent border, corner fill and actual desktop outside the window.
- [ ] Trace `StudioWindowEdge` size, QQuick-painted cached texture, `forgedEdge` token, `outerBorder`, shell titlebar/body composition, QML stacking, native window surface and resize hit zones. Confirm exactly whether the visual gap is the forged exterior or native backdrop beyond the silhouette.
- [ ] Reuse the **one** Settings painter/edge contract and the already established native composition owner. If the actual Windows rounded-material clipping still fails, keep that defect open alongside Settings 1.9 rather than covering it with increasingly opaque decorative caps. Avoid region tricks proven to break Accent/DWM.
- [ ] Prove physical Settings/Studio corner parity at 100% and 150% DPI, on both operator wallpapers and dark/light themes, resizing and maximise/restore, with no border gaps, square bleed, damaged shadows, mouse hit regressions or destruction leaks. Separate Qt hidden-render evidence from actual HWND/DWM evidence. Studio's native compositor may require a separate acceptance screenshot.

**Exit:** visible Studio outer corners match the Settings dialogue's *accepted appearance*, with any broader native material clipping failure explicitly documented rather than hidden.

## UI-2. Eliminate the bright inset **material rim** on widget cards

**Operator report:** a bright band/gap is visible between the main material-covered card interior and its border. The material itself is now visually appealing and should fill the entire available card face up to the inside of its existing border. Target **zero additional panel inset/rim**. This is NOT a request to remove content padding, widen the card, remove the border, or change position/layout.

**Verified owner:** `rendering/quick/qml/shaders/surface_material.frag`, shared `SURFACE` implementation duplicated identically in `text_legibility.frag` and `text_legibility.vert`; `MaterialSurface.qml` passes the current controls. Current shader:

```glsl
float plateInset = borderWidth < 0.0 ? -1.0 : borderWidth + (glassLegibility.y > 0.0 ? 3.0 : 2.5);
```

The extra 2.5 px (Glass 3 px), plus its soft step, produces the deliberately designed inner rim in `Card_Surface_Materials.md` §3.3. That historical preference has now been superseded by this operator request. `contentInset`/`OverlayCard.padding` governs family layout and **must remain unchanged**. The actual card border, configured radius, shadow and clipping remain.

- [ ] Update the **one semantic panel extent calculation** so the material panel reaches the inside of the existing border, with zero extra rim. Respect physical border width and concentric radius; constrain any feathering/soft edge to the border-covered region instead of visibly recreating a bright 2 px strip.
- [ ] Apply identical shared-`SURFACE` changes to all maintained fragment/vertex shader copies. Keep the shader source-contract parity test. Do not fix only `OverlayCard.qml` or only the Visualizer's material Loader. Card families and applicable Visualizer cards use the shared material path.
- [ ] Preserve child controls with a deliberate negative-border sentinel (they already draw panel across their face), and preserve `legibilityPanel: false` on textless controls. Maintain standalone Widget Theme surfaces, inheritance and Opacity Adjust authority.
- [ ] Keep **material density, tint/transparency, refraction, blur, backdrop refresh, text colours, shadows, outlines, animations, and ordinary Normal cards unchanged**. No new plate, extra contrast system, background readback, per-frame property evaluation, extra target or additional material layer. Card material is not to be made more opaque to compensate.
- [ ] Before/after compare representative Clock, Weather, Media incl. transport and volume, Gmail, Reddit, Feeds, System Stats, achievement cards and applicable Visualizer cards on dark/light Glass/Frosted/Acrylic/Mica/Smoked; test non-default border widths and tight/small-radius cards. Check precisely the band inside the border at device pixels and regular card content extent, border and shadow positions. Update any old pixel tests measuring the previously authored intentional rim, but never bless broken content/contrast by changing thresholds without evidence.
- [ ] Retain current legibility-ink fallback: authored light-on-dark text stays bright if conflicting hypothetical surfaces make contrast impossible; do not let this item reopen the theme opacity/density work. In particular no speculative 'fix the card surface to improve text' adjustment.

**Exit:** uninterrupted material surface to the inside edge of the card border, without changed widget sizing, content alignment, transparency or animation cost. Update `Card_Surface_Materials.md` §3.3 to retire the old 2.5/3 px inner-panel requirement **in the same checkpoint**.

## UI-3. Rotate glyph on Visualizer hover, not Edit-only

**Operator report:** mode orientation/Rotate works in Studio and in Edit, but the normal hovered Visualizer card does not offer its rotate glyph.

**Verified owner:** `rendering/quick/qml/VisualizerPresentation.qml` defines `visualizerHoverGlyphLoader` and constructs the common `WidgetHoverEditGlyphs` with `canRotate: false` (lines ~686–708). `CustomLayoutOverlay.qml` separately offers `rotateContentControl` in Edit. `ui/studio/controller.py` has its own preview rotate control. `engine/display_manager.py::_route_hover_edit_glyph` already supports action `rotate`, validates `content_rotation_capable`, resolves the real CUSTOM session and calls `model.rotateContent(row)`. This is an admission/presentation gap, not a missing rotation engine.

- [ ] Offer a **visible hover Rotate Widget Content glyph** on the ordinary Visualizer card in the existing Interaction/Ctrl and allowed-gesture flow, when the mode's `content_rotation_capable` says yes (Sphere remains ineligible). Do not hardcode `canRotate: true` for unsupported modes; project from existing capability/owner.
- [ ] The glyph belongs on the *existing* lower-right Visualizer glyph row with the preset, Reset Camera and expand controls, preserving spacing/fit and a singular rotate action. Do not introduce duplicate overlapping hover/Edit glyphs or disturb Reset Camera/preset availability. The existing common hover glyph module may be reused only with correct placement/admission for the Visualizer's bespoke row.
- [ ] Route action through the existing `DisplayManager`/CUSTOM `rotateContent` authority. Preserve saved per-mode orientation, undo/Save/Cancel and source generation. A hover click may enter the established Edit transaction as the existing hover actions do; it must not mutate stored layout from a second, unaudited action path.
- [ ] **Expanded Visualizer:** current ordinary hover Loader is explicitly disabled when `expandedDisplay`. Offer a matching capability-driven hover rotation path on expanded-capable modes only through the existing **Fullscreen Edit** owner, not by resurrecting the ordinary CUSTOM owner while display takeover is active. Test expanded semantics separately; do not silently claim ordinary hover solves expanded hover.
- [ ] Regression proof: ordinary 2D framed and 3D framed modes, rotate twice/4×, currently active preset/custom, size/orientation round trip, unsupported Sphere, Fullscreen Edit versus ordinary Edit, hover/leave/double-click/admission, inactive widget, small-card glyph fit, no second route/mode switch, and interaction with expansion/camera reset. No polling/timers or additional GL work.

**Exit:** the actual hovered Visualizer offers rotation in both its ordinary and, where applicable, expanded presentation; only eligible modes act, and Edit/Studio behaviour stays intact. Update `Visualizer_Reference.md` and Expanded Visualizer plan affordance notes once the live look passes.

## Source/code change discipline

Separate UI-1, UI-2 and UI-3 checkpoints so a visual regression can be isolated. Keep all code edits inside their proven owners; use whole files, not patches, and no GitHub Actions/product build or game60 load without explicit operator instruction. In each closeout update `Current_Plan.md` §1A with a source/test gate and a *separate* physical visual acceptance checkbox. Do not let a test pass erase the operator's unresolved observation.
