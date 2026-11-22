### Pre-flip reference pack: d1_transitions_native_vulkan_20261122 (a177e2d01, native-vulkan)

Recorded 2026-11-22T12:50:35 to 2026-11-22T12:57:11; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- Control 2160p (NVIDIA GeForce RTX 4090/PCIe/SSE2): offscreen Crossfade control 0.0662 ms quiet GPU, admitted 3/3.
- First row's conditions: displays on; GPU clock 240.0 MHz, P0, 36.65 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 2287.2}, {'pid': 4064, 'name': 'MsMpEng.exe', 'cpu_core_pct': 10.5}, {'pid': 24284, 'name': 'claude.exe', 'cpu_core_pct': 7.9}, {'pid': 4, 'name': 'System', 'cpu_core_pct': 6.5}, {'pid': 22288, 'name': 'claude.exe', 'cpu_core_pct': 5.3}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `transition/beam/2160p/idle` | 189.3 | 0.7 / 0.9 | 5.2 / 5.8 | 0.0 | 0.00 | 37.0 | 1.831 | 967 / 1288 | n/a |
| `transition/block_spins/2160p/idle` | 185.7 | 0.8 / 1.0 | 5.3 / 5.9 | 0.0 | 0.00 | 43.5 | 1.732 | 924 / 1537 | n/a |
| `transition/burn/2160p/idle` | 187.8 | 0.7 / 0.9 | 5.3 / 5.9 | 0.0 | 0.00 | 23.8 | 1.499 | 976 / 1324 | n/a |
| `transition/crossfade/2160p/idle` | 188.3 | 0.7 / 0.9 | 5.3 / 5.8 | 0.0 | 0.00 | 29.5 | 0.421 | 969 / 1287 | n/a |
| `transition/crumble/2160p/idle` | 188.4 | 0.7 / 0.9 | 5.3 / 5.8 | 0.0 | 0.00 | 32.4 | 1.000 | 976 / 1806 | n/a |
| `transition/cube_turn/2160p/idle` | 186.3 | 0.7 / 0.9 | 5.3 / 5.9 | 0.0 | 0.00 | 23.9 | 0.760 | 969 / 1578 | n/a |
| `transition/exploding_tiles/2160p/idle` | 185.9 | 0.8 / 1.3 | 5.3 / 6.1 | 0.1 | 0.00 | 60.8 | 1.247 | 905 / 1748 | n/a |
| `transition/glass_shatter/2160p/idle` | 184.1 | 0.6 / 0.8 | 5.3 / 5.9 | 0.2 | 0.00 | 22.8 | 1.452 | 956 / 1759 | n/a |
| `transition/membrane/2160p/idle` | 184.6 | 0.7 / 0.9 | 5.3 / 5.9 | 0.0 | 0.00 | 20.0 | 1.099 | 969 / 1578 | n/a |
| `transition/page_curl/2160p/idle` | 184.7 | 0.7 / 0.9 | 5.3 / 5.9 | 0.0 | 0.00 | 28.6 | 0.988 | 969 / 1574 | n/a |
| `transition/pixel_accretion/2160p/idle` | 186.6 | 0.7 / 0.8 | 5.3 / 5.8 | 0.1 | 0.00 | 28.9 | 1.809 | 967 / 1770 | n/a |

Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal outside it; the first frame from the run's start):

| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |
|---|---|---|---|---|
| `transition/beam/2160p/idle` | 5.2 / 5.8 / 15.7 | 14.1 | 0 (> 33.0 ms) | pass |
| `transition/block_spins/2160p/idle` | 5.3 / 5.9 / 23.6 | 21.4 | 0 (> 33.0 ms) | pass |
| `transition/burn/2160p/idle` | 5.3 / 5.9 / 13.3 | 7.7 | 0 (> 33.0 ms) | pass |
| `transition/crossfade/2160p/idle` | 5.3 / 5.8 / 20.7 | 3.6 | 0 (> 33.0 ms) | pass |
| `transition/crumble/2160p/idle` | 5.3 / 5.8 / 15.0 | 6.6 | 0 (> 33.0 ms) | pass |
| `transition/cube_turn/2160p/idle` | 5.3 / 6.0 / 18.1 | 18.1 | 0 (> 33.0 ms) | pass |
| `transition/exploding_tiles/2160p/idle` | 5.3 / 6.1 / 49.8 | 10.7 | 1 (> 33.0 ms) | fail: 1 gap(s) over 33 ms ([49.8]) |
| `transition/glass_shatter/2160p/idle` | 5.3 / 5.9 / 26.1 | 20.4 | 0 (> 33.0 ms) | pass |
| `transition/membrane/2160p/idle` | 5.3 / 5.9 / 20.6 | 20.6 | 0 (> 33.0 ms) | pass |
| `transition/page_curl/2160p/idle` | 5.3 / 5.9 / 18.7 | 18.7 | 0 (> 33.0 ms) | pass |
| `transition/pixel_accretion/2160p/idle` | 5.3 / 5.8 / 25.6 | 19.4 | 0 (> 33.0 ms) | pass |
