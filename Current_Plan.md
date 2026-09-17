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

- [~] **CUSTOM Visualizer quarter-turn orientation glyph.** Implementation checkpoint 2026-09-17 is
  in-tree and the 2026-09-18 follow-up makes orientation **per canonical carded mode**: one sparse
  `content_rotation_quarters_by_mode` map rides the existing CUSTOM `size_payload` (the former global
  scalar remains read-only compatibility input and expands across all capable carded modes);
  the persisted/edited viewport stays physical while the shared Visualizer presentation/render contract
  derives the effective logical world and common quad coordinate turn. The five accepted carded modes
  consume that seam; Sphere neither exposes nor renders the turn, while its selection cannot erase a
  dormant carded-mode token. Save/Cancel, layout slots, cross-display state and Restore Size ownership
  stay on their existing carriers. Local static/contract probes pass, but this container has no PySide6,
  so the focused Qt/QML tests, maintained destination profile, real-GL shader path and installed eyes-on
  gate remain **NEEDS RUN** before this item is accepted/closed. General performance self-audit also
  tightened the steady-state path: retained publication snapshots extent/orientation/override under one
  existing controller lock, and the GL rotation uniform is cached so it uploads only on first use or an
  actual turn rather than on every draw. No timer, polling, provider wake, alternate cadence, runtime
  rebuild or per-frame Settings read was added. Operator reports the installed turn behavior is working well;
  the edit glyph has since been moved from the header/upper-left area to an inset **bottom-right** slot that
  stays clear of the right/bottom edge-resize strips and corner handle. A requested live-hover rotate glyph is
  **not admitted yet**: mutating persisted CUSTOM layout outside the edit transaction needs a proper shared live
  layout-action owner; do not let QML write persistence or bolt a second orientation authority onto the live card.
  Full suite/complete per-mode acceptance remains pending. Full spec + golden-proof gate: `Future_Work.md` §8.1.
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
- [~] **Achievement Pulse / Abandonment Issues / Weather — presentation hor-only & vert-only sizing.**
  **Implemented in-tree 2026-09-18; Windows/PySide/QML acceptance still NEEDS RUN.** All current resizable
  ordinary non-Clock families now declare the shared horizontal+vertical `content_extent` contract. Achievement
  Pulse and Abandonment Issues preserve their dense authored canvas as the side-drag floor while redistributing
  added room through their existing layout; the shared CUSTOM owner resolves that floor once at edit admission so
  persisted/session geometry cannot disagree with QML. Weather reflows on both axes and reveals its retained five-day
  forecast only when the CUSTOM vertical box has enough room beyond the compact intrinsic presentation. The Weather
  provider widens its existing single request from 2 to 6 daily rows (today + five future days); no second fetch, timer,
  provider or cadence was added. Corner/wheel scale remains the existing uniform outer transform. Focused family +
  owner tests were updated alongside the implementation; full intended-environment validation remains the acceptance gate.
- [ ] **CUSTOM editable child geometry — after the content-extent rollout.** Add one shared role-based edit
  primitive for a deliberately small set of major visual children, not arbitrary QML elements. CUSTOM becomes
  the sole active size authority for an overridden child while its authored Settings value remains preserved
  underneath; normalize/reuse the existing **“Disable Custom To Adjust!”** disabled-settings treatment wherever
  those authorities would otherwise fight. Initial candidates are Media artwork + seek/volume bars + one grouped playback-controls role, Steam artwork, Achievement Pulse badge,
  Friend Pulse's grouped avatar role, optional Weather hero icon, and Clock **analogue-only** grouped separator /
  Roman-numeral roles. Parent selection in global Edit mode reveals the smaller child-role handles for only that
  widget; do not carpet the whole scene with child handles.
  Child overflow feeds the existing `content_extent` owner; growth may request outer expansion, while shrinking
  never auto-collapses the outer widget. Persist normalized logical geometry, keep Save/Cancel/slots/reset on the
  shared CUSTOM owner, and add no recurring runtime work outside real edit/state events. Artwork size commits may
  request an appropriately higher-quality source through the existing artwork/image owner and crossfade only once
  the replacement is ready, preserving original-aspect/crop rules and never refetching on drag ticks. Detailed
  architecture + build order: `Docs/Future_Work/Custom_Child_Geometry.md`.

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
