# The native core: `_srpss_native_core`

The product's native module (`Current_Plan.md` item 8b, N2; decision D5.7 in
`Docs/Future_Work/Native_Core_P3_Decisions.md`). `native/spike_p1/` beside it stays the harness and evidence and
never ships.

- `CMakeLists.txt`, `build.cmd`: the build. Compiled only by `.github/workflows/native-module.yml` on GitHub (its
  default source); never on this machine. `build.cmd` is the workflow's one CMake invocation.
- `src/`: the C++ module. `abi.h` holds the ABI that `rendering/native/loader.py` speaks (`EXPECTED_ABI`);
  `host_adapter.*` is the host adapter's entry (D5.1).
- `shaders/`: GLSL 440 sources (`.vert`, `.frag`, `.comp`), each baked by PySide6's `qsb` for every shipped backend
  and embedded in the module; the workflow's staging requires one `.qsb` per source.
- `python/import_check.py`: the GPU-free check the workflow runs after the compile, through `rendering.native`.

The guards: CMake refuses a Qt SDK other than `requirements.txt`'s PySide6 pin; the module refuses to import under
any Qt but the one it was compiled for; `rendering.native` refuses a module whose Qt, ABI or MSVC runtime arrangement
does not match this process (`rendering/native/runtime_check.py`: no `msvcp140` import, the loaded `vcruntime140` at
least as new as the compiler). Tests: `tests/test_native_core_*.py`.

Build and fetch it (the lead; agents never build):

```
.venv\Scripts\python.exe tools\build_runner.py --mode github --run --select native_module
```

The module lands in `release\native_module\` of the checkout the command runs from; `rendering.native.load(Path(
"release/native_module"))` loads it from there. `Docs/Guides/GitHub_Remote_Build.md`, "The native modules", has the
rest.
