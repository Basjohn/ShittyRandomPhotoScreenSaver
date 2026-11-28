"""N5.2a's proof of the seven fullscreen transitions on the display's background layer (Current_Plan.md section N2b;
``rendering/quick/render/native_background.py``), in hidden hosts only (never a window on a screen), widened by N5.2b to
the five item-quad programs that are one fragment between two pictures (``N52B_VARIANTS``: Chromatic Shear, Liquid
Lens, Melt Drip, Surface Tension, VHS; ``--topic n5_2b``) and to Beam, whose sparks follow its fragment as instanced
quads of their own vertex stage (``BEAM_VARIANTS``, N5.2b's leftover), and by N5.2c to the 3D transitions drawn as
scenes (``N52C_VARIANTS``: Blinds in both styles, Cube Turn, Depth Card Cascade, Jigsaw; N4.j's photo environment, the
scene target and the opaque composite; ``--topic n5_2c``), whose photo environment must be drawn exactly once a run
(``environment_once_per_photo``), and by N5.2d to the scenes that also draw N4.i's motion blur and trails
(``N52D_VARIANTS``: 3D Block Spins, Crumble, Glass Shatter, Pixel Accretion; ``--topic n5_2d``). The Python reference is
the product's frame at the run's dpr
(``product_capture``: the item's logical size over the display's device pixels, as the runtime gives it).

A photo change runs the configured transition natively over N5.7a's background layer: the transition's own product
pack (baked from the Python renderer's fragment, ``tools/regen_qrc.py --shaders``), its values the Python renderer's
own (``FullscreenPassRenderer.block_values``), the two photos the layer's two texture slots (the destination uploaded
by its job), its progress given every frame by the run's clock (``NativeBackgroundLayer.tick``, the window's
``afterAnimating``). Real photos (the dark Usu_Underwater_Lab_1440p.png to a bright PERSONALSET photo) are processed by
the product's worker arithmetic into the display's device pixels; the display lies in the window under the overscan
placement (its scene root one device pixel right, two down), at dpr 1 and 1.5 (``background_layer_check.Scene``).

Rounds (one child process per API; OpenGL first, its frames kept for Vulkan's comparison):
  draw   every variant of ``fullscreen_pass_check.VARIANTS`` (the seven at their production defaults and with their
         options) at the widened progress values: the layer's run with its clock held at the progress, the display's
         pixels read. Rule (a) (OpenGL): equal pixel for pixel to the Python renderer (the production GL host,
         ``TransitionCapture``) drawing the same run at the same progress; its negative control (the next progress's
         reference) differs. Each run's end: the destination drawn exactly (the slots swapped, no second upload), the
         clock disconnected, and nothing at rest (no record, no pass, no tick over rest frames).
         Vulkan also through the product's route (``BackgroundRenderItem.set_transition_run`` on the native backend):
         the same pixels as the layer driven directly.
  Then rule (b): Vulkan's frames against OpenGL's (within VULKAN_TOLERANCE levels; both native).
Facts: whether the hidden host's frames fire the clock's edge (``afterAnimating``) by themselves; the run's start and
its first frame's record; validation per phase (Vulkan).

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/transition_route_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--variants burn burn_options ...] [--label n52a_transition_route]
Evidence: .artifacts/evidence/native_core/n5_2a/<date>_<label>/ (summary.json; one PNG sheet per API; the frames for the
comparison in work/: delete it once judged). Exit 0 whenever the harness ran; the verdict is the last printed line
("N52A VERDICT PASS" or "N52A VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import background_layer_check as blc  # noqa: E402  (native/core/python)
import fullscreen_pass_check as fsc  # noqa: E402
from tools import pixel_tolerance as pt  # noqa: E402

APIS = ("opengl", "vulkan")
CHILD_TIMEOUT_S = 1800
PHOTO_FOLDER = blc.PHOTO_FOLDER
#: The old photo (dark) and the new one (bright).
PHOTOS = (PHOTO_FOLDER / "Usu_Underwater_Lab_1440p.png", PHOTO_FOLDER / "Alice.(Deemo).full.1971568.jpg")
DPRS = blc.DPRS
PROGRESS = fsc.PROGRESS
DURATION_MS = fsc.DURATION_MS
VULKAN_TOLERANCE = 1
#: Lead decision (14 Nov, N5.2b), judged by the shared pixel tolerance (``tools/pixel_tolerance.py``, D12 "The pixel
#: tolerance"; checkpoint audit 4 M2): a NativeFragmentPass fragment, whose pack the core compiles from translated
#: GLSL, may differ from its Python renderer (rule a) by single levels where the two compilers round a value within
#: float error of a half level (scatter: the measured worst 48 pixels a frame, Surface Tension with options at 0.80 and
#: dpr 1.5, times 1.5), at most TIE_PIXELS pixels a frame past that at 2 levels at most, isolated or on an edge, and
#: the one specular flip where pools pinch (Surface Tension with options at 0.80: one pixel a frame, a value its
#: neighbours hold). N5.2a's seven stay exact under rule (a).
TIE_PIXELS = 8
FRAGMENT_PASS_RULE_A = pt.Tolerance("native fragment pass against its Python renderer (rule a)", scatter_pixels=72,
                                    tie_pixels=TIE_PIXELS, flip_pixels=1)
#: Rule (b), Vulkan against OpenGL, both native on one pack: the two drivers round single values differently (scatter;
#: measured worst 736 pixels a frame of N5.2a's seven, Warp at dpr 1, and 1,317 of the five, VHS at dpr 1, times
#: 1.5). The seven have no pixel past one level; the five at most TIE_PIXELS a frame at 2 levels (measured 5, Liquid
#: Lens Flood at dpr 1).
SEVEN_RULE_B = pt.Tolerance("fullscreen transition, Vulkan against OpenGL (rule b)", scatter_pixels=1100)
FRAGMENT_PASS_RULE_B = pt.Tolerance("native fragment pass, Vulkan against OpenGL (rule b)", scatter_pixels=2000,
                                    tie_pixels=TIE_PIXELS)
#: Beam's rule (b), PROPOSED (agent, 21 Nov; flips need the lead's decision, ``tools/pixel_tolerance.py``): the fragment
#: pass's bound and one flip a frame. Measured over the 54 frames of BEAM_VARIANTS (twice): one pixel in one frame
#: (beam_sparks, dpr 1.5, progress 0.35), 3 levels in every channel, isolated on a spark streak's edge, where the two
#: APIs' rasterisers decide a dim spark's coverage of a pixel differently; native OpenGL holds Python's value there
#: (rule a passes), and no other pixel of any frame is past 2 levels.
BEAM_RULE_B = pt.Tolerance("Beam (fragment and sparks), Vulkan against OpenGL (rule b)", scatter_pixels=2000,
                           tie_pixels=TIE_PIXELS, flip_pixels=1)
REST_FRAMES = 4
#: The variants driven through the product's route: each of these the run drew (N5.2b's: arrays in its block; Beam's:
#: its sparks pass in the program the route builds at the run's start).
ROUTE_VARIANTS = ("burn_options", "surface_tension_options", "beam_sparks", "cube_turn", "jigsaw_options",
                  "block_spins_both", "exploding_tiles_both", "disintegrate_fine", "volumetric_dissolve_center",
                  "edge_bloom_fine", "capillary_bloom_six")
_ALLOWED_ENV: set[str] = set()
#: N5.2b: the item-quad programs that are one fragment between two pictures (``NativeFragmentPass``), at their
#: production defaults and with their options.
N52B_TRANSITIONS = ("chromatic_shear", "liquid_lens", "melt_drip", "surface_tension", "vhs")
N52B_VARIANTS = {
    "chromatic_shear": {},
    "chromatic_shear_options": {"request_direction": "diagonal", "spread": 1.0, "slices": 14},
    "liquid_lens": {},
    "liquid_lens_flood": {"stops": 1, "refraction": 1.0, "dispersion": 1.0},
    "liquid_lens_stops": {"stops": 8, "refraction": 0.0, "dispersion": 0.0},
    "melt_drip": {},
    "melt_drip_center_in": {"request_direction": "center_in", "detail": 2.0, "depth": 1.0, "gloss": 1.0},
    "melt_drip_top_left": {"request_direction": "top_left", "detail": 0.5, "depth": 0.0, "gloss": 0.0},
    "surface_tension": {},
    "surface_tension_options": {"pools": 20, "gloss": 1.0},
    "vhs": {},
    "vhs_options": {"request_direction": "down", "tracking": 1.0, "bleed": 1.0, "noise": 1.0},
}
#: N5.2b's leftover: Beam, its fragment between the two pictures and then its sparks, the item quad drawn once a spark
#: from its own vertex stage, light added (``NativeQuadInstances``; only while Sparks is on). Its production defaults,
#: the sparks on a diagonal at full glow with the quickest cure (the longest sweep: sparks on most frames), and the
#: sparks off at the other extremes. Each keeps its frames at 0.50 and 0.65 apart (the control): the beam still
#: sweeping, or the scorch still curing (no scorch with the slowest cure would show the clean picture at both).
BEAM_VARIANTS = {
    "beam": {},
    "beam_sparks": {"request_direction": "diag_tr_bl", "sparks": True, "color": (0.25, 0.65, 1.0), "glow": 1.0,
                    "scorch": 0.0, "cure": 0.0},
    "beam_plain": {"request_direction": "up", "sparks": False, "glow": 0.0, "scorch": 1.0, "cure": 1.0},
}
#: N5.2c: the 3D transitions drawn as scenes (``NativeScenePasses``: a scene target, its passes and meshes, N4.j's photo
#: environment, the opaque composite). Each at its production defaults (the tier's 4 samples), and with options at the
#: other extremes, single-sampled (``samples`` 0: Python draws straight into Quick's framebuffer), the path rule (a)
#: proves exact; Blinds in both styles.
N52C_TRANSITIONS = ("blinds", "cube_turn", "depth_cascade", "jigsaw")
N52C_VARIANTS = {
    "cube_turn": {},
    "cube_turn_options": {"request_direction": "up", "gloss": 1.0, "samples": 0},
    # Blinds' production default is the flat style, whose request carries no slat values: 3D Slats as High draws them.
    "blinds": {"style": "slats", "slats": 16, "gloss": 0.5, "samples": 4, "request_direction": "horizontal"},
    "blinds_slats": {"style": "slats", "slats": 48, "gloss": 1.0, "request_direction": "vertical", "samples": 0},
    "blinds_slats_few": {"style": "slats", "slats": 6, "gloss": 0.0, "request_direction": "horizontal", "samples": 0},
    "blinds_flat": {"style": "flat", "feather": 0.5, "request_direction": "diagonal"},
    "depth_cascade": {},
    "depth_cascade_options": {"request_direction": "up", "cards": 14, "gloss": 1.0, "shadows": False, "seed": 7,
                              "samples": 0},
    "jigsaw": {},
    "jigsaw_options": {"pieces": 150, "order": "unordered", "seed": 9, "detail": "Performance", "samples": 0},
}
#: N5.2c's rule (a), the lead's decision (21 Nov) on r3's measurement (the ABI 36 build, 068be1f26):
#: - Single-sampled scenes (``samples`` 0): at most N52C_SCATTER_PIXELS isolated pixels a frame one level off, nothing
#:   past one level. Measured worst 1,152 a frame (Cube Turn with options), scattered over the textured faces and none in
#:   the environment's backdrop: the translated packs and Python's compiler round the faces' UVs and lighting within
#:   float error of a half level differently (N5.2b's fragment-pass scatter, on more pixels because a face fills much of
#:   the frame); the bound is the worst times 1.5. Not every one is alone (the agent's "isolated" was loose): over r3's
#:   single-sampled frames the largest group of touching one-level pixels is 19 (Cube Turn with options at 0.80, dpr
#:   1.5), so a group may hold N52C_SCATTER_GROUP (19 times 1.5) and a compact one-level patch still fails.
#: - Multisampled scenes (the tier's 4 samples) are not judged against Python (D8 point 1): the core draws its targets top
#:   row first and Python bottom row first (F1), so the driver's standard 4x pattern, (0.375, 0.125), (0.875, 0.375),
#:   (0.125, 0.625), (0.625, 0.875) and not symmetric under a vertical flip, lands mirrored on the picture: a slanted
#:   edge's pixel covers a different one of four samples (a quarter of the edge's contrast, measured up to about 2,260
#:   pixels a frame along slanted silhouettes; horizontal edges and single-sampled frames agree). The core's row order
#:   is not changed for it. Their rule (a) is their single-sampled forms' (the same geometry: ``*_options`` and
#:   ``blinds_slats*`` at ``samples`` 0); the 4x frames are judged by rule (b), Vulkan against OpenGL, both native.
N52C_SCATTER_PIXELS = 1750
N52C_SCATTER_GROUP = 28
N52C_RULE_A = pt.Tolerance("3D transition scene, single-sampled, against its Python renderer (rule a)",
                           scatter_pixels=N52C_SCATTER_PIXELS, scatter_cluster_pixels=N52C_SCATTER_GROUP)
#: Jigsaw's single-sampled scenes also admit one flip a frame on an edge (the lead, 21 Nov, as Surface Tension's): a
#: pixel of a piece's outline where the two compilers put the outline's edge either side of the pixel centre (r4:
#: Jigsaw with options at 0.05, one pixel 12 levels off, isolated on the outline, both dprs).
JIGSAW_RULE_A = pt.Tolerance("Jigsaw scene, single-sampled, against its Python renderer (rule a; a piece outline's flip)",
                             scatter_pixels=N52C_SCATTER_PIXELS, scatter_cluster_pixels=N52C_SCATTER_GROUP,
                             flip_pixels=1)
#: Blinds' flat style (one fragment between the pictures, judged as a fragment pass): its own scatter bound (the lead, 21
#: Nov): measured 128 pixels a frame one level off (progress 0 to 0.35, both dprs; the two compilers' rounding of its
#: feathered edges), times 1.5.
BLINDS_FLAT_RULE_A = pt.Tolerance("Blinds flat, a fragment pass, against its Python renderer (rule a)", scatter_pixels=192)
MULTISAMPLED_RULE_A = ("a multisampled scene: rule (b) only (D8 point 1: the sample pattern lands mirrored on Python's "
                       "bottom-first rows); rule (a) is its single-sampled form's")
#: Blinds' slats are edge-on at exactly half the run: a slat's side then covers a row only by float error, and Python
#: itself draws that row differently a hair either side (measured: row 267 grey at 0.49999, 0.5 and 0.50001, the picture
#: at 0.4999, another colour at 0.5001). A hair either side is still too near: at 0.4999 and 0.5001 the faces are so
#: near edge-on that six slats at dpr 1.5 put 3,036 pixels one level off (r4), past N52C_RULE_A, where every other pose
#: is within it. So the check takes 0.49 and 0.51 in place of 0.5 (the lead, 21 Nov), never a pose exception or a wider
#: bound for near edge-on faces.
SLAT_PROGRESS = (0.49, 0.51)
SLAT_VARIANTS = ("blinds", "blinds_slats", "blinds_slats_few")
#: Rule (b)'s flips (lead's instruction 21 Nov, as BEAM_RULE_B): measured on the ABI 36 build (068be1f26, r3) at most 3
#: pixels a frame past 2 levels, each isolated on a geometry edge, where the two APIs' rasterisers decide a pixel centre
#: within float error of the edge differently (Vulkan's clip space is OpenGL's with z halved and y flipped, so the edge
#: equations differ in their last bits): Cube Turn's slanted silhouette (up to 233 levels: the box against the
#: backdrop), a Jigsaw piece's outline, and Depth Card Cascade's card edges (options: 3 a frame at x 249-253, one card's
#: left edge, its fwidth ramp). N5.2d (22 Nov): with N5.2c's stages given ``native_clip_depth`` one frame of Depth Card
#: Cascade with options holds 4 such flips, two of them touching on one card's edge (n52c_depth_r1, both dprs); that
#: variant's rule (b) is the piece-edge flip class (``N52D_EDGE_FLIPS_B``: a card is a moving piece), for the lead.
N52C_RULE_B = pt.Tolerance("3D transition scene, Vulkan against OpenGL (rule b)", scatter_pixels=2000,
                           tie_pixels=TIE_PIXELS, flip_pixels=3)
#: N5.2d (with N4.i): the 3D transitions whose scenes also draw motion blur (the velocity, its tile max, the gather) and
#: trails (the ghosts' R8 buffer, its edges). Each at its production defaults, and single-sampled with motion blur
#: alone, trails alone, both and neither (rule a's forms), and with both at the tier's 4 samples (rule b: the velocity's
#: average resolve on both backends).
N52D_TRANSITIONS = ("block_spins", "crumble", "glass_shatter", "pixel_accretion")
N52D_VARIANTS = {
    "crumble": {},
    "crumble_motion": {"motion_blur": True, "motion_trails": False, "samples": 0, "collisions": True,
                       "piece_count": 80, "debris": 1.0},
    "crumble_trails": {"motion_blur": False, "motion_trails": True, "samples": 0, "piece_count": 24,
                       "weight_mode": 3.0, "debris": 0.4},
    "crumble_both": {"motion_blur": True, "motion_trails": True, "samples": 0, "collisions": True, "debris": 0.85},
    "crumble_plain": {"motion_blur": False, "motion_trails": False, "samples": 0, "debris": 0.0, "depth": 1.0,
                      "thickness": 0.5},
    "crumble_both_4x": {"motion_blur": True, "motion_trails": True, "samples": 4},
    "glass_shatter": {},
    "glass_shatter_motion": {"motion_blur": True, "motion_trails": False, "samples": 0,
                             "request_direction": "center_out", "shards": 140},
    "glass_shatter_trails": {"motion_blur": False, "motion_trails": True, "samples": 0, "request_direction": "up",
                             "reshatter": False, "collisions": False},
    "glass_shatter_both": {"motion_blur": True, "motion_trails": True, "samples": 0, "request_direction": "diag_bl_tr",
                           "refraction": 1.0, "dispersion": 1.0},
    "glass_shatter_plain": {"motion_blur": False, "motion_trails": False, "samples": 0, "request_direction": "left",
                            "sheen": 0.0, "transparency": 0.8},
    "glass_shatter_both_4x": {"motion_blur": True, "motion_trails": True, "samples": 4},
    "pixel_accretion": {},
    "pixel_accretion_motion": {"motion_blur": True, "motion_trails": False, "samples": 0, "request_direction": "up",
                               "tile_size": 4, "travel": 1.0},
    "pixel_accretion_trails": {"motion_blur": False, "motion_trails": True, "samples": 0,
                               "request_direction": "diag_tr_bl", "tile_size": 32, "travel": 0.1},
    "pixel_accretion_both": {"motion_blur": True, "motion_trails": True, "samples": 0, "request_direction": "right"},
    "pixel_accretion_plain": {"motion_blur": False, "motion_trails": False, "samples": 0,
                              "request_direction": "down", "tile_size": 6},
    "pixel_accretion_both_4x": {"motion_blur": True, "motion_trails": True, "samples": 4},
    "block_spins": {},
    "block_spins_motion": {"motion_blur": True, "motion_trails": False, "samples": 0, "request_direction": "up",
                           "edge_glass": "Both"},
    "block_spins_trails": {"motion_blur": False, "motion_trails": True, "samples": 0,
                           "request_direction": "diag_tr_bl", "edge_glass": "Off"},
    "block_spins_both": {"motion_blur": True, "motion_trails": True, "samples": 0, "request_direction": "right",
                         "edge_glass": "Refraction"},
    "block_spins_plain": {"motion_blur": False, "motion_trails": False, "samples": 0, "request_direction": "down",
                          "edge_glass": "Reflection"},
    "block_spins_both_4x": {"motion_blur": True, "motion_trails": True, "samples": 4, "request_direction": "left",
                            "edge_glass": "Both"},
}
#: N5.2d's rule (the lead, 21 Nov; ``Native_Parity_And_Timing_Proof.md`` section 3's N5.2d notes): the piece-edge flip
#: class. A small piece's edge that lies within a rasteriser's sub-pixel snap of a pixel centre covers it in one frame
#: and not the other: the core draws its targets top row first (F1), so its edges snap mirrored from Python's (proved:
#: Python drawn upside down differs from itself by exactly the native frame's flips, and the native frame equals Python
#: drawn in the core's frame), and Vulkan's and OpenGL's rasterisers snap differently (rule b). A whole edge row of a
#: piece flips at once, and the motion blur's gather smears each flip along the piece's motion. Admitted per transition
#: and variant: at most N52D_EDGE_FLIPS_A (rule a) or N52D_EDGE_FLIPS_B (rule b) pixels past one level a frame (1.5 times
#: the measured worst, three_r1, bs_r3 and n52d_r4, both dprs, ceiling), every one on a moving piece edge of the reference
#: or on its gather streak along that piece's motion (the native velocity; ``piece_edges``), no compact group of
#: differing pixels (COMPACT_CORE) past N52C_SCATTER_GROUP, at most N52C_SCATTER_PIXELS one-level pixels. The gather-free
#: forms (motion blur and trails off) are judged against Python drawn in the core's frame (``core_frame``) and take the
#: class with their own counts: N52C admits none of their few driver flips (for the lead, 22 Nov). A shifted piece, a
#: patch, a colour shift or a streak across the motion is a compact group or off every edge, and fails
#: (``tests/test_native_scene_transitions.py``'s planted defects).
N52D_EDGE_FLIPS_A = {
    # The gather-free forms against the core-frame reference (their few flips are the drivers' alone: N52C admits none;
    # for the lead, 22 Nov).
    "block_spins_plain": 0, "crumble_plain": 3, "glass_shatter_plain": 5, "pixel_accretion_plain": 0,
    "block_spins_motion": 17, "block_spins_trails": 0, "block_spins_both": 14,
    "crumble_motion": 32, "crumble_trails": 5, "crumble_both": 33,
    "glass_shatter_motion": 69, "glass_shatter_trails": 6, "glass_shatter_both": 35,
    "pixel_accretion_motion": 8283, "pixel_accretion_trails": 104, "pixel_accretion_both": 533,
}
N52D_EDGE_FLIPS_B = {
    # The gather-free forms (the defaults: 4x, no motion blur or trails; and the plain ones), for the lead (22 Nov).
    "block_spins": 0, "crumble": 24, "glass_shatter": 11, "pixel_accretion": 15,
    "block_spins_plain": 0, "crumble_plain": 3, "glass_shatter_plain": 5, "pixel_accretion_plain": 0,
    "block_spins_motion": 0, "block_spins_trails": 0, "block_spins_both": 0, "block_spins_both_4x": 0,
    "crumble_motion": 191, "crumble_trails": 2, "crumble_both": 114, "crumble_both_4x": 54,
    "glass_shatter_motion": 24, "glass_shatter_trails": 6, "glass_shatter_both": 819, "glass_shatter_both_4x": 177,
    "pixel_accretion_motion": 318, "pixel_accretion_trails": 0, "pixel_accretion_both": 33,
    "pixel_accretion_both_4x": 108,
    "depth_cascade_options": 6,      # N5.2c's, after native_clip_depth (N52C_RULE_B's note): measured 4
}
#: A moving piece: a pixel of the reference more than PIECE_LEVEL from the same run's reference at the progress either
#: side (a card showing the photograph itself moves too), grown by PIECE_GROW pixels so a piece's own edge is inside it.
PIECE_LEVEL = 8
PIECE_GROW = 2
#: A flip lies within EDGE_GROW pixels of the reference's edge (the trails' outline is drawn up to two pixels wide and
#: fades below the edge threshold at its rim, so a ghost's flipped row moves it by up to four: n52d_r4 and r5, Crumble
#: and Glass Shatter with trails); a compact group holds a full COMPACT_CORE square, wider than the smallest piece's
#: streak (Pixel Accretion's 4 px tiles, whose flipped rows the gather smears into bands up to 4 x sqrt(2) wide on a
#: diagonal: n52d_r4 Pixel Accretion both 4x at 0.80). A frame may also hold TIE_PIXELS ties (two levels) off every
#: moving edge, as N52C_RULE_B's: a trail's fade over a flat picture, a landed tile's edge (n52d_r5: Glass Shatter and
#: Pixel Accretion with trails, at most 7 a frame).
EDGE_GROW = 4
COMPACT_CORE = 7
#: A piece's edge: a 3 x 3 span of EDGE_LEVEL or more in the reference (a trail outline's faint rim spans 7: n52d_r4,
#: Crumble both at 0.65), on a moving piece.
EDGE_LEVEL = 4
#: N5.2e (N4.l): the bendable grid's scenes (Membrane, Page Curl) and Exploding Tiles' slabs, planar shadows, sparks and
#: bloom. Each at its production defaults (the tier's 4 samples; Exploding Tiles with the tier's bloom), and
#: single-sampled with options at the other extremes (rule a's forms); Exploding Tiles single-sampled with bloom, motion
#: blur, trails, both and neither, and with all three at 4 samples (rule b).
N52E_TRANSITIONS = ("membrane", "page_curl", "exploding_tiles")
N52E_VARIANTS = {
    "membrane": {},
    "membrane_options": {"request_direction": "up", "gloss": 1.0, "seed": 8, "samples": 0},
    "membrane_matte": {"request_direction": "left", "gloss": 0.0, "seed": 3, "samples": 0, "detail": "Performance"},
    "page_curl": {},
    "page_curl_options": {"request_direction": "top_left", "gloss": 1.0, "size": 1.0, "samples": 0},
    "page_curl_edge": {"request_direction": "right", "gloss": 0.0, "size": 0.0, "samples": 0,
                       "detail": "Performance"},
    "exploding_tiles": {},
    "exploding_tiles_plain": {"samples": 0, "bloom": 0.0, "motion_blur": False, "motion_trails": False},
    "exploding_tiles_bloom": {"samples": 0, "bloom": 1.0, "motion_blur": False, "motion_trails": False,
                              "request_direction": "center_out"},
    "exploding_tiles_motion": {"samples": 0, "bloom": 0.0, "motion_blur": True, "motion_trails": False,
                               "request_direction": "left"},
    "exploding_tiles_trails": {"samples": 0, "bloom": 0.0, "motion_blur": False, "motion_trails": True,
                               "detail": "Performance", "columns": 24},
    "exploding_tiles_both": {"samples": 0, "bloom": 0.6, "motion_blur": True, "motion_trails": True, "columns": 8,
                             "force": 2.0},
    "exploding_tiles_both_4x": {"samples": 4, "bloom": 0.6, "motion_blur": True, "motion_trails": True},
}
#: N5.2f (N4.c): the compacted populations (Disintegrate's grains, Volumetric Dissolve's particles and its two photo
#: environments). Each at its production defaults, and single-sampled at the options' extremes (rule a's forms): the
#: finest grain or particle (2 px: the grid grows to its cap at 4K), the strongest and weakest wind, a diagonal, the
#: sweep from the centre, mist and depth at 0 and 1.
N52F_TRANSITIONS = ("disintegrate", "volumetric_dissolve")
N52F_VARIANTS = {
    "disintegrate": {},
    "disintegrate_fine": {"grain_size": 2, "wind": 2.0, "request_direction": "diag_tl_br", "samples": 0},
    "disintegrate_calm": {"grain_size": 8, "wind": 0.5, "request_direction": "left", "seed": 9, "samples": 0},
    "volumetric_dissolve": {},
    "volumetric_dissolve_center": {"request_direction": "center_out", "mist": 1.0, "depth": 1.0, "particle_size": 2,
                                   "samples": 0},
    "volumetric_dissolve_flat": {"request_direction": "up", "mist": 0.0, "depth": 0.0, "particle_size": 8, "seed": 5,
                                 "samples": 0},
}
#: N5.2g (N4.g, ABI 43): the two fragments that read per-run fields the core makes from recipes (Edge Bloom's two edge
#: fields, Capillary Bloom's arrival field and extent). Each at its production defaults, and at the options' extremes:
#: Edge Bloom's detail 0 and 1, glow 0 and 1, every colour source; Capillary Bloom's fewest and most sources, fibres 0
#: and 1, other seeds. Judged as fragment passes (their effect is one fragment between the pictures).
N52G_TRANSITIONS = ("edge_bloom", "capillary_bloom")
N52G_VARIANTS = {
    "edge_bloom": {},
    "edge_bloom_fine": {"detail": 1.0, "glow": 1.0, "color_source": "each", "seed": 7},
    "edge_bloom_bold": {"detail": 0.0, "glow": 0.0, "color_source": "custom", "color": (0.2, 0.8, 1.0), "seed": 3},
    "edge_bloom_next": {"detail": 0.5, "glow": 1.0, "color_source": "next", "seed": 11},
    "capillary_bloom": {},
    "capillary_bloom_one": {"sources": 1, "fibres": 0.0, "seed": 3},
    "capillary_bloom_six": {"sources": 6, "fibres": 1.0, "seed": 11},
}
#: N5.2g's bounds, PROPOSED (agent, 22 Nov; the lead decides): the statistical bound (``tools/pixel_tolerance.py``,
#: "Statistics", the lead's form for Waveform Ribbon) at 1.5 times the measured worst frame (n52g_stats, both dprs).
#: - Capillary Bloom, rule (a) and (b): the wet front's distance is ``g / |grad g|`` over screen derivatives, and its
#:   rim and meniscus are steep in it (``exp(-(d / 0.006)^2)``, a refraction offset along the gradient), so the two
#:   compilers' rounding of ``g`` moves the rim by a fraction of a pixel all along the front: hundreds of one-level
#:   pixels and touching ties a frame along it (r1: up to 524 and 34 a frame, one pixel 17 levels at the rim's crest),
#:   where its single fragment otherwise matches. The fields are not the cause (field_check: the arrival field equal
#:   across forms, 3e-7 across APIs); nor the derivatives' precision (dFdxFine/dFdyFine bake byte-identical frames:
#:   n52g_fine); the gradient's dFdy sign is measured (+1; -1 puts up to 140 levels on the front: n52g_sign_neg).
#: - Edge Bloom, rule (b) only (rule a holds the fragment pass's bound, worst 1 level): Vulkan's and OpenGL's compute
#:   round the edge field's luma and blur (r16f) apart by a hair, and at fine detail a contour's hysteresis then keeps or
#:   drops a few texels on one API (field_check: 3 texels of the edge field differ, 0.057), so a short line segment
#:   lights on one side only (r1, detail 1: 23 touching pixels past 2 levels, 11 levels at most).
#: Measured worst frames (n52g_stats, 460,800 pixels a frame, one pixel a share of 2.2e-6), each figure times 1.5:
#: Capillary over rules (a) and (b) together, mean |d| 3.37e-4 and its tie share 4.12e-5 (six sources at 0.35, rule a),
#: mean signed 4.5e-5 (six sources at 0.20), past 3 levels one pixel (the defaults at 0.35, the rim's crest); Edge
#: Bloom fine (rule b, dpr 1) mean |d| 1.89e-4, signed 1.06e-4, ties 3.04e-5, past 3 levels 1.63e-5 (7 pixels). The
#: wrong dFdy sign (n52g_sign_neg, 38,012 pixels off a frame, up to 140 levels) is the negative control.
N52G_STATISTICS = {
    "capillary_bloom": pt.FrameStatistics(mean_abs=5.1e-4, mean_signed=6.8e-5, tie_share=6.2e-5, flip_share=3.3e-6),
    "edge_bloom": pt.FrameStatistics(mean_abs=2.9e-4, mean_signed=1.6e-4, tie_share=4.6e-5, flip_share=2.5e-5),
}
CAPILLARY_RULE_A = pt.Tolerance("Capillary Bloom, a fragment pass, against its Python renderer (rule a; the wet front)",
                                statistics=N52G_STATISTICS["capillary_bloom"])
N52G_RULE_B = {
    "capillary_bloom": pt.Tolerance("Capillary Bloom, Vulkan against OpenGL (rule b; the wet front)",
                                    statistics=N52G_STATISTICS["capillary_bloom"]),
    "edge_bloom": pt.Tolerance("Edge Bloom, Vulkan against OpenGL (rule b; a contour's hysteresis)",
                               statistics=N52G_STATISTICS["edge_bloom"]),
}
SCENE_TRANSITIONS = N52C_TRANSITIONS + N52D_TRANSITIONS + N52E_TRANSITIONS + N52F_TRANSITIONS
SCENE_VARIANTS = {**N52C_VARIANTS, **N52D_VARIANTS, **N52E_VARIANTS, **N52F_VARIANTS}
#: N5.2e: the piece-edge flip class (N5.2d's rule, for the lead) for Exploding Tiles' tiles (moving pieces; the gather
#: and the bloom smear their edge flips) and Page Curl's moving page edge, per variant: 1.5 times the measured worst
#: pixels past one level a frame (n52e_r2, both dprs, ceiling); every other guard of the class unchanged. Page Curl's
#: single-sampled forms hold none against Python drawn in the core's frame (their two flips a frame against Python's own
#: frame, r1, are F1's alone), so their bound is 0.
N52E_EDGE_FLIPS_A = {
    "page_curl_options": 0, "page_curl_edge": 0,
    "exploding_tiles_plain": 2, "exploding_tiles_bloom": 3, "exploding_tiles_motion": 36, "exploding_tiles_trails": 5,
    "exploding_tiles_both": 44,
}
N52E_EDGE_FLIPS_B = {
    "page_curl_options": 9,
    "exploding_tiles": 110, "exploding_tiles_plain": 12, "exploding_tiles_bloom": 6, "exploding_tiles_motion": 41,
    "exploding_tiles_trails": 9, "exploding_tiles_both": 20, "exploding_tiles_both_4x": 126,
}
#: N5.2f, PROPOSED for the lead (22 Nov, n52f_r3 on the ABI 41 build, both dprs): the grains and particles are many
#: small moving quads, so the piece-edge class (N5.2d's rule) judges them. Their single-sampled forms draw no gather and
#: are judged against Python drawn in the core's frame: against Python's own frame they put up to 886 pixels a frame
#: past two levels (Disintegrate at grain 2, r2), F1's mirrored snap of every quad edge; in the core's frame at most 8
#: (Volumetric from the centre), all on moving quad edges, none compact. Bounds 1.5 times the measured worst, ceiling.
N52F_EDGE_FLIPS_A = {"disintegrate_fine": 3, "disintegrate_calm": 0, "volumetric_dissolve_center": 12,
                     "volumetric_dissolve_flat": 8}
N52F_EDGE_FLIPS_B = {"disintegrate": 53, "disintegrate_fine": 21, "disintegrate_calm": 0, "volumetric_dissolve": 47,
                     "volumetric_dissolve_center": 72, "volumetric_dissolve_flat": 32}
#: N5.2f, PROPOSED for the lead: Volumetric Dissolve's backdrop resolves the new picture from its environment copy
#: (``textureLod`` 1 to 5) and tints the mist from the old one's (3.5): the two drivers' trilinear filtering of the mips
#: differs by one level over smooth patches (n52f_r3: up to 2,870 pixels a frame at one level, the 4x default, in
#: compact bands up to 486 pixels where the haze resolves; nothing there past four levels). Its rule (b) takes that
#: scatter (times 1.5) and judges compact groups past one level only (a shifted particle or patch is still compact past
#: one level, and every pixel past one level must still lie on a moving particle's edge).
N52F_SAMPLER_RULE_B = {"volumetric_dissolve": 4305, "volumetric_dissolve_center": 4305, "volumetric_dissolve_flat": 4305}
#: Every variant judged by the piece-edge class, and its bounds.
PIECE_EDGE_VARIANTS = {**N52D_VARIANTS, **{v: N52E_VARIANTS[v] for v in set(N52E_EDGE_FLIPS_A) | set(N52E_EDGE_FLIPS_B)},
                       **N52F_VARIANTS}
EDGE_FLIPS_A = {**N52D_EDGE_FLIPS_A, **N52E_EDGE_FLIPS_A, **N52F_EDGE_FLIPS_A}
EDGE_FLIPS_B = {**N52D_EDGE_FLIPS_B, **N52E_EDGE_FLIPS_B, **N52F_EDGE_FLIPS_B}
#: N5.2e: Membrane's 4x default, rule (b), for the lead: its translucent sheet blended over 4 samples and averaged puts
#: many pixels one level apart between the two drivers (n52e_r2: at most 9,696 a frame, both dprs; Python's own 4x
#: Membrane differs from run to run by a level, tens of pixels), times 1.5, and N52C_RULE_B's ties and 3 edge flips
#: (measured 2 a frame past one level).
MEMBRANE_RULE_B = pt.Tolerance("Membrane 4x, Vulkan against OpenGL (rule b)", scatter_pixels=14_544,
                               tie_pixels=TIE_PIXELS, flip_pixels=3)
TRANSITIONS = fsc.FULLSCREEN_TRANSITIONS + N52B_TRANSITIONS + ("beam",) + SCENE_TRANSITIONS + N52G_TRANSITIONS
VARIANTS = {**fsc.VARIANTS, **N52B_VARIANTS, **BEAM_VARIANTS, **SCENE_VARIANTS, **N52G_VARIANTS}
#: The variants a sheet shows (each transition's defaults and one with options).
SHEET_VARIANTS = ("burn", "particle_swirl", "ripple", "slide_push", "warp_dissolve", "wipe", "crossfade",
                  *N52B_TRANSITIONS, "chromatic_shear_options", "liquid_lens_flood", "melt_drip_center_in",
                  "surface_tension_options", "vhs_options", *BEAM_VARIANTS, *N52C_VARIANTS, *N52D_VARIANTS, *N52E_VARIANTS,
                  *N52F_VARIANTS)


def variant_progress(variant: str) -> tuple[float, ...]:
    """The progress values ``variant`` is drawn at: PROGRESS, Blinds' slats with 0.5 replaced by SLAT_PROGRESS."""
    if variant.split("@", 1)[0] not in SLAT_VARIANTS:
        return tuple(PROGRESS)
    half = PROGRESS.index(0.5)
    return tuple(PROGRESS[:half]) + SLAT_PROGRESS + tuple(PROGRESS[half + 1:])


def progress_key(progress: float) -> str:
    """A frame's progress in its key: two places (the stored keys), four where two would merge two values."""
    return f"{progress:.2f}" if round(progress, 2) == progress else f"{progress:.4f}"


def variant_transition(variant: str) -> str:
    """The transition a variant of ``VARIANTS`` draws (the longest id that names it)."""
    for transition_id in sorted(TRANSITIONS, key=len, reverse=True):
        if variant == transition_id or variant.startswith(transition_id + "_"):
            return transition_id
    raise ValueError(f"no transition draws the variant {variant!r}")


def product_capture(width: int, height: int, old, new, dpr: float, *, core_frame: bool = False):
    """The production GL host (``TransitionCapture``) drawing the product's frame at ``dpr``: the item's logical size
    is the target's device pixels over ``dpr`` (its ``uItemSize``), its own pixels the target's (``item_pixels``), as
    the runtime's render frame gives them on a window of that ratio. N5.2d: ``core_frame`` draws it upside down (the
    frame matrix's y negated: the core's top-row-first frame, F1), so the frame read back is flipped by the caller
    (``references``); only for a scene drawn straight into the frame (no SceneTarget: its gather reads GL's rows)."""
    from tools.transition_contact_sheet import TransitionCapture

    class _ProductFrameCapture(TransitionCapture):
        def frame(self, run, progress: float):
            from rendering.quick.transitions.render_contract import QuickTransitionRenderFrame

            w, h = self.width, self.height
            lw, lh = w / dpr, h / dpr
            sample = run.sample(run.start_ns + round(progress * (run.end_ns - run.start_ns)))
            matrix = ((2 / lw, 0, 0, 0, 0, 2 / lh, 0, 0, 0, 0, 1, 0, -1, -1, 0, 1) if core_frame
                      else (2 / lw, 0, 0, 0, 0, -2 / lh, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1))
            return QuickTransitionRenderFrame(run, sample, (0, 0, w, h), (lw, lh), matrix,
                                              self.vao, self.textures[0], self.textures[1], device_pixel_ratio=dpr)

    return _ProductFrameCapture(width, height, old, new)


class Clock:
    """The run's clock held at one progress (a harness's control; the product's is ``time.monotonic_ns``)."""

    def __init__(self) -> None:
        self.now = 0

    def at(self, run, progress: float) -> None:
        # TransitionCapture.frame's own sampling of the run at a progress.
        self.now = run.start_ns + round(progress * (run.end_ns - run.start_ns))

    def __call__(self) -> int:
        return self.now


def production_run(variant: str, images, run_id: int):
    """The production run of ``variant`` from the old photo to the new one (``fullscreen_pass_check``'s overrides)."""
    from rendering.quick.transitions.state import TransitionRun
    from tools.transition_contact_sheet import production_transition_spec

    transition_id = variant_transition(variant)
    spec = production_transition_spec(transition_id, DURATION_MS)
    request = spec.build_request(runtime_generation=0, source_image=images[0], destination_image=images[1])
    overrides = VARIANTS[variant]
    if overrides:
        request = fsc.overridden(request, overrides)
    return TransitionRun.start(run_id=run_id, request=request, start_ns=1_000_000_000)


def references(variants, photos, dpr: float, *, core_frame: bool = False) -> dict:
    """The Python renderer's frames (the production GL host) of each variant's run at each progress, at the display's
    pixels, in the product's frame at ``dpr`` (``product_capture``); ``core_frame``: drawn in the core's frame and read
    back the right way up (N5.2d's gather-free forms)."""
    import numpy as np
    from PIL import Image

    pictures = [Image.fromarray(rows, "RGBA") for _image, rows in photos]
    width, height = blc.DISPLAY
    capture = product_capture(width, height, *pictures, dpr, core_frame=core_frame)
    out = {}
    try:
        for index, variant in enumerate(variants):
            run = production_run(variant, [image for image, _rows in photos], index + 1)
            for progress in variant_progress(variant):
                image, _ms = capture.render(run, progress)
                rows = np.asarray(image, dtype=np.uint8)
                out[(variant, progress)] = (rows[::-1] if core_frame else rows).copy()
    finally:
        capture.close()
    return out


def n52d_gather_free(variant: str) -> bool:
    """A piece-edge variant drawn with neither motion blur nor trails (N5.2d's production defaults leave both off) and
    (N5.2e) no bloom: drawn straight into the frame, so Python's frame drawn upside down is its reference."""
    overrides = PIECE_EDGE_VARIANTS.get(variant.split("@", 1)[0])
    return (overrides is not None and not overrides.get("motion_blur") and not overrides.get("motion_trails")
            and not overrides.get("bloom"))


def _grow(flags, steps: int):
    import numpy as np

    out = np.asarray(flags, bool).copy()
    for _ in range(int(steps)):
        padded = np.pad(out, 1)
        out = out | padded[:-2, 1:-1] | padded[2:, 1:-1] | padded[1:-1, :-2] | padded[1:-1, 2:]
        out = out | padded[:-2, :-2] | padded[:-2, 2:] | padded[2:, :-2] | padded[2:, 2:]
    return out


def piece_edges(native, reference, neighbours, velocity=None, longest: float = 0.0):
    """Where N5.2d's piece-edge flips may lie: a content edge of the reference on one of its moving pieces (where it
    differs from a ``neighbours`` frame, the same run's reference at the progress either side, by PIECE_LEVEL, grown
    PIECE_GROW), grown a pixel, and, with ``velocity`` ((2, h, w) pixels a frame in the display's frame, the native
    scene's), each such edge pixel's gather streak: the pixels along its 3 x 3 neighbourhood's longest motion either way,
    at most ``longest`` (2K, the gather's bound) long, grown a pixel. ``native`` is not read (a defect drawn in it makes
    edges of its own)."""
    import numpy as np

    from tools import pixel_tolerance as pt

    def off(frame, picture):
        return np.abs(frame[..., :3].astype(np.int16) - picture[..., :3].astype(np.int16)).max(axis=2) > PIECE_LEVEL

    pieces = np.zeros(reference.shape[:2], bool)
    for neighbour in neighbours:
        pieces |= off(reference, neighbour)
    edges = pt.content_edges(reference[..., :3], EDGE_LEVEL) & _grow(pieces, PIECE_GROW)
    allowed = _grow(edges, EDGE_GROW)
    if velocity is None:
        return allowed
    vx, vy = (np.asarray(v, np.float32) for v in velocity)
    h, w = vx.shape
    magnitude = np.hypot(vx, vy)
    pick = np.zeros((h, w), np.int64)
    best = np.full((h, w), -1.0, np.float32)
    flat = np.arange(h * w).reshape(h, w)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            shifted = np.roll(np.roll(magnitude, dy, axis=0), dx, axis=1)
            index = np.roll(np.roll(flat, dy, axis=0), dx, axis=1)
            better = shifted > best
            best = np.where(better, shifted, best)
            pick = np.where(better, index, pick)
    ys, xs = np.nonzero(edges)
    chosen = pick[ys, xs]
    mx, my = vx.reshape(-1)[chosen], vy.reshape(-1)[chosen]
    length = np.hypot(mx, my)
    scale = np.where((length > longest) & (longest > 0), longest / np.maximum(length, 1e-6), 1.0)
    mx, my = mx * scale, my * scale
    streak = np.zeros((h, w), bool)
    steps = int(np.ceil(float(np.hypot(mx, my).max(initial=0.0)))) + 1
    for t in np.linspace(-1.0, 1.0, 2 * steps + 1):
        sy = np.clip(np.rint(ys + t * my).astype(np.int64), 0, h - 1)
        sx = np.clip(np.rint(xs + t * mx).astype(np.int64), 0, w - 1)
        streak[sy, sx] = True
    return allowed | _grow(streak, 1)


def compact_groups(flags, limit: int) -> list[int]:
    """The sizes of the 8-connected groups of ``flags`` holding a full COMPACT_CORE square (a patch, not a line or a
    streak) larger than ``limit``."""
    import numpy as np

    flags = np.asarray(flags, bool)
    half = COMPACT_CORE // 2
    padded = np.pad(flags, half)
    core = np.ones(flags.shape, bool)
    for dy in range(COMPACT_CORE):
        for dx in range(COMPACT_CORE):
            core &= padded[dy:dy + flags.shape[0], dx:dx + flags.shape[1]]
    seen = np.zeros(flags.shape, bool)
    sizes = []
    h, w = flags.shape
    for y, x in zip(*np.nonzero(core)):
        if seen[y, x]:
            continue
        stack, size = [(y, x)], 0
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            size += 1
            for ny in (cy - 1, cy, cy + 1):
                for nx in (cx - 1, cx, cx + 1):
                    if 0 <= ny < h and 0 <= nx < w and flags[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        if size > limit:
            sizes.append(size)
    return sizes


def judge_piece_edges(candidate, reference, flips: int, allowed, *, ties: int = 0,
                      scatter_pixels: int = N52C_SCATTER_PIXELS, compact_past: int = 0) -> dict:
    """N5.2d's piece-edge flip class for one frame: at most ``scatter_pixels`` (N52C_SCATTER_PIXELS) one-level pixels
    (their spread is the gather's: the compact check judges it); at most ``flips`` pixels past one level, every one in
    ``allowed`` (``piece_edges``); no compact group of pixels past ``compact_past`` levels (0: every differing pixel)
    larger than N52C_SCATTER_GROUP. N5.2f: Volumetric Dissolve's rule (b) takes its own scatter and judges compact
    groups past one level (``N52F_SAMPLER_RULE_B``)."""
    import numpy as np

    delta = np.abs(candidate[..., :3].astype(np.int16) - reference[..., :3].astype(np.int16)).max(axis=2)
    past = delta > 1
    reasons = []
    scatter = int((delta == 1).sum())
    if scatter > scatter_pixels:
        reasons.append(f"{scatter} pixels one level off (scatter: at most {scatter_pixels})")
    count = int(past.sum())
    off = past & ~np.asarray(allowed, bool)
    tie_off = int((off & (delta <= TIE_LEVEL)).sum())
    stray = int(off.sum()) - (tie_off if tie_off <= ties else 0)
    compact = compact_groups(delta > compact_past, N52C_SCATTER_GROUP)
    if count > flips:
        reasons.append(f"{count} pixels past one level (piece-edge flips admitted: {flips})")
    if stray:
        reasons.append(f"{stray} pixels past one level off every moving piece edge and gather streak")
    if compact:
        reasons.append(f"compact groups past one level of {compact} pixels (at most {N52C_SCATTER_GROUP})")
    return {"pass": not reasons, "reasons": reasons, "past_one_level": count, "off_edges": stray, "flips": count,
            "compact_groups": compact, "max_level": int(delta.max(initial=0)), "judged": True,
            "rule": "N5.2d piece-edge flips"}


def _mode_counts(scene) -> dict:
    state = scene.mode_state()
    surface = (scene.composite_state().get("surface") or {})
    return {"records": state.get("records"), "passes": surface.get("passes_recorded"),
            "uploads": state.get("texture_uploads"), "ticks": scene.layer.ticks if scene.layer else None}


def round_draw(core, engine, app, api: str, variants, work: Path, out: Path) -> dict:
    import numpy as np

    vulkan = api == "vulkan"
    checks: dict = {}
    facts: dict = {"variants": {}}
    frames: dict = {}
    velocities: dict = {}
    references_kept: dict = {}             # N5.2d: Python's frames, kept for an offline judgement of rule (a)
    tiles = []
    for dpr in DPRS:
        photos = [blc.processed(path, "fill", blc.DISPLAY) for path in PHOTOS]
        expected = {} if vulkan else references(variants, photos, dpr)
        # N5.2d: the gather-free single-sampled forms are judged against Python drawn in the core's frame.
        core_framed = [] if vulkan else [v for v in variants if n52d_gather_free(v) and VARIANTS[v].get("samples") == 0]
        expected_core = references(core_framed, photos, dpr, core_frame=True) if core_framed else {}
        host = blc._host(core, blc.WINDOW, dpr)
        scene = blc.Scene(core, engine, host, dpr, blc.DISPLAY, kind="layer")
        clock = Clock()
        scene.layer._clock_ns = clock
        try:
            for index, variant in enumerate(variants):
                run = production_run(variant, [image for image, _rows in photos], index + 1)
                scene.present(photos[0][0])
                scene.settle()
                entry: dict = {}
                # N5.2c: a scene's samples (rule a's form) and its photo environment's copies over the run.
                entry["scene"] = variant_transition(variant) in SCENE_TRANSITIONS
                entry["samples"] = int(run.request.parameter_dict().get("samples", 0) or 0)
                copies_before = _environment_copies(core)
                clock.at(run, PROGRESS[0])
                started = time.perf_counter()
                scene.layer.transition(run)
                entry["gui_start_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
                # The run's first frame, before its destination's upload job is waited for (black flicker, 21 Nov:
                # on Vulkan it was black while the job ran): the source's lit pixels are never black.
                scene.frames(1)
                first = scene.display_rows(scene.read())
                entry["first_frame_black"] = black_over_lit(first, photos[0][1])
                entry["first_frame_not_black"] = entry["first_frame_black"] <= FIRST_FRAME_BLACK
                entry["first_frame_waiting_kept"] = scene.mode_state().get("waiting_kept")
                scene.settle()                                   # the destination's upload job committed
                entry["fields_in"] = _await_fields(scene)        # N5.2g: a run's fields committed
                ticks_before = scene.layer.ticks
                scene.frames(2)
                entry["clock_edge_ticks_over_2_frames"] = scene.layer.ticks - ticks_before
                progresses = variant_progress(variant)
                entry["progress"] = list(progresses)
                for progress in progresses:
                    clock.at(run, progress)
                    scene.layer.tick()
                    scene.frames(1)
                    rows = scene.display_rows(scene.read())
                    key = f"dpr{dpr}_{variant}_{progress_key(progress)}"
                    frames[key] = rows
                    if not vulkan and VARIANTS[variant].get("motion_blur") and variant in PIECE_EDGE_VARIANTS:
                        velocities[key] = _native_velocity(scene)
                    if not vulkan:
                        reference = expected[(variant, progress)]
                        if variant in PIECE_EDGE_VARIANTS:
                            references_kept[key] = reference
                            if (variant, progress) in expected_core:
                                references_kept[f"core_{key}"] = expected_core[(variant, progress)]
                        rule = _rule_a(variant, entry)
                        judged = entry[progress_key(progress)] = blc.compare(rows, reference)
                        judged["over_tolerance"] = _over(rows, reference, VULKAN_TOLERANCE)
                        # N5.2c: a multisampled scene is judged by rule (b) only (rule a: its single-sampled form).
                        judged["tolerance"] = (pt.judge(rows[..., :3], reference[..., :3], rule) if rule is not None
                                               else {"pass": True, "judged": False, "reason": MULTISAMPLED_RULE_A})
                        if rule is not None and variant in EDGE_FLIPS_A:
                            # A gather-free form against Python drawn in the core's frame (F1's flips are not its).
                            framed = {q: expected_core.get((variant, q), expected[(variant, q)]) for q in progresses}
                            against = framed[progress]
                            at = progresses.index(progress)
                            neighbours = [framed[q] for q in progresses[max(0, at - 1):at + 2] if q != progress]
                            allowed = piece_edges(rows, against, neighbours, velocities.get(key), N52D_LONGEST)
                            if (variant, progress) in expected_core:
                                judged["against_python_frame"] = judged["tolerance"]
                                judged["core_frame_over_tolerance"] = _over(rows, against, VULKAN_TOLERANCE)
                            judged["tolerance"] = judge_piece_edges(rows, against, EDGE_FLIPS_A[variant],
                                                                    allowed, ties=TIE_PIXELS)
                if not vulkan:
                    # Another progress's reference differs (the pair two thirds into the run's values).
                    here, there = progresses[-5], progresses[-4]
                    entry["control_next_progress_differs"] = not blc.compare(
                        frames[f"dpr{dpr}_{variant}_{progress_key(here)}"], expected[(variant, there)])["equal"]
                # N5.2c: N4.j's copy drawn once over the run (a scene reading it), never for any other run.
                reads = _reads_environment(run) if entry["scene"] else 0
                entry["environment_copies"] = _environment_copies(core) - copies_before
                entry["environment_once_per_photo"] = entry["environment_copies"] == reads
                # The run's end: the item ends the run, then hands over the destination (the runtime's order).
                uploads = _mode_counts(scene)["uploads"]
                scene.layer.transition(None)
                scene.present(photos[1][0])
                scene.settle()
                end = scene.display_rows(scene.read())
                entry["end_is_the_destination"] = blc.compare(end, photos[1][1])["equal"]
                entry["end_uploads_nothing"] = _mode_counts(scene)["uploads"] == uploads
                entry["clock_disconnected"] = not scene.layer.state().get("clock_connected")
                before = _mode_counts(scene)
                scene.frames(REST_FRAMES)
                after = _mode_counts(scene)
                entry["nothing_at_rest"] = before == after
                entry["rest"] = [before, after]
                facts["variants"][f"{variant}@{dpr}"] = entry
                if dpr == 1.0 and variant in SHEET_VARIANTS:
                    tiles.append([blc._tile(frames[f"dpr{dpr}_{variant}_{progress_key(p)}"])
                                  for p in variant_progress(variant)[2:-2:2]][:3])
            facts[f"layer_dpr_{dpr}"] = scene.layer.state()
        finally:
            scene.close(app)
            facts.setdefault("host_close", []).append(blc._close_host(app, host))
    keys = list(facts["variants"])
    if not vulkan:
        # Exact for the seven; the shared tolerance for a NativeFragmentPass (FRAGMENT_PASS_RULE_A).
        judged = [(k, p, facts["variants"][k][progress_key(p)]) for k in keys
                  for p in facts["variants"][k]["progress"]]
        checks["rule_a_equal_to_the_python_renderer"] = all(
            e["tolerance"]["pass"] and (_rule_a(k, facts["variants"][k]) is not pt.EXACT or e["equal"])
            for k, _p, e in judged)
        facts["rule_a_tolerance"] = {
            "bounds": [FRAGMENT_PASS_RULE_A.bound(), pt.EXACT.bound(), N52C_RULE_A.bound(), JIGSAW_RULE_A.bound(),
                       BLINDS_FLAT_RULE_A.bound(), CAPILLARY_RULE_A.bound()],
            "not_judged": sorted({k for k, _p, e in judged if e["tolerance"].get("judged") is False}),
            **pt.summarise(e["tolerance"] for _k, _p, e in judged if e["tolerance"].get("judged") is not False)}
        checks["control_another_progress_differs"] = all(facts["variants"][k]["control_next_progress_differs"]
                                                         for k in keys)
        worst = max(((k, p, e) for k, p, e in judged if e["tolerance"].get("judged") is not False),
                    key=lambda e: e[2].get("max_level", 0), default=("", 0.0, {}))
        facts["rule_a_worst"] = {"variant": worst[0], "progress": worst[1], **worst[2]}
    for name in ("end_is_the_destination", "end_uploads_nothing", "clock_disconnected", "nothing_at_rest",
                 "environment_once_per_photo", "first_frame_not_black"):
        checks[name] = all(facts["variants"][k][name] for k in keys)
    if vulkan:
        checks.update(_route_on_vulkan(core, engine, app, frames, facts, variants))
    np.savez_compressed(work / f"route_{api}.npz", **frames)
    if references_kept:
        np.savez_compressed(work / "python_opengl.npz", **references_kept)
    if velocities:
        facts["velocity_not_read"] = sorted(k for k, v in velocities.items() if v is None)
        np.savez_compressed(work / f"velocity_{api}.npz",
                            **{k: np.stack(v) for k, v in velocities.items() if v is not None})
    if tiles:                                            # a selection without a sheet variant draws no sheet
        blc._sheet(out / f"transition_route_{api}.png", tiles)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


#: The performance step's cost (``--cost``; Native_Parity_And_Timing_Proof.md section 3, "A transition port": C per pass
#: at 2560 x 1440 and 4K on both backends): the layer's record of the run (the environment's copy and chain once, the
#: scene's passes, the composite) timed by the core's GPU timer over COST_FRAMES frames of the effect, median and p90;
#: OpenGL also times the Python renderer (``TransitionCapture.benchmark``, 12 frames) for context, and (N5.2h) the
#: Python presenter on the product route on the same frames by the same instrument (``python_product_frame_gpu``
#: against ``qrhi_frame_gpu``: the comparable pair; the benchmark is the draw alone in a bare FBO on a hot cache, which
#: read 0.04 ms at 4K against the product's 0.057). Crossfade also runs the clear route's negative control
#: (``_clear_control``). Both scenes are the product's display scene (a plain root). Frames run back to
#: back (no readback between them, which let the GPU idle and downclock: the first run's 4K figures were below its
#: 1440p ones); Crossfade, timed in the same run, is the control the others are read against.
COST_SIZES = ((2560, 1440), (3840, 2160))
COST_FRAMES = 240
#: The clear route control's alternating blocks (``_clear_control``): ten blocks of 24 frames a route, 240 frames each.
CLEAR_CONTROL_BLOCKS = 10
CLEAR_CONTROL_BLOCK_FRAMES = 24


class _ClockTime:
    """``time`` for the Python presenter's node (``background_node.run.sample(time.monotonic_ns())``) on the round's own
    clock, so the product route's Python frames sample the run at the native layer's progress (a harness patch)."""

    def __init__(self, clock: Clock) -> None:
        self.monotonic_ns = clock


def _product_python(core, engine, size, photos):
    """N5.2h: the Python presenter on the product route (``BackgroundRenderItem``'s render node drawing into the window)
    in a hidden host of the native layer's size, timed by the same instrument as the native layer (QRhi's whole-frame
    GPU time, the timer's kind 0) on the same frames (interleaved one by one), under the product's display scene (a
    plain root, nothing drawn under the background: DisplayScene.qml). ``python_opengl`` stays the bare-FBO benchmark
    (``TransitionCapture.benchmark``: the draw alone on a hot cache), which no product frame is."""
    host = blc._host(core, (size[0] + 4, size[1] + 6), 1.0, timestamps=True)
    scene = blc.Scene(core, engine, host, 1.0, size, kind="python")
    scene.root.setProperty("color", "transparent")
    scene.present(photos[0][0])
    scene.frames(6)
    return host, scene


#: N5.2h's clear-route controls: the ``stage_control`` name and the ``composite_live`` count prefix of the mode surface's
#: first-run clear (Crossfade's control) and of a scene target's (SCENE_CLEAR_CONTROL_VARIANTS', box 3).
CLEAR_ROUTES = {"surface": ("surface_clear_draw", "mode_surface"), "scene": ("scene_clear_draw", "mode_scene")}
#: The scene variants that run the scene clear control in the cost round: a single-sampled scene and the 4x scene with
#: motion blur and trails (three attachments, four samples: the draw's largest share).
SCENE_CLEAR_CONTROL_VARIANTS = ("crumble_plain", "crumble_both_4x")


def _clear_control(core, api: str, scene, host, clock, run, route: str = "surface") -> tuple[dict, dict]:
    """N5.2h's negative control on Crossfade: the surface cleared at its first run by the pass's own clear (OpenGL;
    Vulkan keeps the clearing draw, rule B) against the full-triangle clearing draw again (``stage_control``'s
    ``surface_clear_draw``): the same pixels (the display read at one progress), the clears counted by their route
    (``composite_live``'s ``mode_surface_pass_clears`` and ``mode_surface_draw_clears``), and the record and frame GPU
    time with the draw back (its share returns). ``route`` "scene": the same for a scene target's first run
    (``scene_clear_draw``, ``mode_scene_*``). A module without the control: ``available`` False, nothing judged."""
    control_name, prefix = CLEAR_ROUTES[route]
    if not core.module.stage_control(control_name, False):
        return {"available": False}, {}

    def counts() -> tuple[int, int]:
        live = core.composite_live()
        return int(live.get(f"{prefix}_pass_clears", 0)), int(live.get(f"{prefix}_draw_clears", 0))

    def drawn(progress: float):
        clock.at(run, progress)
        scene.layer.tick()
        scene.frames(3)
        return scene.read()

    before = counts()
    by_pass = drawn(0.5)
    middle = counts()
    core.module.stage_control(control_name, True)
    try:
        by_draw = drawn(0.5)
        neighbour = drawn(0.55)                                  # the comparison's own control: another progress
        after = counts()
        # Both routes timed under the same conditions (N5.2h successor): the round's main loop interleaves the Python
        # host's frames, which this loop does not, so its figures are not comparable with the main loop's; here the
        # pass route and the draw route alternate in blocks over the same progress span (the control is read per
        # record), each block's samples taken after a flush.
        timed: dict = {False: [], True: []}
        host.set_gpu_timer(True)
        host.gpu_samples()
        frame = 0
        for _block in range(CLEAR_CONTROL_BLOCKS):
            for draw_route in (False, True):
                core.module.stage_control(control_name, draw_route)
                for _ in range(CLEAR_CONTROL_BLOCK_FRAMES):
                    clock.at(run, 0.1 + 0.8 * (frame % COST_FRAMES) / (COST_FRAMES - 1))
                    frame += 1
                    scene.layer.tick()
                    scene.frames(1)
                scene.frames(2)
                timed[draw_route].extend(host.gpu_samples())
        host.set_gpu_timer(False)
    finally:
        core.module.stage_control(control_name, False)
    pixels = blc.compare(by_pass, by_draw)
    control = blc.compare(by_draw, neighbour)

    def stats(draw_route: bool, kind: int) -> dict:
        return blc._ms_stats([x.nanoseconds / 1e6 for x in timed[draw_route] if x.kind == kind])

    record = {"available": True, "pixels_pass_against_draw": pixels, "pixels_against_next_progress": control,
              "pass_clears": [middle[0] - before[0], after[0] - middle[0]],
              "draw_clears": [middle[1] - before[1], after[1] - middle[1]],
              # The alternating blocks: the record (kind 2) and the whole frame (kind 0) on each route.
              "core_record_gpu_clear_pass": stats(False, 2), "core_record_gpu_clear_draw": stats(True, 2),
              "qrhi_frame_gpu_clear_pass": stats(False, 0), "qrhi_frame_gpu_clear_draw": stats(True, 0)}
    opengl = api == "opengl"
    pass_ms = record["core_record_gpu_clear_pass"].get("median_ms")
    draw_ms = record["core_record_gpu_clear_draw"].get("median_ms")
    checks = {"clear_route_pixels_equal": pixels["equal"], "clear_route_control_differs": not control["equal"],
              # OpenGL: the draw's share comes back under the control (the record's median above the pass route's);
              # Vulkan draws on both phases, so nothing is judged there but that both were timed.
              "clear_route_share_returns": pass_ms is not None and draw_ms is not None
              and (draw_ms > pass_ms if opengl else True),
              # [default, control]: OpenGL clears every first run by the pass by default (no draw clear: since
              # 121087442 a multisampled RGBA16F clears by the pass too) and every one by the draw under the control;
              # Vulkan by the draw in both.
              "clear_route_counted": (record["pass_clears"][0] > 0) == opengl and record["pass_clears"][1] == 0
              and record["draw_clears"][1] > 0 and (record["draw_clears"][0] == 0) == opengl}
    return record, checks


#: N5.2h's scene-pass gap: the variants timed per unit (``_scene_passes``) and per Python stage (``_python_stages``), in
#: alternating blocks of SCENE_PASS_BLOCK_FRAMES frames over the cost round's progress span (units on, then off).
SCENE_PASS_VARIANTS = ("crumble_both_4x", "glass_shatter_both_4x")
SCENE_PASS_BLOCKS = 6
SCENE_PASS_BLOCK_FRAMES = 24
#: N5.2h successor: a run timed in parts (``time_scene_run_parts``) sums to the run timed whole within this fraction
#: (the brackets inside the pass flush QRhi's command list and rebind its framebuffer, which moves no GPU work; the
#: alternating blocks' own spread at 4K is a few percent).
RUN_PARTS_SUM_TOLERANCE = 0.1  # timing noise below the units' median


def _program_pass_names(scene) -> tuple[list, str]:
    """The mode program's pass names in the core's order (the index a scene-pass figure names), and where they were
    read; ([], "none") when the state names none (the figures are then labelled by index alone)."""
    mode = scene.layer.state().get("mode") or {}
    for source, passes in (("program", (mode.get("program") or {}).get("passes")),
                           ("facts", (mode.get("facts") or {}).get("passes")), ("mode", mode.get("passes"))):
        if passes:
            return [p.get("name") if isinstance(p, dict) else str(p) for p in passes], source
    return [], "none"


def _scene_passes(core, scene, host, clock, run, api: str = "opengl") -> tuple[dict, dict]:
    """N5.2h: the record timed per unit (``stage_control("time_scene_passes")``: each run with its primes, passes and
    the pass's own resolves; its nearest copies; its self mips; each compute, step and the texture chains) against the
    whole record (the Surface figure) in alternating blocks over the same frames. The off blocks are the control: no
    scene-pass figure without the switch, and the Surface figure with it off only. A module without the switch:
    ``available`` False, nothing judged."""
    from rendering.native.gpu_timing import GPU_UNIT_PARTS

    if not core.module.stage_control("time_scene_passes", False):
        return {"available": False}, {}
    # N5.2h successor: a scene run's parts (its opening, each pass, its end-of-pass resolves; OpenGL) as a third block,
    # against the runs timed whole (the units block) on the same frames; a module without the control runs two blocks.
    parts_available = bool(core.module.stage_control("time_scene_run_parts", False))
    names, names_from = _program_pass_names(scene)
    modes = ("units", "parts", "off") if parts_available else ("units", "off")
    timed: dict = {mode: [] for mode in modes}
    host.set_gpu_timer(True)
    host.gpu_samples()
    try:
        for block in range(SCENE_PASS_BLOCKS):
            for mode in modes:
                core.module.stage_control("time_scene_passes", mode != "off")
                if parts_available:
                    core.module.stage_control("time_scene_run_parts", mode == "parts")
                # Every mode of a block draws the same frames (the block's progress span; _python_stages' frames over
                # the blocks): the motion blur's and the pieces' cost varies with the progress, so blocks on different
                # spans compare different work (measured: the gather 0.08 against 0.18 ms at 4K on Vulkan, where both
                # blocks time the same unit).
                for frame in range(block * SCENE_PASS_BLOCK_FRAMES, (block + 1) * SCENE_PASS_BLOCK_FRAMES):
                    clock.at(run, 0.1 + 0.8 * (frame % COST_FRAMES) / (COST_FRAMES - 1))
                    scene.layer.tick()
                    scene.frames(1)
                scene.frames(2)
                timed[mode].extend(host.gpu_samples())
    finally:
        core.module.stage_control("time_scene_passes", False)
        if parts_available:
            core.module.stage_control("time_scene_run_parts", False)
        host.set_gpu_timer(False)

    def by_units(samples) -> tuple[dict, dict, int]:
        on = [s for s in samples if s.kind == 5]
        grouped: dict = {}
        frames: dict = {}
        for s in on:
            name = names[s.pass_index] if 0 <= s.pass_index < len(names) else "-"
            grouped.setdefault(f"{s.pass_index}:{name}:{GPU_UNIT_PARTS.get(s.part, s.part)}", []).append(
                s.nanoseconds / 1e6)
            frames[s.frame] = frames.get(s.frame, 0.0) + s.nanoseconds / 1e6
        ordered = {key: blc._ms_stats(values) for key, values in sorted(
            grouped.items(), key=lambda kv: (int(kv[0].split(":")[0]), kv[0]))}
        return ordered, frames, len(on)

    units, per_frame, units_count = by_units(timed["units"])
    whole = [s.nanoseconds / 1e6 for s in timed["off"] if s.kind == 2]
    record = {"available": True, "pass_names_from": names_from, "pass_names": names, "units": units,
              "units_per_frame": round(units_count / max(1, len(per_frame)), 2),
              "units_sum_per_frame": blc._ms_stats(list(per_frame.values())),
              "core_record_gpu_units_off": blc._ms_stats(whole),
              "qrhi_frame_gpu_units_on": blc._ms_stats([s.nanoseconds / 1e6 for s in timed["units"] if s.kind == 0]),
              "qrhi_frame_gpu_units_off": blc._ms_stats([s.nanoseconds / 1e6 for s in timed["off"] if s.kind == 0])}
    checks = {"scene_passes_timed": len(per_frame) >= SCENE_PASS_BLOCKS * SCENE_PASS_BLOCK_FRAMES // 2,
              # The switch replaces the whole bracket (GL_TIME_ELAPSED cannot nest) and nothing else times units.
              "scene_passes_replace_the_record": not any(s.kind == 2 for s in timed["units"]),
              "scene_passes_control_has_none": not any(s.kind == 5 for s in timed["off"]) and bool(whole)}
    if parts_available:
        part_units, part_frames, _count = by_units(timed["parts"])
        run_parts = {5, 6, 7}
        has_parts = any(s.kind == 5 and s.part in run_parts for s in timed["parts"])
        record["run_parts"] = part_units
        record["run_parts_sum_per_frame"] = blc._ms_stats(list(part_frames.values()))
        record["qrhi_frame_gpu_run_parts"] = blc._ms_stats(
            [s.nanoseconds / 1e6 for s in timed["parts"] if s.kind == 0])
        # The parts are OpenGL's only (Vulkan keeps the unit: a bracket inside its pass needs an ExternalContent pass).
        # The control: the units block (runs timed whole) holds no part, and the parts cover the units (no work of a
        # run left outside its parts: their sum per frame is no less than the units' median, less timing noise,
        # RUN_PARTS_SUM_TOLERANCE). Brackets inside a pass serialise it, so the parts add time that grows with the
        # pass (measured +0.04-0.05 ms at 1440p, +0.15-0.17 ms at 4K on crumble_both_4x): reported as
        # run_parts_overhead_ms, never judged, as the parts are attribution and the units carry the cost.
        units_ms = record["units_sum_per_frame"].get("median_ms")
        parts_ms = record["run_parts_sum_per_frame"].get("median_ms")
        checks["run_parts_on_opengl_only"] = has_parts == (api == "opengl")
        checks["run_parts_control_has_none"] = not any(s.kind == 5 and s.part in run_parts for s in timed["units"])
        if has_parts:
            record["run_parts_sum_against_units"] = round(parts_ms / units_ms, 4) if units_ms and parts_ms else None
            record["run_parts_overhead_ms"] = round(parts_ms - units_ms, 4) if units_ms and parts_ms else None
            checks["run_parts_cover_the_units"] = bool(units_ms and parts_ms) and (
                parts_ms >= units_ms * (1.0 - RUN_PARTS_SUM_TOLERANCE))
    return record, checks


def _python_stages(capture, run, frames: int = SCENE_PASS_BLOCKS * SCENE_PASS_BLOCK_FRAMES) -> dict:
    """N5.2h: the Python renderer's same work on the same progress span, each stage between two GL timestamps (they
    nest, unlike GL_TIME_ELAPSED): the underlay, the trails (ghosts into R8 and the edges), the scene target's begin,
    the pieces (chunks or shards), the debris, and the scope's end (its resolve and motion blur stamped inside it, the
    composite the rest); ``frame`` the whole render. A harness patch of the implementation's instance only, restored
    after; the capture's bare FBO (``TransitionCapture``), not the product route."""
    from OpenGL import GL as gl

    with capture._target.current():
        capture.host.render(capture.frame(run, 0.5))              # the implementation and its run resources exist
        impl = capture.host._implementations[run.request.transition_id]
        target = impl._target
        owners = [("underlay", impl._resources, "draw_image"), ("trails", impl._trails, "draw"),
                  ("begin", target, "begin"), ("end", target, "end"), ("resolve", target, "_resolve"),
                  ("pieces", impl, "_draw_chunks" if hasattr(impl, "_draw_chunks") else "_draw_shards")]
        if hasattr(impl, "_draw_debris"):
            owners.append(("debris", impl, "_draw_debris"))
        if hasattr(impl, "_draw_ghosts"):
            owners.append(("ghosts", impl, "_draw_ghosts"))          # inside "trails": the R8 ghosts alone
        motion = getattr(target, "_motion", None)
        if motion is not None:
            owners.append(("motion_blur", motion, "apply"))
        stamps: list = []
        pending: list = []

        def stamp() -> int:
            query = int(gl.glGenQueries(1)[0])
            gl.glQueryCounter(query, gl.GL_TIMESTAMP)
            return query

        def wrapped(label, original):
            def call(*args, **kwargs):
                before = stamp()
                try:
                    return original(*args, **kwargs)
                finally:
                    pending.append((label, before, stamp()))
            return call

        saved = [(owner, attr, owner.__dict__.get(attr)) for _label, owner, attr in owners]
        for label, owner, attr in owners:
            setattr(owner, attr, wrapped(label, getattr(owner, attr)))
        try:
            for index in range(frames):
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
                gl.glDisable(gl.GL_SCISSOR_TEST)
                before = stamp()
                capture.host.render(capture.frame(run, 0.1 + 0.8 * (index % COST_FRAMES) / (COST_FRAMES - 1)))
                pending.append(("frame", before, stamp()))
                gl.glFlush()                                     # per frame, as the benchmark does
                stamps.append(pending[:])
                pending.clear()
            per_label: dict = {}
            queries = []
            for frame_stamps in stamps:
                seen: dict = {}
                edges: dict = {}                                 # label: (its first start, its last end), ns
                for label, first, last in frame_stamps:
                    queries += [first, last]
                    values = []
                    for query in (first, last):
                        value = ctypes.c_uint64()
                        gl.glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(value))
                        values.append(value.value)
                    seen[label] = seen.get(label, 0.0) + (values[1] - values[0]) / 1e6
                    start, end = edges.get(label, (values[0], values[1]))
                    edges[label] = (min(start, values[0]), max(end, values[1]))
                # N5.2h successor: the native scene run's span timed directly, one pair of stamps: the target's begin
                # (its clear) to its resolve's end (the underlay, the trails and the pieces between); less the ghosts
                # (the native layer draws them in their own unit before the run), its own stamped sub-span.
                if "begin" in edges and "resolve" in edges:
                    span = (edges["resolve"][1] - edges["begin"][0]) / 1e6
                    seen["scene_span"] = span
                    seen["scene_span_less_ghosts"] = span - seen.get("ghosts", 0.0)
                for label, ms in seen.items():
                    per_label.setdefault(label, []).append(ms)
            gl.glDeleteQueries(len(queries), queries)
        finally:
            for owner, attr, original in saved:
                if original is None:
                    owner.__dict__.pop(attr, None)
                else:
                    setattr(owner, attr, original)
    stats = {label: blc._ms_stats(values) for label, values in per_label.items()}
    end = stats.get("end", {}).get("median_ms")
    inner = sum(stats.get(k, {}).get("median_ms") or 0.0 for k in ("resolve", "motion_blur"))
    if end is not None:
        stats["composite_rest_of_end_median_ms"] = round(end - inner, 4)
    return stats


def round_cost(core, engine, app, api: str, variants) -> dict:
    from PIL import Image

    import rendering.quick.render.background_node as background_node

    facts: dict = {}
    checks: dict = {}
    for size in COST_SIZES:
        label = f"{size[0]}x{size[1]}"
        photos = [blc.processed(path, "fill", size) for path in PHOTOS]
        host = blc._host(core, (size[0] + 4, size[1] + 6), 1.0, timestamps=True)
        scene = blc.Scene(core, engine, host, 1.0, size, kind="layer")
        scene.root.setProperty("color", "transparent")           # N5.2h: the product's display scene, as Python's
        clock = Clock()
        scene.layer._clock_ns = clock
        python = _product_python(core, engine, size, photos) if api == "opengl" else None
        saved_time = background_node.time
        background_node.time = _ClockTime(clock)
        try:
            for index, variant in enumerate(variants):
                run = production_run(variant, [image for image, _rows in photos], index + 1)
                scene.present(photos[0][0])
                scene.settle()
                clock.at(run, 0.1)
                if python is not None:
                    python[1].present(photos[0][0])
                    python[1].frames(2)
                    python[1].item.set_transition_run(run)
                    python[1].frames(8)                          # its per-run resources made before the timing
                    python[0].set_gpu_timer(True)
                    python[0].gpu_samples()
                host.set_gpu_timer(True)                         # N5.2g: the fields' frames timed too (OpenGL's
                host.gpu_samples()                               # in-frame form records them at the commit)
                started = time.perf_counter()
                scene.layer.transition(run)
                scene.settle()
                fields_in = _await_fields(scene)                 # N5.2g: a run's fields committed
                ready_ms = (time.perf_counter() - started) * 1000.0
                scene.frames(4)
                start_records = [s.nanoseconds / 1e6 for s in host.gpu_samples() if s.kind == 2]
                walls = []
                python_walls = []
                if python is not None:
                    python[0].gpu_samples()                      # the timing starts with the native layer's
                for frame in range(COST_FRAMES):
                    clock.at(run, 0.1 + 0.8 * frame / (COST_FRAMES - 1))  # the effect, never the plain ends
                    started = time.perf_counter()
                    scene.layer.tick()
                    scene.frames(1)
                    walls.append((time.perf_counter() - started) * 1000.0)
                    if python is not None:
                        started = time.perf_counter()
                        python[1].item.update()
                        python[1].frames(1)
                        python_walls.append((time.perf_counter() - started) * 1000.0)
                scene.frames(4)
                samples = host.gpu_samples()
                host.set_gpu_timer(False)
                python_frame_gpu = []
                if python is not None:
                    python[1].frames(4)
                    python_frame_gpu = [s.nanoseconds / 1e6 for s in python[0].gpu_samples() if s.kind == 0]
                    python[0].set_gpu_timer(False)
                    python[1].item.set_transition_run(None)
                    python[1].frames(2)
                surface = [s.nanoseconds / 1e6 for s in samples if s.kind == 2]
                frame_gpu = [s.nanoseconds / 1e6 for s in samples if s.kind == 0]
                facts[f"{label}_{variant}"] = {"core_record_gpu": blc._ms_stats(surface),
                                               "qrhi_frame_gpu": blc._ms_stats(frame_gpu),
                                               "gui_tick_and_frame_wall": blc._ms_stats(walls),
                                               "samples": int(run.request.parameter_dict().get("samples", 0) or 0),
                                               # N5.2g: the run's start to its fields' commit (the job's build and
                                               # upload, wall; 0 fields: the settle alone), and the core's field count.
                                               "fields_ready_wall_ms": round(ready_ms, 3),
                                               "start_record_gpu_max_ms": round(max(start_records, default=0.0), 4),
                                               "fields": (scene.layer.state().get("mode") or {}).get("fields")}
                if python is not None:
                    # N5.2h: the comparable pair (same instrument, same frames): qrhi_frame_gpu against this.
                    facts[f"{label}_{variant}"]["python_product_frame_gpu"] = blc._ms_stats(python_frame_gpu)
                    facts[f"{label}_{variant}"]["python_product_wall"] = blc._ms_stats(python_walls)
                    checks[f"{label}_{variant}_python_timed"] = len(python_frame_gpu) >= COST_FRAMES // 4
                checks[f"{label}_{variant}_fields_in"] = fields_in
                if variant == "crossfade":
                    control, control_checks = _clear_control(core, api, scene, host, clock, run)
                    facts[f"{label}_{variant}"]["clear_control"] = control
                    checks.update({f"{label}_{variant}_{k}": v for k, v in control_checks.items()})
                if variant in SCENE_CLEAR_CONTROL_VARIANTS:
                    control, control_checks = _clear_control(core, api, scene, host, clock, run, route="scene")
                    facts[f"{label}_{variant}"]["scene_clear_control"] = control
                    checks.update({f"{label}_{variant}_scene_{k}": v for k, v in control_checks.items()})
                if variant in SCENE_PASS_VARIANTS:
                    units, unit_checks = _scene_passes(core, scene, host, clock, run, api)
                    facts[f"{label}_{variant}"]["scene_passes"] = units
                    checks.update({f"{label}_{variant}_{k}": v for k, v in unit_checks.items()})
                checks[f"{label}_{variant}_timed"] = len(surface) >= COST_FRAMES // 2
                scene.layer.transition(None)
                scene.present(photos[1][0])
                scene.settle()
        finally:
            background_node.time = saved_time
            scene.close(app)
            facts.setdefault("host_close", []).append(blc._close_host(app, host))
            if python is not None:
                python[1].close(app)
                facts.setdefault("host_close", []).append(blc._close_host(app, python[0]))
        if api == "opengl":
            pictures = [Image.fromarray(rows, "RGBA") for _image, rows in photos]
            capture = product_capture(size[0], size[1], *pictures, 1.0)
            try:
                for index, variant in enumerate(variants):
                    run = production_run(variant, [image for image, _rows in photos], index + 1)
                    capture.render(run, 0.5)                     # its per-run resources made before the timing
                    facts[f"{label}_{variant}"]["python_opengl"] = capture.benchmark(run)
                    if variant in SCENE_PASS_VARIANTS:
                        facts[f"{label}_{variant}"]["python_stages"] = _python_stages(capture, run)
            finally:
                capture.close()
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _route_on_vulkan(core, engine, app, frames, facts, variants=ROUTE_VARIANTS) -> dict:
    """The product's route: ``BackgroundRenderItem.set_transition_run`` on the native backend draws the run through its
    layer, the same pixels as the layer driven directly; the run's end draws the destination. Each ``ROUTE_VARIANTS``
    entry the run drew, in its own host. A selection (``--variants``) holding no route variant judges no route; one
    holding a route variant the round did not draw fails ``route_variant_drawn``."""
    dpr = 1.5
    selected = [v for v in ROUTE_VARIANTS if v in variants]
    if not selected:
        facts["route_variants"] = []
        return {}
    drawn = [v for v in selected if f"dpr{dpr}_{v}_{progress_key(PROGRESS[0])}" in frames]
    if len(drawn) != len(selected):
        return {"route_variant_drawn": False}
    facts["route_variants"] = drawn
    checks: dict = {}
    for route_variant in drawn:
        for name, ok in _route_variant_on_vulkan(core, engine, app, frames, facts, route_variant, dpr).items():
            checks[name] = checks.get(name, True) and ok
    return checks


def _route_variant_on_vulkan(core, engine, app, frames, facts, route_variant: str, dpr: float) -> dict:
    from rendering.quick import bootstrap

    owner = bootstrap._owner
    # The run is resolved before the backend is the native one: N5.2c's scenes are drawn natively before Vulkan offers
    # them (registration comes last, playbook checklist 18), so the resolver would refuse them on Vulkan.
    photos = [blc.processed(path, "fill", blc.DISPLAY) for path in PHOTOS]
    run = production_run(route_variant, [image for image, _rows in photos], 1)
    saved = (owner.core, owner.backend)
    owner.core, owner.backend = core, bootstrap.QuickBackend(api="vulkan", requested="vulkan")
    checks: dict = {}
    host = blc._host(core, blc.WINDOW, dpr)
    scene = blc.Scene(core, engine, host, dpr, blc.DISPLAY, kind="route")
    try:
        scene.present(photos[0][0])
        scene.settle()
        layer = scene.item.native_layer
        clock = Clock()
        layer._clock_ns = clock
        clock.at(run, PROGRESS[0])
        scene.item.set_transition_run(run)
        scene.settle()
        _await_fields(scene)                                     # N5.2g: a run's fields committed
        same = {}
        for progress in variant_progress(route_variant):
            clock.at(run, progress)
            layer.tick()
            scene.frames(1)
            rows = scene.display_rows(scene.read())
            same[progress_key(progress)] = blc.compare(rows,
                                                       frames[f"dpr{dpr}_{route_variant}_{progress_key(progress)}"])
        scene.item.set_transition_run(None)
        scene.item.set_presentation_image(photos[1][0])
        scene.settle()
        end = scene.display_rows(scene.read())
        checks["route_draws_the_run_as_the_layer_does"] = all(c["equal"] for c in same.values())
        checks["route_ends_on_the_destination"] = blc.compare(end, photos[1][1])["equal"]
        checks["route_ran_one_run"] = layer.state().get("runs") == 1
        facts.setdefault("route", {})[route_variant] = {"frames": same, "layer": layer.state()}
    finally:
        scene.close(app)
        facts.setdefault("host_close", []).append(blc._close_host(app, host))
        owner.core, owner.backend = saved
    return checks


#: The gather's bound in the display's pixels (2K of the display's allocation: ``motion_post_values``' uLongest).
def _longest() -> float:
    from rendering.quick.transitions.native_scene import motion_geometry

    return 2.0 * motion_geometry(blc.DISPLAY).tile


N52D_LONGEST = _longest()
TIE_LEVEL = pt.TIE_LEVEL


def _native_velocity(scene):
    """The native scene's velocity of the frame just drawn (``scene.velocity``'s x and y, read back), in the display's
    frame: the target's content rows [H - h, H) top first are the display's rows (the core's frame, F1), and its y is
    the display's down (Python's up negated, read back on the build)."""
    import numpy as np

    mode = scene.layer.mode
    mode.read_targets()
    mode.update()
    scene.frames(3)
    pixels = None
    for _ in range(30):
        pixels = mode.target_pixels()
        if pixels:
            break
        scene.frames(1)
    velocity = None
    for entry in pixels or []:
        if entry["name"] == "scene.velocity":                  # N5.2h: one RGBA16F, the motion in .xy
            width, height = entry["size"]
            velocity = np.frombuffer(entry["data"], np.float16).reshape(height, width, 4).astype(np.float32)
    if velocity is None:
        return None          # a frame showing a photograph (no scene): judged by the edges alone, the stricter
    h, w = blc.DISPLAY[1], blc.DISPLAY[0]
    velocity = velocity[velocity.shape[0] - h:, :w]
    return velocity[..., 0], velocity[..., 1]


#: Black flicker (operator, 21 Nov): a run's first frame keeps the source's lit pixels lit (at most this fraction of
#: them black: a transition's own first frame may darken a few, none blacks the picture out).
FIRST_FRAME_BLACK = 0.01
BLACK_LEVEL = 4
LIT_LEVEL = 24


def black_over_lit(frame, source) -> float:
    """The fraction of the source's lit pixels (any channel past LIT_LEVEL) that ``frame`` shows black (every channel at
    most BLACK_LEVEL)."""
    import numpy as np

    lit = source[..., :3].max(axis=2) > LIT_LEVEL
    black = frame[..., :3].max(axis=2) <= BLACK_LEVEL
    return round(float((black & lit).sum()) / max(1, int(lit.sum())), 5)


def _over(a, b, level: int) -> int:
    """How many pixels of ``a`` differ from ``b`` by more than ``level`` in any channel."""
    import numpy as np

    if a.shape[:2] != b.shape[:2]:
        return a.shape[0] * a.shape[1]
    difference = np.abs(a[..., :3].astype(np.int16) - b[..., :3].astype(np.int16)).max(axis=2)
    return int(np.count_nonzero(difference > level))


#: N5.2c variants that are one authored fragment between the two pictures (Blinds' flat style: no scene, no target),
#: judged as N5.2b's fragment passes are (the lead, 21 Nov), with its own scatter bound: BLINDS_FLAT_RULE_A.
N52C_FRAGMENT_VARIANTS = ("blinds_flat",)


def _is_fragment_pass(variant: str) -> bool:
    drawn = variant.split("@", 1)[0]
    return (drawn in N52B_VARIANTS or drawn in BEAM_VARIANTS or drawn in N52C_FRAGMENT_VARIANTS
            or drawn in N52G_VARIANTS)


def _await_fields(scene, frames: int = 600) -> bool:
    """N5.2g: frames until the run's fields are committed (the layer's ready edge started its effect); the harness then
    holds the run's clock itself, so the effect's clock offset is zeroed (the layer test proves the offset). True when
    they were in (a run without fields: at once)."""
    layer = scene.layer if getattr(scene, "layer", None) is not None else scene.item.native_layer
    for _ in range(frames):
        if not layer._fields_pending:
            break
        scene.frames(1)
    layer._clock_offset_ns = 0
    return not layer._fields_pending


def _multisampled_scene(entry: dict) -> bool:
    """N5.2c: a scene drawn with more than one sample (rule b only: MULTISAMPLED_RULE_A)."""
    return bool(entry.get("scene")) and int(entry.get("samples", 0)) > 1


def _rule_a(variant: str, entry: dict):
    """Rule (a)'s tolerance for ``variant`` (None: not judged by rule a, a multisampled scene)."""
    if _multisampled_scene(entry):
        return None
    drawn = variant.split("@", 1)[0]
    if drawn in N52C_FRAGMENT_VARIANTS:
        return BLINDS_FLAT_RULE_A
    if drawn in N52G_VARIANTS and variant_transition(drawn) == "capillary_bloom":
        return CAPILLARY_RULE_A
    if _is_fragment_pass(variant):
        return FRAGMENT_PASS_RULE_A
    if not entry.get("scene"):
        return pt.EXACT
    return JIGSAW_RULE_A if variant_transition(drawn) == "jigsaw" else N52C_RULE_A


def _environment_copies(core) -> int:
    """N5.2c: the photo environments' copies drawn in the process so far (``composite_live``). A module that does not
    count them is refused (a missing count must never read as "no copy", which would pass the copy check)."""
    live = core.composite_live()
    copies = live.get("stage_environment_copies") if isinstance(live, dict) else None
    if isinstance(copies, bool) or not isinstance(copies, int) or copies < 0:
        raise RuntimeError(f"composite_live() has no environment copy count (stage_environment_copies={copies!r}): "
                           "the module predates N5.2c or its accounting is broken")
    return copies


def _reads_environment(run) -> int:
    """The photo environments a run's scene copies (N5.2f: Volumetric Dissolve also the old picture's)."""
    from rendering.quick.render.native_background import native_transition_renderer

    renderer = native_transition_renderer(run.request.transition_id)
    if renderer is None or not getattr(renderer, "native_scene", None):
        return 0
    scene = renderer.native_scene(run, blc.DISPLAY)
    return int(bool(scene.environment)) + int(bool(getattr(scene, "source_environment", False)))


def _neighbour_frames(frames, key: str) -> list:
    """The same run's frames at the progress either side of ``key``'s (``<dpr>_<variant>_<progress>``)."""
    stem, progress = key.rsplit("_", 1)
    variant = stem.split("_", 1)[1]
    keys = [f"{stem}_{progress_key(p)}" for p in variant_progress(variant)]
    at = keys.index(key)
    return [frames[k] for k in keys[max(0, at - 1):at + 2] if k != key and k in frames]


def vulkan_against_opengl(work: Path) -> dict:
    import numpy as np

    vk_path, gl_path = work / "route_vulkan.npz", work / "route_opengl.npz"
    if not (vk_path.exists() and gl_path.exists()):
        return {"pass": False, "error": "both APIs' frames are needed"}
    vk, gl = np.load(vk_path), np.load(gl_path)
    velocity_path = work / "velocity_opengl.npz"
    velocity = np.load(velocity_path) if velocity_path.exists() else {}
    per_variant: dict = {}
    worst = 0
    judged: dict = {}
    for key in sorted(set(vk.files) & set(gl.files)):
        result = blc.compare(vk[key], gl[key])
        variant = key.rsplit("_", 1)[0]
        entry = per_variant.setdefault(variant, {"frames": 0, "max_pixels": 0, "max_level": 0, "max_over": 0})
        entry["frames"] += 1
        entry["max_pixels"] = max(entry["max_pixels"], result.get("differing_pixels", 0))
        entry["max_level"] = max(entry["max_level"], result.get("max_level", 0))
        entry["max_over"] = max(entry["max_over"], _over(vk[key], gl[key], VULKAN_TOLERANCE))
        worst = max(worst, result.get("max_level", 255))
        drawn = variant.split("_", 1)[1]
        tolerance = (BEAM_RULE_B if drawn in BEAM_VARIANTS else
                     MEMBRANE_RULE_B if drawn == "membrane" else
                     N52C_RULE_B if drawn in SCENE_VARIANTS else
                     N52G_RULE_B[variant_transition(drawn)] if drawn in N52G_VARIANTS else
                     FRAGMENT_PASS_RULE_B if _is_fragment_pass(drawn) else SEVEN_RULE_B)
        if drawn in EDGE_FLIPS_B:               # N5.2d: the piece-edge flip class (rule b); the gather-free N52C_RULE_B
            moved = velocity[key] if key in velocity else None
            allowed = piece_edges(vk[key], gl[key], _neighbour_frames(gl, key), moved, N52D_LONGEST)
            sampler = N52F_SAMPLER_RULE_B.get(drawn)
            judged.setdefault(variant, []).append(judge_piece_edges(
                vk[key], gl[key], EDGE_FLIPS_B[drawn], allowed, ties=N52C_RULE_B.tie_pixels,
                **({"scatter_pixels": sampler, "compact_past": 1} if sampler is not None else {})))
            continue
        judged.setdefault(variant, []).append(pt.judge(vk[key][..., :3], gl[key][..., :3], tolerance))
    for variant, frames in judged.items():
        per_variant[variant]["tolerance"] = pt.summarise(frames)
    ok = bool(per_variant) and all(e["tolerance"]["pass"] for e in per_variant.values())
    return {"pass": ok, "worst_level": worst, "variants": per_variant,
            "bounds": [SEVEN_RULE_B.bound(), FRAGMENT_PASS_RULE_B.bound(), BEAM_RULE_B.bound(), N52C_RULE_B.bound(),
                       *(t.bound() for t in N52G_RULE_B.values())]}


# --------------------------------------------------------------------------------------------------- the child


def child(args) -> dict:
    import host_check
    import vk_validation

    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    record: dict = {"api": args.api, "module_loaded": False, "instance_created": False}
    if args.api == "opengl":
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="transition-route-check")
        from PySide6.QtWidgets import QApplication

        app = QApplication([sys.argv[0]])
    else:
        from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Vulkan)
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication([sys.argv[0]])
    from PySide6.QtQml import QQmlEngine
    from rendering.native import NativeCoreUnavailable, load

    try:
        core = load((root / args.module_dir) if not Path(args.module_dir).is_absolute() else Path(args.module_dir))
    except NativeCoreUnavailable as exc:
        record["error"] = f"the module did not load: {exc.reason}"
        return record
    record["module_loaded"] = True
    record["runtime"] = dict(core.info)
    vulkan = args.api == "vulkan"
    if vulkan:
        instance = core.vulkan_instance(validation=True)
        record["instance"] = instance
        if not instance.get("ok"):
            record["error"] = f"the Vulkan instance failed: {instance.get('instance', {}).get('error')}"
            return record
        record["instance_created"] = True
        core.set_vulkan_phase("n52a draw")
    engine = QQmlEngine()
    try:
        try:
            if args.cost:
                record["draw"] = round_cost(core, engine, app, args.api, args.variants)
            else:
                record["draw"] = round_draw(core, engine, app, args.api, args.variants, work, out)
        except Exception:
            record["draw"] = {"pass": False, "error": traceback.format_exc()}
    finally:
        blc._flush(app)
        record["live_hosts_at_end"] = core.live_hosts()
        record["composites_at_end"] = core.composite_live()
        record["jobs_at_end"] = core.job_counts()
        if vulkan:
            teardown = core.destroy_vulkan_instance()
            messages = teardown.pop("messages", {}) if isinstance(teardown, dict) else {}
            summary = vk_validation.validation_summary(messages)
            record["instance_teardown"] = teardown
            record["validation"] = {"layer_loaded": bool(record["instance"].get("validation_layer_loaded")),
                                    "per_phase": messages.get("per_phase"),
                                    **{k: v for k, v in summary.items() if k != "groups"},
                                    "attribution": summary["groups"]}
        del engine
    return record


def main(argv: list[str] | None = None) -> int:
    import host_check
    import vk_validation

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", default="release/native_module")
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--variants", nargs="+", default=list(VARIANTS), choices=list(VARIANTS))
    parser.add_argument("--label", default="n52a_transition_route")
    parser.add_argument("--topic", default="n5_2a", help="the evidence topic (n5_2b for N5.2b's runs)")
    parser.add_argument("--layer-path", type=Path, default=None,
                        help="the folder holding VkLayer_khronos_validation.json (VK_ADD_LAYER_PATH for this run only)")
    parser.add_argument("--require-validation", action="store_true",
                        help="a Vulkan run whose validation layer did not load is a FAIL, never a pass")
    parser.add_argument("--cost", action="store_true",
                        help="the performance step instead of the draw: GPU time per run at COST_SIZES (round_cost)")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--api", choices=APIS, help=argparse.SUPPRESS)
    parser.add_argument("--out-dir", help=argparse.SUPPRESS)
    parser.add_argument("--child-json", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.child:
        try:
            record = child(args)
        except Exception:
            text = traceback.format_exc()
            record = {"api": args.api, "error": text.strip().splitlines()[-1], "traceback": text}
        args.child_json.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
        return 0

    missing = [str(p) for p in PHOTOS if not p.is_file()]
    if missing:
        print(f"N52A VERDICT FAIL: photos missing ({', '.join(missing)})")
        return 0
    vk_validation.use_layer_path(args.layer_path, _ALLOWED_ENV)
    root = host_check._root(args.repo)
    from tools import artifact_paths

    out = artifact_paths.evidence_dir("native_core", args.topic, args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    results: dict = {}
    for api in [a for a in APIS if a in args.apis]:
        child_json = out / f"child_{api}.json"
        child_json.unlink(missing_ok=True)  # discard any earlier child record before launch
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--variants", *args.variants, *(["--cost"] if args.cost else [])]
        started = time.monotonic()
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=CHILD_TIMEOUT_S, cwd=str(root))
            exit_code, stderr = proc.returncode, proc.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code, stderr = "timeout", str(exc.stderr or "")
        record = json.loads(child_json.read_text(encoding="utf-8")) if child_json.exists() else {
            "api": api, "error": f"the child process ended without a record ({exit_code})"}
        child_json.unlink(missing_ok=True)
        record["exit_code"] = exit_code
        record["seconds"] = round(time.monotonic() - started, 1)
        if exit_code != 0 or record.get("error"):
            record["stderr_tail"] = (stderr or "")[-4000:]
        results[api] = record

    verdicts = {api: blc.api_verdict(api, record, args.require_validation) for api, record in results.items()}
    failed = [reason for _ok, reasons in verdicts.values() for reason in reasons]
    for api, record in results.items():
        entry = record.get("draw")
        if isinstance(entry, dict) and not entry.get("pass", False):
            bad = [k for k, v in (entry.get("checks") or {}).items() if not v]
            failed.append(f"{api} draw: {bad or entry.get('error', 'failed')}"[:1500])
    comparison = None
    if set(APIS) <= set(args.apis) and not args.cost:
        comparison = vulkan_against_opengl(out / "work")
        if not comparison.get("pass"):
            failed.append(f"rule (b): Vulkan against OpenGL native, worst {comparison.get('worst_level')} levels")
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "variants": args.variants, "environment": environment,
               "require_validation": args.require_validation,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "vulkan_against_opengl": comparison, "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons)[:2000] + ")"))
    if comparison is not None:
        print(f"vulkan against opengl: worst {comparison.get('worst_level')} levels; "
              + json.dumps(comparison.get("variants")))
    print(f"evidence: {out / 'summary.json'}")
    print("N52A VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
