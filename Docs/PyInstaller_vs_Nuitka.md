# PyInstaller vs Nuitka for SRPSS

This note captures trade-offs so we can revisit the bundler choice later.

## Current setup

- **Bundler:** PyInstaller
- **Script:** `scripts/build.ps1`
- **Mode:** `--onefile`, `--noconfirm`, `--clean`, `--noconsole`
- **Resources:** `--collect-all PySide6`, `--collect-all PIL`, `--collect-all certifi`
- **Version source:** `versioning.py` (`APP_VERSION`)

Result: a single `SRPSS.exe` in `/release`, suitable to rename as `.scr` for Windows screensaver registration.

## PyInstaller onefile

### Pros

- Already integrated and working in this repo.
- Good support for PySide6/Qt on Windows.
- Onefile output matches screensaver requirement (single binary).
- Script avoids UPX by default (more AV-friendly).
- Simple to maintain; build script auto-installs PyInstaller when missing.

### Cons

- Onefile mode self-extracts to a temp dir at runtime:
  - Extra I/O and startup overhead vs onedir or a native binary.
- PyInstaller stubs are widely recognized by AV engines:
  - Generally OK but occasionally trigger heuristic warnings on some vendors.

## Nuitka single-file

### Pros

- Ahead-of-time C compilation:
  - Potentially faster startup and lower interpreter overhead.
  - May look more like a native binary to AV heuristics.
- Can be tuned for optimization (LTO, module-level options).

### Cons

- More complex toolchain:
  - Requires a C compiler on Windows (MSVC/MinGW).
  - Needs explicit plugin/config for PySide6 and resources.
- Single-file mode still uses a loader; setup/debugging is more involved.
- No existing build script in this repo; would require a new `build_nuitka.ps1` and experimentation.

## Recommendation (for now)

- Keep **PyInstaller onefile** as the primary, supported build path.
- Consider adding a **secondary Nuitka build** later if we hit:
  - Real-world AV false positives on the shipped `.scr`, or
  - Noticeable startup performance issues.

### Possible future steps

- Add `build_nuitka.ps1` mirroring `build.ps1` for A/B testing.
- Embed version metadata into the Windows PE for both build paths.
- Optionally experiment with PyInstaller `--onedir` for internal testing (but final screensaver must remain single-file).
