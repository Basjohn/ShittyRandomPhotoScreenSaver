# Usu — remaining Blender work

**Scope:** everything the Usu Moonscape vertical still needs from **Blender** (model, materials, rig, clips, export
preparation), in order, with what "done" means. The vertical's behaviour, runtime architecture (S19–S27) and gates live in
[`Usu_Moonscape.md`](Usu_Moonscape.md); this file is its authoring companion and owns no runtime decisions. The
Windows-local `assets/usu/README.md` records the asset's detailed history (never in Godzips). Authored 2026-10-10.

**Not Blender work.** The moon, craters, starscape, dust and lighting are runtime-procedural (S25–S27, `Usu_Moonscape.md`
§4): an analytic sphere with seeded craters in the shader, instanced stars, `CompactedPopulation` dust. No moon mesh is
modelled. Fur is never simulated or groomed (hair particles were tried: ~10 min a frame, nothing to bake); fuzz is sheen
now and S24 shells at runtime. Blender may optionally serve the moon as a look-development concept render (B7).

---

## 1. Previewing Usu yourself (no Blender experience needed)

1. Open `assets/usu/Usu_Rig.blend` with Blender 5.2 (`F:\Programming\Blender\blender.exe`, or double-click the file).
2. Blender shows a yellow bar: *"For security reasons, automatic execution of Python scripts in this file was disabled"*.
   Click **Allow Execution**. This switches on the small **Usu** preview panel stored in the file (text block
   `USU_PREVIEW.py`, source `assets/usu/source/usu_preview_panel.py`). It only chooses what plays; it never edits the clips.
   If you clicked Ignore: open the **Scripting** tab at the top, pick `USU_PREVIEW.py` in the text editor, press
   **Run Script**, and go back to the **Layout** tab.
3. Over the big 3D view, press **N** to open the sidebar and click its **Usu** tab.
4. **Clip:** choose a clip, then **Play** (it repeats until **Pause**); the arrows step to the previous/next clip.
5. **Camera:** Front, 3/4, Side, Back, High look through the review cameras. **Free** lets you look around yourself:
   middle-mouse drag orbits, the wheel zooms, Shift + middle-drag pans.
6. **Look:** **Felt** (fast, the felt texture under the studio lights; slightly brighter than the final renders),
   **Rendered** (the true Cycles look; takes a moment to clear up, best while paused), **Solid** (plain grey shapes).
7. **Rest Pose** stops playback and stands Usu up again. Close without saving if you changed anything by accident.

The static master is `assets/usu/Usu.blend` (no rig). Pressing `Z` over the 3D view and choosing **Material Preview**
or **Rendered** shows its textures; Solid mode shows only flat colours. Moving previews of every clip, rendered with
EEVEE from the 3/4 camera, are in `assets/usu/review/clips_webp/` (open them in a browser).

---

## 2. Where the asset stands (2026-10-10)

| Area | State |
| --- | --- |
| Static model | approved 2026-10-08 (`Usu.blend`) |
| Materials | felt v4: procedural fibre/stain/relief group on rest-pose coordinates, charcoal felt mittens, darker iris, tan thread, sheen fuzz; rebuilt by `assets/usu/source/usu_felt_materials.py` in either file |
| Rig | rough, `Usu_Rig.blend` (copy): 30 bones (root, spine chain, 4-bone ears, limbs, eye-state bones), procedural per-part weights, Blink_L/Blink_R/Blink drivers, pose library and pose tests |
| Clips | 19 rough actions at 30 fps (`USU_CLIPS.py` rebuilds them); moving previews reviewed 2026-10-10 |
| Export | nothing yet; blocked on S19 (format decided there) |

---

## 3. Remaining work, in order

Each item ends with its check. Visual checks are judged from rendered previews (clip WebPs, pose sheets), not by asking the
operator; the operator accepts milestones.

### B1 — Rig refinement

- Replace procedural weights at shoulders, hips and neck with painted/smoothed weights; remove the shoulder pinch seen when
  arms trail (NarutoRun) and the **ear-root "horn"** that pokes up at the crown when an ear swings back (Run, NarutoRun):
  give the head↔ear.01 transition a softer weight falloff, or a corrective shape keyed on ear.01 rotation.
- Authoring-only **IK** for hands and feet (foot roll pivots, hand plant targets) so contacts can be locked; clips are baked
  back to FK for export.
- Confirm every stitch stays on its owner under extreme poses; keep ≤4 influences per vertex.
- **Check:** pose tests re-rendered (`USU_POSE_TESTS.json` plus arms-trailing and ears-back), no pinch, horn, seam drift or
  stitch lift.

### B2 — Clip fixes from the 2026-10-10 moving review

| Clip(s) | Problem | Fix |
| --- | --- | --- |
| Fall, GetUp, RollOver, PushUp, PushUpFacingCamera | head, mittens and belly sink through the floor | automated **ground clamp** pass (per frame, lift the root so the lowest evaluated vertex sits on the floor, then re-key) plus planted-hand IK |
| PushUp / PushUpFacingCamera end, Stand / StandFacingCamera start | Usu floats, feet off the floor, and the hand-off poses do not match | end and start poses shared exactly between chained clips; feet planted |
| NarutoRun | trailing mittens pass through the streaming ears | lower/wider arm trail or ears higher; check from Behind, Side and Oncoming |
| Run, NarutoRun | ear-root horn (see B1) | B1 |
| Fall | the slide carries Usu out of frame | decide the root-motion owner (`Usu_Moonscape.md` §3.1): author in place, or export the slide as root delta |
| Walk | arms barely swing | a little more swing and counter-rotation |

- **Check:** clip previews re-rendered from the 3/4 camera and from the Moonscape's Behind and Side framing; no floor
  penetration, floating, or limb/ear interpenetration in any frame.

### B3 — Missing clips (from `Usu_Moonscape.md` §3.1)

- `IdleLieFootTap` (additive, occasional slower foot tipping/ear twitch), `StrideAccent`, `DustStep` (additive transient
  accents). They are authored as additive layers on the matching base clips.
- **Check:** each plays over its base clip without popping; additive layers return exactly to zero.

### B4 — Continuity and polish

- Matching boundary poses for every authored chain: Skid→Fall→GetUp, SitDown→LieDown→IdleLie,
  IdleLie→RollOver→PushUp→Stand, and loop entry/exit poses close enough for short cross-fades.
- Contacts: foot-plant markers on every locomotion loop (Walk/Jog/Run/NarutoRun already have `contact.L/R`); no foot
  sliding while planted.
- Ear motion stays keyed lightly: the runtime adds springs (S23), so authored ears must not fight them.
- **Check:** a chained preview of each sequence renders without a visible pop.

### B5 — Export preparation (needs the S19 contract)

- **Bake UVs:** a non-overlapping, packed UV layer (the current `Longitudinal_UV` mirrors, which a bake cannot use for
  unique stains).
- **Texture bake:** felt to albedo (crease dirt and stains included), normal (from the relief bump), roughness/sheen and a
  fuzz mask for S24, at 2K with 1K for lower tiers; eyes as small textures or constants. The procedural graph stays the
  source; the bake is regenerated by script.
- **Runtime mesh:** subdivision applied at a fixed level per LOD (control cages total ~13k vertices); stitches either kept
  as skinned strips at LOD0 or baked into albedo/normal at lower LODs (decided by S19/S20 measurements).
- **Animation:** blink drivers baked to keys; IK baked to FK; only deform bones exported; clip names and marker names
  frozen.
- **Check:** a test export reloaded in Blender matches the source poses and materials within tolerance.

### B6 — Export script and proof (S19 gate C2)

- An offline `tools/` exporter (Blender → validated glTF 2.0 → packed SRPSS asset) run from background Blender, with
  provenance; offscreen comparison of exported sample poses against Blender renders.
- **Check:** `Usu_Moonscape.md` gate C2.

### B7 — Optional look-development scene

- A Blender concept render of Usu on a small moon under stars with key/rim/bounce lighting to agree the palette and
  framing (Behind, Side, Oncoming) before S26/S27 are built. Concept only; nothing from it ships except agreed numbers.
- A tiling regolith detail texture may be baked here if the runtime crater shader wants one.

---

## 4. Working rules for this file

- Remove items when done (record the outcome in `assets/usu/README.md`); this file lists only open Blender work.
- Long Blender scripts run from a `bpy.app.timers` callback or background Blender (MCP request timeout).
- Edits happen on copies or with a dated backup beside the blend; `Usu.blend` stays the static master.
