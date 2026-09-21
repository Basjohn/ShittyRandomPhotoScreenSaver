# SRPSS | Current Plan

This file contains only active work and directly relevant evidence. `Spec.md`, `Docs/Contracts.md` and the focused references own durable product and architecture contracts. Completed work is not kept here as a checkpoint diary; see the canonical `.godzip/` handoff for the current transfer.

## Voxel Sphere | isolated energy-floor controls

The independent fragment and particle minimum-energy settings are implemented with curated/default and user-authored preset protection. Focused pure-Python settings/preset gates were previously reported green. The remaining Sphere-specific operator gate is the native Windows settings/preset run and active-music observation of independent floor effects, Reset and Custom Save/reopen. Do not retune authored values on the operator's behalf; promote a reproduced defect here if one appears.

## Future Work transitions | correction and removal

`Docs/Future_Work/Transition_Expansion.md` owns the detailed work; `Docs/Reference/Transitions.md` owns current behavior and controls.

- [~] Crumble's separate crack-formation stage is implemented on real fracture borders before chunk/debris motion; retain solid depth and wall debris. Operator visual acceptance remains open.
- [~] Melt remains explicitly WIP and is labelled `Melt Drip (WIP - VERY SHITTY)` in Settings while the stable transition ID stays `Melt Drip`. The rejected detached-ball/ray-marched volume has been replaced by a shallow cohesive screen-space liquid front: irregular attached fingers/rivulets, a wet meniscus, local-only refraction/streaking and highlights. Pixels well behind the wet front remain the unwarped source image so horizontal Melt cannot shred the whole photograph into slabs. Operator visual acceptance remains open.
- [~] Awaiting operator visual acceptance of Glass, Tiles, Ink and corrected Crumble at authored durations.
- [ ] Observe both displays with active music and representative heavy external load; confirm Visualizer freshness and transition first-use behavior against the accepted baseline.
- [ ] Validate the installed/frozen build, material save/reopen/Reset and repeated switch/interrupt/retire.


## Runtime -> Settings replacement lifecycle | accepted core retirement fixes

- [~] Restore the last Settings top-level tab plus its semantic subsection/builder on every runtime round-trip. Widgets, Visualizers, Display, Transitions and Themes now persist semantic selection only; restored content is always anchored at the top rather than replaying stale pixel scroll. Native round-trip validation remains open.
- [x] Settings admission during an image transition retires the transition without live cancel/destination callbacks. Native operator testing entered Settings mid-transition successfully; destruction barriers completed normally and runtime transitions resumed after replacement.
- [x] Runtime Visualizer disable retires and detaches both manager and display-unit ownership, then clears retained scene admission. Native operator testing confirmed clean retirement without the former static/uninteractable resurrection.
- [x] Core Audio callback retirement severs mailbox/bound-callback cycles and COM callbacks weakly reference their Python owner. The accepted native lifecycle run exercised Settings replacement, Visualizer/transition activity and media/audio work with `native_faults.log` clean and no watchdog dump. Keep watching future native logs for recurrence rather than reopening this without evidence.

## Handoff and regression rules

When an accepted behavior changes, select only the relevant targeted tests and physical observations; do not re-accept unrelated OSD, Media or widget systems. Keep full superseding GODZIPs with the canonical three `.godzip/` files, manifest-backed replace/delete instructions and no temporary scripts or compiled artifacts. Test commands belong in chat, not an added documentation file.
