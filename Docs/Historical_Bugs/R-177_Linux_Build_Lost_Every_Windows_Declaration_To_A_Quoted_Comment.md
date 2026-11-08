# R-177 | The Linux build lost every Windows Nuitka declaration to an apostrophe in a comment (no presets shipped)

**Status:** fixed 8 Nov 2026 (`fa62ef14`): `tools/linux_build.py` `_strip_ps1_comments`. Regression bar:
`tests/test_build_linux_declarations.py`, which runs on every platform (the old reader finds 1 of the declarations on
today's script). Proven by a GitHub Linux run at the fixed commit: build, smoke test and download green; the tarball
holds 70 presets, 215 themes, both sounds and both `.rcc` packs.

## Symptom

The operator's Linux build from Build Runner failed in the runner's smoke test:
`cp: cannot stat '.../SRPSS-5.1.2-linux-x86_64/presets/visualizer_modes': No such file or directory`, from the
bundled `install.sh` (run 42446955550, commit `3698eb67`). The Nuitka build itself succeeded.

## Cause

The Linux build has no Nuitka option list of its own: `portable_windows_arguments()` reads the quoted `--...` values
out of `scripts/venv/build_nuitka.ps1`'s `$argsList` with a regex that pairs quotes. On 8 Nov a comment was added inside
that list for the GitHub Remote fix ("...Nuitka's one-time Dependency Walker download prompt, whose non-interactive
default "no" is a FATAL..."). Its apostrophe and quotes shifted every later pair, so the reader returned **0 of 29**
declarations: no presets, themes, sounds, `.rcc` packs, packages or Qt plugins. The Linux product built anyway (Nuitka
follows imports), and only `install.sh`'s copy of the presets noticed.

## Why it hid

The extraction tests lived in `tests/test_linux_build.py`. Every `tests/test_linux_*.py` is Linux-only and never
collected on Windows, but the scripts they check are edited on Windows: the test that would have failed at once never
ran where the change was made.

## Fix

- Comments (`<# ... #>` blocks and `#` to the end of a line outside quotes) are stripped before the quoted values are
  read, for the Windows argument list and the Qt size exclusions.
- The platform-neutral text tests moved to `tests/test_build_linux_declarations.py` (every platform), with a synthetic
  script whose comments contain apostrophes and quotes, and a check that every `--...` literal on a code line of the
  Windows list is either read or deliberately filtered.
- With it, Build Runner's GitHub Remote tab gained the Linux job, building the pre-flight's pinned commit
  (`linux-build.yml` `commit`/`token` inputs, verified after checkout).

## Lessons

1. A test that checks a file must run on the platform where that file is edited; a platform prefix belongs to tests
   that need the platform, not to tests about it.
2. A text extractor over source in another language must understand that language's comments and strings, or be
   replaced by a declared data file both builds read.
3. "The build succeeded" proves nothing about payload: the smoke test's install step was the only real gate.
