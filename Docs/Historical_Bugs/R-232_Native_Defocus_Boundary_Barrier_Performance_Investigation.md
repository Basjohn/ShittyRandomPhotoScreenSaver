# R-232: Native OpenGL defocus cost changed at a barrier

**16 November 2026 — STRONG RETENTION VALUE DOCUMENT. Performance cause open; no production performance improvement or synchronization workaround admitted.** Current work and acceptance remain in `Current_Plan.md`; the detailed native contract and measurements are in [D17](../Future_Work/Native_Core_P3_Decisions.md).

## Trigger and what was learned

At 4K, the native Extruded Bubble defocus stage was materially more expensive on OpenGL than the Python renderer and Vulkan on the same machine. In the 15 November comparison, native OpenGL defocus was 4.95 ms at 1x and 3.71 ms at 4x, versus Python's 2.98/2.36 ms and Vulkan's 2.10/2.18 ms. These were GPU record measurements, not a user-facing speedup. The exact cause of the excess is still unknown.

The investigation narrowed the cost to the interaction around the gather and sprite draws. It did **not** repair that cost. A proposed per-record instance-upload stall did not fit the source: the sprites use an empty vertex layout and instance index, with no instance stream; full and high-threshold variants upload the same block arena. The high-threshold case still submits the same instanced draw, so it must not be described as removing the vertex work or the draw.

Draw-local timestamp queries changed the result they were intended to explain. ABI 22's control without queries showed why that mattered: both query mode and external-command boundaries collapsed the measured excess, whereas the off brackets retained it. ABI 23 isolated the boundary between gather and sprites; boundaries before gather or after sprites did not produce the same effect. At 1x the off brackets were 2.2241 and 2.5262 ms full-minus-high-threshold, versus -0.0492 ms with the between-draw boundary; at 4x they were 1.2032 and 1.1878 versus 0.0072 ms. The corresponding pixels were exact, and each isolated boundary executed 239 times with zero queries. These are diagnostic measurements under the recorded ambient GPU conditions, not an acceptance benchmark.

ABI 25 separated two other explanations. Merely declaring external content or disabling compute-resource tracking did not reproduce the collapse. At 1x those modes measured 2.2959 and 2.3040 ms, with off brackets 2.2333/2.2978 and between-only 0.2181 ms; at 4x they measured 1.1673 and 1.2195 ms, with brackets 1.2094/1.2196 and between-only -0.0062 ms. Both samples were actually allocated at the requested counts, pixels matched their corresponding baseline, and the tracking-disabled program had no compute. The full record and its two variants must be compared; timestamps around individual draws are not a neutral substitute.

## The boundary, the barrier, and the limits

Qt 6.12's OpenGL `beginExternal` executes its queued commands and unbinds VAO/buffers; `endExternal` resets cached state, recreates pass tracking, and queues the current framebuffer again. A captured 1x off/between/off trace showed that the between-draw path additionally issued a `glMemoryBarrier`, rebound the same framebuffer and draw buffers, and replayed graphics state. No `glFlush` or `glFinish` occurred inside the inspected gather-to-sprite intervals; occurrences elsewhere include host readback activity and cannot be attributed to that boundary. A boundary is therefore not just a timestamp or one GL command.

The combined-control trace kept the boundary and framebuffer rebind while turning off compute tracking: all 34 tracked intervals had one inter-draw barrier and all 34 untracked intervals had none. Its untraced 1x measurement retained 240 settings records, 239 defocus records and timing samples, actual sample-count and compute-free guards, and exact corresponding pixels. Full-minus-high-threshold medians were **2.0163 ms off before, 0.0378 ms boundary tracked, 2.5651 ms boundary untracked, and 2.3531 ms off after**. The flag changes tracking generally; that comparison alone is correlation, not a single-call experiment. The completion sample was 22% GPU use at 870 MHz; no pre-run sample was recorded.

For a narrower test, headless apitrace replay omitted only the 34 captured inter-draw `glMemoryBarrier` calls while retaining the other recorded commands. Existing whole-record elapsed queries, not added per-draw queries, gave tracked full-minus-threshold medians **0.0594 → 1.7940 → 0.3103 ms** for original, omitted, and restored replay, with 15 samples per case. The stored call selection and query mapping were independently reviewed. The invocation receipt records exact arguments and successful exits retrospectively from execution receipts; it is not an automatic launch log. Query checking can wait for results and replay is not native performance admission. Within that replay the selected calls had a causal effect; it does not establish which hardware resource is responsible, a driver bug, or a production optimization.

The resource graph has read-only near textures and a scene attachment, without shader stores or attachment feedback. OpenGL's ordering and memory-barrier rules did not establish a missing correctness barrier here. This does not remove the separate Vulkan read-stage chaining requirement in D17. A possible overlap/contention mechanism involving the gather's 96-tap fragments and roughly 8.36 million sprite vertex invocations remains an inference, not a finding; workload controls or hardware counters may distinguish it. Native and Python also differ in VAO and uniform handling; those differences are not proven causes.

## Failed and limited approaches

- A draw timestamp run suppressed the excess and measured a perturbed workload. Its query intervals were means, not medians; the high-threshold draw was still present.
- `ExternalContent` alone and the compute-tracking hint alone did not remove the excess. The external boundary bundles execution, resource tracking, and state restoration, so attributing its result to a simple flush would overstate the evidence.
- Startup apitrace injection failed because its loader hook stripped Python's DLL-search flags. Supported late attachment after imports captured the command stream without changing DLLs. The tracer disables program-binary formats, and per-draw replay profiling did not reproduce the native record-level excess; neither is a performance gate.
- Nsight Graphics 2026.3.1 was compatible with the installed 617.42 driver and was signature-checked and extracted without installation. Qt consumed the initial `--platform` value as the QPA plugin name `windows (x86_64)`, which did not match the available `windows` plugin and produced an `ngfx` dialog; a subsequent injection failure and CrashReporter secondary Qt error remained unresolved. Owned failed dialogs and process trees were closed. The profiler is optional follow-up, not proof of the performance cause.

## Comparing the Python workload without draw-local queries

The old `python_defocus_steps` reference inserts `glQueryCounter` after gather and before sprites. Its sprite timing cannot establish the cost of an uninstrumented pair. The existing `python_cost` instead encloses the actual owner in one whole-frame elapsed query, but its old variant list did not include a high-threshold pair. Also, the highlight changes the clip texture that gather samples as well as sprite rejection; full-minus-high-threshold must not be called pure raster cost.

An aligned 3840×2176 native repeat retained the excess: off brackets 2.3542/2.2969 ms, tracked boundary −0.0615 ms, untracked boundary 2.2456 ms. The unchanged combo guards passed, including exact corresponding pixels and 239 samples/records per case. Therefore the original 2160-to-2176 allocation difference does not explain this fixture's excess. GPU conditions were 12%/390 MHz before and 86%/2775 MHz after.

At the same aligned size, a helper reused the unchanged Python `python_cost` and `DefocusLayer.composite` bodies, overriding only the fixture's highlight value. Four cases each executed 244 whole-frame query pairs and composites (four warm frames, 240 samples), with zero `glQueryCounter` calls. Full-minus-high-threshold was 0.6953 ms before and 0.6339 ms after; corresponding bracket frame hashes were exact, and the full/high images differed on 26,832 RGB pixels, maximum 12 code values. GPU conditions were 30%/2595 MHz before and 6%/2790 MHz after. The lead inspected both images; independent High review checked the helper and receipts.

This establishes a smaller paired-workload difference on the Python owner without draw-local timestamps. It does not establish identical submission: Python blocks for each whole-query result and allocates/uploads fixture UBOs, while native uses latched query reads and a different uniform path. The helper's CPU wrappers also affect command pacing.

The native timer's existing `wait_for_results` option then tested whole-pass blocking reads without a query between gather and sprites. The excess remained: off brackets 2.1883/2.5662 ms, tracked boundary 0.1024 ms, untracked boundary 2.2262 ms. Eight timer snapshots confirm blocking mode, 478 blocking reads and 239 results each, zero busy/abandoned slots and unchanged pixel/sample/record guards. GPU conditions were 13%/330 MHz before and 41%/2775 MHz after; independent High review checked the receipt. Blocking-read cadence alone therefore does not explain this fixture's excess. This does not establish equivalence of the remaining submission paths. Hardware counters were unnecessary for this falsifier.

A further Python control replaced the owner's empty VAO temporarily with an owned diagnostic VAO containing four valid vertices and enabled float2 attributes 0 and 1. Setup and attribute queries occurred before timing; the original composite body performed its usual binds/draws, with no injected calls between gather and sprites. All 244 scopes per case restored the owner's VAO, and the diagnostic resources retired in the owning context. Full-minus-high-threshold stayed at 0.6789/0.7024 ms. All four frame hashes and original owner-function hashes matched the earlier Python baseline. GPU conditions were 5%/210 MHz before and 3%/2790 MHz after; independent High review checked source and output. Enabled unused attributes in this Python setup do not reproduce native's excess. This does not reproduce the complete native VAO, shader or submission state; uniform/shader submission remains a concrete comparison boundary.

## Uniform submission: measured difference, insufficient explanation

The captured native GLSL uses loose struct uniforms. The pinned Qt6.12 OpenGL backend keeps QRhi uniform-buffer
data in CPU storage and uploads reflected fields; the Python owner uses an actual std140 UBO. Trace review found
no wrong value or missing upload. Of 102 sprite draws,96 steady draws re-upload only the level integer and two
sampler units; the six first draws also upload radius/highlight. The actual shader bodies and gather path still
differ, so this is a concrete comparison boundary rather than proof of an upload stall.

A separate ignored helper changed only the Python sprite block declaration into four loose uniforms in both
shader stages. Original function bodies, PassBlocks/ring writes and binds, draw, textures and blend remain intact.
The initial uploads occur in the first excluded warm frame; actual locations, absence of the named block and
driver-read values are checked. Buffered and loose modes preserve all four original baseline RGBA hashes, with
240 finite samples,244 whole-query/composite calls and no draw-local timestamps per case. Full-minus-high paired
medians before/after are **0.6902/0.7363 ms buffered and 0.7157/0.6318 ms loose**. Independent High review checked
the helper and actual receipts. Changing this declaration/storage path alone did not reproduce native's multi-ms
excess in this fixture. It does not reproduce Qt's repeated steady integer/sampler uploads or remaining qsb/gather
source and submission differences, and does not establish equivalence or the performance cause.

A real negative uploads half-sized uSize. It fails exactly the two full-case baseline-pixel predicates; both high
hashes, uniform setup/readback and every other guard still pass. Its near-zero difference belongs to deliberately
wrong output and is not a speedup. Buffered/loose GPU conditions were 47%/870MHz→12%/2775MHz and
49%/765MHz→54%/2775MHz, with SRPSS running. Single sequential runs and fixed-order pair brackets do not remove
ambient variation; this is diagnostic evidence, not quiet-GPU admission. Combined gather/sprite lowering,
conventions and translated-body differences remain open before selecting another bounded falsifier.

## Compiled-source comparison and texture-size control

Comparison of the actual submitted gather/sprite GLSL with the Python kernels found no arithmetic, loop-count,
instance-count or discard correctness defect. Both gather paths contain the same fragment-row conditional and
use the same x value; an earlier ignored research note's suggestion of an additional native-only conventions
branch was corrected. The native y tap mirror is required by the row convention. Sampled expanded decimal
literals round to the same float32 values. These checks do not establish identical GPU executables: qsb changes
temporaries/control flow, the native rejected varyings are initialized, and index lowering still differs.

The next bounded control changed only Python sprite size derivation: insert the native `textureSize(uColour,0)`
local at main entry and use it instead of uSize in final placement. The original UBO declaration, packed values,
PassBlocks/ring operations, shader bodies elsewhere and all steady GL calls remain intact. Actual source texture
levels are 3840×2176 and 1920×1088 with base level 0, checked once during excluded warm-up. The unchanged
uniform-size control and level0 query both retain all four original-baseline image hashes and every240-sample,
244-call whole-query/composite guard with zero draw-local timestamps. Paired before/after medians are
**0.7322/0.5908ms uniform and0.6717/0.6697ms query**. The deliberate level1 query fails exactly the two full-case
baseline-pixel checks while both high hashes and all other guards pass. Independent High receipt review is clear.

This expression alone did not reproduce native's multi-ms excess in the Python fixture. It does not prove timing
equivalence, query hoisting, native compiler behavior or a driver cause. GPU before/after was 19%/420MHz→6%/2790MHz
for uniform and 0%/210MHz→42%/2790MHz for level 0; these are sequential available-activity diagnostic runs. Remaining
translated gather/body and complete submission differences need a specific next falsifier, not another profiler
repair or a production synchronization workaround.

## Current disposition (operator, 16 Nov 2026)

Retain this as a detailed, non-blocking investigation for another agent. The operator removed the investigation
as a consumer blocker after the matched backend comparison. Historical gate statements below describe the
state when those measurements were taken; current consumer admission keeps its own parity, lifecycle and
measured-cost requirements. Preserve the statistics, failed controls, traces and unresolved hypotheses so a
successor can challenge the reasoning without repeating discarded avenues. No cause or production repair is
claimed, and no barrier/tracking workaround follows from making the investigation non-blocking.

## Current Vulkan/OpenGL scope check (16 Nov, official `b1451eb11`)

The operator asked whether the native core still benefits and whether Vulkan avoids this observed excess.
A fresh matched comparison uses the official ABI25 binary from run43929409887, manifest and loaded-module hashes
verified. Both APIs run the same canonical passes, targets and settings at3840×2176, actual1x, with full/high
before and after brackets. Whole-record median milliseconds:

| API / bracket | Full | High threshold | Full minus high |
|---|---:|---:|---:|
| OpenGL / before |5.2756|2.9010|2.3746|
| OpenGL / after |5.2306|2.9102|2.3204|
| Vulkan / before |2.6076|2.6052|0.0024|
| Vulkan / after |2.6052|2.6069|-0.0017|

All26 structural/pixel/ownership guards pass per API; each of eight cases has exactly240 requested settings
records and239 finite GPU samples, with zero abandoned/busy slots. Cached diagnostic controls are off; no
draw-local queries, external/untracked passes, flushes or allocation/object churn are recorded. The canonical
whole-record timer reports `wait_for_results=false`. The unchanged source retains the same instanced sprite draw;
the threshold changes gather/light data and visible contributions. The difference is not isolated raster time.

Corresponding before/after RGBA frames are exact within each API, with visible full/high differences. Cross-API
PNGs differ at two full-scene pixels and one high-scene pixel, maximum one channel code; the separate canonical
gate/parity regression on this binary passes rule(a), rule(b) and analytic checks. The lead inspected native images
and an independent High auditor checked receipts and PNG differences. Vulkan synchronization/shader-access
validation loaded; ten recorded Qt defectA errors are excused and zero unexplained errors/warnings remain;
the instance-creation loader warning is retained. Scene resources return to their exact baseline and canonical
host/module/instance teardown passes. Separate validation negative-control rounds are not part of this cost run.

This current fixture avoids the observed OpenGL full/high excess on Vulkan, consistent with the older cost
receipt. It supports continued native/Vulkan work, while leaving the OpenGL cause and performance admission
open. It does not make defocus free, establish global Vulkan immunity, prove an overall product speedup or
justify a production barrier. Fixed API order and one pair per backend limit inference. Endpoint GPU readings
were0%/210MHz before each API,87%/2775MHz after GL and0%/2775MHz after Vulkan; they do not establish continuous
quietness or matching clocks throughout. No additional load generator or profiler was launched.

`20261116_backend_scope_b1451eb11/summary.json` retains timings, counters, machine facts, provenance and verdicts;
`cross_api_pixel_diagnostic.json` retains the PNG comparison. The bounded executable helper and predeclared
interpretation are in `20261116_backend_scope_and_next_falsifier/`, helper SHA256
`3c667e647c69f2671368b863adb88a4204f1fc302d13de5ff9860cb802f029ef`.

## Evidence and repeatable entry points

The retained evidence is under `.artifacts/evidence/native_core/n3_4/`:

- `20261116_n34_individual_sites_abi23/summary.json` and `20261116_n34_flags_abi25/summary.json`: site and flag isolation with counts, pixels and recorded machine conditions.
- `20261116_n34_gl_trace/`: late-attach 1x command capture, sidecar guards and text dump. `20261116_n34_boundary_tracking_combo/trace/` contains the combined-control trace, barrier counts, query logs, selected calls, replay comparison and retrospective invocation receipt; `untraced/combo_check.json` contains the untraced 240-record comparison.
- `20261116_n34_boundary_tracking_combo/combo_check.py` is the bounded evidence helper. Its 16-frame mode is for tracing only; its 240-frame mode is the diagnostic comparison, and its off brackets must actually show a stable excess before drawing conclusions.
- `20261116_n34_aligned_native_pair/` retains the aligned native repeat and machine brackets; its wrapper is `.artifacts/scratch/n34-diagnosis/aligned_native_pair.py`. `20261116_n34_python_whole_pair/` retains the executable Python helper, source hashes, guarded JSON receipt and first full/high PNGs. These are diagnostic evidence, not portable acceptance benchmarks.
- `20261116_n34_native_wait_control/` retains the executable blocking-read wrapper, unchanged combo results and automatic invocation/source/machine/timer receipt.
- `20261116_n34_compiled_shader_comparison/` retains submitted-source hashes, corrected conventions research and
  `python_texture_size_pair.py` with `uniform_size/`, `query_size_0/`, `query_size_1/` receipts/images/shader diffs.
  Use `--sprite-size-source uniform-size|query-size-0|query-size-1 --baseline-json <original-whole-pair-json>
  --out-dir <new-directory>` with `--repo` and `--module-dir`; level1 must fail its full-output pixel predicates.
- `20261116_n34_uniform_submission/` retains the separate `python_uniform_pair.py`, primary-source research,
  declaration-only shader diffs and `buffered/`, `loose/`, `wrong_size/` receipts/images. Use `--sprite-uniforms
  buffered|loose|wrong-size --baseline-json <original-whole-pair-json> --out-dir <new-directory> --dump-shaders`
  with the usual `--repo` and `--module-dir`. The real wrong-size run must exit nonzero for its bad pixels.
- `20261116_n34_python_populated_vao/` retains the guarded populated-VAO output and images; the Python helper's `--populated-vao --baseline-json <prior-json>` mode enforces corresponding baseline pixels and protects the original output directory. The original helper was extended before being archived, so `python_whole_pair_baseline_used.py` was reconstructed retrospectively by reversing that option patch; `baseline_helper_provenance.json` states that no contemporaneous whole-helper hash existed. Original JSON/PNGs and recorded owner-function hashes remain preserved and independently comparable.
- The current harness exposes the guarded individual-site and flag diagnostic through `python native/core/python/post_stage_check.py --apis opengl --rounds defocus_boundaries --label <new-label>`. It needs a matching built native module and an available OpenGL GPU. Running it creates new evidence; it does not reproduce the historical machine conditions.
- The saved trace can be re-analysed with `python .artifacts/evidence/native_core/n3_4/20261116_n34_boundary_tracking_combo/analyze_replay.py`; it maps the saved query logs and rewrites its analysis files. Exact replay arguments and the trace hash are in `trace/replay_invocations.json`.

References: [Qt 6.12 OpenGL backend](https://github.com/qt/qtbase/blob/v6.12.0/src/gui/rhi/qrhigles2.cpp), [Qt begin-pass flags](https://doc.qt.io/qt-6.12/qrhicommandbuffer.html#BeginPassFlag-enum), [OpenGL 4.6 specification](https://registry.khronos.org/OpenGL/specs/gl/glspec46.core.pdf), and the NVIDIA sources linked in D17. The accounting, nonfinite parity, readback and effective-sample repairs from the same audit are separately recorded in R-228 through R-231.
