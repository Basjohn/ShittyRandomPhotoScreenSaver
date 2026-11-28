# R-255: Extruded Bubble's native trails and beads programs could not link on OpenGL

**28 November 2026. Fixed in the native shader composer (`097e5eb7b`, packs rebaked, no module change); found by
N5.6's first native-OpenGL rule (a) smoke ("P, T and C").**

## What happened

Extruded Bubble's native packs (`rendering/native/extruded_bubble_shaders.py`, baked by `tools/eb_native_shaders.py`)
are the Python renderer's GLSL with each program's block members renamed. The Python texts declare their uniform
blocks anonymously (`uniform EbTrails { ... };`). Qt's shader baker turns each block into SPIR-V, and SPIRV-Cross then
writes the OpenGL translation as `uniform <Struct> _<SPIR-V id>;`. Each stage is translated on its own, so the ids are
per stage. The trails program's vertex block `EbTrails` and its fragment block `SrpssConventions` both came out as
`_449`, and the beads program's `EbWakes` and `SrpssConventions` both came out as `_1061`.

OpenGL links uniforms across stages by name. Two different struct types under one name make the link fail ("struct
type mismatch between shaders for uniform (named _449)"), so the trails pipeline could not be created, and the whole
native content build failed. Vulkan was unaffected (SPIR-V binds blocks by set and binding). Layer L (record identity)
never creates pipelines, and the Python renderer compiles its own GLSL text, so nothing found it before the first
native OpenGL draw.

## The fix

The composer now gives every anonymous uniform and storage block an instance name derived from its block name
(`blk_<Block>`), the same in every stage. Each member is reached through a `#define <member> blk_<Block>.<member>`,
so the Python arithmetic stays as written. SPIRV-Cross keeps a declared instance name, so the GL texts declare
`uniform EbTrails blk_EbTrails;` and `uniform SrpssConventions blk_SrpssConventions;`. The core ignores instance names
(it reflects blocks by binding and member), so no module change was needed.

## Proof

- `tests/test_native_eb_shaders.py::test_no_program_declares_one_opengl_uniform_name_with_two_types` reads every
  baked pack's GL translations (GLSL 430 and 460) and refuses a name declared with two types. It failed on the old
  packs (trails `_449`, beads `_1061`, both versions) and passes on the rebaked ones.
  `test_every_anonymous_block_is_named_alike_in_every_stage` checks the composer step itself.
- An offscreen GL 4.6 link of all 12 programs and the 3 sorted fragments: all link
  (`.artifacts/evidence/native_core/n5_6/20261128_gl_block_names/keep/link_after.txt`). The failing build's item
  state is kept beside it (`build_state_before.json`, "pass 'trails': its pipeline could not be created").

## Rule

A native pack whose stages share any block declares that block with an explicit instance name. A test over the baked
packs' OpenGL translations refuses one global name with two types. Never rely on SPIRV-Cross's per-stage
auto-numbering to stay apart.
