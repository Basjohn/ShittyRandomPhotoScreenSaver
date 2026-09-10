# Voxel Sphere — Playback State Is Not Ingress Authority (2026-09-10)

## Symptom

While the source remained in the playing state, incoming voxels could continue to appear through acoustically silent passages. Hardware logs included `active=True` frames with live pre-AGC bass/mid/high all at zero while an incoming envelope was still visible. Some residual envelope is legitimate landing from the preceding event; **authoring a new cohort from playback state or stale event evidence is not.**

## Cause / architectural trap

`playing` proves source ownership/lifecycle only. It says nothing about current acoustic energy. Incoming particles are visually expensive enough that treating source-active state as implicit admission makes quiet scenes feel permanently busy and increases perceptual jerk.

## Binding fix

- New incoming cohorts require a hysteretic **live pre-AGC** energy gate.
- A typed event may bypass the normal open threshold only when the same frame has non-silent live pre-AGC support; true silence always rejects new intake.
- Existing cohorts may finish their landing after the gate closes; do not hard-cut them.
- Optional energy-scaled cohort density and transient velocity are presentation modifiers only. They must not become event detectors, polling loops, or new audio workers.
- The four-corner stable-rank distribution remains independent of event/dominant identity; density changes threshold membership, never the hash.

## Do not regress

Do not "fix" quiet overactivity by reducing Sphere onset frequency, fragmentation strength, raw pre-AGC freshness, tracer travel, or the accepted vocal-linked bounce. The intake gate controls **permission to admit a new cohort**, not the primary musical reactivity contract.
