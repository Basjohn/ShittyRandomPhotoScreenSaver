# R-57 — Scaled Prefetch Popped Selection Order Instead Of Descending Indices

Date: 2026-08-02  
Status: Unresolved; exact cause identified

## Classification

- [ ] COMPLETELY FUCKED
- [x] PARTIAL
- [ ] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure

The installed `3877b2c7` run emitted one real ThreadManager callback failure:

```text
Callback for task ... ImagePrefetcher._submit_load.<locals>._on_done failed:
IndexError: pop index out of range
```

Traceback:

```text
utils/image_prefetcher.py::_on_done
→ _pump_scaled_prefetch(preferred_path=path)
→ request = self._pending_scaled_requests.pop(idx)
```

The failure occurred during ordinary transition-delayed preview prefetching, before either Settings cycle.

Temporary evidence identity:

```text
logs/evidence_chest/08_02_3877b2c7_20_27/
```

## Exact Root Cause

`_pump_scaled_prefetch()` builds `selected_indices` in two passes:

1. append matching `preferred_path` requests first;
2. append other cache-ready requests until all worker slots are filled.

It then executes:

```python
for idx in reversed(selected_indices):
    request = self._pending_scaled_requests.pop(idx)
```

`reversed()` reverses insertion order; it does not sort indices numerically.

A valid queue shape can therefore be:

```text
pending indices:       [0, 1]
preferred request:      index 1
other cache-ready item: index 0
selected_indices:       [1, 0]
reversed selection:     [0, 1]
```

Popping index `0` first shrinks the list to length one. Popping index `1` then raises exactly the observed `IndexError`.

The evidence supports this shape: two scaled requests were queued, multiple raw producers completed, and a preferred raw completion triggered `_pump_scaled_prefetch(preferred_path=...)` while more than one scaled slot was available.

Confidence in this cause: **greater than 99%**.

This is not evidence of general list corruption, a missing lock, or an allocator problem. The queue is protected by `self._lock`; the defect is the assumption that selection order is already descending index order.

## Required Correction

At minimum, remove by unique numeric index in descending order:

```python
for idx in sorted(set(selected_indices), reverse=True):
    ...
```

A stronger implementation would avoid positional mutation entirely:

1. choose request objects or stable cache keys under the lock;
2. partition pending requests into selected and retained collections in one pass;
3. update `_pending_scaled_keys` and `_pending_scaled_bytes` from those exact selected requests;
4. mark valid current-generation requests inflight;
5. submit them after releasing the lock.

Whichever form is used must preserve:

- preferred-path priority;
- bounded concurrency;
- bounded pending request count and future bytes;
- generation rejection;
- raw-source lifetime until every derivative owner completes;
- exact pending-key and pending-byte accounting;
- no duplicate scaled submission.

## Required Regression Tests

The missing decisive fixture is:

```text
max_concurrent = 2
pending[0] = nonpreferred but cache-ready
pending[1] = preferred and cache-ready
preferred_path points to pending[1]
```

The test must prove both requests dispatch once, the pending list reaches zero, accounting reaches zero, and no exception occurs.

Additional tests should cover:

- preferred request at the first, middle, and final queue position;
- one, two, and maximum available slots;
- mixed cache-ready and not-ready requests;
- stale-generation requests skipped without corrupting byte/key accounting;
- `clear_inflight()` followed by late raw and scaled callbacks;
- no duplicate selected key when preferred and general selection overlap.

Existing tests cover bounded parallelism, queueing, generation invalidation, and raw-release ownership, but do not place a later preferred item ahead of an earlier general cache-ready item in the same pump.

## Runtime Consequence

The callback exception prevented part of that prefetch pump from dispatching normally. The application continued, and later image transitions, Settings recreation, and visualizer operation remained functional. It is nevertheless a real cache-delivery defect and may increase later worker fallback or cache misses.

It is independent of R-53 recreation ownership and must not be used to explain the two surviving `CustomLayoutManager` owners or the historical memory staircase.

## Evidence

- `logs/evidence_chest/08_02_3877b2c7_20_27/screensaver.log`
- `logs/evidence_chest/08_02_3877b2c7_20_27/screensaver_cache.log`
- `utils/image_prefetcher.py`
- `tests/test_image_prefetcher.py`

## Guardrail

When removing multiple positions from a mutable sequence, numeric removal order must be explicitly descending or the implementation must partition by stable identity. Priority order and positional deletion order are different contracts; never assume reversing one produces the other.