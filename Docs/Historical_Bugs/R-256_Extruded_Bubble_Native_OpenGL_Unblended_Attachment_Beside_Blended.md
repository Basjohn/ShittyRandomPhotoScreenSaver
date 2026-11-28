# R-256: Extruded Bubble's native backdrop left the scene's alpha 0 on OpenGL

**28 November 2026. Fixed in the native program's declaration (`rendering/native/extruded_bubble_program.py`, no
module change); found by N5.6's native-OpenGL rule (a) smoke ("P, T and C"), whose native frame showed the glass over
black.**

## What happened

The backdrop pass draws into the scene's two attachments: its colour replaced (`PassOutput(True, "replace")`, blending
off) and its emission added (`"additive"`, ONE, ONE). The core hands QRhi exactly those two target blends
(`mode_content.cpp` `outputBlend`), and the device reports `PerRenderTargetBlending`. On OpenGL the colour attachment
was nonetheless drawn blended, with the blend funcs a previous pipeline had left: the specks' and glints' light blend
(colour ONE, ONE; alpha ZERO, ONE). Over the cleared target the colour came out right, but the alpha kept the cleared 0.
The overlay composite reads the scene's alpha as coverage, so the scene showed only the glass that the transparency
resolve put over it.

Nothing raised an error. The readback of the scene targets (`NativeMode.read_targets`) showed the colour mean
(0.87, 0.40, 0.22) with alpha 0.0 in the background capture. The probe and shaft targets were whole. Three variants of
the same frame isolated the cause:

- with the specks' colour write masked, the alpha was still 0;
- with the backdrop's emission masked, it was 1.0;
- with the backdrop's colour declared as an enabled ONE, ZERO blend, it was 1.0 with the emission intact.

Vulkan sets each attachment's blend enable on its own, so it was unaffected. Layer L never draws, and the Python
renderer draws its passes through its own GL state, so nothing found it before the first native OpenGL draw.

## The fix

The backdrop's colour output is declared as an enabled blend equal to replace (`BlendState(("add", "one", "zero"),
("add", "one", "zero"))`). Every written attachment of the pass now blends explicitly, so no stale funcs apply. On
Vulkan the result is the same replace. The other multi-attachment passes (the glass, the near layer, Bubble's) blend
every attachment already.

## Proof

- `tests/test_native_eb_program_blends.py` refuses any pass in the program (1 and 4 samples) that writes an attachment
  with blending off beside a blended one. It failed on the old program (`['backdrop']`). Its control restores the
  plain `"replace"` and sees the backdrop again.
- The readbacks are in `.artifacts/evidence/native_core/n5_6/20261128_gl_mixed_blend/keep/`: before, specks masked,
  emission masked, explicit replace, plus the probe script.

## Rule

On a native pass with several attachments, never leave one written attachment with blending off beside a blended one.
Declare replace as an enabled ONE, ZERO blend there.

## The core's guard (ABI 47)

The core now refuses such a pass by name on every backend, so a program means the same on Vulkan and OpenGL
(`mode_content.cpp` `mixedBlendRefusal`, commit `29a844943`, built at `8bf270aa7`). The program is refused at parse
with "mixed blend: pass '<name>' writes attachment <i> with blending off beside attachment <j> with it on ...", for the
pass's own outputs and for its sorted pack's outputs; a masked attachment writes nothing and counts as neither. The
guard refuses rather than rewriting the replace silently, so the program's declaration stays the one truth. No shipped
program mixes them: Extruded Bubble's backdrop was fixed above, and the two harness programs that did (the post-stage
backdrop and the waveform primitives' `two`) moved to an enabled ONE, ZERO blend. `tests/test_native_post_stages.py`
proves the refusal; its control on the old source (`.artifacts/scratch/n56key/mixed_control.py`) failed.
