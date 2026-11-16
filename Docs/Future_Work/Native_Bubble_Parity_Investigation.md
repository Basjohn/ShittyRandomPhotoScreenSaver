# Native Bubble parity investigation

The live acceptance sequence is `Current_Plan.md` item 8b, N5.1 Bubble; the common pixel rule is D12 in `Docs/Future_Work/Native_Core_P3_Decisions.md`. This document records the unresolved classification, not a tolerance decision. Bubble's native route remains dormant until its parity, cost, lifecycle, registration and other plan gates pass.

## Reproduced owner residual

The latest baseline (`.artifacts/evidence/native_core/n5_1_bubble/20261116_current_rule_a_7d7fe160a/native_render_parity.json`, `reproduction_metadata.json` and the six input-244 PNGs beside them) reruns the retained variant-a rule-(a) comparison through the dormant owner on official module7d7fe160a. It is Python versus native OpenGL at the display placement, 1920 × 1080, actual DPR1.5, device-aligned origin(30,30),5.5 seconds and the full549-input sequence. Each path drew549 frames; native published360, with the mode switch at input337. It reproduces both the earlier b1451eb11 replay and the retained historical result exactly:350 differing inputs,3,423,997 differing pixels and maximum difference8 levels. The judge fails215 frames; the worst frame has101 ties and8 flips. This is not accepted parity. The original executed helper is retained with each current baseline.

The retained source review and CPU analysis are in `.artifacts/evidence/native_core/n5_1_bubble/20261116_residual_source_review/research.md` and `retained_analysis.json`; the earlier owner receipt is `.artifacts/evidence/native_core/n5_1_bubble/20261115_rule_a_variant_a/`. The inputs are generated from the canonical settings spec, not a frozen preset. In the retained breakdown, steady frames account for 328 differing inputs and 7,240 differing pixels (532 above one level); fade frames account for 22 inputs and 3,416,757 pixels (57 above one level). Most differences are one-level fade/composite differences; the maximum and the rule failures still require classification.

At input 244, 47 pixels differ: 41 by one level, four by two, one by three and one by eight. The six pixels above one level cluster at x 251–255, y 347–354 in the retained 739 × 529 region. The maximum at (253, 354) is Python RGB `[208, 56, 98]`, native `[208, 50, 106]`. Its entire 5 × 5 reference neighborhood spans only `[1, 9, 12]` levels across the three channels, so its 3 × 3 neighborhood cannot satisfy D12's 32-level content-edge criterion. It is also adjacent to other differences, not an isolated tie. The retained images are RGB; alpha, per-pixel mask and ambient-attachment readbacks were not retained. Do not broaden the tolerance or call this an allowed edge on these figures.

## Ownership and eliminated explanations

`rendering/quick/visualizer/implementations/bubble.py` builds the shared frame and draws ambient points and hero mask before the final Bubble pass. `rendering/quick/visualizer/native_route.py` declares the same point/mask shader files, target formats (RGBA8 coverage and RGBA16F light), streams and final shader. `bubble_native_schema.project` consumes the same frame values and ambient payload. Source review found no separate simulation or authored-data owner.

- The mask's custom erase blend is wired: `parsePassTargetState` preserves the custom output state, `outputBlend` selects it, and geometry pipeline construction supplies it to `setTargetBlends`. A serialized preset label of `replace` is not evidence that the custom erase was omitted. Source inspection does not substitute for inspecting the actual built pipeline and attachments.
- Both paths in the current rule-(a) comparison draw instanced quads. The earlier `.artifacts/evidence/native_core/n5_1_bubble/20261115_quads_vs_points/figures.json` compares Python points with quads; it cannot explain or authorize the present native-versus-Python quad residual. Its old light-error script uses an absolute 1/255 threshold despite an FP16-step comment; those figures do not prove ULP parity.
- Python's ambient allocation is exact while native targets may round allocation to 64-pixel buckets. `widgets/spotify_visualizer/shaders/bubble.frag` maps through actual texture size, clamps to content texel centers and accounts for row convention. This is a real path difference worth isolating, not an established cause. RGBA16F on both paths alone establishes neither equal sums nor unequal sums.
- The retained run used DPR 1.5, not DPR 1. Neither a point-coordinate difference nor a presumed shader compiler/orientation defect is established by the current images.

## Next discriminating control

An independent GPU-free input244 block oracle passes on the same official7d7fe160a module. The production Python
packer matches all3,552 compared shader-read bytes:49 hero positions/extras,147 trail.xyz samples, two addressable
class words, enabled ambient size and scalar/style fields; reflected offsets match too. Ambient point/mask
non-core settings also match. Mutating the serialized first position by+.01 fails only `u_bubbles_pos`. The lead
reviewed and reran it; `20261116_block_oracle/` retains raw/expected/negative bytes, manifest, source and summary.
This excludes packing differences in those spans, not actual GPU uniform upload, shader arithmetic or pixels.
Matrix/target conventions are explicit exclusions. The GPU-free helper lacks per-pass target context, so its
ambient core-size field is the overall630×420 while the real draw uses618×408; that helper limitation is not a
native target-size defect.

The no-final-light diagnostic wraps only `bubble_frame_scalars` and replaces its returned `u_ambient_light_enabled`
with zero. Logical frames, point/occluder data, light allocation/draws, mask blend, settings, pass order and the owner
judge remain intact; the wrapper restores all functions. This differs from an authored glow toggle, which also
changes simulation data. Source review was independently clear before execution.

The first matching7d7fe160a run is retained in `20261116_current_rule_a_7d7fe160a_light_disabled/`. Canonical parity
still fails:346 differing inputs,3,467,030 differing pixels,max8. At input244, the reference/native images each
change visibly against baseline (20,056/20,055 pixels;9,630 pixels change by at least2 levels,max31). Yet the same
six pixels above one level remain atx251–255/y347–354, including the original max8 coordinate. This supports
investigating boundaries beyond final light composition, subject to the diagnostic integrity issue below.

Fourteen integrity guards pass; the raw projected-record equality guard fails. The in-memory record contains
tuples whereas the saved baseline JSON contains lists. The original failed receipt and executed helper SHA
`f4a1b81081bd764d04044d3a6ee6ac54d104b8469904f586008be319c250234d` remain unchanged. Independent inspection of
the saved JSON records finds exactly one changed key, `u_ambient_light_enabled:1→0`; the complete actual record
equals that expected record. `posthoc_wire_guard_inspection.json` records this check and both metadata hashes.
Correct the comparison at its JSON representation boundary and audit it before treating the control as fully
guarded. This is a diagnostic representation defect, not evidence for widening pixel tolerance or changing renderer data.

Require an actual visible baseline-versus-control difference in lit regions as the negative control, and recompute each image's reference-derived mask. If input 244's cluster disappears and the other residuals shrink, final light contribution or its read is implicated; that alone cannot distinguish accumulation, sampling, coordinates and final mapping. Compare actual light and coverage attachment readbacks on the fixed input before proposing a precision change. If the cluster persists, localize coverage/mask and final hero arithmetic with the same frozen logical frame. A diagnostic is not port acceptance; do not widen D12 bounds without the lead's explicit decision.

If current evidence instead establishes a passing parity run, continue the plan's widened offers and placements, rule-(b), block/item negative controls, performance, rest and retirement proofs before registration. The source review's `reproduce_owner.py` and the executed copy beside the current receipt preserve the process-local dormant-registration method; they do not register Bubble in product settings.
