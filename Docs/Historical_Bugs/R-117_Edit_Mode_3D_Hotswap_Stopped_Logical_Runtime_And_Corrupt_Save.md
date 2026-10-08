# R-117 | 3D Edit hot-swap left old logical runtime stopped and invalid CUSTOM Save

## Operator / source evidence (2026-10-08)

Windows targeted Qt gate: **757 passed in 72.65s**, but physical test failed. In Edit on Extruded Spectrum, requesting Shockwave left only the stage and wireframe cage, no visible mode. Exiting Edit initiated a runtime shutdown and exit code 1. `logs6de7ccbbf33.zip` records:

- 05:45:58 `[SPOTIFY_VIS] Quick mode activation requested extruded_spectrum -> shockwave_grid` then `[SPOTIFY_VIS][LOGICAL] Runtime stopped`, **without** corresponding `Quick mode activation committed`.
- 05:46:14 `Live geometry promotion found retained-runtime incoherence: CUSTOM live visualizer geometry has no viewport extent`; Save triggered `save_corrupt_retained_runtime` **after** persisting the CUSTOM session.
- 05:46:23 `[LIFECYCLE_BARRIER] timeout reason=custom_edit ... python_owners={'QuickDisplayUnit': 1, 'QuickDisplayVisualizerOwner': 1}`. Native fault capture has no native exception; the logged exit code is 1.
- Scene telemetry `viz_geometry_mismatches=0` did not detect this incomplete activation.

**Root ownership flaws:** the fallible Edit profile projection occurred only *after* the outgoing audio/logical owner was stopped, with no logged activation-exception stage; old named 3D profile entries lacking `viewport_extent` could become live session items with `None`. Save persisted first and discovered invalid geometry only during retained presentation promotion. This produced a destructive session/recreation path rather than refusing incomplete state.

## R-117 correction (acceptance pending)

1. Hidden Edit target projection/validation runs **before** stopping the outgoing logical source. Failure leaves old source alive, resets the transition to idle, does not write Settings. A partial Edit selection restores the previous parked/visible profile before propagating an exception.
2. Old named 3D profile data without logical viewport hydrates a canonical transient world instead of borrowing outgoing geometry; dormant malformed session items repair both working and Cancel baselines.
3. All Edit Save/Cancel actions preflight transition phase, active named layout profile against live mode, and active logical viewport **before committing Settings**. Any mismatch rejects Save before persistence, and Cancel also rejects an unfinished activation rather than restoring through a mismatched renderer. Settings navigation respects that Cancel gate and leaves Edit/session/Settings intact. Strict retained Save promotion is unchanged for coherent inputs.
4. Hidden activation exceptions log exact stage/source/target. Before mode takeover, failures try to restore the original source and Edit profile without an added cadence/timer; post-takeover errors remain fail-closed and prevent Edit Save.
5. The projected North face marker remains derived from cage vertices and is reduced to one-quarter its former face-space size; thick white strokes within a black outline.

**Automated Windows and physical acceptance remain OPEN.** In particular, test Extruded→Shockwave→Sphere with unedited and edited named profiles, close Edit before/after target reveal, Save/Cancel/Undo, absent historical viewport values, and retired-owner barriers. No C4/Spectrum audio/response change or new geometry SSOT. E8 Extruded shadow remains queued.

## R-118 FOLLOW-UP: WHOLE GRAPH AUDIT (2026-10-08)

R-117's preflight/Save gate alone did not prove failure-path convergence. The adjacent owner/renderer/Edit/Settings/retirement audit found latent indefinite `waiting_target` when a target emits no usable frame, unhandled failure after controller mutation, incomplete provisional profile cleanup, and an unguarded completion-persistence exception after transition phase became `idle`. See `Docs/Audits/R-118_3D_Edit_Mode_Lifecycle_Adjacent_Contract_Audit.md` for source-to-owner matrix, implemented R-118 corrections, failure outcome matrix, explicitly deferred risks and Windows acceptance steps. The operator reported the R-117 initial physical behavior as good, but **did not grant G17–G21 acceptance**. R-118 remains pending Windows Qt and physical lifecycle verification.
