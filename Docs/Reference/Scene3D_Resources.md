# Shared scene3d GPU resources

The retained Quick transition host remains the render owner. `rendering/quick/scene3d/` supplies context-local,
lazy resources; it does not create a clock, scheduler, global texture cache or alternate renderer. All admitted
operations require the validated OpenGL 4.6 context. PyOpenGL DSA creation calls use explicit output arrays.

## Rejected Extruded cast-shadow receiver and Scene3D camera (R-120/R-121 consolidation)

Early E8 receiver attempts produced triangular near-footprint casts or a corner-only sliver even at long distance. A translated top cap is **not** the requested cast: any future operator-approved design must sweep from the bar base footprint toward the shifted upper silhouette, stay visible without gigantic side smear, and respect screen-edge clipping and overflow without shrinking the authored Spectrum geometry. These experiments remain rejected/disabled; see `Docs/Historical_Bugs/R-125_to_R-128_Extruded_Cast_Shadow_Failure.md` for the full negative history. Sphere's turn/tilt/box and Edit cage share the live Scene3D pose authority, not preset-managed camera copies. The E8-era Python 3.13 sequencing and two-original WebP paths were superseded and are **not** current product instructions.

## Shared framed-camera and transparent-scene admission contract

The **implemented Neon Lake internal view** establishes the behavior to generalize, not a new camera subsystem.
Before Extruded Bubble, §4A FC must promote the existing `view_orbit_settings`, optional
`scene_transform_settings`, gesture admission and projection/fit helpers into one opt-in **framed 3D camera
capability**. The outer retained card and CUSTOM stage remain fixed, while its content orbits/pans/zooms inside
CARD_INTERIOR. Mode declarations supply bounds, pivot, pan/zoom safety, fit and near-plane behavior; do **not**
globalize landscape angles, wrap bounded modes, give future modes copied camera controllers or change unframed 3D
behavior. Save camera view under the existing presentation authority, not the art presets or layout profile.

Before a consumer with overlapping translucent geometry, prove these **separate, lazy shared primitives**:

- **G1 attachments/depth:** context-local normal/material/depth/history only where used; exact target/format,
  clear/resolve/state, resize and context-lifetime ownership. Render-to-card alpha, sky/foreground occlusion,
  translucent depth ordering and GL-state restoration are validated on real pixels.
- **G3A transparent compositor:** opt-in order-independent blending for multiple translucent surfaces, correct
  opaque/depth interaction and emitted-light resolve. Rendering order is an explicit contract; do not transplant
  Neon Lake's special-case glass logic into another mode or substitute an EB-only transparency path.
- **G2 fitted real shadow maps:** one shared directional caster/receiver/depth-map owner with measured tiers,
  independently proved after G1. This does **not** authorize reenabling the rejected Extruded Spectrum shadow.
- **G3B optics:** opt-in, target-justified Fresnel/rough transmission, thickness/refraction and restrained
  dispersion, following G3A. Existing material math should be reused; any omitted feature remains deferred,
  not a silent EB-local implementation.

G0 measures the exact existing delta before these additions. Their opt-in allocations, shaders and per-frame work
must be absent for all inactive consumers. Validate opposite-order overlapping sphere renders, near-plane crossings,
window/card resize and mixed DPR, alpha/depth/bloom agreement, context-loss/retirement, dual-display and
CPU/GPU budgets. Shared primitives may be proved by small test scenes without shipping a fake consumer. G4 particle
ribbons and G5 volumes are demand-driven separate gates. `Current_Plan.md` §4A is the live implementation checklist;
`Docs/Reference/Visualizer_Reference.md` owns visible/view-pose semantics.

## Static meshes and per-draw image bindings

`MeshResources` owns named programs, uniform locations and static interleaved meshes. A mesh's VAO and VBO use DSA
construction and immutable buffer storage with flags zero. Construction does not change generic VAO/array-buffer
bindings. Handles enter the existing owner before storage/upload; incomplete allocation remains a loud error until
release, and failed deletion retains its handle for retry. A later successful release permits clean recreation.

The existing per-linked-program uniform cache also owns immutable image-sampler descriptors and one-time sampler-unit
assignment. `bind_frame` uploads the current matrix/item size and binds current source/destination texture IDs with
one `glBindTextures` call. There is no texture-binding cache: Qt may have changed inherited state between calls.
Frame admission already requires positive source/destination names; the binding helper never fills gaps with zero
names, which would unbind all texture targets on that unit. Program retirement also retires sampler initialization.

Two-sampler warm passes remove five Python-to-GL calls. A bounded local measurement (32×32 offscreen context,
7 batches of 4,000 warm `bind_frame` calls, sampler initialization excluded) measured 41.56 → 28.91 microseconds
median per call. This measures only frame binding, not whole-transition FPS or loaded-desktop tails. Static DSA mesh
construction alone is not claimed to improve steady frames.

## Opt-in authored heightfields

`scene3d_grid_points` supplies unique UV vertices for an optional point presentation. Consumers draw the same displaced
lattice as their surface triangles, retain real depth/occlusion and own the lazy mesh with MeshResources. A consumer that
uses edges only acquires no point mesh or point-size state work.
Both grid helpers accept an optional bounded front extension; default consumers keep the original UV domain/data.
An extended mesh's near controls sample clamped authored data, with identical point/triangle UV coordinates.

`rendering/gl_programs/heightfield.py` and `heightfield_glsl.py` share bilinear authored-zero water classification and
opt-in positive cubic B-spline surface sampling, over the existing bendable mesh. Fragment-only helpers supply curved
surface wire coordinates and contours; tessellation edges are not the artistic wireframe.
Only admitted heightfield consumers import/use these primitives. `rendering/quick/scene3d/heightfield.py` owns one lazy
immutable R32F or explicitly requested RG32F texture per consumer/context, with upload-on-change and explicit
unpack/texture/sampler restoration. The optional second channel holds authored distance to bilinear land support;
its bounded separable distance transform runs at configuration, never on the logical or render clock.
Failed release retains the owned handle for retry. There is no shared simulation, clock or global texture cache.
`heightfield_volume_glsl.py` supplies opt-in bounded single scattering over that same sampler. High/Balanced/
Performance/KAK admit 12/8/6/4 world-ray steps with four coarse light-occlusion taps each, at most 60 height samples
per fragment. Density fades from water/lower slopes with world height; zero strength returns transparent black.
Thin ridges between taps may be missed, and this is not a shadow map or a fluid simulation. The consumer reuses its
target/program/quad and owns admission; no volume texture or independent clock is created. Unrelated consumers
do not import this shader fragment or acquire its work.
Neon Lake Basin's source/authoring contract lives in `Docs/Reference/Neon_Lake_Basin.md`; its cost/fidelity gates remain
in `Current_Plan.md` until measured and accepted.

## Photo reflection resources

`PhotoEnvironment` owns its photo copy, immutable texture and framebuffer. Named construction allocates the complete
mip chain (`max(width, height).bit_length()` levels), preserves the existing sampler parameters and generates mipmaps
on the owned texture. It never alters the lent presentation photo. The existing per-run identity reuses a completed
copy; `park()` retires it. Actual copy drawing still binds its framebuffer and restores draw/read framebuffer,
viewport and scissor state.

Allocation and copy failures invalidate the cache identity and retire the incomplete texture. A failed deletion keeps
its name with this owner for release retry; a partially written image cannot become a valid cached reflection.
Named construction removes three owned-texture active/bind calls from allocation plus first copy. This is a bounded
construction saving, with no measured steady-frame FPS claim. Eighteen representative Block Spins / Glass Shatter
captures matched the preceding implementation byte-for-byte.

## Fixed-size scene and post-process allocations

The existing target, bloom, motion and trail owners construct named framebuffers and immutable textures at their
known allocation size. Named attachment/status/draw-buffer operations replace allocation-only framebuffer queries
and binds; depth renderbuffers also use named storage. Rendering and resolve passes keep their state restoration.

| Owner | Storage and allocation contract |
| --- | --- |
| `SceneTarget` | RGBA8 colour, optional RG16F velocity and depth24; existing multisample count and 64-pixel size buckets ; an **overlay** scope (a Visualizer drawn over its card) clears to transparent and composites the resolved scene back as straight alpha times an opacity, discarding where nothing was drawn, with no motion blur. An overlay **with bloom** adds an RGBA16F emission attachment (location 1, written only inside `emission_writes()` as `sceneEmission(light)`), blurs it through the shared bloom chain and composites premultiplied with the glow added, under a blend it sets and then hands back as the caller had it (captured at `begin`), so glow is exactly additive over what Quick drew and no emission writes means no glow. The non-bloom overlay path is unchanged |
| `SceneTarget` depth texture and background (§4A G1, 2026-10-17) | `depth_texture=True` makes the depth attachment a DEPTH_COMPONENT32F texture (multisampled with the colour) instead of the depth24 renderbuffer; drawing is pixel-identical. `background()` captures, mid-scope, what has been drawn so far into a plain RGBA8 colour (averaged over samples) and an R32F nearest window depth (the far plane without a depth texture), then hands drawing back where it was (draw framebuffer, viewport, colour masks 0-1, blend, depth test, program, units 0-1). Allocated on first use or by `warm(..., background=True)` as one unit; released with the target |
| `SceneTarget` order-independent transparency (§4A G3A, 2026-10-17) | `oit=True` adds an RGBA16F accumulation and an R16F revealage (multisampled with the colour) in their own framebuffer, sharing the scene depth (tested, never written) and, with bloom, the emission attachment at location 2 (added). Passes inside `transparent_writes(frame, resources)` write `sceneTransparent(premultiplied, alpha, view_depth)` (`SCENE_OIT_GLSL`: weighted blended OIT, McGuire-Bavoil equation 10 on view depth); leaving resolves per sample (`gl_SampleID`) over attachment 0, premultiplied, alpha added on overlays (coverage) and only dimmed otherwise (emitted brightness), then restores blend (indices 0-2), colour masks, depth test and depth mask |
| `SceneTarget` light shafts (2026-10-17) | `shafts=True` (overlays only) adds an R16F shaft-source attachment at location 2, written only inside `shaft_writes()` (colour and emission masked there); a `ShaftLight` set during the scope makes `end` run `LightShafts` (half-size resolve plus two 16-tap radial gathers into two R16F levels) and composite through `_with_shafts`, the one transform of the overlay composite that adds the rays where the scene drew. Without a light that frame, the overlay composites as before |
| Bloom | Four progressively halved RGBA16F levels, allocated with the requesting target |
| Motion | One RG16F compute-written tile-max image (no framebuffer) and one RGBA8 output, using existing tile and target sizes |
| Motion Trails | Existing R8 mask, allocated only for its active requesting consumer |

Names enter their current owner before parameter/storage calls so an exception cannot strand an untracked resource.
Resize and `park()` release the same owned names; size reuse creates no replacement allocations. Features that are
Off acquire no resources. No second pool, background preparation cadence or binding cache is introduced.

Focused real-context bars cover immutable storage, framebuffer completeness, inherited construction bindings,
partial-allocation cleanup, resize/reuse and the existing disabled/parked lifecycle. Eighteen representative Block
Spins / Exploding Tiles captures matched the preceding implementation byte-for-byte. These checks establish the
allocation and pixel contracts; ordinary two-display loaded-desktop observation remains in `Current_Plan.md`.

## Per-frame stream ring and std430 storage (S14)

`StreamRing` (`stream.py`) carries small payloads that change every frame. One immutable buffer is created with
`glNamedBufferStorage` and mapped once, write-persistent-coherent; a payload is one `memmove` into the mapping and one
raw `glBindBuffersRange` of its aligned range (uniform alignment 256, storage 16 on the RTX 4090). Multi-bind never
changes the generic buffer binding, so `bound` saves and restores only the indexed point (its range, or a whole-buffer
binding). Coherent mapping needs no flush call; explicit flushes would add one call per write and were not adopted.

Capacity is fixed: four 16 KiB slots, at most 4 KiB per outermost `bound`. Writes advance through the current slot;
slots rotate only when every `bound` has exited, because each exit restores the previous binding and no later command
can read the ring. Rotation places one fence on the slot it leaves and, before writing a slot again, waits on that
slot's fence (one bounded blocking `glClientWaitSync`, never a poll; a second's wait is a loud error). At Exploding
Tiles' sizes a fence is placed every few dozen frames. Exceeding the per-frame capacity raises; nothing is overwritten
silently and nothing grows.

`UniformBlock` streams through a ring: a renderer passes its blocks one shared ring and releases it itself (a block
without one owns a private ring). `update_fields` writes a patched copy and rebinds it, so draws already submitted keep
their values. Exploding Tiles' frame and ghost blocks share one ring, allocated by its gradual warm-up rather than its
first frame, kept warm across `park()` and released with the renderer. A ring nobody writes allocates nothing.

`Scene3DStorageLayout` (import-safe, `rendering/gl_programs/scene3d.py`) declares one std430 record array: GLSL struct and
buffer block, member offsets, record stride (rounded to the largest member alignment only, so three floats stride 12),
`pack(records)` and an equivalent numpy structured `dtype()`. Records bind through the same ring at a consumer-chosen
storage binding. Sphere's bounded section drives and cohort arrays instead travel together in its shared
`SphereFrameBlock`: `Scene3DBlockLayout` supports fixed-size std140 scalar/vector/matrix arrays with their standard padded
strides. Hero and projected-shadow programs share that declaration and one renderer-owned ring. Intake uses one bounded
scope with distinct immutable shadow/hero copies; outtake uses bounded per-layer scopes with its extra pass patched inside
each. Program attachment is allocation
free, prepared reveal warms the ring only for admitted Sphere, and the normal renderer retirement releases it. The detailed
consumer/ownership contract is in `Sphere_Visualizer.md` → Shared frame upload and retirement.

Measured (960x540 offscreen Exploding Tiles, three interleaved HEAD/new process pairs, 210 warm frames each, flush per
frame; 28 frames across four setups byte-identical): GL calls per frame 215 -> 211 by default and 281 -> 267 with Motion
Trails; CPU submit median 1.19-1.26 -> 1.23-1.27 ms by default (neutral), 1.80-1.84 -> 1.70-1.72 ms with trails and
2.09-2.15 -> 1.94 ms with trails and motion blur (p90 2.79-2.97 -> 2.33-2.38 ms). The removed work is the per-frame
buffer re-specification, the generic-binding query/restore and three sub-data writes per trail ghost.

## Compute seam and first consumer (S15)

`compute.py` is the whole seam: `dispatch(groups, barriers)` takes explicit workgroup counts and the barrier bits its
readers need, and issues that barrier straight after the dispatch (the writer owns it; readers never know a writer
exists). `bound_image(unit, texture, access, format)` binds level 0 of an owned texture for the scope and hands the unit's
previous binding back (name, level, layering, access, format), because the transition host does not fence image units.
`MeshResources.compute_program` compiles through `compile_compute_program` (shared link/cleanup with graphics programs)
and `warm_programs` accepts `(resources, key, compute_source)` entries, so compute programs are gradual warm-up steps.
No queue, scheduler, worker, readback or polling exists: work runs on the owning render thread in the frame that uses it.

**First consumer: motion blur's tile max.** The candidates were measured first (2560x1440 offscreen, RTX 4090):

- Particles: Exploding Tiles' 480 sparks are analytic and culled in the vertex shader; compute evaluation would add a
  dispatch and a barrier to an already cheap pass.
- Active-piece compaction / indirect counts: every 3D transition is at most 0.3 ms whole-frame GPU (median), its
  instanced populations are single draws, and per-frame CPU (0.6-1.6 ms) is state save/restore, not draw loops.
- Exploding Tiles' dominant body colour (0.93 ms of render-thread Python per run per display): a GPU result must be
  bound every frame (about 8-15 us), more total CPU per run than the scan it removes.
- Bloom: still one pass per level with a barrier each, so compute removes no calls.
- Motion blur's separable tile max (two fragment passes into two targets) and neighbour max (a third) were the one
  consumer where compute removes passes, targets and calls for every admitted shared-Scene3D transition that enables Motion Blur.

The tile max is one dispatch, one workgroup per K x K tile: an invocation per tile row finds the first strictly longest
motion left to right, then the first invocation takes the first strictly longest row top to bottom, which is exactly
the separable column-then-row scan (ties and partial edge tiles included). The gather takes the 3 x 3 neighbourhood
maximum of the tile image itself (same scan order). Values are RG16F velocity texels stored back unchanged. Tile
rows are held in a fixed 256-row shared array; a target needing larger tiles (over ~10,000 px high) is a loud error.
The dispatch issues `GL_TEXTURE_FETCH_BARRIER_BIT` for the gather's sampled read. Motion Blur Off compiles, allocates
and dispatches nothing.

Measured on the then-current shared-3D transition cohort: 84 frames across two sizes (2560x1440; 1366x768 with partial tiles) and Exploding
Tiles' High/Balanced/trails setups are byte-identical to the fragment passes. GL calls per frame with Motion Blur fall
by 14 (Tiles 260 -> 246, Glass 191 -> 177, Crumble 199 -> 185, Accretion 183 -> 169, Block Spins 182 -> 168). Owned
memory per motion target falls by two textures and three framebuffers (about 0.42 MB at 2560x1440). Separate-process
timing was dominated by GPU clock state, so the accepted comparison alternates old and new reductions frame by frame
on one renderer (two runs of 480 frames per transition): CPU submit median -0.05 to -0.07 ms (p90 -0.05 to -0.09),
reduction stage GPU -0.006 to -0.022 ms, whole-frame GPU -0.006 to -0.020 ms with lower p90.

On this driver, dropping the barrier changed none of 30 frames: the hazard is not observable here, so the bar is the
recorded dispatch -> barrier(texture fetch) -> gather order rather than a pixel failure.

## Compacted GPU populations (S16/S18)

`CompactedPopulation` (`population.py`) holds a large deterministic pool whose live members change every frame. A
consumer supplies two GLSL hooks over a member id, `populationActive` and `populationState` (one `vec4` per live
member), reading its own uniforms. Each frame, three dispatches run:

- **count:** each 256-member workgroup counts its live members.
- **scan:** one 1024-invocation workgroup turns the counts into each group's first slot and writes the indirect command
  (vertices, live count, 0, 0) itself.
- **scatter:** a workgroup prefix sum gives each live member its slot; the member writes its id and its state there.

The draw is one `glDrawArraysIndirect` reading `populationIds` and `populationStates` (`POPULATION_DRAW_GLSL`).
Properties:

- **No readback:** the live count never returns to the CPU.
- **Stable order:** slots follow id order (no atomic append), so membership changes never reorder survivors and
  order-dependent blending is identical every frame and on every GPU.
- **Writer-owned barriers:** each dispatch issues the barrier its reader needs: storage reads for the next pass, and
  storage plus command reads for the draw.
- **Fixed capacity:** five immutable buffers (counts, offsets, command, ids, 16-byte states) per allocation. A larger
  population is a loud error.
- **Bindings restored:** `bound` binds the five storage points from 3 and the indirect buffer with one multi-bind, and
  restores them, querying a point's range only when something is bound to it.
- **Uniforms:** the population's own uniforms are set only when they change; the consumer's frame values stay its own
  (Disintegrate streams them as one uniform block).
- **Dormancy:** nothing is allocated before a consumer warms it; consumers release it at `park()`.

**First consumer: Disintegrate** (up to 600,000 grains). The alternative that already-shipped effects use is to draw
the whole pool and evaluate each grain in the vertex shader, culling dead ones. The comparison below alternated that
reference path with the compacted path frame by frame on one renderer (RTX 4090, pixels equal apart from isolated
edge pixels in one Balanced case, where compute and vertex arithmetic round differently):

| Size, grains | GPU, compacted / reference (median) | CPU submit, compacted / reference |
| --- | --- | --- |
| 2560x1440, 410k, High | 0.154 / 0.245 ms | 0.68 / 0.57 ms |
| 2560x1440, 410k, Balanced | 0.130 / 0.224 ms | 0.49 / 0.39 ms |
| 3840x2160, 518k, High | 0.244 / 0.342 ms | 0.66 / 0.55 ms |
| 1920x1080, 518k, Balanced | 0.137 / 0.266 ms | 0.49 / 0.39 ms |

Compaction removes 29-49% of the GPU work: each live grain is evaluated once instead of once per vertex, and dead
grains never reach the vertex stage. That saving grows with the population and on GPUs where vertex work is
expensive. It costs a fixed ~0.1 ms of CPU submit (about 20 calls: three dispatches, barriers, bindings). On this
GPU the two paths are close in total; the decision rests on the GPU side scaling with hardware and population while
the CPU side stays constant. A future consumer with a smaller pool should be measured the same way before using it.

## Edge fields (contour distance)

`rendering/quick/scene3d/edge_field.py` derives, once per run and photograph, a field of the distance to the
picture's nearest structural contour and that contour's strength (RG16F, linear) from the lent presentation texture:
luma copy, two binomial blurs, Sobel ridges after non-maximum suppression (seeded at their sub-texel ridge position), jump flooding on 32-bit positions, resolve. Seven dispatches
plus one per flood step, on the render thread in the frame that first needs it; image units are scoped by
`bound_image`. Six textures at 768 px on the longer side (about 8.6 MB at 16:9: three R16F, two RG32F flood buffers, the RG16F field), allocated by the consumer's warm-up
for the render size and dropped at its `park()`; nothing exists otherwise. `edge_field_reference` is the CPU mirror
(tests compare ridges and flooded distances). First consumer: Edge Bloom Reveal. Seeded differently it can serve
organic fills (Capillary Bloom, Surface Tension Merge).

## Propagation fields (geodesic arrival)

`rendering/quick/scene3d/propagation_field.py` derives, once per run, the cheapest cost-weighted arrival from a few
sources over a consumer's GLSL cost function (`propagationCost`): a seed stage (cost plus a straight-line upper bound),
192 in-place relaxation passes over a 16-neighbour stencil (monotone, so read races only speed convergence) and a
one-workgroup reduction to the largest arrival in a 1x1 texture consumers read with `texelFetch`. Three R32F textures,
256 px on the longer side (about 0.3 MB at 16:9), allocated and built by the consumer's gradual warm-up in bounded steps
(48 passes per step) because the cost depends only on the run's seed and the render's aspect, and dropped at its
`park()`; nothing exists otherwise. `propagation_reference` is the CPU mirror. First consumer: Capillary Bloom.

## Sphere impostors (§4A, 2026-10-17)

`rendering/gl_programs/scene3d_spheres.py` (import-safe GLSL + CPU mirrors) draws exact spheres from one view-space
quad per instance: `sceneSphereCorner` sizes the quad to the silhouette cone through the centre
(`(r + blur) d / sqrt(d^2 - (r + blur)^2)`, collapsed when the eye is inside), `sceneSphereRay` intersects the view
ray, `sceneSphereCoverage` antialiases the silhouette (or softens it over `blur` for defocus) and `sceneSphereDepth`
writes the true surface depth, so interpenetrating spheres meet along their real intersection. View space has the eye
at the origin looking down -z; consumers supply their own placement and projection. No resources: a consumer's own
instanced draw and program. Proven by `test_scene3d_spheres.py` (GPU id/depth picture equals a CPU ray cast apart
from under 1% edge pixels, silhouettes within 1% of the analytic area from 1.5 to 0.02 radius, blur widens and softens
the edge) and `test_scene3d_spheres_mirrors.py` (GLSL equals the mirrors).

Round on screen (2026-10-17): a rectilinear view draws an off-axis sphere as an oval stretched toward the frame's edges.
`sceneSphereScreenCorner` (vertex) places a screen-aligned square round the projected centre, sized to the apparent
width across the line of sight, and `sceneSphereFacingRay` (fragment) gives the view ray as if the sphere were seen
straight along the line to its centre, so every sphere is a circle wherever it sits (deformation is reserved for
collisions). The mirror test proves every unit-circle corner grazes the silhouette.

## Scene probe (§4A, 2026-10-17)

`rendering/quick/scene3d/probe.py`: `SceneProbe(label, size)` owns one RGBA16F cube with a full mip chain, a depth
renderbuffer and a framebuffer. `capture(draw)` renders the six faces (GL's cube convention; each face's 3x3
world-to-view rotation and a 90-degree projection are handed to the callback), then pre-filters every mip level from
the one above over a Gaussian cone (32 taps, sampled across face edges, about two texels of that level wide), so
blurred lookups are a smooth, rotation-invariant filter (GL's per-face mipmaps read as blocks). The caller's
framebuffer, viewport, scissor, clear colour, depth, blend, program, vertex array and unit 0's cube binding come back;
nothing is allocated after the first capture. GLSL `sceneProbe(probe, direction, blur, levels)`. It is how glass,
water and bubbles show the scene they sit in (the light, beams, lit particulate) instead of painted highlights.
`test_scene3d_probe.py`: face rotations follow the cube convention, every direction reads back what the scene put
there (with a mirrored-face negative control), blur is the same filter across faces and full blur is the hemisphere,
state and allocation.

## Defocus layer and HDR scenes (§4A, 2026-10-17)

`rendering/quick/scene3d/defocus.py`: `DefocusLayer` is depth of field for objects near the lens. `begin(w, h)`
binds an RGBA16F premultiplied colour and an RG16F alpha-weighted circle of confusion (both mipmapped); the caller
draws its near objects sharp with `SCENE_DEFOCUS_GLSL` `sceneDefocusWrite(premultiplied, alpha, cocPixels)`; `end()`
hands back framebuffer, viewport, blend and depth state; `composite(max_radius)` spreads every pixel evenly over its
own circle (64 golden-angle taps, each read from the mip level matching the taps' spacing so no source pixel is
missed, weighted by 1 / its circle's area so light is conserved) and lays the result over the bound framebuffer.
A near transparent object should write only its own light (reflections), so the scene behind stays visible.
Highlights (`composite(max_radius, highlight=0.25)`, 2026-10-18): the fixed taps catch a small bright source
unevenly at a coarse read level (striped, blocky blobs where a lens draws a round disc). Light in a texel of the read
level above the floor and above the mean round it (two levels coarser) is taken out of the gather (a clipped copy of
that level, so gather and sprites split the same texels and light is kept) and drawn as one instanced disc per such
texel, of its circle, antialiased and slightly brighter at its edge. Cost in the bubble lab: within noise of the
gather alone (~0.05 ms).
`test_scene3d_defocus.py`: a bright point becomes an even filled disc of its circle holding its light, a sharp pixel
stays exactly in place, state comes back, nothing is left after `release`; a highlight under a wide circle is one
even round disc (and the gather alone, the case it guards, is measurably lumpier).

`SceneTarget.scope(..., hdr=exposure)` (overlay with bloom only): colour, background capture and resolve are
half-float, so light brighter than white survives for every pass that reads the scene (refraction, reflection,
bloom), and the overlay composite tone maps it once (ACES fit) at that exposure to an ordinary display. This is HDR
rendering, not an HDR display. Without `hdr` everything is as before. `test_scene3d_target.py` proves light past
white in the background capture and a smooth monotonic tone curve, single- and multisampled.

## Shared optics and underwater light (§4A G3B, 2026-10-17)

Import-safe GLSL + CPU mirrors, no resources. `scene3d_optics.py`: `sceneFresnelDielectric` (exact unpolarised, total
internal reflection past the critical angle), `sceneThinFilm` (two-beam interference with the inner reflection's half
wave, seven wavelengths folded into RGB) and `sceneSphereRefraction` (in at the front, out at the back of a homogeneous
sphere). `scene3d_water.py`: `waterWaves`/`waterNormal` (eight golden-angle deep-water waves, height and gradient),
`waterCaustics` (two layers of moving Voronoi edges on the shared hash), `waterSurfaceFromBelow` (Snell's window with
transmission and refracted sun glare, a mirror of the deep outside it) and `waterMedium` (per-channel absorption and
in-scatter). `test_scene3d_optics_water.py` holds each to its mirror and its physics (Fresnel at normal incidence and
past the critical angle, no colour without a film and shifting fringes with thickness, an air sphere passing the axis
straight and spreading the rest, wave gradients equal to finite differences, a thin moving caustic network, the sky
overhead and the deep past the window, the medium's colour with distance).

Light paths through spheres (2026-10-17, `scene3d_optics.py`): `sceneSpherePaths` (a homogeneous sphere: front
reflection, through, one inner bounce, exact Fresnel weights) and `sceneHollowSphereTrace` (a ray traced through a
shell between two concentric spheres, outside/shell/core indices: every interface splits by Fresnel, the reflected
share handed back as a path and the refracted share followed, total internal reflection followed without loss, so
light entering a glass wall near the silhouette is guided round inside it; up to eight (direction, weight) paths, the
last the ray that leaves). Consumers look the directions up in a `SceneProbe`. Tests hold both to CPU mirrors on the
GPU, conservation, the air bubble's mirror band, straight passage with matched indices and a solid sphere's
reflection when the core is empty.

## §4A gate status (G0 inventory, 2026-10-18)

What each pre-Extruded-Bubble gate has, what proves it and what is missing. Extruded Bubble's demands come from
`Extruded_Bubble_Target.md` (§1 target, §7 recovery, §9 preset surface); its lab
(`tools/labs/extruded_bubble_lab.py`) is the consumer that exercised these primitives.

| Gate | Owner | Proof | Gap |
| --- | --- | --- | --- |
| G1 attachments/depth | `SceneTarget` (`depth_texture`, mid-scope `background`, `hdr`) | `test_scene3d_target.py`: same pixels as the renderbuffer target, background colour + nearest depth at 1/4 samples, nothing allocated unless asked, allocation reuse/resize, failure hands state back | None for Extruded Bubble (2026-10-18: resize and release of every optional attachment, a card moved from 100% to 200% scale and a 3x2 px card all match direct draws). Normal/material/history attachments: not demanded (none planned) |
| FC framed camera | descriptor `view_orbit_settings` / `scene_transform_settings`, `widgets/spotify_visualizer/view_orbit.py`, `core/settings/visualizer_view_orbit.py` | Neon Lake, Sphere, Extruded Spectrum orbit through it | Neon Lake's policies are keyed on its mode id (clamped turn, `_bounded_basin_pose` lake/sky anchors); FC needs them as per-mode declared bounds/fit/pivot so a second framed mode declares its own |
| G3A transparency | `SceneTarget(oit=True)`, `SCENE_OIT_GLSL` | `test_scene3d_target.py`: either draw order gives the same picture at 1/4 samples (ordinary blending differs by >40 levels), nearer outweighs farther, opaque depth respected, state restored, nothing allocated without `oit` | Context loss is the renderer owner's (`visualizer/item.py` retires on `sceneGraphInvalidated`; the target releases completely), proven per consumer at its EB3 (near-plane crossing proven 2026-10-18: bright HDR layers at the eye overflowed the half-float accumulation to NaN; each layer's weighted light is now capped at 2048) |
| G2 shadow map | none (planar/directional silhouettes in `shadows.py` only) | — | No fitted depth-map foundation. Extruded Bubble's target has no receiver (abyss, no seabed): not demanded by it; stays deferred until a consumer needs it |
| G3B optics | `scene3d_optics.py` (Fresnel, thin film, `sceneSpherePaths`, `sceneHollowSphereTrace`), `scene3d_spheres.py` impostors, `probe.py`, `defocus.py`, `scene3d_water.py` | mirror tests for every traced path, probe and defocus pixel tests, HDR tone curve | Rough transmission and dispersion: evaluated, not needed by the target (recorded unnecessary) |

**Baselines.** Overhead (1920x1080, all transitions and modes): `tools/baselines/overhead/2026-10-18_f4dbb4ab.json`;
it caught one shared regression from the HDR change (an exposure uniform written per frame by every overlay composite)
which is fixed. Extruded Bubble lab at 2560x1440, 4x MSAA, RTX 4090 (`--size=2560x1440`), GPU ms per pass, median:

| Scene | shafts | backdrop + particulate | shells | clusters | OIT resolve | near defocus | bloom + composite |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Mock 1 | 0.25 | 0.24 | 2.03 | 0.20 | 0.08 | 1.07 | 0.12 |
| Mock 2 | 0.23 | 0.23 | 1.83 | 0.36 | 0.08 | 0.84 | 0.11 |
| Mock 3 | 0.23 | 0.24 | 1.89 | 0.34 | 0.08 | 0.91 | 0.11 |
| Mock 4 | 0.26 | 0.27 | 2.10 | 0.28 | 0.08 | 1.17 | 0.12 |
| Abyss | 0.30 | 0.92 | 0.77 | 0.25 | 0.05 | 3.30 | 0.11 |
| Camera down | 0.30 | 0.12 | 0.90 | 0.25 | 0.06 | 0.75 | 0.11 |
| Mock 6 | 0.32 | 1.23 | 1.57 | 0.42 | 0.07 | 1.09 | 0.13 |

About 4.0–5.7 ms for a full-screen 1440p card plus the probe (0.18 ms GPU; its lab timestamp is Python submission).
Only one Visualizer ever runs, so that is the whole cost: within a 165 Hz frame (6.06 ms) with little room. Budget work
before EB3: near defocus (64 full-resolution taps; the
abyss's 3.3 ms) and the shells' rim sub-rays (~2 ms) are the measured hot spots.
An exact-looking gather early-out (skip where the coverage mip shows nothing within reach) saved <= 0.2 ms and was
not exact (half-float mips flush tiny coverage to zero: 77 pixels differed): rejected. The abyss's near-defocus time
is mostly the near giants' traced shells drawn into the layer, so the shell shading is the budget lever.
Shell cost is mostly beads: mock 2 at 1440p spends 1.84 ms on 32k shells, 0.40 ms without its 25k bead-chain
instances. Beads are 2-6 px and each runs the full 8-path hollow trace (skipping the trace only at <= 1 px, where it
is mixed away, changed nothing: few beads are that small). The EB3/EB4 budget lever is a cheaper small-bead model
(rim, light lobe and core) below a pixel threshold, judged against the mocks, worth about 1.4 ms per 1440p display.

## State restoration

The common transition fence restores 2D textures on units 0, 1 and 2, multisample textures on units 0 and 1, and the
incoming active unit. Reflections/motion use unit 2 and scene resolves use the multisample targets; neither may leak
bindings to Qt, including after a renderer raises. Existing program, VAO, array-buffer, framebuffer, viewport, blend,
depth and stencil restoration remains binding. DSA construction does not remove draw-time inherited-state duties.
The expanded fence deliberately pays for the previously missing state; the isolated binding measurement excludes it.

## Direct translucent bodies and directional shadows

Extruded Spectrum keeps its opaque body draw unchanged at body alpha 1. Below that value it draws only each box's
eye-facing faces, in the existing far-to-near bar order, with depth writes disabled; this is exact for the row's
disjoint x slabs and lets the photographed backdrop remain visible. This is not an Extruded-local OIT target.

`directional_shadow_vector()` and `directional_shadow_pass()` are target-free shared Scene3D primitives. A consumer
derives orientation only from the already-resolved canonical `widgets.shadows.direction` projection, keeps its own
shadow magnitude/strength, and draws into its existing scene target. An off shadow therefore creates no target,
program, texture or background cadence; an active shadow adds one direct silhouette draw. Consumers explicitly restore
their following body-pass depth state, and the existing visualizer fence still owns inherited Quick state.

## Change boundaries and regression routes

- `test_scene3d_resources.py`: real static mesh pixels, immutable storage, untouched generic bindings, one sampler
  assignment per linked program, correct multi-bind routing and partial-upload retirement/rebuild.
- `test_scene3d_environment.py`: complete immutable mip storage, reflection pixels, borrowed-photo immutability,
  construction state isolation, failed-copy invalidation and allocation/deletion retry.
- `test_scene3d_dsa_targets.py`: real immutable scene/post storage and completeness, untouched active texture and
  draw/read framebuffer bindings, and injected partial-allocation failures that leave no owned names behind.
- `test_qtquick_transition_state_fence.py`: deliberately non-default state restoration on success/failure, plus real
  reflection and multisample texture sentinels across a scene pass and a thrown renderer.
- `test_qtquick_bootstrap.py`: each required entry point must resolve on the actual context; no frame-time probing.
- Existing transition warm-up, scene foundation, target, environment and Motion Trails tests protect pixels,
  gradual preparation, parked resources and disabled-feature dormancy across registry-discovered shared-Scene3D transition consumers.

- `test_scene3d_stream.py`: driver-reported std430 offsets/strides equal the layout and values arrive through the
  ring; indexed ranges restored and generic bindings untouched for uniform and storage targets; every reused slot
  waited on its fence with each of 48 unsynchronised frames reading its own values; fixed loud capacity; a dormant
  ring makes no GL call; failed deletion keeps its handle, release returns to zero and rebuilds; a failed mapping
  leaves no buffer.
- `test_scene3d_uniforms.py`: std140 layout and values, previous binding handed back, and draws before an
  `update_fields` keep their values.
- `test_transition_warmup.py`: counts ring allocation as a warm-up unit, so a run's first frame cannot allocate it;
  it counts compute compiles too (leaving the tile-max program out of warm-up fails ten motion-blur cases).
- `test_scene3d_population.py`: live ids, slots, states and the indirect count equal a CPU reference exactly from 1 to
  300,000 members (a broken scan fails), survivors keep their order when membership changes, the indirect draw draws
  exactly the live members, barrier order and bits, fixed loud capacity with bindings restored, a dormant pool makes no
  GL call, release/rebuild.
- `test_scene3d_compute.py`: the compute tile max equals the column-then-row reference exactly on random, tied,
  single-texel and still fields with partial edge tiles (a non-strict tie rule fails it); the dispatch is followed by a
  texture-fetch barrier before the gather; dispatches name groups and barriers; image units come back (bound or
  unbound, after a failure, and across a real motion-blurred frame); runs without Motion Blur compile and dispatch no
  compute for every covered transition consumer; fixed loud tile capacity; release returns to zero and rebuilds; failed compute
  compiles/links leave no shader or program.
- `test_scene3d_target.py` (G1, shafts): a depth-texture target draws the same pixels as the renderbuffer one; its
  mid-scope background holds the colour and nearest depth at 1 and 4 samples and drawing resumes exactly where it was;
  targets that ask for neither allocate no depth texture or background; the shafts composite is one transform of the
  overlay composite and its programs warm with the target.
- `test_scene3d_target.py` (G3A): overlapping translucent layers give the same pixels in either draw order at 1 and
  4 samples (ordinary alpha blending of the same layers, the negative control, differs by over 40 levels), the nearer
  layer outweighs the farther, an opaque wall hides the layer behind it, blend/depth state comes back, and nothing is
  allocated without `oit`.
- `test_scene3d_target.py` (G3A near plane): eight bright (HDR) translucent layers at the eye stay finite, keep light
  past white and give the same picture in either order (it failed before the weight cap).
- `test_scene3d_target.py` (G1 scale): one logical card on a 100% then a 200% display reallocates to its device pixels
  and matches a direct draw at 1 and 4 samples with depth texture and OIT on; so does a 3x2 px card.
- `test_scene3d_target.py` (G1 lifetime): with depth texture, background, OIT and HDR all on, every attachment
  reallocates when the rect outgrows its bucket and no GL object survives `release` (negative control: skipping one
  OIT texture's delete fails it).
- `test_qtquick_extruded_spectrum.py`: real-driver alpha compositing over an existing backdrop, order-sensitive
  overlapping translucent bars, directional-shadow positive/negative pixels, and unchanged target ownership across
  the shadow switch.
