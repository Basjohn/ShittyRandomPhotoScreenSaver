# SRPSS Index

Last updated: 2026-08-24

Navigation and architecture-epoch routing.

## Authority chain

```text
current user instruction + exact current main
        ↓
Current_Plan.md
        ↓
Spec.md + Docs/Guardrails.md + focused current docs
        ↓
current evidence
        ↓
phase reports / Historical_Bugs
        ↓
Future_Cleanup.md
        ↓
Future_Work.md
```

`Current_Plan.md` owns current sequence/work admission. Historical plans/reports are evidence/rationale,
not current status authority.

`Docs/TestSuite.md` is the canonical live test inventory/retirement ledger. `Docs/Harness_Index.md`
routes recurring runtime/physical harnesses.

## Current migration status

Current normal implementation work is **Phase F0.5 — Widgets → General canonical shadow controls before retained family ports**.

- Phase C transition implementation: closed; remaining physical acceptance explicit.
- Phase D visualizer implementation: closed; remaining physical acceptance explicit.
- E2 capability/SETUP: closed.
- E2.7 Visualizer CUSTOM failover/reclaim: independently GREEN.
- E1 presentation-neutral runtime/model/provider ownership: independently GREEN / closed @ `4466c306`.
- E3 retained ordinary-widget host + shell primitives: independently GREEN / closed @ `1f25a791`.
- **E4 is independently GREEN / CLOSED at `3a562632`; Phase E is CLOSED.**
- **Phase F is active: F0 deletion is source-audited GREEN from `19460a7` and this reconciliation removes its final stale scraping dependency pins; F0.5 completes Widgets → General shadow controls; F1 Clock follows after audit.**

## Start here

| Task | Read |
| --- | --- |
| Active migration work | `Current_Plan.md` |
| Qt Quick technical index | `Docs/QtQuick_Migration/README.md` |
| Accepted runtime presentation architecture | `Docs/Compositor_Architecture.md` |
| Ownership map | `Docs/Contracts.md` |
| Cross-cutting safety | `Docs/Guardrails.md` |
| Stable architecture | `Spec.md` |
| Capability activation / SETUP | `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md` |
| Widget runtime ownership/threading | `Docs/10_WIDGET_GUIDELINES.md`, `Docs/QtQuick_Migration/08_Widget_Runtime_Ownership_Threading.md` |
| Widget retained shell + shadows | `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md` |
| Widgets → General shadow controls / direction + tuning | `Docs/Custom_Style_Implementation.md` |
| Widget state/models/actions/assets | `Docs/QtQuick_Migration/09_Widget_Quick_Presentation_Bridge.md` |
| Detailed family ports / Clock | `Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md` |
| CUSTOM/input/geometry variants | `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md` |
| Transitions | `Docs/Transition_Change_Checklist.md`, `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md` |
| Visualizer presentation/cadence | `Docs/Guardrails/Visualizer_Presentation.md` |
| Bubble temporal fidelity | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| Visualizer subsystem | `Docs/Visualizer_Reference.md`, `Docs/QtQuick_Migration/03_Visualizer.md` |
| Defaults/settings schema | `Docs/Defaults_Guide.md` |
| Tests / retirement | `Docs/TestSuite.md` |
| Recurring harnesses | `Docs/Harness_Index.md` |
| Deferred cleanup | `Future_Cleanup.md` |
| Deferred feature/experiments | `Future_Work.md` when explicitly admitted |

Do not read every document by default.

## Accepted presentation destination

```text
one physical display
        ↓
one standalone top-level QQuickWindow
        ↓
threaded Qt Quick scene graph
        ↓
base image + transitions + visualizer + retained runtime widgets
        ↓
OS presentation
```

No `QQuickWidget`, no second accelerated widget surface, no permanent fallback presenter.

## Current ordinary-widget direction

```text
presentation-neutral runtime/model owner
        ↓
stable presentation model
        ↓
per-display retained ordinaryWidgetHost
        ↓
OverlayWidget + OverlayCard + family content
```

E3 proved this substrate. E4 supplied one canonical shadow direction and normalized the retained
shadow primitives. Phase F then ports families.

## Global shadow controls

One canonical token:

```text
NW N NE W E SW S SE
```

Default `SE`.

Direction changes signs/axis only; card/text/header class baselines remain authored values. F0.5 adds
user-level Widget/Card Darkness + Blur + Extra Offset and Text Darkness + Extra Offset in the same
General → Appearance bucket. Extra Offset is additive before direction resolution. Text has no Blur.

Card `RectangularShadow` is cached by default for static ordinary cards.

Do not resurrect retired Intense-shadow modes and do not repurpose legacy `widgets.shadows.offset` as a
new magnitude authority. The General saver must preserve the complete `widgets.shadows` mapping.

Quick family ports must also discard QWidget-era effect-carrier/dummy and staged shadow-fade
workarounds. Whole-widget fade is the outer retained root opacity; card/text shadow alpha remains style,
not another fade timeline. Intermediate Items need a real composition responsibility.

## Clock migration direction

Clock is the first retained Phase-F family after F0 and the F0.5 canonical shadow-controls Settings slice.

Its Quick port intentionally includes:

- 2 logical px separator;
- roughly 40% wider separator (~0.77 inner-width ratio);
- symmetric gap above/below separator;
- separator in analogue mode as well when selected;
- day/date text shadow matching timezone ordinary-text shadow semantics;
- digital/analogue as separate geometry variants so repeated live switches restore exact saved sizes/
  positions rather than recursively deriving and drifting.

Final CUSTOM variant persistence belongs to Phase G.

## Current-legacy warning

Before H/I cutover/deletion, source may still contain:

- `DisplayWidget`;
- QRhiWidget / `GLCompositorWidget`;
- QWidget runtime widget presentation;
- painter/QPixmap shadow implementations.

These are migration source/reference only. Do not use them as permission to add new old-presentation
machinery.

## Migration execution

Normal:

```text
focused gate
-> diff/status
-> commit
-> push
```

Audit-required adds:

```text
-> independent review of actual pushed source
```

Repository connectors are read/audit only for normal SRPSS work.

## Historical navigation

Historical records may contain old owner maps and old phase status. Use them for mechanism/evidence
only, never to override current source + `Current_Plan.md`.
