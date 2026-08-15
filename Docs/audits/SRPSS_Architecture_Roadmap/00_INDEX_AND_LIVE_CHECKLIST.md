# 00 — Index and Live Checklist

Last reconciled: 2026-08-15

This is the compact roadmap status ledger. Detailed active tasks belong only in
`Current_Plan.md`.

## Status Legend

- `[ ]` not started
- `[-]` active
- `[x]` complete with accepted evidence
- `[!]` evidence reopened a gate
- `[~]` deferred until prerequisites pass

## Authority And References

```text
working branch:                 main
approved visual behaviour:      ff93461685476bd0657aa88312fc2e35e9037880
rejected persistent lane:       666624d421b08f978c5f610571a078570150a1e7
rejected Spectrum second clock: ebfec397fb2ae0bbc1f3e95c5298c0e7d6ff1db9
historical candidate/reference: 7376bb9bb380253f3bd14079e65d7bdbca062fad
active task/evidence owner:      Current_Plan.md
historical causal reference:    logs/evidence_chest/08_09_ca830d7_14_59/
```

Historical commits are negative controls/reference only. Current architecture starts from
`main`.

## Roadmap Status

### Phase 0 — Evidence foundation

- [x] Historical baselines/candidates, source ownership and forensic evidence are preserved.
- [x] Current work no longer treats a historical branch/candidate as implementation authority.

### Phase 1 — Measurement foundation

- [x] Frame/request-age, task, lifecycle, resource, image-install and whole-process sampling exists.
- [x] Owner-context visualizer/compositor GPU timing is supported, bounded and parser-visible.
- [x] Heavy GL query-driver observation is isolated behind explicit sampled `--gpu-timing`; ordinary `--perf` contains no query-driver calls.
- [x] The ordinary-PERF control showed removing query observation does not recover the remaining delivery regression.
- [!] Absolute process memory/commit/VRAM still exceeds tracked application bytes.

### Phase 2 — Visualizer fidelity protection

- [x] Logical replay and known-bad scheduler/presentation controls exist.
- [-] Stronger source-to-state/source-to-visible/paint-receipt evidence remains active.
- [x] Bubble/Spectrum current behavioural authority remains `ff934616`.

### Phase 3 — Lifecycle and Qt/GL ownership

- [x] Full stop–destroy–recreate, generation rejection, owner-context GL deletion and fail-closed destruction barriers are established.
- [x] Settings/Edit compiled-bound-method ownership and Diagnostic reproduction are solved and historical.
- [x] Clock-shadow work is solved and removed from active work.

**Interpretation:** lifecycle is a regression contract and release stress target, not an
active causal bug investigation.

### Phase 4 — Resource containment

- [x] CPU image caches, prefetch, textures, PBOs and shared-memory ownership are bounded/accounted.
- [x] Exact current-texture reuse is repaired at the display/presenter DPR handoff.
- [x] Steady retained-base presentation consumes the retained texture instead of redrawing the full pixmap through QPainter.
- [x] Redundant ordinary texture-upload conversion/source-buffer copies are removed and validated.
- [!] Absolute RSS/private commit/VRAM still needs owner-level reduction/attribution.

### Phase 5 — Workload, delivery, GPU and resource efficiency

- [-] Active. `Current_Plan.md` owns exact order.
- [x] Repair retained-current → next-old texture identity reuse.
- [x] Move ordinary logging filtering/formatting/deduplication/rotation/file I/O behind one bounded process-owned writer.
- [x] Make persistent log sinks precede optional console presentation and expose queue-wait/file-commit/console timing separately.
- [x] Keep main as human narrative/WARNING+ fan-in while family sidecars retain canonical machine-oriented evidence.
- [x] Establish immutable multi-family LogRecord routing metadata and repair GL cache routing.
- [x] Move settings serialization/temp-write/fsync/atomic replace behind one ordered process-owned writer.
- [x] Move proven Reddit/Weather/Gmail preparation/persistence work away from avoidable GUI ownership.
- [x] Prepare shared/static GUI-owned overlay caches at commit boundaries rather than cold-building them in paint.
- [x] Validate visualizer owner-context GPU collection; Bubble remains small and Spectrum negligible.
- [x] Validate shared-compositor query seam; ordinary transition draw cost is normally small.
- [x] Validate retained-texture steady presentation removes the previous expensive 4K QPainter base draw.
- [x] Validate native RGB32/ARGB32 direct read-only upload and remove redundant ordinary copy spans.
- [x] Validate no-transition old-upload removal and cold-context span attribution.
- [x] Separate heavyweight GL timer timing from ordinary PERF and run the ordinary control.
- [-] Attribute adaptive-render wakeup lateness separately from queued-dispatch waiting and paint-pending waiting before changing admission/coalescing/scheduling.
- [ ] Audit remaining GUI-thread service/cache work only where source/runtime evidence proves it.
- [ ] Remove proven temporary compatibility/fallback debris without changing behaviour.
- [ ] Complete stronger visualizer temporal/paint-receipt protection.
- [ ] Reduce or fully attribute absolute memory/commit/VRAM.

### Phase 6 — Explicit GPU resource store

- [~] Reassess only after Phase 5. A shared store is not automatically an improvement.

### Phase 7 — Visualizer state / presentation decoupling

- [~] Blocked by Phase 5 starvation attribution and stronger goldens.
- [ ] Preserve exact logical/source cadence while presentation consumes latest immutable state.
- [ ] Prove missed paints cannot alter Bubble/Spectrum state, events, dt or publication order.
- [ ] Complete late logging taxonomy/routing refinement before Phase 8.

### Phase 8 — One compositor surface per display

- [~] Future option only if Phase 7 and GPU/context evidence justify it.
- [ ] One surface **per display**, not one global surface; compositor never owns visualizer simulation/cadence.

### Phase 9 — Transition simplification

- [~] Remove remaining terminal/temporary scaffolding while preserving local exactly-once completion.

### Phase 10 — Remaining legacy/deprecated cleanup

- [~] Remove lower-priority dead compatibility/migration debris after production/dynamic/frozen-use proof.

### Phase 11 — Hostile/soak/topology validation

- [ ] Canonical `main.py` only for official performance captures; explicit CPU/disk/GPU/mixed-load timestamps and long soak.
- [ ] Diagnostic remains for frozen-runtime/lifecycle attribution, not performance baseline comparison.

### Phase 12 — Release and documentation

- [ ] Code, current docs, historical records, rollback points and known limitations agree.

## Immediate Blockers

| Area | Required result |
|---|---|
| UI delivery | distinguish adaptive wake lateness, queued GUI dispatch waiting and paint-pending waiting before scheduling changes |
| Visualizer evidence | stronger temporal + paint-receipt controls protect exact logical cadence |
| Absolute resources | memory/commit/VRAM reach reasonable levels or have approved owner-level explanation |
| Compatibility debris | temporary Bubble façade and other proven dead alternate authorities are retired or justified |
| Evidence tooling | canonical parser/tests remain read-only, rotation-compatible and able to normalize human main-log presentation without changing sidecar semantics |

Do not add benchmark narratives here when they belong in `Current_Plan.md`, phase reports,
or the evidence guide.
