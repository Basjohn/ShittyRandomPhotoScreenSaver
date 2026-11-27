### Pre-flip reference pack: 20261127_n52f_warm_units_disintegrate (d85202f9f, native-vulkan)

Recorded 2026-11-27T23:59:14 to 2026-11-28T00:00:31; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- Control 2160p (NVIDIA GeForce RTX 4090/PCIe/SSE2): offscreen Crossfade control 0.0204 ms quiet GPU, admitted 3/3.
- First row's conditions: displays on; GPU clock 2760.0 MHz, P0, 62.5 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 1765.8}, {'pid': 34032, 'name': 'enshrouded.exe', 'cpu_core_pct': 319.4}, {'pid': 2792, 'name': 'NZXT CAM.exe', 'cpu_core_pct': 19.1}, {'pid': 4, 'name': 'System', 'cpu_core_pct': 15.5}, {'pid': 4316, 'name': 'MsMpEng.exe', 'cpu_core_pct': 12.8}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `transition/disintegrate/2160p/idle` | 163.7 | 1.5 / 1.9 | 6.1 / 6.9 | 0.0 | 0.00 | 72.8 | 0.695 | 858 / 1522 | n/a |

Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal outside it; the first frame from the run's start):

| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |
|---|---|---|---|---|
| `transition/disintegrate/2160p/idle` | 6.1 / 6.9 / 14.7 | 12.2 | 0 (> 33.0 ms) | pass |
