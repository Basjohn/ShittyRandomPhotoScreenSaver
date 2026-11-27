### Pre-flip reference pack: 20261127_n52f_warm_units (d36187d66, native-vulkan)

Recorded 2026-11-27T23:55:34 to 2026-11-27T23:58:00; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- Control 2160p (NVIDIA GeForce RTX 4090/PCIe/SSE2): offscreen Crossfade control 0.0340 ms quiet GPU, admitted 3/3.
- First row's conditions: displays on; GPU clock 2760.0 MHz, P0, 64.39 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 1837.1}, {'pid': 34032, 'name': 'enshrouded.exe', 'cpu_core_pct': 169.0}, {'pid': 4, 'name': 'System', 'cpu_core_pct': 107.1}, {'pid': 37004, 'name': 'python.exe', 'cpu_core_pct': 63.2}, {'pid': 2064, 'name': 'dwm.exe', 'cpu_core_pct': 17.4}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `transition/disintegrate/2160p/idle` | 164.2 | 1.2 / 1.6 | 6.1 / 6.6 | 0.0 | 0.00 | 75.1 | 0.529 | 878 / 1546 | n/a |
| `transition/volumetric_dissolve/2160p/idle` | 164.4 | 1.2 / 1.4 | 6.1 / 6.5 | 0.0 | 0.00 | 71.7 | 0.513 | 878 / 1542 | n/a |

Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal outside it; the first frame from the run's start):

| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |
|---|---|---|---|---|
| `transition/disintegrate/2160p/idle` | 6.1 / 6.6 / 19.5 | 9.3 | 0 (> 33.0 ms) | pass |
| `transition/volumetric_dissolve/2160p/idle` | 6.1 / 6.5 / 13.7 | 13.7 | 0 (> 33.0 ms) | pass |
