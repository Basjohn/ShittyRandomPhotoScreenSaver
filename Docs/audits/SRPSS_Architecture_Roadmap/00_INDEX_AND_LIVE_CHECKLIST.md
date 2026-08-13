# 00 — Index and Live Checklist

Last reconciled: 2026-08-13

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
current typical-load evidence:  logs/evidence_chest/08_13_1ece5167_19_33_19_39_parser119_typical/
```

Historical commits are negative controls/reference only. Current architecture starts
from `main`.

## Roadmap Status

### Phase 0 — Evidence foundation

- [x] Historical baselines/candidates, source ownership and forensic evidence are preserved.
- [x] Current work no longer treats a historical branch/candidate as implementation authority.

### Phase 1 — Measurement foundation

- [x] Frame/request-age, task, lifecycle, resource, image-install and whole-process sampling exists.
- [x] Owner-context visualizer/compositor GPU timing is supported, bounded and parser-visible.
- [!] Per-paint query-driver calls materially contaminated the latest performance comparison; the heavyweight query profile is now explicit and awaits an ordinary-`--perf` control run.
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
- [x] Establish authoritative immutable multi-family LogRecord routing metadata and migrate the real GL program-cache producer; retain name/tag fallback for unmigrated and third-party records.
- [x] Move settings serialization/temp-write/fsync/atomic replace behind one ordered process-owned writer with revision and explicit durability boundaries.
- [x] Move Reddit normal fetch-result preparation, sparse-cache merge and post-cache persistence behind the shared IO worker and publish one immutable GUI commit.
- [x] Move Reddit startup post-cache/gate loading and blocked-gate persistence off GUI; use worker-refreshed process metadata for runtime cadence checks.
- [x] Prepare Reddit's GUI-owned static content cache before paint with exact size/DPR/revision identity, snapshot-matched hit routing and one transition-terminal coalesced rebuild.
- [x] Prepare the shared `BaseOverlayWidget` painted-frame cache at exact GUI state/geometry commits; paint validates and blits only, with explicit batching for known setter cascades.
- [x] Move Weather startup cache selection and accepted-result persistence to shared IO; publish immutable, generation/location-gated GUI commits with newest-wins atomic durability.
- [x] Move Gmail startup-cache, backend-config and DPAPI credential preparation to shared IO while retaining GUI-affine backend/OAuth facades and one coalesced settings/widget commit authority.
- [x] Add bounded owner-context visualizer GPU timer queries plus CPU paint/state-age windows without changing logical or presentation cadence. The first run exposed the PyOpenGL uint64 result-buffer contract; the corrected-query run successfully collects bounded samples.
- [x] Validate visualizer owner-context GPU collection in the corrected-query typical run: all `26` windows supported/collected with no errors or drops; Bubble remains sub-millisecond GPU and Spectrum negligible.
- [x] Validate the shared-compositor query seam: `42` supported/error-free windows show active transition shaders are normally cheap and isolate a `36–41 ms` physical-4K steady QPainter base draw.
- [x] Validate exact retained-texture steady presentation removes that base-draw spike without terminal visual discontinuity, identity regression or teardown residue.
- [x] Attribute texture-upload CPU phases in a typical teardown/churn run: ordinary uploads are dominated by redundant image preparation/source copying rather than texture submission, while cold PBO staging and pair-warm residual remain separate owners.
- [x] Validate native RGB32/ARGB32 plus direct read-only QImage-buffer upload: all `34/34` installed-run uploads use the direct path, the two copy spans are effectively eliminated, and pixel/identity/teardown bars remain closed.
- [x] Validate the correlated cold-install probe under startup and Settings recreation: all `32/32` accepted IDs are complete, all `26` steady old lookups hit, and the six generation-first misses isolate native show/context creation plus an unnecessary no-transition old upload.
- [x] Validate no-transition old-upload removal and parser-1.19 offscreen-surface/shared-context split: all `37/37` accepted installs complete, all `31/31` steady old lookups hit, and generation-first installs upload only the new destination.
- [x] Separate GL timer-query driver calls from ordinary `--perf`; `--gpu-timing` now implies PERF, samples one in eight paint observations and reports sampling coverage.
- [ ] Repeat the same typical-load Settings/CUSTOM/Bubble/Spectrum route under ordinary `--perf` before attributing the observed frame-delivery regression or changing render admission.
- [ ] Remove proven GUI-thread service/cache preparation.
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
