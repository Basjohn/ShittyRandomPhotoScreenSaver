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
- `test_qtquick_transition_state_fence.py`: deliberately non-default state restoration on success/failure, plus real
  reflection and multisample texture sentinels across a scene pass and a thrown renderer.
- `test_qtquick_bootstrap.py`: each required entry point must resolve on the actual context; no frame-time probing.
- Existing transition warm-up, scene foundation, target, environment and Motion Trails tests protect pixels,
  gradual preparation, parked resources and disabled-feature dormancy across the five shared 3D transitions.

Changing uniform streams still use the existing mutable/orphaned UBO owner. Immutable static storage is not a
drop-in replacement for that update policy. Persistent mapped streaming, multiple buffer-range binding and effect-
private dynamic/instanced transport require the separate S14 decomposition in `Docs/Future_Work/3D_Scene_Foundation.md`.
