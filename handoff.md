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
- [x] Cross-stage shared-resource admission proved on official build and both backends (R-235).
- [x] Same-layout mesh retarget/tail retention and reserved conventions/set-zero admission proved on both APIs (R-236/237).
- [x] Bubble class-word upload and unsigned-vector admission repaired/proved on both APIs (R-238); parity remains open.
- [x] Texture-size control and real wrong-mip negative proved; size derivation alone did not reproduce excess.
- [x] Current matched backend check confirms this GL excess absent on Vulkan (R-232).
- [ ] Non-blocking deeper N3.4 investigation by another agent; retain R-232's stats, failed avenues and hypotheses.
  No production barrier or tracking exception without proof; no consumer hold from this investigation (operator, 16 Nov).
- [ ] Finish N5.1's unlanded shared mask-AA candidate (`widgets/spotify_visualizer/shaders/bubble_ambient_mask.vert`
  and `.vert.qsb`); focused old-shader negative and candidate tests are proved, full replay/fringe acceptance pending.
  Resume: `Docs/Future_Work/Native_Bubble_Parity_Investigation.md`; evidence
  `.artifacts/evidence/native_core/n5_1_bubble/20261116_mask_support_candidate/` and
  `20261116_components_346_v2_c53/` (69 guarded checks). Archive/fringe helper:
  `.artifacts/evidence/native_core/n5_1_bubble/20261116_reference_archive_prep/archive_reference.py`;
  complete provenance audit, then old-reference and candidate archives serially. Official module remains ABI25 c53e3fe27.
- [ ] Finish reusable diagnostics at `tools/visualizer_replay/bubble_native_diagnostics.py` and private
  `_bubble_native_*.py` helpers; `tests/test_bubble_native_diagnostics.py` owns CPU guards. Receipt-provenance audit
  and durable tool documentation are pending; keep frozen evidence/helpers intact. Then continue Bubble parity,
  with unchanged bounds, before Oscilloscope.
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
