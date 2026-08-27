# 05 — CUSTOM Layout, Input, Interaction and Auxiliary Runtime Pixels

Status: **Phase-G destination contract; some geometry semantics already proven during F**  
Last updated: 2026-08-27

`Current_Plan.md` owns work admission.

## Preserve neutral CUSTOM data

Preserve/rehome screen signatures/aliases, normalize/denormalize, clamp/snap/gutters/grid, display ownership,
restore maps, Save/Cancel, slot persistence and family-specific size payload semantics. Move presentation/
session ownership away from QWidget edit shells.

## `CustomLayoutSession`

Working state per edited item includes widget/model identity, source/current display, geometry variant,
baseline/current global rect, baseline/current size payload, resize scale and working removed/enabled state.
Session does not require QWidget. Editing one variant does not silently mutate another.

## Geometry variants

Conceptually:

```text
read committed geometry(widget_id, display_identity, variant)
write committed geometry(widget_id, display_identity, variant, rect, size_payload)
```

Missing target variant may initialize via documented default. Committed variant restores exactly subject to
deterministic current-screen clamp. Never repeatedly derive one saved variant from another.

The variant-aware CUSTOM map is version 2. Version-1 single-entry geometry is invalidated; do not add replay,
conversion aliases or mode-to-mode reconstruction as a compatibility path.

### Clock digital / analogue

First missing target: keep current center intent -> obtain target natural size -> center -> clamp once ->
establish target baseline. Once both exist, A->B->A restores exact committed rects without drift. Moving/
resizing one changes that variant only; cross-display sets independent.

## Edit the real Quick presentation

Live retained item stays visible; one shared Quick edit overlay/handles layer sits above it; session geometry
temporarily overrides placement; model/provider may keep publishing; persistence unchanged until Save.
No screenshot shell, duplicate visual owner or second accelerated edit window.

## Edit-mode X — REQUIRED

Every adjustable edit-mode card gets X. Clicking changes **working session only**:

- duplicate -> remove that duplicate from working layout;
- singleton -> working ordinary enabled OFF, exactly as normal Settings checkbox;
- never family/capability deactivation;
- no immediate settings persistence;
- no committed provider/runtime destruction merely because preview disappeared.

Singleton closed then cancelled reappears exactly as before.

## Save / Cancel

Context-menu Save or Enter commits active geometry variant, final display, duplicate removals, ordinary
enabled changes from X, and canonical monitor/position settings where product semantics require.

Cancel restores active variant, duplicate set, ordinary enabled state and visualizer scale+viewport together
where applicable. Do not mutate inactive variants or replay destructive setters for never-committed state.

## Layout slots

`Shift+1` through `Shift+0` save slots; `1` through `0` load them. A slot is a source-free snapshot of the ordinary
visible layout, including committed geometry/size and ordinary ON/OFF state. Loading saved ordinary ON turns an
ordinarily-OFF widget ON only while its owning capability family and dependencies remain effective; loading saved
ordinary OFF turns an ordinarily-ON widget OFF.

Ordinary `enabled` is never authority to activate a fully deactivated family/capability. Slot replay leaves
family-activation, provider, account and source settings untouched. This is the same distinction used by edit-mode X:
singleton X changes working ordinary enabled state, never capability activation.

## Resize

Quick handles emit deltas; Python session/geometry math owns min size, aspect constraints, anchors, family
size payload, active variant and display/DPR projection. No QML-only persisted geometry.

Corner handles and wheel resize are shared retained Quick material. Family size payloads project onto the same
retained presentation models during preview; Cancel restores their baseline payload without item/model recreation.

Visualizer keeps `uniform_visual_scale` separate from `content_viewport_size`; never anisotropically stretch
finished pixels.

## Cross-monitor transfer

One live pixel owner: resolve target -> detach/retire source presentation -> target creates/adopts -> logical
runtime/model survives unless product semantics require otherwise -> target-local variant rect -> update
session display. No simultaneous source/target copies. Do not overwrite all target variants silently.

The retained move request includes both the proposed global rect and actual pointer position. Python routes those
through the canonical screen-choice threshold, clamp, snap-guide and monitor-route owner; QML does not choose a
screen or commit geometry. Shared session publication flips ordinary retained display-local visibility without
recreating those items.

Visualizer transfer preserves the same snapshot bridge and render identity, explicitly retires the source
window's render item/presentation root, creates the target-window item, and reprojects presentation DPR from the
target window. The shared Quick CUSTOM scene coordinator performs the same handoff when Cancel restores the source
display. A missing or already-occupied target is rejected before handoff and restores the prior working display,
monitor route and rect rather than leaving a partial transfer.

## Edit overlay pixels

One shared retained Quick overlay layer per display: grid, snap guides, selection outline, handles, widget
label/control chrome including X.

Centering guides use red so display/peer-centre alignment remains visually distinct from ordinary grid and edge
guides.

## Input / actions

Quick may own hit regions/pointer handlers and emit semantic actions. Python owns mode changes, provider
actions, persistence, CUSTOM session commands and context/global shortcuts. Enter=Save, Esc=Cancel. Clock
double-click mode toggle is semantic; QML writes neither Settings nor committed geometry.

G6 is closed. `QuickInputState` is projected from each generation-scoped input controller through its matching
scene and retained ordinary-widget host. The scene rejects mismatched screen/generation state and closed
admission; the host stores the latest accepted state so newly created retained family presenters receive the
same admission facts without item recreation. Interactive family models derive only bounded pointer admission
from those facts.

Retained QML hit regions emit semantic requests only. Clock mode changes, Media transport/seek/app-volume/
system-mute, Weather refresh/settings, Reddit URL/refresh, Gmail message/auth/actions and both Steam-family
refresh/settings paths terminate in Python presentation admission and the existing neutral runtime/settings/
provider owners. Unsupported capabilities remain inert, accepted runtime/provider state remains authoritative,
and every retained double-click hit region explicitly suppresses the global next-image fallback only while its
own action is admitted.

## Context menu / auxiliary pixels

A QWidget context menu may remain temporarily if decoupled from `DisplayWidget` and not a second runtime
presenter/lifecycle owner. If popup focus blocks, migrate once; no permanent dual menu implementations.

Halo/dimming/pixel shift are retained pixels/transforms in same Quick scene, not extra translucent top-level
windows.

## MC / focus gates

Stress two displays focus A->B->A, Ctrl interaction, context menu, Clock switching, media controls/seek/
volume, Gmail/Reddit interactions, halo/shadows, activation toggles, Settings/CUSTOM transition, cross-monitor
transfer and edit-mode X Save/Cancel. Do not reintroduce focus-driven shadow corruption.

## Suggested G boundaries

```text
G1 session + multi-variant/working-state contract
G2 Quick edit overlays + ordinary geometry + X
G3 Save/Cancel + exact variant/enabled/duplicate persistence
G4 resize semantics
G5 cross-monitor transfer
G6 runtime-neutral input/action routing
G7 context/halo/dimming/pixel-shift
G8 MC/focus closure
```
