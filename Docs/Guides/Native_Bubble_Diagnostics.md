# Native Bubble diagnostics

`tools.visualizer_replay.bubble_native_diagnostics` keeps the Bubble owner replay and its bounded fade and attachment probes available for parity investigation and optimization analysis. The live work and acceptance order are in `Current_Plan.md` N5.1; findings and retained receipts are in [Native Bubble Parity Investigation](../Future_Work/Native_Bubble_Parity_Investigation.md). The class-word upload failure is recorded in [R-238](../Historical_Bugs/R-238_OpenGL_Unsigned_Uniform_Arrays_Dropped_Class_Words.md); [Bubble Temporal Fidelity](../Guardrails/Bubble_Temporal_Fidelity.md) §24 owns the separate recorded-music optimization gate.

These recipes use the existing owner, hidden host, canonical graphics configuration and pixel judge. Their fixed synthetic scope is 5.5 seconds, variant a, display placement and 549 ordinary inputs. Inputs 244 and 346 and their component landmarks belong to that recipe; they are not general landmarks for other clips or settings. No environment flags or alternate renderer are needed. Run with the matching official native module and a fresh label for each receipt, under the lead's GPU reservation and timeout.

From the repository root, with the project virtual environment active (replace the placeholders with real paths and fresh labels):

```powershell
python -m tools.visualizer_replay.bubble_native_diagnostics replay --repo . --module-dir release/native_module --label <fresh_replay_label>
python -m tools.visualizer_replay.bubble_native_diagnostics fade-inputs --repo . --module-dir release/native_module --label <fresh_fade_label> --baseline-dir <replay_evidence_dir>
python -m tools.visualizer_replay.bubble_native_diagnostics components --repo . --module-dir release/native_module --label <fresh_components_label> --baseline-dir <replay_evidence_dir> --passive-dir <fade_evidence_dir>
```

`--repo` must identify the checkout containing the tool. Each command writes a date-prefixed directory under `.artifacts/evidence/native_core/n5_1_bubble/`; the artifact-path owner resolves its storage. The label must be unused: existing output is refused. Preserve receipts and use a new label for each run. `--baseline-dir` names the replay directory; `--passive-dir` names its matching successful fade-input receipt. The probes require matching module, source, settings and full 549-frame provenance; inspect the metadata and all guards rather than assuming a partial run is comparable.

- `replay` retains the owner parity report, all ordinary frame hashes, the reference/native images selected by the canonical owner, and `reproduction_metadata.json` with provenance and the input-244 capture. It does not archive every frame image.
- `fade-inputs` retains `fade_capture_metadata.json` for the recipe's inputs 244 and 346, including actual fade, uploads and native card data. An optional `--quad-adapter <existing_adapter_path>` runs the explicit own-vertex quad control. That control combines changed geometry with `itemClipMatrix` rounding; it is a falsifier, not an isolated geometry result or product acceptance.
- `components` requires the matched passive receipt and retains `component_capture_metadata.json` and `ambient_components_346.npz` for the fixed input's ambient pre/post-mask coverage and post-mask light. Its physical and restoration guards must pass before interpreting the captured differences.

The command preserves the owner's exit code: exit 1 can be an honest owner parity failure even when diagnostic guards pass. A completed run with failed diagnostic guards returns 2; exceptions also fail and may have another nonzero exit. Inspect `owner_exit_code`, `passive_guards_pass` and the individual checks in metadata separately. A failed or interrupted capture is not a successful diagnostic and must not be rewritten as one. Cleanup and registry restoration are part of the recorded guards.

## Optimisation gate

After the port lands, Bubble is optimised on OpenGL and Vulkan; these tools, `tools/visualizer_replay/bubble_parity.py`, `bubble_fidelity.py`, `tools/conventions_identity.py` and BTF §24 are that work's proof, and none of them is deleted. An optimisation's before/after proof passes four tiers in order:

- **(a) Logic and reactivity, zero loss:** `bubble_parity.py` save/compare under frozen settings, plus BTF §24's real-music frame-by-frame byte-parity lock (the `bubble_fidelity.py` observer).
- **(b) Pixels, byte parity per backend:** the standard proof is the four 60 s recorded clips of BTF §24 (`owner_render_parity.py --native --mode bubble --runs bubble --placements display --seconds 60 --recording <take>`), all-frame hashes before against after, identical on OpenGL and separately on Vulkan; the 5.5 s `replay` recipe is the quick check. Across backends the bound stays rule (b)'s one level; byte parity is never claimed across backends.
- **(c) Where hashes differ:** `fade-inputs` and `components` classify where.
- **(d) Cost:** the port's per-pass GPU timing, `tools/overhead_baseline.py`, and `preflip_pack.py --compare`.

Long-clip runs keep the frozen settings exactly as set, adaptive ones included (the replay's Bubble settings run Dynamic Floor, Adaptive Sensitivity and AGC on; never switch them off for a run). Each clip runs continuously from a cold owner with no reset of any adaptive state between frames or segments. Adaptive state drifts with clip length, so late-clip results are reported separately: the owner report's `rule_a_halves` gives rule (a) for the first and second half of the mode's shown span, and a second half worse than the first is classified before anything else.

An optimisation that cannot hold byte parity (reordered float math, half floats, merged passes) is a tier-2 change: it needs the shared tolerance (`tools/pixel_tolerance.py`) and the operator's sign-off, never a silent pass. The `replay` recipe's current limits (synthetic clip, one variant, no hash-only compare) are an open plan item.

For an optimization investigation, capture a matched before/after pair and use these probes to classify changes in final fragments, ambient attachments and fades, retaining the original owner judge and provenance. They are not GPU benchmarks and do not replace BTF §24's recorded-music matrix, exact logical fidelity, independent performance/reactivity measurement and live operator acceptance. The separate fringe/archived research helper remains ignored research pending promotion; it is not a durable CLI command.
