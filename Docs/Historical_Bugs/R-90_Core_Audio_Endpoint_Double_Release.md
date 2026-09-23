# R-90 — Core Audio Endpoint Released Twice (ctypes.cast Shared A COM Pointer)

Date: 2026-09-23  
Status: SOLVED — `50052050`; closed 2026-09-23 by a native test on the real endpoint

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

An access violation on the GUI thread during replacement construction (a Settings-style round trip), and the
exit segfault of `tests/test_s_hotkey_workflow.py`. Found while gating the runtime audit.

## Root Cause

`CoreAudioCallbackProbe` obtained `IAudioEndpointVolume` with `ctypes.cast(interface, POINTER(...))`. `cast`
shares the raw COM pointer **without AddRef** and stores the source in the result's `_objects`, forming a
ctypes reference cycle. Rebinding/retiring the endpoint released the object; the cyclic original was released
again at the next garbage collection.

## Why It Was Hard To Find

The second release happened at an arbitrary later GC, on whatever code was running. The fake Core Audio test
fixture stubbed `ctypes.cast` as identity, so tests could never see it.

## Fix

`interface.QueryInterface(IAudioEndpointVolume)`: each Python pointer owns its own reference. The fixture no
longer stubs `cast` (it now fails if used) and a bar asserts `QueryInterface`.

## Regression Coverage

`tests/test_core_audio_callback_probe.py` with the de-stubbed fixture; `tests/test_s_hotkey_workflow.py` exits cleanly;
`tests/test_core_audio_native_rebind.py` drives the real endpoint through 25 rebinds (the default-output-device path),
retirement and garbage collection in a subprocess, and fails on the old `ctypes.cast` code. The 2026-09-23 19:29 run's
two Settings replacements recorded no native fault.

## Guardrail

Never `ctypes.cast` between COM interface pointers; use `QueryInterface`. Test fakes must not stub away the
reference-ownership behaviour under test.
