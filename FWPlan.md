# Future Work implementation plan

Last updated: 2026-09-12

The Qt Quick migration is closed and operator-accepted. This file no longer mirrors migration-close gates or keeps
completed future slices as pseudo-work. `Current_Plan.md` owns active sequencing; `Future_Work.md` owns dormant feature
intent. This file is only a compact handoff/router for dormant future implementation.

## Active/promoted work is not owned here

Anything promoted into active execution is intentionally omitted from this file. `Current_Plan.md` is the sole sequencing/status authority for active work; focused decompositions own implementation detail. Do not mirror active investigations, widget queues, run results or completion status here.

## Dormant future ordering

1. **Directional Pixel Accretion** — isolated deterministic instanced transition experiment.
2. **Glass Shatter** — isolated deterministic 3D shard experiment.
3. **Exploding Tiles** — isolated instanced 3D tile experiment.
4. **Slide Perspective Push** — remaining optional Slide modifier; Linear/Elastic/Wobble/Flex are already landed.
5. **Deformable 3D Sphere / Blob Sphere** — separate future experiment; never mutate the accepted Voxel Sphere into it.
6. **Organic Growth / Ink Bloom** — bounded shader experiment.
7. **Other 3D Visualizer experiments** — each gets its own isolated mode boundary/decomposition.
8. **Settings FlowContainer polish [low]** — only for a demonstrated layout improvement.
9. **Two-texture artwork crossfade [low]** — only if current event-driven fade has a visible defect worth the extra
   texture residency.

## Golden / landed work is not backlog

- Current accepted Voxel Sphere reactivity/motion/presets are golden and remain isolated. No Sphere implementation work
  is queued here; future retuning/migration requires an explicit operator request.
- Widget interaction glow is landed and operator-accepted.
- Slide Linear/Elastic/Wobble/Flex are landed current architecture. Do not recreate their old proposal sections.
- Live Edit commit and ordinary resize/auto-fit normalization are landed/accepted; their old decomposition documents are
  historical references only.

## Cleanup interaction

Future implementation does not reopen cleanup/migration fossils. Before coding a selected item, inspect
`Future_Cleanup.md` only for a genuine technical prerequisite. READY cleanup does not become feature scope merely
because nearby code is touched. Never restore retired QWidget/native-event/compositor/polling owners to satisfy an old
test.

## Checkpoint discipline

For every activated future slice: inspect current owners first; pin the pre-implementation GODZIP/HEAD; create a
focused decomposition for sizeable/unique work; compile changed Python; run focused falsifying tests; inspect the
diff; update the live authority that actually owns the work; then produce a narrow checkpoint. Keep user-environment
physical/installed/visual acceptance explicit where automation cannot prove pixels or Qt lifetime.
