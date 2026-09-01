# R-69 — Bubble Extreme-Viewport Global Radius Compression Suppressed Reactivity

Date: 2026-09-01
Status: PARTIAL / AWAITING PHYSICAL VALIDATION — failed correction retired; original extreme full-expansion footprint remains open

## Symptom

A Quick-only attempt to stop Bubble from becoming visually huge on very tall CUSTOM cards made Bubble appear close to non-reactive as the CUSTOM viewport became tall or wide. The same Bubble preset remained strongly reactive outside CUSTOM and at near-canonical CUSTOM geometry. Ghost/motion-trail displacement also became much less visible as the viewport diverged from canonical proportions.

The failure was therefore geometry-dependent rather than a general DSP, GC, source-cadence or Bubble-energy regression.

## Evidence

The 2026-09-01 falsifier run exercised non-canonical logical viewport domains reaching roughly `4.662 x 8.313` and `2.362 x 1.000`.

During those bad physical shapes:

- Visualizer logical publication remained roughly `88-92 Hz`.
- Presentation geometry mismatch count remained zero after the separate R-68 CUSTOM-authority repair.
- Bubble pulse/event/stream diagnostics remained materially active; representative pulse values commonly remained around `0.5-0.9`, event spikes reached roughly `0.9`, and stream motion remained in its ordinary active range.
- The visual failure worsened with viewport extent and disappeared again near canonical geometry.

That combination rules out the retained DSP-state/GC work as the primary owner of this symptom and points directly at presentation scaling.

## Failed Method — Do Not Reintroduce

The rejected correction introduced a Quick-only `head_radial_scale` that capped physical Bubble-head growth once the viewport exceeded roughly `1.75x` authored height.

That looked locally attractive because an extreme-tall Bubble at full expansion could become much larger than desired. It was architecturally wrong because Bubble radius is already renderer-facing state: it is intentionally expressed as a fraction of the actual card height. Applying another `baseline/current`-style compression to the complete head radius reduced **every** radius delta as viewport height grew. The result was not merely a smaller maximum Bubble; the visible musical expansion/contraction itself was compressed toward flatness.

The first Ghost implementation repeated the same class of mistake on motion history. BubbleSimulation had already normalized historical positions into renderer-content coordinates, but the Ghost path reused the older R4 ripple-wake `u_trail_axis_scale` (`baseline/current`) correction. That double-compensated history displacement and made Ghost/motion trails disappear progressively on wide/tall CUSTOM shapes.

These are failed repair methods, not dormant alternatives.

## Contract Restoration

- Remove `head_radial_scale` completely from the retained Bubble layout, uniform upload and shader.
- Render Bubble head radius directly from the authored renderer-facing radius again.
- Preserve the already-accepted R4/R5 compact **ripple wake** correction; its baseline-pixel footprint is a separate presentation effect and must not be generalized to Bubble head radius or Ghost history.
- Let Ghost consume the already-normalized historical Bubble position exactly once.
- Make Ghost fade modestly gentler, reusing the existing three-sample history and existing shader loop only.
- Preserve the smooth `0..+1` authored-pixel large-viewport outline bonus. It does not alter Bubble simulation, radius response, cadence or history ownership.

No timer, render pass, history owner, polling path, DSP gain change, scheduler change or GC-policy change is part of this restoration.

## Remaining Open Visual Tail

Restoring the binding radius contract can make an extreme-tall Bubble at **full expansion** physically very large again. That is preferable to globally destroying reactivity, but it is not declared visually ideal.

If the oversized full-expansion tail remains objectionable after this restoration is physically validated, the next repair must target only a **proven upper expansion tail** (or another source-proven presentation seam). It must not multiply the entire radius sequence by viewport extent, and it must preserve the same visible response delta at canonical, wide and tall CUSTOM geometry.

## Acceptance Required

- Near-canonical, very wide and very tall CUSTOM Bubble must show comparable musical expansion/contraction character.
- Ghost displacement must remain visible at wide/tall shapes and decay gently rather than vanishing from double viewport compensation.
- Non-CUSTOM Bubble must remain unchanged in feel.
- The large-viewport +1 authored-pixel outline treatment must remain inexpensive and must not create a second cadence/render pass.
- If full-expansion heads are still too large, record that separately as the remaining visual-tail problem rather than reviving the rejected global radius multiplier.

## Binding Lesson

When a logical simulation already projects state into renderer-content coordinates, do not apply a second `1 / viewport_extent` correction simply because the physical card is large. A correction that makes the maximum geometry prettier can still destroy the **delta** that carries reactivity. Extreme-tail appearance and whole-range responsiveness are separate problems and must be solved at separate seams.
