# R-227 | Partial scene allocations were invisible to resource accounting

**Status:** fixed and proved 16 Nov 2026, N3.1c L3. Owner: `native/core/src/scene_targets.cpp`, `SceneTargets::allocateStep`.

The new bounded allocation proof stopped between attachment steps while native textures were still owned.
Its skipped-destruction control failed: the normal zero-resource predicate accepted this live partial allocation.
This was a proof/accounting defect; no leaked texture was demonstrated.

The canonical target/global counters were updated only in the final render-target or capture step.
An incomplete target therefore reported zero targets, textures and bytes, despite owning QRhi texture objects.
The normal one-record allocation loop had hidden this interval.

The repair updates those existing counters after every allocation step, successful or failed.
It counts only owned texture pointers, including optional captures; borrowed attachments remain their owner's.
`releaseTarget` remains the sole subtraction owner. Completed targets do no extra bookkeeping per record.

Proof: `scene_target_check.py --apis opengl vulkan --rounds partial_retire_control`, separately from `--rounds retire`.
The first module (`b7b2d4105`) reported zero for two live textures and the skipped-release control failed on both APIs.
The repaired module (`2b63f4752`) reported two textures / 2,621,440 bytes; skipping destruction failed the normal
retirement predicate, and actual destruction returned all target counters to zero before host close.
Vulkan validation was required; only recorded Qt defect A was excused.
Evidence: `.artifacts/evidence/native_core/n3_1/20261116_l3_partial_control_before_accounting/summary.json`,
`20261116_l3_partial_control_after_accounting/summary.json` and `20261116_l3_retire_after_accounting/summary.json`.
