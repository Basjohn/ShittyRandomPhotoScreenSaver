# R-81 — Clock Layout Slot Restored Variant Geometry Without Restoring Per-Display Face State

Date: 2026-09-13  
Status: Resolved In Code / Installed Validation Pending

## Classification

- [ ] COMPLETELY FUCKED
- [x] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure

Clock correctly retained different CUSTOM geometry for digital and analogue. Live double-click could also keep different face choices on different displays. But a numbered layout slot saved while a Clock was digital could later be loaded while that same display was analogue and the Clock would remain analogue instead of restoring the digital state saved with the slot. The runtime then selected the analogue geometry variant even though the slot contained the intended digital geometry as well.

A related persistence hole meant opening/saving the Clock Settings section could replace `clock` / `clock2` / `clock3` mappings and silently drop the runtime-authored per-display mode overrides.

## Root Cause

R-45 and R-48 intentionally separated behavior from geometry:

- shared `display_mode` is the global/default face;
- `display_mode_overrides[screen_signature]` is the per-display double-click face state;
- `custom_layout` stores independent `digital` / `analog` geometry variants and size payloads.

That architecture was correct, but the layout-slot serializer only treated `display_mode` and geometry as slot-visible state. It never captured `display_mode_overrides`. Slot load therefore restored both geometry variants but could inherit a newer override from current Settings and activate the wrong one. Separately, the Clock Settings saver rebuilt its section dictionaries without carrying the override maps forward.

## Fix

Layout-slot **payload** format is now version 2 while the outer `widgets.layout_slots` container/default remains version 1. A v2 payload captures each real Clock section's complete per-display override map, including an explicit empty map, alongside the already-captured shared `display_mode` baseline. CUSTOM geometry remains untouched and continues to own only the independent digital/analogue variant rectangles and resize-derived size payloads.

Slot replay restores all three Clock override maps before applying ordinary section fields and before the existing fenced runtime rebuild. Explicitly empty saved maps clear later runtime overrides instead of inheriting them. Legacy v1 slots cannot reconstruct mode overrides they never stored, so replay clears current overrides and deterministically uses the legacy slot's saved shared `display_mode` baseline.

Clock Settings save now deliberately preserves valid `display_mode_overrides` for `clock`, `clock2`, and `clock3` while the visible checkbox continues to author only the shared/global baseline.

## Contract

Clock face selection and Clock geometry are separate persisted state and both must participate in numbered layout-slot save/load:

```text
face state:
    display_mode
    display_mode_overrides[screen_signature]

geometry state:
    custom_layout[screen][clock][digital]
    custom_layout[screen][clock][analog]
```

Do not solve slot replay by putting `display_mode` back into geometry payloads, by collapsing analogue/digital to one rect, or by rewriting a per-display double-click into the shared baseline.

## Validation Target

Use a Clock with visibly different analogue and digital CUSTOM positions/sizes. Save a numbered slot in one face, switch the live face and geometry, then load the slot. Require the saved face and its matching geometry to return. Repeat with Clock routed to ALL and different per-display face states, then exercise unrelated Clock Settings save, runtime rebuild, restart, mixed-DPI displays, and an explicit-empty-override slot.

Dedicated automated Clock/slot coverage is intentionally deferred to the next test pass; `Docs/TestSuite.md` was not changed in this checkpoint.
