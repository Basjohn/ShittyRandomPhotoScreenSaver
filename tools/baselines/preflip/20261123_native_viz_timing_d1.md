### Pre-flip reference pack: 20261123_native_viz_timing_d1 (ec29a3d4e, native-vulkan)

Recorded 2026-11-23T19:09:39 to 2026-11-23T19:11:58; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- Control 2160p (NVIDIA GeForce RTX 4090/PCIe/SSE2): offscreen Crossfade control 0.0238 ms quiet GPU, admitted 3/3.
- First row's conditions: displays on; GPU clock 1560.0 MHz, P3, 44.33 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 2063.6}, {'pid': 25708, 'name': "Fortune's Eden.exe", 'cpu_core_pct': 200.6}, {'pid': 4, 'name': 'System', 'cpu_core_pct': 62.4}, {'pid': 19896, 'name': 'ChatGPT.exe', 'cpu_core_pct': 15.9}, {'pid': 20316, 'name': 'ChatGPT.exe', 'cpu_core_pct': 6.1}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `visualizer/bubble/2160p/idle` | 89.3 | 1.5 / 2.0 | 11.2 / 14.0 | 0.1 | 3.04 | 101.0 | 1.558 | 943 / 1304 | 172 |
| `visualizer/waveform_ribbon/2160p/idle` | 50.0 | 2.1 / 3.3 | 20.4 / 24.4 | 7.8 | 3.05 | 140.2 | 1.592 | 974 / 1641 | 94 |
