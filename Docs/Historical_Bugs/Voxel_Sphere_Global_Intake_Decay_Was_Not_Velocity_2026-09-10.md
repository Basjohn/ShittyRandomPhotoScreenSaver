# Voxel Sphere — Global Intake Decay Was Not Velocity (2026-09-10)

## Failure

The early Sphere **Intake Velocity** control changed the release time of one global
`incoming_drive` scalar. New audio events could raise that scalar again while earlier
voxels were still returning. Physically this looked persistently fast and could reset a
large detached population; it was not particle/cohort velocity.

## Fix / binding contract

- Detached flow is a bounded **four-slot Sphere-only cohort ring** on the existing logical
  frame cadence.
- Each cohort captures stable voxel lane/quadrant, density, strength, travel progress,
  transient velocity accent, vocal-bounce ownership and intake/outtake direction at launch.
- New events do **not** globally change the progress or speed of cohorts already in flight.
  If all four slots are materially occupied, this secondary reward may coalesce rather than
  teleport active voxels.
- Particle Velocity changes real cohort travel duration/curve only. It must never become a
  global audio-chasing velocity multiplier.
- Intake voxels return to their own canonical shell slot. Optional Particle Outtake moves
  the selected source outward/fading while a replacement fades into the same canonical slot.
  Direction is captured at launch and cannot reverse an existing cohort.
- Outtake's extra source is an optional second instanced draw of the **same static Sphere
  voxel buffer**. Do not introduce a second geometry owner, private timer/poller/worker,
  per-voxel Python object graph, or accepted-visualizer behavior.
- Playing/source-active remains lifecycle state only; live pre-AGC energy + qualified events
  remain the admission authority. Preserve the physically accepted four-corner distribution
  and vocal-linked intake bounce.

## Regression signal

If a future implementation can make every visible detached voxel change speed/position when
one new event arrives, or describes one exponential global envelope as "particle velocity",
this bug has returned.
