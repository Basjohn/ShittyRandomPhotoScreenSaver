# Usu authoring asset

`Usu_Static_Approval.blend` is the editable, unrigged character source. This
directory is authoring/review material and has no SRPSS runtime consumer.
The live approval checklist is in `../../Current_Plan.md`; the filename does
not assert visual acceptance.

The constrained correction pass is saved, but does not yet satisfy the full
visual brief. The remaining ear-root work is listed under **Before rigging**.

The art direction is the asset section and approval gates in
`../../Docs/Future_Work/Usu_Moonscape_Visualizer_Future_Plan_f104a29eec.md`.
Its runtime proposals remain deferred. The supplied approved turnaround is
`../../tmp/UsuForModelling.png`, packed inside the `.blend`. No original novel
drawings were available during this session.

## Editable geometry

- Four closed principal surfaces: joined head/ears, torso with connected arms,
  and two separate rounded feet. The feet's upper caps sit inside the torso.
- The head/ear cage retains 4,390 quads and two small repair triangles. Local
  depth adjustments fill the rear attachment valleys; local surface fairing
  rounds the temple and upper crown transitions. The face, lower ear volume
  and front silhouette constrain these edits. No overlay patches remain.
- The torso/arm cage has 4,313 quads and 698 triangles. Folded internal shoulder
  faces were removed, the joins rebuilt, and the surrounding surface faired.
  The feet retain their original longitudinal quad loops and small end fans.
- Subdivision remains unapplied: level 1 on the head/ears and torso/arms, level
  2 on the feet. Eyes and brows are separate simple
  surface meshes; there are no sockets, nose, mouth, fur, toes or tail.
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

All individual views are 1000 × 1200 PNGs. These four use the same orthographic scale:

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
`source/front_preservation.json` compares the evaluated front silhouette with
the pre-correction anchor and records unchanged eye/brow and foot coordinates.
This geometric comparison measures preservation, not artistic acceptance.

## Before rigging

User visual approval is mandatory. The correction improves the rear attachment
trenches and arm transitions, but a small side-temple indentation and shallow
rear-root bands remain visible from some angles. These are outstanding modelling
review items, not accepted details. Also check the upper rear crown contour in
HIGH SIDE. Check SIDE, HIGH SIDE and HIGH REAR closely
alongside the front anchor and supplied turnaround.

The profile eye still reads narrower than the drawn side eye. Ear/shoulder
deformation and the feet's hidden root overlaps have not been tested; static
acceptance must precede rigging. A single welded whole-character mesh is not assumed.

`source/mesh_validation.json` records direct Blender checks of the principal
surfaces: closed/manifold edges, no loose vertices, zero-area faces or
nonadjacent self-intersections in the cages or evaluated subdivision, and no
armatures, armature modifiers or animation actions. These checks do not prove
visual likeness or future deformation quality. No rig, animation or engine
asset export has been created.
