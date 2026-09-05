# Bubble aspect response and presentation cost

Last updated: 2026-09-05

The operator activated this investigation after Sphere implementation/visual review. `FWPlan.md`
owns its sequence; `Current_Plan.md` retains broader J optimization and physical acceptance.
Starting source: `66be7344`. BTF, R-69 and the Performance Optimization Contract remain binding.

## Superseding operator correction

The operator rejected the height-only presentation analyzed below. The recovery now projects the full
radius waveform through `sqrt(content_width * content_height / 1.5)`, preserving response across
same-area shapes and growing with visible area. This deliberate product correction is not a performance
cap or a DSP change. The older height-only evidence below is historical, not acceptance of that symptom.
See `Visualizer_Visual_Regression_Recovery.md`; live preview/outline follow-up is in
`Visualizer_Edit_Geometry_And_Sphere_Materials.md`.

## Questions and exact owners (historical investigation)

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
- [x] Compare identical authored radius sequences in real GL at constant-height width variants,
  constant-width height variants, uniform scale and screen-fit limits. Measure pixel diameter/delta,
  roundness, clipping and fractional occupancy separately.
- [x] Compare deterministic logical response under the same input/seed at representative extents.
- [x] Pin the highlight defect with a failing production-seam oracle before correcting its owner.
- [x] Correct the proven highlight mutation/orientation aspect defect and prove canonical pixels plus
  constant-height crop equivalence in real GL; leave radius, Ghost and simulation untouched.
- [x] Preserve canonical response/random ordering, consume-once events, Ghost/history and cadence.
- [x] Record the remaining perception/interaction question below as Awaiting Validation with concrete evidence.

Evidence: the existing deterministic ten-tick consume-once transient fixture at widths 140/280/420/630/
1260 and height 280, plus 420x840, produces the identical radius sequence (0.022231 initially,
0.045650 finally), identical normalized travel 0.030179 within floating arithmetic, and one snare
delivery. The real GL radius oracle passes before and after the correction. The specular-only crop
oracle fails before it (maximum channel difference 255 at every noncanonical width) and passes after
it (at most one channel step). A separate real GL comparison against the actual pre-change shader
from `139aed21` is byte-identical at canonical extent and scales 0.4/0.65/1/2, including the real 4px
scale-aware border. Evidence artifacts: `logs/evidence_chest/fw_bubble/canonical_comparison.json` and
`width_comparison.png`; the latter was visually inspected.

At every tested constant-height width the measured diameters are 24px at radius 0.04 and 48px at
radius 0.08, giving the same 24px expansion including antialiasing/outline. Heights 140/280/420/630/
1260 produce 14/24/36/56/108px at radius 0.04. Uniform 0.65 scale passes, and display-width fitting
is pixel-identical to explicitly choosing the same resulting 0.5 scale. No original response equation
changed to obtain these results.

**Awaiting Validation:** this isolates actual per-head amplitude from field occupancy; it does not prove
that every part of the operator's live symptom is explained. Obtain the resize operation and a same-preset
canonical/wide/narrow runtime comparison. Width-only at constant scale/height must keep per-head pixel
amplitude; changing height changes it by the existing R-69 contract. Crowding/collision population changes
are not yet justified. Do not relabel the highlight correction as an audio-reactivity fix.

## B2 — bounded presentation-cost attribution

Current Plan's poor 60 Hz run is separate temporal evidence. GC freeze, usage partitioning and source
handoff already have accepted attribution; this work does not reopen them. The first real runtime
comparison remains `--perf --viz` without `--usage`, using the same load/preset/display.

- [x] Inspect existing aggregate instrumentation and measure payload preparation / persistent float32 copies.
- [ ] **Awaiting Logs:** after a representative 60 Hz `--perf --viz` run without `--usage`, attribute
  surviving tails across sync, render entry, uniform upload and draw using bounded diagnostics.
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
- [x] Correct only the measured tuple owner; add no timer, poller, cadence owner, GPU stall or permanent probe loop.
- [x] Verify fresh-frame changes, retained identity and uniform upload safety across repeated/new snapshots.
- [x] Record scoped before/after results honestly; callback/microbenchmark costs do not prove physical pacing.

Instrumentation inventory: `scene_controller.py` PERF already aggregates draw/revision rates, pacer
skips and logical timestamp age; `visualizer/telemetry.py` owns sync/render/draw counts and last drawn
revision but no stage durations. T3-T6 live in `reactivity_diagnostics.py`; T7 in `visualizer/item.py`
arms on playback flips, not continuous render entry. Producer Bubble diagnostics already include
integration/tick/collision/snapshot cost. This leaves a real stage-duration gap, not proof of a slow
stage. The advertised `--gpu-timing` flag has no Quick timer-query owner; its reconciliation is in
`Future_Cleanup.md`. No extra permanent instrumentation was added before a runtime repro needs it.

## B3 — closure and remaining optimization

- [x] Run focused Bubble viewport/reactivity/BTF, payload/GL and relevant lifecycle gates; inspect diff.
  169 focused tests passed; the final screen-fit pixel addition passed its two-test real-GL file again.
  Changed Python compile and diff checks passed. The new pixel file is in the maintained destination profile.
- [x] Update live plans/navigation and checkpoint commit/push each validated slice.
- [ ] Await physical 60 Hz Bubble (canonical/wide/narrow), then 165 Hz comparison and tall Spectrum.
- [ ] Broader CPU/GPU/QML, contention and allocation/lifetime passes remain in Current Plan until measured;
  resource plateau is already accepted, bounded handle drift still needs the planned soak.

No global radius or Ghost multiplier, lower cadence, revision suppression, forced GC or mutable
cross-thread buffer is admitted by this decomposition.
