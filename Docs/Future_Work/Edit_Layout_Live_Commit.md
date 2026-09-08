# Live Edit commit

Implemented; physical cross-display Save validation remains open.

## Contract

Healthy geometry-only Edit Save stays in the current runtime generation, including
ordinary widgets and the Visualizer moved across displays. Save persists the working
layout, promotes retained geometry/ownership, then closes all Edit overlays. Cancel
restores the baseline without promotion. Saved-slot load keeps its explicit fenced
replacement contract. A proven dead/incoherent retained graph remains a loud invariant
repair case; a display crossing alone is not evidence that reconstruction is needed.

Family activation/presence changes and Reset have separate admission semantics; this
geometry repair does not alter those paths or introduce a new restart requirement.

## Existing owners, completed transfer

`QuickCustomLayoutSceneCoordinator` already moves the same ordinary item, its shadow
and parented model during the gesture. Before this repair, Save rebuilt merely because
the source presenter still held family/binding/service records. Save now validates the
exact target retained item against the source family, then moves those records through
the existing presenter, family binder and WidgetRuntimeManager owners. The service is
neither recreated, reinjected, activated nor retired during transfer.

The existing preferred-size subscription is retargeted to the destination presenter;
committed target geometry is applied before Edit ends. Clock's display context follows
so variant lookup and semantic mode-toggle persistence use the destination. No second
model, geometry owner, timer, polling loop or render/source subscription is introduced.
Cancel before Save retains the established reverse pixel transfer; the source binding
and service records have not moved yet. Subsequent Edit captures the destination's
family registry, permitting repeated Save and return transfers in the same generation.

Visualizer remains its existing atomic scene/runtime/pacer/manager-unit transfer,
including stable display-local shells. Its logical owner and authored cadence remain
unchanged. The prior source/target corruption repair is not weakened.

## Evidence and self-audit

`logs/live_edit_audit_20260908_1606` proves two unnecessary `display_transfer` Save
rebuilds at 16:04:32 and 16:05:37, with 609/593ms destruction barriers and repeated
provider startup. No Qt warning or corruption recovery caused either replacement.

The real-Qt ordinary transfer regression now exercises move -> Cancel -> move -> Save
-> re-enter -> move back -> Save. It retains the exact item/family/service, moves the
preferred-size binding and service retirement authority, preserves committed geometry
on content-size events, and requests no reload. A separate real-Qt Clock adapter test
verifies mode actions read the live destination identity rather than the constructor's
captured source identity. Existing owner gates pass 57 tests; five presenter/action
gates also pass. The old Clock presentation suite has nine stale shadow fixtures
missing current required fields; that reconciliation is tracked in Current_Plan.

## Awaiting Validation

- [ ] Repeat the operator's multi-widget cross-display edits and Save twice. Confirm
  no `save_continue` / `custom_edit` runtime replacement for healthy geometry changes.
- [ ] Confirm all retained actions, Clock variant switching, provider updates and
  move/resize remain usable after each Save, including a return transfer.
- [ ] Confirm saved-slot loads still retire/reconstruct cleanly and final exit retains
  no ordinary service, Quick root or Visualizer lifecycle owner.
