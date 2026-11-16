# R-233: Batched draw-parameters shader bypassed interface admission

**16 November 2026. Source repair reviewed; official built-module proof pending in Current_Plan.md.**

N3.2 checkpoint audit 4 L1 found that `checkGeometryPass` checked the optional draw-parameters vertex pack's stage
but derived bindings, block packing and vertex layout only from the plain pack. A device with multi-draw support
could therefore construct a pipeline using an incompatible shader and the plain shader's layout. Choosing the
plain form on another device did not make the declared pair valid.

The installed ABI25 module from native commit `7717614d1` accepted nine incompatible valid vertex packs through
the GPU-free `mode_blocks` entry: changed uniform binding, equal-total-size reordered uniform members, storage
binding, storage member offset, storage access qualifier, added sampler, added vertex input, moved varying output
and an added output built-in. Every rejection regression failed with `DID NOT RAISE`; four selected positive tests
passed, including the actual draw-parameters built-in variant and reordered resource declarations. No GPU pipeline
or undefined draw was needed to reproduce the admission defect.

The repair compares the two packs' reflected interfaces before deriving resources or creating any pipeline.
Qt6.12's exported equality operators include nested block members, offsets, sizes, array/matrix strides, matrix
orientation, descriptor sets and storage access qualifiers. Top-level declaration lists are compared as
permutations; nested member layout is not reordered. Outputs include built-ins. Input built-ins are intentionally
outside the comparison because draw-parameters and loop forms obtain the batch index differently; shader
semantics still require pixel parity. A mismatch names the pass, draw-parameters pack and interface category.
There is no render-thread per-record work, API/schema change, new fallback or ABI-number change.

`tests/test_native_mesh_buffers.py` crosses the real admission seam, tests the nine mutations and admits equivalent
interfaces. The equal-size block case prevents a names/binding/total-size-only comparison from blessing changed
offsets. Source review is clear; runtime acceptance requires the official rebuilt module, the focused parser tests
and the existing OpenGL/Vulkan batched-draw pixel/validation harness. Do not treat this source checkpoint as runtime
proof. The shallow sorted-transparency-pack comparison is a related, separately admitted follow-up, not repaired here.

Evidence: `.artifacts/evidence/native_core/n3_2/20261116_pack_interface_old/pytest_final.{log,xml}` records the old
module's nine failures and four passes. D15 owns the durable two-pack contract. Pinned Qt reflection sources are
retained in `.artifacts/scratch/native_pack_interface/`.

Primary references: [Qt6.12 reflection equality](https://github.com/qt/qtbase/blob/v6.12.0/src/gui/rhi/qshaderdescription.cpp)
and [reflection structures](https://github.com/qt/qtbase/blob/v6.12.0/src/gui/rhi/qshaderdescription.h).
