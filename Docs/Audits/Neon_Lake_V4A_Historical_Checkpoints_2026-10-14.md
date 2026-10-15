# Neon Lake V4A historical checkpoints (superseded)

This is an archival copy of the earlier `Current_Plan.md` Neon Lake implementation/checkpoint
notes before the operator closed all but two active Neon Lake actions on 2026-10-14.
The checkboxes and acceptance requests below are **historical**, not live action items.
The current two-item scope is solely in `Current_Plan.md` §2A; authoritative
implementation contracts remain in `Docs/Reference/Neon_Lake_Basin.md`.

---

**2026-10-13 Settings-handoff audit:** The operator's `logs6a63dcda0b3.zip` records a
Settings-requested destruction-barrier timeout: after Qt objects and resources drained,
`QuickDisplayUnit` and `QuickDisplayVisualizerOwner` were still retained, preventing
Settings launch (exit code 1). Explicit mode-independent Qt runtime signal callbacks
were found strongly capturing the display unit; converted to weak generation-fenced
routes. The terrain editor received the established Spectrum/Dev Curve dark-glass
palette with no change to authored terrain or brush/preset semantics. Standalone
signal-lifetime and editor-contract tests are green; **not a Windows crash-fix
certification**, particularly for the remaining visualizer owner. For code paths,
visual complexities, proposed Settings retirement/consolidation, and withheld
features see `Docs/Audits/Neon_Lake_Settings_And_Settings_Handoff_2026-10-13.md`.
All control removals/consolidations and new capability work require operator
approval. Skyline remains provisional and unchanged; Preset 1 protected.

**2026-10-13 late Neon Lake follow-up (source implemented, physical acceptance OPEN):**
The operator's latest screenshot (`image(20261013-215744).png`) rejects the projected-column skyline: it drew horizontal magenta boxes; do not restore that shader. The current handoff replaces it with a land-only screen-space silhouette of the *same displaced triangle mesh*, offset 1.8 physical pixels and rejected by its own true terrain depth. It also establishes landscape depth before sky colour/Sun/Moon, removing the `GREATER` rear-body path that let stars/bodies show through nominally thick Glass. `logs6a63dcda0b6.zip` and operator traceback identify the Settings `KeyError` for the `shockwave_grid:terrain_motion` bucket absent from canonical UI defaults: corrected with a closed-by-default key and spec/bucket default parity test. `Starscape Beat` is added as an opt-in checkbox (OFF by default so Preset 1 visuals stay untouched) and consumes the existing admitted strong-onset ring; up to three widely separated panoramic stars per beat illuminate briefly and fade without any new timer, DSP, or polling. The terrain brush and hover cursor are now physically circular on non-square editors. Retired Edges values are handled by a one-way input/preset migration, not a live spec normalizer. Preset 1's file remains unchanged; Presets 2/3 are still retired. **Do not close V4A; test screen pixels, panorama star placement, real-music transients, foreground/mountain occlusion, clipping, MSAA, and dual-1440p overhead on Windows**. Prior 10/10 passing tests were not visual proof, nor are any new Mesa shader compiler checks. All test invocations must use the project venv and may not mutate environment variables.

**2026-10-14 Neon Lake camera/sky/glow follow-up (implemented, physical validation OPEN):** The operator now accepts the main depth-tested terrain silhouette; keep its actual-triangle outline. The latest physical image revealed a flat sky/terrain transparency seam, no visible Starscape Beat reactivity, effectively fixed Sun/Moon corona brightness and still-missing subdued rear horizon. This handoff draws the sky once across the full framed interior, then performs the original terrain-depth admission while subtracting the sky's premultiplied colour/emission by the **same smooth terrain-coverage fade**. It retains the depth-masked Moon/Sun and thick-glass rule without an alpha-step where the outer skirt fades. Skyline uses the real continuation's base height rather than clamping the texture at the editor edge, and has a restrained distant-land silhouette tail. Celestial Glow Enabled/Intensity/Reactivity and Star Glow Intensity/Reactivity join an advanced **Glow** bucket (canonical closed-default UI state); they use the same visualizer midband/onset-ring, not a second FFT, clock or timer. Star selection admits realistic strong beats (>=0.35 instead of 0.85) and targets visible existing panorama cells rather than offscreen candidates. Celestial Orbit Speed range is bounded to 0..0.025 rev/s; the prior authored Preset 1 at 0.016 rev/s stays byte-identical. **No GPU pixel acceptance, vocal-isolation claim, or full-performance certification is made.** Operator to inspect sky fade, distant contour, glow contrast at silence/vocals/onsets, reflections and dual-display frame-time overhead. No environment-variable mutations; Windows Qt runs must use the project's `.venv`. Keep V4A open.


**2026-10-14 Neon Lake Settings UX regrouping (implemented; Windows UI round-trip pending):**
The existing advanced Glow bucket now contains Surface Glow, Ridge Light Response, Celestial Halo
and its two controls, Light Rays and its two controls, Starscape Beat and its two controls.
Starscape Beat moves from Sky to Glow; Light Rays moves from Celestial to Glow; Ridge Light Response
moves from Waves to Glow. Water Detail and Flow now sit in Waves; Water Reflection moves to Render.
The timing-only `terrain_motion` bucket is titled **Growth Timing** while retaining the same persisted
bucket key. Shared declarative visibility conditions now support AND predicates so dependent halo,
ray and beat-star rows are hidden unless **all** of their owning toggles are enabled. Disabled/hidden
rows retain their saved values. No new keys, altered defaults/ranges, timers, render/DSP changes,
card geometry changes, or curated-preset rewrites. Preset 1 is still byte-for-byte protected,
Presets 2/3 remain retired; the accepted main mountain skyline is untouched. Standalone spec tests
are green; UI signal/live load/collect round-trip on Windows is still operator/local validation,
not a claim of physical visual proof. Use the project `.venv`; no environment-variable mutations.

**2026-10-14 diagnostic reproducibility + scene correction (source changes, OPERATOR VALIDATION REQUIRED):**
`logs6a63dcda0b9.zip` confirms Settings succeeds at 01:06:15 (barrier clears in 664 ms),
Neon Lake activates at 01:06:29, the RUN GC freeze captures 210,488 objects at
01:06:50, and a second Settings request at 01:07:00 fails at 01:07:08 with two
`QuickDisplayUnit` and one `QuickDisplayVisualizerOwner` retained. Diagnostic
`gc.get_referrers` sees zero referrers because the active generation is in the
permanent generation: the policy's existing documentation admits such cycles
are not collected before unfreeze, yet unfreeze previously happened only on RUN
exit. Fix: at a RUN stop boundary, thaw once before asynchronous retirement;
when zero Qt/GL/task/subscription roots remain, the **existing strict barrier**
may ask that same GC-policy owner for exactly one explicit stop-only cycle sweep.
Do not weaken the barrier, introduce a timer, or collect in presentation. A
second freeze is not performed in this RUN after replacement. The existing
45-second one-shot will not freeze while Settings is open. This must be verified
with Settings → Neon activation → idle past the original 45-second freeze point
→ Settings again; PySide/Windows runtime verification has NOT occurred here.

The initial diagnostic Settings snapshot has `shockwave_grid_starscape_beat=False`;
a later in-Settings edit could have enabled it, and there is no subsequent
value snapshot proving the live activation's toggle state. Therefore this log
alone cannot establish whether the failed visual response was enabled. Existing captured strong
onsets are present. The selected beat-star cells now map the *actual* framed sky
camera ray (fit, internal zoom/pan, tilt/turn), rather than guessing elevation
from tilt alone. No new DSP or animated timer. Sky alpha tapers over a broad
angular horizon band and remote ground heights vary mildly to address the hard
wallpaper opacity stripe / unnaturally flat distant silhouette. The foreground
accepted depth-tested mountain skyline and Preset 1 authored values remain
unchanged. These are shader/geometry hypotheses until Windows GPU pixels and
real-music reactivity have been inspected; V4A remains open.

## 2A. Visualizer spec migration | V4A next

One mode per slice in this order. Rendering, saved values, Settings appearance/behavior and musical response remain
unchanged **except for the explicitly authorized Shockwave Grid replacement in V4A**.
`core/settings/visualizer_mode_settings.py` owns declarations; bespoke shape editors stay Custom entries for modes that
still use them. Oscilloscope, Sine Waves, Dev Curve, Extruded Spectrum, Spectrum and Voxel Sphere are migrated; Shockwave already has spec-layer support; Shockwave's existing support does
not substitute for completing its spec migration **together with** the Neon Lake Basin rework. No further Oscilloscope
acceptance gate.

- [ ] **V4A — Shockwave Grid: finish spec migration AND completely rework into Neon Lake Basin in the same slice.**
  This is one coordinated Settings/spec + logical/reaction + renderer + authoring replacement, **not** a spec-only pass
  followed by a postponed visual upgrade. Use `Docs/Future_Work/Additional_Future_Transitions_Package.zip`, including its
  `Additional_Future_Transitions.md` and the **Neon Lake Basin low-/high-react visual mocks**, as the concept and
  feasibility reference. Replace the flat Shockwave Grid scene with an 80s/cyberpunk neon-wireframe basin: an editable
  terrain heightfield whose **unraised/base-level regions are water**, with raised mountains/islands around or within it.
  Both water (ripples/rings/wave propagation) and terrain (contour glow, restrained displacement and ridge energy)
  react musically, with distinct tunable responses rather than identical motion. Replace Shockwave's shape-authoring
  approach with a **proper terrain editor** exposed as a bespoke spec-owned Custom entry. Complete and consolidate
  all remaining controls, defaults, conditional settings, persisted state, presets and editor hooks through the new
  `visualizer_mode_settings` spec method; do not create competing settings or geometry authorities. Preserve existing
  mode identity/activation and shared audio/transient, Quick presentation, orbit/geometry and lazy Scene3D ownership,
  staying on the Qt Quick + Python + OpenGL 4.6 architecture. Adapt old saved settings safely where possible instead
  of silently corrupting or discarding Custom state.
  **Framing contract (operator, 2026-10-13):** Neon Lake Basin is a normal bordered/framed card containing an orbitable
  3D scene. Use CARD / CARD_INTERIOR presentation and retain the applicable 3D geometry/orbit contracts inside that card.
  The scene never escapes its border at any pose or during Edit; no overflow option may bypass the clip. Forward-retire
  the old Shockwave overflow state at canonical input/save boundaries, and prove real rendered clip pixels as well as
  fixed outer-card geometry through orbit/resize. The old frameless Shockwave policy is superseded by this replacement.
  Preserve the existing 3D bindings: **WASD / Alt+left-drag orbit, Alt+right-drag moves, Alt+scroll scales**. In framed
  modes every one targets the internal scene, leaving outer-card position, size and viewport unchanged. Internal
  turn/tilt/pan/scale persist through future load via the canonical view-pose owner, independently of art presets and
  CUSTOM geometry. Add real input/settlement/reload tests and an independent audit even if the implementation appears
  correct; this spec/descriptor contract is the template for later bordered 3D modes.
  **Visual correction (operator, 2026-10-13):** the first rendered candidates are rejected for poor fidelity. Wireframe,
  including terrain, must be based on curves; water must retain the older Shockwave crest/trough ripple character;
  terrain needs its own growth mechanics; the sun must be independently optional and vibrant. Use genuine displaced
  3D geometry, shared Scene3D projection/depth/resources and the existing logical clock. Do not accept a flat cosmetic
  substitute or a dense straight-triangle reskin. Preserve this correction alongside the mock and Astra's detailed audit.
  Reuse existing GPU wave/event facilities, stream rings, bloom and scene primitives; any missing heightfield/material
  capability is built as a measured, opt-in shared primitive **within this V4A delivery**, not silently deferred to §4
  or added as a private rendering stack. **High visual and musical parity with the supplied mocks is required on at
  least one curated preset**, at both low and high reactivity, rather than accepting a token terrain reskin. Keep other
  presets freely operator-editable; do not freeze artistic preset values as regression-test oracles. Prove terrain
  editing/save/reload/reset, water classification, distinct terrain/water response, quiet/onset/sustained passages on
  fixed synthetic clips and the operator's real-music recordings at
  `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\logs\visualizer_recordings`, plus bounded CPU/GPU cost and
  dormancy in both-display use.
  Reject jelly mountains, harsh strobing, uncontrolled flashes or saturated glow; high react should be powerful but
  still legible. Scope and checkpoint V4A internally as necessary, but **do not mark migration complete until the
  full rework and at least one high-parity preset are implemented and accepted together**.
  Internal checkpoints remain part of this one delivery:
  Render-cost baseline before this replacement: `tools/baselines/overhead/2026-10-13_000e222e.json` (960×540,
  control-relative timings and deterministic GL/Python call counts; compare unrelated consumers after shared changes).
  Terrain/migration, typed controls, editor and five-key framed input/persistence are source-complete; durable contracts
  live in `Docs/Reference/Neon_Lake_Basin.md`. Native input, real QSG clipping, authoring/save/reset, lazy GPU ownership
  and shared-consumer preservation have focused proof. Visual acceptance remains open and the source checkpoint does
  not close V4A.
  - [ ] **V4A.3 — Shared heightfield and complete scene.** Add only the missing opt-in sampling/classification/GPU
    representation to Scene3D, mirrored by CPU/GL tests. Reuse the existing onset ring, MeshResources, StreamRing,
    SceneTarget and optional emission bloom. Terrain changes replace one bounded GPU representation; ordinary frames
    allocate/rebuild nothing. Deliver distinct water waves and solid terrain/ridge response with lazy retirement, a fixed
    normal card and unconditional interior clipping of the orbitable 3D scene.
    Curved cubic geometry/wire paths, separate capture-clock growth, old crest/trough response, bank continuity and
    optional vibrant Sun are implemented. Surface Style is spec-owned, with Vertices the default; vertices use
    the same displaced surface lattice, lazy resources and real GL points. Growth-only passage weighting now separates
    quiet/loud recordings without changing water events. The source and visual work still needing completion is:
    - [ ] Recheck the roughly 10% denser vertices and real foreground continuation in the final presets, including the
      previously visible bottom-right hole, coherent surface depth and rounded card clipping.
    - [ ] Break/distort mirrored wire shapes into water trails, preserving bright shoreline connections and dark gaps.
    - [ ] **Glass and retained combinations (revised by operator approval):** deliver only Vertices, Glass and Glass + Vertices through Surface Style. Generic Edges/Both combinations are retired; skyline and lake outlines are separate effects. Glass uses smooth 3D normals, shared Scene3D GGX/Fresnel materials and sky/body reflections; Glass + Vertices uses outlined markers. Expose tint, strength, roughness and point colours conditionally. Confirm depth, thick-glass sky occlusion, clipping and lazy resources physically on Windows.
    - [ ] **Celestial body:** add spec-owned Sun/Moon choice, authored 3D position and separate RGBA colours. Add optional
      orbit around the visible scene, **default off**, driven only by the existing logical animation clock. Body placement
      and orbit must remain inside the card scene, independently of outer geometry and the five-key camera pose.
    - [ ] **Optional volumetric light:** integrate bounded 3D scattering/terrain occlusion from the authored body into
      mountains and lake through shared Scene3D/heightfield facilities. Keep the disabled path dormant; measure enabled
      quality-tier cost. Do not substitute a flat screen-space ray decoration for scene-aware light.
    - [ ] Audit colour controls for body, terrain/wire accents, water, sky, horizon/clouds/stars and rays; promote any
      missing authoring to the canonical spec without duplicate UI/model/binding tables.
  **2026-10-13 operator-approved simplification and provisional visual pass (NOT accepted):** the operator confirmed only Preset 1 is salvageable and must remain protected. Shipped Neon Lake presets 2/3 are now explicitly retired through GODZIP debris; Preset 1 is left byte-for-byte unchanged, and Custom remains. User approval covers removing generic internal Edges and reducing Surface Style to Vertices / Glass / Glass + Vertices (legacy persisted values are normalized), clarifying UI labels, and moving growth timing under Advanced, without changing growth DSP. The left-side skyline smear was caused by grazing-angle lighting and is replaced by a dedicated projected terrain-sky envelope line using the shared heightfield and GL depth; its fidelity is **provisional**. Repeated outer-hill heights are decayed sooner; Sun/Moon get a faint visible-body halo with a modest spectrum midband intensity lift and unchanged orbit/lighting authority. Shader compile/link and static coverage tests are not operator pixel acceptance; request screenshots at multiple camera angles and check any skyline gaps, glow, performance and former edge-style migration. No `--shaders` flag added in this slice. No environment-variable setup is authorized for tests.
  **2026-10-13 regression / superseding repair (NOT operator-accepted):** the first overscan
  Godzip produced catastrophic diagonal sheeting, separated terrain and foreground interference
  on the RTX 4090 with Glass + Vertices. The operator supplied physical screenshot and logs;
  shader compiles and 90 fps did NOT establish correctness. The root cause is pre-clipping
  screen-space perspective division of a wide terrain skirt containing vertices behind the
  camera. The repair uses *homogeneous* basin-local camera projection, hardware near-plane
  triangle clipping, matching body/depth-prepass projection, and additional near-skirt alpha
  fade. The same extended triangle/point UV lattice remains in place. Verified on software
  Mesa: both GLSL programs compiled/linked under GLSL 4.50 (diagnostic header change only),
  plus standalone no-environment-mutation geometry/eye-crossing tests; the Windows production
  GLSL 4.60 / Qt Quick visual result is still UNSIGNED and must be inspected. Do not mark
  continuity, skyline, or camera physical acceptance closed until the operator sees it.
  **Test-policy blocker:** existing `tests/conftest.py` changes APPDATA and LOCALAPPDATA through
  process environment variables. Those mutations violate the operator's standing rule; do
  not recommend any normal pytest route through that fixture as compliant. Geometry tests
  must use `py -3.14 -m pytest -q --noconftest tests/test_neon_lake_landscape_extension.py`
  until test storage isolation is reworked without environment-variable mutation. This
  renderer slice intentionally does not remove test-wide storage guards in a way that could
  expose the operator's actual settings/cache.
  **2026-10-13 operator review of repaired near-plane scene:** the first catastrophic
  projection regression is physically resolved; the operator now sees the extended
  Vertices + Glass geometry and largely acceptable camera bounds. Do not interpret
  this as final V4A acceptance. Image 1 shows a narrow oblique coverage hole and
  unnaturally extruded infinite edge hills; Image 2 needs several more degrees of
  flattened/upward camera tilt; Image 3 demonstrates that the mountain skyline
  outline is essentially absent. The next follow-up widens the mode-only far/front
  coverage, smooths outer hills down rather than preserving tall border heights,
  lowers the allowed minimum camera tilt to 0.17 (~15 degrees), and strengthens
  the approximate land rim without enabling general mesh edges. Preset 1 is
  protected; reject repeat changes to its terrain or artistic values. The orbiting
  Sun/Moon is an analytic ray-sphere, not a planar circle. Only the camera-visible
  disc fades out when it approaches/engulfs the eye; orbital light/reflections
  remain active. Verify the revised tilt, unusual coverage angle, star/land skyline,
  Glass + Vertices and close body orbit on the operator's RTX 4090 before closure.
  **Suggested separate diagnostic backlog:** evaluate opt-in `--shaders` startup
  switch for bounded GL debug messages, program compile/link/resource admissions
  and useful labels, **not** per-frame readbacks or a competing scheduler. Current
  program owners already raise compilation/link errors; such a switch would not
  automatically diagnose visually valid-but-wrong geometry/shading. Do not add
  runtime work without dedicated operator approval and performance-neutral design.
  **2026-10-13 additional source checkpoint, pending physical/visual confirmation:** operator's
  Preset 1 is the sole salvage reference; do not modify its authored terrain, palette or Custom
  values during renderer fixes. The bounded overscanned mesh now extends each axis beyond
  the editor with lower distant lattice density; vertex markers and fill use the identical
  UV lattice. The continuation stays land outside editor ownership and fades terrain, glass,
  wire illumination, reflected colour and point markers before the remote mesh boundary.
  Neon-only view spec ranges bound turn/tilt (WASD and Alt-drag cannot wrap) and scene pan
  is scale-dependent through canonical presentation admission, retaining Alt-scroll zoom.
  A raised-land grazing-angle skyline highlight reuses the existing crest colour, musical
  energy and glow. These are new physical source changes, **not proof of attractive pixels,
  complete horizon coverage, stable GPU cost or acceptable skyline contour**. Validate
  foreground/right/left/back at wide and tall card sizes and maximum zoom, all Vertices/Glass
  choices and sun/moon, both displays, and confirm no bad orbit angle. Do not close V4A.
  The operator's next intended scope is settings mass simplification and likely retirement
  of non-outline Edges, keeping the lake shoreline and desired mountain skyline, but that
  is deliberately deferred; no preset changes or Settings deletion in this slice.
  - [ ] **V4A.4 — Preset, reaction and visual proof.** Author one editable basin preset, capture low/high frames and
    quiet/onset/sustained sequences from identical synthetic and real clips, and compare with the supplied mock.
    Use the single High Astra audit after this significant renderer work; resolve parity findings before acceptance.
    Measure control-relative CPU/GPU/resource cost at supported tiers and both-display use. Leave only evidence that
    genuinely needs operator eyes/logs as Awaiting Validation; internal green checkpoints alone do not close V4A.
    **Current visual audit actions:** separate dark terrain faces from selective cyan/magenta curve/ridge light; add a
    luminous irregular shoreline and broken water reflections without reflected land fill; replace dotted water with
    directional ripples/sheens driven by the original waves; retain an enclosed lake and foreground continuing to the
    card bottom; give the optional sun vibrant colour/emission and keep a navy sky with sparse stars and broken clouds.
    Make all three starting presets visibly different in terrain, palette, water/growth response, wire style and celestial
    presentation, with orbit off unless the operator chooses it. Capture the actual presets and production quiet/onset/sustained motion after these corrections; stills and
    green engineering tests do not establish fidelity. Refresh the stale Guided Setup mode artwork from accepted pixels.
