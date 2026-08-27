# SRPSS Qt Quick Migration — Stand-Alone Reorientation

Date: 2026-08-28  
Source checkpoint reviewed: `59f4a3c98235215a9ff89fc09e4cc979d1831e89`

This is a current handoff, not a changelog. Read `Current_Plan.md` first; exact later source outranks this file.

## Where the migration actually is

Phase F is closed. G1–G6 are closed. G7 is at its tail: retained dimming/pixel shift, cursor halo and context menu are
already in the Quick scene. G8 remains after G7 closure.

A documentation/source audit exposed one earlier G4 omission that now takes priority over declaring G7/G complete:
**independent visualizer viewport-extent edge resizing was not landed.**

## First task — G4 correction

Use `Remaining_G4_Visualizer_Viewport_Resize_Decomposition.md` as the implementation playbook; the broader visualizer and
CUSTOM contracts remain authoritative for product behavior.

G4 currently provides retained wheel/corner **uniform whole-size scaling**. The destination contract also requires:

```text
left/right edge -> viewport extent width only
top/bottom edge -> viewport extent height only
```

This is not texture stretching. Scale remains constant while the visualizer's world/playroom/aspect changes.

It applies to **all five modes**:

```text
Spectrum
Oscilloscope
Sine
Bubble
DevCurve
```

Do not preserve the current Bubble `viewport_resize_capable=False` as product intent. It is unfinished migration gating.
Bubble is an especially important consumer of the feature: update its spatial viewport configuration so wide/tall domains
remain physically coherent while circles remain circles and radii/velocity/collision/trail/transient behavior plus BTF
remain intact. Geometry updates are configuration, never a new clock.

Required persistence semantics: uniform scale and viewport extent are distinct values through live edit, Save/Cancel,
geometry variants, layout slots and cross-display/DPR projection.

## Then finish G7

Use `Remaining_G7_G8_Auxiliary_Focus_Decomposition.md` for G7 caller retirement and the subsequent G8 matrix.

Already landed:

- `QuickAuxiliaryController`/retained state for dimming + shared pixel shift;
- retained cursor halo;
- retained Quick context-menu model/QML and semantic action admission.

Finish exact caller proof and remove superseded QWidget/top-level auxiliary pixels/helpers where no neutral responsibility
remains. Python remains command/settings/business authority. No dual presentation for temporary continuity.

## G8

Perform the focused MC/focus closure across two displays, Ctrl/interaction, retained context menu/halo, family hit regions,
Settings/CUSTOM transitions, cross-monitor movement, Save/Cancel/X and both visualizer resize operations.

## H is smaller than old docs made it sound

Use `Remaining_H_Production_Cutover_Decomposition.md` for the exact owner-wiring/deletion order.

The old planning assumption that the application had to remain fully functional throughout migration is no longer valid.
The source may still route startup through `DisplayWidget`, but the half-migrated old runtime does not need to work.

Do not spend work preserving/reconstructing legacy presentation for an atomic handoff.

H is:

```text
DisplayManager / engine production route
-> QuickDisplayRuntime per selected display
-> one display-owned WidgetRuntimeManager
-> canonical capability + ordinary-instance admission
-> existing neutral services/models
-> QuickSceneController retained scene
```

Prove sole ownership/cardinality/lifecycle, then delete the remaining `DisplayWidget`/QRhi/GLCompositor physical-host
path and fallback policy. No product switch back.

Comprehensive installed/physical proof is J, not a reason to make H emulate a seamless legacy handover.

## I / J

I is residue only.

J owns compiled/installed real-hardware closure: 1/2/N display, mixed refresh/DPR, topology/off-wake, full widget and
Visualizer eyes-on parity, physical continuity/tail metrics, clean shutdown and final doc/test-ledger closure.

## Binding architecture

```text
one selected physical display
-> one QuickDisplayRuntime
-> one standalone threaded QQuickWindow
-> one retained Quick scene
-> inline QSGRenderNode custom GL where needed
```

Never introduce `QQuickWidget`, second accelerated presentation surfaces, permanent old/software fallback, provider waits
for paint, or a second visualizer clock.

## Important state semantics

Ordinary ON/OFF is not family/capability activation.

- CUSTOM singleton X -> ordinary OFF only;
- layout slots save/load ordinary ON/OFF plus geometry/size;
- loading a slot may turn an effective widget ordinarily ON/OFF;
- a fully deactivated family stays deactivated;
- provider/account/source settings are not layout-slot state.

Clock geometry remains variant-aware by `(widget_id, display_identity, geometry_variant)`.

## Working method

Use exact current source before acting. `Current_Plan.md` owns sequence. Focused test -> diff/status -> commit/push ->
post-push self-audit. Use external audit for architecture/lifecycle/shared-owner changes or unresolved evidence conflicts.
Do not add hosted CI unless explicitly requested and do not routinely full-build during implementation migration.

Historical plans/bugs/performance evidence are evidence only. Do not modernize them into current instructions and do not
let old “keep legacy app functional” wording override the current migration policy.
