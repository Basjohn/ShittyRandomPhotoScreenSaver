# 00 — Index and Live Checklist

Last reconciled: 2026-08-11

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
active task owner:              Current_Plan.md
historical causal reference:    logs/evidence_chest/08_09_ca830d7_14_59/
current typical-load evidence:  logs/evidence_chest/08_11_51ff1e03_03_14_03_21_typical/
```

Historical commits are negative controls/reference only. Current architecture starts
from `main`.

## Roadmap Status

### Phase 0 — Evidence foundation

- [x] Historical baselines/candidates, source ownership and forensic evidence are preserved.
- [x] Current work no longer treats a historical branch/candidate as implementation authority.

### Phase 1 — Measurement foundation

- [x] Frame/request-age, task, lifecycle, resource, image-install and whole-process sampling exists.
- [!] Transition GPU timing is not truthful across all transition families; owner-level GPU attribution is active P5.2B work.
- [!] Absolute process memory/commit/VRAM still exceeds tracked application bytes.

### Phase 2 — Visualizer fidelity protection

- [x] Logical replay and known-bad scheduler/presentation controls exist.
- [-] Stronger source-to-state/source-to-visible/paint-receipt evidence remains active.
- [x] Bubble/Spectrum current behavioural authority remains `ff934616`.

### Phase 3 — Lifecycle and Qt/GL ownership

- [x] Full stop–destroy–recreate, generation rejection, owner-context GL deletion and fail-closed destruction barriers are established.
- [x] Settings/Edit compiled-bound-method ownership and Diagnostic reproduction are solved and historical.
- [x] Clock-shadow work is solved and removed from active work.

**Interpretation:** lifecycle is a regression contract and release stress target, not an active causal bug investigation.

### Phase 4 — Resource containment

- [x] CPU image caches, prefetch, textures, PBOs and shared-memory ownership are bounded/accounted.
- [x] Exact current-texture reuse is repaired at the display/presenter DPR handoff; the deterministic retained-ID/one-new-upload bar passes.
- [!] Absolute RSS/private commit/VRAM and GPU busy still need owner-level reduction/attribution.

### Phase 5 — Workload, delivery, GPU and resource efficiency

- [-] Active. `Current_Plan.md` owns exact order.
- [x] Repair retained-current → next-old texture identity reuse.
- [x] Move ordinary logging filtering/formatting/deduplication/rotation/file I/O behind one bounded process-owned writer.
- [ ] Remove avoidable GUI-thread persistence/service/cache preparation.
- [ ] Attribute GPU busy across upload/transition/visualizer/presentation owners.
- [ ] Remove proven temporary compatibility/fallback debris without changing behaviour.
- [ ] Complete stronger visualizer temporal/paint-receipt protection.
- [ ] Reduce or fully attribute absolute memory/commit/VRAM.

### Phase 6 — Explicit GPU resource store

- [~] Reassess only after Phase 5. A shared store is not automatically an improvement.

### Phase 7 — Visualizer state / presentation decoupling

- [~] Blocked by Phase 5 starvation removal and stronger goldens.
- [ ] Preserve exact logical/source cadence while presentation consumes latest immutable state.
- [ ] Prove missed paints cannot alter Bubble/Spectrum state, events, dt or publication order.
- [ ] Complete full logging taxonomy/routing refinement late in Phase 7 before Phase 8.

### Phase 8 — One compositor surface per display

- [~] Future option only if Phase 7 and GPU/context evidence justify it.
- [ ] One surface **per display**, not one global surface; compositor never owns visualizer simulation/cadence.

### Phase 9 — Transition simplification

- [~] Remove any remaining terminal/temporary scaffolding while preserving local exactly-once completion.

### Phase 10 — Remaining legacy/deprecated cleanup

- [~] Remove lower-priority dead compatibility/migration debris after production/dynamic/frozen-use proof.

### Phase 11 — Hostile/soak/topology validation

- [ ] Canonical `main.py` only for official captures; explicit CPU/disk/GPU/mixed-load timestamps and long soak.

### Phase 12 — Release and documentation

- [ ] Code, current docs, historical records, rollback points and known limitations agree.

## Immediate Blockers

| Area | Required result |
|---|---|
| UI workload | routine logging/persistence and proven service/cache preparation leave GUI ownership |
| GPU | transition/visualizer/upload/presentation costs are separately measurable and actionable |
| Visualizer evidence | stronger temporal + paint-receipt controls protect exact logical cadence |
| Absolute resources | memory/commit/VRAM reach reasonable levels or have approved owner-level explanation |
| Compatibility debris | temporary Bubble façade and other proven dead alternate authorities are retired or justified |

Do not add implementation detail here when it belongs in `Current_Plan.md`.
