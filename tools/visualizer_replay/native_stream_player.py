"""The native-only pixel run of the fast long-clip proof (part 2 step 4b): a take's delivery stream drawn by the native
item alone, on OpenGL and on Vulkan, every frame hashed, and Vulkan judged against OpenGL (rule (b)).

    python tools/visualizer_replay/native_stream_player.py --deliveries <folder> --out <evidence dir>
        [--apis opengl vulkan] [--against <an earlier native_stream_player.json>]

The delivery stream is what the product's route delivered to the native core per input of a production owner tick
(``native_record_identity.py --deliveries``, CPU only): the record the core holds, the settings, the card and the
target sizes. Each API runs in its own child process (Qt Quick's API is process-wide) on the module's hidden host, with
the generic mode harness's own item placement (``native/core/python/devcurve_check.py``'s ``Scene`` and ``Stream``,
with the mode's ``program_item``: ``bubble_check.py`` for Bubble). The item is drawn over a transparent root, so a
frame's alpha is the native item's own translucency (rule (b)'s mask). Per frame, as it is drawn, one progress line:
its hash. Then:

- **rule (b)**: every frame drawn on both APIs, Vulkan against OpenGL under the mode's ``VULKAN_RULE_B`` (the shared
  tolerance), the mask the OpenGL frame's translucent pixels, every failing frame recorded, per half;
- **native before against native after**: with ``--against``, each API's hashes against that report's, every changed
  frame listed (no tolerance).

The modes: the generic modes the harnesses place (``MODES``: Spline Curve, Bubble). Spectrum's hand-written item has its
own placement (``spectrum_check.py``) and is not played yet. Hidden only, no window is shown.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import traceback
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "native" / "core" / "python"
for path in (ROOT, HARNESS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from tools import artifact_paths  # noqa: E402

APIS = ("opengl", "vulkan")
#: mode id -> the generic mode harness module whose ``Scene``, ``Stream`` and ``program_item`` place its item.
MODES = {"devcurve": "devcurve_check", "bubble": "bubble_check"}
CHILD_TIMEOUT_S = 7200
#: The method proof's shader controls (guide section 7: the selected windows must catch a one-ulp shader change):
#: mode -> name -> (shader file, the line, its replacement). ``ulp_ring``: every bubble outline's coverage one float
#: ulp up (x 1.00000012), a change each antialiased ring edge carries. A control must change pixels on the full run
#: first: the background gradient's offset (0.5 -> 0.50000006) changed none of nightsolong's 5,313 frames (21 Nov),
#: because the take's light and dark gradient colours are equal, so grad_t reaches no pixel.
SHADER_CONTROLS = {
    "bubble": {"ulp_ring": ("bubble.frag",
                            "        ring_alpha *= balpha;\n",
                            "        ring_alpha *= balpha * 1.00000012;\n")},
}
REPORT_NAME = "native_stream_player.json"
#: The player's scene: the harness's item at its margin over a transparent root (the frame's alpha is the item's).
SCENE_QML = b"""import QtQuick
Item {
    Item { objectName: "contentHost"; x: %(margin)d; y: %(margin)d; width: 4; height: 4 }
}
"""


def _harness(mode: str):
    import importlib

    module = importlib.import_module(MODES[mode])
    base = getattr(module, "base", module)
    if mode == "bubble":
        base.use_mode(SLOT_BYTES=module._slot_bytes())
    return module, base


def read_deliveries(folder: Path):
    """(the header, the input lines, the records file)."""
    lines = (Path(folder) / "deliveries.jsonl").read_text(encoding="utf-8").splitlines()
    return json.loads(lines[0]), [json.loads(line) for line in lines[1:]], Path(folder) / "records.bin"


def child(args) -> dict:
    """One API's run: every delivered input drawn, hashed, its frame kept (zlib) in the work folder."""
    api = args.api
    out = Path(args.out_dir)
    header, inputs, records_path = read_deliveries(Path(args.deliveries))
    mode = header["mode"]
    record: dict = {"api": api, "mode": mode, "inputs": len(inputs)}
    if api == "opengl":
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="native-stream-player")
        from PySide6.QtWidgets import QApplication

        app = QApplication([sys.argv[0]])
    else:
        from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Vulkan)
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication([sys.argv[0]])
    from PySide6.QtQml import QQmlEngine
    from rendering.native import load

    core = load(ROOT / args.module_dir if not Path(args.module_dir).is_absolute() else Path(args.module_dir))
    record["runtime"] = dict(core.info)
    if api == "vulkan":
        instance = core.vulkan_instance(validation=False)
        if not instance.get("ok"):
            record["error"] = f"the Vulkan instance failed: {instance}"
            return record
    module, base = _harness(mode)
    base.SCENE_QML = SCENE_QML % {b"margin": base.MARGIN}
    if args.control:
        base.CONTROL = args.control                     # read by the mode's control_record
        record["control"] = args.control
    if args.shader_control:
        # The shader control: the mode's pack baked from its source with one line changed, drawn instead of the
        # product's (the product's own baker; no module build).
        import probe_rings
        from rendering.native import program_values

        filename, line, replacement = SHADER_CONTROLS[mode][args.shader_control]
        text = module._shader_text(filename)
        if text.count(line) != 1:
            raise RuntimeError(f"{filename}: the shader control's line is not found exactly once")
        pack = probe_rings.bake(text.replace(line, replacement), filename, out / "work" / "control_packs")
        original = program_values.mode_fragment_pack
        program_values.mode_fragment_pack = lambda mode_id, _o=original: pack if mode_id == mode else _o(mode_id)
        record["shader_control"] = args.shader_control
    engine = QQmlEngine()
    host = core.hidden_host(*base.HOST_PIXELS)
    progress = out / f"progress_{api}.jsonl"
    progress.write_text("", encoding="utf-8")
    allowed = None
    if args.windows:
        from tools.visualizer_replay.coverage_windows import window_inputs

        allowed = window_inputs(json.loads(Path(args.windows).read_text(encoding="utf-8")))
        record["window_inputs"] = len(allowed)
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    frames_file = (work / f"frames_{api}.bin").open("wb")
    index_rows: list = []
    scene = stream = None
    drawn_count = 0
    started = time.perf_counter()
    try:
        records = records_path.open("rb")
        settings = card = sizes = current = None
        dpr = None
        for line in inputs:
            for key in ("settings", "card", "sizes"):
                if key in line:
                    if key == "settings":
                        settings = line[key]
                    elif key == "card":
                        card = line[key]
                    else:
                        sizes = line[key]
            if "record" in line:
                offset, size = line["record"]
                records.seek(offset)
                current = records.read(size)
            row = {"input": line["input"], "drawn": False}
            if allowed is not None and line["input"] not in allowed:
                row["skipped"] = True                     # outside every window: state kept, nothing drawn
            elif line["drawn"] and current is not None:
                if scene is None or float(card["dpr"]) != dpr:
                    if scene is not None:
                        scene.close(app)
                        stream.close()
                    dpr = float(card["dpr"])
                    host.set_device_pixel_ratio(dpr)
                    scene = base.Scene(core, engine, host)
                    stream = base.Stream()
                entry = {"card": card, "shown": card, "settings": settings, "sizes": sizes or {}}
                placed = scene.place(entry, dpr, stream)
                published = current
                if args.control and api == "vulkan":
                    published = module.control_record(current)        # the mode's own record control
                stream.publish(published, float(line["input"]))
                scene.mode.update()
                pixels = scene.read(placed)
                raw = pixels.tobytes()
                row.update(drawn=True, hash=hashlib.sha256(raw).hexdigest(), offset=frames_file.tell(),
                           shape=list(pixels.shape))
                data = zlib.compress(raw, 1)
                row["size"] = len(data)
                frames_file.write(data)
                drawn_count += 1
            index_rows.append(row)
            with progress.open("a", encoding="utf-8") as stream_out:
                stream_out.write(json.dumps({k: row.get(k) for k in ("input", "drawn", "hash")}) + "\n")
        records.close()
    finally:
        frames_file.close()
        if scene is not None:
            scene.close(app)
        if stream is not None:
            stream.close()
        host.frames(2)
        host.close()
    (work / f"index_{api}.json").write_text(json.dumps(index_rows), encoding="utf-8")
    record.update(drawn=drawn_count, seconds=round(time.perf_counter() - started, 1))
    if api == "vulkan":
        record["teardown"] = core.destroy_vulkan_instance()
    del engine, app
    return record


def _frames(out: Path, api: str):
    import numpy as np

    rows = json.loads((out / "work" / f"index_{api}.json").read_text(encoding="utf-8"))
    path = out / "work" / f"frames_{api}.bin"

    def pixels(row):
        with path.open("rb") as stream:
            stream.seek(row["offset"])
            return np.frombuffer(zlib.decompress(stream.read(row["size"])), np.uint8).reshape(row["shape"])

    return rows, pixels


def rule_b(out: Path, mode: str, switch_input: int | None, windows: dict | None = None) -> dict:
    """Vulkan against OpenGL, frame by frame, under the mode's ``VULKAN_RULE_B``; every failing frame recorded; with
    ``windows`` (a coverage_windows.json), each window's figures with its position in the take."""
    from tools import pixel_tolerance as pt

    module, base = _harness(mode)
    tolerance = getattr(module, "VULKAN_RULE_B", base.VULKAN_RULE_B)
    # Rule (b) judges two peers, neither the reference: its mask is the union of each frame's class (the lead, 21 Nov;
    # ``pt.peer_mask``): the translucent pixels of either frame, and the mode's own frame-side class where it has one.
    frame_mask = getattr(module, "peer_frame_mask", None) or getattr(base, "peer_frame_mask", None)
    gl_rows, gl_pixels = _frames(out, "opengl")
    vk_rows, vk_pixels = _frames(out, "vulkan")
    judged, failed = [], []
    compared = equal = 0
    drawn_mismatch = []
    for a, b in zip(gl_rows, vk_rows):
        if a["drawn"] != b["drawn"]:
            drawn_mismatch.append(a["input"])
            continue
        if not a["drawn"]:
            continue
        compared += 1
        if a["hash"] == b["hash"]:
            equal += 1
            continue
        gl, vk = gl_pixels(a), vk_pixels(b)
        sides = [frame_mask(frame) for frame in (gl, vk)] if frame_mask is not None else []
        verdict = pt.judge(vk[..., :3], gl[..., :3], tolerance,
                           mask=pt.peer_mask(pt.translucent_by_alpha(gl), pt.translucent_by_alpha(vk), *sides))
        verdict["input"] = a["input"]
        judged.append(verdict)
        if not verdict["pass"]:
            failed.append({k: verdict.get(k) for k in ("input", "reasons", "max_level", "scatter", "ties",
                                                       "scatter_group", "scatter_window")})
    summary = pt.summarise(judged)
    halves = None
    if switch_input:
        half = switch_input // 2
        halves = {name: pt.summarise([v for v in judged if lo <= v["input"] < hi])
                  for name, lo, hi in (("first", 0, half), ("second", half, switch_input))}
    result = {"pass": compared > 0 and not drawn_mismatch and summary["pass"] and len(gl_rows) == len(vk_rows),
              "bound": tolerance.bound(), "frames": [len(gl_rows), len(vk_rows)], "compared": compared,
              "hash_equal": equal, "judged": len(judged), "drawn_on_one_api": drawn_mismatch, "summary": summary,
              "halves": halves, "failed_frames": failed}
    if windows is not None:
        drawn_inputs = {row["input"] for row in gl_rows if row["drawn"]}
        result["windows"] = []
        for window in windows["windows"]:
            lo, hi = window["inputs"]
            inside = [v for v in judged if lo <= v["input"] < hi]
            result["windows"].append({
                "inputs": [lo, hi], "seconds": window.get("seconds"), "reasons": window["reasons"],
                "drawn": sum(1 for i in range(lo, hi) if i in drawn_inputs),
                "failed": [v["input"] for v in inside if not v["pass"]], "summary": pt.summarise(inside)})
    return result


def against(out: Path, api: str, baseline: dict) -> dict:
    old = baseline.get("hashes", {}).get(api)
    if old is None:
        return {"compared": False, "identical": False, "reason": f"the baseline has no {api} hashes"}
    rows, _pixels = _frames(out, api)
    new = [row.get("hash") for row in rows]
    skipped = {i for i, row in enumerate(rows) if row.get("skipped")}      # a windowed run's undrawn inputs
    changed = [i for i, (x, y) in enumerate(zip(old, new)) if i not in skipped and x != y]
    return {"compared": True, "frames": [len(old), len(new)], "judged": len(new) - len(skipped), "changed": changed,
            "identical": not changed and len(old) == len(new) and len(new) > len(skipped)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--deliveries", type=Path, required=True)
    parser.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--against", type=Path, default=None)
    parser.add_argument("--switch-input", type=int, default=None,
                        help="the take's mode-switch input (the layer L report's switch_input): halves of rule (b)")
    parser.add_argument("--module-dir", default="release/native_module")
    parser.add_argument("--windows", type=Path, default=None,
                        help="a coverage_windows.json: only its windows' inputs (with their warm-up) are drawn; the "
                             "delivered state is still followed through every input")
    parser.add_argument("--control", default=None,
                        help="a negative control: one of the mode harness's record controls (bubble_check's "
                             "position_nudged or big_class_bit) applied on the Vulkan child; rule (b) must FAIL")
    parser.add_argument("--shader-control", default=None,
                        help="a shader control (SHADER_CONTROLS, e.g. ulp_ring) drawn on every API's child: with "
                             "--against a native-before run, the changed frames show it")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--api", choices=APIS, help=argparse.SUPPRESS)
    parser.add_argument("--out-dir", help=argparse.SUPPRESS)
    parser.add_argument("--child-json", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child:
        try:
            record = child(args)
        except Exception:
            text = traceback.format_exc()
            record = {"api": args.api, "error": text.strip().splitlines()[-1], "traceback": text}
        args.child_json.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
        return 0
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    header, _inputs, _records = read_deliveries(args.deliveries)
    mode = header["mode"]
    if mode not in MODES:
        parser.error(f"the player draws the generic modes {sorted(MODES)}, not {mode!r}")
    report: dict = {"mode": mode, "deliveries": str(args.deliveries), "children": {}, "hashes": {}}
    for api in args.apis:
        child_json = out / f"child_{api}.json"
        child_json.unlink(missing_ok=True)
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--deliveries",
                   str(Path(args.deliveries).resolve()), "--module-dir", args.module_dir, "--out-dir", str(out),
                   "--child-json", str(child_json), "--out", str(out)]
        if args.control:
            command += ["--control", args.control]
        if args.windows:
            command += ["--windows", str(Path(args.windows).resolve())]
        if args.shader_control:
            command += ["--shader-control", args.shader_control]
        started = time.monotonic()
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=CHILD_TIMEOUT_S, cwd=str(ROOT))
            code, stderr = proc.returncode, proc.stderr
        except subprocess.TimeoutExpired as exc:
            code, stderr = "timeout", str(exc.stderr or "")
        record = json.loads(child_json.read_text(encoding="utf-8")) if child_json.exists() else {
            "api": api, "error": f"the child ended without a record ({code})"}
        child_json.unlink(missing_ok=True)
        record.update(exit_code=code, wall_s=round(time.monotonic() - started, 1))
        if code != 0 or record.get("error"):
            record["stderr_tail"] = (stderr or "")[-4000:]
        report["children"][api] = record
        print(f"[PLAYER] {api}: {record.get('drawn')} frames drawn in {record.get('seconds')} s"
              + (f"; ERROR {record['error']}" if record.get("error") else ""), flush=True)
        if not record.get("error"):
            rows, _ = _frames(out, api)
            report["hashes"][api] = [row.get("hash") for row in rows]
    if all(api in report["hashes"] for api in APIS):
        windows = json.loads(Path(args.windows).read_text(encoding="utf-8")) if args.windows else None
        report["rule_b"] = rule_b(out, mode, args.switch_input, windows)
        rb = report["rule_b"]
        print(f"[PLAYER] rule (b): {rb['compared']} frames compared ({rb['hash_equal']} hash-equal), "
              f"{len(rb['failed_frames'])} failing; {'PASS' if rb['pass'] else 'FAIL'}", flush=True)
    if args.against is not None:
        baseline = json.loads(Path(args.against).read_text(encoding="utf-8"))
        report["against"] = {api: against(out, api, baseline) for api in report["hashes"]}
        for api, entry in report["against"].items():
            print(f"[PLAYER] {api} against the baseline: {json.dumps(entry)[:300]}", flush=True)
    (out / REPORT_NAME).write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    ok = all(not c.get("error") for c in report["children"].values())
    ok = ok and report.get("rule_b", {"pass": True})["pass"]
    ok = ok and all(e.get("identical", True) for e in report.get("against", {}).values())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
