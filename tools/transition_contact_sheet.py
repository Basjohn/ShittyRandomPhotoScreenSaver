"""Render deterministic transition frames through the production GL host.

No runtime timers or settings writes. This diagnostic creates one offscreen
context, checks exact endpoints/retirement and writes optional contact sheets.
Physical Quick multi-display/load acceptance remains a separate gate.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
from pathlib import Path
import random
import sys
from time import perf_counter

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def fixture_images(width: int, height: int):
    """Textured, nonblack test scenes expose UV discontinuity and image holes."""
    import numpy as np
    from PIL import Image, ImageDraw

    y, x = np.mgrid[0:height, 0:width]
    u, v = x / max(1, width-1), y / max(1, height-1)
    images = []
    for index in range(2):
        pixels = np.empty((height, width, 4), dtype=np.uint8)
        pixels[..., 0] = (45 + 135 * (1-v) + 30*np.sin(u*8+index)).clip(20, 245)
        pixels[..., 1] = (65 + 110 * (u if index else v)).clip(20, 245)
        pixels[..., 2] = (90 + 100 * (v if index else 1-u)).clip(20, 245)
        if index: pixels[..., :3] = pixels[..., [2, 0, 1]]
        pixels[..., 3] = 255
        image = Image.fromarray(pixels)
        draw = ImageDraw.Draw(image)
        sunx = width * (.76 if index else .23)
        suny = height * .28
        radius = min(width, height) * .09
        draw.ellipse((sunx-radius, suny-radius, sunx+radius, suny+radius), fill=(247, 221, 144, 255))
        for layer in range(3):
            points = [(0, height), (0, height*(.55+layer*.11))]
            for j in range(13):
                points.append((j*width/12, height*(.48+layer*.14 + .11*math.sin(j*1.9+index+layer))))
            points.append((width, height))
            color = ((48+layer*14, 62+layer*17, 112+layer*20, 255) if not index else
                     (35+layer*12, 116+layer*14, 101+layer*17, 255))
            draw.polygon(points, fill=color)
        # Fine linework distinguishes real tile translation from threshold reveal.
        for j in range(1, 12):
            draw.line((j*width/12, 0, j*width/12, height), fill=(217, 193, 166, 255), width=1)
        images.append(image)
    return tuple(images)


class TransitionCapture:
    def __init__(self, width: int, height: int, source=None, destination=None):
        import numpy as np
        from OpenGL import GL as gl
        from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext, QSurfaceFormat
        from rendering.quick.transitions.mesh_support import MeshResources
        from rendering.quick.transitions.render_host import QuickTransitionRenderHost

        self.width, self.height = width, height
        self.app = QGuiApplication.instance() or QGuiApplication([])
        fmt = QSurfaceFormat()
        fmt.setRenderableType(QSurfaceFormat.OpenGL)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        fmt.setVersion(4, 1)
        fmt.setDepthBufferSize(24)
        self.context = QOpenGLContext()
        self.context.setFormat(fmt)
        if not self.context.create(): raise RuntimeError("OpenGL 4.1 context unavailable")
        self.surface = QOffscreenSurface()
        self.surface.setFormat(self.context.format())
        self.surface.create()
        if not self.context.makeCurrent(self.surface): raise RuntimeError("offscreen GL admission failed")
        self.driver = gl.glGetString(gl.GL_RENDERER).decode()
        self.host = QuickTransitionRenderHost()
        self.mesh = MeshResources("transition diagnostic quad")
        self.vao, _ = self.mesh.mesh("quad", (0., 0., 1., 0., 0., 1., 1., 1.), (2,))
        fixtures = fixture_images(width, height)
        self.images = tuple(image.convert("RGBA").resize((width, height)) for image in
                            (source or fixtures[0], destination or fixtures[1]))
        self.textures = []
        for image in (*self.images, None):
            texture = int(gl.glGenTextures(1))
            self.textures.append(texture)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            for axis in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T): gl.glTexParameteri(gl.GL_TEXTURE_2D, axis, gl.GL_CLAMP_TO_EDGE)
            for filt in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER): gl.glTexParameteri(gl.GL_TEXTURE_2D, filt, gl.GL_LINEAR)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE,
                            None if image is None else np.asarray(image))
        self.fbo = int(gl.glGenFramebuffers(1))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, self.textures[2], 0)
        self.depth = int(gl.glGenRenderbuffers(1))
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self.depth)
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT24, width, height)
        gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_RENDERBUFFER, self.depth)
        if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("transition diagnostic framebuffer incomplete")

    def run(self, effect: str, *, seed: int = 713, direction=None, parameters=None):
        from rendering.quick.image_state import PresentationImage
        from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
        from rendering.quick.transitions.state import TransitionRequest, TransitionRun

        if effect == "slide":
            resolved_direction, resolved_params = "left", {"motion_style": "Perspective Push"}
        else:
            resolved = resolve_parameterized_phase_c_inputs(effect, {}, random_source=random.Random(seed))
            resolved_direction, resolved_params = resolved.direction, resolved.parameter_dict()
        resolved_params.update(parameters or {})
        images = [PresentationImage(str(index), "diagnostic", (self.width, self.height), 1.,
                                    (self.width, self.height), self.width*4, image.tobytes())
                  for index, image in enumerate(self.images)]
        request = TransitionRequest(0, effect, effect, False, 1000, direction or resolved_direction,
                                    resolved_params, *images)
        return TransitionRun.start(run_id=1, request=request, start_ns=0)

    def frame(self, run, progress: float):
        from rendering.quick.transitions.render_contract import QuickTransitionRenderFrame
        w, h = self.width, self.height
        return QuickTransitionRenderFrame(run, run.sample(round(progress*1e9)), (0, 0, w, h), (w, h),
                                          (2/w, 0, 0, 0, 0, -2/h, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1),
                                          self.vao, self.textures[0], self.textures[1])

    def render(self, run, progress: float):
        from OpenGL import GL as gl
        from PIL import Image
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(1., 0., 1., 1.)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        start = perf_counter()
        self.host.render(self.frame(run, progress))
        submit_ms = (perf_counter()-start)*1000
        pixels = gl.glReadPixels(0, 0, self.width, self.height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        image = Image.frombytes("RGBA", (self.width, self.height), bytes(pixels)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if gl.glGetError() != gl.GL_NO_ERROR: raise RuntimeError("transition GL error")
        return image, submit_ms

    def benchmark(self, run):
        """Bounded test-only GPU query; no runtime instrumentation or glFinish."""
        from OpenGL import GL as gl
        cpu, queries = [], []
        for index in range(12):
            query = int(gl.glGenQueries(1)[0])
            queries.append(query)
            gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
            start = perf_counter()
            self.host.render(self.frame(run, .15+.7*index/11))
            cpu.append((perf_counter()-start)*1000)
            gl.glEndQuery(gl.GL_TIME_ELAPSED)
        gpu = []
        try:
            for query in queries:
                value = ctypes.c_uint64()
                gl.glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(value))
                gpu.append(value.value/1e6)
        finally:
            gl.glDeleteQueries(len(queries), queries)
        return {"warm_cpu_submit_ms_max": max(cpu), "gpu_ms_max": max(gpu),
                "gpu_ms_mean": sum(gpu)/len(gpu)}

    def close(self):
        from OpenGL import GL as gl
        self.host.set_enabled_transition_ids(())
        if self.host.has_resources or self.host.resolved_transition_ids:
            raise RuntimeError("disabled transition retained resources")
        self.mesh.release_resources()
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glDeleteRenderbuffers(1, [self.depth])
        gl.glDeleteFramebuffers(1, [self.fbo])
        gl.glDeleteTextures(self.textures)
        self.context.doneCurrent()


def quick_smoke(args):
    """Reuse the existing threaded QQuickWindow lifecycle/telemetry harness.

    This checks real scene integration; the deterministic offscreen suite owns
    geometric/parameter/continuity discrimination, not this sparse readback.
    """
    from tools import qtquick_render_node_smoke as smoke
    from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs

    effect = args.effect
    if effect == "slide":
        direction, parameters = args.direction or "left", {"motion_style": "Perspective Push"}
    else:
        resolved = resolve_parameterized_phase_c_inputs(effect, {}, random_source=random.Random(args.seed))
        direction, parameters = args.direction or resolved.direction, resolved.parameter_dict()
    if effect not in smoke._TRANSITION_IDS:
        smoke._TRANSITION_IDS = (*smoke._TRANSITION_IDS, effect)
    smoke._TRANSITION_SMOKE_DIRECTIONS[effect] = (direction,)
    if direction is not None:
        smoke._TRANSITION_DIRECTION_CHOICES = tuple(sorted(set(smoke._TRANSITION_DIRECTION_CHOICES) | {direction}))
    smoke._TRANSITION_PALETTE_RGB[effect] = smoke._DIRECTIONAL_PALETTE_RGB
    smoke._TRANSITION_SMOKE_PARAMETERS[effect] = parameters
    smoke._DENSE_MIDPOINT_TRANSITION_IDS.add(effect)

    def mixed_image_domains(source, destination, midpoint, progress, direction):
        if not source or not destination or not midpoint or not 0.0 < progress < 1.0:
            return False
        colors = [smoke._argb_components(value)[1:] for value in midpoint]
        return (sum(b > r*1.25 for r, g, b in colors) >= 2
                and sum(r > b*1.25 for r, g, b in colors) >= 2)

    smoke._TRANSITION_MIDPOINT_ORACLES[effect] = mixed_image_domains
    if effect == "crumble":
        # The first telemetry sample (~35%) now sees the deliberately intact,
        # cracked wall. Require fissures there, then sample the later fall;
        # demanding an early destination reveal would erase the crack stage.
        def cracked_wall(source, destination, midpoint, progress, direction):
            if not source or not destination or not midpoint:
                return False
            colors = [smoke._argb_components(value)[1:] for value in midpoint]
            if progress < .43:
                fissures = sum(max(rgb) < 30 for rgb in colors)
                intact = sum(b > r*1.25 for r, g, b in colors)
                return fissures >= 3 and intact >= len(colors)*.6
            return mixed_image_domains(source, destination, midpoint, progress, direction)

        def crack_then_fall(source, destination, progresses, colors, direction):
            if len(progresses) != 2 or len(colors) != 2:
                return False
            if not mixed_image_domains(source, destination, colors[0], progresses[0], direction):
                return False
            late = [smoke._argb_components(value)[1:] for value in colors[1]]
            return progresses[1] >= .75 and sum(r > b*1.25 for r, g, b in late) >= len(late)*.8

        smoke._TRANSITION_MIDPOINT_ORACLES[effect] = cracked_wall
        smoke._TRANSITION_PIXEL_PROBES[effect] = (.55, .82)
        smoke._TRANSITION_PROBE_ORACLES[effect] = crack_then_fall
    args.output_dir.mkdir(parents=True, exist_ok=True)
    forwarded = ["--windows", str(args.windows), "--generations", "2", "--hide-show-cycles", "1",
                 "--size", f"{args.width}x{args.height}", "--phase-delay-ms", "500",
                 "--transition-id", effect, "--output", str(args.output_dir/f"{effect}_quick.json")]
    if direction is not None: forwarded.extend(("--transition-direction", direction))
    if effect == "slide": forwarded.extend(("--slide-motion-style", "Perspective Push"))
    return smoke.main(forwarded)


def main(argv=None):
    from PIL import Image, ImageDraw
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effect", default="glass_shatter")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--direction")
    parser.add_argument("--seed", type=int, default=713)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--quick-smoke", action="store_true")
    parser.add_argument("--windows", type=int, choices=(1, 2), default=2)
    parser.add_argument("--animate", action="store_true", help="also export a two-second, 60-frame WebP motion preview")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.quick_smoke:
        return quick_smoke(args)
    capture = TransitionCapture(args.width, args.height,
                                Image.open(args.source) if args.source else None,
                                Image.open(args.destination) if args.destination else None)
    report = {"effect": args.effect, "driver": capture.driver, "size": [args.width, args.height]}
    try:
        run = capture.run(args.effect, seed=args.seed, direction=args.direction)
        report["parameters"] = run.request.parameter_dict()
        report["direction"] = run.request.direction
        frames, timings = [], []
        times = (0., .12, .28, .45, .65, .82, .95, 1.)
        for progress in times:
            image, ms = capture.render(run, progress)
            frames.append(image)
            timings.append(ms)
        assert frames[0].tobytes() == capture.images[0].tobytes(), "source endpoint mismatch"
        assert frames[-1].tobytes() == capture.images[1].tobytes(), "destination endpoint mismatch"
        assert capture.render(run, .45)[0].tobytes() == frames[3].tobytes(), "nondeterministic render"
        assert frames[3].tobytes() not in (frames[0].tobytes(), frames[-1].tobytes()), "static midpoint"
        report.update(capture.benchmark(run))
        report["cold_submit_ms_max"] = max(timings)
        report["endpoints_exact"] = report["repeatable"] = True
        args.output_dir.mkdir(parents=True, exist_ok=True)
        thumb_w = min(args.width, 480)
        thumb_h = round(args.height*thumb_w/args.width)
        sheet = Image.new("RGB", (thumb_w*4, (thumb_h+26)*2), (18, 22, 31))
        draw = ImageDraw.Draw(sheet)
        for index, (progress, frame) in enumerate(zip(times, frames)):
            x, y = index % 4 * thumb_w, index // 4 * (thumb_h+26)
            sheet.paste(frame.resize((thumb_w, thumb_h)), (x, y+26))
            draw.text((x+8, y+7), f"{args.effect}  {progress:.0%}", fill=(235, 240, 248))
            frame.save(args.output_dir/f"{args.effect}_{progress:.2f}.png")
        sheet.save(args.output_dir/f"{args.effect}_contact.png")
        if args.animate:
            motion = [capture.render(run, index/59)[0] for index in range(60)]
            motion[0].save(args.output_dir/f"{args.effect}_motion.webp", save_all=True,
                           append_images=motion[1:], duration=34, loop=0, quality=85, method=4)
    finally:
        capture.close()
    report["retired"] = True
    (args.output_dir/f"{args.effect}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
