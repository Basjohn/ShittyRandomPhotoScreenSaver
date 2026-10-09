# R-167: Spectrum 2D ghost control disabled by source projection

## Evidence (2026-10-09)

Operator reports all four R166-focused Windows test modules passing, while 2D
Spectrum shows neither ordinary trailing ghosts nor Rainbow Ghost. The
operator-supplied `Preset 1 (Organs)` snapshot explicitly sets
`spectrum_ghosting_enabled=true`, `spectrum_rainbow_ghost=true`,
`spectrum_ghost_alpha=0.71`, and `spectrum_ghost_decay=0.18`. The accompanying
20:58–21:00 runtime logs show Spectrum was active, shader source loaded, and
playing frames carried live Spectrum data. The logs do not contain a ghost
uniform/peak trace and do **not** independently prove its render output.
Extruded Spectrum Rainbow Ghost is physically accepted by the operator.

## Root cause

`core/settings/visualizer_mode_registry.py` declared
`spectrum_ghost_controls=True` for `extruded_spectrum`, but omitted it for
`spectrum`. `widgets/spotify_visualizer/source_config_applier.py` therefore
entered its non-ghost-family fallback and unconditionally assigned
`resolved["spectrum_ghosting_enabled"] = False` for the actual 2D Spectrum mode.
`QuickDisplayVisualizerOwner._configure` applies that resolved map to the
logical tick state. Logical frame capture and the Quick renderer then read the
disabled state, causing ordinary and Rainbow Ghost alike to vanish.

## Repair and regression gate

Declare the existing ghost capability on Spectrum's canonical mode descriptor.
Leave the common source projection, individual authored presets, existing
Spectrum peak/runtime clock, GLSL fragment shader, and accepted Extruded pass
unchanged. A new focused test in `test_spectrum_rainbow_ghost_contract.py`
passes synthetic enabled/disabled Spectrum configurations through the actual
mode-source resolver and logical-settings apply path, while independently
checking Extruded's owned control projection. This test fails against the
original R166 Spectrum descriptor.

**Pending operator acceptance:** Run the focused Windows test command and
physically check visible normal and Rainbow Ghost in 2D Spectrum, both while
playing and over decaying peaks. No full-suite gate or product build required.
