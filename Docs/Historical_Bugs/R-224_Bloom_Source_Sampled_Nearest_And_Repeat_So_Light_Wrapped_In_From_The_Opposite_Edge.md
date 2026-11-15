# R-224 | The bloom chain read its source with NEAREST filtering and REPEAT wrap, so light wrapped in from the opposite edge

**Status:** fixed 15 Nov 2026 (found by N3.4's native-core proof). Present since the bloom chain landed. Owner:
`rendering/quick/scene3d/target.py` (`_allocate_plain_texture`, `_BLOOM_SOURCE_KEYS`, the alpha clear in `begin`) and
`rendering/quick/scene3d/motion.py` (the blurred scene's output texture). Regression bar:
`tests/test_scene3d_target.py::test_bloom_light_never_wraps_in_from_the_opposite_edge` (emission at one card edge adds
nothing to the opposite edge), with the negative control `test_the_wrap_guard_fails_on_the_old_nearest_repeat_sampler`
(the old sampler state back: the same probe sees the wrapped light).

## Symptom

None reported. Emission at a card edge lit a few pixels at the opposite edge, and the chain's 13-tap
downsample and tent upsample, which are designed for bilinear taps, ran on point samples. The native core (N3.4)
samples LINEAR with CLAMP_TO_EDGE; the Python target was the odd one out.

## Cause

`SceneTarget._allocate_plain_texture` gave every plain attachment GL's default wrap (REPEAT) and NEAREST filtering. The
bloom chain samples four of them with `texture()`: the scene colour, its resolve, the emission and its resolve (and the
motion-blurred scene when both run). The chain's own level textures were already LINEAR + CLAMP_TO_EDGE; defocus and
the shaft chain already clamp.

## Fix

Those four textures (and the motion output) are LINEAR + CLAMP_TO_EDGE. Reading them bilinearly exposed a second
defect that NEAREST had hidden: the bright pass scales colour by alpha-over-brightness per tap, and a non-overlay
bloom scene cleared to alpha 1 (black), so bilinear taps at the border between a drawn pixel (alpha 0) and the cleared
area blended into false emission (a whole photograph bloomed). With bloom the scene now clears to alpha 0 (the
composite writes opaque alpha, so nothing else reads it).

## Why it hid

- The wrapped light was a few pixels at a card edge, under a glow that is already soft.
- The cleared alpha was harmless while every tap read one texel.

## Lessons

1. A texture a shader samples with `texture()` has a sampler state that is part of its contract; the plain-texture
   helper's default is for texel fetches only.
2. A per-tap nonlinear weight (alpha over brightness) does not commute with the hardware's bilinear blend: whatever the
   filter blends must be linear in what it blends, or the cleared background must be neutral.
