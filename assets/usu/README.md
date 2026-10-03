# Usu authoring asset

`Usu_Static_Approval.blend` is the editable, unrigged character source. This
directory is authoring/review material and has no SRPSS runtime consumer.
Modelling review notes belong in this asset directory, never in the SRPSS
runtime plan. The filename does not assert visual acceptance.

The rear head and ear attachments have been reshaped and saved for visual
review. The posterior surface is fuller and rounder, the upper ear rail has a
gentler slope, and two folded lower cheek/ear patches were repaired. No visual
acceptance is implied.

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

Edit the `.blend` directly; it is the single modelling source. The rejected
procedural builder has been retired. `source/review_static_usu.py`, executed
through Blender MCP from this open file, checks the principal surfaces,
renders all nine views, and saves the `.blend`. It does not replace geometry.

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

## Before rigging

User visual approval is mandatory. Review the ear slope and roundness of the
rear head in SIDE, HIGH SIDE and HIGH REAR, then inspect the lower cheek/ear
transition in the enlarged 3/4 view. A small crease remains at that transition;
it should be assessed before accepting the static form. Compare the updated
views with `renders/CORRECTIONS.png` and the supplied turnaround. Also review
the open eye arcs in FRONT and 3/4 and their stronger foreshortening in SIDE.

The profile eye still reads narrower than the drawn side eye. Ear/shoulder
deformation and the feet's hidden root overlaps have not been tested; static
acceptance must precede rigging. A single welded whole-character mesh is not assumed.

`source/mesh_validation.json` records direct Blender checks of the principal
surfaces: closed/manifold edges, no loose vertices, zero-area faces or
nonadjacent self-intersections in the cages or evaluated subdivision, and no
armatures, armature modifiers or animation actions. These checks do not prove
visual likeness or future deformation quality. No rig, animation or engine
asset export has been created.
