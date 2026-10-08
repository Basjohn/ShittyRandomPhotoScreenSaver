# R-119 | Expanded Qt gate, E8 visibility, and sequenced 3D/Python work

**Base:** Superseding R-118 full Godzip, source HEAD `8448717216`. The user visually accepts the R-118 3D Edit/cage behavior on their host, while the *expanded* Windows suite produced 5 failures / 1054 passed. The reported Foundry hang is not proven by this output: pytest reached `[100%]` and printed a summary at 83.51 seconds. Independently investigate any worker/process lifetime after pytest emits its summary; do not confuse an application session log with the test process's exit status.

## A. Expanded adjacent-contract corrections

1. `QuickCustomLayoutOwner._promote_live_geometry_commit` now tolerates a legacy minimal synthetic item lacking `profile_parked` (`getattr(..., False)`). Typed session items always own this flag; a parked typed profile still cannot be projected onto the one retained Visualizer. No saved format change.
2. An ordinary widget host uses its QQuickItem as the QObject parent for the shared 240ms refresh clock when it **is** a QObject; synthetic non-Qt lifecycle hosts receive an unparented clock that the host still owns and stops. Never pass a raw `object()` to `QObject.__init__`. In real scenes QObject parentage and one-clock-per-display remain unchanged.
3. The H cutover test's intentionally replaced sync stand-in must implement the real authored-view callback seam in addition to `sync_latest`; otherwise its fake raises during mode completion and again on owner retirement, triggering a fake activation failure and corrupting the test's cleanup.
4. Arrange's saver-parity test must read the Visualizer's canonical `layout_profile`, not assume legacy `default`. Ordinary families remain on `default`. No runtime fallback, no copy of planar geometry to wrong modes, and no weakening of actual landing-rect assertions.

## B. Visual Edit chrome

The cage is one read-only, projection-derived Canvas. Edge line width 2.5 → **3.5 px**. The face-tilted `N` is inverted: **black 3.8 px inner body, white 10.6 px outer outline**, yielding an additional 1px visible white rim on each side relative to R-118. Face coordinates, footprint admission, snapping and persistence are untouched.

## C. E8 shadow visibility correction (awaiting real-GL/physical confirmation)

The existing GPU floor-silhouette pass, canonical global signed direction, one target, scene3d cuboid world and stable reach are preserved. A previously undocumented multiplicative attenuation `0.34` reduced the dedicated `extruded_spectrum_shadow_strength` setting to about **12% cast alpha** at the shipped 0.45 strength and global 0.77 shadow alpha, despite the setting appearing substantial. The cast alpha now equals **canonical shadow alpha × authored Extruded strength**, without inventing a second opacity authority. Default shadow enable remains **false**, so idle/other modes have zero new render work. The existing real-GL directional and silhouette-extent tests remain; an added real-GL pixel test checks a visible ≥20/255 darkening region at strength 0.45 over light wallpaper with no body/reflection/ghost passes. `--viz` / `--geo` diagnostics log one admission snapshot per changed shadow configuration (not every audio/render frame), including effective alpha and vector. Do not declare E8 physically fixed without the user's host screenshot/testing, including dark/bright wallpaper and strength 0/0.45/1.

## D. Strict user-ordered next steps; NO transitions

1. **Fix the expanded gate and identify whether the hang is post-pytest.** This R-119 patch plus Windows test run; retain strict Qt lifecycle assertions.
2. **E8 shadow.** This R-119 visibility correction and real-GL oracle; obtain physical acceptance before closing. If still absent, trace pass admitted → draw target → alpha resolve → viewport/scissor → final Qt overlay. Avoid speculative renderer changes.
3. **Sphere true-3D migration, only after E8 acceptance.** Important factual baseline: Sphere already allocates an instanced real GL 3D cube mesh, rotates full 3D world coordinates, uses perspective depth and GL depth testing. The remaining migration seam is Sphere's PRIVATE `turnedPosition`/`cameraW`/`gl_Position` clip/camera projection and private shadow treatment, not replacing 2D painted dots with cubes. Identify the intended new camera/world-authoring contract, move it onto the shared Scene3D projection basis while preserving existing 3D voxel/audio/cohort semantics and goldens at the compatibility default, give persistent pose the canonical mode-owned lane (NEVER presets), and make projected cage use the same pure production projection. Real-GL/golden/loaded-desktop GPU p90 proof is mandatory. Do not call current Sphere a flat 2D renderer.
4. **Self-audit** after the Sphere migration, covering Settings/preset SSOT, CUSTOM/Arrange/Edit, GL resource ownership, render scheduling, latency and both displays.
5. **Python 3.13 migration**, last. Currently the pinned environment is Python 3.11.9 + NumPy 1.26.4 + PySide6 6.11.2 and Nuitka 2.7.12. NumPy 1.26.4 is not a valid Python 3.13 base; don't just modify an interpreter string. Prove CPython 3.13 wheels/API compatibility for PySide/shiboken, NumPy, WinRT, PyAudioWPatch/PortAudio, pywin32 and Nuitka, then build Windows normal/MC/SCR and run cold-start/audio/QML/3D tests. The current R-119 handoff does NOT claim to move the build interpreter.

**No transition expansion, transition effects or unrelated defaults changes are authorized in this sequence.** The operator's supplied Organs JSON remains byte-identical to its authoritative uploaded file.
