from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_current_visualizer_reference_docs_exist():
    for relative in (
        "Docs/Visualizer_Reference.md",
        "Docs/Visualizer_Change_Checklist.md",
        "Docs/Guardrails/Visualizer_Presentation.md",
        "Docs/Contracts.md",
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


def test_spec_describes_the_current_visualizer_presentation_contract():
    spec_text = (ROOT / "Spec.md").read_text(encoding="utf-8")
    assert "## 5. Visualizer logical contract" in spec_text
    assert "shell_policy = CARD" in spec_text
    assert "shell_policy = FRAMELESS" in spec_text
    assert "canonical baseline visualizer viewport aspect ratio" in spec_text
    assert "scroll-wheel resize" in spec_text
    assert "spectrum_growth" in spec_text
    assert "explicitly retired from destination ownership" in spec_text
    assert "Docs/Visualizer_Reset_Matrix.md" not in spec_text
    assert "Docs/Visualizer_Signal_Contract.md" not in spec_text
    assert "Docs/Visualizer_Baseline_Tuning_Matrix.md" not in spec_text
    assert "Docs/Visualizer_Presets_Plan.md" not in spec_text
    assert "Docs/Advanced_Migration.md" not in spec_text
    assert "tools/rebuild_visualizer_presets.py" not in spec_text


def test_visualizer_reference_describes_the_current_quick_boundary():
    reference_text = (ROOT / "Docs" / "Visualizer_Reference.md").read_text(encoding="utf-8")
    assert "display's sole `QQuickWindow`" in reference_text
    assert "one canonical baseline viewport aspect ratio" in reference_text
    assert "FRAMELESS + VIEWPORT_RECT" in reference_text
    assert "scroll-wheel resize -> uniform scale" in reference_text
    assert "tools/rebuild_visualizer_presets.py" not in reference_text


def test_contracts_route_visualizer_shell_clip_and_geometry_owners():
    contracts_text = (ROOT / "Docs" / "Contracts.md").read_text(encoding="utf-8")
    assert "Mode presentation policy" in contracts_text
    assert "one render-node-local SDF/stencil host" in contracts_text
    assert "QSGClipNode" not in contracts_text
    assert "shell_policy = FRAMELESS" in contracts_text
    assert "canonical baseline viewport/aspect" in contracts_text
    assert "uniform_visual_scale" in contracts_text
    assert "viewport_extent" in contracts_text
    assert "left/right edge-handle resize" in contracts_text


def test_compositor_architecture_does_not_make_visualizer_card_universal():
    architecture_text = (ROOT / "Docs" / "Compositor_Architecture.md").read_text(encoding="utf-8")
    assert "optional retained visualizer shell/chrome" in architecture_text
    assert "Card existence is a presentation policy" in architecture_text
    assert "shell_policy = FRAMELESS" in architecture_text
    assert "one canonical baseline viewport aspect" in architecture_text
    assert "- visualizer/card;" not in architecture_text


def test_project_overview_keeps_visualizer_scope_current():
    overview_text = (ROOT / "Docs" / "00_PROJECT_OVERVIEW.md").read_text(encoding="utf-8")
    assert "high-fidelity multi-mode visualizer" in overview_text
    assert "FRAMELESS + VIEWPORT_RECT" in overview_text
    assert "scroll / corner resize" in overview_text
    assert "per-mode visualizer card-height/growth controls" in overview_text
    assert "tools/rebuild_visualizer_presets.py" not in overview_text


def test_deleted_qtimer_policy_is_not_referenced_by_active_docs():
    assert not (ROOT / "Docs" / "QTIMER_POLICY.md").exists()
    for relative in ("Index.md", "Spec.md", "Docs/00_PROJECT_OVERVIEW.md", "Docs/10_WIDGET_GUIDELINES.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "QTIMER_POLICY" not in text
