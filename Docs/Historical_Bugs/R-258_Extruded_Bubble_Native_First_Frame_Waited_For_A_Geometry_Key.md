# R-258: Extruded Bubble's native first frame was never drawn (it waited for a geometry key the record could not name)

**28 November 2026. Fixed in the core (`native/core/src/compute_passes.cpp`, ABI 47, commit `29a844943`, built at
`8bf270aa7`); found by N5.6's native-OpenGL rule (a) smoke ("P, T and C"), where input 0 differed by 252,112 pixels at
up to 211 levels: the native card was empty while Python's showed the scene.**

## What happened

Extruded Bubble's drift (the chains, the snow and the specks) is solved on the GPU from steps the logical frame
carries, and its geometry travels through the D3 arena: each family's record names a geometry key, and the core binds
that key's buffer when it is resident (`ModeStorage::syncGeometry`). A record naming a key the arena does not hold yet
makes the frame wait (`waiting: a geometry buffer has no resident key`), so a draw never reads half-written geometry.

The first logical frame of a stream has no drift families yet: the drift log publishes them from its first step,
which comes with the second frame. The record's projection (`DriftRecordProjector.project`) then names the null key
for all three families, correctly. The core read a null key as "no resident key" and waited the frame, so the native
item drew nothing at input 0. Python draws that frame with the families absent: the backdrop, the shells and the glass
are there, only the drift is not. From input 1 on, every family had a key and both renderers drew.

Nothing failed loudly. The item's state said `last_reason: waiting: a geometry buffer has no resident key yet` with
`draws: 0` at input 0 (`.artifacts/scratch/n56key/first_frame_probe.py`, the projection's null keys printed beside the
item's state). In the product the same frame would have been missing at every start of the mode and after every
reactivation: the card's fade-in started from a frame that was not there. Layer L never draws, and the earlier smokes
were dominated by larger differences (R-256, R-257), so only the rule (a) run on the module with those fixed showed it.

## The fix

A declared geometry buffer whose record names no key binds a 16-byte zero placeholder (`emptyGeometry`, made once per
slot and never counted as a residency), and the frame does not wait. The compute entries that read the buffer still
hold, as for any absent family (`geometryResident`: no current key), so nothing is solved from the zeros and the draws
that read the drift output draw nothing of it, exactly as Python draws the absent family. A record that names a key
the arena does not hold yet still waits, as before.

## Proof

- `tests/test_native_eb_port_core.py::test_a_record_naming_no_geometry_key_draws_and_its_entries_hold` checks the
  core's source: an absent key binds the zero buffer and is not waited on, and the zero buffer never counts as
  resident (so the entries hold). Its in-test controls (the absent key waited on again; the zero buffer counted
  resident) fail it, and it failed on the old source (`.artifacts/scratch/n56key/src_control.py`). The ABI 46 test
  beside it keeps a named key that is not resident yet held with its trigger.
- The rule (a) smoke on the built module (human_heavy1, 6 s, both variants at both placements;
  `.artifacts/evidence/native_core/n5_6/20261128_rule_a_input0/`): all 594 frames of each run published and drawn.
  Input 0 now differs by 187 pixels at 1 level (variant a) and 73 at 3 levels (variant b), against 252,112 at 211
  before, the same order as its neighbours. The runs still fail rule (a) on other frames: speckled 1-3 level ties
  inside the near layer's defocused bubbles and scattered pixels, up to 55 levels. That is reported under N5.6, not
  this entry.

## Rule

A native record that names no resource (a family with no geometry yet, a stream with nothing to upload) is a valid
frame with that content absent, never a frame to wait for. Waiting is only for a named resource that is not resident
yet. A first frame must fade in, never be missing.
