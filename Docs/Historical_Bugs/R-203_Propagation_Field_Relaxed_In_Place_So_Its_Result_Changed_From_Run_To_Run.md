# R-203 | The propagation field relaxed in place, so its result changed from run to run

**Status:** fixed 13 Nov 2026 (N1.6 plan box "the propagation field's relax pass"). Present since the field landed with
Capillary Bloom (a7742fe3, 11 Oct 2026). Owner: `rendering/quick/scene3d/propagation_field.py`. Regression bar in
`tests/test_propagation_field.py`: `test_the_build_is_bit_repeatable_and_independent_of_its_step_split` (at 1920x1080
and the harness size). It failed on the code before the fix: 9 of 10 builds differed from the first, in up to 1,118 and
1,128 of 36,864 values. Silent: no frame changed in the rendered case.

## Symptom

None visible. Two builds of the same field from the same inputs were not bit-identical. With the identity tool's
cost (`tools/compute_pass_identity.py`, 1920x1080, so a 256x144 field), 552 to 1,063 of 36,864 values differed between
runs, by at most 0.0009 cost units. For Capillary Bloom's own paper cost the race was rarer: 2 of 120 inputs (40 seeds,
three source counts and fibre values) differed between two runs, in up to 66 values, and the rendered frames on real
photos never changed by one 8-bit step. The outcome depends on how the driver schedules workgroups, so it can be larger
on another GPU or backend, and a recorded frame could not be compared across runs or backends.

## Cause

The relax pass read and wrote the same image (`coherent image2D uArrival`), the neighbours of a texel included texels
of other workgroups in the same dispatch, and nothing ordered those reads against those writes. The module explained it
away: the field only falls and every value read is a true upper bound, so "read races only speed convergence". That
is true of the result's bound, not of its bits: which value a read gets (before or after a neighbour's write) is
undefined behaviour in GLSL and in Vulkan, and it changes which path reaches a texel first in floating point.

## Fix

- Relax ping-pongs between two R32F fields (`arrival` and `relaxed`; one more 147 KB texture at 16:9, allocated in the
  warm-up with the others and released with them). Each pass reads one and writes the other, Jacobi order, as
  the CPU mirror `propagation_reference` always did. The two directions are two programs over image bindings 1 and 2,
  bound once per build step. Rebinding both image units every pass doubled the build's GPU time, and switching
  programs cost much less. After each pass the names swap, so `arrival` always names the newest field and a build split
  across warm-up steps of any size ends bit-identical to a build done in one frame (asserted with 37-pass steps).
- Ten builds at 1920x1080 and at 256x144 are bit-identical. The rendered Capillary Bloom and Edge Bloom frames
  (PERSONALSET photos, 20 to 80 %) are pixel-identical before and after. Edge Bloom does not use this field; its jump
  flood already ping-pongs. The identity cost's field moved by at most 0.00049 in 696 values, within the old run-to-run
  spread. Paired GPU time for a whole 192-pass build: 1.79 to 2.54 ms (+0.72 ms, p10 +0.29, p90 +1.00). That is about
  +0.18 ms per 48-pass warm-up step, spent between runs. GL calls per build went from 442 to 642 (one `glUseProgram` per
  pass). Evidence: `.artifacts/evidence/transitions/propagation_relax/relax_pingpong/20261113_*`.

## Why it hid

- The race only shuffles values that are already upper bounds, so every bound and reference test passed.
- No test built the same field twice and compared bits.
- On the development GPU the differences are smaller than one 8-bit step of the composite.

## Lessons

1. A compute pass that reads values other workgroups write in the same dispatch is undefined, however monotone the
   update is. Ping-pong (or a barrier between the read and the write), and never argue it away.
2. Test a GPU build for bit-repeatability, not only for closeness to a reference. Two runs of the same code are
   the cheapest oracle there is.
