# GitHub Remote builds (Build Runner's third tab)

The two expensive Windows builds, **Standard + Diagnostic** (`SRPSS.scr`, one compile, also published as
`SRPSS_Diagnostic.scr`) and **Media Center** (`SRPSS_Media_Center.exe` and its one-dir payload), can compile on
GitHub's free Windows runners instead of this machine. Build Runner sends each one to GitHub, follows it, downloads
the result, validates it, puts it into `release\` exactly where a local build would, and can then compile the
installers locally. Nothing is virtualised or compiled locally for the remote products: no WSL, Docker or Hyper-V.

Owners: `tools/github_remote_build.py` (the remote contract, both sides), `.github/workflows/windows-build.yml` (the
runner job), `tools/build_runner.py` (the tab). Normal and Repo Venv are unchanged. The native modules (the product's
native core and the P1 harness) have their own workflow on the same contract (section "The native modules").

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

## The native modules (jobs `native_module` and `native_spike`)

Two native modules are compiled only on GitHub (operator, 12 Nov 2026: builds happen only through GitHub workflows,
never on this machine), both by one workflow, `.github/workflows/native-module.yml`, whose `source` input names the
folder (`Current_Plan.md` item 8b, N0.9 and N2.1):

| Job key | Source | Module | What it is |
| --- | --- | --- | --- |
| `native_module` | `native/core` (the workflow's default source) | `_srpss_native_core.pyd` | the product's native core (D5.7); imported only by `rendering/native/` |
| `native_spike` | `native/spike_p1` | `_srpss_native_spike.pyd` | the P1 harness (the N0.6 and N0.7 rounds); never ships |

Each is a target of the same contract as the products: the workflow compiles it, `tools/github_remote_build.py`
dispatches (with `source=<folder>`), follows, cancels, downloads and validates it, and **Native Core Module (GitHub)**
and **Native Spike Harness (GitHub)** on this tab run them. Neither is pre-selected and no installer packages either.
The workflow is reusable (`workflow_call`), so the product builds can call it as a job.

**The lead's commands** (agents never start them, nor any other build):

```
F:\Programming\Apps\ShittyRandomPhotoScreenSaver\.venv\Scripts\python.exe <checkout>\tools\build_runner.py --mode github --run --select native_module
F:\Programming\Apps\ShittyRandomPhotoScreenSaver\.venv\Scripts\python.exe <checkout>\tools\build_runner.py --mode github --run --select native_spike
```

(`--select native_module native_spike` builds both, as two runs in parallel.) `<checkout>` is the checkout whose
`release\` should receive the module: the main checkout, or an agent's worktree (see below). The same runs are
`python tools/github_remote_build.py run --target native_module` (or `--target native_spike`) without the Build Runner
pre-flight, or the tab's checkboxes in the window. Until 12 Nov 2026 the spike was the job `native_module` and landed
in `release\native_module\`; it is now `native_spike` in `release\native_spike\`, and the N0.6/N0.7 drivers say so.

**What the runner does** (`windows-2025`, about the products' toolchain): checks out the exact pushed SHA and verifies
it; resolves the source's target (`tools/github_remote_build.py native-target --source <folder>`, refused for a folder
no target builds, and checked against the target the run was named for, which Build Runner looks it up by); reads the
Qt version, which is one value: `requirements.txt`'s `PySide6==x.y.z` pin (`tools/native_sdk_fetch.py
--print-qt-version`; each source's CMake guard reads the same pin); creates the repo `.venv` from `requirements.txt`
(PySide6: `qsb.exe` and the Qt DLLs the module binds to); creates a tool venv from `native/tool_requirements.txt`
(ninja, py7zr); fetches that Qt's SDK with `tools/native_sdk_fetch.py` (its entry in `QT_SDKS`: the msvc2022_64 qtbase
and qtdeclarative archives and the Vulkan-Headers release, each checked against its pinned and published sha256 before
anything is extracted; cached per Qt version and script hash); runs `<source>\build.cmd`, the one CMake invocation
(every source takes the same four arguments; MSVC found with `vswhere`, Ninja, Release, Qt Quick part on); runs
`<source>\python\import_check.py`, the GPU-free part (the runner has no GPU device): for the core it loads the module
through `rendering.native` (the exact-Qt guard, the Qt and ABI checks, the MSVC runtime origin check of
`rendering/native/runtime_check.py`: no `msvcp140` import, the loaded `vcruntime140` copies at least as new as the
compiler) and checks the Qt DLLs came from PySide6's folder; for the spike, the import, `runtime_info()` and the Qt
DLLs' origin. Then it stages (refused when the module, or a baked shader for any shader source in `<source>\shaders\`,
is missing) and uploads.

**What is checked before `release\<job key>` is replaced:** the local HEAD must be the pushed commit (an unpushed or
diverged HEAD makes the rows unavailable at pre-flight and is refused at START; the products, by contrast, build the
pushed tip and warn). The download must name the requested commit, version and run token like a product, plus its
source folder, the Qt that the built commit's `requirements.txt` pins, the PySide6 release of that Qt and an MSVC
version; the `.pyd` must be listed, and exactly one baked shader per shader source the built commit has in
`<source>\shaders\` (read with `git ls-tree` at that commit; the core has none yet); every listed file must match its
size and SHA-256 and no unlisted file may be present. Only then is `release\<job key>` swapped (a locked `.pyd`, for
example a Python process that imported it, makes the swap fail and the previous module is restored).

| What | Where |
| --- | --- |
| The module | `release\native_module\_srpss_native_core.pyd`; `release\native_spike\_srpss_native_spike.pyd` and its `shaders\*.qsb` |
| What it was built from and with | `release\<job key>\remote_build_manifest.json` (source, commit, version, Qt, PySide6, MSVC, sha256 per file) |
| Runner log | `logs\build_runner_<job key>_<token>.log` |
| The runner's build log and import check | `logs\<job key>_build_<token>.log`, `logs\<job key>_import_<token>.json` |
| Evidence bundle | `logs\build_evidence_<job key>_<token>.zip` |
| A failed run | the run's `srpss-<job key>-failure-logs` artifact (the logs, CMake's cache and configure log) |

**How a C++ slice iterates** (the agent never pushes or builds; the lead does both):

1. The agent commits its slice in its worktree (its branch is `worktree-agent-<id>`), says so in its journal and asks
   the lead for a module build (and which: `native_module` for `native/core`, `native_spike` for the harness).
2. The lead pushes that branch from the main checkout: `git push origin worktree-agent-<id>` (any work-branch name
   works; GitHub runs the branch's own copy of the workflow, so the branch must contain `native-module.yml` with the
   `source` input: GitHub refuses an input a branch's workflow does not declare).
3. The lead runs the command above with `<checkout>` = the agent's worktree, so the validated module lands in that
   worktree's `release\<job key>\` (ignored by git). Pre-flight refuses when the worktree's HEAD is not the pushed
   commit.
4. The agent tests it from there, offscreen and hidden only: the core with
   `python -m pytest tests/test_native_core_module.py` (it skips, saying why, where the module is not built) or
   `python native/core/python/import_check.py --module-dir release/native_module --expect-qt <Qt>`; the harness with
   `python native/spike_p1/python/run_spike.py --module-dir release/native_spike --part all --label <label>`.
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

- GitHub builds pushed commits only. Uncommitted work needs a commit and push first (a local build covers it).
- The runner's toolchain is GitHub's `windows-2025` image (Visual Studio 2022 MSVC) with Python 3.14 from
  `actions/setup-python`, not this machine's Build Tools; the requirement pins and Nuitka version are identical.
- The Linux Media Center artifact uses `srpss-linux-mc` and publishes `SRPSS-<version>-linux-mc-x86_64.tar.gz`;
  Linux Screensaver retains `srpss-linux` and `SRPSS-<version>-linux-x86_64.tar.gz`. Both are smoke-tested in Xvfb;
  a full frozen build on GitHub and physical Linux acceptance are still required after this change.
- The repository is public: its Actions minutes on standard runners are free, and run logs and artifacts are
  visible to signed-in GitHub users until they expire (3 days; failure logs 7).
- Each run reinstalls `requirements.txt` into a fresh `.venv`; Nuitka's compile cache is kept between runs.
- No installer is compiled on GitHub. The Linux job is the other tabs' own (`Docs/Guides/Linux_Guide.md` §7); here it
  builds the pre-flight's commit, and its tarball is downloaded as is (no manifest validation like the Windows
  products; the runner's smoke test is its gate). Only this tab's Linux dispatch sends the workflow's `commit` and
  `token` inputs (`-Commit`): GitHub refuses inputs a branch's `linux-build.yml` does not declare (HTTP 422), so the
  other tabs keep the plain dispatch and find their run by commit and start time, and an older branch still builds
  there. On this tab a branch whose `linux-build.yml` predates the inputs fails its Linux dispatch (one cut before
  8 Nov has no Windows workflow either).
- Physical acceptance (installing and running the products) is still the operator's.
