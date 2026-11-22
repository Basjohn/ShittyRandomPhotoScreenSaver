### Pre-flip reference pack: n52f_load_control (938b66f36, native-vulkan)

Recorded 2026-11-22T15:29:06 to 2026-11-22T15:33:26; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- First row's conditions: displays on; GPU clock 1920.0 MHz, P0, 54.76 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 2014.2}, {'pid': 22588, 'name': "Fortune's Eden.exe", 'cpu_core_pct': 240.0}, {'pid': 22908, 'name': 'claude.exe', 'cpu_core_pct': 58.0}, {'pid': 15300, 'name': 'firefox.exe', 'cpu_core_pct': 9.2}, {'pid': 20300, 'name': 'claude.exe', 'cpu_core_pct': 6.6}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `transition/crossfade/2160p/idle` | 164.9 | 1.2 / 1.5 | 6.0 / 6.4 | 0.0 | 0.00 | 53.2 | 1.137 | 856 / 1237 | n/a |
| `transition/disintegrate/2160p/idle` | 164.2 | 1.2 / 1.6 | 6.0 / 6.5 | 0.0 | 0.00 | 73.1 | 1.381 | 862 / 1528 | n/a |

Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal outside it; the first frame from the run's start):

| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |
|---|---|---|---|---|
| `transition/crossfade/2160p/idle` | 6.0 / 6.4 / 18.7 | 3.1 | 0 (> 33.0 ms) | pass |
| `transition/disintegrate/2160p/idle` | 6.0 / 6.5 / 18.9 | 10.3 | 0 (> 33.0 ms) | pass |
