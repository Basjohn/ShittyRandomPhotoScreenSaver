# Interim handoff (15–20 Nov 2026)

`Current_Plan.md` owns active work and ordering. Delete this handoff when the lead returns or its interim route ends.
The pre-flip recovery checkpoint is `preflip-checkpoint-20261115`; benchmarks are in `Docs/Reference/Benchmarks.md`.
Never rewrite main or force-push.

- [x] Native retirement, scissor/allocation/oracle proofs, stream-ring harness repair and ABI 25 audit are complete. D17
  owns the detailed evidence and N3.4's remaining performance investigation.
- [~] P1 desktop alpha, DPI and sleep/wake need lead/operator validation at N0.6; hidden results do not close it.
- [x] Whole-query/alignment, blocking-read and populated-VAO controls proved; no production speedup or established cause.
- [x] Sprite uniform control and real wrong-input negative proved; uniform storage alone did not reproduce excess.
- [x] N3.2 L1 shader-interface admission proved on the official build and both backends (R-233).
- [x] Sorted-pack resource/layout admission and live SSBO aliases proved on both backends (R-234).
- [ ] Reproduce and repair vertex/fragment shared-block layout admission, including conventions/storage at that boundary.
- [x] Texture-size control and real wrong-mip negative proved; size derivation alone did not reproduce excess.
- [ ] Select the next N3.4 falsifier of remaining generated gather/control-flow or native submission differences.
  Overlap/contention remains unproved; hardware counters are optional. R-232 retains the investigation. No production barrier
  or tracking exception is admitted.
- [ ] Continue the Bubble port from its N5.1 box. Oscilloscope waits for N3.4's remaining performance gate.
- [ ] Keep N3.6, heavy ports N5.3–N5.6, the Vulkan flip and Python-renderer removal held for the lead.
- [ ] Keep quiet-GPU `stream_ring` performance admission separate from its passing functional proof before a
  Waveform consumer.

Read the relevant plan item and durable contract before work. The lead uses `Docs/Guides/Orchestrator_Handbook.md`;
agents use `Docs/Guardrails/Agent_Worktree_Rules.md`. Native ports use `Docs/Guides/Native_Port_Playbook.md`,
`Docs/Reference/Primitives.md` and the decisions in `Docs/Future_Work/Native_Core_P3_Decisions.md`.

- [ ] Use focused foreground tests. Native builds use the GitHub build runner; local frozen builds are operator-owned.
- [ ] Keep visible runs lead-owned on Display 1 through bounded `tools/d1_run.py`; never show probes on Display 0.
  Obtain the operator's explicit approval for each game60 load run.
- [ ] Preserve authored presets, canonical settings owners, fades, retirement barriers, and protected QSG/clip
  performance. No environment-variable flags; diagnostic instrumentation costs nothing at rest.
- [ ] Retire merged worktrees through `tools/agent_handover.py --retire`; preserve cited evidence and WebPs.
- [ ] Keep the live plan actionable; historical facts belong in the relevant reference or historical bug record.
