### Pre-flip reference pack: n52f_native_vulkan (ca63ccc14, native-vulkan)

Recorded 2026-11-22T14:26:18 to 2026-11-22T15:28:51; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- Control 2160p (NVIDIA GeForce RTX 4090/PCIe/SSE2): offscreen Crossfade control 0.0640 ms quiet GPU, admitted 3/3.
- First row's conditions: displays on; GPU clock 1755.0 MHz, P0, 53.99 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 2072.2}, {'pid': 22588, 'name': "Fortune's Eden.exe", 'cpu_core_pct': 254.0}, {'pid': 4, 'name': 'System', 'cpu_core_pct': 6.6}, {'pid': 3996, 'name': 'MsMpEng.exe', 'cpu_core_pct': 6.6}, {'pid': 19324, 'name': 'Spotify.exe', 'cpu_core_pct': 5.3}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `transition/disintegrate/2160p/idle` | 64.2 | 0.9 / 1.5 | 15.5 / 16.3 | 0.2 | 0.00 | 2.1 | 1.514 | 858 / 1529 | n/a |
| `transition/volumetric_dissolve/2160p/idle` | 64.6 | 1.0 / 1.5 | 15.5 / 16.3 | 0.0 | 0.00 | 12.7 | 1.515 | 862 / 1530 | n/a |

Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal outside it; the first frame from the run's start):

| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |
|---|---|---|---|---|
| `transition/disintegrate/2160p/idle` | 15.5 / 16.3 / 47.1 | 9.8 | 1 (> 33.0 ms) | fail: 1 gap(s) over 33 ms ([47.14]) |
| `transition/volumetric_dissolve/2160p/idle` | 15.5 / 16.3 / 20.6 | 17.3 | 0 (> 33.0 ms) | pass |
