### Pre-flip reference pack: flicker_native_vulkan (22b43529a, native-vulkan)

Recorded 2026-11-22T01:25:06 to 2026-11-22T01:35:59; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- Control 2160p (NVIDIA GeForce RTX 4090/PCIe/SSE2): offscreen Crossfade control 0.0458 ms quiet GPU, admitted 3/4.
- First row's conditions: displays on; GPU clock 210.0 MHz, P8, 47.33 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 2107.0}, {'pid': 26648, 'name': 'python.exe', 'cpu_core_pct': 102.7}, {'pid': 26076, 'name': 'python.exe', 'cpu_core_pct': 96.1}, {'pid': 24284, 'name': 'claude.exe', 'cpu_core_pct': 23.7}, {'pid': 4, 'name': 'System', 'cpu_core_pct': 23.6}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `transition/beam/2160p/idle` | 63.9 | 1.2 / 1.8 | 15.6 / 16.5 | 0.5 | 0.00 | 0.0 | 1.064 | 930 / 1267 | n/a |
| `transition/block_spins/2160p/idle` | 63.8 | 1.3 / 1.8 | 15.6 / 16.6 | 0.2 | 6.70 | 39.7 | 4.553 | 922 / 1510 | n/a |
| `transition/burn/2160p/idle` | 63.8 | 1.3 / 1.8 | 15.7 / 16.6 | 0.2 | 0.00 | 10.9 | 3.329 | 933 / 1297 | n/a |
| `transition/crossfade/2160p/idle` | 64.2 | 1.4 / 2.0 | 15.6 / 16.6 | 0.0 | 0.00 | 0.0 | 2.584 | 928 / 1264 | n/a |
| `transition/crumble/2160p/idle` | 63.9 | 1.4 / 1.9 | 15.6 / 16.7 | 0.0 | 0.00 | 29.4 | 2.485 | 933 / 1778 | n/a |
| `transition/cube_turn/2160p/idle` | 64.0 | 1.4 / 1.9 | 15.6 / 16.6 | 0.0 | 0.00 | 62.0 | 2.809 | 928 / 1552 | n/a |
| `transition/glass_shatter/2160p/idle` | 63.4 | 1.1 / 1.6 | 15.7 / 16.5 | 1.6 | 0.00 | 17.6 | 2.349 | 955 / 1731 | n/a |
| `transition/pixel_accretion/2160p/idle` | 63.7 | 1.2 / 1.7 | 15.7 / 16.7 | 0.2 | 0.00 | 10.3 | 2.976 | 967 / 1746 | n/a |

Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal outside it; the first frame from the run's start):

| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |
|---|---|---|---|---|
| `transition/beam/2160p/idle` | 15.6 / 16.5 / 35.1 | 5.0 | 1 (> 33.0 ms) | fail: 1 gap(s) over 33 ms ([35.1]) |
| `transition/block_spins/2160p/idle` | 15.6 / 16.6 / 55.4 | 33.8 | 2 (> 33.0 ms) | fail: 2 gap(s) over 33 ms ([33.76, 55.44]) |
| `transition/burn/2160p/idle` | 15.7 / 16.6 / 31.3 | 7.1 | 0 (> 33.0 ms) | pass |
| `transition/crossfade/2160p/idle` | 15.6 / 16.6 / 21.4 | 5.6 | 0 (> 33.0 ms) | pass |
| `transition/crumble/2160p/idle` | 15.6 / 16.7 / 24.9 | 12.4 | 0 (> 33.0 ms) | pass |
| `transition/cube_turn/2160p/idle` | 15.6 / 16.6 / 18.1 | 8.4 | 0 (> 33.0 ms) | pass |
| `transition/glass_shatter/2160p/idle` | 15.7 / 16.6 / 31.0 | 22.6 | 0 (> 33.0 ms) | pass |
| `transition/pixel_accretion/2160p/idle` | 15.7 / 16.7 / 30.0 | 12.1 | 0 (> 33.0 ms) | pass |
