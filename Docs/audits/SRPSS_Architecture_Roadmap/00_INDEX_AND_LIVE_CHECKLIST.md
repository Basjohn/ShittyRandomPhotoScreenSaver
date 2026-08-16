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
| P1 fidelity/presentation lock | `[ ]` | logical cadence/edges survive fewer presentation opportunities |
| P2 bad smell 1 | `[!]` | production visualizer presentation no longer emits one auxiliary update request per logical publication |
| P3 remaining visualizer handoff | `[!]` | name or close the additional visualizer-family GUI preparation/commit owner |
| P4 bad smell 2 | `[!]` | name/fix residual no-visualizer queued-GUI-dispatch owner on the 165 Hz path |
| P5 topology/wake hardening | `[!]` | one topology authority; settled snapshot; transactional rebuild; sticky visualizer ownership; physical-off/wake recovery |
| P6 lower Phase 5 work | `[~]` | resume memory/resource/debris work after P0–P5 gates |

Do not interleave unrelated media-browser, cleanup or memory experiments into P0–P5
unless a gate directly requires them.

## Phase 5 Status

- [-] Active. `Current_Plan.md` P0→P5 owns exact order.
- [x] Adaptive timer wakeup is separated from downstream GUI/paint pending delivery.
- [x] Visualizer repaint/update request stream is a proven shared-GUI amplifier.
- [x] Visualizer shader GPU cost is too small to explain the delivery loss.
- [!] Another visualizer-family GUI owner remains unassigned to one handoff/preparation substage.
- [!] Residual non-visualizer queued-GUI-dispatch loss remains on the 165 Hz path.
- [!] Physical dual-display off→screensaver→wake can hang the ordinary installed runtime; exact blocking native owner remains open.
- [!] Current monitor wake/reconfiguration still has overlapping notification/mutation paths and first-event-style settlement that P5 must centralize.
- [!] Current visualizer recovery may fallback after a short participation delay; P5 replaces this with authoritative absence + one coarse ~60-second confirmation and event-driven return-home.
- [~] Memory/resource/debris work remains Phase 5 but follows P5.

## Immediate Blockers

| Area | Required result |
|---|---|
| P0 | completed diagnostic probe removed before measuring production presentation fix |
| P1 | edge/fidelity and mixed-refresh regression bars exist |
| P2 | one-publication→one-update presentation coupling removed without cadence change |
| P3 | remaining visualizer handoff/preparation cost named or closed |
| P4 | residual no-visualizer queued dispatch attributed to a concrete GUI owner |
| P5-A/B | one topology authority and actual quiet-period settled snapshots |
| P5-C | one retire/rebuild transaction; strict GL teardown unchanged |
| P5-D | no migration on temporary participation; fallback only after genuine absence + ~60 s coarse confirmation; return-home event-driven |
| P5-E | ordinary `grabWindow(0)` anti-flash preserved; recovery path no longer depends on synchronous desktop capture |
| P5-F | repeated ordinary installed physical-off/wake cycles recover both displays and input without Ctrl+Alt+Delete |
| Resources | memory/commit/VRAM reduced or owner-level explained after delivery/topology work |
| Evidence tooling | canonical parser/logging tests match current formats and remain read-only |

## Deferred Architecture

- Phase 6 shared GPU resource store remains conditional.
- Phase 7 broader visualizer state/presentation architecture remains conditional after P2/P3.
- Phase 8 one-surface-per-display remains deferred; current C-vs-B evidence does not justify it.
- Phase 11 hostile/soak/topology validation remains the broad release-validation phase, but P5 now contains a mandatory focused physical-wake gate because the failure is repeatable today.

Do not add benchmark narratives here; use phase reports or focused evidence records.
