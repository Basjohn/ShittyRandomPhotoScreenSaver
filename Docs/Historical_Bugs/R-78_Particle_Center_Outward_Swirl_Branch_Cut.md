# R-78 — Particle Center-Outward Swirl Had A Radial Branch Cut

## Classification

- [x] SOLVED

## Symptom

With Particle transition mode set to `Random`, an occasional particle build showed a hard radial cut/wedge through what should have been a continuous swirl. The failure was intermittent because Random must first choose `Swirl` and then choose the affected Center Outward build order.

## Root cause

`getSwirlOrderKey()` converted `atan()` to a normalized `0..1` angle and fed that angle directly into a linear Center Outward ordering term. `atan()` wraps from `+PI` to `-PI`; a linear use of that wrapped angle therefore creates a discontinuity along one radial seam. Typical and Edges Inward already use periodic trigonometric angle terms and do not have that cut.

Settings also mislabeled the existing integer contracts. Shader indices `0..4` mean `NW, NE, Front, SW, SE`, while the UI displayed `Front, Left, Right, Top, Bottom`. Swirl order indices `0..2` mean `Typical, Center Outward, Edges Inward`, while the UI used unrelated labels. Runtime/persisted indices were correct; only the labels were wrong.

## Repair

Center Outward keeps radius as the dominant order authority but its angular hint is now periodic (`sin(theta + radial phase)`), so the `+PI/-PI` wrap is continuous. No other Particle mode/order path was retuned. Settings labels now mirror the existing shader index meanings without migrating or rewriting persisted values.

## Guardrail

Never feed a wrapped polar angle directly into a non-periodic ordering term for a circular/swirl effect. If angle affects timing/order, pass it through a periodic representation such as `sin/cos`, or otherwise explicitly unwrap it. UI labels for numeric shader enums must match the existing index contract rather than inventing a second semantic mapping.
