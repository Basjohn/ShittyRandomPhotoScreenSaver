# R-237: Reserved conventions layouts and unsupported descriptor sets passed admission

**16 November 2026. Source repair; official build and focused/native proof pending.**

Draw admission recognized `SrpssConventions` by block name and binding17 without requiring the canonical host
layout. A stage-only or fullscreen shader could redefine members, types, offsets or arrays while the host still
bound the fixed `ConventionsBlock`. Cross-stage equality cannot establish an absolute reserved layout. Geometry,
fullscreen and compute resource admission also omitted an absolute descriptor-set check; comparing shader pairs
only establishes agreement, not support by QRhi's one set-zero binding plan.

On official `b1451eb11`, 53 GPU-free actual-reflection cases give 20 valid controls and33 intended failures:
malformed conventions names/types/offsets/sizes and equal-size arrays/nested structs are accepted in vertex-only,
fragment-only and fullscreen packs; nonzero descriptor sets are accepted across own/conventions/storage/sampler
geometry resources and fullscreen/compute uniform, sampler, storage-buffer and storage-image resources. No unsafe
pipeline or undefined draw is required. Canonical shared, stage-only, alias and set-zero controls pass.
Evidence: `.artifacts/evidence/native_core/n3_2/20261116_reserved_resource_old/` retains XML, logs and module manifest.

The repair checks resource descriptor sets before binding-plan assembly in all three owners. Supported resources
must use set0; existing separate-resource/push-constant refusals remain. Draw conventions must match deep reflection
of the embedded production capture shader, which consumes the canonical `srpss_conventions.glsl` include. Its owned,
immutable reflection must contain exactly one valid block at the fixed host size/binding/set. Comparing normalized
uniform blocks excludes only pack-local `structName`; it does not duplicate a member-layout schema. Compute still
rejects conventions because a dispatch has no target. No ABI change, per-record work, shader bake or fallback is added.

Independent High source review is clear. Rebuilt positive/negative cases and shipped geometry/fullscreen/compute
native regression remain required. The tests are `tests/test_native_reserved_resource_admission.py`; D15 owns the
stable admission contract. The original cross-stage repair remains separately recorded in R-235.

Primary source: [Qt6.12 Vulkan pipeline and descriptor binding](https://github.com/qt/qtbase/blob/v6.12.0/src/gui/rhi/qrhivulkan.cpp).
Both graphics and compute create one descriptor layout, and binding uses firstSet0/descriptorSetCount1. The pinned
source and exact lines are retained in `.artifacts/scratch/reserved_resource/`.
