# R-226 | A failed native harness child could reuse a successful JSON result

**Owner:** `native/core/python/*_check.py` parent launchers and their verdicts.
Found during the P1 retirement audit, 16 Nov 2026. This was a silent validation defect, not a renderer failure.

The harness kept a deterministic `child_<api>.json` path. It neither removed an older record before launching a
child nor made a failed exit/timeout override that record's successful rounds. A reused evidence label and a
crashed or stalled child could therefore produce PASS without completing the current proof.

The actual negative reproduction loaded both harnesses from pre-fix commit `126c5c82a`, seeded a successful
`child_opengl.json`, and replaced only the subprocess call with `TimeoutExpired`. No window or GPU was used.
Both printed their PASS verdict while the summary recorded `exit_code: "timeout"`.

The parents now unlink the child record before each launch. The shared verdict independently rejects every
nonzero exit and timeout, even if the current child wrote successful JSON before failing. The JSON remains useful
diagnostic evidence but cannot overrule process failure.

The caller sweep covers timer, spectrum, generic mode, devcurve, fullscreen pass, job service, background layer,
backdrop pyramid, transition route, compute pass and post-stage harnesses. Compute and post-stage reference
verdicts also reject failed processes, independently of the shared native verdict.

Regression bar: `tests/test_native_core_host.py::test_native_harness_never_accepts_stale_or_failed_child_success`,
parameterized across both harnesses and timeout/nonzero exit. `tests/test_native_harness_child_results.py` applies
the same controls to the caller sweep and reference verdicts. Each seeds stale success, requires its removal before
launch, writes another success during the failed call, and requires FAIL. The pre-fix versions fail at the stale
record assertion. The focused host/composite gate passes all 99 tests after repair.

Lesson: a proof record belongs to one successful execution. File presence and successful checks cannot establish
that execution when its process failed.
