"""Hidden capture of the real Waveform Studio shell rendering the real production scene.

No window is shown: the Studio shell renders through QQuickRenderControl into a GL
texture (Windows QPA). The store is in-memory (a resolved preset copy), so nothing is
saved. Writes one PNG per workspace plus a JSON record of frame/evaluation timings.

    .venv\\Scripts\\python.exe tools\\waveform_studio_capture.py --output .artifacts\\evidence\\...\\studio
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class MemoryStore:
    def __init__(self, values, label, card_extent=None, border=None):
        self.values = dict(values)
        self.label = label
        self._extent = card_extent
        self._border = border

    def card_extent(self):
        return self._extent

    def card_style(self):
        return None if self._border is None else {"border_width": self._border, "content_inset": 0.0}

    def snapshot(self):
        return dict(self.values)

    def commit(self, values, changed):
        self.values.update(values)
        return dict(self.values)

    def preset_label(self):
        return self.label


class NoPresence:
    def conceal(self):
        pass

    def reveal(self):
        pass


def _apply_shell_state(surface, args) -> None:
    """Evidence-only shell state (picker open, dock expanded, inspector scroll) via QML object names."""
    root = surface.host.root

    def named(name):
        stack, found = [root], []
        while stack:
            item = stack.pop()
            if item.objectName() == name:
                found.append(item)
            stack.extend(reversed(item.childItems()))
        return found

    if args.pick_node >= 0:
        for row in named("gradientRow")[:1]:
            row.setProperty("selected", args.pick_node)
    if args.help_open:
        for overlay in named("helpOverlay"):
            overlay.setProperty("open", True)
    if args.dock_open:
        for dock in named("responseDock"):
            dock.setProperty("expanded", True)
    if args.scroll:
        for scroll in named("inspectorScroll"):
            flick = scroll.property("contentItem")
            bottom = max(0.0, flick.property("contentHeight") - flick.height())
            flick.setProperty("contentY", bottom if args.scroll < 0 else min(bottom, args.scroll))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preset", type=int, default=3)
    parser.add_argument("--size", default="1600x900")
    parser.add_argument("--fixture", default="peak")
    parser.add_argument("--time", type=float, default=5.0)
    parser.add_argument("--clip", default="", help="Recorded clip stem to analyse and show (slow)")
    parser.add_argument("--source-time", type=float, default=None,
                        help="With --clip: seconds from the recording's first frame (as tools/waveform_ribbon_capture --start)")
    parser.add_argument("--compare", type=Path, default=None,
                        help="A production capture PNG to place beside the Studio's presented frame")
    parser.add_argument("--framing", default="", help="Viewport framing id (default: the mode's own default)")
    parser.add_argument("--theme", type=Path, default=None, help="A .srtheme to activate for this capture")
    parser.add_argument("--tag", default="", help="Suffix for output names")
    parser.add_argument("--card-extent", default="", help="Live card world extent WxH (CUSTOM viewport_extent)")
    parser.add_argument("--border", type=float, default=None, help="Live card border width (px)")
    parser.add_argument("--workspaces", default="composition,reactivity,appearance,world")
    parser.add_argument("--expand", default="", help="Inspector groups to open (comma list, or 'all')")
    parser.add_argument("--pick-node", type=int, default=-1,
                        help="Open the colour picker on this gradient node (Appearance)")
    parser.add_argument("--scroll", type=float, default=0.0, help="Inspector scroll offset (px; negative = bottom)")
    parser.add_argument("--dock-open", action="store_true", help="Expand the Reactivity response editor")
    parser.add_argument("--help-open", action="store_true", help="Show the help overlay")
    args = parser.parse_args()
    width, height = (int(v) for v in args.size.split("x"))

    from rendering.quick.bootstrap import configure_quick_graphics
    configure_quick_graphics(reason="studio-capture")
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from PIL import Image
    from core.settings.visualizer_presets import get_preset_names, resolve_visualizer_activation_payload
    from ui.studio.controller import StudioController
    from ui.studio.surface import OffscreenStudioSurface
    from ui.studio.theme import studio_theme
    from ui.studio.waveform_adapter import WaveformStudioAdapter

    if args.theme is not None:
        from ui.settings_theme_io import load_settings_theme_file
        from ui.settings_theme_runtime import set_active_settings_theme
        set_active_settings_theme(load_settings_theme_file(args.theme))
    mode = "waveform_ribbon"
    activation = resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": args.preset - 1}, mode=mode)
    extent = tuple(float(v) for v in args.card_extent.split("x")) if args.card_extent else None
    store = MemoryStore(activation.resolved_config, get_preset_names(mode)[args.preset - 1], extent, args.border)
    surfaces = []

    def factory(controller):
        surface = OffscreenStudioSurface(controller, size=(width, height))
        surfaces.append(surface)
        return surface

    controller = StudioController(WaveformStudioAdapter(), store, NoPresence(), factory, theme_provider=studio_theme)
    if not controller.open():
        raise SystemExit("Studio did not open")
    surface = surfaces[0]
    bridge = controller.bridge
    record = {"preset": store.label, "size": [width, height], "fixture": args.fixture, "time": args.time}
    try:
        def settle():
            for _ in range(240):
                surface.pump()
                if bridge.viewportStatus != "preparing":
                    break
            if bridge.viewportStatus != "live":
                raise SystemExit(f"Viewport did not go live: {bridge.viewportStatus} {bridge.viewportError}")

        if args.clip:
            clip = next(c for c in controller.adapter.recorded_clips() if c.id == "clip:" + args.clip)
            from ui.studio.waveform_recorded_inputs import extract, to_inputs
            from dataclasses import replace
            data = extract(clip.description, store.values, seconds=12.0)
            controller.evaluator.add_recorded(to_inputs(data, replace(clip, duration=float(data["duration"]))))
            controller.select_fixture(clip.id)
            if args.source_time is not None:
                with open(clip.description, encoding="utf-8") as stream:
                    first = json.loads(stream.readline())["timestamp_us"] / 1e6
                args.time = args.source_time + first - float(data["origin"])
                record["studio_time"] = args.time
        else:
            controller.select_fixture(args.fixture)
        controller.seek(args.time)
        settle()
        # Frame cost while playing: wall time of one Quick frame with glFinish, real scene vs evaluation.
        controller.set_playing(True)
        samples, evals = [], []
        for _ in range(60):
            t0 = time.perf_counter()
            surface.pump()
            gl.glFinish()
            samples.append((time.perf_counter() - t0) * 1000)
        controller.set_playing(False)
        for _ in range(30):
            t0 = time.perf_counter()
            controller.evaluator.evaluate(controller.transport.time + 1 / 60, controller.evaluation_values())
            evals.append((time.perf_counter() - t0) * 1000)
            controller.transport.time += 1 / 60
        samples.sort()
        evals.sort()
        record["playing_frame_ms"] = {"p50": samples[len(samples) // 2], "p90": samples[int(len(samples) * .9)]}
        record["evaluate_one_step_ms"] = {"p50": evals[len(evals) // 2], "p90": evals[int(len(evals) * .9)]}
        if args.framing:
            controller.select_framing(args.framing)
        args.framing = controller.bridge.framingId
        controller.seek(args.time)
        settle()
        args.output.mkdir(parents=True, exist_ok=True)
        suffix = (("_" + args.clip) if args.clip else "") + (("_" + args.tag) if args.tag else "")
        # The presented frame alone (the letterboxed live-card extent), for production comparison.
        from PySide6.QtCore import QPointF
        slot = surface.host.slot
        origin = slot.mapToScene(QPointF(slot.property("frameX"), slot.property("frameY")))
        fw, fh = int(slot.property("frameWidth")), int(slot.property("frameHeight"))
        frame = surface.grab()[int(origin.y()):int(origin.y()) + fh, int(origin.x()):int(origin.x()) + fw]
        frame_path = args.output / f"studio_frame_{args.framing}{suffix}.png"
        Image.fromarray(frame).save(frame_path)
        record["presented_frame"] = [fw, fh]
        if args.compare is not None:
            production = Image.open(args.compare).convert("RGBA")
            studio = Image.fromarray(frame).resize(production.size, Image.LANCZOS)
            sheet = Image.new("RGBA", (production.width * 2 + 12, production.height + 28), (10, 10, 10, 255))
            sheet.paste(production, (0, 28))
            sheet.paste(studio, (production.width + 12, 28))
            from PIL import ImageDraw
            draw = ImageDraw.Draw(sheet)
            draw.text((6, 6), "production capture", fill="white")
            draw.text((production.width + 18, 6), "Studio presented frame (resized to match)", fill="white")
            compare_path = args.output / f"compare_{args.framing}{suffix}.png"
            sheet.save(compare_path)
            record["compare"] = str(compare_path)
        for workspace in args.workspaces.split(","):
            bridge.setWorkspace(workspace)
            if workspace == "appearance":
                bridge.selectObject("ribbon1")
            if args.expand:
                groups = {g for w in controller.session.schema.workspaces for g in w.groups} \
                    if args.expand == "all" else set(args.expand.split(","))
                import dataclasses
                # Evidence only: exactly these groups open (the bridge's own schema copy).
                bridge._schema = dataclasses.replace(bridge._schema, workspaces=tuple(
                    dataclasses.replace(w, open_groups=tuple(g for g in w.groups if g in groups) or ("(none)",))
                    for w in bridge._schema.workspaces))
                bridge._rebuild_inspector()
            surface.pump(3)
            for _ in range(240):           # starting-point tile previews (served one per frame)
                if not controller.previews_pending:
                    break
                surface.pump()
            _apply_shell_state(surface, args)
            surface.pump(3)
            name = args.output / f"studio_{workspace}{suffix}.png"
            Image.fromarray(surface.grab()).save(name)
            record.setdefault("images", []).append(str(name))
        (args.output / f"studio_capture{'_' + args.clip if args.clip else ''}.json").write_text(
            json.dumps(record, indent=1), encoding="utf-8")
        print(json.dumps(record, indent=1))
    finally:
        controller.close()
        app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
