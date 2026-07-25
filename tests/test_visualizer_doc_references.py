from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_current_visualizer_reference_docs_exist():
    for relative in (
        "Docs/Visualizer_Reference.md",
        "Docs/Visualizer_Change_Checklist.md",
    ):
        path = ROOT / relative
        assert path.exists(), f"Visualizer reference document missing: {relative}"


def test_index_does_not_reference_missing_visualizer_docs():
    index_text = (ROOT / "Index.md").read_text(encoding="utf-8")
    assert "Docs/Visualizer_Reference.md" in index_text
    assert "Docs/Visualizer_Change_Checklist.md" in index_text
    assert "Docs/Visualizer_Reset_Matrix.md" not in index_text
    assert "Docs/Visualizer_Signal_Contract.md" not in index_text
    assert "Docs/Visualizer_Baseline_Tuning_Matrix.md" not in index_text
    assert "Docs/Visualizer_Presets_Plan.md" not in index_text
    assert "Docs/Bubble_Motion_Plan.md" not in index_text
    assert "Docs/Advanced_Migration.md" not in index_text


def test_spec_does_not_reference_missing_visualizer_docs():
    spec_text = (ROOT / "Spec.md").read_text(encoding="utf-8")
    assert "## 5. Visualizer Contract" in spec_text
    assert "Docs/Visualizer_Reset_Matrix.md" not in spec_text
    assert "Docs/Visualizer_Signal_Contract.md" not in spec_text
    assert "Docs/Visualizer_Baseline_Tuning_Matrix.md" not in spec_text
    assert "Docs/Visualizer_Presets_Plan.md" not in spec_text
    assert "Docs/Advanced_Migration.md" not in spec_text
    assert "tools/rebuild_visualizer_presets.py" not in spec_text


def test_visualizer_reference_uses_current_preset_tooling():
    reference_text = (ROOT / "Docs" / "Visualizer_Reference.md").read_text(encoding="utf-8")
    assert "tools/visualizer_preset_repair.py" in reference_text
    assert "tools/rebuild_visualizer_presets.py" not in reference_text


def test_project_overview_keeps_visualizer_scope_current():
    overview_text = (ROOT / "Docs" / "00_PROJECT_OVERVIEW.md").read_text(encoding="utf-8")
    assert "Spotify visualizers" in overview_text
    assert "tools/rebuild_visualizer_presets.py" not in overview_text


def test_deleted_qtimer_policy_is_not_referenced_by_active_docs():
    assert not (ROOT / "Docs" / "QTIMER_POLICY.md").exists()
    for relative in ("Index.md", "Spec.md", "Docs/00_PROJECT_OVERVIEW.md", "Docs/10_WIDGET_GUIDELINES.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "QTIMER_POLICY" not in text
