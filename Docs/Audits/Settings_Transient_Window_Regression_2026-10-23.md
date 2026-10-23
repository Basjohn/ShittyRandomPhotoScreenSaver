# Settings transient-window regression after single-active bucket repair (23 October 2026)

**Status: [~] REAL OPERATOR-REPORTED REGRESSION, SOURCE MITIGATION CANDIDATE, NATIVE WINDOWS VERIFICATION REQUIRED.** [Live task](../../Current_Plan.md) | [Persistence repair](Settings_Bucket_Persistence_Repair_Candidate_2026-10-23.md) | [Historical R-18](../Historical_Bugs/R-18_Settings_Dialog_Taskbar_Ghost.md).

## Observation and source mechanism

After the October 23 single-active bucket persistence godzip, the operator reports a tiny window flashing roughly three times as the Settings dialog opens. This is not a hypothetical polish item: it is a real operator-observed regression. Do **not** call it visually fixed without native evidence.

Source review found a concrete exposure path in the shared Qt Widgets `build_bucket_toggle()` factory: it constructs `body = BucketTreeBody()` **without a QWidget parent**, then, when initially expanded and not deferred, calls `body.setVisible(True)` **before** passing it to `host_layout.addWidget(body)`. Qt can expose this as a temporary top-level native window. The new persistence scheme makes opening/restoring more context-dependent and may have made this older hazardous ordering reachable again. This is a plausible mechanism, **not proven from an HWND trace here**. Do not assume that each observed flash corresponds to one body.

The earlier R-18 Settings dialog taskbar ghost was actually attributed to a different constructor-time visibility call on `VisualizerPresetSlider`'s edit button. Its retained harness `tools/flicker_test.py` and external Windows observer `tools/winprobe_observer.py` are still useful to distinguish these mechanisms, but the R-18 cause must not simply be copied onto the new recurrence.

## Bounded fix candidate

In `ui/tabs/shared_styles.py::build_bucket_toggle`, create the new `BucketTreeBody` hidden, add it to its actual parent layout, and only then explicitly reveal it if (a) the bucket is initially expanded, (b) deferred initialization was not requested, and (c) Qt confirms it has a `parentWidget()`. Do not show detached widgets or add a timer/extra window. Preserve the existing deferred/finalize behavior, bucket nesting, rails, signal wiring, theme and persisted expanded state. This source candidate addresses the known unparented-body exposure path, not necessarily every transient-window source.

## Native agent falsifiers (not an operator-only task)

1. Run the existing Windows flicker harness full Settings profile (variants 13/17 and relevant targeted variants) with `winprobe_observer.py` (or equivalently instrument HWND creation within the process). Inspect **all** short-lived top-level windows, `Qt*QWindowIcon` or otherwise; compare before/after at identical saved Settings context. No environment-variable setup or overrides in tests.
2. Repeat Settings cold open, close/reopen, initial Sources, Widgets→Steam nested buckets, Visualizer→EB Custom/Technical, and lazy Transitions. Compare expanded versus all-closed initial state. Verify exactly one dialog HWND and no undesired temporary top-level HWNDs.
3. Verify that an initially expanded bucket becomes visible after construction, that a deliberately deferred bucket stays hidden until `finalize_bucket_body()`, and that no pre-parent exposure occurs. Use `tests/test_settings_bucket_tree.py::test_initially_open_bucket_is_parented_before_any_show` and source guard `tests/test_settings_bucket_single_open_contract.py::test_shared_bucket_builder_does_not_expose_unparented_widgets`.
4. Check collapse/reopen/nested rails and one-active editing path; ensure no settings values, authored presets, focus or performance were changed. Agent should collect native evidence and mark this fixed only when the flash is absent. Operator confirmation is helpful but **not a substitute** for achievable automated/native validation.

## 2026-10-24 native result (Windows, PySide6)

`tools/settings_window_probe.py` (out-of-context WinEvent hook; its self-test records a deliberately flashed
unparented QWidget) found **zero** top-level windows besides the dialog in: two direct opens visiting all ten tabs;
three reopens with Widgets → Backend expanded and remembered; the same reopen with the pre-candidate ordering
restored; a real `main.py /c` launch (one show: the dialog); and two canonical in-saver MC Settings cycles
(display window + dialog only). Temporary instrumentation recorded 28 bucket builds, all with a parented host
layout and none built expanded: remembered buckets restore after construction. The audited mechanism is
therefore not reachable from saved state; the candidate remains correct hardening, and the observed flash is
unreproduced and unattributed. Receipt: `logs/run_matrix/2026-10-24_settings_transient_windows/receipt.json`.

**Environment limitation (original Linux audit):** PySide6 and Windows native HWND observation are unavailable in this Linux/container audit. Source/static tests can be run here; native behavior remains open.
