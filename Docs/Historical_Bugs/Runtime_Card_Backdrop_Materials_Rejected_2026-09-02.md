# Runtime Card Backdrop Materials Rejected — 2026-09-02

Status: **REJECTED / ANTI-RESURRECTION GUARD**  
Scope: ordinary Qt Quick runtime widget cards and Context Menu only.  
Does not apply to: Settings-window Glass/Acrylic, which remains accepted QWidget/HWND theme architecture.

## Incident

A J+ experiment attempted to give retained Qt Quick runtime cards Normal / Glass / Acrylic backdrop materials while preserving zero extra cost for Normal and modest shared cost for special cards.

Multiple implementations could make parts of the proposed pipeline technically active, but none delivered an acceptable product result within the existing renderer architecture. The final layer-backed approaches produced a modest visible card effect only by interfering with the custom background/transition render path: wallpaper/transition pixels became visually frozen even while transition and performance counters continued to advance and the Visualizer remained live.

The user explicitly rejected escalating to a custom compositor solely to recover decorative card backdrops. The value of the feature did not justify creating or destabilizing a broader presentation architecture.

## Binding lesson

Runtime cards stay on the ordinary retained RGBA surface/border/shadow path. Do **not** reintroduce any of the following as a hidden or disabled feature scaffold:

- Surface Style / Theme Default / Normal / Glass / Acrylic runtime UI;
- Widget Theme material recommendation or persisted material override;
- card-material enum/state in retained presentation owners;
- per-card or shared backdrop `ShaderEffectSource` capture;
- layer-backed wallpaper/background source solely for cards;
- material mask host/tree/consumer counts;
- material-specific transition-pacer or frame callbacks;
- a custom compositor whose only product justification is card cosmetics.

A future renderer architecture may revisit backdrop cards only if the renderer change is **independently justified by broader product/performance architecture** and card materials can piggyback without adding a second presentation/cadence owner or weakening wallpaper transitions, Visualizer freshness/reactivity, CUSTOM geometry, mixed-DPR behavior, or Normal-path cost.

## Evidence / failed methods

The full v0 -> v3.1 method ledger, including the withdrawn render-count diagnostic assumption, lives in:

`Docs/QtQuick_Migration/Rejected_Card_Material_Experiments_2026-09-02.md`

The permanent current-source source guard is:

`tests/test_widget_theme_no_material_contract.py`

## Healthy destination

```text
BackgroundRenderItem directly composited by the retained display scene
-> authored wallpaper / transition presentation
-> ordinary semantic RGBA widget cards
-> Visualizer / Context Menu retain their accepted Quick presentation owners
```

Settings Glass/Acrylic is intentionally separate and must not be used as precedent for Quick runtime backdrop capture.
