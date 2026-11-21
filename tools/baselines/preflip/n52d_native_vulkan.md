### Pre-flip reference pack: n52d_native_vulkan (e24549ad3, native-vulkan)

Recorded 2026-11-21T21:11:11 to 2026-11-21T21:13:21; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- Control 2160p (NVIDIA GeForce RTX 4090/PCIe/SSE2): offscreen Crossfade control 0.0386 ms quiet GPU, admitted 5/5.
- First row's conditions: displays on; GPU clock 825.0 MHz, P3, 52.73 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 2165.0}, {'pid': 24816, 'name': 'python.exe', 'cpu_core_pct': 102.2}, {'pid': 24264, 'name': 'python.exe', 'cpu_core_pct': 36.2}, {'pid': 5576, 'name': 'python.exe', 'cpu_core_pct': 21.9}, {'pid': 4, 'name': 'System', 'cpu_core_pct': 12.8}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `transition/block_spins/2160p/idle` | 187.2 | 1.2 / 1.8 | 5.3 / 6.1 | 0.0 | 0.00 | 48.1 | 1.982 | 831 / 1541 | n/a |
| `transition/crumble/2160p/idle` | 185.2 | 1.1 / 1.6 | 5.3 / 6.1 | 0.0 | 0.00 | 48.6 | 2.053 | 882 / 1812 | n/a |
| `transition/glass_shatter/2160p/idle` | 184.4 | 1.0 / 1.6 | 5.4 / 6.2 | 0.0 | 0.00 | 48.1 | 2.035 | 869 / 1770 | n/a |
| `transition/pixel_accretion/2160p/idle` | 188.4 | 1.1 / 1.6 | 5.2 / 6.0 | 0.0 | 0.00 | 44.8 | 2.106 | 873 / 1773 | n/a |

Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal outside it; the first frame from the run's start):

| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |
|---|---|---|---|---|
| `transition/block_spins/2160p/idle` | 5.3 / 6.1 / 15.0 | 11.3 | 0 (> 33.0 ms) | pass |
| `transition/crumble/2160p/idle` | 5.3 / 6.2 / 13.8 | 7.8 | 0 (> 33.0 ms) | pass |
| `transition/glass_shatter/2160p/idle` | 5.4 / 6.2 / 18.0 | 9.6 | 0 (> 33.0 ms) | pass |
| `transition/pixel_accretion/2160p/idle` | 5.2 / 6.0 / 17.3 | 9.6 | 0 (> 33.0 ms) | pass |
