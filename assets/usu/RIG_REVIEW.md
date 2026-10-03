# Usu simple rig — awaiting approval

The user explicitly approved the existing static model on 2026-10-03 and
authorized a separate simple rig and rough capability tests. Blender MCP was
used for all Blender operations. This is the rig-review checkpoint; polished
animation and runtime export remain gated.

## Files and preservation

- Approved source: `Usu_Static_Approval.blend`, never saved during rigging.
- Rigged copy: `Usu_Rig_Validation.blend`, opens neutral with the rig selected
  in Pose Mode and no active test action.
- Approved-source SHA256:
  `6e3c29130f4a8f8408f6babe352db1a6f439b3e64437c8b519b475df039cf2b1`.
- All 14 character surfaces retain identical base vertex coordinates,
  connectivity, material indices and object transforms. No geometry was changed.
  No transforms or subdivision modifiers were applied. The largest evaluated
  rest difference is 0.000003657 units from float32 armature arithmetic on a
  character about five units tall.
- Each surface has a vertex-group Armature modifier before the retained
  subdivision, with Preserve Volume enabled. Envelopes are disabled.

## Exact hierarchy

There are 14 bones. ROOT is the only nondeforming bone. L means +X and R means
-X, consistent with the approved feet. Front is -Y and Z is up.

```text
ROOT
└── BODY_ROOT
    ├── BODY
    │   ├── HEAD
    │   │   ├── EAR_L_ROOT
    │   │   │   └── EAR_L_MID
    │   │   │       └── EAR_L_TIP
    │   │   └── EAR_R_ROOT
    │   │       └── EAR_R_MID
    │   │           └── EAR_R_TIP
    │   ├── ARM_L
    │   └── ARM_R
    ├── LEG_L
    └── LEG_R
```

Arms inherit BODY so the shoulders follow a torso lean. All controls are simple
FK, with no constraints, drivers, IK, simulations or facial controls. Scale
channels are locked. ROOT controls overall placement; BODY_ROOT, BODY and HEAD
provide lift, lean, tilt and bob. Bone collections group placement, torso/head,
limbs and ears.

## Controlled weights

- Skull, face and upper ear attachments: HEAD only. All ten eye/brow meshes
  follow HEAD rigidly; the existing open outer eye arcs are unchanged.
- Ears: the fused attachment remains rigid above Z=3.42, across the central
  skull and face. The exterior lower lobe blends HEAD → EAR_ROOT, then
  ROOT → MID over Z=3.02 to 2.62, and MID → TIP over Z=2.62 to 2.20. MID/TIP
  pivots are at Z=2.90 and 2.40. Normal tests keep EAR_ROOT neutral.
- Body/neck: the torso residual transitions BODY_ROOT → BODY between Z=1.15
  and 2.30, then BODY → HEAD only at the neck cap between Z=2.80 and 3.13.
- Arms: a smooth lateral blend across |X|=0.55 to 0.95 and a shoulder fade
  across Z=2.62 to 2.87. The medial dark-hand surface shares the existing welded
  torso web, so it blends rather than being forced rigidly to the arm. This
  removes the folds found with whole-hand rigid weights while retaining the
  approved geometry. ±32-degree swings were checked.
- Feet: each approved soft foot is rigidly weighted to its single LEG bone.
  Its hidden upper cap continues to overlap the body; LEG never skins the torso.

Weights are authored deterministic fields, not automatic heat/envelope weights.
`manual_weights.json` is vertex-order-specific and includes geometry
fingerprints. `bind_usu.py` refuses coordinates/topology that differ from the
approved source.

## Validation and playback

Plain Workbench material shading uses fixed paint studio lighting with shadows,
cavity, highlights and outlines disabled. Every required pose was rendered from
FRONT, SIDE, BACK, 3/4, HIGH REAR and HIGH SIDE. The latter two are perspective
free-angle checks. PNGs are 600 × 720; motion frames are 400 × 480.

The five retained actions in Blender's Action Editor are:

| Action | Frames | Purpose |
|---|---:|---|
| Usu_TEST_Poses | 1–100 | Labeled neutral, head tilt/bob, arm swing, each leg, ear back, independent MID/TIP, lean, compact rest |
| Usu_TEST_RestCollapsed | 1–49 | Compact folded rest with a tiny head settle |
| Usu_TEST_Walk | 1–49 | Restrained arm/leg swing, bob and delayed ear motion |
| Usu_TEST_Run | 1–49 | Stronger swing and ear follow-through; two rough cycles |
| Usu_TEST_EarFollowThrough | 1–48 | Authored ear impulse, overshoot and decay |

Select Usu_Rig and choose a named action in the Action Editor; use its frame
range and play at 24 fps. The rig opens with no active action so its approved
neutral form can be checked immediately. Clear the action and clear pose
transforms to return to neutral.

Review images and two-angle GIFs are in `renders/rig_validation/`:

- `review_neutral_6view.jpg`, `review_arm_swing_6view.jpg`,
  `review_collapsed_6view.jpg`, and the other named pose sheets.
- `review_pose_matrix.jpg` and `review_ears_backward_vs_neutral.jpg`.
- `review_motion_comparison_side.gif` and
  `review_motion_comparison_three_quarter.gif` each compare REST, WALK, RUN and
  EAR tests, sampled at approximately 12 fps from the 24 fps test actions.
  These are capability proofs, not polished cycles.
- `pose_metrics.json`, `subdivision_metrics.json`, `weight_isolation.json`.

Technical checks found zero nonadjacent self-intersections and no zero-area
faces in the subdivided surfaces at 11 required poses and 28 sampled motion
states. Opposite-ear displacement and upper attachment displacement are both
zero in the independent MID test. There are no opposite-side arm/ear weights,
and ROOT placement carries the whole character rigidly within float precision.

## Review before polished animation

Assess the lower-lobe ear bend, the gradual inner-hand/torso motion, and the
strong forward fold of the compact pose. The rest test deliberately explores a
compact limit; it does not prescribe the finished resting posture. Walk/run
timing, foot contact and final motion appeal remain rough. No unresolved
pinching or surface intersection was detected within the tested ranges;
untested extreme rotations still need ordinary animator review.

The asset waits for explicit rig approval. SRPSS plans and runtime code were
not changed, and no runtime asset was exported.

## Rechecking through Blender MCP

`source/snapshot_approved_usu.py` reads the static file without saving it and
writes a disposable baseline under `tmp/Usu_Rig_Validation/`. That baseline is
used by `manual_rig_weights.py` and the rest audit. The saved rigged `.blend`
already contains the weights and actions and needs no script to use it.

`source/validate_rig_usu.py` guards the rigged filepath. Its functions explicitly
render, audit, or save the rigged copy. `source/compose_rig_review.py` labels and
arranges the output without retouching it. Raw motion frames are left locally
and can be regenerated; the review GIFs and pose images are the saved evidence.
