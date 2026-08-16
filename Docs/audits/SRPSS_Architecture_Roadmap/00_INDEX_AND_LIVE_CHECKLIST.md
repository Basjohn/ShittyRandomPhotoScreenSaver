# 00 — Index and Live Checklist

Last reconciled: 2026-08-16

This is the compact roadmap status and **audit-priority ledger**. Detailed active tasks
belong only in `Current_Plan.md`. Detailed accepted delivery evidence belongs in
`Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md`.

## Status Legend

- `[ ]` not started
- `[-]` active
- `[x]` complete with accepted evidence
- `[!]` evidence reopened or split a gate
- `[~]` deferred until prerequisites pass

## Authority And References

```text
working branch:                 main
approved visual behaviour:      ff93461685476bd0657aa88312fc2e35e9037880
active task owner:               Current_Plan.md
delivery evidence owner:         Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md
cleanup/test debt owner:         Future_Cleanup.md
rejected persistent lane:        666624d421b08f978c5f610571a078570150a1e7
rejected Spectrum second clock:  ebfec397fb2ae0bbc1f3e95c5298c0e7d6ff1db9
```

## Current Audit Priority

| Priority | State | Required result |
|---|---|---|
| P0 diagnostic cleanup | `[-]` | remove completed A/B/C monkeypatch/CLI/hotkey scaffolding; keep passive delivery metrics |
| P1 fidelity/presentation lock | `[ ]` | tests prove logical cadence/edges survive fewer presentation opportunities |
| P2 bad smell 1 | `[!]` | production visualizer presentation no longer emits one auxiliary update request per logical publication |
| P3 remaining visualizer handoff | `[!]` | name or close the additional visualizer-family GUI preparation/commit owner |
| P4 bad smell 2 | `[!]` | name/fix residual no-visualizer queued-GUI-dispatch owner on the 165 Hz path |
| lower Phase 5 work | `[~]` | resume memory/resource/debris work after P0–P4 gates |

Do not interleave unrelated media-browser, cleanup or memory experiments into P0–P4
unless a gate directly requires them.

## Roadmap Status

### Phase 0 — Evidence foundation

- [x] Historical baselines/candidates and forensic references are preserved.
- [x] Current work uses `main` rather than a historical candidate as implementation authority.

### Phase 1 — Measurement foundation

- [x] Frame/request-age, event-loop, task, lifecycle, resource and image-install sampling exists.
- [x] Passive delivery-stage attribution separates deadline wake lateness, queued GUI dispatch and paint-pending wait.
- [x] Owner-context visualizer/compositor GPU timing is explicit and bounded behind `--gpu-timing`.
- [!] Absolute process memory/commit/VRAM still exceeds tracked application bytes.

### Phase 2 — Visualizer fidelity protection

- [x] Logical replay and known-bad scheduler/presentation negative controls exist.
- [-] P1 must extend edge/presentation-opportunity protection before the P2 production fix is accepted.
- [x] Bubble/Spectrum behavioural authority remains `ff934616`.

### Phase 3 — Lifecycle and Qt/GL ownership

- [x] Full stop–destroy–recreate, generation rejection, owner-context GL deletion and fail-closed destruction barriers are established.
- [x] Settings/Edit compiled ownership, Diagnostic ownership and clock-shadow incidents are historical regression contracts.

### Phase 4 — Resource containment

- [x] CPU caches, prefetch, textures, PBOs and shared-memory ownership are bounded/accounted.
- [x] Current→old texture identity, retained-base presentation and redundant ordinary upload-copy work are closed.
- [!] Absolute RSS/private commit/VRAM remains open independently of delivery work.

### Phase 5 — Workload, delivery, GPU and resource efficiency

- [-] Active. `Current_Plan.md` P0→P4 owns exact order.
- [x] Adaptive timer wakeup is separated from downstream GUI/paint pending delivery.
- [x] Visualizer repaint/update request stream is proven a material shared-GUI amplifier by same-process A/B/A.
- [x] Visualizer shader GPU cost is proven too small to explain the loss.
- [x] Hiding the still-live auxiliary GL surface adds only a modest benefit beyond suppressing requests.
- [!] Another visualizer-family GUI owner exists but is not yet assigned to one handoff/preparation substage.
- [!] A residual non-visualizer queued-GUI-dispatch owner remains on the 165 Hz path.
- [~] Memory/resource/debris work remains Phase 5 but is lower leverage until P0–P4 close.

### Phase 6 — Explicit GPU resource store

- [~] Reassess only after active Phase 5 delivery/resource evidence. A shared store is not automatically an improvement.

### Phase 7 — Generalized visualizer state / presentation boundary

- [~] The **minimal proven presentation correction is promoted into Phase 5 P2**.
- [ ] Phase 7 remains the broader/generalized state-presentation architecture only if P2/P3 evidence warrants it.
- [ ] Preserve exact logical/source cadence while presentation consumes valid immutable state and protected edges/events.

### Phase 8 — One compositor surface per display

- [~] Deferred. Current C-vs-B evidence does not show enough incremental surface-existence cost to justify the lifecycle risk.

### Phase 9–10 — simplification / remaining legacy cleanup

- [~] Lower priority than active delivery owners; one proven authority at a time.

### Phase 11 — hostile/soak/topology validation

- [ ] Canonical `main.py` only for official performance comparisons; explicit observer/load manifest.

### Phase 12 — release and documentation

- [ ] Code, `Current_Plan`, phase reports, cleanup ledger, roadmap and limitations agree.

## Immediate Blockers

| Area | Required result |
|---|---|
| P0 | completed diagnostic probe removed before measuring production fix |
| P1 | edge/fidelity and mixed-refresh regression bars exist |
| P2 | one-publication→one-update visualizer presentation coupling removed without cadence change |
| P3 | remaining visualizer-family handoff/preparation cost named or closed |
| P4 | residual no-visualizer queued dispatch attributed to a concrete GUI owner |
| Resources | memory/commit/VRAM reduced or owner-level explained after delivery work |
| Evidence tooling | canonical parser/logging tests match current formats and remain read-only |

Do not add benchmark narratives here; use the Phase 5 report.
