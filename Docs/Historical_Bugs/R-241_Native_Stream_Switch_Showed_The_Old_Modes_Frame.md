# R-241: a native stream switch showed the old mode's frame

**21 November 2026. Fixed in the native core at ABI 27 (958f40418), regression case at ABI 28 (merged 48de19846).
Status: FIXED.**

## Observed failure

During the Oscilloscope port (N5.1), owner rule (a) failed on the frames right after the replay switched from the
Oscilloscope to Bubble. The native path drew the Oscilloscope's last frame under Bubble for a frame, where Python drew
nothing of it. Nothing logged it: the card simply presented a stale picture.

## Root cause

`StreamSource::syncStream` (`native/core/src/stream_source.cpp`) cleared its held frame at a new stream's first sync only
when the new stream held nothing yet. When the new stream's first frame was present but rejected by admission (not a
present frame), the source kept `m_hasFrame` from the old stream, so the old mode's last admitted frame was drawn under
the new mode. The same path serves every native mode switch, not only the Oscilloscope's; it shows only where a
switch's first frame is rejected.

## Repair

- At a new stream's first sync the source drops the old stream's frame whatever the new stream's first read is
  (`m_hasFrame = false`); its first admitted frame then draws. With no stream bound, the last admitted frame still stays,
  so a card's fade-out after an unbind fades a frame, not a cleared target.
- Checkpoint audit 10 (M4, `Docs/Future_Work/Checkpoint_Audits_Nov21.md`) probed it directly on ABI 27 and asked for a
  regression case: `native/core/python/generic_mode_check.py` now binds a new stream whose first frame admission rejects
  and checks that nothing of the old stream shows and that its first real frame draws, on both APIs.

## Validation boundary

The case passes on OpenGL and Vulkan at ABI 28. It has no negative control: reverting the fix would need a switch in
the core, which the project does not add for one check.

## Lesson

A source that holds a frame across reads must define what a new binding inherits. Here the "new stream holds nothing"
case was handled and the "new stream's first frame is rejected" case was not; parity at a mode switch is what found it.
