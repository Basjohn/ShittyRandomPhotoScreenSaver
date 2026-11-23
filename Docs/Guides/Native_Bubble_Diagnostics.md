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

## Display 1 timing control

Use `tools/visualizer_live_check.py --mode bubble --display 1` with recorded audio, the same copied display settings and
fresh evidence labels. Alternate `--app-arg=--graphics-backend=vulkan` and `--app-arg=--graphics-backend=opengl` in paired
runs. Add `--no-perf-hud-text` to the suppression arm. It consumes the held text in the child harness while keeping PERF
sampling and frame tracing active. Verify that `GUI_PERF_HUD_UPDATE` records are present in the control and absent in the
suppression arm. Compare Qt frame-begin gaps and correlated Visualizer swap gaps with the sampled GPU clocks.

## Optimisation gate

The rules for what to run, how much, and when it passes belong to `Native_Parity_And_Timing_Proof.md` (layers L, P, T,
C and its change-type table). This section names only Bubble's own tools for each layer:

- **L:** `tools/visualizer_replay/bubble_parity.py` save/compare, and BTF section 24's real-music byte-parity lock
  (the `bubble_fidelity.py` observer), for any change that touches the simulation, settings or packing.
- **P:** `owner_render_parity.py --recording <take>`. The port's reference hashes are in
  `.artifacts/evidence/native_core/n5_1_bubble/20261117_rule_a_60s_<take>/`. Where hashes differ, `fade-inputs` and
  `components` (above) classify where.
- **T:** `bubble_judder.py` and `bubble_breathing_continuity.py` on recorded music, beside the guide's general T tools.
- **C:** the port's per-pass cost round (`native/core/python/bubble_check.py`), `tools/overhead_baseline.py`.

For an optimization investigation, capture a matched before/after pair and use these probes to classify changes in final fragments, ambient attachments and fades, retaining the original owner judge and provenance. They are not GPU benchmarks and do not replace BTF §24's recorded-music matrix, exact logical fidelity, independent performance/reactivity measurement and live operator acceptance. The separate fringe/archived research helper remains ignored research pending promotion; it is not a durable CLI command.
