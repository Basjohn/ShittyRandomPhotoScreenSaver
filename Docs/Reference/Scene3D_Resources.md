# Shared scene3d GPU resources

The retained Quick transition host remains the render owner. `rendering/quick/scene3d/` supplies context-local,
lazy resources; it does not create a clock, scheduler, global texture cache or alternate renderer. All admitted
operations require the validated OpenGL 4.6 context. PyOpenGL DSA creation calls use explicit output arrays.

## Rejected Extruded cast-shadow receiver and Scene3D camera (R-120/R-121 consolidation)

Early E8 receiver attempts produced triangular near-footprint casts or a corner-only sliver even at long distance. A translated top cap is **not** the requested cast: any future operator-approved design must sweep from the bar base footprint toward the shifted upper silhouette, stay visible without gigantic side smear, and respect screen-edge clipping and overflow without shrinking the authored Spectrum geometry. These experiments remain rejected/disabled; see `Docs/Historical_Bugs/R-125_to_R-128_Extruded_Cast_Shadow_Failure.md` for the full negative history. Sphere's turn/tilt/box and Edit cage share the live Scene3D pose authority, not preset-managed camera copies. The E8-era Python 3.13 sequencing and two-original WebP paths were superseded and are **not** current product instructions.

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
- `test_qtquick_extruded_spectrum.py`: real-driver alpha compositing over an existing backdrop, order-sensitive
  overlapping translucent bars, directional-shadow positive/negative pixels, and unchanged target ownership across
  the shadow switch.
