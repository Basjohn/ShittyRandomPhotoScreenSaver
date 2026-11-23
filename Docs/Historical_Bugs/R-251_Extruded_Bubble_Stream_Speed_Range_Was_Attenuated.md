# R-251 | Extruded Bubble attenuated the authored Stream Speed range

**Date:** 23 November 2026. **Status:** global stream endpoint correction verified with held inputs.
The operator still reports insufficient visible speed swing during playback in the latest run.
[Post-port follow-up](../../Current_Plan.md#1b10a-extruded-bubble-stream-and-particle-response-after-the-native-port).

The recorded PCM runs showed improved global-stream modulation on heavy and ragdoll. Peak speeds reached
87.6%, 95.6% and 97.2% of the authored span in the heavy, acoustic and ragdoll takes, respectively.
Those runs and the held-input controls leave live full swing, individual particle-layer transport and
Studio controls open. The 22:46 Studio entries in `logs8acd9d88e9.zip` still show separate Peak and Quiet
controls and a save to the existing range.

## Symptom

The operator reported that Stream Speed missed the authored quiet and loud values. Old and new shells already
shared the same forward velocity owner. Their correlation with the global stream measured how they followed it,
while the stream's actual amplitude remained unverified.

## Cause and repair

`ExtrudedBubbleSimulation.advance` multiplied the entire interpolated speed by activity, including during
playback. At settled zero energy this turned an authored 0.12836 into 0.05295. A cascade through the shared
passage follower, fixed headroom, a soft ceiling and the stream follower left the upper endpoint out of reach
during held body energy. Maximum constant body input produced 0.83191 against an authored 0.89165.

The stream now maps the existing fixed-scale passage and body feed monotonically to the authored interval.
A beat uses the remaining headroom before the single fast-attack, slow-release speed follower. During pause it
releases toward the existing settled idle speed. The transport still carries existing shells and integrates
procedural travel from the same published physical speed.

## Falsifiers

- The existing simulation test file tests literal active endpoints, strictly increasing intermediate targets and a
  faster active rise than release. Both new tests failed on the original owner and pass with the repair.
- Three whole 60-second recordings on the two comparable authored profiles show zero active below-minimum
  samples and zero upper-stop occupancy. Human and Ragdoll show greater quiet-to-loud modulation. Acoustic's
  former quiet excursion crossed the lower handle. It now approaches that handle on quiet input.
- The per-tick traces, six replays, fixed-input control, and comparison plot are under
  `.artifacts/evidence/visualizers/extruded_bubble/stream_speed_range/20261123_candidate_steps/`. N5.6's refreshed native references are a
  separate validation step.
