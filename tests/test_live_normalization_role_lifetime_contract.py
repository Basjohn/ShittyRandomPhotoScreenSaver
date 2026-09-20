"""Edit-only role identity under content-driven normalization changes.

These source checks protect three real families while a retained Qt scene test
exercises live binding, delegate identity, painted bounds and Edit teardown.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering/quick/qml"


def _role_declaration(family: str) -> str:
    qml = (QML / f"{family}Presentation.qml").read_text(encoding="utf-8")
    return qml.split("customEditableChildRoles: {", 1)[1].split("return roles", 1)[0]


def test_card_and_accessory_normalization_changes_cannot_rebuild_role_lists() -> None:
    for family, count in (("Media", 9), ("Reddit", 2), ("Gmail", 2)):
        qml = (QML / f"{family}Presentation.qml").read_text(encoding="utf-8")
        roles = _role_declaration(family)
        root = family[0].lower() + family[1:] + "Root"
        assert roles.count(f'"normalizationTarget": {root}') == count, family
        assert '"normalizationWidth":' not in roles, family
        assert '"normalizationHeight":' not in roles, family
        # Evaluating a role list must never read a live baseline, actual widget
        # bounds, provider state, or a dynamic visibility gate.
        for source in (
            "canonicalPreferredCardWidth", "canonicalVolumeAccessoryExtent",
            "canonicalPreferredWidth", "canonicalAuthoredHeight",
            ".visible", "source.count", "contentExtentWidth",
            "contentExtentHeight", "customChildGeometry",
        ):
            assert source not in roles, (family, source)
        assert f"readonly property real childNormalizationWidth:" in qml
        assert f"readonly property real childNormalizationHeight:" in qml


def test_media_accessory_uses_its_existing_distinct_normalization_and_real_lane() -> None:
    qml = (QML / "MediaPresentation.qml").read_text(encoding="utf-8")
    roles = _role_declaration("Media")
    volume = roles.split('"roleId": "volume_bar"', 1)[1].split("roles.push", 1)[0]
    assert '"normalizationTarget": mediaRoot' in volume
    assert '"normalizationWidthProperty": "volumeChildNormalizationWidth"' in volume
    assert '"containmentTarget": appVolumeSlider' in volume
    assert '"target": appVolumeTrack' in volume
    assert "canonicalPreferredCardWidth + canonicalVolumeAccessoryExtent" in qml.split(
        "readonly property real volumeChildNormalizationWidth:", 1
    )[1].split("readonly property", 1)[0]
    assert "? volumeChildNormalizationWidth" in qml
    assert "headerFlipped" in qml  # external volume's accepted automatic side remains family-owned


def test_selected_mapper_resolves_live_normalizations_without_runtime_observers() -> None:
    qml = (QML / "CustomLayoutOverlay.qml").read_text(encoding="utf-8")
    selected = qml.split("id: childRoleLoader", 1)[1]
    assert "active: editFrame.selectedForChildEdit" in selected
    assert 'modelData.normalizationWidthProperty' in selected
    assert 'source[propertyName]' in selected
    assert 'modelData.normalizationHeightProperty' in selected
    assert 'source[propertyName]' in selected
    assert 'modelData.normalizationWidth || live || preferred' in selected
    assert 'modelData.normalizationHeight || live || preferred' in selected
    assert 'const live = source ? source[propertyName] : 0.0' in selected
    assert 'const preferred = source && !live ? source.preferredContentWidth : 0.0' in selected
    assert 'const preferred = source && !live ? source.preferredContentHeight : 0.0' in selected
    # No edit-independent listener, timer, implicit role-model key, or extra state owner.
    for banned in ("normalizationTargetChanged", "normalizationWidthChanged:",
                   "normalizationHeightChanged:", "Timer {", "onTriggered:"):
        assert banned not in selected.split("id: childRoleRepeater", 1)[0], banned


def test_qt_test_keeps_actual_target_and_roles_through_twenty_baseline_changes() -> None:
    test = (ROOT / "tests/test_qtquick_child_mapped_geometry.py").read_text(encoding="utf-8")
    fixture = test.split("def test_selected_roles_retain_identity_when_live_normalization_baselines_change", 1)[1]
    assert "range(20)" in fixture
    assert '"normalizationWidthProperty": "volumeChildNormalizationWidth"' in fixture
    assert 'is card_role' in fixture and 'is accessory_role' in fixture
    assert '"normalizationWidth") == pytest.approx' in fixture
    assert '_assert_bounds(' in fixture
    assert 'overlay.clear_session()' in fixture
    assert '"non-bindable" in message' in fixture


def test_remaining_dense_and_grouped_families_keep_authored_baselines_out_of_role_models() -> None:
    """Changing canonical baselines must not retire selected family Edit delegates."""
    cases = (
        ("Weather", "weatherRoot", 11, "childNormalizationWidth", "childNormalizationHeight"),
        ("SystemStats", "statsRoot", 3, "childNormalizationWidth", "childNormalizationHeight"),
        ("FriendPulse", "friendRoot", 6, "baseAuthoredWidth", "baseAuthoredHeight"),
        ("AchievementPulse", "achievementRoot", 8, "baseAuthoredWidth", "baseAuthoredHeight"),
        ("AbandonmentIssues", "abandonmentRoot", 7, "baseAuthoredWidth", "baseAuthoredHeight"),
    )
    for name, owner, count, width, height in cases:
        qml = (QML / f"{name}Presentation.qml").read_text(encoding="utf-8")
        if name == "SystemStats":
            roles = qml.split("customEditableChildRoles: [", 1)[1].split("\n    ]", 1)[0]
        else:
            roles = _role_declaration(name)
        if name == "Weather":
            assert roles.count(f"roles[i].normalizationTarget = {owner}") == 1
        else:
            assert roles.count(f'"normalizationTarget": {owner}') == count
            assert '"normalizationWidth":' not in roles
            assert '"normalizationHeight":' not in roles
            if width == "baseAuthoredWidth":
                assert roles.count('"normalizationWidthProperty": "baseAuthoredWidth"') == count
                assert roles.count('"normalizationHeightProperty": "baseAuthoredHeight"') == count
        # Source baselines and provider flags are not allowed to recreate the
        # entire semantic descriptor array during an active pointer gesture.
        for forbidden in (f"{owner}.{width}", f"{owner}.{height}",
                          "childNormalizationWidth,", "childNormalizationHeight,",
                          "if (normalContent.visible", "if (activitySummary.visible"):
            assert forbidden not in roles, (name, forbidden)
        for prop in (width, height):
            assert f"property real {prop}:" in qml, (name, prop)


def test_named_authored_axes_have_real_retained_qt_identity_and_paint_oracle() -> None:
    test = (ROOT / "tests/test_qtquick_child_mapped_geometry.py").read_text(encoding="utf-8")
    fixture = test.split("def test_selected_roles_retain_identity_when_live_normalization_baselines_change", 1)[1]
    for value in ('"baseAuthoredWidth"', '"baseAuthoredHeight"',
                  'is dense_role', 'dense_role.property("normalizationWidth")',
                  'dense_role.property("normalizationHeight")', 'dense, frame'):
        assert value in fixture
    assert 'range(20)' in fixture
    assert 'overlay.clear_session()' in fixture
