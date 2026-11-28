### Pre-flip reference pack: 20261128_n52h_ghosts_first_vulkan_hitch (d5e9371ab, native-vulkan)

Recorded 2026-11-28T03:18:39 to 2026-11-28T03:21:16; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- Control 2160p (NVIDIA GeForce RTX 4090/PCIe/SSE2): offscreen Crossfade control 0.0232 ms quiet GPU, admitted 3/3.
- First row's conditions: displays on; GPU clock 2775.0 MHz, P0, 53.9 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 1562.5}, {'pid': 4480, 'name': 'enshrouded.exe', 'cpu_core_pct': 407.4}, {'pid': 7664, 'name': 'python.exe', 'cpu_core_pct': 98.8}, {'pid': 40724, 'name': 'python.exe', 'cpu_core_pct': 97.0}, {'pid': 2064, 'name': 'dwm.exe', 'cpu_core_pct': 21.8}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `transition/crumble/2160p/idle` | 164.4 | 1.5 / 1.9 | 6.1 / 6.7 | 0.0 | 0.00 | 86.8 | 0.944 | 863 / 1754 | n/a |
| `transition/glass_shatter/2160p/idle` | 164.2 | 1.5 / 1.9 | 6.1 / 6.7 | 0.0 | 0.00 | 71.0 | 0.945 | 861 / 1725 | n/a |

Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal outside it; the first frame from the run's start):

| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |
|---|---|---|---|---|
| `transition/crumble/2160p/idle` | 6.1 / 6.7 / 16.9 | 11.4 | 0 (> 33.0 ms) | pass |
| `transition/glass_shatter/2160p/idle` | 6.1 / 6.7 / 17.8 | 13.0 | 0 (> 33.0 ms) | pass |
