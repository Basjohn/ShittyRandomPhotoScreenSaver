# Python 3.14 | Current Windows Toolchain and Operator Build Gate

**Current machine state (2026-10-09):** Standard-GIL x64 Python **3.14.8** is installed through Python Install Manager at `%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe`. The repo-root `.venv` is already recreated, tested and used by Foundries/Build Runner. Python 3.11 is uninstalled. **Do not rerun `scripts/cutover_python314.ps1` on this installation**: it deliberately destroys `.venv`. That script remains only for a freshly provisioned machine needing an operator-authorized clean cutover.

## Interpreter, dependencies and compiler

- Run developer tools with `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\.venv\Scripts\python.exe` (or `pythonw.exe` for GUI desktop shortcuts), not a global `python`/`pythonw` or obsolete `C:\Python311` path.
- PySide6/Qt **6.11.2**; NumPy **2.4.5**; Nuitka **4.2**; PyAudioWPatch **0.2.12.9**; `threadpoolctl` inspects the actual NumPy 2 BLAS backend. The pinned `requirements.txt` and helper requirements are authoritative.
- Windows frozen builds require **Visual Studio 2022+ Build Tools**, *Desktop development with C++*, MSVC and Windows SDK. Nuitka's regular MinGW64 flow is unsupported under Python 3.14; experimental forced MinGW is not the SRPSS release authority. Retain `--msvc=latest` until the operator accepts an alternative compiler.
- `scripts/python314_runtime.ps1` resolves the single interpreter. Normal and Repo Venv Build Runner options still have independent build workspaces but use the **same repo `.venv` Python for QRC and Nuitka preparation**. Godzip Foundry RUN SCRIPT does not rewrite pasted commands.
- Preserve `core/native_threads.py`'s **one OpenBLAS thread before NumPy import**, including child processes, and the Qt GUI image-pool thread-retention policy (R-99/R-97). Both are native-memory/thread-churn guardrails, not optional Python-migration cleanup.

## Evidence already accepted

The operator's migration tooling selection passed **47/47**; R149's source repair focus passed **124/124**; R150 Sphere/Shockwave audio isolation focus passed **96/96**; and R151's Windows Steam/Settings regression selection passed **106/106**. Sphere and Shockwave were also physically accepted. Those focused results do not imply a full R151 destination-suite pass. The latest supplied four-chunk results, from before the R151 publication-lock repair, had one Windows Steam final-publication collision in chunk 4; its repair has now passed the relevant focused tests. The now-retired R149 test diary is not current evidence authority; the substantial Sphere analysis and cache publication mechanisms remain in R150 and R151, linked from `Docs/Historical_Bugs.md`.

## Build and physical acceptance | operator owns execution

**Agents must not launch Build Runner, Nuitka, installers, trial builds, helper freezes, or expensive product compilation.** The **operator** runs Standard, Diagnostic, Media Center and Reddit Helper frozen builds and provides their outputs, Nuitka compilation reports and footprint JSON. The agent then diagnoses the actual logs and returns source corrections with only relevant focused tests. A full four-chunk repeat is **not requested** unless the operator chooses it.

The operator may use the Build Runner GUI or the existing worker scripts. Workers remain documented as entry points, **not agent-run instructions**:

`script/venv` is **not** a valid owner; the canonical build worker directory is `scripts/venv/`.

- Standard: `scripts/venv/build_nuitka.ps1`
- Diagnostic: `scripts/venv/build_nuitka_diagnostic.ps1`
- Media Center: `scripts/venv/build_nuitka_mc_onedir.ps1`
- Reddit Helper: `scripts/venv/build_reddit_helper.ps1`

Physical acceptance covers frozen launch/exit, dual-display transitions (400 ms ordinary desync, 200 ms first-image stagger), audio/widgets, image cache/prefetch, runtime/installer footprint and clean retirement. Native build acceptance can only be claimed from operator-run Windows results.

## Build Runner evidence for onefile and onedir parity

For each **operator-launched** build, Build Runner now uses the same run token for its wrapper log and the worker reports. After a job completes (including compiler failures), use the **Evidence ZIP** link beside that job or collect `logs/build_evidence_<job>_<run-id>.zip` (e.g. `build_evidence_standard_...zip`). It contains `evidence.json`, Build Runner transcript, and any reports actually generated for that run. An absent XML is reported as missing, not substituted from a different build. The large SCR/EXE is **not** duplicated in the ZIP; `evidence.json` records its size and SHA-256.

For Nuitka jobs, the worker also validates `rendering.quick.context_menu`, `core.sources.image_bans`, and critical engine modules against the generated XML **before publishing**. A source fingerprint prevents reusing a onefile extraction directory across different tracked source revisions. This is a build-provenance safeguard, **not** proof of on-screen menu parity. The Normal onefile Ban Image discrepancy remains open in `Docs/Guides/Python314_Cutover.md` until operator physical confirmation.

No agent should launch a build to generate this evidence. Use relevant focused source/packaging tests and wait for the operator's build reports.

## Operator-requested focused command format

Use **one line, semicolon-separated**, suitable for Godzip Foundry RUN SCRIPT. Example toolchain read-only probe:

```powershell
$root = 'F:\Programming\Apps\ShittyRandomPhotoScreenSaver'; Set-Location $root; & '.\.venv\Scripts\python.exe' tools/python314_probe.py
```

Do **not** automatically append the four-chunk suite or a build to a focused source fix. The active queue is in `Current_Plan.md`; the original cutover rationale and failures are archived in the historical records.
