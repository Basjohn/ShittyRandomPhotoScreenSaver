# R-68 — Visualizer CUSTOM Working Geometry Rejected Fresh Logical Snapshots

Date: 2026-09-01
Status: Solved (CUSTOM presentation-authority admission); later Bubble extreme-viewport scaling weakness is a separate presentation contract

## Symptom

During a CUSTOM Visualizer resize the editor shell could adopt the new working rectangle immediately while the retained renderer stopped advancing visually for seconds. Telemetry in the failing run showed Visualizer revision rate collapsing to `0 Hz` and snapshot age climbing to roughly `8-11 s` even though the logical producer and audio analysis continued running.

This looked like dead Bubble reactivity, but the failure was not in Bubble's DSP/simulation path.

## Root Cause

The retained render bridge correctly rejects snapshots whose presentation geometry belongs to an obsolete runtime shape. That strict rule was also being applied while a live CUSTOM edit session temporarily owned presentation geometry. Fresh logical snapshots could therefore carry the producer's previous presentation record while the editor shell had already moved to its new working rectangle. The bridge rejected those newest logical revisions solely because their presentation record had not yet caught up.

CUSTOM working geometry and runtime snapshot geometry were both being treated as simultaneous presentation authorities.

## Fix

- Outside CUSTOM, presentation mismatch remains a hard rejection; stale geometry never becomes authority.
- While the retained item is bound to an active CUSTOM session, the editor's working rectangle is the sole temporary presentation authority.
- The bridge may rebase only the immutable presentation record of the newest logical snapshot onto that working geometry. Logical state, revision identity, audio/transient payload and source timestamps are not rewritten.
- No timer, polling loop, retry queue or second cadence owner was added.

## Validation

The 2026-09-01 follow-up deliberately exercised very non-canonical Bubble shapes, including logical viewport domains around `4.662x8.313` and `2.362x1.000`. Through those edits the logs held roughly `88-92` Visualizer logical revisions/s with zero geometry mismatches instead of reproducing the previous multi-second stale-age climb.

The operator still observed weak Bubble response at those extreme shapes. Source/log comparison showed healthy pulse/event/stream activity and therefore identified that remaining symptom as a **separate viewport-scaling regression**: the presentation layer was suppressing head/Ghost displacement as aspect extent grew. That later defect must not be "fixed" by removing this CUSTOM authority rebase.

## Binding Lesson

A temporary editor that owns working geometry must not force newest logical state to wait for a second presentation authority to converge. Rebase presentation only at the explicit CUSTOM boundary; preserve strict stale-geometry rejection everywhere else. When visible response is weak but revision rate, snapshot age and source energy remain healthy, investigate presentation scaling before retuning DSP or scheduler cadence.
