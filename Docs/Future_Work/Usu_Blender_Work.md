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
| Rig | `Usu_Rig.blend` (copy): 30 bones (root, spine chain, 4-bone ears, limbs, eye-state bones), procedural per-part weights with a blended ear root, ear pivots on the root's back-top edge, Blink_L/Blink_R/Blink drivers, pose library |
| Clips | 23 actions at 30 fps, rebuilt by `USU_CLIPS.py` → `USU_EARS.py` → `USU_GROUND.py` (text blocks; source copies in `assets/usu/source/`): grounded, in place, every chain and loop seam exact, no ear/arm/body/foot interpenetration in any frame (2026-10-10) |
| Interchange | `assets/usu/Usu_Rig.fbx` from `source/usu_export_fbx.py` (rig + meshes, every clip as a take, validated by re-import); not the runtime format, which S19 decides |

---

## 3. Remaining work, in order

Each item ends with its check. Visual checks are judged from rendered previews (clip WebPs, pose sheets), not by asking the
operator; the operator accepts milestones.

### B1–B4 — done for the rough stage (2026-10-10)

- **Ground and in place** (`USU_GROUND.py`): only the root is re-keyed per frame from the evaluated meshes; contact
  frames sit exactly on the floor (worst sink had been 1.87 units), flight phases only lift, root-rotating clips keep the
  pelvis horizontally at rest; additive overlays are never grounded.
- **Ear clearance:** ears flare outward with their swing and bend along the ear (`ears(..., clear=True)`), and
  `USU_EARS.py` searches mirrored ear.01 corrections on any frame where an ear still touches an arm, the body or a foot
  (per-ear only where no mirrored turn clears), smoothed, with clip ends pinned so hand-offs and loop seams stay exact.
  Lying now rests the arms along the sides (chin-on-mittens cannot clear Usu's big head); a full roll ends back on the
  belly and PushUpFacingCamera rises from there.
- **Ear root:** weights blend head→ear.01 over ~0.65 units and the ear.01 pivots sit on the root's back-top edge, so a
  backward swing seats the root instead of lifting a knuckle above the crown (rise at NarutoRun's widest swing +0.07 →
  −0.03 units).
- **New clips:** `Jump` (markers `takeoff`/`apex`/`land`; planted outside them), `IdleLieFootTap` (IdleLie variant),
  `StrideAccent` and `DustStep` (additive; `dust` marker). `yawed()` turns body-relative swings with a yaw (fixed
  TurnToTravel's ears and LieDown's crossing legs).
- **Gate:** the BVH scan (arms vs ears/head/feet, ears vs body) reports nothing above the rest pose except upper arms
  brushing the underside of the head (26-130 face pairs, 136 already at rest by construction, hidden under the head):
  accepted, no shoulder repaint.
- **Decided against for now:** authoring IK. The ground pass already plants contacts and in-place gaits must let the
  feet slide with the moon; IK becomes useful only when clips are hand-polished.

### B4b — Polish (when the clips are refined by hand)

- Hand-polish timing and arcs per clip; IK for hand/foot locks if a polished clip needs them; stitches checked under
  extreme poses (≤4 influences). Previews: `assets/usu/review/clips_webp/` (3/4 and Side).

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
