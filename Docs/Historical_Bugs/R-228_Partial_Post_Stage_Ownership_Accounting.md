# R-228 | Partial post-stage ownership escaped live accounting

**Status:** ownership and rebind-report repairs fixed and proved 16 Nov 2026.

`PostStages` admitted texture/chain counts only after a complete allocation, but released every owned texture on
failure. The exact original implementation with a bounded fifth-create fault reported −3 textures and −1 bloom
chain after cleanup; subsequent successful allocation and retirement retained that corruption. Sampler, binding
and pipeline wrappers also needed accounting at acquisition, including partial builds and reused bindings.

The canonical owner now counts each wrapper when acquired, updates storage bytes after each create edge, and
subtracts exactly what release owns. Partial skipped-release counts use the actual held wrappers. Native ABI24
proves fault cleanup and recovery to zero; 27 cold/resize/rebind/partial-release cases per backend pass their
ownership predicates. The unchanged no-churn predicate additionally exposed a stale published rebind count:
no stage wrappers were created at resize, but the report remained 0→0. Publication now follows the successful
rebind edge; ABI25 passes all 27 cases per backend, including unchanged no-churn checks and report 0→1.

Evidence: `native_core/n3_4/20261116_partial_accounting_original_regression/{original_result,repaired_result}.json`
and `20261116_n34_accounting_{edges_abi24,abi25_final}/summary.json`. Focused guard: `tests/test_native_post_stage_accounting.py`.
No leaked GPU allocation was demonstrated; this repairs accounting and its evidence boundary.
