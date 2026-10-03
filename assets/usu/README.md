# Usu authoring asset

`Usu_Static_Approval.blend` is the editable, unrigged character source. This
directory is authoring/review material and has no SRPSS runtime consumer.
Asset review notes belong in this asset directory, never in the SRPSS runtime
plan. The user explicitly approved this static model before requesting rigging.

`Usu_Rig_Validation.blend` is the separate rigged review copy. The approved
static file is byte-for-byte unchanged. Its geometry, facial styling and
unapplied subdivision were retained in the rigged copy. See `RIG_REVIEW.md`
for the exact hierarchy, controlled weights, validation and approval gate.

The art direction is the asset section and approval gates in
`../../Docs/Future_Work/Usu_Moonscape_Visualizer_Future_Plan_f104a29eec.md`.
Its runtime proposals remain deferred. The supplied approved turnaround is
`../../tmp/UsuForModelling.png`, packed inside the `.blend`. No original novel
drawings were available during this session.

## Editable geometry

- Four closed principal surfaces: joined head/ears, torso with connected arms,
  and two separate rounded feet. The feet's upper caps sit inside the torso.
- The head/ear surface was corrected from the existing mesh, using an authored
  rear-volume guide and gradual redistribution of its cage. The posterior
  contour follows the correction sheet's crown-to-ear slope. The existing
  subdivision was applied once to resolve folded cage faces; two small
  cheek/ear interiors were then replaced by quad patches with fixed collars.
  The editable head now has 17,568 vertices and 17,566 quads. No guide or overlay
  surface remains. The body, arms and feet are unchanged from the preceding
  saved checkpoint.
- The torso/arm cage has 4,313 quads and 698 triangles. Folded internal shoulder
  faces were removed, the joins rebuilt, and the surrounding surface faired.
  The feet retain their original longitudinal quad loops and small end fans.
- A further subdivision preview remains unapplied: level 1 on the head/ears
  and torso/arms, level 2 on the feet. Eyes and brows are separate surface meshes.
  Each eye retains
  a fine closed iris rim and a separate mirrored, open outer arc with a
  lower/inner gap and tapered ends. The filled outer oval and white inset were
  replaced in the preceding linework pass. All eye and brow coordinates are
  unchanged in this attachment correction. There is no nose,
  mouth, fur, toe detail or tail.
- Smooth matte neutral clay, charcoal hands and simple eye materials expose
  the shape without surface texture. The reference's ear greys and body
  highlights are interpreted as shading, rather than new markings.
- Z is up; front faces -Y; height is about five arbitrary authoring units.
  Final engine units and export conventions have not been established here.

The `.blend` files are the authoring sources. The rejected procedural builder
has been retired. `source/review_static_usu.py` is for the static file only: it
checks the principal surfaces, renders the static views and saves the static
`.blend`. Never run it as a rig review helper. Rig validation uses
`source/validate_rig_usu.py`, which guards the separate rigged filepath.

## Review images

All individual views are 1000 × 1200 PNGs. Validation uses Workbench material
colors and a fixed plain studio light, with shadows, cavity, specular highlights
and object outlines disabled. Scene beauty lights do not affect these images.
These four use the same orthographic scale:

- `renders/Usu_front.png`
- `renders/Usu_side.png`
- `renders/Usu_back.png`
- `renders/Usu_three_quarter.png`

The 3/4 camera has a modest elevation and a roughly 22-degree horizontal angle guided by the
illustration. `renders/Usu_Static_Views.png` arranges all four renders.
`renders/Usu_Reference_Comparison.png` places the approved illustration above
the current model, with comparable character heights. This layout is composed
by `source/compose_review.py` without altering either image's content.

Five 85 mm perspective checks use the same character geometry:

- `renders/Usu_oblique_front.png`
- `renders/Usu_oblique_rear.png`
- `renders/Usu_high_rear.png`
- `renders/Usu_low_front.png`
- `renders/Usu_high_side.png`

`renders/Usu_Free_Angles.png` arranges those views. The low-front view hides
the studio ground to keep its horizon from crossing the subject.
Four 1000 × 1000 attachment close-ups are saved as
`renders/Usu_detail_three_quarter.png`, `renders/Usu_detail_side.png`,
`renders/Usu_detail_back.png` and `renders/Usu_detail_high_rear.png`.
`renders/Usu_Attachment_Details.png` arranges them without retouching.
`source/front_preservation.json` compares the evaluated front silhouette with
the preceding saved checkpoint (`710cd414`). Its silhouette overlap is 98.38%;
body/arm and foot cage coordinates and connectivity are unchanged. All face
detail coordinates are unchanged. The head topology was refined and locally repaired.
This geometric comparison measures preservation, not artistic acceptance.

## Rig review

Static approval was given on 2026-10-03. The resulting 14-bone FK rig, manual
weights and rough validation actions are ready for user review. Polished
animation requires further approval. No runtime format or export was selected.

`renders/rig_validation/` contains plain six-angle pose renders, labeled review
sheets, and two-angle rough motion previews. The arm/body welded join required
a gradual lateral weight blend; rigidly weighting the entire dark hand created
folds. The accepted technical pass keeps the skull/upper ear attachment rigid
and confines ear follow-through to the lower lobes. Review the amount of that
bend and the strongly folded compact rest pose before choosing animation style.

`source/mesh_validation.json` is evidence for the unrigged static source.
`source/rig_validation.json` compares the separate rigged copy with that source.
`renders/rig_validation/subdivision_metrics.json` covers 39 posed states with
zero detected self-intersections or zero-area faces. Numerical checks support
the rig review; they do not grant artistic approval.
