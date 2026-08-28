# 05 — CUSTOM Layout, Input, Interaction and Auxiliary Runtime Pixels

Status: **G1–G6 closed; G4 core landed with bounded audit corrections priority; G7 near closure; G8 pending**  
Last updated: 2026-08-29

`Current_Plan.md` owns work admission.

## Neutral CUSTOM authority

`CustomLayoutSession` is presentation-neutral. Working state retains exact item/model identity, source/current display,
geometry variant, baseline/current global rect, baseline/current family size payload, resize state and working removed/
ordinary-enabled state. Session semantics do not depend on QWidget.

Preserve screen signatures/aliases, normalize/denormalize, clamp/snap/gutters/grid, display ownership, restore maps,
Save/Cancel, layout slots and family-specific size payload semantics.

## Geometry variants

```text
read committed geometry(widget_id, display_identity, variant)
write committed geometry(widget_id, display_identity, variant, rect, size_payload)
```

The variant-aware CUSTOM map is version 2. Version-1 single-entry geometry is invalidated; do not add compatibility
replay or reconstruct one mode from another.

Clock digital/analogue: first missing target may initialize once from current center intent + target natural size +
clamp. Once committed, A->B->A restores exact independent rects without drift. Cross-display sets remain independent.

## Edit real retained presentation

The live retained item remains the presentation. One shared Quick edit overlay/handles layer sits above it and session
geometry temporarily overrides placement. Provider/model state may keep publishing. No screenshot shell, duplicate
visual owner or second accelerated edit window.

## Edit-mode X

Every adjustable edit card gets X. It changes **working session only**:

- duplicate -> remove that duplicate from working layout;
- singleton -> ordinary widget OFF, exactly as its normal Settings checkbox;
- never family/capability deactivation;
- no immediate settings persistence;
- no committed provider/runtime destruction merely because preview disappears.

Cancel restores it exactly.

## Save / Cancel

Save/Enter commits active geometry variant, final display, family size payload, duplicate removals, ordinary enabled
changes and canonical monitor/position settings where product semantics require.

Cancel restores active variant, duplicate set, ordinary enabled state and all family size payload dimensions. Do not
mutate inactive variants or replay destructive setters for never-committed state.

## Layout slots

`Shift+1` through `Shift+0` save slots; `1` through `0` load them. A slot is a source-free ordinary visible-layout
snapshot including committed geometry/size and ordinary ON/OFF state.

Loading saved ordinary ON turns an ordinarily-OFF widget ON only while its capability family/dependencies remain
effective. Loading saved ordinary OFF turns an ordinarily-ON widget OFF. Slot replay never activates a deactivated
family/capability and never overwrites provider/account/source configuration.

## Resize — two distinct visualizer operations

Ordinary family resize and visualizer whole-size resize remain Python/session-owned. QML handles emit semantic deltas;
Python owns minimums, anchors, family payloads, active variant, display/DPR projection and persistence.

### Uniform whole-size resize — LANDED G4

```text
wheel
corner handles
    -> uniform_visual_scale / family uniform size semantics
```

Visualizer final pixels remain uniformly scaled and the committed viewport extent is unchanged.

### Visualizer viewport-extent resize — CORE LANDED; POST-CHECKPOINT CORRECTIONS OPEN

The retained **edge** operation is landed:

```text
left/right edge -> viewport extent width only
top/bottom edge -> viewport extent height only
```

This changes world/layout playroom and current aspect while keeping `uniform_visual_scale` constant. It is not X/Y
stretch of a rendered image.

All five current modes participate: Spectrum, Oscilloscope, Sine, Bubble and DevCurve. The core Bubble logical reflow and
all-five-mode capability policy are landed; do not reintroduce a false gate as a workaround.

Bubble receives viewport bounds as spatial configuration, preserving circles/radii/velocity units, trajectories/collisions,
trails/transients and BTF. Pointer/render cadence may not become simulation cadence.

Save/Cancel, committed CUSTOM geometry and layout slots round-trip `uniform_visual_scale` and viewport extent as separate
values. Corner/wheel operations may not silently rewrite extent; edge operations may not silently rewrite scale. In
addition, viewport configuration has explicit precedence: ordinary committed extent remains truth outside CUSTOM; an active
working extent is a temporary override. Save commits the new extent, Cancel restores the pre-edit committed extent, and
ending CUSTOM removes only the override.

The durable scale/extent architecture is decomposed in `Remaining_G4_Visualizer_Viewport_Resize_Decomposition.md`. The
current bounded corrections are owned by `G4_Post_Checkpoint_Audit_Corrections_Decomposition.md`.

## Cross-monitor transfer — CLOSED G5

One live pixel owner: resolve target -> detach source presentation -> target adopts/reprojects -> logical runtime/model
survives -> target-local active-variant rect -> session display update. No simultaneous source/target copies and no
silent overwrite of unrelated target variants.

Retained move requests include proposed global rect and actual pointer position. Python owns screen-choice threshold,
clamp, snap guides and monitor route. Visualizer transfer preserves snapshot bridge/logical render identity while the
source window render item retires and target-window item is created with target DPR.

## Input / semantic actions — CLOSED G6

Generation-scoped `QuickInputState` is projected through the matching scene and retained ordinary-widget host. Scene
rejects mismatched screen/generation state and closed admission. Interactive family QML emits semantic requests only;
Python owns mode/provider/settings/actions and accepted runtime state remains authoritative.

Clock mode, Media transport/seek/volume/mute, Weather, Reddit, Gmail and Steam-family actions route through existing
Python owners. Unsupported capabilities remain inert. A retained double-click suppresses global next-image fallback
only while its own action is admitted.

## G7 retained context / auxiliary state

Landed destination presentation:

- dimming is one retained same-scene overlay;
- pixel shift is one retained shared scene transform/cadence owner;
- cursor halo is retained same-scene presentation driven by generation-scoped input state and inactivity;
- context menu is a retained Quick model/QML surface with Python semantic command authority.

No auxiliary feature gets a second translucent top-level accelerated window. A QWidget context menu is no longer a
destination option; any remaining old context/halo/pixel-shift QWidget owner is caller-proof migration debris.

G7 closure is exact caller audit + retirement of superseded legacy auxiliary pixels/helpers + focused same-window,
generation and focus proof. Do not keep dual implementations for temporary product continuity. Follow
`Remaining_G7_G8_Auxiliary_Focus_Decomposition.md` for the caller classification and focus/input closure sequence.

## Edit overlay pixels

One shared retained Quick overlay layer per display owns grid, snap guides, selection outline, handles and widget
label/control chrome including X. Centering guides are red so display/peer-centre alignment is distinct from ordinary
grid/edge guides.

## G8 MC / focus gates

Stress two displays focus A->B->A, Ctrl/interaction, retained context menu, Clock switching, Media controls/seek/volume,
Gmail/Reddit interactions, halo/shadows, activation toggles, Settings/CUSTOM transition, cross-monitor transfer,
visualizer uniform+viewport resize and edit-mode X Save/Cancel. Do not reintroduce focus-driven shadow corruption.

## Phase summary

```text
G1 session + multi-variant/working-state contract                   CLOSED
G2 Quick edit overlays + ordinary geometry + X                    CLOSED
G3 Save/Cancel + exact variant/enabled/duplicate persistence      CLOSED
G4 core uniform + independent viewport extent                   LANDED
G4 post-checkpoint ownership/spatial corrections                  REQUIRED FIRST
G5 cross-monitor transfer                                         CLOSED
G6 runtime-neutral input/action routing                           CLOSED
G7 context/halo/dimming/pixel-shift                               NEAR CLOSURE
G8 MC/focus closure                                               PENDING
```
