# R-NEW: native settings lost the sign of negative zero through Qt's JSON

**28 November 2026. Fixed in the settings transport (`14d763931`, ABI 47 module built on GitHub from `14d76393`);
found by Extruded Bubble's layer L (N5.6, "Native record and route").**

## What happened

Since 14 Nov 2026 (`76107fcf7`, N2.5 round 4) a native mode's settings travel from Python to the core as
name-to-number JSON (`rendering/native/program_values.py` `settings_json`), and the core parses them with Qt's JSON
reader into the program block (`native/core/src/program_blocks.cpp` `BlockValues::setJson`). Python's `json` writes
`-0.0` as `-0.0`, but Qt's parser stores it as the integer 0, so the native block held `+0.0` wherever the Python
renderer packed `-0.0`. Nothing reported it: every value compared equal (`-0.0 == 0.0`), and the landed modes' L
proofs never met a negative-zero setting.

Extruded Bubble is the first mode whose settings carry negative zeros: `world_point`-derived members (`uLightEnd`,
the stream and speck source and end points) and, at light type 0, `uLightTravel` and `uLightAxis`. Its first L smoke
differed on every frame in those members only by the sign of zero. A sign-of-zero difference can change a shader's
result (`atan`, `sign`, `1/x`, `normalize` of a zero-length vector, `step` at 0), so it is a byte-identity failure
rather than noise.

## The fix

The transport carries the sign; the frozen Python reference producer is untouched (a first fix that canonicalised
`world_point` to `+0.0` changed the producer and missed light type 0's members: `7f9f002d8`, reverted in `853dbb0b3`).

- `settings_json` writes a negative zero as the string `"-0"` (scalars and list items).
- The core's `settingNumber` reads a number, a boolean, or exactly `"-0"` (as `-0.0`); any other string is still
  refused.

## Proof

- `tests/test_native_program_values.py::test_a_negative_zero_travels_as_the_string_the_core_reads_as_one` and
  `tests/test_native_core_mode.py::test_a_negative_zero_setting_reaches_the_block_with_its_sign` (seen failing on the
  pre-fix module; pass on the `14d76393` module, 28 Nov).
- Before the fix, a per-member diagnostic over 11 L runs of Extruded Bubble found signed zero the only difference
  class (`.artifacts/evidence/native_core/n5_6/20261128_diag_*`). After it, L on the rebuilt module: see N5.6's
  "Native record and route" note in `Current_Plan.md` (light type 0 on all three takes, a base and a b run).

## Rule

A value that crosses into the core goes through a transport that keeps its exact bits; when it is text (JSON), the
special values the parser cannot hold (negative zero) are spelled explicitly and read back explicitly, and a test
compares bits, never `==`.
