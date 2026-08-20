"""C3 gates for lazy internal transition renderer implementations."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from rendering.quick.transitions.implementation_registry import (
    resolve_quick_transition_renderer,
)
from rendering.quick.transitions.implementations.slide import _slide_rects
from rendering.quick.transitions.render_host import QuickTransitionRenderHost


ROOT = Path(__file__).resolve().parents[1]


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
        "ids": ["crossfade", "slide"],
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

renderer = resolve_quick_transition_renderer(
    "crossfade",
    enabled_transition_ids=frozenset(),
)
slide = resolve_quick_transition_renderer(
    "slide",
    enabled_transition_ids=frozenset(),
)
loaded = sorted(
    name for name in sys.modules
    if name.startswith("rendering.quick.transitions.implementations.")
)
print(json.dumps({
    "resolved": renderer is not None or slide is not None,
    "loaded": loaded,
}))
"""
    )

    assert report == {"resolved": False, "loaded": []}


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
        "shader_modules": [
            "rendering.gl_programs.base_program",
            "rendering.gl_programs.slide_program",
        ],
    }


@pytest.mark.parametrize(
    ("direction", "old_xy", "new_xy"),
    (
        ("left", (-0.25, 0.0), (0.75, 0.0)),
        ("right", (0.25, 0.0), (-0.75, 0.0)),
        ("up", (0.0, -0.25), (0.0, 0.75)),
        ("down", (0.0, 0.25), (0.0, -0.75)),
        ("diag_tl_br", (-0.25, -0.25), (0.75, 0.75)),
        ("diag_tr_bl", (0.25, -0.25), (-0.75, 0.75)),
    ),
)
def test_slide_rects_preserve_all_canonical_direction_semantics(
    direction,
    old_xy,
    new_xy,
):
    old_rect, new_rect = _slide_rects(direction, 0.25)

    assert old_rect == (*old_xy, 1.0, 1.0)
    assert new_rect == (*new_xy, 1.0, 1.0)


def test_slide_rects_default_left_clamp_progress_and_reject_unknown_direction():
    assert _slide_rects(None, -2.0) == (
        (-0.0, 0.0, 1.0, 1.0),
        (1.0, -0.0, 1.0, 1.0),
    )
    assert _slide_rects("LEFT", 2.0) == (
        (-1.0, 0.0, 1.0, 1.0),
        (-0.0, -0.0, 1.0, 1.0),
    )
    with pytest.raises(ValueError, match="unknown canonical Slide direction"):
        _slide_rects("Random", 0.5)


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
