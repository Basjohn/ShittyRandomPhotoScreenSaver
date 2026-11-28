"""Lazy Quick renderer for Volumetric Dissolve: the old picture bursts into particles and mist
while the new one resolves through it."""

from __future__ import annotations

import functools
from collections.abc import Mapping


from rendering.gl_programs.scene3d import scene3d_request_samples
from rendering.gl_programs.volumetric_dissolve_options import VOLUMETRIC_DIRECTIONS, VOLUMETRIC_PARTICLE_SIZE_RANGE
from rendering.gl_programs.volumetric_dissolve_program import (
    VOLUMETRIC_FRAME_BLOCK,
    VOLUMETRIC_HOOKS,
    VOLUMETRIC_VERTICES,
    volumetric_backdrop_program,
    volumetric_grid,
    volumetric_particle_program,
)
from ..directions import direction_vector
from ..native_scene import (QUAD_MESH, NativeScene, NativeScenePass, NativeScenePasses, NativeScenePopulation,
                            eased_show, native_one_block, population_packs, population_values)

_DIRECTION_CODES = frozenset(VOLUMETRIC_DIRECTIONS.values())

# N5.2f: the native scene's passes, each with the frame block merged into its pass block, and its population (the
# frame block merged into the count and scatter packs' dispatch block); the particles are blended premultiplied over,
# the alpha kept (``blend_scope``). The copies are the two photo environments (Python's roles destination and source).
# Each is built on first use (the hitch rows, 22 Nov): ``WARM_PIECES`` lists them in the order a run needs them, one
# warm-up unit each.
_FRAME = VOLUMETRIC_FRAME_BLOCK.name
_OVER = (("add", "one", "one_minus_src_alpha"), ("add", "zero", "one"))


@functools.cache
def _backdrop_pass() -> NativeScenePass:
    vertex, fragment, _block = volumetric_backdrop_program()
    return NativeScenePass("backdrop", *native_one_block((vertex, fragment), _FRAME), QUAD_MESH, "triangle_strip", 4,
                           samplers=(("uOldTex", "old"), ("uNewTex", "new"), ("uNewCopy", "environment"),
                                     ("uOldCopy", "source_environment")))


@functools.cache
def _particle_pass() -> NativeScenePass:
    vertex, fragment, _block = volumetric_particle_program()
    return NativeScenePass("particles", *native_one_block((vertex, fragment), _FRAME), None, "triangle_strip",
                           VOLUMETRIC_VERTICES, samplers=(("uOldTex", "old"), ("uOldCopy", "source_environment")),
                           blend=_OVER)


@functools.cache
def _scene_passes() -> tuple[NativeScenePass, ...]:
    return (_backdrop_pass(), _particle_pass())


@functools.cache
def _population() -> NativeScenePopulation:
    count, scatter = population_packs(VOLUMETRIC_HOOKS, _FRAME)
    return NativeScenePopulation("particles", VOLUMETRIC_HOOKS, _FRAME, "particles", count, scatter)


WARM_PIECES = (volumetric_backdrop_program, _backdrop_pass, volumetric_particle_program, _particle_pass, _scene_passes,
               _population)


def volumetric_parameters(parameters: Mapping[str, object]) -> tuple[int, int, float, float]:
    """The resolved seed, particle size, mist and depth, validated before any GL state changes."""
    seed, size = parameters.get("seed"), parameters.get("particle_size")
    mist, depth = parameters.get("mist"), parameters.get("depth")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 65535:
        raise ValueError("Volumetric Dissolve seed must be an integer between 1 and 65535")
    low, high = VOLUMETRIC_PARTICLE_SIZE_RANGE
    if isinstance(size, bool) or not isinstance(size, int) or not low <= size <= high:
        raise ValueError(f"Volumetric Dissolve particle size must be an integer between {low} and {high}")
    for name, value in (("mist", mist), ("depth", depth)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"Volumetric Dissolve {name} must be between 0 and 1")
    return seed, size, float(mist), float(depth)


def volumetric_sweep(direction: object) -> tuple[tuple[float, float], float]:
    """(unit sweep in item space, radial flag) for a resolved direction."""
    if direction not in _DIRECTION_CODES:
        raise ValueError(f"unknown resolved Volumetric Dissolve direction: {direction!r}")
    if direction == "center_out":
        return (0.0, 1.0), 1.0
    return direction_vector(direction), 0.0


class QuickVolumetricDissolveRenderer(NativeScenePasses):
    transition_id = "volumetric_dissolve"
    scene_pixels = True                  # N5.2f: the particle grid is of the item's device pixels

    # ------------------------------------------------------------------------------- N5.2f: the scene, one owner

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        return _scene_passes()

    @classmethod
    def native_scene_populations(cls) -> tuple[NativeScenePopulation, ...]:
        return (_population(),)

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        parameters = run.request.parameter_dict()
        volumetric_parameters(parameters)
        return NativeScene(_scene_passes(), (), scene3d_request_samples(parameters), True, source_environment=True,
                           populations=(_population(),))

    def scene_show(self, run, sample) -> int:
        return eased_show(max(0.0, min(1.0, float(sample.eased_progress))))

    def scene_values(self, run, sample, logical_size: tuple[float, float],
                     pixels: tuple[int, int] | None = None) -> dict[str, object]:
        """The frame block's values (``frame_values``, one owner with ``render``) and the population's over the item's
        device ``pixels``."""
        if pixels is None:
            pixels = (round(logical_size[0]), round(logical_size[1]))
        progress = max(0.0, min(1.0, float(sample.eased_progress)))
        seed, size, mist, depth = volumetric_parameters(run.request.parameter_dict())
        sweep, radial = volumetric_sweep(run.request.direction)
        columns, rows, _size = volumetric_grid(int(pixels[0]), int(pixels[1]), size)
        values = self.frame_values(progress, seed, mist, depth, sweep, radial, columns, rows, logical_size)
        values.update(population_values(_population(), columns * rows, VOLUMETRIC_VERTICES))
        return values

    @staticmethod
    def frame_values(progress: float, seed: int, mist: float, depth: float, sweep, radial: float, columns: int,
                     rows: int, logical_size) -> dict[str, object]:
        return {"uGrid": (columns, rows), "uDirection": sweep, "uFrameSize": tuple(logical_size),
                "uProgress": progress, "uSeed": seed, "uDepth": depth, "uMist": mist, "uRadial": radial}

    # The photographs each program reads (bind_frame binds them); the copies' samplers are bound in the sources, the
    # quad's values are in each program's pass block and the rest in the frame block.
    _BACKDROP_SAMPLERS = ("uOldTex", "uNewTex")
    _PARTICLE_SAMPLERS = ("uOldTex",)


def create_transition_renderer() -> QuickVolumetricDissolveRenderer:
    return QuickVolumetricDissolveRenderer()
