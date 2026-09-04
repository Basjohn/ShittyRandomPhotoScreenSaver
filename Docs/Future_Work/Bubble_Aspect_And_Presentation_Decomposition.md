# Bubble aspect response and presentation cost

Last updated: 2026-09-05

The operator activated this investigation after Sphere implementation/visual review. `FWPlan.md`
owns its sequence; `Current_Plan.md` retains broader J optimization and physical acceptance.
Starting source: `66be7344`. BTF, R-69 and the Performance Optimization Contract remain binding.

## Questions and exact owners

The reported symptom is progressively weaker response in wide rectangles and excessive size/response
in narrow rectangles, including modest deviations from square/ordinary rectangles.

Production chain:

1. Retained CUSTOM commits independent viewport extent and uniform scale through
   `widgets/spotify_visualizer/presentation_geometry.py` and the existing configuration route.
2. `bubble_frame_runtime.py` supplies extent to `BubbleSimulation.tick()` as spatial configuration.
3. `bubble_simulation.py` expands independent world axes; snapshot normalizes positions/history once.
   The authored radius remains a fraction of actual content height (R-69).
4. `BubbleFrame` freezes/validates float tuples. The retained bridge publishes immutable latest state.
5. `rendering/quick/visualizer/implementations/bubble.py` resolves payload and copies into persistent
   render-thread float32 buffers. The existing shader corrects X distance by content aspect.

Consequently `radius_px = authored_radius * content_height`; relative horizontal coverage is
`2 * authored_radius / content_aspect`. Width-only changes should preserve pixel radius/delta while
changing occupancy. Height changes intentionally scale both. Screen-fit can additionally reduce
uniform scale when an extent exceeds display bounds. None alone proves lost audio sensitivity.

Another hypothesis needs separation: collision/spawn pair distances normalize each axis into a unit
square, whereas the shader uses height-isotropic distances. Determine whether this is an actual
reported failure or protected authored placement before changing it; do not retune the simulation
from a geometrical suspicion.

Independent review confirmed a narrower shader defect: the directional specular offset already divides
X by aspect, but `spec_ox * r` does not. After the shader multiplies X distance by aspect, this supposedly
bubble-local mutation moves farther across a wide head and less across a narrow head. The ellipse light
direction also uses the changing viewport aspect, rotating the highlight with an edge resize. These
affect apparent surface depth; they do not explain or authorize changing pulse amplitude.

The owning correction keeps the canonical content aspect at the same uniform scale/chrome inset as
the specular reference. Convert only the local mutation's X offset by `reference_aspect / aspect` and
orient the ellipse using that reference. At canonical extent the reference equals actual content aspect,
preserving the existing appearance exactly. At wider/narrower extents the same head keeps the same
highlight. This is one scalar uniform on the existing draw, with no new pass/resource/cadence.

## B1 — geometry diagnosis before behavior edits

- [x] Read exact source, current plan, BTF and R-69; identify logical, projection and shader owners.
- [ ] Compare identical authored radius sequences in real GL at constant-height width variants,
  constant-width height variants, uniform scale and screen-fit limits. Measure pixel diameter/delta,
  roundness, clipping and fractional occupancy separately.
- [ ] Compare deterministic logical response under the same input/seed at representative extents.
- [ ] Pin any source-proven defect with a failing production-seam oracle before correcting its owner.
- [ ] Correct the proven highlight mutation/orientation aspect defect and prove canonical pixels plus
  constant-height crop equivalence in real GL; leave radius, Ghost and simulation untouched.
- [ ] Preserve canonical response/random ordering, consume-once events, Ghost/history and cadence.
- [ ] Record any remaining perception/interaction question as Awaiting Validation with concrete evidence.

## B2 — bounded presentation-cost attribution

Current Plan's poor 60 Hz run is separate temporal evidence. GC freeze, usage partitioning and source
handoff already have accepted attribution; this work does not reopen them. The first real runtime
comparison remains `--perf --viz` without `--usage`, using the same load/preset/display.

- [ ] Inspect existing aggregate instrumentation and measure the exact payload preparation / persistent
  float32 copy / uniform upload / draw boundaries with a bounded probe if needed.
- [x] Name removable work and benchmark it before production changes. Renderer `_payload()`
  recasts already validated immutable BubbleFrame tuples every draw. Preserve size validation, latest
  revision and native float32 safety transport; do not suppress repeat revisions or share mutable arrays.

Pre-change measurement (80 batches of 200 calls, warmed imports, this Windows/Python environment):
26 heads with history: payload preparation median 32.37 us / batch p95 48.35 us; 110 heads with history:
95.61 / 122.44 us. The separate three persistent float32 copies cost 19.83 / 30.49 us and 71.32 /
87.10 us respectively. This attributes removable three-tuple reconstruction, not a 60 Hz stall.
The safe correction is to retain the already finite/float/immutable `BubbleFrame` tuple objects in
the renderer payload, slicing only oversized accepted arrays. Keep all active-length checks and the
native float32 transport; there is no cache or revision-based decision.

After removing recasts: payload median/batch-p95 is 0.96/2.93 us at 26 heads and 1.09/3.06 us at
110 heads. The unchanged transport varied to 16.14/22.07 us and 66.84/94.16 us, illustrating normal
run noise. Three active-size tuples (up to 1,870 entries total) and their generator traversals disappear
from each draw. The payload record remains tiny; no cache or new ownership machinery was added.
143 focused Bubble viewport/config/reactivity/BTF/Quick payload/native transport tests passed.
- [ ] Correct only a measured owner; add no timer, poller, cadence owner, GPU stall or permanent probe loop.
- [x] Verify fresh-frame changes, retained identity and uniform upload safety across repeated/new snapshots.
- [ ] Record scoped before/after results honestly; callback/microbenchmark costs do not prove physical pacing.

## B3 — closure and remaining optimization

- [ ] Run focused Bubble viewport/reactivity/BTF, payload/GL and relevant lifecycle gates; inspect diff.
- [ ] Update live plans/navigation and checkpoint commit/push each validated slice.
- [ ] Await physical 60 Hz Bubble (canonical/wide/narrow), then 165 Hz comparison and tall Spectrum.
- [ ] Broader CPU/GPU/QML, contention and allocation/lifetime passes remain in Current Plan until measured;
  resource plateau is already accepted, bounded handle drift still needs the planned soak.

No global radius or Ghost multiplier, lower cadence, revision suppression, forced GC or mutable
cross-thread buffer is admitted by this decomposition.
