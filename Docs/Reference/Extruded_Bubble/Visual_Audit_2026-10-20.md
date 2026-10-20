# EB visual audit — rejected native result

One user-authorized Astra High reviewer inspected the three supplied targets, the lab comparison sheet,
P1/P7 full native frames and their contact sheets. No edits or new captures were made by the reviewer.
The primary retains implementation ownership. Paths below are exact source at this audit, not permanent line IDs.

**Verdict: reject.** P1 has repeated bright interior blobs and near-white rims instead of coherent depth.
P7 has busy luminous near lenses, dark disc-like far bubbles and an artificial upper-right dot lattice.
Pinhole off-axis elongation does not explain these material failures. Important specks must remain.

## 1. Near-defocus highlight grid — strongest immediate attribution

`rendering/quick/scene3d/defocus.py:129–144` places highlight sprites at mip-texel centres. The sampling mip is
chosen from maximum blur radius, but individual circles as small as 1.5 px are admitted. EB's 1440p budget
selects mip level 3: 8-pixel spacing, with centers at residues 3/4. Numeric inspection of the existing P7
`frame_0090.png` upper-right ROI confirms bright dots locked to 8-pixel rows and columns at those residues.
The lattice follows a large shell edge. This is strong source/image attribution, not yet the causal A/B.

**Next falsifier:** freeze this exact snapshot and change only the existing near-highlight split. Preserve
all particles/geometry and their light energy. The predicted lattice should disappear without erasing detail.
Do not change emitter density to conceal a defocus sampling defect.

## 2. Conflicting background and light refraction

`extruded_bubble_program.py:506` replaces the hollow-shell transmitted direction with a solid-sphere
background lens using `1/uIors.x`; line 518 uses `uIors.x/uIors.z` for transmitted light. Current indices
(1.15, 2, 1) mean approximately .870 versus 1.15: opposing background/light lens conventions. The source
describes the replacement as antialiasing accommodation. A shell tracer's existence does not prove coherent
air-shell refraction. Transmission also projects to fixed `uBehind=8`, not the actual rear scene depth.

**Next falsifier:** use the existing diagnostic modes on central and near ordinary shells with a recognizable
background feature. Compare background and hollow-shell exit directions before changing rim/glow multipliers.

## 3. Refracted background omits rear bubbles and trails

The renderer captures background after water/additive specks, before ordinary shells/unions/chains/snow/wakes
(`rendering/quick/visualizer/implementations/extruded_bubble.py:457–475`). Those rear populations cannot enter
another shell's transmitted background. OIT overlap is not refraction of rear geometry. The targets rely on
layered distorted interior detail, so raising speck brightness cannot supply the missing information.

**Next falsifier:** a fixed near/far two-shell and microbubble-layer scene, retaining correct world identities,
must show the rear recognizable feature bending through the front shell. Extend the existing pass ownership
only as the demonstrated requirement needs; do not add a second compositor.

## 4. Reflection proxies and analytic light ownership

`extruded_bubble_scene.py:235` makes an ordinary-shell proxy with radius .6× its owner. The shared eye-origin
probe does not exclude the shell later sampling it, nor enforce a small angular glint. All bubbles sample
this directional environment. Repeated bright interior marks plausibly come partly from these proxies;
dominance needs isolation. Separately `_glass` at renderer line 269 sets analytic specular to
`light_colour*300` independently of authored `light_strength`, while backdrop/probe light does consume strength.
The inconsistent control consumer is source-proved.

**Next falsifier:** isolate proxies and analytic specular separately on one immutable scene, sweep the existing
Light Strength endpoint, and inspect actual reflected output. Avoid combining several material changes.

## 5. Continuous union silhouette, approximate union optics

Cluster shading (`extruded_bubble_program.py:729–740`) builds a tangent sphere at the union hit point using
the nearest member's radius, then calls ordinary sphere shading. It does not trace entry/exit through the
continuous union. Member radius can switch at the neck even where the union normal is smooth.

**Next falsifier:** inspect one unequal-radius union through a small camera movement. Check normal continuity
and optical continuity independently. The supplied frames do not isolate a union well enough to prove a seam.

## 6. Particulate depth and source organization

Actual specks use a fixed world domain; the grid is not evidence of camera-spawned particles. Their additive
Gaussian/angular lighting lacks explicit distance absorption and focus-dependent blur, preserving intense
far dots that near shells magnify. The target distinguishes smoky illuminated streams, sharp mid-distance
microbubbles and soft foreground particles. Free chains also remain procedural segments rather than fully
authored localized stream volumes. Increasing global counts cannot create that organization.

Reactivity, native timing and idle speed are separate gates; stills cannot accept them. Follow the live plan,
and retain these exact targets and failed captures in this folder when testing each correction.
