"""Import-free real-admission guard: one ordinary family, one source, no hidden work."""
from pathlib import Path
import ast
import json

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_one_canonical_live_family_reuses_the_existing_retained_scene_and_lease():
    registry = _text("rendering/quick/widgets/registry.py")
    binder = _text("rendering/quick/widgets/family_binder.py")
    model = _text("rendering/quick/widgets/games_you_follow.py")
    services = _text("rendering/widget_runtime_services.py")
    assert registry.count('family_id="steam_progress"') == 1
    assert registry.count('qml_filename="GamesYouFollowPresentation.qml"') == 1
    assert binder.count('GamesYouFollowFamilyAdapter(on_steam_action_requested=steam_open_requested)') == 1
    assert '_enabled_from_candidates(widgets_config, ("steam_progress",))' in binder
    assert '_attach_runtime_service(runtime_manager, widget_id, model, widgets_config)' in binder
    assert '"steam_progress": _FOLLOWED_SERVICE_SPEC' in services
    assert 'host.create_family_widget(\n            "steam_progress"' in model
    assert 'initial_properties={"followedModel": model}' in model
    assert 'model.apply_custom_layout_size_payload' in model
    assert 'model.activate(thread_manager)' in model
    assert 'model.retire' in model and 'return self._retained.retire()' in model
    assert not any(token in model for token in ('QTimer(', 'QThread(', 'time.sleep(', 'urlopen(', 'QQmlEngine('))


def test_existing_steam_progress_settings_identity_is_only_defaults_authority():
    settings = _text("ui/tabs/widgets_tab_steam.py")
    defaults = _text("core/settings/default_settings.py")
    snapshot = json.loads(_text("core/settings/defaults_snapshot.json"))
    model = _text("rendering/quick/widgets/games_you_follow.py")
    assert '("steam_progress", "Games You Follow", "Top Right")' in settings
    assert 'is_steam_enabled()' not in settings
    assert 'visible=key != "steam_progress"' not in settings
    assert 'dev_feature_gate="steam"' not in _text("rendering/widget_descriptors.py")[
        _text("rendering/widget_descriptors.py").index('widget_id="steam_progress"'):
        _text("rendering/widget_descriptors.py").index('widget_id="achievement_pulse"')]
    assert 'require_canonical_default("widgets.steam_progress")' in model
    assert 'widgets.games_you_follow' not in defaults
    assert snapshot['widgets']['steam_progress']['enabled'] is False
    assert snapshot['widgets']['steam_progress']['preferred_width'] == 520
    assert snapshot['widgets']['steam_progress']['preferred_height'] == 360


def test_disabled_card_keeps_stable_qml_and_no_separate_source_or_action_path():
    qml = _text("rendering/quick/qml/GamesYouFollowPresentation.qml")
    code = _text("widgets/steam_followed_runtime.py")
    tree = ast.parse(_text("rendering/quick/widgets/games_you_follow.py"))
    assert 'model: followedModel.storyRows' in qml
    assert 'customEditableChildRoles: [' in qml
    assert 'initial_properties={"followedModel": model}' in _text("rendering/quick/widgets/games_you_follow.py")
    assert len([n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "FollowedStoryRows"]) == 1
    for forbidden in ("Timer {", "MouseArea {", "Qt.openUrlExternally", "XMLHttpRequest", "http://", "https://"):
        assert forbidden not in qml
    assert '_SHARED: dict[' in code
    assert 'self._submit(cache_only=True)' in code
    assert 'if self._retired or self._manager is None or self._consumer_ref is None:' in code


def test_live_descriptor_is_public_with_grouped_custom_roles_and_no_dev_gate():
    descriptor_source = _text("rendering/widget_descriptors.py")
    block = descriptor_source.split('widget_id="steam_progress",', 1)[1].split('widget_id="achievement_pulse",', 1)[0]
    assert 'custom_child_roles=FOLLOWED_CHILD_ROLES' in block
    assert 'content_extent_axes=("horizontal", "vertical")' in block
    assert 'dev_feature_gate=' not in block
    assert 'settings_section_id="steam"' in block
    qt_binder = _text("rendering/quick/widgets/family_binder.py")
    assert 'GamesYouFollowFamilyAdapter(on_steam_action_requested=steam_open_requested)' in qt_binder
    assert 'get_widget_runtime_descriptor("steam_progress")' not in qt_binder  # descriptor remains shared infrastructure


def test_click_refresh_and_artwork_are_card_owned_and_enter_existing_steam_route():
    qml = _text("rendering/quick/qml/GamesYouFollowPresentation.qml")
    model = _text("rendering/quick/widgets/games_you_follow.py")
    binder = _text("rendering/quick/widgets/family_binder.py")
    route = _text("engine/display_manager.py")
    source = _text("core/steam/games_followed_source.py")
    assert "signal refreshRequested()" in qml and "onTapped: followsRoot.refreshRequested()" in qml
    assert "signal articleRequested(int slot)" in qml
    assert "onTapped: followsRoot.articleRequested(storySlot)" in qml
    assert "!followsRoot.customLayoutInputBlocked" in qml
    assert "ArtworkFadeImage {" in qml and "storyArtwork" in qml
    assert "storyGame" in qml and "storyPreview" in qml and "storyPublished" in qml
    assert '"articleRequested", model.open_story' in model
    assert '"refreshRequested", model.request_manual_refresh' in model
    assert 'self._article_action(target.kind, target.browser_url)' in model
    assert 'news_hub_target(story.appid)' in model
    assert "GamesYouFollowFamilyAdapter(on_steam_action_requested=steam_open_requested)" in binder
    assert 'kind == "news_article" and widget_id == "steam_progress"' in route
    assert 'kind == "news_hub" and widget_id == "steam_progress"' in route
    assert 'news_hub_target(int(hub_match[1]))' in route
    assert "news_article_target(int(match[1]), match[2], value)" in route
    assert "news_article_target(1, community_game[1], value)" in route
    assert "self._decorate(snapshot, allow_network=opener is None," in source
    # The article batch is not the image-fetch ceiling: existing visible
    # winners must also become eligible for bounded artwork hydration.
    assert "fetched < MAX_NEWS_APPS_PER_REFRESH" in source
    assert "for story in snapshot.stories:" in source
    assert "QTimer(" not in qml and "XMLHttpRequest" not in qml


def test_card_reflow_and_flip_remain_four_stable_shared_custom_roles():
    qml = _text("rendering/quick/qml/GamesYouFollowPresentation.qml")
    model = _text("rendering/quick/widgets/games_you_follow.py")
    assert qml.count('"roleId":') == 4
    assert 'contentReversed: followsRoot.headerFlipped' in qml
    assert 'parent.width - 12.0 - width * scale' in qml
    assert 'customAnchor.length > 0 ? 0.0 : followsRoot.childOffsetX("header")' in qml
    assert 'childNormalizationWidth: followedModel.baseAuthoredWidth' in qml
    assert 'childNormalizationHeight: followedModel.baseAuthoredHeight' in qml
    assert 'childOffsetX("story_tiles")' in qml and 'childOffsetY("story_tiles")' in qml
    assert 'childWidthScale("story_tiles")' in qml and 'childHeightScale("story_tiles")' in qml
    assert 'childWidthScale("refresh")' in qml and 'childHeightScale("refresh")' in qml
    assert 'model: followedModel.storyRows' in qml
    assert 'Math.floor((width + 4.0) / (followedModel.layoutArrangement === "tall"' in qml
    assert 'Math.floor((paintHeight + 14.0) / 112.0)' in qml
    assert 'height: Math.max(0.0, authoredGroupHeight * childHeightScale("story_tiles"))' in qml
    assert 'followedModel.visibleStoryCount, columns * rowsFit' not in qml
    assert 'followedModel.omittedBySetting' in qml and 'def omittedBySetting(self)' in model
    assert "self._rows.apply_display(projected)" in model
    assert "self.set_custom_child_geometry(payload.get(\"child_geometry\"))" in model


def test_followed_header_and_action_hover_inherit_existing_widget_contracts():
    qml = _text("rendering/quick/qml/GamesYouFollowPresentation.qml")
    model = _text("rendering/quick/widgets/games_you_follow.py")
    theme = _text("ui/widget_visual_roles.py")
    assert "BrandedHeader {" in qml
    assert 'resolve_header_colors(\n            "steam_progress"' in model
    for channel in ("fill", "border", "text"):
        assert f'"steam_progress.header.{channel}": "header.{channel}"' in theme
    assert 'objectName: "followedStoryFrame" + storySlot' in qml
    assert 'id: tileHover' in qml and 'enabled: tile.canActivate' in qml
    assert 'objectName: "followedStoryHoverOutline" + storySlot' in qml
    assert 'visible: tileHover.hovered && tile.canActivate' in qml
    # Reference (Steam_Games_You_Follow.md): the admitted clickable hover outline
    # turns bright white; the resting border keeps its semantic colour.
    assert 'border.color: "white"' in qml
    assert 'id: refreshHover' in qml and 'enabled: refreshGlyph.canActivate' in qml
    assert '!followsRoot.customLayoutInputBlocked' in qml
    assert 'text: followedModel.remainingFollowedCount > 0' in qml
    assert '"CACHED UPDATES"' not in qml
