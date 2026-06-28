from __future__ import annotations

from pathlib import Path


def test_dedicated_visualizer_modules_do_not_read_foreign_mode_runtime_fields() -> None:
    contract = {
        "widgets/spotify_visualizer/renderers/blob.py": ("_osc_", "_sine_", "_bubble_", "_spectrum_"),
        "widgets/spotify_visualizer/renderers/bubble.py": ("_osc_", "_sine_", "_blob_", "_spectrum_"),
        "widgets/spotify_visualizer/renderers/spectrum.py": ("_osc_", "_sine_", "_blob_", "_bubble_"),
        "widgets/spotify_visualizer/renderers/oscilloscope.py": ("_blob_", "_bubble_", "_spectrum_"),
        "widgets/spotify_visualizer/oscilloscope_contract.py": ("_sine_", "_blob_", "_bubble_", "_spectrum_"),
        "widgets/spotify_visualizer/renderers/sine_wave.py": ("_blob_", "_bubble_", "_spectrum_"),
        "widgets/spotify_visualizer/blob_math.py": ("_osc_", "_sine_", "_bubble_", "_spectrum_"),
        "widgets/spotify_visualizer/blob_pockets.py": ("_osc_", "_sine_", "_bubble_", "_spectrum_"),
        "widgets/spotify_visualizer/blob_shaper_solver.py": ("_osc_", "_sine_", "_bubble_", "_spectrum_"),
        "widgets/spotify_visualizer/bubble_simulation.py": ("_osc_", "_sine_", "_blob_", "_spectrum_"),
        "widgets/spotify_visualizer/bar_computation.py": ("_osc_", "_sine_", "_blob_", "_bubble_"),
        "widgets/spotify_visualizer/transient_bus.py": ("_osc_", "_sine_", "_blob_", "_bubble_", "_spectrum_"),
    }

    root = Path(__file__).resolve().parents[1]
    for rel_path, forbidden_tokens in contract.items():
        text = (root / rel_path).read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in text, f"{rel_path} unexpectedly references foreign runtime token {token}"
