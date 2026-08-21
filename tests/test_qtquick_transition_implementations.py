"""C3 gates for lazy internal transition renderer implementations."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from rendering.gl_programs.blockspin_program import (
    BLOCK_SPIN_BOX_VERTEX_COUNT,
    BLOCK_SPIN_BOX_VERTICES,
    BLOCK_SPIN_FRAGMENT_SOURCE,
    BLOCK_SPIN_QUICK_VERTEX_SOURCE,
    BLOCK_SPIN_VERTEX_STRIDE_FLOATS,
    block_spin_progress,
    block_spin_specular_band_center,
)
from rendering.quick.transitions.implementation_registry import (
    resolve_quick_transition_renderer,
)
from rendering.quick.transitions.implementations.block_flip import (
    _BLOCK_FLIP_FRAGMENT_SOURCE,
    _block_flip_direction_vector,
    _block_flip_grid,
)
from rendering.quick.transitions.implementations.block_spins import (
    _block_spin_direction_state,
)
from rendering.quick.transitions.implementations.slide import (
    _SLIDE_FRAGMENT_SOURCE,
    _slide_direction_vector,
    _slide_partition_sample,
)
from rendering.quick.transitions.implementations.wipe import _wipe_mode
from rendering.quick.transitions.render_host import QuickTransitionRenderHost


ROOT = Path(__file__).resolve().parents[1]
_ALL_QUICK_TRANSITION_IDS = (
    "crossfade",
    "slide",
    "wipe",
    "warp_dissolve",
    "block_flip",
    "block_spins",
    "blinds",
    "diffuse",
    "ripple",
    "crumble",
    "particle",
    "burn",
)


def _probe(source: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-c", source],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def test_quick_implementation_catalog_does_not_import_renderer_modules():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import (
    iter_quick_transition_implementations,
)

entries = iter_quick_transition_implementations()
loaded = sorted(
    name for name in sys.modules
    if name.startswith("rendering.quick.transitions.implementations.")
)
shader_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.gl_programs.") and name.endswith("_program")
)
print(json.dumps({
    "ids": [entry.transition_id for entry in entries],
    "loaded": loaded,
    "shader_modules": shader_modules,
}))
"""
    )

    assert report == {
        "ids": list(_ALL_QUICK_TRANSITION_IDS),
        "loaded": [],
        "shader_modules": [],
    }


def test_importing_quick_runtime_keeps_renderer_implementations_dormant():
    report = _probe(
        """
import json
import sys
from rendering.quick.runtime import QuickDisplayRuntime

implementation_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.quick.transitions.implementations.")
)
shader_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.gl_programs.") and name.endswith("_program")
)
print(json.dumps({
    "runtime": QuickDisplayRuntime.__name__,
    "implementation_modules": implementation_modules,
    "shader_modules": shader_modules,
}))
"""
    )

    assert report == {
        "runtime": "QuickDisplayRuntime",
        "implementation_modules": [],
        "shader_modules": [],
    }


def test_disabled_resolution_keeps_transition_implementations_dormant():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import (
    resolve_quick_transition_renderer,
)

transition_ids = (
    "crossfade",
    "slide",
    "wipe",
    "warp_dissolve",
    "block_flip",
    "block_spins",
    "blinds",
    "diffuse",
    "ripple",
    "crumble",
    "particle",
    "burn",
)
resolved = [
    resolve_quick_transition_renderer(
        transition_id,
        enabled_transition_ids=frozenset(),
    )
    for transition_id in transition_ids
]
loaded = sorted(
    name for name in sys.modules
    if name.startswith("rendering.quick.transitions.implementations.")
)
print(json.dumps({
    "resolved": any(item is not None for item in resolved),
    "loaded": loaded,
}))
"""
    )

    assert report == {"resolved": False, "loaded": []}


def test_enabled_resolution_imports_only_block_spins_surface():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import (
    resolve_quick_transition_renderer,
)

renderer = resolve_quick_transition_renderer(
    "block_spins",
    enabled_transition_ids=frozenset({"block_spins"}),
)
implementation_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.quick.transitions.implementations.")
)
shader_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.gl_programs.") and name.endswith("_program")
)
print(json.dumps({
    "renderer": type(renderer).__name__,
    "implementation_modules": implementation_modules,
    "shader_modules": shader_modules,
}))
"""
    )

    assert report == {
        "renderer": "QuickBlockSpinsRenderer",
        "implementation_modules": [
            "rendering.quick.transitions.implementations.block_spins"
        ],
        "shader_modules": [
            "rendering.gl_programs.blockspin_program",
        ],
    }


def test_enabled_resolution_imports_only_crossfade_surface():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import (
    resolve_quick_transition_renderer,
)

renderer = resolve_quick_transition_renderer(
    "crossfade",
    enabled_transition_ids=frozenset({"crossfade"}),
)
implementation_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.quick.transitions.implementations.")
)
shader_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.gl_programs.") and name.endswith("_program")
)
print(json.dumps({
    "renderer": type(renderer).__name__,
    "implementation_modules": implementation_modules,
    "shader_modules": shader_modules,
}))
"""
    )

    assert report == {
        "renderer": "QuickCrossfadeRenderer",
        "implementation_modules": [
            "rendering.quick.transitions.implementations.crossfade"
        ],
        "shader_modules": [
            "rendering.gl_programs.base_program",
            "rendering.gl_programs.crossfade_program",
        ],
    }


def test_enabled_resolution_imports_only_slide_surface():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import (
    resolve_quick_transition_renderer,
)

renderer = resolve_quick_transition_renderer(
    "slide",
    enabled_transition_ids=frozenset({"slide"}),
)
implementation_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.quick.transitions.implementations.")
)
shader_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.gl_programs.") and name.endswith("_program")
)
print(json.dumps({
    "renderer": type(renderer).__name__,
    "implementation_modules": implementation_modules,
    "shader_modules": shader_modules,
}))
"""
    )

    assert report == {
        "renderer": "QuickSlideRenderer",
        "implementation_modules": [
            "rendering.quick.transitions.implementations.slide"
        ],
        "shader_modules": [],
    }


def test_enabled_resolution_imports_only_wipe_surface():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import (
    resolve_quick_transition_renderer,
)

renderer = resolve_quick_transition_renderer(
    "wipe",
    enabled_transition_ids=frozenset({"wipe"}),
)
implementation_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.quick.transitions.implementations.")
)
shader_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.gl_programs.") and name.endswith("_program")
)
print(json.dumps({
    "renderer": type(renderer).__name__,
    "implementation_modules": implementation_modules,
    "shader_modules": shader_modules,
}))
"""
    )

    assert report == {
        "renderer": "QuickWipeRenderer",
        "implementation_modules": [
            "rendering.quick.transitions.implementations.wipe"
        ],
        "shader_modules": [
            "rendering.gl_programs.base_program",
            "rendering.gl_programs.wipe_program",
        ],
    }


def test_enabled_resolution_imports_only_warp_surface():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import (
    resolve_quick_transition_renderer,
)

renderer = resolve_quick_transition_renderer(
    "warp_dissolve",
    enabled_transition_ids=frozenset({"warp_dissolve"}),
)
implementation_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.quick.transitions.implementations.")
)
shader_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.gl_programs.") and name.endswith("_program")
)
print(json.dumps({
    "renderer": type(renderer).__name__,
    "implementation_modules": implementation_modules,
    "shader_modules": shader_modules,
}))
"""
    )

    assert report == {
        "renderer": "QuickWarpRenderer",
        "implementation_modules": [
            "rendering.quick.transitions.implementations.warp"
        ],
        "shader_modules": [
            "rendering.gl_programs.base_program",
            "rendering.gl_programs.warp_program",
        ],
    }


def test_enabled_resolution_imports_only_block_flip_surface():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import (
    resolve_quick_transition_renderer,
)

renderer = resolve_quick_transition_renderer(
    "block_flip",
    enabled_transition_ids=frozenset({"block_flip"}),
)
implementation_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.quick.transitions.implementations.")
)
shader_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.gl_programs.") and name.endswith("_program")
)
print(json.dumps({
    "renderer": type(renderer).__name__,
    "implementation_modules": implementation_modules,
    "shader_modules": shader_modules,
}))
"""
    )

    assert report == {
        "renderer": "QuickBlockFlipRenderer",
        "implementation_modules": [
            "rendering.quick.transitions.implementations.block_flip"
        ],
        "shader_modules": [],
    }


@pytest.mark.parametrize(
    ("direction", "vector"),
    (
        ("left", (1.0, 0.0)),
        ("right", (-1.0, 0.0)),
        ("up", (0.0, -1.0)),
        ("down", (0.0, 1.0)),
        ("diag_tl_br", (1.0, 1.0)),
        ("diag_tr_bl", (-1.0, 1.0)),
    ),
)
def test_block_flip_preserves_cardinal_and_diagonal_directions(
    direction,
    vector,
):
    assert _block_flip_direction_vector(direction) == vector


def test_block_flip_requires_resolved_settings_owned_grid_and_direction():
    assert _block_flip_grid({"cols": 5, "rows": 7}) == (5, 7)
    with pytest.raises(ValueError, match="requires resolved integer parameter 'cols'"):
        _block_flip_grid({"rows": 7})
    with pytest.raises(ValueError, match="cols must be between 2 and 25"):
        _block_flip_grid({"cols": 1, "rows": 7})
    with pytest.raises(ValueError, match="unknown resolved Block Puzzle Flip"):
        _block_flip_direction_vector("Random")


def test_block_flip_shader_is_strip_slab_authoritative_with_clean_endpoints():
    assert "if (t <= 0.0)" in _BLOCK_FLIP_FRAGMENT_SOURCE
    assert "if (t >= 1.0)" in _BLOCK_FLIP_FRAGMENT_SOURCE
    assert "stripCount" in _BLOCK_FLIP_FRAGMENT_SOURCE
    assert "faceScale" in _BLOCK_FLIP_FRAGMENT_SOURCE
    assert "showsNewFace" in _BLOCK_FLIP_FRAGMENT_SOURCE
    assert "cellIndex" not in _BLOCK_FLIP_FRAGMENT_SOURCE
    assert "hash1" not in _BLOCK_FLIP_FRAGMENT_SOURCE


@pytest.mark.parametrize(
    ("direction", "state"),
    (
        ("left", (0, 1.0)),
        ("right", (0, -1.0)),
        ("up", (1, 1.0)),
        ("down", (1, -1.0)),
        ("diag_tl_br", (2, 1.0)),
        ("diag_tr_bl", (3, -1.0)),
    ),
)
def test_block_spins_preserves_all_authored_axis_and_spin_directions(
    direction,
    state,
):
    assert _block_spin_direction_state(direction) == state


def test_block_spins_rejects_an_unresolved_random_direction():
    with pytest.raises(ValueError, match="unknown resolved 3D Block Spins"):
        _block_spin_direction_state("Random")


def test_block_spins_owns_a_real_thin_box_mesh_without_quad_fallback():
    assert BLOCK_SPIN_BOX_VERTEX_COUNT == 36
    assert len(BLOCK_SPIN_BOX_VERTICES) == (
        BLOCK_SPIN_BOX_VERTEX_COUNT * BLOCK_SPIN_VERTEX_STRIDE_FLOATS
    )
    positions = tuple(
        BLOCK_SPIN_BOX_VERTICES[index : index + 3]
        for index in range(
            0,
            len(BLOCK_SPIN_BOX_VERTICES),
            BLOCK_SPIN_VERTEX_STRIDE_FLOATS,
        )
    )
    assert {position[2] for position in positions} == {0.0, -0.05}
    renderer_source = (
        ROOT
        / "rendering"
        / "quick"
        / "transitions"
        / "implementations"
        / "block_spins.py"
    ).read_text(encoding="utf-8")
    assert "gl.GL_TRIANGLES" in renderer_source
    assert "BLOCK_SPIN_BOX_VERTEX_COUNT" in renderer_source
    assert "box_vao and" not in renderer_source


def test_block_spins_keeps_linear_run_input_and_authored_cubic_spin_timing():
    assert block_spin_progress(0.0) == 0.0
    assert block_spin_progress(0.25) == pytest.approx(0.0625)
    assert block_spin_progress(0.5) == pytest.approx(0.5)
    assert block_spin_progress(0.75) == pytest.approx(0.9375)
    assert block_spin_progress(1.0) == 1.0


def test_block_spins_opposite_directions_move_side_highlight_opposite_ways():
    assert block_spin_specular_band_center(0.25, 1.0) == pytest.approx(0.295)
    assert block_spin_specular_band_center(0.25, -1.0) == pytest.approx(0.705)
    assert block_spin_specular_band_center(0.75, 1.0) == pytest.approx(0.705)
    assert block_spin_specular_band_center(0.75, -1.0) == pytest.approx(0.295)
    assert "uSpecDirection < 0.0" in BLOCK_SPIN_FRAGMENT_SOURCE
    assert "? 1.0 - timeline" in BLOCK_SPIN_FRAGMENT_SOURCE
    renderer_source = (
        ROOT
        / "rendering"
        / "quick"
        / "transitions"
        / "implementations"
        / "block_spins.py"
    ).read_text(encoding="utf-8")
    assert 'uniforms["uSpecDirection"], spin_direction' in renderer_source


def test_block_spins_shader_uses_quick_geometry_depth_and_authored_face_uvs():
    assert "localPosition" in BLOCK_SPIN_QUICK_VERTEX_SOURCE
    assert "uMatrix * vec4(localPosition" in BLOCK_SPIN_QUICK_VERTEX_SOURCE
    assert "projected.z = -position.z" in BLOCK_SPIN_QUICK_VERTEX_SOURCE
    assert "flat out int vFaceKind" in BLOCK_SPIN_QUICK_VERTEX_SOURCE
    assert "backUv = vec2(1.0 - vUv.x, 1.0 - vUv.y)" in (
        BLOCK_SPIN_FRAGMENT_SOURCE
    )
    assert "backUv = vec2(vUv.x, vUv.y)" in BLOCK_SPIN_FRAGMENT_SOURCE
    assert "backUv = vec2(1.0 - vUv.y, vUv.x)" in (
        BLOCK_SPIN_FRAGMENT_SOURCE
    )
    assert "backUv = vec2(vUv.y, 1.0 - vUv.x)" in (
        BLOCK_SPIN_FRAGMENT_SOURCE
    )
    assert "u_blockRect" not in BLOCK_SPIN_QUICK_VERTEX_SOURCE


@pytest.mark.parametrize(
    ("direction", "vector"),
    (
        ("left", (-1.0, 0.0)),
        ("right", (1.0, 0.0)),
        ("up", (0.0, -1.0)),
        ("down", (0.0, 1.0)),
    ),
)
def test_slide_supports_the_four_product_cardinal_directions(direction, vector):
    assert _slide_direction_vector(direction) == vector


def test_slide_defaults_left_and_rejects_non_cardinal_directions():
    assert _slide_direction_vector(None) == (-1.0, 0.0)
    assert _slide_direction_vector("LEFT") == (-1.0, 0.0)
    with pytest.raises(ValueError, match="unknown canonical Slide direction"):
        _slide_direction_vector("Random")


@pytest.mark.parametrize("direction", ("left", "right", "up", "down"))
def test_slide_partition_has_full_coverage_at_authored_and_missed_frame_samples(
    direction,
):
    progress_values = {
        0.0,
        1.0,
        0.5,
        0.017,
        0.113,
        0.347,
        0.511,
        0.829,
        0.997,
        *(index / 257.0 for index in range(1, 257)),
    }
    horizontal = direction in {"left", "right"}
    for progress in sorted(progress_values):
        owners: list[str] = []
        for pixel in range(257):
            axis = (pixel + 0.5) / 257.0
            coordinate = (axis, 0.371) if horizontal else (0.371, axis)
            owner, local_uv = _slide_partition_sample(
                direction,
                progress,
                coordinate,
            )
            owners.append(owner)
            assert owner in {"source", "destination"}
            assert all(0.0 <= component < 1.0 for component in local_uv)

        assert len(owners) == 257
        if progress == 0.0:
            assert set(owners) == {"source"}
        elif progress == 1.0:
            assert set(owners) == {"destination"}


def test_slide_shader_uses_one_shared_sample_without_a_background_branch():
    assert "vec2 localUv = fract(uv - u_direction * t);" in _SLIDE_FRAGMENT_SOURCE
    assert "texture(uOldTex, localUv)" in _SLIDE_FRAGMENT_SOURCE
    assert "texture(uNewTex, localUv)" in _SLIDE_FRAGMENT_SOURCE
    assert "FragColor = mix(oldColor, newColor, destinationOwns);" in (
        _SLIDE_FRAGMENT_SOURCE
    )
    assert "vec4(0.0" not in _SLIDE_FRAGMENT_SOURCE


@pytest.mark.parametrize(
    ("direction", "mode"),
    (
        ("left_to_right", 0),
        ("right_to_left", 1),
        ("top_to_bottom", 2),
        ("bottom_to_top", 3),
        ("diag_tl_br", 4),
        ("diag_tr_bl", 5),
    ),
)
def test_wipe_modes_preserve_all_canonical_direction_semantics(direction, mode):
    assert _wipe_mode(direction) == mode


def test_wipe_mode_defaults_left_to_right_and_rejects_unknown_direction():
    assert _wipe_mode(None) == 0
    assert _wipe_mode("LEFT_TO_RIGHT") == 0
    with pytest.raises(ValueError, match="unknown canonical Wipe direction"):
        _wipe_mode("Random")


def test_common_runtime_owners_have_no_transition_specific_dispatch_tree():
    paths = (
        ROOT / "rendering" / "quick" / "render" / "background_node.py",
        ROOT / "rendering" / "quick" / "transitions" / "render_host.py",
        ROOT / "rendering" / "quick" / "transitions" / "controller.py",
        ROOT / "rendering" / "quick" / "scene_controller.py",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "transition_id ==" not in source
    assert "transition_id in (" not in source
    assert "GLCompositorWidget" not in source
    assert "DisplayWidget" not in source


class _OwnedRenderer:
    transition_id = "crossfade"

    def __init__(self) -> None:
        self.live = True
        self.release_count = 0

    @property
    def has_resources(self) -> bool:
        return self.live

    def render(self, _frame) -> None:
        raise AssertionError("disabled renderer must not draw")

    def release_resources(self) -> None:
        self.release_count += 1
        self.live = False


def test_disabling_releases_resolved_surface_and_reenable_resolves_cleanly():
    host = QuickTransitionRenderHost(enabled_transition_ids={"crossfade"})
    owned = _OwnedRenderer()
    host._implementations["crossfade"] = owned  # type: ignore[assignment]

    host.set_enabled_transition_ids(set())

    assert owned.release_count == 1
    assert host.resolved_transition_ids == frozenset()
    assert host.enabled_transition_ids == frozenset()
    assert resolve_quick_transition_renderer(
        "crossfade",
        enabled_transition_ids=host.enabled_transition_ids,
    ) is None

    host.set_enabled_transition_ids({"crossfade"})
    replacement = resolve_quick_transition_renderer(
        "crossfade",
        enabled_transition_ids=host.enabled_transition_ids,
    )
    assert replacement is not None
    assert type(replacement).__name__ == "QuickCrossfadeRenderer"
