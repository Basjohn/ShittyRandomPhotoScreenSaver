# R-84 — Usage PDH Counter Cardinality Could Masquerade As A Main-Process Handle Leak

Date: 2026-09-14  
Status: COMPLETELY FUCKED — Instrumented Attribution Awaiting Windows Soak Proof

## Classification

- [x] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure

During the stable overnight interval, main-process Windows handles appeared to climb at roughly **+19 handles/hour** while RSS, USS/private memory, thread count, shared-memory ownership, and worker resource counts remained flat. Taken alone, that graph looked like a slow application lifetime leak.

## Leading Attribution — Not Yet Closed

The apparent slope aligned overwhelmingly with `--usage`'s Windows GPU telemetry observer itself, but this remains an **instrumented hypothesis until the next Windows soak proves the residual handle slope disappears after PDH cardinality is accounted for**. Source tracing is strong enough to avoid random product fixes, not strong enough to declare the leak question solved.

`WindowsGpuUsageCollector` intentionally rebuilds a PDH query every 300 seconds so dynamic `GPU Engine` and `GPU Process Memory` instances remain discoverable. Each query owns one counter per matching engine instance and two counters per matching process-memory instance. Windows may expose a different number of instances on each rebuild.

The process-handle sample is captured before the same usage task performs the GPU rebuild, so the following 15-second usage sample observes the replacement query's new cardinality. Over the stable 04:00–13:30 interval, samples immediately following the existing PDH rebuild boundaries were sufficient to explain more than the entire net positive handle trend; non-rebuild intervals netted downward.

Source trace also proved the required lifecycle semantics:

- every rebuild calls `_close_query()` before opening its replacement;
- `CloseQuery()` owns disposal of that query's PDH counters;
- the Python counter lists are replaced, not appended;
- final `close()` drains the last query.

The present evidence makes PDH observer/cardinality effects the leading explanation and argues against blindly changing Gmail/Reddit/image lifetime code. It does **not** yet prove there is no independent product handle leak. Because the remaining uncertainty is being resolved by instrumentation rather than a shipped product repair, this incident stays **COMPLETELY FUCKED** until the instrumented Windows soak closes that question.

## Diagnostic Improvement

Do **not** reduce GPU/VRAM fidelity or lengthen/drop the 300-second rediscovery merely to make the handle graph look flatter.

`--usage` now records, with each GPU sample:

- `gpu_query_generation`;
- `gpu_engine_counters`;
- `gpu_dedicated_counters`;
- `gpu_shared_counters`;
- `gpu_pdh_counters_total`.

These values are derived from already-owned counter lists. They perform no additional OS query, enumeration, timer, or work when `--usage` is disabled. Future handle analysis can therefore compare handle steps directly with the observer's current PDH cardinality instead of treating total handles as a context-free leak oracle.

No new diagnostic sidecar is needed: this evidence belongs to `--usage`, not the already-busy `--perf` stream.

## Regression Coverage

`tests/test_usage_sampler.py` uses a dynamic fake PDH source whose engine/memory instance cardinality changes between rebuilds. It proves:

- query 1 is closed before query 2 opens;
- counter ownership is replaced rather than accumulated;
- snapshot generation/cardinality matches the current query;
- usage log output exposes the exact PDH counter denominator;
- final `close()` retires the last query and clears every counter list.

## Exit Condition From COMPLETELY FUCKED

Repeat a multi-hour Windows soak with `--usage` and compare `handles_main` against `gpu_query_generation` and `gpu_pdh_counters_total`. This is not optional acceptance polish; it is the evidence required to determine whether the observed handle slope was observer-owned or whether an independent leak remains.

Expected result for promotion to **AWAITING VALIDATION** or **SOLVED**: handle discontinuities at 300-second rebuild boundaries are explained by changing PDH query cardinality and there is no independent monotonic residual trend once that diagnostic ownership is subtracted/considered.

If a residual main-process handle slope survives that accounting, keep this record **COMPLETELY FUCKED** and add targeted Windows handle-type diagnostics in a dedicated diagnostic sidecar (not `--perf`). Do not weaken `--usage` statistics merely to flatten the graph.

## Guardrail

Diagnostic observers consume resources too. A process-wide resource graph must distinguish observer-owned dynamic cardinality from product lifetime ownership before declaring a leak. Preserve statistical fidelity; improve attribution first.
