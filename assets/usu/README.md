# Usu authoring asset

`Usu_Static_Approval.blend` is the editable, unrigged character source. This
directory is authoring/review material and has no SRPSS runtime consumer.
The live approval checklist is in `../../Current_Plan.md`; the filename does
not assert visual acceptance.

The corrected eye linework and a constrained crown/root repair are saved.
The ear roots still do not fully satisfy the correction sheet; the remaining
review items are listed under **Before rigging**. No visual acceptance is implied.

The art direction is the asset section and approval gates in
`../../Docs/Future_Work/Usu_Moonscape_Visualizer_Future_Plan_f104a29eec.md`.
Its runtime proposals remain deferred. The supplied approved turnaround is
`../../tmp/UsuForModelling.png`, packed inside the `.blend`. No original novel
drawings were available during this session.

## Editable geometry

- Four closed principal surfaces: joined head/ears, torso with connected arms,
  and two separate rounded feet. The feet's upper caps sit inside the torso.
- The head/ear cage retains 4,390 quads and two small repair triangles. Local
  volume filling and vertex redistribution soften the attachment recesses;
  bounded crown and rear-surface fairing smooth the profile. The retained
  repair changes vertex positions, not the cage topology. Trial replacement
  patches were discarded; no overlay patches remain. The body and feet are
  unchanged from the preceding saved checkpoint.
- The torso/arm cage has 4,313 quads and 698 triangles. Folded internal shoulder
  faces were removed, the joins rebuilt, and the surrounding surface faired.
  The feet retain their original longitudinal quad loops and small end fans.
- Subdivision remains unapplied: level 1 on the head/ears and torso/arms, level
  2 on the feet. Eyes and brows are separate surface meshes. Each eye now has
  a fine closed iris rim and a separate mirrored, open outer arc with a
  lower/inner gap and tapered ends. The filled outer oval and white inset were
  replaced. Iris/glint/brow positions in the front projection are retained;
  their depth was re-seated on the evaluated facial surface. There is no nose,
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
`source/front_preservation.json` compares the evaluated front silhouette with
the preceding saved checkpoint (`68943262`). Its silhouette overlap is 99.32%;
body/arm and foot cage coordinates and all principal face connectivity are unchanged.
This geometric comparison measures preservation, not artistic acceptance.

## Before rigging

User visual approval is mandatory. Small temple dimples and pinched rear-root
depressions remain visible, especially in SIDE, HIGH SIDE and HIGH REAR. The
crown transition is smoother, but the roots are not yet clean from every angle.
These are outstanding modelling issues, not accepted details. Compare those
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
