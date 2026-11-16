# R-231 | Transparency fallback used requested instead of effective samples

**Status:** fixed and proved 16 Nov 2026.

The transparency gate required sample shading for a requested multisample count even when the device's canonical
clamp resolved it to 1x. The gate now uses SceneTargets' supported-count owner and clamp at the existing gate edge,
including its capability-control generation. No independent clamp or per-record sample list is introduced.

The native proof holds the item, program and missing-sample-shading control constant while effective samples
change 4→1→4. Old ABI22 fails only the clamped phase on OpenGL/Vulkan; ABI24 admits actual 1x and restores the
multisample fallback at actual 4x. The proof reads `effective_samples`, rather than accepting requested labels.

Evidence: `native_core/n3_4/20261116_n34_audit6_abi24_final/summary.json` and the old-module control retained from
`20261116_n34_gate_old_abi22_complete`; guard: `tests/test_native_post_stage_diagnostic_harness.py`.
