# Usu authoring asset

`Usu_Static_Approval.blend` is the editable, unrigged character source. This
directory is authoring/review material and has no SRPSS runtime consumer.
The live approval checklist is in `../../Current_Plan.md`; the filename does
not assert visual acceptance.

The art direction is the asset section and approval gates in
`../../Docs/Future_Work/Usu_Moonscape_Visualizer_Future_Plan_f104a29eec.md`.
Its runtime proposals remain deferred. The supplied approved turnaround is
`../../tmp/UsuForModelling.png`, packed inside the `.blend`. No original novel
drawings were available during this session.

## Editable geometry

- Four closed principal surfaces: joined head/ears, torso with connected arms,
  and two separate rounded feet. The feet's upper caps sit inside the torso.
- The head and ears were shaped from the reference profiles, joined at their
  broad upper attachments, retopologized with symmetric QuadriFlow, welded,
  and smoothed at the rear roots. Its cage has 4,390 quads and two small repair
  triangles. The torso/arm cage uses sewn quad loops; the feet have longitudinal
  quad loops and small end fans. No leg ports distort the belly or profile feet.
- Subdivision remains unapplied: level 1 on the head/ears and level 2 on the
  torso/arms and feet. Eyes and brows are separate simple
  surface meshes; there are no sockets, nose, mouth, fur, toes or tail.
- Smooth matte neutral clay, charcoal hands and simple eye materials expose
  the shape without surface texture. The reference's ear greys and body
  highlights are interpreted as shading, rather than new markings.
- Z is up; front faces -Y; height is about five arbitrary authoring units.
  Final engine units and export conventions have not been established here.

Edit the `.blend` directly; it is the single modelling source. The rejected
procedural builder has been retired. `source/review_static_usu.py`, executed
through Blender MCP from this open file, checks the principal surfaces,
renders the four views, and saves the `.blend`. It does not replace geometry.

## Review images

All individual views are 1000 × 1200 PNGs at the same orthographic scale:

- `renders/Usu_front.png`
- `renders/Usu_side.png`
- `renders/Usu_back.png`
- `renders/Usu_three_quarter.png`

The 3/4 camera has a modest elevation and a roughly 22-degree horizontal angle guided by the
illustration. `renders/Usu_Static_Views.png` arranges all four renders.
`renders/Usu_Reference_Comparison.png` places the approved illustration above
the current model, with comparable character heights. This layout is composed
by `source/compose_review.py` without altering either image's content.

## Before rigging

User visual approval is mandatory. Review the overall head/body balance,
the broad upper ear attachments, gentle flop and lower thickness, arm/foot
shapes and placements, and the cheek depth in 3/4 and profile. The profile eye
still reads narrower than the drawn side eye, and the rear ear-root transitions
need particular visual review. Future ear deformation and the feet's hidden
root overlaps have not been tested; approval of the static model comes first.
A single welded whole-character mesh is not assumed.

`source/mesh_validation.json` records direct Blender checks of the principal
surfaces: closed/manifold edges, no loose vertices or zero-area faces, and no
armatures, armature modifiers or animation actions. These checks do not prove
visual likeness or future deformation quality. No rig, animation or engine
asset export has been created.
