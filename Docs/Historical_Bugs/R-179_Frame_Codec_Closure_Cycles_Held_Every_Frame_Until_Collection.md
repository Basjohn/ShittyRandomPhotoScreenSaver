# R-179 | The frame codec's recursive closures held every encoded frame until the next cyclic collection (a 60-100 MB sawtooth in Waveform Ribbon's engine worker)

**Status:** fixed 8 Nov 2026: `core/visualizer_engine/frame_codec.py` clears `encode`'s `put` and `decode`'s `take`
on every exit. Regression bar:
`tests/test_visualizer_engine_frame_codec.py::test_encoding_and_decoding_leave_nothing_for_the_cyclic_collector`
(before the fix: 30 codec closures left for the collector by 10 round trips, and one per refused call). Found while
reading the first frozen check of the engine worker (`Docs/Future_Work/Native_Core_P2_Engine_Design.md`, step 6,
"Frozen check"). Only the engine-worker path (`--viz-engine-worker`, default off) encodes and decodes frames.

## Symptom

In the frozen check, the Visualizer's engine worker held 142 MB RSS with Spectrum and, after a switch to Waveform
Ribbon, swung between about 160 and 265 MB every 3-4 s (psutil every 1.2 s; `--usage` read 286 and 277 MB). From
source the same session (the worker's message handler in process, recorded PCM, no device) did the same: Spectrum flat
at 78 MB RSS / 55 MB USS, Waveform Ribbon a sawtooth of 84-155 MB RSS / 59-130 MB USS, growing ~32 MB/s and dropping
every ~2.5 s. Gate 4's 1 s / 5 s readings had read it as "105-115 MB private after the first Extruded Bubble or
Waveform Ribbon, then flat".

## Cause

`encode` serialises a frame with a nested function `put` that calls itself, and `decode` reads one with a nested
`take` that calls itself. A nested function that refers to its own name holds its closure cell, and the cell holds the
function: a reference cycle, built on every call. `put`'s closure also holds `out` (the bytearray the payload is being
written into, and its bound `extend`), and `take`'s holds `view` (the memoryview over the payload being read, which
pins the payload). Reference counting can never free a cycle, so every frame's buffer stayed alive until the cyclic
collector next ran. Bytearrays, bytes and memoryviews are not tracked by the collector, so they do not count toward its
allocation threshold: the worker, which allocates few tracked objects per frame, collects rarely, and a mode with large
frames (Waveform Ribbon's packet, Extruded Bubble's arrays) piles up tens of MB of dead payloads between collections.
The main process's `decode` (on the GUI thread, every frame) left the same cycle, with each payload pinned by its view.

A probe that saved the collector's garbage for 0.5 s of a Waveform Ribbon session found only the codec's closures
(`encode.<locals>.put` and, on Python 3.14, its `__annotate__`) with their cells: 240 calls' worth.

## Fix

Both functions run their recursion in `try` / `finally` and set the closure name to None on every exit (`put = None`,
`take = None`), which empties the self-referencing cell: the function, its cells and the buffer go when the call
returns, by reference counting. Encoding, decoding and their refusals are unchanged (the codec's identity tests for
every mode pass). From source after the fix, the same Waveform Ribbon session holds 85 MB RSS / 60 MB USS flat and
Extruded Bubble 57-58 MB USS flat.

## Why it hid

- Every codec test checked bytes and identity; none looked at what a call left behind.
- The cycles are collected eventually, so nothing grows without bound: a sawtooth, not a leak, and a memory reading
  every few seconds lands anywhere on it (gate 4 read it as a plateau).
- The worker's thread and handle counts were flat, and its RSS was dominated by the frozen binary's own pages, so a
  60-100 MB swing looked like a mode's working set.

## Lessons

1. A recursive nested function is a reference cycle per call. On a per-frame path, recurse through a module-level
   function, or clear the closure name in `finally`; test with the collector off and `DEBUG_SAVEALL`, not by reading RSS.
2. Read a worker's memory continuously (one second or finer) across a mode switch before calling a plateau: a
   sawtooth of untracked buffers looks like a plateau at any fixed reading.
