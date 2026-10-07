# R-106 | Visualizer Dormancy Audit and Frame-Trace Observer Pressure

Status: **CLOSED / PHYSICAL ACCEPTANCE GREEN**
Opened: 2026-10-05
Closed: 2026-10-05
Binding contracts: `Docs/Guardrails/Performance_Optimization_Contract.md` P5 and
`Docs/Guardrails/Visualizer_Presentation.md` 1A.

## Scope

This record preserves two things discovered in the same audit:

1. architectural dormancy/retirement smells that remain active engineering tasks; and
2. the intermittent `memoryview`/native-startup failure that appeared during `--frame-trace` runs and is now physically closed.

The remaining dormancy/terminal-owner work is sequenced only in `Current_Plan.md`; this historical record is not a second
checklist.

## Dormancy findings retained as negative controls

### Inactive Sine heartbeat

The common logical tick previously called Sine heartbeat without first requiring Sine to be active, so a saved non-zero value
could retain energy/transient/event queries after switching away. The correction resolves heartbeat only for active Sine and
fences before those queries during replacement; inactive Sine contributes zero heartbeat work.

### Per-mode early-return dispatch growth

The common tick historically called mode-specific helpers and relied on each inactive helper to return immediately. That cost is
small for a few modes but violates count invariance if repeated for every new registry entry. The durable destination is one
optional logical-step hook resolved at activation. The controller now retains that one callable; registry-derived switching,
lazy-import and synthetic-growth tests protect it against accumulating hot-path dispatches.

### Registry-derived proof

Dormancy tests must derive from the canonical Visualizer registry and prove lazy import/construction, inactive non-advancement,
resource retirement and hot-path cost independent of registry cardinality. Hand-written mode counts are not an acceptance bar.

## Separate terminal Python-owner smell

One supplied shutdown timed out after Qt/resources/thread work had drained while Python ownership still listed
`QuickDisplayUnit`, `QuickDisplayPresenter` and `QuickDisplayVisualizerOwner`. That remains an ownership-order investigation,
not evidence of surviving GL resources. Do not fix it by lengthening the destruction-barrier timeout or forcing GC.

## GC freeze attribution

The 2026-10-07 loaded two-display RUN observed the existing one-shot freeze at 45 seconds: 145,142 tracked objects,
`freeze_boundary_ms=6.567` (freeze, threshold restoration and count observation). It is not a recurring timer or a standalone
explanation for >25 ms presentation holes in that run; no threshold/cadence change was admitted. Local source/argv/log/trace
evidence is retained under `logs/shared_runtime_acceptance/gc_freeze_20261007_140929/`. This all-diagnostics run does not close
the low-observer Bubble/DevCurve physical bar, and its process exit mismatch remains owned by the live retirement task.

## Intermittent exported-memoryview startup failure

### Symptom

Trace-enabled starts intermittently emitted:

```text
Exception ignored in tp_clear of: <class 'memoryview'>
...
BufferError: memoryview has 1 exported buffer
```

A native-fault capture also caught an access violation while CPython was garbage-collecting. The visible Python traceback moved
between PyOpenGL converter/list code, `json.decoder.raw_decode()` and unrelated worker activity. That migration is the key
negative control: the Python frame current when GC clears the problematic object is **not trustworthy ownership attribution**.

### Failed/overfit attribution

- Removing a `memoryview` chain from the binary frame-trace writer was worthwhile hygiene but did not close the symptom.
- A speculative `clip_host` direct-query repair followed one PyOpenGL-shaped crash surface; later failures moved elsewhere, so
  that crash-specific change was backed out. CHK26's independently accepted direct-query optimization remains untouched.
- Process killing/window broadcast was rejected as acceptance methodology because it bypasses SRPSS terminal ownership and can
  kill the GODZIP Foundry parent.

### Trigger isolated to observer pressure

Historically, plain `--frame-trace` was a bounded binary ring/writer and had been used repeatedly. N1e later attached
`GuiStallSampler` automatically. On a >40 ms GUI-wake gap it performed `sys._current_frames()` and formatted stacks for every
live Python thread, including during startup/reveal/terminal windows that the lifecycle contract already classifies as expected
noise. The supplied rolled-start evidence showed repeated all-thread snapshots while the interpreter was constructing and
retiring large object graphs.

The accepted correction restored diagnostic separation:

- plain `--frame-trace` creates only the low-observer binary trace;
- all-thread stack capture requires explicit `--gui-stall-stacks` in addition;
- the stack sampler disarms completely during lifecycle windows and re-arms from a fresh post-window wake;
- the frame-trace writer keeps owned-byte output rather than exported-memoryview chains;
- ordinary product runtime receives none of this diagnostic work.

This identifies **observer pressure as the reproducing trigger removed by the repair**. It does not claim the exact internal
CPython exported-buffer object was uniquely identified.

## Physical closure

The accepted unattended harness used SRPSS's RUN-owned bounded shutdown rather than external process control:

```powershell
python main_mc.py --debug --perf --usage --viz --geo --set --life --cache --steam --feeds --frame-trace --fresh --exit-after 15 /s
```

The command was run consecutively through the maintained 10-run wrapper. Result: **10 / 10 PASS**.

Across the accepted sequence:

- every process reached RUN/reveal and armed `--exit-after` only after engine start;
- no `memoryview.tp_clear`, exported-buffer `BufferError`, native access violation or startup abort was observed;
- each deadline entered normal `engine.stop(reason="cli_exit_after")` terminal retirement;
- image workers exited normally and ThreadManager shutdown completed;
- the binary trace drained with zero pending records, zero drops and zero write errors at each recorded close;
- Settings persistence closed cleanly and each process returned exit code 0;
- Qt/QML capture reported no warning/error/critical messages in the accepted runs.

Reopen this incident only if **plain** `--frame-trace` reproduces the failure again. If a future run with
`--gui-stall-stacks` fails while plain trace remains clean, treat that as a heavyweight-observer defect first, not a product
renderer defect.

## Durable tooling outcome

`--exit-after <seconds>` / `--exit-after=<seconds>` is retained as permanent test infrastructure. It arms one Qt one-shot only
for an explicitly requested RUN session and enters the normal terminal authority; it does not kill the process, add a recurring
scheduler or exist in ordinary runtime. See `Docs/Reference/Harness_Index.md`.
