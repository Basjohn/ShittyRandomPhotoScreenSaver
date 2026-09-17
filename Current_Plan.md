# Current Plan — Active Work

Last updated: 2026-09-17

The Qt Quick runtime is operator-accepted. This file contains **active work only**; completed cutover work, accepted feature closeouts (Steam Friend Pulse, System Stats, Settings slider crash hardening, Friend Pulse shadow/artwork polish, content-extent resize rollout), Sphere polish, widget resize/Edit lifetime and bucket normalization are intentionally absent — their durable contracts live in the family Reference docs.

---

## Accepted baseline context — CHK26 GOLDEN

Production performance/freshness authority is **CHK26 / repository commit `a0bf70932c`**. CHK23 is the immediately prior GOLDEN rollback/bisect landmark; CHK15 / `0abc479c52` is the older pre-retained-background baseline. The generic headroom campaign is closed and performance work is symptom-driven. CHK27-CHK29 retained useful bounded `--frame-trace` attribution and closed scheduler/Bubble false trails rather than superseding CHK26. Full evidence and rejected methods live in `Docs/Historical_Bugs/R-87_QtQuick_HighRefresh_Freshness_And_Scheduler_Regression.md`.

Bubble remains the strongest protected reaction canary. Any future production change touching its timing/simulation/payload/reactive delivery requires active-music physical acceptance; idle-only evidence is insufficient.

## 1. Documentation / ownership hygiene — perpetual maintenance

- [~] Keep shrinking live docs toward present owners: current contracts/guides/reference for what is true now; `Docs/Historical_Bugs/` for durable regression archaeology; source control for ordinary chronology.
- [~] Keep code comments/docstrings aligned with current ownership and remove phase/cutover breadcrumbs that imply retired migration docs remain authority.

## 2. Up-and-coming feature work

Accepted next builds — queued, not yet started. The full decomposition stays in the linked doc; do not
duplicate that spec here.

- [ ] **CUSTOM Visualizer quarter-turn orientation glyph.** A themed turn/flip glyph in CUSTOM Edit mode
  that advances the visualizer's logical "up" by one clockwise quarter-turn per click
  (`0° → 90° → 180° → 270°`), persisted in the CUSTOM `size_payload` and round-tripping through
  Save/Cancel, layout slots and cross-display hop. It is a **presentation/layout-seam** transform
  resolved through the shared Visualizer render contract (kin to vertical/horizontal-only scaling),
  **not** a final-pixel QML `rotation`: `90°/270°` swap to an effective logical viewport so authored
  shape/reactivity/preset invariants hold. Accepted carded modes only (Spectrum, Oscilloscope, Sine,
  Bubble, Dev Curve); Voxel Sphere excluded. Full spec + golden-proof gate: `Future_Work.md` §8.1.
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
- [ ] **Achievement Pulse / Abandonment Issues / Weather — presentation hor-only & vert-only sizing.** Extend
  the shared `content_extent` one-axis side-reflow (plus corner/wheel uniform scale) to these three families,
  matching the other widgets. For now the extra axis room adjusts spacing/placement/padding only (room for
  richer content later) — with one exception: **Weather's vertical growth reveals a 5-day forecast as an
  additional section**. Reuse the existing content-extent owner; never add a second sizing/normalization
  authority.

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
