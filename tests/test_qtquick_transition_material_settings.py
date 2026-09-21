"""Material values cross canonical defaults, lazy Settings and immutable requests."""

from copy import deepcopy
import random
import uuid

import pytest

from core.settings.defaults import get_default_settings
from core.settings.settings_manager import SettingsManager
from rendering.quick.transitions.parameter_resolution import (
    resolve_parameterized_phase_c_inputs,
)
from ui.tabs.transitions_tab import TransitionsTab


CASES = (
    ("crumble", "Crumble", ("depth", "thickness", "debris")),
    (
        "glass_shatter",
        "Glass Shatter",
        ("thickness", "transparency", "refraction", "dispersion", "sheen"),
    ),
    ("exploding_tiles", "Exploding Tiles", ("thickness", "force")),
    ("ink_bloom", "Ink Bloom", ("depth", "gloss")),
    ("tendril_reveal", "Tendril Reveal", ("depth", "gloss")),
    ("melt_drip", "Melt Drip", ("depth", "gloss")),
)


@pytest.mark.parametrize("section,name,fields", CASES)
def test_surface_requests_use_canonical_finite_bounded_values(section, name, fields):
    canonical = get_default_settings()["transitions"][section]

    def resolve(config):
        return resolve_parameterized_phase_c_inputs(
            section, {section: config}, random_source=random.Random(7)
        ).parameter_dict()

    sparse = resolve({})
    for field in fields:
        assert sparse[field] == canonical[field]
        for bad in ("bad", None, float("nan"), float("inf")):
            assert resolve({field: bad})[field] == canonical[field]
        low, high = (
            (0.5, 2.0)
            if field == "force"
            else (
                (0.2, 1.5) if section == "crumble" and field == "depth" else (0.0, 1.0)
            )
        )
        assert resolve({field: -100})[field] == low
        assert resolve({field: 100})[field] == high
        assert resolve({field: 0.73})[field] == 0.73


@pytest.mark.qt
@pytest.mark.parametrize("section,name,fields", CASES)
def test_material_controls_save_reopen_refresh_and_reset(
    qt_app, qtbot, tmp_path, section, name, fields
):
    settings = SettingsManager(
        organization="Test",
        application="Materials_" + uuid.uuid4().hex,
        storage_base_dir=tmp_path,
    )
    settings.reset_to_defaults()
    tab = TransitionsTab(settings)
    qtbot.addWidget(tab)
    if section != "crumble":
        assert not hasattr(tab, section + "_group")
    tab._activation_checkboxes[name].setChecked(True)
    tab._on_nav_selected(name)
    for field in fields:
        getattr(tab, f"{section}_{field}_spin").setValue(0.73)
    tab._save_settings()
    saved = settings.get("transitions", {})
    params = resolve_parameterized_phase_c_inputs(section, saved).parameter_dict()
    for field in fields:
        assert params[field] == 0.73

    reopened = TransitionsTab(settings)
    qtbot.addWidget(reopened)
    reopened._on_nav_selected(name)
    for field in fields:
        assert getattr(reopened, f"{section}_{field}_spin").value() == 0.73
    external = deepcopy(settings.get("transitions", {}))
    for field in fields:
        external[section][field] = 0.91
    settings.set("transitions", external)
    qt_app.processEvents()
    reopened._save_settings()
    for field in fields:
        assert getattr(reopened, f"{section}_{field}_spin").value() == 0.91
        assert settings.get("transitions", {})[section][field] == 0.91

    settings.reset_to_defaults()
    qt_app.processEvents()
    reopened._activation_checkboxes[name].setChecked(True)
    reopened._on_nav_selected(name)
    canonical = get_default_settings()["transitions"][section]
    for field in fields:
        assert getattr(reopened, f"{section}_{field}_spin").value() == canonical[field]


@pytest.mark.qt
@pytest.mark.parametrize("old_label", ("Bias Old Image", "Bias New Image"))
def test_crumble_retires_misleading_weight_labels_without_changing_order(
    qt_app, qtbot, tmp_path, old_label
):
    settings = SettingsManager(
        organization="Test",
        application="CrumbleLabels_" + uuid.uuid4().hex,
        storage_base_dir=tmp_path,
    )
    config = settings.get("transitions", {})
    config["crumble"]["weighting"] = old_label
    settings.set("transitions", config)
    tab = TransitionsTab(settings)
    qtbot.addWidget(tab)
    tab._on_nav_selected("Crumble")
    assert tab.crumble_weight_combo.currentText() == "Top Weighted"
    tab._save_settings()
    assert settings.get("transitions", {})["crumble"]["weighting"] == "Top Weighted"
    assert (
        resolve_parameterized_phase_c_inputs(
            "crumble", settings.get("transitions", {})
        ).parameter_dict()["weight_mode"]
        == 0.0
    )
