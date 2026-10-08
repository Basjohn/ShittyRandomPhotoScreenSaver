# R-120 | E8 Extruded cast-shadow receiver audit

**Authority:** R-119 full-tree Godzip + user's 2026-10-08 near-front screenshot and 1,060/1,060 Windows pytest gate. This is a source-path and projection audit, **not yet a real-host GL acceptance**. The image shows an Extruded reflection but no discernible southeast cast at the user's highest tested strength. Do not claim E8 closed.

## Findings (not another opacity tweak)

1. The source path *exists*: mode parameter capture (`config_applier.extruded_spectrum_parameters`) → `QuickExtrudedSpectrumRenderer.render` → `uPass=4` cuboid projection → `directional_shadow_pass` (one GL_MAX silhouette union in the existing `SceneTarget`) → retained overlay composite. Opaque bars and their floor reflection are rendered **after** the shadow. No additional target or continuous render driver is present.
2. The old shadow receiver was the exact horizontal world plane `world.y = 0`. In a front-on view that plane projects edge-on: even a very dark cast has effectively zero vertical extent. Near-front tilt, opaque bars and the floor reflection can conceal most of the cast. An alpha-only correction, R-119, cannot repair this geometry.
3. The directional input is display-owned/canonical but the old renderer interpreted its signed screen-axis tuple directly as **fixed world x/z**. The cast therefore changes or reverses its on-screen direction as the user orbits. This violates the declared global Shadow Direction contract.
4. The old real-GL test for R-119's 0.45 opacity rendered **body alpha=0, reflection=0**, a useful shader/composite smoke test but not representative of the operator's actual opaque, reflecting 3D bars. This left the visual defect outside the test oracle.
5. The mode's `Cast Shadow` checkbox is **disabled by default**, but the `Shadow Strength` slider previously remained active regardless. A 100% slider alone does not admit any GL shadow pass. The user's submitted screenshot does not establish the checkbox state; do not claim which condition caused that particular image. Future UI must make this dependency unambiguous.
6. Frame allocation and Edit footprint both include cast geometry via `extruded_reach`/`extruded_footprint`. Any updated shadow projection **must** update those pure mirrors in lockstep; overflow remains the same established 3D contract.

## Correction

- Keep the existing single instanced cuboid shadow pass, its GL_MAX alpha-union, composite, light-direction input, render resources and pass scheduling. No new framebuffer, shadow-map cadence, timer, per-mode camera or persistent geometry authority.
- Translate the canonical direction into world space with the **inverse of the existing Scene3D orbit yaw**. The operator's southeast remains down/right regardless of camera turn. Neither Settings nor a mode preset gets a new direction key.
- Use the real horizontal receiver at steep/top-down tilt. As the camera flattens and that plane disappears edge-on, visually project into the **already established reflection-side floor receiver** just below the bar bases. The receiver-offset interpolation is a pure mode render projection, not authored stage/view geometry. It goes to exactly zero on a top-down camera; cardinal-direction zero components remain zero. Bar positions, heights, material, mirror and actual reflection shader are untouched. This is a stylized receiver at shallow tilt, not a claim that a front-on camera can photograph a physical horizontal plane.
- Make the Strength slider visually inactive whenever Cast Shadow is disabled, and explicitly tell the operator how the two settings work. This does not auto-enable the shadow or change saved defaults/curated presets.
- Add pure CPU projection/direction tests (including a complete orbit), update the ceiling reach test, and add **real GL rendered-over-wallpaper** coverage with **opaque bars and enabled reflection at shallow tilt**. Require darkening in the visible lower receiver, not merely any pixel difference or a source-string match. These real-GL cases need a Windows run.

## Remaining gates and discipline

- Run full grouped Windows pytest after the handoff. The new render-GL shadow test is included in `tests/test_qtquick_extruded_spectrum.py`; the CPU contract is `tests/test_extruded_shadow_receiver_contract.py`.
- Physically check **Cast Shadow enabled** and Shadow Strength 0 vs 0.45 vs 1.0 over light and dark wallpaper at both near-front and high tilt, global directions SE and NW, normal and large CUSTOM stages, reflection on and off. Validate visibly separated cast and that camera turn preserves screen direction. `--geo` `[EXTRUDED_SHADOW]` must say `pass_admitted=True` with nonzero alpha/vector. No claim based on a log alone.
- Confirm fixed stage and overflow right/bottom extent on both displays. If the screen edge clips the cast, do not secretly shrink or move Spectrum's established bar geometry to fit it.
- Keep E8 open until visual acceptance. After acceptance, next user-ordered phases are Sphere shared Scene3D camera migration → full self-audit → Python 3.13. No transition work.
