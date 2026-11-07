# R-175 | Every Settings round trip left its retired generations in uncollected cycles (~20 MB a round trip)

**Status:** fixed 7 Nov 2026 (`core/performance/gc_policy.py` `collect_retired_generations`, called from
`engine/engine_handlers.py` `_construct_and_start_replacement_runtime`). Regression test with a negative control on
main: `tests/test_settings_roundtrip_retired_generations.py`. Narrowly supersedes R-53's "no production `gc.collect()`"
(see the 2026-10-25 sweep assessment's 7 Nov note).

## Symptom

The live check's Settings round trips (`tools/visualizer_live_check.py --settings-roundtrip`, Waveform P4, 600 s, no
load, 9 round trips) grew about 20 MB a round trip, linear, no plateau, on main (+24 MB RSS) and before the 7 Nov GC
change (+17 MB). Every barrier completed; every reveal re-froze.

## Classification (`--roundtrip-memory`, measured at each reveal before its freeze)

| Category | Per round trip on main | Evidence |
|---|---|---|
| Python-reclaimable cycles of the retired display generation and Settings dialog | ~5,200 objects; one `gc.collect()` there freed them and 11.0 MB RSS/private, every round | DisplayManager, QuickSceneFactory, QQmlEngine, QuickDisplayWindow wrappers (C++ already destroyed), the dialog's ~330 widget wrappers, 15 Python-owned `QQmlComponent`s still alive natively, one ~11 MB heap block |
| Native memory map | heap_large +11.0 MB (one 8–16 MB block a round), heap +5–7, python_arena +4–5; driver (`private_other`), images, stacks flat | `tools/win_memory_map.py` per reveal |
| Qt native trees, GL accounting, OS | flat: app QObject tree 1313→1323, 1 window, 0 GL textures/FBOs tracked, threads 49–51, handles ~1500 | census |
| Retired generations alive | all of them: +2 generations of wrappers each round (DisplayManager + 9 runtime roots, ~330 dialog widgets) | weakrefs and `destroyed` edges per generation |

Spectrum P1 matched (+19 MB RSS, +23 MB private; the same +11.0 MB heap_large block a round), so the owner is the
shared display/Settings lifecycle, not a mode.

## Cause

The destruction barrier judges each retiring generation by reference counting and by native `destroyed` edges
(R-53/R-154): the C++ objects really are gone. Their Python wrappers, with dicts, closures, Python-owned native objects
(`QQmlComponent(engine, url)` has no QObject parent) and buffers, stay in reference cycles. Only a deep collection frees
them, and the RUN thresholds `(2000, 20, 50)` practically never run one: none in either 10-minute run (on main and before
the GC change, `collections=(661, 28, 0)` and `(662, 31, 0)`). On main each later reveal froze that garbage too.

## Fix

`RuntimeGCPolicy.collect_retired_generations()` runs one collection per replacement, at the start of
`_construct_and_start_replacement_runtime`: every caller (Settings, CUSTOM, monitor topology) is the continuation of a
completed destruction barrier (for Settings, also the dialog's), so the barrier has already judged and still fails
closed; no display generation exists at that point. It never runs while a generation is frozen, at frame time, inside a
teardown or outside the RUN policy. It costs 60–90 ms inside the lifecycle window and collects ~5,200 objects a round
trip.

## Proof

- Waveform P4, plain live check, 9 round trips, rounds 2–8 before each teardown: main +22.4 MB RSS / +23.0 MB private
  a round trip; fix +6.3 / +6.9. No barrier timeout, every reveal re-froze.
- Spectrum P1 (census runs): main +19.1 / +22.7; fix +6.5 / +9.1.
- After the fix no retired display-generation object survives a reveal (the census's weakrefs), and the 11 MB
  heap_large block a round trip is gone.
- **Not fully flat:** against no-round-trip controls of the same build, round trips still add ~2–6 MB RSS each, in
  the default native heap (+5–6 MB a round trip in the map, unchanged by this fix). That is a separate, still
  unattributed native owner, tracked in `Current_Plan.md` §3.
- `tests/test_settings_roundtrip_retired_generations.py` drives the real Settings path three times with the real
  `RuntimeGCPolicy` and automatic collection off; on main it fails with "3 retired display generation(s) and 3 retired
  Settings dialog(s) are still reachable".

## Lesson

A barrier that proves native destruction does not prove the Python side is gone. Under a policy that never runs deep
collections, a lifecycle that recreates whole generations must reclaim their cycles itself, after they have been
judged, never before.

## Evidence

`.artifacts/evidence/memory/settings_roundtrip/20261107_settings_roundtrip/` (`wf_p4_census_map_main`, `wf_p4_collect_main`,
`wf_p4_plain_{main,fix}`, `wf_p4_tracemalloc_fix`, `sp_p1_census_{main,fix}`, ...).
