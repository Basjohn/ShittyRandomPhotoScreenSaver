from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
INSTALLERS = (
    ROOT / "scripts" / "SRPSS_Installer.iss",
    ROOT / "scripts" / "SRPSS_MediaCenter_Installer.iss",
)


def test_installers_use_forced_dark_style_without_slate_inversion() -> None:
    for path in INSTALLERS:
        text = path.read_text(encoding="utf-8")
        assert "WizardStyle=modern dark includetitlebar hidebevels" in text
        assert " dark slate " not in text
        # The chosen dark shade is artwork, not a compatibility constant.
        assert re.search(r"(?m)^WizardBackColor=#[0-9A-Fa-f]{6}$", text)
        assert "WizardSmallImageBackColor=none" in text
        assert "WizardSmallImageFile=..\\ui\\assets\\installer\\SRPSSWizard.png" in text


def test_installers_do_not_reintroduce_custom_pascal_icon_conversion() -> None:
    for path in INSTALLERS:
        text = path.read_text(encoding="utf-8")
        assert "InitializeBitmapImageFromIcon" not in text
        assert "WizardStyleFile=" not in text
