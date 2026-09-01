# R-71 — Visualizer Audio Per-Frame Task And DSP-State Allocation Drove GC Pressure

Date: 2026-09-01
Status: H performance remediation accepted; residual rare deep-GC debt deferred to late J

## Symptom

Heavy source-mode runs remained visually smooth much of the time but showed periodic deep Python GC/event-loop stalls, including ~80-120ms-class and later ~130-146ms collections. Earlier runs also showed very high audio-analysis job counts and queue/execute accounting despite the analysis itself being modest work.

The danger was to treat GC as a collector-threshold problem and hide it by reducing Visualizer cadence/reactivity.

## Evidence And Root Allocation Sources

A pre-repair run submitted roughly `26,219` `visualizer.audio_analysis` generic compute jobs in about 6.5 minutes — effectively one Task/Future/callback chain per captured frame. The repository already contained a persistent serial compute-lane primitive designed to avoid that ownership/allocation pattern, yet the Visualizer had not migrated onto it.

After moving audio analysis to the persistent lane, another source-side smell remained: each analysis packet still deep-reconstructed detached NumPy/history/transient DSP state. That produced high short-lived allocation pressure even though only one analysis operation could be in flight.

The second repair retained detached DSP state across ordinary serial-lane frames and rebuilt it only at real config/activation/reset epoch changes.

## Accepted Architecture

```text
shared BeatEngine
-> persistent serial visualizer.audio_analysis lane
-> at most one executing packet
-> at most one newest pending source replacement
-> retained detached DSP state between ordinary frames
-> explicit epoch invalidation on config/activation/reset
-> stale result rejected if an epoch boundary lands during compute
-> newest immutable logical/render state publication
```

There is **no** generic Future/task fallback. Required lane creation failure is loud.

A small per-request stable `previous_bars=tuple(self._smoothed_bars)` snapshot remains intentionally. The live silence/UI path can mutate the backing list in place; removing that tuple merely to reduce allocation would reintroduce a correctness race without evidence that the tuple is the dominant tracked-GC source.

## Measured Result

Across the H investigation, normalized gen-0 pressure moved from roughly `19-20/s` in bad lane-era runs to `~12.2/s` after retained DSP state, then to about `~9.8/s` in the final deliberate heavy-load run. The final run produced only two gen-2 collections over roughly 312 seconds (~`0.39/min`).

The remaining deep collections were still large (~`130-146 ms`) and reclaimed real cyclic objects. They are accepted as optimization debt, not declared ideal.

Audio/reactivity evidence remained strong in the final heavy-load run: approximately 89-90 logical Visualizer revisions/s when active, typical snapshot age ~18-22ms, mean analysis execution ~1.86ms, and no generic Future fallback/busy-lane failure population.

## Failed / Forbidden Directions

Do not improve GC/perf counters by:

- lowering authored Visualizer cadence;
- batching or FIFO-queueing old audio frames instead of newest-source replacement;
- allowing source/snapshot age to grow while visuals continue;
- reducing musical response amplitude/motion or applying viewport-dependent compression;
- retuning Bubble/Spectrum/DSP to hide stalls;
- restoring per-frame generic Future/task submission;
- changing GC thresholds simply to reduce collection count without allocation/lifetime evidence;
- making GC less frequent by retaining unbounded objects/resources;
- deleting the stable previous-bars snapshot without a replacement race-proof ownership contract.

## H Closure Decision

No further H-stage allocation source had the same combination of strong evidence and low reactivity risk. Performance therefore exits H with the persistent lane + retained DSP-state architecture accepted.

Further work belongs near the end of J, after visual parity/residue cleanup stabilizes the tree. It must start from fresh allocation/lifetime evidence and preserve the golden Visualizer reactivity/freshness contract.
