# R-73 — Quick card-shadow Extra Offset translated the whole shadow; Visualizer missed global shadow ownership

**Status:** ORDINARY CARD PHYSICALLY ACCEPTED / VISUALIZER AWAITING VALIDATION  
**Date:** 2026-09-01

## Symptom

Increasing General → Widget/Card → Shadow Extra Offset moved the entire retained card shadow in the selected
direction. At larger values the opposite corner/edge could lose visible shadow entirely. Separately, the
Visualizer card did not visibly participate in the same global shadow style contract.

## Root cause

Ordinary family projectors originally added `frame_extra_offset` directly to the authored `(4,4)` base
displacement before `ShadowDirection` applied signs. Extra Offset therefore became a second translation
magnitude. The first retained-Quick repair correctly split base displacement from directional edge growth, but
missed the live QML forwarding seam: `RetainedOverlayWidget.set_card_style()` wrote
`cardShadowExtendLeft/Top/Right/Bottom` on `OverlayWidget.qml`, while that root exposed no aliases for those four
properties. The values therefore never reached `OverlayCard` / its `RectangularShadow`, and a source-only test
failed to notice the inert projection. A second repair added that forwarding seam and correctly kept Extra Offset
out of the Python translation magnitude, but physical acceptance still showed the rendered shadow surface moving
away from the opposite edge. The remaining problem was architectural inside the QML primitive: the card still
forwarded its signed authored base direction to `RectangularShadow.offset`. Qt effect offset translates the whole
shadow surface, so combining a translated surface with one-sided extension did not satisfy the operator's hard
"opposite edge never moves" contract. Separately, the Visualizer's independent presentation resolver had used
its own default shadow values rather than a plain, owner-time projection of `widgets.shadows`.

## Destination contract

- The authored base card direction remains family/destination-owned and directional, but for **card** shadows
  it is represented as one-sided geometry rather than `RectangularShadow.offset`. The actual Qt effect offset is
  always `(0,0)`.
- **Frame Extra Offset is directional edge growth, not full-shadow translation.** Python resolves it to
  `(left, top, right, bottom)` extensions; QML combines those extensions with the signed authored base direction
  and grows only the selected far edges. The opposite edge coordinate is invariant.
- Text Extra Offset remains signed glyph displacement; do not stretch text shadow geometry to imitate a card.
- Visualizer receives the same global card-shadow enabled/color/frame-opacity/blur/direction/Extra Offset
  projection once when its display owner is constructed/reconstructed. It does not read Settings or update
  shadow style per logical/render tick.
- `RectangularShadow` remains cached/static presentation work.

## Failed method / negative control

Do **not** restore `ORDINARY_CARD_SHADOW_BASE + frame_extra_offset` as the signed shadow offset. That recreates
the original missing-opposite-corner defect. Do not restore a non-zero `RectangularShadow.offset` for card
shadows either: the second repair proved that keeping Qt effect translation alive while adding directional
extension is still physically wrong. Also do not accept source-text-only tests as proof that a retained style
property crosses a QML forwarding seam: the first repair had correct resolver/QML primitive code but inert
root properties. Do not solve Visualizer parity by polling Settings from QML or the Visualizer render loop.

## Acceptance state

The operator physically confirmed the third ordinary-card mechanism fixes the original opposite-edge failure: increasing Extra Offset in the selected direction no longer steals shadow coverage from the opposite edge. Keep that ordinary-card invariant accepted.

Still validate the **Visualizer** card against the same global direction/Extra Offset contract and confirm no per-frame settings churn or material performance change. Cross-widget shadow overpaint is a separate stacking incident now tracked by R-74; do not reopen R-73 merely because one widget shadow can overlap another widget's content.
