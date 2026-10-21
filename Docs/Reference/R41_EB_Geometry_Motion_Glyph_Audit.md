# R41 | EB screenshot geometry, range transport and glyph presentation

## Status and evidence

Operator screenshots: Settings 3/4 volume editor for Light, Ray and Stream, native
Sunlit Surface scene capture (2026-10-21 22:46), Media hover-glyph placement, and
native pytest output: 1 failure/9 pass in `test_r39_hover_edit_qml_native.py`.
Do not claim visual or native correction based on these screenshots or Qt-free checks.

## Geometric audit

The oblique world-volume editor is NOT the exact view from `physical_camera()`;
its rendering cannot be compared as if it were a projection of the underwater
capture. Camera marker and Aim marker are authored physical pose, not an FOV knob.
One screenshot can show plausible water overhead and shafts, not establish their
world-space pixel parity. Use production camera eye/matrices + Dev-only projected
landmarks for an exact source/end→pixel comparison. No extra runtime loop.

`scene_knobs` in `extruded_bubble_scene.py`:
- **Surface:** Light Source→End determines distant `sun` direction. The visible
  sun/surface glow uses a directional sun projection; physical Ray Source→End
  independently bounds volumetric shaft samples. Consequently they are not
  automatically co-located. This is a design/semantic audit, not a confirmed
  faulty transform from the supplied view alone.
- **Deep:** renderer replaces `ray_source` with `light_source`. Deep light emitter,
  glints and shaft source are intended to coincide; Ray End independently bounds
  beam reach. Check native pixels, attenuation, exposure and color separately.
- **Stream:** Source→End is its own physical transport path, independent of
  illumination. Never force unrelated light/ray paths to match it silently.

## Musical motion, auditable counterexample

`extruded_bubble_simulation.advance()` resolves Stream Speed and Drift musical
ranges but applies both via a compressed `change_drive` and a separate activity
factor; fixed-follow stream rate attack is 0.68 s, drift 0.20 s, release slow.
Camera perspective and sine-wander amplitudes can hide logical changes even when
synthetic source tests pass. Record stable-ID positions and per-frame pixels for
slow/fast/slow music, not merely idle/active. Preserve all nine range audit flags,
large-radius plateau, small judder, ray response and strict lifecycle failure.

## UI candidate

- Hover chrome anchors to the *actual* ordinary card, not host accessory width.
- Close X is centred vector strokes inside the same 24 px circular button.
- Glyph tooltip: short static text, one compact renderer per admitted hover widget,
  delayed by an explicit 1800 ms QML NumberAnimation whose first 1008 ms remain
  completely transparent; action change restarts delay. Existing hover events
  only; no Timer/polling/window/thread. Native cost and interaction checks pending.
- EB Settings tooltips wrap their authoritative text to bounded human-readable
  lines using escaped Qt rich text, including `[NEEDS AUDIT]`; no spec changes.
- Native hover QML gate should attach the test item to an actual Quick window
  before checking effective visibility, retaining semantic Lock checks.

## Operator acknowledgement and remaining scope

Operator accepts manual screenshot captures and general hover-glyph interaction,
slow reveal and child-edit actions. Archive their history outside the active EB
queue. Correctness of this new layout, vector X, tooltip dwell/fade and old test
remain unaccepted. This is no basis for closing the EB visual fidelity list.
