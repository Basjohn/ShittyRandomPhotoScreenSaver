# Native core P3: decisions before any C++ (P3.0)

**Status:** D4 proposed by the lead on 11 Nov 2026 (design only; its proof steps are in `Current_Plan.md`, item 8b).
D1 to D3 and the transport rule are still to be written here. Nothing in this file is built. Inputs:
`Native_Core_P2_Closeout_and_P3_Entry_2026-11-09.md` section 3, `Native_Core_P2_Phase_Boundary_Audit.md`,
`Graphics_Backend_Decision_2026-11-05.md`.

**The operator's rule this file answers to (11 Nov 2026):** Vulkan is "the front strong stable face" of the
product, never the fallback (OpenGL is the fallback). A limitation of Vulkan gets a solution of equal quality, not a
degraded path.

## D4. Extruded Bubble's drift solver without 64-bit shader floats

### The problem

The drift solver (`rendering/quick/visualizer/implementations/extruded_bubble_drift_solver.py`) is two compute
programs that use `double`. On OpenGL 4.6 Core that is guaranteed. On Vulkan it is the optional device feature
`shaderFloat64` (absent on Intel Arc, most mobile GPUs and Apple's), and QRhi cannot even ask. A second, lesser
path for devices without it would make Vulkan the weaker face on exactly those devices.

### What the doubles are actually for

From the inventory of 11 Nov (`D:\Temp\Scratch\SRPSS\research\20261111\eb_fp64_drift_inventory.md`; the facts are
repeated in the plan). Everything the draws read is already 32-bit: displacement, shift, phase offset and progress
leave the solver as `vec4` of floats, and displacement is 32-bit state between steps. The doubles serve three
things only, with add, multiply, divide, `floor` and `mod` and no double transcendental:

1. **A discrete decision per chain per step:** how many knots the chain's history moves,
   `floor(shifted / stepSize + 1e-10)`, with the remainder `shift` carried to the next step. A float32 span or
   carry once moved this one tick early against the CPU reference. At most 240 chains.
2. **Three growing phase arguments,** `sin(wrapped(t * k + c * p))` for k = 0.37, 0.83, 0.29: the music phase `t`
   grows without limit and must be reduced mod 2 pi before `sin`. These are per step, not per point.
3. **One growing quotient per mote,** `progress = mod(seed + travel * carry / span + phaseOffset, 1)`: `travel`
   grows without limit (about 5,000 after an hour at the default, 32,000 at the fastest), and there are up to
   218,500 motes, so this one must stay on the GPU.

### The decision: no double in any shader, on any backend; precision goes where it is free or is rebuilt exactly

One path for OpenGL, Vulkan, Direct3D and Metal alike. No device feature is queried, so no device is second class.

- **(1) Chain decisions move to the engine worker, in float64, as the reference itself computes them.** The worker
  already produces the step record each tick; it also advances each chain's `shift` and takes the `floor`, in
  NumPy float64 with the reference's own arithmetic, and publishes per step and per chain the pair
  (`moved`, an integer; `shift`, a float32, always in [0, 0.008)). The chain program reads those and does only
  32-bit work (moving the knot row by `moved`, updating displacement). This is not an approximation of the
  64-bit decision: it *is* the 64-bit decision, made once, by the code the tests already treat as truth.
  Cost: 240 chains times a handful of float64 operations per tick in the worker (vectorised; microseconds), and
  8 bytes per chain per unapplied step on the transport (about 2 KB for a typical frame, 246 KB for a full
  128-step history).
- **(2) Phase reduction moves to the step record.** The worker reduces `t * k` mod 2 pi in float64 for the three
  constants and publishes three float32 angles per step. The shader computes `sin(angle + c * p)` in 32-bit, both
  terms bounded. The rule "reduce mod 2 pi in 64-bit before `sin`" is kept; it simply runs where 64-bit is free.
- **(3) The per-mote quotient is rebuilt exactly from pairs of floats (double-single arithmetic).** The division
  leaves the GPU: at geometry build the worker computes `r = carry / span` per mote in float64 and stores it as a
  high and a low float32 in the two unused floats of the mote's second `vec4` (the geometry record does not grow).
  Each step carries `travel` as a high and a low float32, split by the worker in float64. The shader forms
  `travel * r` as an error-free product of pairs (`fma`-based two-product, results marked `precise` so the
  compiler may not contract or reorder them) and takes its fractional part. That gives about 48 significant bits
  for the quotient; the output is a float32 with 24. At an hour's quotient of 800 the pair arithmetic is exact to
  about 3e-12 of a span, against 1e-13 for a double, and both are four or more orders of magnitude below the
  6e-8 of a span the float32 result can resolve. The geometry-edit rebase (`oldTravel / oldSpan`) uses the same
  pairs.

**Why not the alternatives.** Keeping `double` where `shaderFloat64` exists and a second path elsewhere gives two
solvers to test and makes the feature-less Vulkan devices the lesser face. Integrating all drift in the worker
would ship about 4 MB a revision at full population and brings back the cost the GPU solver was built to remove
(152 ms a tick at 216,000 specks in the old CPU path). A camera-relative or periodically rebased quotient in plain
float32 accumulates rounding at every rebase and loses the closed form the reference is compared against.

### What "equal quality" means here, and how it is proved

The bar is the float64 CPU reference (`MaterialDriftReference`), the same judge the current solver has:

1. **Tick-exact chains:** `moved` for every chain on every tick equals the reference's, as integers, over a long
   recorded drive. Not a tolerance.
2. **Outputs within the current bound, at long horizon:** displacement, shift, phase offset and progress within
   the existing 1e-4 of the reference, on runs that start at an hour's and at eight hours' `travel` and `phase`
   (today's suite covers about four seconds). The current `double` shader is run on the same horizons, so the new
   path is compared with what it replaces as well as with the reference.
3. **No visible difference:** the largest displacement difference converted to pixels at 4K for the nearest bead
   the camera admits, stated as a number.
4. **It compiles for Vulkan:** both programs pass `qsb` (their loose uniforms move into a block) and leave the
   `LEGACY_GL_ONLY` list; the shader-readiness check discovers compute sources instead of using a fixed list.
5. **No cost at rest and no cost rise:** GPU time per dispatch at preset 1 and at 216,000 specks against today's,
   in one alternated session; the worker's tick cost for (1) and (2); a frame with no new step still dispatches
   nothing.

The pair arithmetic is first proved without a GPU: a NumPy float32 model of the shader's exact operation order
(with `math.fma`) against the reference over the long horizons. Only then is the shader changed.

### Consequences

- The solver stops being a Vulkan blocker and can be ported by the native core like any other compute pass.
- This can be built **now, in the existing OpenGL renderer**, before any C++ exists: it is a change to two shader
  programs, the step record, the mote geometry record and the worker's drift log, all behind the existing
  reference tests.
- The step record grows by three floats and the travel pair; chains gain their per-step decision stream; mote
  geometry does not grow. D3 (geometry once per revision) is unaffected and still owed.
- A device or driver whose compiler ignores `precise` would break (3). The readiness test therefore includes a
  runtime self-check of the two-product on a known pair at warm-up, on the edge, never per frame; a failure is
  logged and reported rather than silently producing drift.

## D1, D2, D3 and the transport rule

Not yet written. Their one-line statements are in `Current_Plan.md` (item 8b, step 4) and their inputs in the
closeout document's section 3. Order: D1 and D2 with the drop edge, then D3.
