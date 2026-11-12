# Shared scene3d GPU resources

The retained Quick transition and visualizer hosts remain their scenes' render owners. `rendering/quick/scene3d/` supplies context-local,
lazy resources; it does not create a clock, scheduler, global texture cache or alternate renderer. All admitted
operations require the validated OpenGL 4.6 context. PyOpenGL DSA creation calls use explicit output arrays.

Visualizer content quarter-turns use the shared scene-frame orientation and the target's existing final composite.
The logical camera viewport swaps axes for odd turns, at unchanged uniform pixel scale; integer texels map back into
the fixed physical stage without another target/pass or changing the immutable camera and world payload. Overflow
reach remains in the oriented scene frame and clips to the same physical window. Transition frames remain unturned.

## Rejected Extruded cast-shadow receiver and Scene3D camera (R-120/R-121 consolidation)

Early E8 receiver attempts produced triangular near-footprint casts or a corner-only sliver even at long distance. A translated top cap is **not** the requested cast: any future operator-approved design must sweep from the bar base footprint toward the shifted upper silhouette, stay visible without gigantic side smear, and respect screen-edge clipping and overflow without shrinking the authored Spectrum geometry. These experiments remain rejected/disabled; see `Docs/Historical_Bugs/R-125_to_R-128_Extruded_Cast_Shadow_Failure.md` for the full negative history. Sphere's turn/tilt/box and Edit cage share the live Scene3D pose authority, not preset-managed camera copies. The E8-era Python 3.13 sequencing and two-original WebP paths were superseded and are **not** current product instructions.

## Shared framed-camera and transparent-scene admission contract

The opt-in **framed 3D camera capability** is implemented in `core/settings/framed_camera.py` with the existing
view-orbit/scene-transform declarations and shared physical projection/admission helpers. Neon Lake and Extruded Bubble
are current consumers; future modes reuse this owner rather than repeating per-mode camera plumbing.
The outer retained card and CUSTOM stage remain fixed, while its content orbits/pans/zooms inside
CARD_INTERIOR. Mode declarations supply bounds, pivot, pan/zoom safety, fit and near-plane behavior; do **not**
globalize landscape angles, wrap bounded modes, give future modes copied camera controllers or change unframed 3D
behavior. Live gesture pose persistence stays with the existing view-pose/presentation owner; a mode's authored initial
pose retains its declared Settings/preset keys.

Perspective is the only camera projection for every 3D mode. The 28 October "Orthographic default" decision is
superseded: Orthographic was removed from the whole project on 5 Nov 2026 (operator), including `orthographic_matrix`,
the parallel-ray branch of `rendering/gl_programs/framed_camera.py` and every per-mode Projection control. That GLSL
supplies the explicit Perspective per-pixel ray origins/directions and footprints.

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
ribbons and G5 volumes are demand-driven separate gates. `Current_Plan.md` section 1, item 8b (stages N0 to N6: the 3D work inside the native core) is the live implementation checklist since 12 Nov 2026;
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

## Program links and the program binary cache

Every custom GL program (Visualizer modes, transitions, scene3d passes, the background and backdrop nodes, the
Visualizer clip; `BaseGLProgram.create_program` too) is linked by one function, `rendering/quick/render/gl_resources.py`
`_link`, reached through `compile_program` / `compile_compute_program`; no other production module calls
`glLinkProgram` (`tests/test_gl_program_cache.py` holds that). It links on the caller's render thread, in the frame or
warm-up step that needs the program, as before.

`_link` first asks the app-owned program binary cache (`rendering/quick/render/gl_program_cache.py`), because the
driver's own shader cache is per executable path and every onefile build is a new path (R-180: Neon Lake's basin is one
5-7 s cold `glLinkProgram` that holds every display):

- **Key:** SHA-256 of the store's schema, the context's `GL_VENDOR` / `GL_RENDERER` / `GL_VERSION` strings, its
  `GL_PROGRAM_BINARY_FORMATS`, and every stage's type and source in link order. A shader edit, a driver update or
  another GPU is a clean miss; labels are not part of it.
- **Location:** `<LOCALAPPDATA>/SRPSS/gl_program_cache/<key>.bin` via `core.platform_paths.user_local_root()`
  (`$XDG_STATE_HOME` on Linux): outside the onefile extraction folder, shared by Standard, Media Center and source
  runs (the key carries everything that decides validity). No local root: the store is off and links behave as before.
- **Hit:** the file's header (magic, schema, format, length, key, payload SHA-256) must check out and the format must be
  one the driver lists, so `glProgramBinary` never raises a GL error that the node's per-frame drain would report;
  the program is kept only when `GL_LINK_STATUS` is true. Neon Lake's basin: ~0.6 MB, loaded in ~30 ms.
- **Miss:** the ordinary compile and link with `GL_PROGRAM_BINARY_RETRIEVABLE_HINT` set before linking, then
  `glGetProgramBinary` and an atomic write (per-writer temporary, `os.replace`), so concurrent render threads or
  processes never see a partial file. A damaged, foreign or driver-refused entry is a miss and is replaced; a failed
  compile stores nothing; any I/O failure only skips the store.
- **Bound:** after each write, least-recently-used entries (a hit refreshes the file time) are removed until the store
  is within 64 MB (`MAX_CACHE_BYTES`; the whole app's programs are a few MB), with temporaries older than an hour.
- **Diagnostics:** one INFO line per saved cold link (`[GL_PROGRAM_CACHE] <label> linked cold in N ms, saved K KB
  (hits=h misses=m)`); a hit is a DEBUG line. Nothing runs between links: no thread, timer or poll, and gradual
  warm-up still compiles one program per spaced, already-rendered frame (a hit just makes that step short).

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
Neon Lake's source/authoring contract lives in `Docs/Reference/Neon_Lake_Basin.md`; its cost/fidelity gates remain
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

## Fog volume and detail march (S3D-7)

- **`scene3d/fog_volume.py:FogVolume`:** one camera's coarse froxel grid.
  - x and y follow the viewport; z is exponential in view depth. One view matrix and lens serve both projections.
  - A consumer's `fogMedium(world, radiance, extinction, steady)` compute source (`gl_programs/fog_volume.py`) is
    evaluated per cell.
  - The front-to-back integral is exact per slice and lands in an RGBA16F 3D texture that `MIST_GLSL` samples:
    `mistTransmittance` for additive and OIT passes, `mistOver` for opaque surfaces.
  - The analytic mist path is unchanged when no volume is bound.
- **`FogMarch`:** reads the coarse medium at reduced resolution.
  - It erodes the non-steady coverage with a baked tiling 3D noise and self-shadows toward lower coverage, where a
    consumer's lights sit.
  - Steps are adaptive: long through clear air, short in the medium.
  - It stops at an optional analytic ground plane and composites `dst x T + S`, plus a bloom share.
  - The steady share, smooth haze for example, is never eroded.
- **Resources and lifecycle:**
  - Three 3D textures per volume, plus one 2D target and the noise per march. All allocate at first use, are reused
    at a size, and are released in the owning context.
  - A mirrored reflection camera uses its own instances.
- **Proof:** `tests/test_scene3d_fog_volume.py` proves exact slab transmittance and in-scatter in both projections,
  world anchoring (a moved clear sphere; a moved eye), the steady share surviving full erosion with erodible coverage
  as the control, and lazy allocation, bounds, foreign-context rejection and release.
- **Cost:** `wr07_mist_substrate/fog_cost.json` on an RTX 4090 at 820x718 (warm-clock medians):
  - coarse updates: about 0.03-0.15 ms;
  - main march: 0.4-1.2 ms;
  - mirrored march: 0.2-0.7 ms.

  That is too costly for full-screen production. The planned reductions are a precomputed clear-air direction instead
  of six gradient fetches per step, fewer steps, and a lower march scale.

## Planar reflections and rough receivers (S3D-5)

`scene3d/reflection.py:PlanarReflection` owns one mipmapped RGBA16F target and depth renderbuffer, allocated lazily
at the requested size. `gl_programs/reflection.py:mirror_view` mirrors the physical camera in a horizontal plane.
The caller draws the same scene snapshot, excludes the receiver, disables winding culling and admits only geometry
above the plane: this primitive does not yet clip crossing geometry. `end()` builds mips and restores the saved
framebuffer, viewport, depth test/write mask and colour mask. Release belongs to the owning current context.

The receiver samples the reflected scene at its projected position. Optical roughness defines a short-axis mip
footprint and a longer vertical footprint; `textureGrad` integrates it using anisotropy capped at the lesser of
16 and the OpenGL 4.6 device limit. A streak longer than 16:1 is split into up to eight abutting, Gaussian-weighted
segments so the short axis keeps its mip (one long footprint washed neighbouring highlights together).
Optional contact hardening (`uReflectionContact`: plane height, spread per unit height, along/across ratio, probe
mip) reads the light-weighted height of what is reflected from a coarse probe of the target's alpha and widens the
footprint with it. Emitters opt in by writing luminance x world height into alpha and blending alpha ONE, ONE in
the reflection pass. The ribbon light and spark passes do; scene targets keep alpha with ZERO, ONE. The capability query occurs only on allocation. This replaces seven discrete
samples that copied a bright highlight into seven separated bands. It adds no targets or passes; hardware sampling
cost must be measured rather than inferred from shader call count. This is a bounded directional filter, not a full
microfacet ray-traced reflection. In `wr05_floor_candidate/filter_cost.json`, 45 warm draws per state at 820x718 on
RTX 4090 measured the same low/high medians before and after (0.039/0.040 ms); p90 rose by about 0.002 ms. This
same-recipe comparison measures only the floor draw, excluding reflection generation and every other scene pass.

`tests/test_scene3d_reflection.py` proves mirrored object registration in both projections with camera translation,
foreign-context rejection, lazy reuse/retirement, a continuous elongated highlight, a narrow segmented long streak
(negative control: one footprint, more than twice as wide and displaced) and height-proportional contact spread
(negative control: spread off ignores height); `test_ribbon_material.py` proves the light pass's height alpha.
Same-code floor draw at 820x718 on RTX 4090 (`wr05_wet_contact/floor_cost.json`): 0.162 to 0.222 ms median for the
wet recipe; reflection generation medians are unchanged, and its p90 is spiky in both recipes and unexplained. The highlight regression
fails the old kernel with twelve-pixel gaps between copies. Consumer OIT-body/volume inclusion, clipping, resize and
failure-path proof, whole-scene cost and visual acceptance remain in the Waveform Lab Plan; existing focused checks
must not be cited as completion of those gates.

## Fixed-size scene and post-process allocations

The existing target, bloom, motion and trail owners construct named framebuffers and immutable textures at their
known allocation size. Named attachment/status/draw-buffer operations replace allocation-only framebuffer queries
and binds; depth renderbuffers also use named storage. Rendering and resolve passes keep their state restoration.

| Owner | Storage and allocation contract |
| --- | --- |
| `SceneTarget` | RGBA8 colour, optional RG16F velocity and depth24; existing multisample count and 64-pixel size buckets ; an **overlay** scope (a Visualizer drawn over its card) clears to transparent and composites the resolved scene back as straight alpha times an opacity, discarding where nothing was drawn, with no motion blur. An overlay **with bloom** adds an RGBA16F emission attachment (location 1, written only inside `emission_writes()` as `sceneEmission(light)`), blurs it through the shared bloom chain and composites premultiplied with the glow added, under a blend it sets and then hands back as the caller had it (captured at `begin`), so glow is exactly additive over what Quick drew and no emission writes means no glow. The non-bloom overlay path is unchanged |
| `SceneTarget` depth texture and background | `depth_texture=True` makes the depth attachment a DEPTH_COMPONENT32F texture (multisampled with the colour) instead of the depth24 renderbuffer; drawing is pixel-identical. `background()` captures, mid-scope, what has been drawn so far into a plain RGBA8 colour (averaged over samples) and an R32F nearest window depth (the far plane without a depth texture), then hands drawing back where it was (draw framebuffer, viewport, colour masks 0-1, blend, depth test, program, units 0-1). Allocated on first use or by `warm(..., background=True)` as one unit; released with the target |
| `SceneTarget` order-independent transparency | `oit=True` adds an RGBA16F accumulation and an R16F revealage (multisampled with the colour) in their own framebuffer, sharing the scene depth (tested, never written) and, with bloom, the emission attachment at location 2 (added). Passes inside `transparent_writes(frame, resources)` write `sceneTransparent(premultiplied, alpha, view_depth)` (`SCENE_OIT_GLSL`: weighted blended OIT, McGuire-Bavoil equation 10 on view depth); leaving resolves per sample (`gl_SampleID`) over attachment 0, premultiplied, alpha added on overlays (coverage) and only dimmed otherwise (emitted brightness), then restores blend (indices 0-2), colour masks, depth test and depth mask |
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

### Owned frames: `restore=False` (5 Nov 2026)

Every save/restore fence above reads GL state back, and each read is a round trip to the driver thread: ~20-25 us on a
quiet machine, up to milliseconds when the CPU is saturated, and a GPU bubble either way. A scene that owns the GL state
of its whole frame (the visualizer render host's fence hands Quick's state back afterwards, and every pass sets what it
draws with) opts out per call: `StreamRing.bound(..., restore=False)` and `bound_image(..., restore=False)` read nothing
and leave the point/unit unbound; `SceneTarget.transparent_writes(..., restore=False)` reads nothing and leaves a fixed
state (blending off on its draw buffers, depth test on, depth writes off, buffer 0 written and the others masked as
`begin` masks them); `FogVolume.update/bound`, `RibbonPrimitive.draw/packet_scope`, `RibbonBurstRenderer.draw`,
`WaveformField.update` and `FloorGiveField.update` take the same flag, and the ribbon draws also take the known
`viewport`. Uniform locations are looked up once per program. Defaults are unchanged for every other caller. The
Waveform scene uses it throughout (`OWNED` in `waveform.py`): 169 -> 31 reads per frame (the rest is the host fence and
the scene target's and reflection's fences of the caller's state); `tests/test_waveform_render_thread_queries.py` keeps
a steady frame free of uniform lookups and within its read budget.

## Compute seam and first consumer (S15)

`compute.py` is the whole seam: `dispatch(groups, barriers)` takes explicit workgroup counts and the barrier bits its
readers need, and issues that barrier straight after the dispatch (the writer owns it; readers never know a writer
exists). `bound_image(unit, texture, access, format)` binds level 0 of an owned texture for the scope and hands the unit's
previous binding back (name, level, layering, access, format), because the transition host does not fence image units.
`MeshResources.compute_program` compiles through `compile_compute_program` (shared link/cleanup with graphics programs)
and `warm_programs` accepts `(resources, key, compute_source)` entries, so compute programs are gradual warm-up steps.
No queue, scheduler, worker, readback or polling exists: work runs on the owning render thread in the frame that uses it.
A compute program has no loose uniforms (Vulkan GLSL, N1.2): its values are one std140 `Scene3DBlockLayout` declared
with `layout.glsl(COMPUTE_BLOCK_BINDING)`, which the pass's owner binds through its own `DispatchBlocks` (a small
stream ring, warmed as one step of the owner's `warm`, left unbound after each scope; `rebind` gives a later dispatch
in the same scope its own values). Every resource in a compute source has its own binding number (samplers, images,
storage and the block share one namespace on Vulkan); in OpenGL the texture or image unit is that number.
`tools/compute_pass_identity.py` records each converted pass's outputs on fixed inputs and its GL calls, and compares
two records bit by bit.

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

## Sphere impostors

`rendering/gl_programs/scene3d_spheres.py` (import-safe GLSL + CPU mirrors) draws exact spheres from one view-space
quad per instance: `sceneSphereCorner` sizes the quad to the silhouette cone through the centre
(`(r + blur) d / sqrt(d^2 - (r + blur)^2)`, collapsed when the eye is inside), `sceneSphereRay` intersects the view
ray, `sceneSphereCoverage` antialiases the silhouette (or softens it over `blur` for defocus) and `sceneSphereDepth`
writes the true surface depth, so interpenetrating spheres meet along their real intersection. View space has the eye
at the origin looking down -z; consumers supply their own placement and projection. No resources: a consumer's own
instanced draw and program. Proven by `test_scene3d_spheres.py` (GPU id/depth picture equals a CPU ray cast apart
from under 1% edge pixels, silhouettes within 1% of the analytic area from 1.5 to 0.02 radius, blur widens and softens
the edge) and `test_scene3d_spheres_mirrors.py` (GLSL equals the mirrors).
Vertex stages include `SCENE3D_SPHERES_VERTEX_GLSL`: it compiles out the fwidth-based `sceneSphereCoverage`
overload, because derivatives are fragment-only and strict compilers (Mesa) reject them even unused in a vertex
shader. Fragment stages keep `SCENE3D_SPHERES_GLSL`.

Round on screen (2026-10-17): a rectilinear view draws an off-axis sphere as an oval stretched toward the frame's edges.
`sceneSphereScreenCorner` (vertex) places a screen-aligned square round the projected centre, sized to the apparent
width across the line of sight, and `sceneSphereFacingRay` (fragment) gives the view ray as if the sphere were seen
straight along the line to its centre, so every sphere is a circle wherever it sits (deformation is reserved for
collisions). The mirror test proves every unit-circle corner grazes the silhouette.

## Scene probe

`rendering/quick/scene3d/probe.py`: `SceneProbe(label, size)` owns one RGBA16F cube with a full mip chain, a depth
renderbuffer and a framebuffer. `capture(draw)` renders the six faces (GL's cube convention; each face's 3x3
world-to-view rotation and a 90-degree projection are handed to the callback), then pre-filters every mip level from
the one above over a Gaussian cone (32 taps, sampled across face edges, about two texels of that level wide), so
blurred lookups are a smooth, rotation-invariant filter (GL's per-face mipmaps read as blocks). The caller's
framebuffer, viewport, scissor, clear colour, depth, blend, program, vertex array and unit 0's cube binding come back;
nothing is allocated after the first capture; `warm()` allocates it (and compiles its prefilter) on a hidden frame
instead. GLSL `sceneProbe(probe, direction, blur, levels)`. It is how glass,
water and bubbles show the scene they sit in (the light, beams, lit particulate) instead of painted highlights.
`test_scene3d_probe.py`: face rotations follow the cube convention, every direction reads back what the scene put
there (with a mirrored-face negative control), blur is the same filter across faces and full blur is the hemisphere,
state and allocation.

## Defocus layer and HDR scenes

`rendering/quick/scene3d/defocus.py`: `DefocusLayer` is depth of field for objects near the lens. `begin(w, h)`
binds an RGBA16F premultiplied colour and an RG16F alpha-weighted circle of confusion (both mipmapped); the caller
draws its near objects sharp with `SCENE_DEFOCUS_GLSL` `sceneDefocusWrite(premultiplied, alpha, cocPixels)`; `begin`
sets its own colour masks for both outputs (masks are per draw buffer index: a scene target masks its emission index
outside `emission_writes()`, which dropped every circle); `end()` hands back framebuffer, viewport, blend, depth and
masks; `warm(w, h, max_radius)` allocates the layer and the read level `composite(max_radius)` clips into, one unit a
hidden frame; `composite(max_radius)` spreads every pixel evenly over its
own circle (64 golden-angle taps, each read from the mip level matching the taps' spacing so no source pixel is
missed, weighted by 1 / its circle's area so light is conserved) and lays the result over the bound framebuffer.
A near transparent object should write only its own light (reflections), so the scene behind stays visible.
Highlights (`composite(max_radius, highlight=0.25)`, 2026-10-18): the fixed taps catch a small bright source
unevenly at a coarse read level (striped, blocky blobs where a lens draws a round disc). Light in a texel of the read
level above the floor and above the mean round it (two levels coarser) is taken out of the gather (a clipped copy of
that level, so gather and sprites split the same texels and light is kept) and drawn as one instanced disc per such
texel, of its circle, antialiased and slightly brighter at its edge. Cost in the bubble lab: within noise of the
gather alone (~0.05 ms).

The full-resolution gather must cover at least the wide gather's actual mip-texel width. Otherwise
an intermediate circle can be too small for that mip while receiving neither fine-gather nor
resolved-highlight coverage. The split remains smooth, with fixed tap counts and the caller's budget.

`test_scene3d_defocus.py`: a bright point becomes an even filled disc of its circle holding its light, a sharp pixel
stays exactly in place, state comes back, nothing is left after `release`; a highlight under a wide circle is one
even round disc (and the gather alone, the case it guards, is measurably lumpier).

`SceneTarget.scope(..., hdr=exposure)` (overlay with bloom only): colour, background capture and resolve are
half-float, so light brighter than white survives for every pass that reads the scene (refraction, reflection,
bloom), and the overlay composite tone maps it once (ACES fit) at that exposure to an ordinary display. This is HDR
rendering, not an HDR display. Without `hdr` everything is as before. `test_scene3d_target.py` proves light past
white in the background capture and a smooth monotonic tone curve, single- and multisampled.

## Shared optics and underwater light

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
light entering a glass wall near the silhouette is guided round inside it; up to eight direction/weight paths with
matching local interface/exit points, the last the ray that leaves). GLSL returns `paths[8]` and `points[8]`;
`capturePoints=false` omits unused point metadata for directional consumers, which must not read those outputs.
the CPU mirror returns `(direction, weight, point)` triples. `sceneSphereRefraction` also returns its matching
unit-sphere chord exit via `exitNormal`, including the front point on entry TIR. EB uses these points to evaluate
the physical Deep Source direction; directional/probe consumers retain their ray directions. Tests hold both to CPU mirrors on the
GPU, conservation, the air bubble's mirror band, straight passage with matched indices and a solid sphere's
reflection when the core is empty.

## Shared Scene3D capability inventory

Current owners, proof and known limits for the reusable Scene3D substrate. Extruded Bubble's target and lab are one
important consumer/proof source; this table is a durable capability inventory, not a retired-plan status board.

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

## S3D-1 CPU test references and independent GPU prototype

`core/ribbon_geometry.py` provides bounded absolute-coordinate CPU history and centripetal interpolation for
new strips; see `Docs/Reference/Ribbon_Path.md`. The standalone CPU path probe is its current consumer.
`core/ribbon_frames.py` adds the CPU transported/camera-facing width reference. Neither module migrates EB wakes. WR-02a adds the independent oriented SSBO strip prototype in
`rendering/quick/scene3d/ribbon.py` and `rendering/gl_programs/ribbon.py`, admitted packets in `core/ribbon_packet.py`.
See the focused path reference for native proof and input-path separation: the current packet builder invokes
the CPU test oracle, whose full rebuild timing is neither a software-rendering backend nor an app runtime cost. OIT, defocus,
camera-facing GPU behavior, broader normal/precision/native proof and scene composition remain open.
