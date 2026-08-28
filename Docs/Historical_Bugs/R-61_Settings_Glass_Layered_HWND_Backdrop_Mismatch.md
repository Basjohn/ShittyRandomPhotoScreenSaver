# R-61 — Settings Glass Used The Wrong Composition Family For A Layered QWidget

Date: 2026-08-28
Status: Solved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

Schema-v5 Settings themes introduced separate Acrylic and Glass product modes. Acrylic could render correctly on a fresh persisted startup, while Glass could start with no visible native material. A later theme application could make Glass appear. DWM calls could report success and read back the requested system-backdrop state even when the visual material was absent.

This distinction became decisive after transition cleanup restored the original Acrylic primitive: persisted Acrylic was reliable on first show, while persisted Glass alone retained the startup failure.

## Investigation Evidence

Native diagnostics proved the Settings HWND remained `WS_EX_LAYERED` for its lifetime. The top-level Settings widget uses Qt `WA_TranslucentBackground`, so this is the actual presentation architecture that the native material must coexist with.

The initial Glass implementation used the Windows 11 system-backdrop family:

```text
DWMWA_SYSTEMBACKDROP_TYPE = DWMSBT_TRANSIENTWINDOW
+ experimental DWMWA_REDIRECTIONBITMAP_ALPHA handling
```

Successful DWM HRESULT/readback state did not correlate with a successfully composed first-start Glass visual. The bug therefore could not be treated as a failed API write.

Several proposed lifecycle explanations were falsified or rejected:

- a zero-delay/post-show native reassert could wake the visual but was a retry workaround, not ownership repair;
- replaying QSS after native setup was rejected as sequencing folklore rather than root cause;
- a QWindow Expose-bound application produced the same failure;
- moving attention to `DWMWA_REDIRECTIONBITMAP_ALPHA` did not establish a valid bridge to Qt's layered presentation;
- replacing Glass with near-clear AccentPolicy **Acrylic state 4** made every Glass theme render as pure black.

## Root Cause

The Glass implementation had crossed composition families on a window whose presentation model was already fixed by Qt.

Acrylic used `SetWindowCompositionAttribute` AccentPolicy and was healthy on the layered Settings HWND. Glass instead requested DWM's system/redirection-backdrop material. Treating those as interchangeable ways to place blur under the same layered QWidget was the architectural mistake.

The correct Glass primitive for this existing Settings architecture is the AccentPolicy blur state on the same mechanism already proven by Acrylic.

A critical terminology trap prolonged the investigation: `ACCENT_ENABLE_BLURBEHIND` is an undocumented **AccentPolicy state used through `SetWindowCompositionAttribute`**. It is not the documented `DwmEnableBlurBehindWindow` API. Documentation describing Windows 8+ behavior of the latter does not describe the former.

## Fix

Both product materials now stay on one AccentPolicy composition family:

```text
Acrylic
    ACCENT_ENABLE_ACRYLICBLURBEHIND (state 4)
    + theme native tint / strength

Glass
    ACCENT_ENABLE_BLURBEHIND (state 3)
    + zeroed AccentPolicy (no native tint)
    + semantic Qt RGBA surfaces own visible tint / opacity

Off
    ACCENT_DISABLED (state 0)
```

`DWMWA_SYSTEMBACKDROP_TYPE`, `DWMSBT_TRANSIENTWINDOW`, the redirection-bitmap-alpha experiment and associated build/system-backdrop machinery were removed from the Settings Glass path.

Native mode ownership was kept clean: Glass-to-Glass does not reinstall an invariant primitive, Acrylic-to-Acrylic only needs to update its native tint when required, cross-material changes replace the AccentPolicy state directly, and Off disables it.

## Runtime Validation

Physical Windows testing of the landed fix established all three acceptance points:

- a persisted Glass theme shows blur immediately on a fresh Settings startup without a retry/theme switch;
- persisted Acrylic remains healthy on fresh startup;
- Glass is materially visually different from Acrylic, with Glass palette/opacity differences supplied by the semantic Qt layers rather than a hidden native Glass tint.

The accepted implementation was committed at `cdb2a0f83a98dfd9244cedc46d8d641afc8adc8f`.

## Guardrail

Do not reintroduce DWM system-backdrop/redirection-bitmap machinery to the current layered Settings top-level as an incremental Glass tweak. Such a design requires an intentional window/presentation architecture change and new physical proof.

Do not repair native material activation with timers, duplicate DWM calls, QSS replay or theme-toggle side effects.

Keep the product distinction explicit: Acrylic is state-4 native tinted Acrylic; Glass is untinted state-3 AccentPolicy blur plus semantic Qt surface composition.
