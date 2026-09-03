# Rejected Qt Quick Runtime Card-Material Experiments — 2026-09-02

## Decision

Runtime Widget cards are ordinary semantic RGBA Qt Quick surfaces. The attempted
Glass/Acrylic backdrop-material feature is **rejected/shelved** and has been removed
from Widget Theme schema, persistence, Settings controls, retained runtime
composition and transition pacing.

This decision does **not** apply to the Settings GUI. Settings-window Glass/Acrylic
is a separate accepted QWidget/native-HWND backdrop system.

Do not build a custom compositor solely to restore card cosmetics. A future shared
compositor/material architecture may revisit backdrop cards only if that architecture
is independently justified by broader renderer/performance work and the card effect
can piggyback without compromising transition/Visualizer ownership.

## Failed-method ledger

### v0 — implicit mask-child admission

The shared material Loader inferred demand from
`ordinaryCardMaterialMaskHost.children.length > 0`. Python-created/reparented QML
mask children made Loader admission depend on an implicit scene-graph side effect.
Normal/Glass/Acrylic were physically indistinguishable.

### v1 — explicit retained consumer admission

Admission was hardened to an explicit event-driven retained consumer count. This
proved the old child-list contract was fragile, but physical pixels were still
indistinguishable. Admission alone was not the rendering failure.

### v2 — lexical bindings + explicit shared captures

Python/dynamic-QML `var` and `Loader.onLoaded` source/mask handoff was removed.
Backdrop source and mask became lexical QML bindings and the shared mask capture was
explicit. Runtime diagnostics proved mode, consumer count, Loader admission/load,
source binding, mask binding, captures and blur visibility were all active; pixels
still lacked a convincing material effect. The failure was downstream of admission.

### Diagnostic assumption withdrawn

A working capture was incorrectly expected to make the custom background
`QSGRenderNode` render count roughly double. Qt may redirect an ancestor subtree into
an offscreen target instead of drawing the node once for the window and again for a
texture. Render-count doubling is not a valid proof of capture success.

### v3 — layer the displayed background and feed MultiEffect directly

The actual displayed background host became the one layer-backed texture source,
removing the redundant background `ShaderEffectSource`. This finally produced a
small visible card-material difference, proving composition could affect pixels.
However it catastrophically broke the background architecture: the base wallpaper
and authored transitions became visually frozen while transition/performance counters
continued and the Visualizer remained live. The custom background render node was
cached by the layer.

### v3.1 — dirty the layered custom source from the existing transition pacer

The existing transition pacer was reused to call `BackgroundRenderItem.update()`
while a special material was active; no second timer/cadence owner was introduced.
The card effect became stronger, but the background/transition architecture remained
visually dead. This falsified the layered-background route for the current renderer.

## Rollback contract

The healthy destination is:

```text
BackgroundRenderItem directly parented to DisplayScene root
-> ordinary authored background + transition renderer
-> ordinary widget/card RGBA surfaces
-> Visualizer and Context Menu retain their existing independent presentation paths
```

Forbidden material debris after rollback:

- `CardMaterialBackdrop.qml`;
- `OverlayCardMaterialMask.qml`;
- `cardMaterial*` / `card_material_*` runtime state;
- background layer/capture admission for card materials;
- material mask hosts/consumer counts;
- material-specific transition-pacer callbacks;
- `Surface Style` control;
- Widget Theme `default_card_material_mode` or persisted `card_material_override`;
- material suffixes in Widget-theme catalogue display names or Widget-theme filenames.

`tests/test_widget_theme_no_material_contract.py` is the permanent source guard.
