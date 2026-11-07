"""Offscreen real-GL strips of Bubble on several card shapes, for frame-by-frame motion review.

Replays a recording through the production logical path at each committed extent
(``replay_clip(viewport_extent=...)``), renders the published Quick snapshots with the production
``QuickVisualizerRenderHost`` into an offscreen framebuffer (no window is shown), and writes:

* ``<prefix>_cards.png``  - one row per time step, one full card per column (scaled to a common height);
* ``<prefix>_window.png`` - the same steps, each card cropped to a canonical-card-sized window at its
  centre and scaled by the world's zoom, so every column shows bubbles at the same size: equal
  per-step travel across columns means equal perceived speed.

Usage::

    python -m tools.visualizer_replay.bubble_shape_strip --out-dir .artifacts/evidence/visualizers/bubble/shape_invariance/<YYYYMMDD>_<label>
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .bubble_shape_invariance import CANONICAL, RECORDINGS, load_clip
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
if str(_Path(__file__).resolve().parents[2]) not in _sys.path:
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from tools import artifact_paths  # noqa: E402
from tools import evidence_media  # noqa: E402

SHAPES = {"baseline": CANONICAL, "tall": (280.0, 1200.0), "wide": (2400.0, 300.0)}


def _matrix(width: int, height: int):
    return (2 / width, 0, 0, 0, 0, 2 / height, 0, 0, 0, 0, 1, 0, -1, -1, 0, 1)


class _OffscreenTarget:
    def __init__(self, width: int, height: int):
        from OpenGL import GL as gl
        from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat

        from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost

        fmt = QSurfaceFormat()
        fmt.setRenderableType(QSurfaceFormat.OpenGL)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        fmt.setVersion(4, 6)
        self.gl = gl
        self.context = QOpenGLContext()
        self.context.setFormat(fmt)
        if not self.context.create():
            raise RuntimeError("OpenGL 4.6 context unavailable")
        self.surface = QOffscreenSurface()
        self.surface.setFormat(fmt)
        self.surface.create()
        if not self.surface.isValid() or not self.context.makeCurrent(self.surface):
            raise RuntimeError("offscreen OpenGL context unavailable")
        self.size = (width, height)
        self.color = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.color)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
        self.fbo = gl.glGenFramebuffers(1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, self.color, 0)
        if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("offscreen framebuffer incomplete")
        self.host = QuickVisualizerRenderHost()

    def render(self, snapshot, width: int, height: int):
        from PIL import Image

        gl = self.gl
        gl.glViewport(0, 0, width, height)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        if self.host.render(snapshot=snapshot, viewport=(0, 0, width, height),
                            logical_size=(float(width), float(height)),
                            matrix_values=_matrix(width, height)) != "bubble":
            raise RuntimeError("host did not render Bubble")
        data = bytes(gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE))
        return Image.frombytes("RGBA", (width, height), data).transpose(Image.Transpose.FLIP_TOP_BOTTOM).convert("RGB")

    def release(self):
        self.host.release_resources()
        self.gl.glDeleteFramebuffers(1, [self.fbo])
        self.gl.glDeleteTextures([self.color])
        self.context.doneCurrent()
        self.surface.destroy()


def main() -> None:
    from PIL import Image, ImageDraw
    from PySide6.QtGui import QGuiApplication

    from .driver import replay_clip

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clip", default="balanced")
    parser.add_argument("--recordings", type=Path, default=RECORDINGS)
    parser.add_argument("--preset", type=int, default=0)
    parser.add_argument("--start", type=float, default=8.0, help="seconds into the clip")
    parser.add_argument("--step-frames", type=int, default=9, help="logical frames between rows")
    parser.add_argument("--rows", type=int, default=8)
    parser.add_argument("--out-dir", type=artifact_paths.evidence_arg, required=True)
    parser.add_argument("--prefix", default="")
    args = parser.parse_args()
    evidence_media.redirect_output(args, "out_dir", "bubble_shape_strip")
    QGuiApplication.instance() or QGuiApplication([])
    clip = load_clip(args.clip, fixture=False, seconds=args.start + args.rows * args.step_frames / 90.0 + 1.0,
                     recordings=args.recordings)
    first = next(index for index, frame in enumerate(clip.frames)
                 if frame.timestamp_us - clip.frames[0].timestamp_us >= args.start * 1e6)
    wanted = [first + row * args.step_frames for row in range(args.rows)]
    target = _OffscreenTarget(int(max(w for w, _ in SHAPES.values())), int(max(h for _, h in SHAPES.values())))
    cards, windows = {}, {}
    try:
        for name, extent in SHAPES.items():
            result = replay_clip(clip, "bubble", preset=args.preset, viewport_extent=extent, snapshots_at=wanted)
            width, height = int(extent[0]), int(extent[1])
            cards[name], windows[name] = [], []
            for index in wanted:
                snapshot = result["snapshots"][index]
                zoom = float(getattr(snapshot.logical.mode_state, "world_scale", 1.0))
                image = target.render(snapshot, width, height)
                cards[name].append(image)
                crop_w, crop_h = min(width, CANONICAL[0] * zoom), min(height, CANONICAL[1] * zoom)
                left, top = (width - crop_w) / 2.0, (height - crop_h) / 2.0
                window = image.crop((round(left), round(top), round(left + crop_w), round(top + crop_h)))
                windows[name].append(window.resize((round(crop_w / zoom), round(crop_h / zoom))))
    finally:
        target.release()
    prefix = args.prefix or f"preset{args.preset}"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    tile_h = 240
    for kind, tiles in (("cards", cards), ("window", windows)):
        columns = list(SHAPES)
        scaled = {name: [im.resize((max(1, round(im.width * tile_h / im.height)), tile_h)) if kind == "cards" else im
                         for im in tiles[name]] for name in columns}
        widths = [max(im.width for im in scaled[name]) for name in columns]
        row_h = max(im.height for name in columns for im in scaled[name]) + 4
        sheet = Image.new("RGB", (sum(widths) + 4 * len(columns), row_h * len(wanted)), (40, 40, 40))
        for row, index in enumerate(wanted):
            x = 0
            for column, name in enumerate(columns):
                image = scaled[name][row]
                sheet.paste(image, (x, row * row_h))
                ImageDraw.Draw(sheet).text((x + 4, row * row_h + 2),
                                           f"{name} t={clip.frames[index].timestamp_us / 1e6:.2f}s", fill=(255, 255, 0))
                x += widths[column] + 4
        path = args.out_dir / f"{prefix}_{kind}.png"
        sheet.save(path)
        print(path)


if __name__ == "__main__":
    main()
    evidence_media.finish(0)
