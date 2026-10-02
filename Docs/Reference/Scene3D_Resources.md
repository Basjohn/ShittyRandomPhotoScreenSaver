# Shared scene3d GPU resources

The retained Quick transition host remains the render owner. `rendering/quick/scene3d/` supplies context-local,
lazy resources; it does not create a clock, scheduler, global texture cache or alternate renderer. All admitted
operations require the validated OpenGL 4.6 context. PyOpenGL DSA creation calls use explicit output arrays.

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
| `SceneTarget` | RGBA8 colour, optional RG16F velocity and depth24; existing multisample count and 64-pixel size buckets |
| Bloom | Four progressively halved RGBA16F levels, allocated with the requesting target |
| Motion | Three RG16F velocity reduction/neighbour passes and one RGBA8 output, using existing tile and target sizes |
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
storage binding. No current consumer moves to storage buffers: a two-array Visualizer upload would trade two calls for
four, and Sphere's eight cohort arrays plus section drives belong to its S19 promotion; S15-S18 consumers use it first.

Measured (960x540 offscreen Exploding Tiles, three interleaved HEAD/new process pairs, 210 warm frames each, flush per
frame; 28 frames across four setups byte-identical): GL calls per frame 215 -> 211 by default and 281 -> 267 with Motion
Trails; CPU submit median 1.19-1.26 -> 1.23-1.27 ms by default (neutral), 1.80-1.84 -> 1.70-1.72 ms with trails and
2.09-2.15 -> 1.94 ms with trails and motion blur (p90 2.79-2.97 -> 2.33-2.38 ms). The removed work is the per-frame
buffer re-specification, the generic-binding query/restore and three sub-data writes per trail ghost.

## State restoration

The common transition fence restores 2D textures on units 0, 1 and 2, multisample textures on units 0 and 1, and the
incoming active unit. Reflections/motion use unit 2 and scene resolves use the multisample targets; neither may leak
bindings to Qt, including after a renderer raises. Existing program, VAO, array-buffer, framebuffer, viewport, blend,
depth and stencil restoration remains binding. DSA construction does not remove draw-time inherited-state duties.
The expanded fence deliberately pays for the previously missing state; the isolated binding measurement excludes it.

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
  gradual preparation, parked resources and disabled-feature dormancy across the five shared 3D transitions.

- `test_scene3d_stream.py`: driver-reported std430 offsets/strides equal the layout and values arrive through the
  ring; indexed ranges restored and generic bindings untouched for uniform and storage targets; every reused slot
  waited on its fence with each of 48 unsynchronised frames reading its own values; fixed loud capacity; a dormant
  ring makes no GL call; failed deletion keeps its handle, release returns to zero and rebuilds; a failed mapping
  leaves no buffer.
- `test_scene3d_uniforms.py`: std140 layout and values, previous binding handed back, and draws before an
  `update_fields` keep their values.
- `test_transition_warmup.py`: counts ring allocation as a warm-up unit, so a run's first frame cannot allocate it.
