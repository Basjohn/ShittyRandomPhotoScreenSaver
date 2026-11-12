# R-198 | The conventions buffer registry was keyed by a PySide wrapper that Qt Quick's context does not keep

**Status:** fixed 12 Nov 2026, the day it shipped (cefbfa2b, N1.4's conventions include). Found by the Fable audit of
12 Nov evening (`Docs/Future_Work/Audit_2026-11-12_Evening.md`, finding 1 High and finding 2 Medium). Owner:
`rendering/quick/render/gl_resources.py`. Regression bars in `tests/test_conventions_include.py`:
`test_a_context_qt_owns_has_one_entry_one_buffer_and_every_hold_with_no_wrapper_kept`,
`test_two_sharing_contexts_each_bind_their_own_buffer_and_a_foreign_delete_is_refused`,
`test_a_destroyed_context_leaves_no_entry`, `test_only_a_program_that_reads_the_block_holds_it`,
`test_every_program_linked_through_gl_resources_is_deleted_through_delete_program`, and
`test_one_buffer_per_context_held_by_the_programs_that_declare_it` (moved onto a context Qt owns). Each failed on the
code before its fix. Silent: no picture changed on the development GPU.

## Symptom

None visible here. Measured with the audit's probe on Qt's global share context (created by Qt in C++, as Qt
Quick's render-thread context is), three programs that declare the block linked and deleted through the product path:

```
registry entries after 3 links in one context: 3 | buffers created: [1, 2, 3] | holds: [1, 1, 1]
registry entries after deleting all 3: 3 | buffers still alive: [1, 2, 3] | stale program holds: 3
```

In the product: every link of a program with the block (Extruded Bubble, the 3D transitions' resolve, OIT, defocus,
motion and trails passes) created another 16-byte buffer, registry entry and signal connection, and the delete gave
nothing back; a mode switch or reload linked again, so it grew for the life of the process. Where a freed wrapper's
address was reused by a wrapper of another context (a second display, the Studio preview), that context found the
other's entry and bound nothing at binding 17, and a release could delete a buffer still bound elsewhere. A read of an
unbacked uniform block is undefined; NVIDIA returns zeros, which are exactly this renderer's values, so nothing on the
development machine could show it. On a driver returning anything else `srpssConventions.x > 0.5` mirrors rows.

## Cause

1. **The key was `id(QOpenGLContext.currentContext())`.** For a QObject that Python did not create, PySide keeps a
   wrapper only while Python references it. The registry stored the integer, not the wrapper, and a connected
   `aboutToBeDestroyed` does not keep the wrapper either, so each later call built a new wrapper at a new address or at
   a freed one (the probe: 8 calls in one context, 3 distinct ids). `rendering/quick/scene3d/waveform.py` already
   recorded the same PySide behaviour and stores its wrapper, which is why Waveform alone was spared while its scene
   lived.
2. **The guard could not see it.** `tests/test_conventions_include.py` created its own `QOpenGLContext` and held it for
   the whole test, which the product never does for Qt Quick's context.
3. **Holders were chosen by text** (finding 2). `_link` took a hold when a source contained `SrpssConventions`; the
   mapping-only include carries the name inside an `#if` that is false, so the fog march and composite fragments held
   a buffer without a block, and their owner deleted them with a raw `glDeleteProgram`, which never gave it back.

## Fix

- The registry is keyed by the native `QOpenGLContext` pointer (`shiboken6.getCppPointer`), which lives exactly as
  long as the context. `aboutToBeDestroyed` is connected once per context (Qt's connection outlives any wrapper) and
  forgets the entry, so a pointer reused by a later context starts clean. Holding the wrapper in the entry was tried
  and dropped: it kept contexts Python owns alive after their owner let go.
- A delete from another context of the same share group keeps the hold and logs an error instead of unbinding the
  block where the program was linked.
- `_link` asks the linked program (`glGetUniformBlockIndex`, after the text check) whether it declares the block. A
  declared std140 block is always active, so this answers "declares", which is the right question for the binding.
- Every program linked through `gl_resources` is deleted through `delete_program` (17 raw deletes in 12 files routed);
  a scan keeps it so. The identity harness: every frame of every mode and transition bit-identical, steady GL calls per
  frame unchanged, one `glGetUniformBlockIndex` per candidate link
  (`.artifacts/evidence/native_core/n1_4_conventions/20261112_registry_fix/`).

## Why it hid

- The only GPU returns zeros for an unbacked block, and zeros are this renderer's values.
- `tools/gl_object_ledger.py` does not see buffers created through out-parameters (`glCreateBuffers(1, arr)`), so the
  lifecycle tests could not count the leak (separately boxed in the plan).
- The test held its own context, the one shape in which `id()` of the wrapper is stable.

## Lessons

1. Never key per-context state by `id()` of a PySide wrapper of an object Qt owns. Key by the native pointer and tie
   the entry's end to the object's own destroy signal.
2. A lifetime test must reach the object the way the product does: a context Qt created, with no Python reference kept
   between calls. A test that holds what the product does not hold proves only the test.
3. Decide resource ownership from the linked program, not from text a preprocessor may discard.
