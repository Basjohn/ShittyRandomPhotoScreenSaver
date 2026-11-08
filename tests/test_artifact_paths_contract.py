"""Tool output goes through one owner (``tools/artifact_paths.py``); temp folders are cleaned up.

Operator, 7 Nov 2026: "agents have littered" and "centralize their output". By then ``.artifacts/evidence`` held
38 flat ad-hoc folders, ``logs/evidence_chest`` a second evidence root, the live check had copied 9.8 GB of
profiles, and ``%TEMP%`` held 14.7 GB: session scratchpads used as ``--out``, a lab render folder, 293 never
deleted ``mkdtemp`` settings roots from tests and probes, and ``srpss_*`` folders from tools.

Static bars over ``tools/`` (and ``tests/`` for temp folders):

1. No hard-coded write roots: no ``.artifacts``/``evidence_chest`` path literal, no ``tmp`` folder, no
   ``logs/<subfolder>`` other than the application's own logs and the operator's recordings.
2. A tool that declares an output argument routes it through the owner (``artifact_paths``).
3. A tool that writes PNG evidence encodes it with ``tools/evidence_media.py`` (WebP; PNGs only in scratch).
4. ``tempfile.mkdtemp(``, ``NamedTemporaryFile(..., delete=False)`` and ``tempfile.gettempdir()`` appear only
   where the folder is provably removed or on the reasoned allowlist; ``TemporaryDirectory`` and in-place atomic
   ``mkstemp(dir=...)`` are fine.

Each allowlist entry carries its reason. A new entry needs one too.
"""
from __future__ import annotations

import ast
import pathlib
import re
from pathlib import Path

import pytest

from tools import artifact_paths

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
OWNERS = {"tools/artifact_paths.py", "tools/evidence_media.py"}

# Outputs that are not evidence: product assets, fixtures, builds, the operator's recordings, app logs.
NOT_EVIDENCE = {
    "tools/release_media.py": "product showcase WebPs in assets/webp (release media)",
    "tools/convert_svg_to_png.py": "product icon PNGs beside their SVG sources",
    "tools/convert_weather_svgs.py": "product weather icon PNGs in assets",
    "tools/regen_qrc.py": "product QRC resource packs in ui/resources",
    "tools/linux_build.py": "release build output (release/linux)",
    "tools/build_runner.py": "release builds and the build log under logs/",
    "tools/github_remote_build.py": "GitHub Remote release builds (release/, logs/) and the runner's build manifest "
                                    "in its workspace root, which the workflow uploads",
    "tools/freeze_visualizer_settings.py": "a committed settings fixture",
    "tools/onboarding_preview_foundry.py": "product onboarding preview assets",
    "tools/onboarding_sheet_previews.py": "product onboarding sheet assets",
    "tools/visualizer_replay/record.py": "the operator's recordings (logs/visualizer_recordings)",
    "tools/godzip_foundry_core.py": "GODZIP packaging of loose logs the operator asked for",
    "tools/godzip_script_runner.py": "GODZIP capture of a script run's loose logs",
    "tools/frozen_build_audit.py": "frozen-build audit report beside the build it audits",
    "tools/defaults_foundry_core.py": "atomic in-place writes of authored defaults",
    "tools/artifact_migration.py": "one-off move of the legacy evidence roots into the layout (reads them by name)",
}

# PNG writers whose PNGs are fixtures or temporary inputs, not evidence (rule 3 only).
PNG_NOT_EVIDENCE = {
    "tools/visualizer_replay/sphere_golden.py": "test goldens (tests/goldens/visualizer_replay/sphere_visual)",
    "tools/image_worker_shm_lifecycle_harness.py": "a synthetic input PNG inside a TemporaryDirectory",
    "tools/linux_headless.py": "synthetic input images for a Linux run, in that run's scratch",
}

# logs/<name> path parts tools may name: the app's own logs and the operator's recordings (both inputs).
_LOGS_ALLOWED = re.compile(r"^(visualizer_recordings|screensaver[\w.]*|[\w.-]+\.(log|bin|jsonl?|txt)(\.\d+)?)$")

# Temp-folder uses that are cleaned up or deliberately outside the layout, with the reason.
TEMP_ALLOWED = {
    "tools/reddit_helper_task_harness.py": "the task XML (delete=False for schtasks) is unlinked in finally",
    "tools/godzip_script_runner.py": "the ZIP staging file sits in the output folder and is unlinked in finally",
    "tests/test_studio_worker_lifetime.py": "removes the temp folders a killed Studio worker under test left behind",
}

_OUTPUT_ARG = re.compile(
    r"^--(out|output|outdir|out-dir|output-dir|output-json|output-text|report|save|json|png-all|"
    r"write|write-visual|evidence)$"
)


def _tool_files() -> list[Path]:
    return sorted(path for path in TOOLS.rglob("*.py") if "__pycache__" not in path.parts)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _string_constants(tree: ast.AST) -> list[ast.Constant]:
    docs = _docstring_ids(tree)
    return [node for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs]


def _path_chain(node: ast.AST, logs_names: frozenset[str] = frozenset()) -> list[str | None]:
    """``a / "b" / "c"`` -> [None, "b", "c"] (non-constant parts are None; a name bound to ``.../"logs"`` is
    "logs")."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _path_chain(node.left, logs_names) + _path_chain(node.right, logs_names)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Name) and node.id in logs_names:
        return ["logs"]
    return [None]


def _logs_names(tree: ast.AST) -> frozenset[str]:
    """Module names assigned a path ending in ``"logs"`` (``LOGS = REPO / "logs"``)."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _path_chain(node.value)[-1:] == ["logs"]:
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return frozenset(names)


def hard_coded_roots(path: Path) -> list[str]:
    rel = _rel(path)
    if rel in OWNERS or rel in NOT_EVIDENCE:
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in _string_constants(tree):
        text = node.value.replace("\\", "/")
        if "evidence_chest" in text or re.search(r"(^|/)\.artifacts(/|$)", text):
            found.append(f"{rel}:{node.lineno} literal {node.value!r}")
        elif text.startswith("logs/"):
            part = text.split("/")[1] if len(text.split("/")) > 1 else ""
            if not _LOGS_ALLOWED.match(part):
                found.append(f"{rel}:{node.lineno} literal {node.value!r}")
        elif text in ("tmp", "tmp/"):
            found.append(f"{rel}:{node.lineno} tmp folder {node.value!r}")
    logs_names = _logs_names(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            chain = _path_chain(node, logs_names)
            for index, part in enumerate(chain[:-1]):
                if part == "logs" and chain[index + 1] is not None and not _LOGS_ALLOWED.match(chain[index + 1]):
                    found.append(f"{rel}:{node.lineno} logs/{chain[index + 1]}")
    return sorted(set(found))


def output_arguments(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"
                and not any(keyword.arg == "action" for keyword in node.keywords)):  # flags, not paths
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and _OUTPUT_ARG.match(arg.value):
                    names.append(arg.value)
    return names


def _uses(path: Path, name: str) -> bool:
    return re.search(rf"\b{name}\b", path.read_text(encoding="utf-8")) is not None


def unowned_outputs(path: Path) -> list[str]:
    rel = _rel(path)
    if rel in OWNERS or rel in NOT_EVIDENCE:
        return []
    names = output_arguments(path)
    if names and not _uses(path, "artifact_paths"):
        return [f"{rel}: {', '.join(names)} not routed through tools/artifact_paths.py"]
    return []


_PNG_WRITE = re.compile(
    r"""\.png['"]|['"]PNG['"]|with_suffix\(\s*['"]\.png|f['"][^'"\n]*\.png"""
)


def png_evidence(path: Path) -> list[str]:
    rel = _rel(path)
    if rel in OWNERS or rel in NOT_EVIDENCE or rel in PNG_NOT_EVIDENCE:
        return []
    text = path.read_text(encoding="utf-8")
    if _PNG_WRITE.search(text) and not re.search(r"\bevidence_media\b", text):
        return [f"{rel}: writes PNG without tools/evidence_media.py"]
    return []


_TEMP_LEAK = re.compile(r"tempfile\.mkdtemp\(|\bmkdtemp\(|delete\s*=\s*False|gettempdir\(\)")


def temp_leaks(path: Path) -> list[str]:
    rel = _rel(path)
    if rel in TEMP_ALLOWED or rel in OWNERS:
        return []
    text = path.read_text(encoding="utf-8")
    return [f"{rel}:{text.count(chr(10), 0, match.start()) + 1} {match.group(0)}"
            for match in _TEMP_LEAK.finditer(text)]


def test_tools_hard_code_no_write_roots():
    found = [item for path in _tool_files() for item in hard_coded_roots(path)]
    assert not found, "tools hard-code a write root; use tools/artifact_paths.py:\n" + "\n".join(found)


def test_tool_output_arguments_go_through_the_owner():
    found = [item for path in _tool_files() for item in unowned_outputs(path)]
    assert not found, "\n".join(found)


def test_png_output_goes_through_the_evidence_publisher():
    found = [item for path in _tool_files() for item in png_evidence(path)]
    assert not found, "\n".join(found)


def test_temp_folders_are_cleaned_up_or_reasoned():
    files = _tool_files() + sorted((ROOT / "tests").rglob("*.py"))
    found = [item for path in files if path.name != Path(__file__).name for item in temp_leaks(path)]
    assert not found, "temp folders that are never deleted (use tmp_path, TemporaryDirectory or " \
                      "artifact_paths.scratch):\n" + "\n".join(found)


def test_allowlist_entries_name_existing_files():
    for rel in (*NOT_EVIDENCE, *PNG_NOT_EVIDENCE, *TEMP_ALLOWED):
        assert (ROOT / rel).is_file(), f"stale allowlist entry {rel}"


# -- The owner itself -------------------------------------------------------------------------------------


def test_unknown_areas_raise():
    with pytest.raises(artifact_paths.ArtifactPathError):
        artifact_paths.evidence_dir("misc", "x", "y")
    with pytest.raises(artifact_paths.ArtifactPathError):
        artifact_paths.evidence_dir("visualizers/not_a_mode", "x", "y")
    with pytest.raises(artifact_paths.ArtifactPathError):
        artifact_paths.evidence_dir("visualizers", "x", "y")


def test_the_layout_shape(tmp_path):
    with artifact_paths.use_root(tmp_path / ".artifacts") as root:
        assert artifact_paths.evidence_dir("visualizers/bubble", "live_check", "p1", date="20261107") == (
            root / "evidence" / "visualizers" / "bubble" / "live_check" / "20261107_p1")
        assert artifact_paths.webp_path("transitions/melt", "showcase", "a", date="20261107") == (
            root / "webp" / "transitions" / "melt" / "showcase" / "20261107_a.webp")


def test_cli_outputs_outside_the_layout_are_refused(tmp_path):
    with artifact_paths.use_root(tmp_path / ".artifacts") as root:
        good = root / "evidence" / "performance" / "overhead" / "20261107_run" / "summary.json"
        assert artifact_paths.checked_output(good) == good
        assert artifact_paths.checked_output(root / "scratch" / "agent" / "frames")
        for bad in (
            tmp_path / "elsewhere",                                   # %TEMP% / a session scratchpad
            root / "evidence" / "loose_folder",                       # the old flat ad-hoc folders
            root / "evidence" / "misc" / "topic" / "20261107_x",      # undeclared area
            root / "evidence" / "settings" / "topic" / "no_date",     # missing <YYYYMMDD>_<label>
            artifact_paths.REPO_ROOT / "logs" / "evidence_chest" / "x",
        ):
            with pytest.raises(artifact_paths.ArtifactPathError):
                artifact_paths.checked_output(bad)
        with pytest.raises(artifact_paths.ArtifactPathError):
            artifact_paths.checked_output(good.with_suffix(".webp"), kind="webp")


def test_scratch_is_deleted_on_success_and_kept_on_failure(tmp_path):
    with artifact_paths.use_root(tmp_path / ".artifacts") as root:
        with artifact_paths.scratch("unit") as folder:
            (folder / "frame.png").write_bytes(b"x")
        assert not folder.exists()
        assert not (root / "scratch" / "unit").exists()
        with pytest.raises(KeyError):
            with artifact_paths.scratch("unit") as folder:
                (folder / "frame.png").write_bytes(b"x")
                raise KeyError("boom")
        assert (folder / "frame.png").exists(), "a failed run's scratch is kept for debugging"


def _aged(path, hours, now):
    import os

    for item in [path, *path.rglob("*")]:
        os.utime(item, (now - hours * 3600, now - hours * 3600))


def test_prune_scratch_is_a_dry_run_unless_applied_and_never_leaves_scratch(tmp_path):
    import os
    import time

    now = time.time()
    with artifact_paths.use_root(tmp_path / ".artifacts") as root:
        stale = root / "scratch" / "agent_a" / "999999_dead"            # no such process
        fresh = root / "scratch" / "agent_a" / "999998_fresh"
        live = root / "scratch" / "agent_b" / f"{os.getpid()}_live"     # this process is running
        for folder in (stale, fresh, live):
            folder.mkdir(parents=True)
            (folder / "frame.png").write_bytes(b"\0" * 1000)
        evidence = root / "evidence" / "visualizers" / "bubble" / "live_check" / "20261101_old"
        (evidence / "profile").mkdir(parents=True)
        (evidence / "summary.json").write_text("{}")
        (evidence / "frame.png").write_bytes(b"x")              # a still: never reported
        frames = evidence / "spin"
        frames.mkdir()
        for index in range(12):                                   # a PNG frame sequence: reported
            (frames / f"spin_{index:03d}.png").write_bytes(b"x")
        webp = root / "webp" / "settings" / "probe" / "20261101_big.webp"
        webp.parent.mkdir(parents=True)
        with open(webp, "wb") as handle:
            handle.truncate(artifact_paths.OVERSIZED_WEBP_BYTES + 1)
        for folder in (stale, live, evidence, webp.parent):
            _aged(folder, 48, now)
        _aged(fresh, 1, now)

        dry = artifact_paths.prune_scratch(now=now)
        decisions = {pathlib.Path(run["path"]).name: run["delete"] for run in dry["scratch"]}
        assert decisions == {"999999_dead": True, "999998_fresh": False, f"{os.getpid()}_live": False}
        assert stale.exists(), "a dry run deleted something"
        reported = {item["why"].split(" ")[0] for item in dry["oversized"]}
        assert reported == {"profile", "PNG", "WebP"}
        assert not any(item["path"].endswith("frame.png") for item in dry["oversized"]), "a PNG still was reported"
        assert any(item["path"] == str(frames) for item in dry["oversized"]), "a PNG frame sequence went unreported"

        artifact_paths.prune_scratch(apply=True, now=now)
        assert not stale.exists()
        assert fresh.exists() and live.exists()
        # Evidence and WebPs are only ever reported, never deleted.
        assert (evidence / "profile").exists() and (evidence / "frame.png").exists() and webp.exists()


def _junction(link, target) -> bool:
    import subprocess
    import sys

    if sys.platform != "win32":
        return False
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
    return result.returncode == 0 and link.exists()


def test_a_junctioned_layout_root_still_counts_as_inside(tmp_path):
    """The operator may move the archive to a large HDD (or scratch to an NVMe) with a directory junction."""
    artifacts = tmp_path / "repo" / ".artifacts"
    artifacts.mkdir(parents=True)
    elsewhere = tmp_path / "other_drive" / "srpss_evidence"
    elsewhere.mkdir(parents=True)
    if not _junction(artifacts / "evidence", elsewhere):
        pytest.skip("directory junctions are not available here")
    try:
        with artifact_paths.use_root(artifacts) as root:
            through = root / "evidence" / "memory" / "memory_map" / "20261107_run" / "snap.json"
            assert artifact_paths.checked_output(through) == (
                elsewhere / "memory" / "memory_map" / "20261107_run" / "snap.json").resolve()
            # The junction target itself, named directly, is the same place.
            assert artifact_paths.checked_output(elsewhere / "settings" / "probe" / "20261107_a")
            for bad in (elsewhere / "loose", tmp_path / "other_drive" / "beside", root / "webp_not"):
                with pytest.raises(artifact_paths.ArtifactPathError):
                    artifact_paths.checked_output(bad)
    finally:
        (artifacts / "evidence").rmdir()        # removes the junction, never its target


def test_pytest_never_pins_a_shared_basetemp():
    """A --basetemp in addopts would let concurrent runs (agents, chunked isolation) wipe each other's folders."""
    import configparser

    config = configparser.ConfigParser()
    config.read(ROOT / "tests" / "pytest.ini", encoding="utf-8")
    assert "--basetemp" not in config.get("pytest", "addopts", fallback="")


def test_product_names_resolve_to_the_mode_id_folder(tmp_path):
    """Folders use mode ids; the product name (and Neon Lake's former name) are accepted and resolve to the id."""
    with artifact_paths.use_root(tmp_path / ".artifacts") as root:
        expected = root / "evidence" / "visualizers" / "shockwave_grid" / "capture" / "20261107_a"
        for name in ("neon_lake_basin", "neon_lake", "shockwave_grid"):
            assert artifact_paths.evidence_dir(f"visualizers/{name}", "capture", "a", date="20261107") == expected
        assert artifact_paths.webp_path("visualizers/spline_curve", "strip", "a", date="20261107") == (
            root / "webp" / "visualizers" / "devcurve" / "strip" / "20261107_a.webp")
        given = root / "evidence" / "visualizers" / "neon_lake" / "capture" / "20261107_a" / "summary.json"
        assert artifact_paths.checked_output(given) == expected.resolve() / "summary.json"
        with pytest.raises(artifact_paths.ArtifactPathError):
            artifact_paths.evidence_dir("visualizers/neon_pond", "capture", "a")


def test_script_tools_set_their_import_path_before_importing_tools():
    """A tool run as a script (``python tools/x.py``) has only its own folder on ``sys.path``: importing ``tools.*``
    before its ``sys.path`` setup fails with ModuleNotFoundError (7 Nov: waveform_music_response and 14 others)."""
    import re

    offenders = []
    for path in _tool_files():
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        first_import = next((index for index, line in enumerate(lines)
                             if re.match(r"(from|import)\s+(core|rendering|widgets|ui|engine|tools)\b", line)), None)
        if first_import is None:
            continue
        setup = next((index for index, line in enumerate(lines)
                      if "sys.path.insert" in line or "sys.path.append" in line), None)
        if setup is not None and setup > first_import:
            offenders.append(f"{path.relative_to(ROOT)}: line {first_import + 1} imports a repo module before line {setup + 1}")
    assert not offenders, "\n".join(offenders)
