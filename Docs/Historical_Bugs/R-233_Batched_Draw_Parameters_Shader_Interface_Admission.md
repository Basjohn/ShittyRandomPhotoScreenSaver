# R-233: Batched draw-parameters shader bypassed interface admission

**16 November 2026. Source repair reviewed; official built-module proof pending in Current_Plan.md.**

N3.2 checkpoint audit 4 L1 found that `checkGeometryPass` checked the optional draw-parameters vertex pack's stage
but derived bindings, block packing and vertex layout only from the plain pack. A device with multi-draw support
could therefore construct a pipeline using an incompatible shader and the plain shader's layout. Choosing the
plain form on another device did not make the declared pair valid.

The installed ABI25 module from native commit `7717614d1` accepted nine incompatible valid vertex packs through
the GPU-free `mode_blocks` entry: changed uniform binding, equal-total-size reordered uniform members, storage
binding, storage member offset, storage access qualifier, added sampler, added vertex input, moved varying output
and an added output built-in. The final GPU-free recheck admits all nine mutations; the initial pytest run's
equal-size fixture error is recorded below. Valid controls pass, including the actual draw-parameters built-in
variant and reordered resource declarations. No GPU pipeline
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
module's initial eight admitted mutations, one invalid equal-size fixture precondition and four passes. The corrected
same-size mutation swaps `mat4` and `vec4` (84 bytes in both packs). `final_cases.json` and
`recheck_final_cases.py` record all nine final mutations admitted and three valid controls passed on the SHA-verified
preserved old module, without replacing the installed module. D15 owns the durable two-pack contract. Pinned Qt reflection sources are
retained in `.artifacts/scratch/native_pack_interface/`.

Primary references: [Qt6.12 reflection equality](https://github.com/qt/qtbase/blob/v6.12.0/src/gui/rhi/qshaderdescription.cpp)
and [reflection structures](https://github.com/qt/qtbase/blob/v6.12.0/src/gui/rhi/qshaderdescription.h).

The first official candidate (`7a3e52023`, run43900693922) was not accepted: deep uniform-block equality also
compared generated `structName` identifiers. The valid plain and draw-parameters packs use `_42`/`_100` for
CellDraw and `_146`/`_144` for conventions despite matching bindings and layouts. The revised predicate excludes
only this translated instance identifier and retains the block name, size, binding, set and full deep member
comparison. Initial proof43pass/5fail and canonical shader dumps remain in
`.artifacts/evidence/native_core/n3_2/20261116_pack_interface_fixed/`; a subsequent official build must prove the
revised candidate. No performance or broad semantic equivalence claim follows from reflection admission.
