# R-257: Extruded Bubble's native scene was drawn over the whole 64-pixel bucket, magnified on the card

**28 November 2026. Fixed in the native shader texts (`rendering/native/extruded_bubble_shaders.py`, packs rebaked,
no module change); found by N5.6's native-OpenGL rule (a) smoke ("P, T and C").**

## What happened

The core allocates a surface-sized scene target in 64-pixel buckets, and its content is that bucket
(`mode_content.cpp` `sceneAnchor`: a 630 x 420 card gets a 640 x 448 scene, with the card in the first 630 columns
and 420 rows). Python's `SceneTarget` allocates the same bucket, but it draws through a viewport of the scene's own
pixels (`SceneTarget.scope`). Extruded Bubble's passes project with a raw camera matrix (no item matrix), so the
viewport alone places them. On the core, every pass into the scene, its transparency target and the near layer drew
with the content viewport, which was the whole bucket. The composite then showed the first 630 x 420 pixels.

Native therefore showed the whole scene magnified by the bucket over the card: 640/630 across and 448/420 up, about the
card's bottom-left corner. Nothing raised an error and the picture looked right. Every rule (a) frame differed,
though: about 250k pixels, up to level 211. The difference read as noise because specks and streaks were close to their
Python places, with offsets that grew smoothly from 1 to 9 px across and from 8 to 22 px down the card.

How it was found: the drift solver output, the step serials and any frame offset were ruled out first, by reading back
the drift buffers on both sides and comparing the serials input by input. A per-region shift search
(`n56key/shift_probe.py`) then measured that displacement field. Magnifying the native crop by exactly 640/630 x 448/420
about the card's corner (`n56key/warp_probe.py`) roughly halved its mean difference from Python (8.4 to 4.6 levels).
The scene targets' readback reported `content` 640 x 448.

Layer L never draws, and Waveform, the other bucketed 3D port, already placed its passes with `srpssTargetClip`.
Extruded Bubble's texts were taken from the Python renderer without that step.

## The fix

Each program drawn into a bucketed target (`PLACED`: the backdrop, specks, shells, clusters, beads, trails, near and
near clusters) has its vertex `main` wrapped (`placed_vertex`). The `main` runs as written, then
`gl_Position = srpssTargetClip(gl_Position, u_scene_item.zw, u_target_px)` places the clip position. This uses
Waveform's conventions helper and the core's own members: the scene's pixels and the target's. It also puts the
clip depth into 0 to 1 where the target's depth runs that way (Vulkan). Each fragment `main` of those programs starts
with `srpssItemOnly`, so nothing lands in the bucket's slack, where Python's viewport clips (`placed_fragment`). The
members are appended to each program's own block in both stages. The shafts, their blur and the probe draw into exact
targets and are unchanged.

## Proof

- At input 200 of the human_heavy1 smoke, the native crop's mean absolute difference from Python is 0.012 levels
  (it was 8.4). Magnifying the crop by the old ratio now makes it worse (10.4): `warp_probe.py`.
- `tests/test_eb_native_placement.py` checks these things:
  - the passes into non-exact targets are exactly `PLACED`;
  - each placed text clips and discards, and no other text does;
  - the clip arithmetic puts the scene's corners on the bucket's first 630 x 420 pixels.
  Its controls are the texts with nothing placed, and the unplaced arithmetic reaching the bucket's corner.
- On the whole 6 s human_heavy1 rule (a) smoke (594 frames), the differing pixels fell from 99.8M to 8.1M in total.
  Per frame they are now p50 6.7k and p99 17.5k, almost all one level apart
  (`.artifacts/evidence/native_core/n5_6/20261128_rule_a_placed/`). What remains sits on the near layer's content,
  the case decision H (Native_Core_P3_Decisions.md) left "judged and reported" at an unaligned card. It is outside
  this bug and is followed in Current_Plan.md's N5.6 "P, T and C".

## Rule

A native port of a scene drawn with its own projection into a core scene target must place its clip position with
`srpssTargetClip` (and discard the slack), as Waveform's does. The core's content viewport of a surface-sized scene
target is the whole bucket, not the card.
