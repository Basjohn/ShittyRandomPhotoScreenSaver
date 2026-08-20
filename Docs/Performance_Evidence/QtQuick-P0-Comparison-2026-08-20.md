# Qt Quick P0 common-workload comparison — 2026-08-20

## Scope

This record covers the first comparable standalone threaded `QQuickWindow` P0
candidate. It uses the same deterministic 15-second Slide + Bubble workload as
the preserved worker+push P0 references.

Common workload SHA-256 for every worker and Quick run in this record:

```text
0881aa60ea36cc67a50d2a7ae7cee688c36b8557a86a2aa81661704da9184cf8
```

No worker+push baseline was rerun.

## Operator load classification

Two captures were launched before the operator clarified the actual load. The
operator explicitly authorized correcting their embedded load labels. The raw
executed run IDs and window titles remain unchanged for PresentMon correlation.

| Evidence pair | Actual load | System CPU p50 / p95 | Label provenance |
|---|---:|---:|---|
| `QtQuick-P0-External-Heavy-01.*` | external-heavy | 68.3% / 72.0% | operator correction from `light` |
| `QtQuick-P0-External-Heavy-02.*` | external-heavy | 65.0% / 76.7% | captured correctly |
| `QtQuick-P0-Light-01.*` | light | 9.8% / 13.5% | operator correction from `external-heavy` |
| `QtQuick-P0-Light-02.*` | light | 10.2% / 14.0% | captured correctly |
| `QtQuick-P0-Light-03.*` | light | 9.7% / 11.5% | captured correctly |

The passive CPU samples independently support the operator classification.

The preserved worker heavy reference had the same metadata problem. Its
embedded `load_label` is corrected to `external-heavy` in
`WorkerPush-P0-Heavymanual-01.json`; its executed run ID remains unchanged.

## Quick architecture proof

All five Quick runs report:

- `valid_internal_run=true`;
- exactly two top-level presented `QQuickWindow` surfaces;
- actual scene-graph API `OpenGL` for both windows;
- `QSG_RENDER_LOOP=threaded`;
- one render-thread ID per window, each distinct from the GUI thread;
- no native window created by the logic-only replay `QWidget`;
- `completed_physical_frames=null` internally because `frameSwapped` is only a
  queued-for-presentation proxy.

External physical evidence is the paired PresentMon CSV. PresentMon defines
`DisplayedTime` as how long a frame remained displayed; `NA` means the frame
was not displayed. See the official
[PresentMon console CSV contract](https://github.com/GameTechDev/PresentMon/blob/main/README-ConsoleApplication.md#comma-separated-value-csv-file-output).

## Physical-tail result

`Composed: Copy with GPU GDI` row counts match the internal 165 Hz screen-0
proxy counts. `Hardware: Legacy Flip` row counts match the internal 60 Hz
screen-1 proxy counts. This is the available display mapping because installed
PresentMon 2.5.1 reports `SwapChainAddress=0x0` and does not expose the newer
display-metadata option. One light run put both windows in the GDI mode and is
therefore retained only as a combined physical-tail sample.

Displayed-time values below are milliseconds. Counts are displayed frames with
`DisplayedTime >= 25 ms`.

| Candidate / load | Display path | runs | p95 | p99 | max | >=25 ms |
|---|---|---:|---:|---:|---:|---:|
| worker light | 165 Hz / GDI | 1 | 25.55 | 124.46 | 1358.86 | 12 / 221 |
| Quick light | 165 Hz / GDI | 2 separable | 9.47–9.97 | 17.45–23.30 | 236.59–236.60 | 3–4 / 489–582 |
| worker heavy | 165 Hz / GDI | 1 | 58.31 | 253.76 | 2280.88 | 26 / 185 |
| Quick heavy | 165 Hz / GDI | 2 | 12.15–12.16 | 41.38–53.46 | 418.57–451.44 | 16–18 / 617–711 |
| worker light | 60 Hz / legacy flip | 1 | 19.21 | 27.76 | 55.73 | 9 / 799 |
| Quick light | 60 Hz / legacy flip | 2 separable | 17.62–17.69 | 18.25–19.72 | 26.17–33.82 | 2 / 892–893 |
| worker heavy | 60 Hz / legacy flip | 1 | 21.67 | 58.87 | 69.50 | 15 / 697 |
| Quick heavy | 60 Hz / legacy flip | 2 | 19.38–19.72 | 20.95–21.68 | 61.59–62.87 | 1–3 / 864–865 |

The non-separable third Quick light run recorded combined p95 `12.14 ms`, p99
`16.84 ms`, max `248.73 ms`, and four displayed durations at or above 25 ms.

## Current conclusion

The experimental arm now exists and the first repeated physical evidence says
that moving presentation ownership to standalone threaded `QQuickWindow`
materially improves p95/p99 and severe-gap frequency under both lower and
higher system load. The 165 Hz maximum tail is still poor (roughly 237 ms light
and 419–451 ms heavy), so this is evidence for continuing the Quick path, not a
claim that presentation is solved.

The remaining acceptance input is the operator's eyes-on note for Slide
continuity, Bubble continuity, and startup flash/flicker. Do not rerun the
worker heavy reference.
