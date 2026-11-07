# GitHub Remote builds (Build Runner's third tab)

The two expensive Windows builds, **Standard + Diagnostic** (`SRPSS.scr`, one compile, also published as
`SRPSS_Diagnostic.scr`) and **Media Center** (`SRPSS_Media_Center.exe` and its one-dir payload), can compile on
GitHub's free Windows runners instead of this machine. Build Runner sends each one to GitHub, follows it, downloads
the result, validates it, puts it into `release\` exactly where a local build would, and can then compile the
installers locally. Nothing is virtualised or compiled locally for the remote products: no WSL, Docker or Hyper-V.

Owners: `tools/github_remote_build.py` (the remote contract, both sides), `.github/workflows/windows-build.yml` (the
runner job), `tools/build_runner.py` (the tab). Normal and Repo Venv are unchanged.

## One-time setup

1. Install the GitHub CLI: `winget install GitHub.cli` (Build Runner's pre-flight says so if it is missing).
2. Sign in once: `gh auth login` → GitHub.com → HTTPS → log in with a browser. The account needs write access to
   `Basjohn/ShittyRandomPhotoScreenSaver` (dispatching a workflow requires it). Check with `gh auth status`.
3. The workflow file must be on the default branch (`main`); GitHub only offers manual runs of workflows it lists
   there. It is committed on `main`, so this is already true.
4. The repository must allow GitHub's own actions (`checkout`, `setup-python`, `cache`, `upload-artifact`):
   Settings → Actions → General → Actions permissions → "Allow Basjohn, and select non-Basjohn, actions and reusable
   workflows" with **Allow actions created by GitHub** ticked. With "local actions only" every run ends at once in
   `startup_failure` (the first attempt, 8 Nov 2026); pre-flight now names this setting before dispatching, and a run
   GitHub refuses to start is reported with its link. The Linux workflow needs the same setting.

## Running a remote build

1. Commit and **push** what you want built. GitHub builds the pushed commit, never your working tree.
2. Open Build Runner (`python tools/build_runner.py`, or `--mode github`) and choose **GITHUB REMOTE**.
3. Read the pre-flight line. It names exactly what GitHub will build: `GitHub builds origin/main @ 1a2b3c4d: <subject>`.
   It warns when your local HEAD is not that commit (unpushed commits) or when you have uncommitted changes, which
   are not part of the remote build.
4. Tick **Standard + Diagnostic (GitHub)**, **Media Center (GitHub)** or both. Optionally tick **Reddit Helper
   (local)** (pre-selected when its fingerprint says it is stale) and the installers you want afterwards.
5. **START SELECTED.** Both selected products are dispatched at once and build in parallel on separate runners. Each
   row shows `Queued`, `Building`, `Downloading`, `Validating`, `Publishing`; the progress line shows the runner's
   current step, and a **GitHub run** link opens the run in your browser. While GitHub builds, the Reddit Helper (if
   selected) builds locally.
6. When a run succeeds its artifact is downloaded, validated and published; then the selected installers compile
   locally. A typical run takes about as long as a local build (the runner has 4 cores); your machine stays idle.

**EMERGENCY STOP** (or closing the window) cancels the real GitHub runs (`gh run cancel`), not just the local
monitoring, and stops any local step. Already published products stay published; an interrupted download keeps the
previous payload.

Headless (for scripts, or the lead when the operator asks for a build):

```
python tools/github_remote_build.py run --target standard --target media_center
```

Ctrl+C cancels the runs on GitHub. Installers are compiled from the Build Runner tab.

## What gets checked before anything is replaced

- **The commit.** The SHA is fixed at pre-flight and re-checked at START: if `origin/<branch>` moved meanwhile, nothing
  is dispatched (re-run pre-flight by switching tabs). The runner checks out that exact SHA, verifies it, and
  refuses to describe any other.
- **The build itself.** The runner runs the canonical worker (`scripts/venv/build_nuitka.ps1` or
  `scripts/venv/build_nuitka_mc_onedir.ps1`) with all of its own checks: defaults authority, QML source contract,
  QRC regeneration, product assets, runtime dependencies, the frozen module/source audit, the onefile payload and
  shader contracts, and its publication step. Nothing is skipped or weakened for remote builds.
- **The download** (into `build\github_remote\<token>\<product>\` first). `remote_build_manifest.json` must name the
  requested product, commit, version (read from that commit's `versioning.py`) and run token. Every payload and
  report file must match its recorded size and SHA-256; no unlisted file may be present; the diagnostic copy must
  be the same binary as `SRPSS.scr`; the primary binary's Windows product version must equal the version.
- **Publishing.** Only then are `release\screensaver` + `release\diagnostic` (Standard) or `release\media_center`
  swapped in. If a swap fails (for example a running `.scr` locks the folder) the previous payload is restored.
  A failed run, download or validation never touches `release\`.

## Where things land

| What | Where |
| --- | --- |
| Standard + Diagnostic | `release\screensaver\SRPSS.scr`, `release\diagnostic\SRPSS_Diagnostic.scr` |
| Media Center | `release\media_center\` (onedir, `SRPSS_Media_Center.exe`) |
| Installers (local) | `release\installers\Setup_SRPSS.exe`, `release\installers\Setup_SRPSS_Media_Center.exe` |
| Runner log per product | `logs\build_runner_<product>_<token>.log` (Log link: dispatch, run URL, status, validation; the failed steps' log tail on failure) |
| Worker reports from the runner | `logs\build_nuitka[_mc_onedir]_{,report_,footprint_,frozen_audit_}<token>.*` |
| Evidence bundle | `logs\build_evidence_<product>_*.zip` (Evidence ZIP link; same bundle as a local build) |
| The run on GitHub | the row's **GitHub run** link (artifacts expire after 3 days; failure logs after 7) |

## Installers (local, after download)

Installers are opt-in on this tab and compile with the same Inno Setup path and version stamping as the other tabs.
They are compiled only for a build that was downloaded **and validated in the same run**, and only when every
repository file the installer reads beside the payload equals the built commit in your working tree:

- Standard installer: `scripts\SRPSS_Installer.iss`, `scripts\reddit_helper_task_template.xml`, `SRPSS.ico`,
  `versioning.py`, `presets\visualizer_modes`, `themes`, `resources\tutuogg.ogg`, `resources\jedimodeyall.mp3`,
  `ui\assets\installer`, and the Reddit Helper's fingerprinted sources. It also needs a current Reddit Helper payload
  (`release\reddit_helper`): select **Reddit Helper (local)** when its badge says rebuild.
- Media Center installer: `scripts\SRPSS_MediaCenter_Installer.iss`, `SRPSS.ico`, `versioning.py`,
  `ui\assets\installer` (its presets, themes and sounds come from the downloaded payload).

Build Runner's own version stamp on the `.iss` files is not a difference. Anything else (an uncommitted preset or
theme, a different `versioning.py`) blocks that installer with the list of differing files, so a remote payload is
never packaged with another revision's assets. Commit and push them, or revert them, and run again.

## Limitations

- GitHub builds pushed commits only. Uncommitted work needs a commit and push first (a local build covers it).
- The runner's toolchain is GitHub's `windows-2025` image (Visual Studio 2022 MSVC) with Python 3.14 from
  `actions/setup-python`, not this machine's Build Tools; the requirement pins and Nuitka version are identical.
- The repository is public: its Actions minutes on standard runners are free, and run logs and artifacts are
  visible to signed-in GitHub users until they expire (3 days; failure logs 7).
- Each run reinstalls `requirements.txt` into a fresh `.venv`; Nuitka's compile cache is kept between runs.
- No installer is compiled on GitHub, and Linux keeps its own job (`Docs/Guides/Linux_Guide.md` §7).
- Physical acceptance (installing and running the products) is still the operator's.
