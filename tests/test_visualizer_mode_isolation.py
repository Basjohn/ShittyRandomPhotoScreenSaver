from __future__ import annotations

from pathlib import Path
import ast


def test_dedicated_visualizer_modules_do_not_read_foreign_mode_runtime_fields() -> None:
    # Post-cutover renderers live under rendering/quick/visualizer/implementations/.
    # The pre-Quick widgets/spotify_visualizer/renderers/ directory was retired;
    # the mode-isolation invariant is rehomed onto the current owners.
    contract = {
        "rendering/quick/visualizer/implementations/bubble.py": ("_osc_", "_sine_", "_spectrum_"),
        "rendering/quick/visualizer/implementations/spectrum.py": ("_osc_", "_sine_", "_bubble_"),
        "rendering/quick/visualizer/implementations/oscilloscope.py": ("_bubble_", "_spectrum_"),
        "rendering/quick/visualizer/implementations/sine_wave.py": ("_bubble_", "_spectrum_"),
        "widgets/spotify_visualizer/bubble_simulation.py": ("_osc_", "_sine_", "_spectrum_"),
        "widgets/spotify_visualizer/bar_computation.py": ("_osc_", "_sine_", "_bubble_"),
        "widgets/spotify_visualizer/transient_bus.py": ("_osc_", "_sine_", "_bubble_", "_spectrum_"),
    }

    root = Path(__file__).resolve().parents[1]
    for rel_path, forbidden_tokens in contract.items():
        # The contract is about field ownership, not a foreign word occurring in
        # comments, local helper names or a retired module's former location.
        tree = ast.parse((root / rel_path).read_text(encoding="utf-8"))
        accessed_fields = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        for token in forbidden_tokens:
            violations = sorted(field for field in accessed_fields if token in field)
            assert not violations, f"{rel_path} accesses foreign fields: {violations}"
