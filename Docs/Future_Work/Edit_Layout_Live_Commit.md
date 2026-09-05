# Keep retained presentation alive after geometry-only Edit Save

Status: source audit complete; implementation active. Live sequencing: `FWPlan.md`.

The operator reports nearly correct live visualizer adjustment and asks whether ordinary edit exit can avoid
teardown. Archived `fw_geo_material_2026_09_05` logs show Save triggers full `custom_edit` replacement and input
suppression. They do not establish stale-frame behaviour for a path that currently never runs without replacement.
Validate continuity directly rather than infer it from the absence of logs.

## Owning seams and decision

`QuickCustomLayoutOwner.save` persists before promotion and ending the session. Its visualizer promotion currently
commits controller metrics alone; the live visualizer owner's committed rectangle stays old. The next ordinary frame
therefore resolves an old rectangle against a new extent. Generation replacement currently conceals this fault.
Ordinary presentations also need their existing `OverlayGeometryBinding.policy.committed_rect` promoted, otherwise
a subsequent preferred-size event can restore saved-before-edit geometry.

Implement an explicit running-safe `QuickDisplayVisualizerOwner.commit_live_custom_layout(local_rect, viewport_extent)`.
While the CUSTOM override is still active, validate and capture its current presentation, then promote owner rectangle,
owner extent and controller committed metrics together on the existing GUI owner. Do not call the configure-only
operation or recreate/retire the runtime. The effective extent must remain identical across clearing CUSTOM.

Save order: persist successfully -> promote working geometry -> end CUSTOM -> continue running. Cancel restores the
baseline and ends CUSTOM without promotion. Persistence failure must leave the editable session and live baseline intact.

The initial no-teardown admission is explicit: same-display, enabled, non-removed items with geometry/scale/payload
changes only. Changes to family presence, removal or display routing retain the existing generation reconciliation,
with a reason logged. Reset and layout-slot loading retain their explicit reload semantics. This is a topology boundary,
not a silent fallback for malformed data or failed live promotion. Invalid promotion must fail loudly.

## Live implementation checklist

- [x] Trace Save/Cancel, controller metrics, committed layout owners and normal-frame publications.
- [ ] Implement and validate the running-safe visualizer commit operation; stage values before mutation.
- [ ] Promote ordinary retained geometry through its existing binding, including applied size payload semantics.
- [ ] Route geometry-only Save through promotion before session removal; retain explicit topology reconciliation.
- [ ] Prove all six modes retain rectangle/extent across the next normal publication, along with owner, source
  identity, runtime generation and logical-state identity. Include extreme saved extents and wheel/edge adjustment.
- [ ] Prove Cancel retains baseline committed state and failed persistence does not promote or end editing.
- [ ] Prove ordinary preferred-size events retain saved geometry and geometry-only Save requests no replacement.
- [ ] Prove removal, display transfer and explicit reset/slot-load semantics still reconcile as required.
- [ ] Review focused results, update durable contracts and checkpoint commit/push.
- [ ] Awaiting physical validation: real music continues without a Save hitch, wrong geometry or stale-frame interval
  at 60/165 Hz; verify mixed-DPR and repeated Save/Cancel after the source-to-visible gates pass.

No timer, polling, render loop, source subscription, alternate persistence authority or new generation fence is added.
