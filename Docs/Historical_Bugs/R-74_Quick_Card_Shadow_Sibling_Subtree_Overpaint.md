# R-74 — Quick card shadows could overpaint sibling widget content

**Status:** IMPLEMENTED / AWAITING PHYSICAL VALIDATION (2026-09-01)

## Symptom

With several retained ordinary cards close together, a shadow from one widget could visibly darken/paint over another widget's card/content. Operator evidence showed Abandonment Issues leaking upward over Gmail while other more widely separated cards looked normal. CUSTOM edit handles made the boundary especially obvious but were not the cause.

## Mechanism

Every ordinary `OverlayWidget` previously owned its `RectangularShadow` inside its own QML subtree. `z: -1` on that shadow only put it behind **its own card/background**. It did not create a process/display-global "all shadows below all cards" plane. When a later-created sibling widget subtree was painted after an earlier sibling, the later widget's negative-z shadow could still overpaint the earlier sibling's content wherever the blur/extension crossed the geometry boundary.

This is a stacking-contract bug, not a shadow-direction or CUSTOM-handle geometry bug.

## Repair

Production ordinary cards now use a display-local two-plane composition:

```text
pixelShiftLayer
  -> ordinaryWidgetShadowHost  (all ordinary card shadows)
  -> ordinaryWidgetHost        (all ordinary card/content subtrees)
```

`OverlayCardShadow.qml` is a presentation-only underlay bound to its source `OverlayWidget` for geometry, uniform-scale visual bounds, style, direction/Extra Offset and whole-widget fade. Production host adoption enables the external underlay and disables the local `OverlayCard` shadow; direct primitive/smoke hosts retain the local fallback when no underlay host/factory is supplied.

Cross-display retained-widget transfer moves the underlay together with its source widget so CUSTOM monitor moves cannot strand the shadow on the old display.

## Guardrails

- Ordinary card shadows must never rely on a negative child `z` to escape sibling-subtree paint ordering.
- Shadow ownership remains presentation-only; no settings/model/service polling enters QML.
- Externalization must preserve uniform CUSTOM scale/letterbox geometry and whole-widget fade opacity.
- R-73 remains binding: card direction/Extra Offset are asymmetric geometry with `RectangularShadow.offset == (0,0)`; opposite-edge coverage must not be stolen.
- Do not solve sibling overpaint by clipping shadows to each card rectangle; that would delete the intended external shadow.
- Visualizer currently retains its independent presentation root/shadow contract and must be validated separately before any attempt to unify its layer topology.

## Validation still required

Physically place Gmail, Abandonment Issues and Achievement Pulse close enough that their shadow extents overlap, both in ordinary mode and CUSTOM. Confirm all ordinary shadows remain below all ordinary card/content pixels regardless of creation order, movement or duplicate state. Re-test large directional Extra Offset and whole-widget fade so externalization did not regress R-73 or lifecycle opacity.
