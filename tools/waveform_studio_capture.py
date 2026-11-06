"""Hidden capture of a real mode Studio shell rendering the real production scene (Waveform by default;
``--mode`` picks any registered Studio, e.g. ``extruded_bubble``).

No window is shown: the Studio shell renders through QQuickRenderControl into a GL
texture (Windows QPA). The store is in-memory (a resolved preset copy), so nothing is
saved. Writes one PNG per workspace plus a JSON record of frame/evaluation timings.

    .venv\\Scripts\\python.exe tools\\waveform_studio_capture.py --output .artifacts\\evidence\\...\\studio
    .venv\\Scripts\\python.exe tools\\waveform_studio_capture.py --mode extruded_bubble --preset 1 --output ...
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

    def environment_image(self):
        """What a reflecting mode mirrors: the saver's first source image (read-only settings), else neutral."""
        from ui.studio.environment import environment_image
        return environment_image(getattr(self, "folders", ()) or ())

    def snapshot(self):
        return dict(self.values)

    def commit(self, values, changed):
        self.values.update(values)
        return dict(self.values)

    def preset_label(self):
        return self.label

    def presets(self):
        from core.settings.visualizer_presets import get_preset_names
        return list(get_preset_names("waveform_ribbon"))

    def preset_index(self):
        names = self.presets()
        return names.index(self.label) if self.label in names else -1


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
    if args.preset_menu:
        from PySide6.QtCore import QMetaObject, QObject
        menu = root.findChild(QObject, "presetMenu")
        if menu is not None:
            QMetaObject.invokeMethod(menu, "open")
    if args.viewport_expanded:
        root.setProperty("viewportExpanded", True)
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


def _settle_replay(controller, surface) -> None:
    """Pump frames until the exact replay of the current values has landed (``converging`` off)."""
    surface.pump()
    for _ in range(2000):
        if not getattr(controller.evaluator, "converging", False):
            break
        surface.pump()
    surface.pump(2)


def _presented_frame(surface):
    """The presented frame's pixels (the letterboxed live-card extent) of the current shell frame."""
    from PySide6.QtCore import QPointF
    slot = surface.host.slot
    origin = slot.mapToScene(QPointF(slot.property("frameX"), slot.property("frameY")))
    fw, fh = int(slot.property("frameWidth")), int(slot.property("frameHeight"))
    return surface.grab()[int(origin.y()):int(origin.y()) + fh, int(origin.x()):int(origin.x()) + fw]


def _paint_stroke(controller, surface, args) -> dict:
    """One brush stroke through the bridge, as the shell's brush layer sends it (press, moves between frame starts,
    release), then the footprint hovered at the stroke's end. ``--brush`` is in presented-frame fractions."""
    bridge = controller.bridge
    if bridge.brush is None:
        raise SystemExit(f"{args.mode} has no Studio brush")
    fx0, fy0, fx1, fy1 = (float(v) for v in args.brush.split(","))
    _settle_replay(controller, surface)
    frames = {"before": _presented_frame(surface)}
    bridge.setBrushActive(True)
    bridge.setBrushValue("mode", args.brush_mode)
    if args.brush_strength is not None:
        bridge.setBrushValue("strength", args.brush_strength)
    if args.brush_radius is not None:
        bridge.setBrushValue("radius", args.brush_radius)
    target = bridge.brush.target
    width, height = controller.presented_geometry()[0]
    (x0, y0), (x1, y1) = (fx0 * width, fy0 * height), (fx1 * width, fy1 * height)
    before = controller.session.values[target.key]
    bridge.brushPress(x0, y0)
    steps = 32
    for index in range(1, steps + 1):
        t = index / steps
        bridge.brushMove(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
        if index % 4 == 0:
            surface.pump()
    bridge.brushRelease()
    bridge.setBrushActive(False)          # the scene alone (the panel and footprint are over the frame)
    _settle_replay(controller, surface)
    frames["after"] = _presented_frame(surface)
    bridge.setBrushActive(True)
    bridge.brushHover(x1, y1)
    surface.pump(3)
    frames["cursor"] = _presented_frame(surface)
    from PIL import Image
    tag = ("_" + args.tag) if args.tag else ""
    for name, pixels in frames.items():
        Image.fromarray(pixels).save(args.output / f"brush_{name}{tag}.png")
    after = controller.session.values[target.key]
    changed = sum(1 for a, b in zip(before["heights"], after["heights"]) if a != b)
    return {"stroke_frame_fraction": [fx0, fy0, fx1, fy1], "screen": [[x0, y0], [x1, y1]], "mode": args.brush_mode,
            "settings": bridge.brush.settings.as_map(), "previews": bridge.brush.previews,
            "pointer_events": bridge.brush.pointer_events, "cells_changed": changed,
            "commits": controller.session.commit_count, "undo": controller.session.undo_label}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", default="waveform_ribbon", help="A registered Studio mode id")
    parser.add_argument("--preset", type=int, default=3)
    parser.add_argument("--size", default="1600x900")
    parser.add_argument("--fixture", default="peak")
    parser.add_argument("--time", type=float, default=5.0)
    parser.add_argument("--clip", default="", help="Recorded clip to analyse and show (slow): a shipped clip id "
                             "(rag_doll, human, growing_pains) or a logs/visualizer_recordings stem")
    parser.add_argument("--source-time", type=float, default=None,
                        help="With --clip: seconds from the recording's first frame (as tools/waveform_ribbon_capture --start)")
    parser.add_argument("--compare", type=Path, default=None,
                        help="A production capture PNG to place beside the Studio's presented frame")
    parser.add_argument("--framing", default="", help="Viewport framing id (default: the mode's own default)")
    parser.add_argument("--theme", type=Path, default=None, help="A .srtheme to activate for this capture")
    parser.add_argument("--tag", default="", help="Suffix for output names")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=JSON",
                        help="Override one value of the in-memory store (evidence only; nothing is saved)")
    parser.add_argument("--card-extent", default="live",
                        help="Live card world extent: WxH (CUSTOM viewport_extent), 'live' (default: the card in "
                             "this machine's saved settings, read only) or 'baseline' (420x280)")
    parser.add_argument("--border", type=float, default=None, help="Live card border width (px)")
    parser.add_argument("--workspaces", default="", help="Comma list (default: every workspace of the mode)")
    parser.add_argument("--object", default="", help="Scene object to select for the first workspace")
    parser.add_argument("--expand", default="", help="Inspector groups to open (comma list, or 'all')")
    parser.add_argument("--pick-node", type=int, default=-1,
                        help="Open the colour picker on this gradient node (Appearance)")
    parser.add_argument("--scroll", type=float, default=0.0, help="Inspector scroll offset (px; negative = bottom)")
    parser.add_argument("--dock-open", action="store_true", help="Expand the Reactivity response editor")
    parser.add_argument("--help-open", action="store_true", help="Show the help overlay")
    parser.add_argument("--preset-menu", action="store_true", help="Open the header preset dropdown")
    parser.add_argument("--viewport-expanded", action="store_true", help="Expand the viewport over the panels")
    parser.add_argument("--brush", default="", metavar="X0,Y0,X1,Y1",
                        help="A mode with the Studio brush (Neon Lake): paint one stroke between two points of the "
                             "presented frame (fractions of its width and height) "
                             "before the workspace captures (the in-memory store takes it; nothing is saved), "
                             "leaving the brush active with its footprint at the stroke's end")
    parser.add_argument("--brush-mode", default="Raise", help="With --brush: Raise, Lower, Flatten or Water")
    parser.add_argument("--brush-strength", type=float, default=None, help="With --brush: 0..1")
    parser.add_argument("--brush-radius", type=float, default=None, help="With --brush: grid uv share")
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
    from core.settings.visualizer_mode_settings import mode_settings
    from ui.studio.registry import create_adapter

    if args.theme is not None:
        from ui.settings_theme_io import load_settings_theme_file
        from ui.settings_theme_runtime import set_active_settings_theme
        set_active_settings_theme(load_settings_theme_file(args.theme))
    mode = args.mode
    activation = resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": args.preset - 1}, mode=mode)
    if args.card_extent == "live":
        from core.settings.settings_manager import SettingsManager
        from ui.studio.settings_link import live_card_extent
        saved = SettingsManager().get("widgets")          # read only: nothing is written
        extent = live_card_extent(saved, mode)
        if args.border is None and isinstance(saved, dict):
            border = (saved.get("global") or {}).get("card_border_width_px")
            args.border = float(border) if border is not None else None
    elif args.card_extent in ("", "baseline"):
        extent = None
    else:
        extent = tuple(float(v) for v in args.card_extent.split("x"))
    values = dict(activation.resolved_config)
    spec = mode_settings(mode)
    if mode != "waveform_ribbon" and spec is not None:
        # The Settings store's canonical admission (legacy direction pairs -> six-coordinate paths, ...).
        values.update({c.key: c.admit(values[c.key], values[c.key]) for c in spec.controls if c.key in values})
    for override in args.set:
        key, _, text = override.partition("=")
        values[key.strip()] = json.loads(text)
    store = MemoryStore(values, get_preset_names(mode)[args.preset - 1], extent, args.border)
    if args.card_extent == "live":
        from core.settings.settings_manager import SettingsManager
        folders = SettingsManager().get("sources.folders") or []       # read only
        store.folders = folders if isinstance(folders, (list, tuple)) else [folders]
    surfaces = []

    def factory(controller):
        surface = OffscreenStudioSurface(controller, size=(width, height), present_on_show=False)
        surfaces.append(surface)
        return surface

    controller = StudioController(create_adapter(mode), store, NoPresence(), factory, theme_provider=studio_theme)
    if not controller.open():
        raise SystemExit("Studio did not open")
    surface = surfaces[0]
    bridge = controller.bridge
    record = {"mode": mode, "preset": store.label, "size": [width, height], "fixture": args.fixture,
              "time": args.time, "card_extent": list(extent) if extent else "baseline", "border": args.border}
    try:
        def settle():
            for _ in range(240):
                surface.pump()
                if bridge.viewportStatus != "preparing":
                    break
            if bridge.viewportStatus != "live":
                raise SystemExit(f"Viewport did not go live: {bridge.viewportStatus} {bridge.viewportError}")

        if args.object:
            bridge.selectObject(args.object)
        def analysed():
            """An evaluator that analyses in the background (``analysing``) has landed its answers."""
            for _ in range(6000):
                if not getattr(controller.evaluator, "analysing", False):
                    return
                app.processEvents()
                time.sleep(0.01)
            raise SystemExit("Background analysis did not finish")

        if args.clip:
            clip = next(c for c in controller.adapter.recorded_clips() if c.id == "clip:" + args.clip)
            from dataclasses import replace
            if mode == "waveform_ribbon":
                from ui.studio.waveform_recorded_inputs import extract, to_inputs
                data = extract(clip.description, store.values, seconds=12.0)
                inputs = to_inputs(data, replace(clip, duration=float(data["duration"])))
            else:
                # The mode's own clip loader (its out-of-process worker), waited for on the event loop.
                landed = []
                job = controller.adapter.start_clip_load(clip, store.values, lambda r, e="": landed.append((r, e)))
                for _ in range(12000):
                    if landed:
                        break
                    app.processEvents()
                    time.sleep(0.01)
                if not landed or landed[0][1]:
                    raise SystemExit(f"Clip analysis failed: {landed[0][1] if landed else 'timeout'} ({job})")
                inputs = landed[0][0]
            controller.evaluator.add_recorded(inputs)
            controller.select_fixture(clip.id)
            if args.source_time is not None:
                from widgets.spotify_visualizer.compact_clip import first_timestamp_us
                first = first_timestamp_us(clip.description) / 1e6
                args.time = args.source_time + first - float(inputs._origin)
                record["studio_time"] = args.time
        else:
            controller.select_fixture(args.fixture)
            # The default recorded clip still analysing in the background would replace the chosen fixture when
            # it lands; this capture asked for the fixture.
            for job in tuple(controller._clip_jobs.values()):
                job.cancel()
            controller._clip_jobs.clear()
        controller.seek(args.time)
        settle()
        controller.evaluator.evaluate(controller.transport.time, controller.evaluation_values())
        analysed()
        controller._invalidate()
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
        if args.brush:
            record["brush"] = _paint_stroke(controller, surface, args)
        workspaces = args.workspaces.split(",") if args.workspaces else [
            w.id for w in controller.session.schema.workspaces]
        for workspace in workspaces:
            bridge.setWorkspace(workspace)
            if mode == "waveform_ribbon" and workspace == "appearance":
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
            if bridge.handles.get("handles"):
                record.setdefault("handles", {})[workspace] = [h["id"] for h in bridge.handles["handles"]]
        (args.output / f"studio_capture{suffix}.json").write_text(
            json.dumps(record, indent=1), encoding="utf-8")
        print(json.dumps(record, indent=1))
    finally:
        controller.close()
        app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
