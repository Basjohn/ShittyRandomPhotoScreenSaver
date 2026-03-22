from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_visualizer_audit_index_exists():
    path = ROOT / "Docs" / "Visualizer_System_Audit" / "00_Audit_Index.md"
    assert path.exists(), "Visualizer system audit index must exist"


def test_index_does_not_reference_missing_visualizer_docs():
    index_text = (ROOT / "Index.md").read_text(encoding="utf-8")
    assert "Docs/Visualizer_Reset_Matrix.md" in index_text
    assert "Docs/Visualizer_Signal_Contract.md" in index_text
    assert "Docs/Visualizer_Baseline_Tuning_Matrix.md" in index_text
    assert "Docs/Visualizer_Presets_Plan.md" not in index_text
    assert "Docs/Bubble_Motion_Plan.md" not in index_text
    assert "Docs/Advanced_Migration.md" not in index_text


def test_spec_does_not_reference_missing_visualizer_docs():
    spec_text = (ROOT / "Spec.md").read_text(encoding="utf-8")
    assert "Docs/Visualizer_Reset_Matrix.md" in spec_text
    assert "Docs/Visualizer_Signal_Contract.md" in spec_text
    assert "Docs/Visualizer_Baseline_Tuning_Matrix.md" in spec_text
    assert "Docs/Visualizer_Presets_Plan.md" not in spec_text
    assert "Docs/Advanced_Migration.md" not in spec_text


def test_visualizer_baseline_tuning_matrix_exists():
    path = ROOT / "Docs" / "Visualizer_Baseline_Tuning_Matrix.md"
    assert path.exists(), "Visualizer baseline tuning matrix must exist"
