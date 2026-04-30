from pathlib import Path


def test_overlay_effect_invalidation_includes_gmail_widget() -> None:
    """Gmail must participate in the same shadow-cache cadence as peer widgets."""
    source = Path("rendering/widget_effects.py").read_text(encoding="utf-8")

    assert '"gmail_widget"' in source
