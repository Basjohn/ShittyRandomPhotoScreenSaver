"""Lazy Quick renderer for Depth Card Cascade: the picture's cards lift and slide past the viewer."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.depth_cascade_program import (
    CASCADE_CARDS_RANGE,
    CASCADE_DONE,
    CASCADE_FRAGMENT_SOURCE,
    CASCADE_SHADOW_FRAGMENT_SOURCE,
    CASCADE_SHADOW_VERTEX_SOURCE,
    CASCADE_VERTEX_SOURCE,
    cascade_cards,
)
from rendering.gl_programs.depth_cascade_options import CASCADE_SWEEP_VECTORS
from rendering.gl_programs.scene3d import scene3d_request_samples
from rendering.quick.scene3d.environment import PHOTO_ENVIRONMENT_PROGRAM, PhotoEnvironment
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from ..render_contract import QuickTransitionRenderFrame

_QUAD = (0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0)


def depth_cascade_parameters(parameters: Mapping[str, object]) -> tuple[int, float, bool, int]:
    """The resolved card count, gloss, shadows and seed, validated before any GL state changes."""
    cards, gloss = parameters.get("cards"), parameters.get("gloss")
    shadows, seed = parameters.get("shadows"), parameters.get("seed")
    low, high = CASCADE_CARDS_RANGE
    if isinstance(cards, bool) or not isinstance(cards, int) or not low <= cards <= high:
        raise ValueError(f"Depth Card Cascade needs a resolved card count between {low} and {high}")
    if isinstance(gloss, bool) or not isinstance(gloss, (int, float)) or not 0.0 <= float(gloss) <= 1.0:
        raise ValueError("Depth Card Cascade needs a resolved gloss between 0 and 1")
    if not isinstance(shadows, bool):
        raise ValueError("Depth Card Cascade needs a resolved shadows choice")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Depth Card Cascade needs a resolved seed")
    return cards, float(gloss), shadows, seed


class QuickDepthCascadeRenderer:
    transition_id = "depth_cascade"

    _CARD_UNIFORMS = ("uMatrix", "uItemSize", "uProgress", "uOldTex", "uNewTex", "uEnvironment", "uGloss")
    _SHADOW_UNIFORMS = ("uMatrix", "uItemSize", "uProgress")

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Depth Card Cascade")
        self._target = SceneTarget("Quick Depth Card Cascade")
        self._environment = PhotoEnvironment("Quick Depth Card Cascade")
        self._cards_key: tuple | None = None
        self._cards = (0, 0, 0)          # vao, vertex count, card count

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._target.has_resources or self._environment.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        sweep = CASCADE_SWEEP_VECTORS.get(str(frame.run.request.direction))
        if sweep is None:
            raise ValueError(f"unknown resolved Depth Card Cascade sweep: {frame.run.request.direction!r}")
        parameters = frame.run.request.parameter_dict()
        count, gloss, shadows, seed = depth_cascade_parameters(parameters)
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            # Every card has left the frame: the new picture.
            if progress >= CASCADE_DONE:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            width, height = frame.logical_size
            self._ensure_cards(seed, count, width / max(1e-6, height), sweep)
            samples = scene3d_request_samples(parameters)
            environment = self._environment.texture(frame, self._resources)
            if samples:
                with self._target.scope(frame, samples, self._resources):
                    self._draw(frame, progress, gloss, shadows, environment)
            else:
                self._draw(frame, progress, gloss, shadows, environment)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing (its cards are drawn from ``direction``
        only at render time, so the card mesh is built by the first frame: a few dozen floats)."""
        depth_cascade_parameters(parameters)
        samples = scene3d_request_samples(parameters)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM), (r, *PHOTO_ENVIRONMENT_PROGRAM),
                   (r, "cards", CASCADE_VERTEX_SOURCE, CASCADE_FRAGMENT_SOURCE),
                   (r, "shadows", CASCADE_SHADOW_VERTEX_SOURCE, CASCADE_SHADOW_FRAGMENT_SOURCE)]
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, False)]
        if not warm_programs(entries):
            return False
        return warm_run_resources(self._target, None, size, samples)

    def park(self) -> None:
        """Drop the per-run target, photo copy and cards; programs stay warm."""
        self._target.release()
        self._environment.release()
        self._drop_cards()

    def _ensure_cards(self, seed: int, count: int, aspect: float, sweep) -> None:
        key = (seed, count, round(aspect, 4), sweep)
        if key == self._cards_key:
            return
        self._drop_cards()
        cards = cascade_cards(seed, count, aspect, sweep)
        instances = tuple(value for card in cards for value in card)
        vao, vertices = self._resources.mesh("cards", _QUAD, (2,), instances=instances, instance_attributes=(4, 4))
        self._cards_key, self._cards = key, (vao, vertices, len(cards))

    def _drop_cards(self) -> None:
        self._resources.drop_mesh("cards")
        self._cards_key, self._cards = None, (0, 0, 0)

    def _draw(self, frame, progress: float, gloss: float, shadows: bool, environment: int) -> None:
        r = self._resources
        vao, vertices, count = self._cards
        r.draw_image(frame, frame.destination_texture_id)         # the new picture beneath the cards
        if shadows:
            program = r.program("shadows", CASCADE_SHADOW_VERTEX_SOURCE, CASCADE_SHADOW_FRAGMENT_SOURCE)
            uniforms = r.uniforms("shadows", self._SHADOW_UNIFORMS)
            bind_frame(program, uniforms, frame)
            gl.glUniform1f(uniforms["uProgress"], progress)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFuncSeparate(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ZERO, gl.GL_ONE)
            try:
                gl.glBindVertexArray(vao)
                gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, vertices, count)
            finally:
                gl.glDisable(gl.GL_BLEND)
        r.begin_depth(frame)
        program = r.program("cards", CASCADE_VERTEX_SOURCE, CASCADE_FRAGMENT_SOURCE)
        uniforms = r.uniforms("cards", self._CARD_UNIFORMS, required=False)
        bind_frame(program, uniforms, frame)
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform1f(uniforms["uGloss"], gloss)
        # Units 0 and 1 hold the photographs (bind_frame); the copy goes on 2 (restored by the host fence).
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glUniform1i(uniforms["uEnvironment"], 2)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glBindVertexArray(vao)
        gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, vertices, count)

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._environment.release, self._drop_cards,
                        self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(" | ".join(errors))


def create_transition_renderer() -> QuickDepthCascadeRenderer:
    return QuickDepthCascadeRenderer()
