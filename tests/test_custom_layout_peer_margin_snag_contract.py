"""Qt-free contract for the light 30 px CUSTOM peer-margin snag."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "rendering/custom_layout_contract.py"


def _load_axis_helper():
    source = CONTRACT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_snap_axis_position"
    )
    module = ast.Module(body=[function], type_ignores=[])
    namespace = {
        "CUSTOM_LAYOUT_SNAP_THRESHOLD_PX": 24,
        "CUSTOM_LAYOUT_ALIGNMENT_SNAG_BIAS_PX": 3,
        "CUSTOM_LAYOUT_SNAP_GUTTER_PX": 30,
        "CUSTOM_LAYOUT_GUTTER_SNAG_THRESHOLD_PX": 5,
        "CUSTOM_LAYOUT_GRID_STEP_PX": 12,
        "SnapGuide": type(
            "SnapGuide",
            (),
            {
                "__init__": lambda self, position, kind, distance=0: (
                    setattr(self, "position", position),
                    setattr(self, "kind", kind),
                    setattr(self, "distance", distance),
                    None,
                )[-1]
            },
        ),
    }
    exec(compile(module, str(CONTRACT), "exec"), namespace)
    return namespace["_snap_axis_position"], source


def test_alignment_edges_and_centers_get_a_small_semantic_snag_bias():
    snap_axis, source = _load_axis_helper()

    assert "CUSTOM_LAYOUT_ALIGNMENT_SNAG_BIAS_PX = 3" in source

    # Display center is x=410 for a 180px item in a 1000px display. Without
    # the small semantic bias, the 408px grid point is closer and masks it.
    snapped, guides = snap_axis(405, 180, 1000, [])
    assert snapped == 410
    assert guides and guides[0].kind == "display_center"
    assert guides[0].distance == 5

    # The same light preference applies to peer-edge alignment. A nearby grid
    # point still owns ordinary dragging, but the alignment line can now be felt.
    snapped, guides = snap_axis(344, 140, 1000, [(300, 480)])
    assert snapped == 340
    assert guides and guides[0].kind == "peer"
    assert guides[0].distance == 4

    # It remains a snag, not a sticky edge mode: 8px from the display boundary
    # the closer ordinary grid target still wins.
    released, guides = snap_axis(8, 180, 1000, [])
    assert released == 12
    assert guides and guides[0].kind == "grid"


def test_peer_margin_snag_is_external_30px_and_narrow():
    snap_axis, source = _load_axis_helper()

    assert "CUSTOM_LAYOUT_SNAP_GUTTER_PX = 30" in source
    assert "CUSTOM_LAYOUT_GUTTER_SNAG_THRESHOLD_PX = 5" in source
    assert "peer_start + gutter" not in source
    assert "peer_end - span - gutter" not in source

    # Peer occupies [300, 480]; a 140px item should lightly snag at x=510,
    # exactly 30px to its right, only once the cursor is close to that target.
    snapped, guides = snap_axis(509, 140, 1000, [(300, 480)])
    assert snapped == 510
    assert guides and guides[0].kind == "peer_gutter"
    assert guides[0].distance == 1

    # Outside the narrow attraction neighborhood, normal grid/mouse behavior wins.
    released, guides = snap_axis(505, 140, 1000, [(300, 480)])
    assert released == 504
    assert guides and guides[0].kind == "grid"
