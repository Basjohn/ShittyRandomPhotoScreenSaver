# GitHub Remote builds (Build Runner's third tab)

The two expensive Windows builds, **Standard + Diagnostic** (`SRPSS.scr`, one compile, also published as
`SRPSS_Diagnostic.scr`) and **Media Center** (`SRPSS_Media_Center.exe` and its one-dir payload), can compile on
GitHub's free Windows runners instead of this machine. Build Runner sends each one to GitHub, follows it, downloads
the result, validates it, puts it into `release\` exactly where a local build would, and can then compile the
installers locally. Nothing is virtualised or compiled locally for the remote products: no WSL, Docker or Hyper-V.

Owners: `tools/github_remote_build.py` (the remote contract, both sides), `.github/workflows/windows-build.yml` (the
runner job), `tools/build_runner.py` (the tab). Normal and Repo Venv are unchanged. The native module has its own
workflow on the same contract (section "The native module").

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
2. Open Build Runner (`python tools/build_runner.py`, or `--mode github`) and choose **GITHUB REMOTE**. (`--debug`
   prints the window's DPI awareness mode as it opens; Build Runner reads no environment variable flags.)
3. Read the pre-flight line. It names exactly what GitHub will build: `GitHub builds origin/main @ 1a2b3c4d: <subject>`.
   It warns when your local HEAD is not that commit (unpushed commits) or when you have uncommitted changes, which
   are not part of the remote build.
4. Tick **Standard + Diagnostic (GitHub)**, **Media Center (GitHub)** or both. **Reddit Helper (local)** is
   pre-selected when its fingerprint says it is stale, and the two installers are pre-selected as on the venv tab;
   optionally tick **Linux (GitHub runner)**, **Linux Media Center (GitHub runner)**, or both.
5. **START SELECTED.** Both selected products are dispatched at once and build in parallel on separate runners. Each
   row shows `Queued`, `Building`, `Downloading`, `Validating`, `Publishing`; the progress line shows the runner's
   current step, and a **GitHub run** link opens the run in your browser. Each selected Linux profile also starts
   a separate Ubuntu run on the same pinned commit and downloads its separately named tarball into `release\linux`
   (`Docs/Guides/Linux_Guide.md` §7). Their local monitoring runs independently from the Windows pipeline. While
   GitHub builds, the Reddit
   Helper (if selected) builds locally.
6. When a Windows run succeeds its artifact is downloaded, validated and published; then the selected installers
   compile locally. None of this waits for the Linux run: it has its own process owner on its own thread, so a
   Windows product is published (or its failure reported) as soon as its run ends. The pipeline reports done once all
   selected Linux builds have ended too. A typical run takes about as long as a local build (the runner has 4 cores); your
   machine stays idle.

**EMERGENCY STOP** (or closing the window) cancels the real GitHub runs (`gh run cancel`, both Linux profiles included),
not just the local monitoring, and stops any local step. The Linux job's process owner follows the pipeline's, so one
stop ends both. A Linux job stopped before it began following its run still cancels it: the run is found by the run
token its log names (or, for a temporary `linux-build/*` tag, by the tag, which is also deleted). Already published
products stay published; an interrupted download keeps the previous payload.

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

## Installers (local)

The installers are local jobs, exactly the venv tab's own: the same Inno Setup path (`ISCC.exe` from the Inno Setup 7
then 6 install folders, else PATH; `--iscc <path>` on `tools/build_runner.py` is the only override, no environment
variable) and version stamping, compiling
whatever `release\` holds (operator, 8 Nov: "It's supposed to be local, github has no say"). On this tab they run after
this run's GitHub products are published when those are selected, and straight away when they are not (for example
after an earlier GitHub run or a headless `tools/github_remote_build.py run`). Like the venv tab, an installer is
compiled even when its product's build failed in the same run: it packages the previous payload, which a failed
retrieval leaves in place. The Standard installer packages `release\reddit_helper` as it is: select **Reddit Helper
(local)** when its badge says rebuild.

## The native module (job `native_module`)

The native module (`native/spike_p1` today, the native core later; `Current_Plan.md` item 8b, N0.9) is compiled only
on GitHub (operator, 12 Nov 2026: builds happen only through GitHub workflows, never on this machine). It is a target
of the same contract as the products: `.github/workflows/native-module.yml` compiles it, `tools/github_remote_build.py`
dispatches, follows, cancels, downloads and validates it, and **Native Module (GitHub)** on this tab (job key
`native_module`) runs it. It is never pre-selected and no installer packages it (until N2.1 folds it into the product
builds, which will call the same workflow as a job: it is a reusable `workflow_call` workflow).

**The lead's command** (agents never start it, nor any other build):

```
F:\Programming\Apps\ShittyRandomPhotoScreenSaver\.venv\Scripts\python.exe <checkout>\tools\build_runner.py --mode github --run --select native_module
```

`<checkout>` is the checkout whose `release\` should receive the module: the main checkout, or an agent's worktree
(see below). The same run is `python tools/github_remote_build.py run --target native_module` without the Build
Runner pre-flight, or the tab's checkbox in the window.

**What the runner does** (`windows-2025`, about the products' toolchain): checks out the exact pushed SHA and verifies
it; reads the Qt version, which is one value: `requirements.txt`'s `PySide6==x.y.z` pin
(`tools/native_sdk_fetch.py --print-qt-version`; CMake's guard reads the same pin); creates the repo `.venv` from
`requirements.txt` (PySide6: `qsb.exe` and the Qt DLLs the module binds to); creates a tool venv from
`native/tool_requirements.txt` (ninja, py7zr); fetches that Qt's SDK with `tools/native_sdk_fetch.py` (its entry in
`QT_SDKS`: the msvc2022_64 qtbase and qtdeclarative archives and the Vulkan-Headers release, each checked against its
pinned and published sha256 before anything is extracted; cached per Qt version and script hash); runs
`native/spike_p1/build.cmd`, the one CMake invocation (MSVC found with `vswhere`, Ninja, Release, Qt Quick part on);
runs `native/spike_p1/python/import_check.py` (the import, `runtime_info()`, the Qt DLLs loaded from PySide6's
folder: the GPU-free part; every rendering part of the spike needs a GPU device, which the runner does not have);
then stages and uploads.

**What is checked before `release\native_module` is replaced:** the local HEAD must be the pushed commit (an unpushed
or diverged HEAD makes the row unavailable at pre-flight and is refused at START; the products, by contrast, build
the pushed tip and warn). The download must name the requested commit, version and run token like a product, plus
the Qt that the built commit's `requirements.txt` pins, the PySide6 release of that Qt and an MSVC version; the `.pyd`
and at least one
baked shader must be listed; every listed file must match its size and SHA-256 and no unlisted file may be present.
Only then is `release\native_module` swapped (a locked `.pyd`, for example a Python process that imported it, makes
the swap fail and the previous module is restored).

| What | Where |
| --- | --- |
| The module | `release\native_module\_srpss_native_spike.pyd`, `release\native_module\shaders\*.qsb` |
| What it was built from and with | `release\native_module\remote_build_manifest.json` (commit, version, Qt, PySide6, MSVC, sha256 per file) |
| Runner log | `logs\build_runner_native_module_<token>.log` |
| The runner's build log and import check | `logs\native_module_build_<token>.log`, `logs\native_module_import_<token>.json` |
| Evidence bundle | `logs\build_evidence_native_module_<token>.zip` |
| A failed run | the run's `srpss-native_module-failure-logs` artifact (the logs, CMake's cache and configure log) |

**How a C++ slice iterates** (the agent never pushes or builds; the lead does both):

1. The agent commits its slice in its worktree (its branch is `worktree-agent-<id>`), says so in its journal and asks
   the lead for a module build.
2. The lead pushes that branch from the main checkout: `git push origin worktree-agent-<id>` (any work-branch name
   works; GitHub runs the branch's own copy of the workflow, so the branch must contain `native-module.yml`).
3. The lead runs the command above with `<checkout>` = the agent's worktree, so the validated module lands in that
   worktree's `release\native_module\` (ignored by git). Pre-flight refuses when the worktree's HEAD is not the pushed
   commit.
4. The agent tests it from there, offscreen and hidden only:
   `python native/spike_p1/python/run_spike.py --module-dir release/native_module --part all --label <label>`.
5. A failed compile: the row's log names the GitHub run; the failure-logs artifact has the compiler output.
   The next attempt is a new commit, push and run.

The time from dispatch to download is recorded by the lead at N0.9's end-to-end proof; it sets how C++ slices
iterate.

One-time setup beyond the products': `native-module.yml` must be on `main` before GitHub lists it (pre-flight warns
and marks only this row unavailable until then).

Qt upgrades (decision D11, between stages, by the lead): add the version's entry to `QT_SDKS` in
`tools/native_sdk_fetch.py` (from `download.qt.io/online/qtsdkrepository/windows_x86/desktop/qt6_<xyz>/
qt6_<xyz>_msvc2022_64/qt.qt6.<xyz>.win64_msvc2022_64/`: the qtbase and qtdeclarative archive names, their published
`.sha256` and their sizes from the `.mirrorlist` page; the Vulkan-Headers release from `VULKAN_HEADERS`), then change
the PySide6 pins in `requirements.txt`. Nothing else names the version: the workflow, CMake's guard and the manifest
check all read the pin, and a pin with no entry is refused (`tests/test_native_sdk_fetch.py` holds this). The cache key
changes with the version, so the next run fetches the new SDK. Older entries stay in the table as history.

## Limitations

- GitHub builds pushed commits only. Uncommitted work needs a commit and push first (the operator's local build covers it; the lead never builds locally).
- The runner's toolchain is GitHub's `windows-2025` image (Visual Studio 2022 MSVC) with Python 3.14 from
  `actions/setup-python`, not this machine's Build Tools; the requirement pins and Nuitka version are identical.
- The Linux Media Center artifact uses `srpss-linux-mc` and publishes `SRPSS-<version>-linux-mc-x86_64.tar.gz`;
  Linux Screensaver retains `srpss-linux` and `SRPSS-<version>-linux-x86_64.tar.gz`. Both are smoke-tested in Xvfb;
  a full frozen build on GitHub and physical Linux acceptance are still required after this change.
- The repository is public: its Actions minutes on standard runners are free, and run logs and artifacts are
  visible to signed-in GitHub users until they expire (3 days; failure logs 7).
- Each run reinstalls `requirements.txt` into a fresh `.venv`; Nuitka's compile cache is kept between runs.
- No installer is compiled on GitHub; the lead's installers are the Build Runner's Inno step over the downloaded payloads, and the operator may compile them locally too. The Linux job is the other tabs' own (`Docs/Guides/Linux_Guide.md` §7); here it
  builds the pre-flight's commit, and its tarball is downloaded as is (no manifest validation like the Windows
  products; the runner's smoke test is its gate). Only this tab's Linux dispatch sends the workflow's `commit` and
  `token` inputs (`-Commit`): GitHub refuses inputs a branch's `linux-build.yml` does not declare (HTTP 422), so the
  other tabs keep the plain dispatch and find their run by commit and start time, and an older branch still builds
  there. On this tab a branch whose `linux-build.yml` predates the inputs fails its Linux dispatch (one cut before
  8 Nov has no Windows workflow either).
- Physical acceptance (installing and running the products) is still the operator's.
