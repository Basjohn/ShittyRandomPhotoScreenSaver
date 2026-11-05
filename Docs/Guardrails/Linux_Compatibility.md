# Linux Compatibility Guardrail

Binding rules that keep one SRPSS codebase working on Windows (the primary, accepted
product) and Linux. Live Linux work, gaps and merge notes are in [`Linux_Plan.md`](../../Linux_Plan.md);
how to run, build and test on Linux is in [Linux Guide](../Guides/Linux_Guide.md). This file holds only rules
that stay true.

## 1. Windows behaviour is the reference

- Linux support never changes Windows behaviour, resolution, defaults, timing or
  rendering. A shared-code change for Linux must leave the Windows branch
  byte-for-byte equivalent, or it is a Windows change and needs Windows evidence.
- Do not remove, weaken or "generalise away" a Windows mechanism (DWM, WinRT media,
  WASAPI loopback, secure-desktop helper, `.scr` modes) to make Linux simpler.
  Linux gets a parallel implementation behind the same owner, or the feature is
  explicitly unavailable there.

## 2. Platform selection

- Branch on `sys.platform == "win32"` (or `core.platform_paths.IS_WINDOWS` /
  `IS_LINUX`). Do not mix in `os.name`, `platform.system()` or ctypes-attribute
  sniffing for new code.
- **Every module must import on Linux.** Windows-only APIs (`ctypes.windll`,
  `winrt`, `pycaw`, `comtypes`, `pyaudiowpatch`, `winreg`, `win32*`, `msvcrt`) are
  imported lazily inside the Windows branch or behind a guarded import. Proof:
  the import sweep in `Linux_Plan.md` → Verification.
- Windows-only subsystems live under `core/windows/` (or are clearly named) and
  are never *called* on Linux. Their callers check the platform first.

- Linux backends talk to the system through CLI sidecars (`pactl`, `parec`) or D-Bus, never environment
  configuration. A sidecar's blocking stdout reader runs on a named ThreadManager worker
  (`core/media/sidecar_reader.py`); no raw threads, no polling cadence, and stop ends the process first.

- Credentials are protected only through `core/windows/dpapi.py` (DPAPI on Windows, the Secret Service
  keyring key on Linux). No plaintext credential write or read on any OS; without protection, nothing is saved.

## 3. Unavailable is loud, never a silent fallback

- When a feature has no Linux implementation, its owner reports it once at INFO or
  WARNING with a `[PLATFORM]` tag naming the feature, and the feature presents
  as unavailable. It must not pretend to succeed, return fake success, or quietly
  substitute different behaviour.
- A Windows API that *returns false/None* on Linux is acceptable only if its
  caller handles "unavailable" explicitly.

## 4. Paths

- `core/platform_paths.py` is the only reader of `%APPDATA%`, `%PROGRAMDATA%`,
  `%LOCALAPPDATA%` and the XDG base-directory variables. Every other path
  authority derives from it (settings store, data/cache root, logs, curated
  presets/themes/sounds). Never read those variables elsewhere, and never
  hard-code `C:\`, `AppData` or `ProgramData` outside Windows-only modules.
- Linux mapping: user roaming → `~/.config`, machine shared/curated →
  `~/.local/share`, user local → `~/.local/state` (absolute `XDG_*` values honoured).
- Open folders and URLs through Qt (`QDesktopServices`), not `explorer`,
  `os.startfile`, `cmd /c start` or PowerShell.

## 5. Dependencies

- `requirements.txt` is the single dependency authority for both systems.
  Windows-only distributions carry `; sys_platform == "win32"`; Linux-only ones
  carry `; sys_platform == "linux"`. Never add a second Linux requirements list.
- Pins stay identical across systems where a distribution exists on both.

## 6. Rendering

- The OpenGL 4.6 Core production floor (`rendering/quick/bootstrap.py`) applies on
  Linux unchanged. No GLES/4.5 renderer fallback.
- Headless Linux harnesses may give their child process Mesa's 4.6 version
  override for llvmpipe (`tools/linux_headless.py` owns it). That is a test-environment
  knob, never product configuration, and software-rendered runs are never
  performance, pacing or Windows evidence.

## 7. Tests

- Tests of a Linux branch or Linux-only backend live in `tests/test_linux_*.py`. Off Linux they are never
  run: `tools/impacted_tests.all_test_files()` (whole-suite and `--changed` selection) leaves them out and
  `tests/conftest.py` neither collects nor runs them (directory or explicit file). Never put a Linux-branch test
  in a shared file.
- Each Windows owner's platform selection ("Windows still constructs the Windows owner") is pinned in
  `tests/test_platform_selection.py`, which runs everywhere.
- Tests that pin a Windows contract select it explicitly: the `windows_platform`
  fixture for path roots, or `pytest.mark.skipif(sys.platform != "win32", ...)`
  when the test needs a real Windows API. Never delete or loosen the assertion to
  make Linux pass.
- Tests must not import Windows-only modules at collection time.
- `tests/conftest.py` isolates both the Windows variables and the XDG roots; a
  test run must never touch a real user profile on either system.
- Linux test runs go through `tools/linux_pytest.py` (display + GL floor confined
  to the child), so test commands carry no environment-variable writes.

## 8. Evidence limits

Linux CI/cloud evidence (Xvfb, llvmpipe) proves imports, lifecycle, settings,
correctness and rendered pixels. It does not prove real-GPU performance, vsync/pacing,
compositor (X11/Wayland) behaviour, multi-monitor/DPI hardware, real audio
devices or desktop integration. Those stay **Awaiting Validation** in `Linux_Plan.md`
until checked on a physical Linux machine.
