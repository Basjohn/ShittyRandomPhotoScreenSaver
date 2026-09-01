# R-70 — Gmail CUSTOM Uniform Scale Needed Different Width And Height Shell Semantics

Date: 2026-09-01
Status: Solved / H accepted

## Symptom

Gmail exposed two related CUSTOM-size failures during the ordinary-family uniform-resize migration:

1. before whole-card retained scaling, shrinking Gmail could reduce the outer shell while fixed header/row presentation stopped shrinking, allowing content to escape below the card;
2. after adding shell compensation for recreation containment, the CUSTOM edit shell reported Gmail as wider than the visible card, making it impossible to align cleanly with peer widgets.

The second defect was especially deceptive because the preview scaling itself looked correct while editor geometry truth was wrong.

## Root Cause

Gmail's preferred dimensions do not have symmetric meaning:

- `gmailModel.contentWidth` is already the authored **outer card width**;
- `gmailModel.contentHeight` is row/content-derived and does **not** include the retained shell inset needed for the final outer height.

Adding `shellInset` to both axes double-counted horizontal shell space. Omitting it from height under-sized the recreated outer shell.

The earlier font-only CUSTOM payload path was also structurally incapable of preserving fixed header/row containment as the shell shrank.

## Fix

- Gmail joins Reddit/Reddit2 and Media in the retained whole-card `uniformScaleTransform` family.
- CUSTOM resize is geometry-only for Gmail; no private font-only scale competes with retained presentation scale.
- `preferredContentWidth` is exactly `gmailModel.contentWidth`.
- `preferredContentHeight` is `gmailModel.contentHeight + gmailRoot.shellInset`.
- ordinary absolute `_custom_resize_scale` / 40% floor ownership remains the shared R-67 contract.

Permanent tests pin both family membership and the asymmetric preferred-dimension semantics.

## Failed Method — Do Not Reintroduce

Do not treat shell inset as a generic `+2*padding`-style correction that must be applied to every reported dimension. Preferred-size fields are semantic contracts; inspect what the model already includes per axis.

Do not return Gmail to partial font-size payload scaling merely because a shell dimension looks wrong. Fix the preferred outer geometry at its actual owner.

## Binding Lesson

Whole-card uniform scaling only works if the authored baseline rectangle is truthful. A shared resize architecture does not imply every family computes that baseline identically, and even one family may have different width-vs-height source semantics. Preserve one outer geometry authority and correct the family adapter rather than creating another scaling owner.
