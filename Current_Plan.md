# Current Plan — Active Work

Last updated: 2026-09-18

The Qt Quick runtime is operator-accepted. This file contains **active work only**; completed cutover work, accepted feature closeouts (Steam Friend Pulse, System Stats, Settings slider crash hardening, Friend Pulse shadow/artwork polish), Sphere polish, widget resize/Edit lifetime and bucket normalization are intentionally absent — their durable contracts live in the family Reference docs.

---

## Accepted baseline context — CHK26 GOLDEN

Production performance/freshness authority is **CHK26 / repository commit `a0bf70932c`**. CHK23 is the immediately prior GOLDEN rollback/bisect landmark; CHK15 / `0abc479c52` is the older pre-retained-background baseline. The generic headroom campaign is closed and performance work is symptom-driven. CHK27-CHK29 retained useful bounded `--frame-trace` attribution and closed scheduler/Bubble false trails rather than superseding CHK26. Full evidence and rejected methods live in `Docs/Historical_Bugs/R-87_QtQuick_HighRefresh_Freshness_And_Scheduler_Regression.md`.

Bubble remains the strongest protected reaction canary. Any future production change touching its timing/simulation/payload/reactive delivery requires active-music physical acceptance; idle-only evidence is insufficient.

## 1. Documentation / ownership hygiene — perpetual maintenance

- [~] Keep shrinking live docs toward present owners: current contracts/guides/reference for what is true now; `Docs/Historical_Bugs/` for durable regression archaeology; source control for ordinary chronology.
- [~] Keep code comments/docstrings aligned with current ownership and remove phase/cutover breadcrumbs that imply retired migration docs remain authority.

## 2. Up-and-coming feature work

Accepted next builds, with the first slice now in validation. The full decomposition stays in the linked doc; do not
duplicate that spec here.

- [x] **CUSTOM Visualizer quarter-turn orientation — operator validated 2026-09-18.** The shared logical
  viewport/presentation transform, per-canonical-mode sparse persistence, Sphere exclusion, Save/Cancel/layout-slot
  ownership and bottom-right Edit glyph are accepted in installed physical use. Keep the existing implementation and
  its performance guardrails; reopen only for a reproduced regression. The proposed live-hover rotate affordance is
  intentionally **not admitted** because it would require a new live persistence/action authority for convenience.
- [~] **CUSTOM editable child geometry — active after validated content-extent rollout.** Add one shared role-based edit
  primitive for a deliberately small set of major visual children, not arbitrary QML elements. CUSTOM becomes
  the sole active size authority for an overridden child while its authored Settings value remains preserved
  underneath; normalize/reuse the existing **“Disable Custom To Adjust!”** disabled-settings treatment wherever
  those authorities would otherwise fight. Initial candidates are Media artwork + seek/volume bars + one grouped playback-controls role, Steam artwork, Achievement Pulse artwork + badge + progress circle,
  Friend Pulse's grouped avatar role, optional Weather hero icon, and Clock **analogue-only** grouped separator /
  Roman-numeral roles. The first shared foundation is now in-tree: parent selection is transient state owned by the
  global CUSTOM session, so only one parent across displays can expose focused edit chrome/child handles. Parent
  selection in global Edit mode reveals the smaller child-role handles for only that widget; do not carpet the whole
  scene with child handles. Selection-driven controls may use a short event-triggered QML opacity animation; no timer,
  polling or idle hover scan is admitted.
  Existing white square corners/wheel retain uniform whole-widget scaling. The first foundation also implements a
  distinct lighter-blue diagonal corner affordance that reflows both admitted `content_extent` axes together through
  the same Python owner; it is loaded only for the selected ordinary
  parent and draws inside the corner wedge between the two blue side strips; it suppresses itself when that inward
  hit wedge would overlap another widget/edit-control exclusion. The diagonal's collision check is edit-event/geometry-driven only and its 110 ms opacity fade
  runs only when a parent is selected. Child overflow feeds the existing `content_extent` owner; growth may request outer expansion, while shrinking
  never auto-collapses the outer widget. Persist normalized logical geometry, keep Save/Cancel/slots/reset on the
  shared CUSTOM owner, and add no recurring runtime work outside real edit/state events. Artwork size commits may
  request an appropriately higher-quality source through the existing artwork/image owner and crossfade only once
  the replacement is ready, preserving original-aspect/crop rules and never refetching on drag ticks. Detailed
  architecture + build order: `Docs/Future_Work/Custom_Child_Geometry.md`. Artwork child rectangles are explicitly freeform X/Y while their images preserve native aspect via the existing fill/crop/zoom policy; intrinsic shapes such as Pulse circles/square badges remain uniformly constrained.
  **Achievement Pulse proof slice is now implemented and awaiting operator/Qt validation:** artwork, latest-achievement badge and progress circle are all live targets on the shared owner. Artwork can change X/Y independently while `PreserveAspectCrop` protects the source image; badge/circle resize as intact intrinsic shapes. Family reflow preserves the authored rails and reports one grow-only outer minimum, and descriptor-owned handle admission exposes only the corner that matches each role's retained anchor so no child-position persistence is needed. Achievement artwork shape/size Settings controls join the existing CUSTOM lock while CUSTOM owns that geometry. General runtime remains event-driven; no new timer/poller/provider/cadence was added.
  **Settings/second-family continuation now implemented, awaiting Qt/physical validation:** the old Steam section-wide CUSTOM settings lock is split into widget-scoped Achievement / Abandonment / Friend Pulse locks, and its revert action restores only the affected family rather than all CUSTOM widgets. Friend Pulse now consumes one grouped `avatars` child role in Rows and Grid; one scalar sizes every avatar, layout/column admission yields space to the new footprint, and no per-avatar persistence/provider state exists. Artwork geometry declarations now reuse the shared `freeform_artwork_child_role(...)` constructor so later Steam/Media artwork can share frame semantics without sharing provider ownership or disturbing dormancy. Next significant consumer is Media; keep its provider/image lifecycle isolated while reusing the geometry primitive.
- [ ] **Weather five-day reveal defect — keep high.** The shared ordinary `content_extent` rollout is now
  operator-validated, but the intended five-day forecast section did **not** appear during that validation. Treat
  this as a focused Weather presentation/data-admission defect, not as evidence that the outer sizing contract is
  still unvalidated. Keep it near the top of the queue while CUSTOM child geometry proceeds; do not solve it with
  another provider cadence, geometry owner or drag-triggered request.
- [ ] **Games You Follow.** Next retained Steam family member — currently owned only by the `--devsteam`
  scaffold. Feasibility-gated: only after the existing-key `GetGamesFollowed` route is live/fixture-proved.
  Its first retained implementation must consume both shared `content_extent` axes and reuse the Friend
  Pulse source/privacy/cache/runtime ownership rather than adding a second owner. Full
  admission/decomposition: `Docs/Future_Work/Steam_Games_You_Follow.md`.
- [ ] **System volume/mute OSD — as a widget.** Promote the opt-in system-audio OSD from ephemeral overlay
  to a positionable **widget with optional dormancy**: an Edit-mode shell resolved on the correct display so
  the user can side-resize (hor-only / vert-only), corner-size and wheel-scale it through the shared
  `content_extent` reflow + uniform-scale system, round-tripping through the ordinary CUSTOM save/load/slot
  path. Its level bar reuses the Media volume bar's visual language (a proper left→right fill), with text
  customization — font/size; text position = left of bar / inside bar / right of bar / no text / numbers-only;
  and bar thickness. Theme semantics inherited (may match media volume). Disabled ⇒ fully dormant (no shell,
  no item, no endpoint, no callback). Full spec + COM/threading/dormancy traps: `Future_Work.md` §10.2.

**Build constraint for the widget work in this section:** maintain widget normalization and reuse the shared
widget aspects — `content_extent` side-reflow + uniform scale, the CUSTOM Edit shell/overlay, Restore Size,
theme roles, the volume-bar component — rather than re-implementing per widget. Introduce a new reusable only
when it is genuinely the better architecture; never fork a second normalization/sizing owner.

## Standing guardrails — routed, not duplicated

`Docs/Guardrails.md` is the gatekeeper and outranks this file for cross-cutting rules; do not
re-inline their text here. The ones binding on work touched from this plan and where each lives:

- Voxel Sphere isolation, Visualizer fidelity/scaling (R-69) and Live/global CUSTOM ownership → `Docs/Guardrails.md` (geometry / preset-authority / CUSTOM sections).
- Media GSMTC/event ownership (no fast polling or process-probe fallbacks; no second Media owner) → `Spec.md`, `Docs/Contracts.md`, `Docs/Historical_Bugs/R-66_Media_Event_Ownership_Replaced_Fast_Polling.md`.
- System-audio dormancy and general lifecycle admission → `Docs/Guardrails.md` (Lifecycle).
- CHK26 performance admission (symptom-driven only; Bubble is a protected oracle, not an optimization target) → `Docs/Guardrails/Performance_Optimization_Contract.md`.
- Defaults SSOT and the dark.qss retirement → `Docs/Contracts.md`, `Docs/Architecture/Settings_Theme_Architecture.md`.
- Protected-behaviour REDs are real signal: investigate against current owners/floors, protect confirmed-correct behaviour as a floor, never weaken a protected contract to reach green.

## Authority order

```text
exact current source + current reconciled test tree
-> Current_Plan.md (this file: active work + order)
-> Spec.md
-> FWPlan.md (future / non-blocking implementation)
-> Docs/TestSuite.md (test truth)
-> Index.md + focused/decomposition docs
```

## Durable references

- `Index.md` — routing map to current owners.
- `Docs/TestSuite.md`
- `Docs/Architecture/Persisted_Input_Compatibility.md` — compatibility-bridge guard.
- `FWPlan.md` / `Future_Work.md`
- `Docs/Reference/Steam_Friend_Pulse.md`
- `Docs/Reference/System_Stats_Widget.md`
