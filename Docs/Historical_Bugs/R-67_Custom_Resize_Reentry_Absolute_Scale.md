# R-67 — CUSTOM Resize Re-entry Rebased Persisted Geometry And Could Compound Shrink

Date: 2026-09-01
Status: Solved (ordinary-family absolute resize ownership); Gmail reinit shell containment remains a separate follow-up

## Symptom

Ordinary widgets could appear to respect a minimum scale during one CUSTOM edit session yet shrink far below that minimum across repeated Save/re-entry cycles. A committed rectangle that was already reduced was treated as the next session's fresh 100% baseline, so applying the same nominal floor repeatedly could compound geometrically (`40% -> 16% -> 6.4% -> ...`). Partial family-specific resize payloads also made it possible for a shell to continue shrinking after fixed internal content had reached its own minimum.

This was especially dangerous because each individual edit interaction could look locally correct while persisted geometry drifted across sessions.

## Root Cause

CUSTOM had no persisted **absolute** ordinary-widget scale authority. Session-local resize math was rebased from the current committed rectangle, conflating "this is the saved 40% state" with "this rectangle is a new 100% authored baseline." At the same time, some families resized selected payload values rather than one retained authored presentation, allowing outer geometry and internal minima to diverge.

## Fix

- Ordinary CUSTOM entries own a private persisted `_custom_resize_scale` interpreted against the authored/preferred family size, never against the previous session's already-scaled rectangle.
- The shared absolute lower bound is **40%**. Further shrink input at the bound refuses to reduce committed scale instead of continuing to distort or escape content.
- Existing geometry-only entries infer the absolute scale once from committed geometry versus authored preferred size, then persist it.
- Reddit/Reddit2, Media and Gmail opt into the retained whole-presentation `uniformScaleTransform`; presentation scale is derived from Python-owned outer geometry, so text/chrome/spacing/hit geometry move together rather than becoming second geometry owners.
- Families that retain legacy payload sizing may refuse shrink earlier when a tighter content minimum is reached. They must not let the shell continue shrinking underneath fixed content.
- Visualizer remains excluded because its viewport/scale contract has a separate owner.

## Physical Acceptance

The operator reports the repaired ordinary-family resize behavior is now working exceptionally well across the other widget families, including repeated scaling/re-entry, and the catastrophic non-uniform/compounding behavior is no longer present.

Gmail subsequently exposed a **different** recreation-only containment defect: its preferred dimensions omitted the retained card shell inset. That follow-up is not evidence that the absolute-scale contract failed and must not be "fixed" by reintroducing session-relative scaling.

## Binding Lesson

A persisted resize floor is meaningful only if its scale is absolute against a stable authored baseline. Never derive a new 100% baseline from geometry that already contains the previous scale. Outer geometry remains the single persisted layout authority; retained presentation scaling is derived, and family content minima may stop shrink earlier but may never silently move the absolute floor.
