# R-229 | Nonfinite post-stage pixels could pass parity

**Status:** fixed and proved 16 Nov 2026.

The FP16 parity judge converted rounded error values to signed integers before rejecting nonfinite data.
NaN/Inf could become the integer minimum, which passed positive error thresholds. An actual pre-fix NaN candidate
reported PASS. The judge now rejects nonfinite candidate, reference and delta before conversion, reports invalid
counts, and safely bounds large finite conversions. Finite equality and FP16 ULP limits remain unchanged.

Eleven focused cases cover both sides, NaN/±Inf, invalid delta units and large finite differences. All 593 retained
ABI22 arrays were finite and passed the corrected rules (a)/(b) and analytic checks; fresh ABI24 native/reference
parity also passes. This does not claim the earlier native frames contained nonfinite values.

Evidence: `native_core/n3_4/20261116_abi22_float_recheck/recheck.json` and
`20261116_n34_audit6_abi24_final/summary.json`; guard: `tests/test_native_post_stage_float_parity.py`.
