# Keep retained presentation alive after geometry-only Edit Save

Status: **geometry-only live commit accepted; interactive cross-display Visualizer transfer Save now also live-commits when the transfer graph is coherent (awaiting physical validation); family-presence/monitor-route changes and layout-slot save/load still reconcile**. Live sequencing: `FWPlan.md`.

The retained path now keeps ordinary same-display geometry Save in the current runtime generation. The operator reports
that live visualizer adjustment and Save are flowing extremely well: no visible teardown/rebuild is required to commit the
already-rendered rectangle/extent. Display ownership transfer remains a topology boundary and is separately under repair.

## Owning seams and decision

`QuickCustomLayoutOwner.save` now persists first, classifies whether topology changed, promotes the already-retained
working geometry when it did not, then ends CUSTOM. `QuickDisplayVisualizerOwner.commit_live_custom_layout` atomically
promotes the current retained rectangle, viewport extent and controller committed metrics while the temporary CUSTOM
override is still active. Clearing CUSTOM therefore changes **authority**, not the value consumed by the next logical step.
Ordinary retained families promote through their existing presentation/binding owner as part of the same transaction.

Save order is now: persist successfully -> classify topology -> promote retained geometry -> end CUSTOM -> continue
running. Cancel restores the baseline and ends CUSTOM without promotion. Invalid live promotion still fails loudly.

The no-teardown admission remains explicit: same-display, enabled, non-removed items with geometry/scale/payload changes
only. Family presence/removal, display transfer and monitor-route changes retain generation reconciliation. Reset and
layout-slot topology semantics remain explicit. This is not a hidden fallback.

The 03:40-03:45 operator run exposed the remaining cross-display edge clearly: 432 QML warnings reported
`CUSTOM Visualizer target already has a retained scene admission`, followed at shutdown by a destruction-barrier timeout
retaining one `QuickDisplayVisualizerOwner`. Source tracing found that scene transfer moved `_presentation_runtime` but
left the owner's active `_runtime`/frame-pacer/bind/retirement edge on the old display. A later mode/preset or retirement
could therefore act on the wrong scene. The current source repair moves that runtime edge transactionally with the retained
presentation and latches one visualizer display crossing per pointer gesture to prevent seam ping-pong. The CUSTOM
Visualizer frame also exposes theme-palette left/right display-hop buttons. Those buttons carry only semantic direction into
Python; `QuickCustomLayoutOwner` selects the nearest horizontal retained display, projects the current shape/relative position,
and the existing scene coordinator performs the same single retained admission transfer. There is no second transfer owner and
no fade/timer. Physical validation is still required; interactive display-transfer Save now live-commits when the transfer
graph is coherent (fail-safe to reconciliation otherwise), while layout-slot save/load remain generation reconciliations.

## Live implementation checklist

- [x] Trace Save/Cancel, controller metrics, committed layout owners and normal-frame publications.
- [x] Implement the running-safe visualizer commit operation; stage/validate values before mutation.
- [x] Promote ordinary retained geometry through its existing binding, including applied size payload semantics.
- [x] Route geometry-only Save through promotion before session removal; retain explicit topology reconciliation.
- [x] Prove all six modes retain rectangle/extent across the next normal publication, along with owner, source
  identity, runtime generation and logical-state identity in focused production-chain coverage.
- [x] Prove Cancel retains baseline committed state and failed persistence does not promote or end editing.
- [x] Prove ordinary preferred-size events retain saved geometry and geometry-only Save requests no replacement.
- [~] Interactive cross-display Save now live-commits: active retained runtime/pacer/manager-unit/retirement ownership
  moves with the scene during the drag (both pointer drag and discrete theme-palette left/right hop), and
  `QuickCustomLayoutOwner.save` promotes the retained geometry in place when `_cross_display_transfer_is_coherent()`
  confirms a fully target-owned graph, logging `Save live-committed cross-display Visualizer transfer`. Any partial/
  incoherent transfer, a non-Visualizer cross-display move, family presence/monitor-route change, or a layout-slot save
  (`defer_topology_reconciliation`) still falls back to one explicit generation reconciliation. Layout-slot load stays a
  fenced generation replacement. Awaiting the physical validation run below.
- [ ] Awaiting physical validation: cross-display drag **and arrow hop** each move exactly one live visualizer, preserve the
  intended shape/placement, leave no dead duplicate, produce no QML warning storm/destruction-barrier owner, and same-display
  Save remains hitch-free at 60/165 Hz. Decide on any fade-out/fade-in only from this run.

No timer, polling, render loop, source subscription, alternate persistence authority or new generation fence is added.

## 2026-09-05 cross-display lifecycle follow-up

The first no-teardown geometry work exposed a separate display-transfer owner split. The retained scene and
`QuickDisplayVisualizerOwner._runtime` moved, but `DisplayManager._quick_visualizer_unit` and the source
`QuickDisplayUnit._visualizer_owner` retirement attachment did not. A later slot-load destruction barrier therefore
retained only `QuickDisplayVisualizerOwner`, while Save after transfer could retire the target pacer through the owner and
then make the target unit touch that already-closed pacer. The repair moves manager unit + exact unit retirement attachment
in the same event transaction as the owner runtime/pacer edge. Geometry-only same-display Save remains no-teardown;
layout-slot load and topology-changing Save remain fenced generation replacements pending further physical proof.

### Transaction hardening after WIP review

The lifecycle repair is now intentionally **one Visualizer session callback**, not two ordered subscribers. The coordinator delegates the scene move to `QuickCustomLayoutOwner._transfer_visualizer_display_transaction()`, which performs retained-scene transfer and the manager/unit/pacer move before the session placement can commit. If manager-side transfer fails, the retained scene is transferred back first; only then may the coordinator restore the working item geometry. This closes the partial-commit hole identified in the interrupted WIP. See `Docs/Historical_Bugs/Visualizer_Cross_Display_Split_Ownership_2026-09-05.md`.
