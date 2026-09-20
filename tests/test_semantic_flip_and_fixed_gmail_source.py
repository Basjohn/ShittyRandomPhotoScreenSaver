"""Low-cost source ownership gates for the Sept 19 editor recovery.

These are not substitutes for actual Qt geometry/interaction gates in the family
suites. They protect the stated causal design without introducing mock state.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / 'rendering' / 'quick' / 'qml'


def source(name: str) -> str:
    return (QML / name).read_text(encoding='utf-8')


def test_gmail_natural_height_uses_authored_settings_not_live_mail_population():
    gmail = (ROOT / 'rendering/quick/widgets/gmail.py').read_text(encoding='utf-8')
    block = gmail.split('def contentHeight(self) -> float:', 1)[1].split('@Slot(str, result=str)', 1)[0]
    assert 'self.config.limit' in block
    assert 'self.fontSize' in block
    assert 'self._row_model' not in block
    assert 'self.viewState' not in block
    assert 'self._snapshot' not in block
    assert 'len(' not in block


def test_media_positioner_only_owns_flow_slots_and_never_child_edit_offsets():
    media = source('MediaPresentation.qml')
    column = media.split('Item {\n                id: metadata', 1)[1].split(
        '            Rectangle {\n                id: artworkFrame', 1
    )[0]
    assert 'objectName: "mediaMetadataFlowSlot"' in column
    assert 'objectName: "mediaPlaybackStateFlowSlot"' in column
    assert 'height: trackMetadata.implicitHeight' in column
    assert 'height: visible ? playbackState.implicitHeight : 0.0' in column
    assert 'y: trackMetadataSlot.height + (visible ? mediaRoot.metadataSpacing : 0.0)' in column
    assert 'height: implicitHeight' in column
    assert 'MediaMetadataColumn {\n                        id: trackMetadata' in column
    assert 'ShadowedText {\n                        id: playbackState' in column
    assert 'x: mediaRoot.childOffsetX("metadata")' in column
    assert 'y: mediaRoot.childOffsetY("metadata")' in column
    assert 'y: mediaRoot.childOffsetY("playback_state")' in column
    # The movable children have flow-slot parents. The slots are a single
    # explicit authored flow, independent of the editable child offsets.
    assert column.index('id: trackMetadataSlot') < column.index('id: trackMetadata\n')
    assert column.index('id: playbackStateSlot') < column.index('id: playbackState\n')


def test_reddit_gmail_flip_semantic_rails_not_inherited_mirroring():
    for family in ('RedditPresentation.qml', 'GmailPresentation.qml'):
        qml = source(family)
        assert 'readonly property bool headerFlipped: childAlignment("header", "left") === "right"' in qml
        assert 'LayoutMirroring.enabled:' not in qml
        assert 'LayoutMirroring.childrenInherit:' not in qml
        assert 'headerFlipped ? headerArea.width - width * scale : 0.0' in qml
        assert 'headerFlipped ? 0.0 : headerArea.width - width' in qml
    reddit = source('RedditPresentation.qml')
    assert 'visualColumnOrder' in reddit
    assert 'postRow.columnX("age")' in reddit
    assert 'postRow.columnX("ago")' in reddit
    assert 'postRow.columnX("title")' in reddit
    assert 'anchors.right: redditRoot.headerFlipped ? ageText.left : parent.right' not in reddit
    assert 'horizontalAlignment: Text.AlignLeft' in reddit
    gmail = source('GmailPresentation.qml')
    assert 'visualColumnOrder' in gmail
    assert 'openArea.columnX("timestamp")' in gmail
    assert 'openArea.columnX("sender")' in gmail
    assert 'openArea.columnX("subject")' in gmail
    assert 'envelope.left : menuButton.left' not in gmail
    assert 'timestampText.left : parent.right' not in gmail



def test_lock_is_edit_only_and_separator_grip_uses_existing_move_gesture():
    qml = source('CustomLayoutOverlay.qml')
    assert 'id: thinChildMoveGrip' in qml
    assert 'childRoleFrame.height < 28.0' in qml
    assert 'childRoleFrame.width < 44.0' in qml
    assert 'z: childRoleFrame.thinMoveTarget ? 5 : 2' in qml
    assert 'customLayoutOverlay.sessionModel.beginChildMove(' in qml
    assert 'customLayoutOverlay.sessionModel.moveChild(' in qml
    assert 'id: childEditLockMark' in qml
    assert 'scale: 0.9' in qml
    assert 'childEditingLocked = !childEditingLocked' in qml
    assert 'editFrame.toggleChildEditLock()' in qml
    assert 'Timer {' not in qml


def test_media_friend_stats_project_widget_flip_from_existing_header_record_only():
    for family in ('MediaPresentation.qml', 'SystemStatsPresentation.qml'):
        qml = source(family)
        assert 'readonly property bool headerFlipped: childAlignment("header", "left") === "right"' in qml
        assert 'LayoutMirroring.enabled:' not in qml
        assert 'LayoutMirroring.childrenInherit:' not in qml
        assert 'contentReversed:' in qml
    friend = source('FriendPulsePresentation.qml')
    assert 'friendPulseModel.customHeaderAlignment === "right"' in friend
    assert 'friendRoot.headerFlipped' in friend
    assert 'friendRoot.friendPulseModel.authoredWidth' in friend
    assert 'friendRoot.headerSafeInsetX - width' in friend
    assert 'onAuthoredRightRail' in friend
    assert 'customEditPlacementCompensationX: x - (' in friend
    assert '!== friendRoot.headerFlipped ? Text.AlignRight : Text.AlignLeft' in friend
    stats = source('SystemStatsPresentation.qml')
    assert 'readonly property bool headerFlipped: childAlignment("header", "left") === "right"' in stats
    assert 'statsRoot.headerFlipped' in stats
    assert 'function metricRoleX(roleId, panelWidth, roleWidth)' in stats
    assert 'headerFlipped ? 16.0 : panelWidth - 16.0 - valueLaneWidth' in stats
    assert 'headerFlipped ? panelWidth - 18.0 - roleWidth : 18.0' in stats
    assert 'statsRoot.metricRoleX("metric_values", panel.width, width)' in stats
    assert 'statsRoot.metricRoleX("metric_labels", panel.width, width)' in stats
    media = source('MediaPresentation.qml')
    assert 'mediaRoot.headerFlipped && mediaRoot.artworkOnAuthoredRail' in media
    assert 'artworkFrame.authoredArtworkWidth + 16.0' in media
    assert 'artworkFrame.x + artworkFrame.width + 16.0' not in media
    assert 'parent.width - x - 2.0' in media
    assert 'Timer {' not in friend + stats + media


def test_child_edit_lock_draws_connected_unlocked_shackle_without_new_runtime_cadence():
    lock = source('CustomLayoutOverlay.qml').split('id: childEditLockMark', 1)[1].split(
        'id: thinChildMoveGrip', 1
    )[0]
    assert 'scale: 0.9' in lock
    assert 'id: childEditLockShackle' in lock
    assert 'ctx.bezierCurveTo(' in lock
    assert 'ctx.lineCap = editFrame.childEditingLocked ? "round" : "butt"' in lock
    assert 'ctx.lineJoin = editFrame.childEditingLocked ? "round" : "miter"' in lock
    assert 'ctx.lineTo(6, 4.5)' in lock
    assert 'ctx.lineTo(15.2, 4.5)' in lock
    assert 'ctx.lineTo(15.2, 7.4)' in lock
    assert 'onChildEditingLockedChanged()' in lock
    assert 'childEditLockShackle.requestPaint()' in lock
    assert 'Timer {' not in lock


def test_dense_steam_flip_moves_semantic_regions_without_pixel_mirror_or_parent_growth_cycle():
    achievement = source('AchievementPulsePresentation.qml')
    abandonment = source('AbandonmentIssuesPresentation.qml')
    for qml, prefix in ((achievement, 'achievementRoot'), (abandonment, 'abandonmentRoot')):
        assert f'{prefix}.headerFlipped' in qml
        assert 'LayoutMirroring.enabled:' not in qml
        assert 'LayoutMirroring.childrenInherit:' not in qml
        assert 'mirror: true' not in qml
        assert 'xScale: -1' not in qml
        assert 'scale: -1' not in qml
        assert f'{prefix}.baseAuthoredWidth' in qml
        assert 'customEditableChildRequirementTarget: null' in qml
        assert 'customEditPlacementCompensationX:' in qml
    assert 'achievementModel.customHeaderAlignment === "right"' in achievement
    assert 'function semanticRailX(baseX, baseWidth, onAuthoredRail)' in achievement
    assert 'baseAuthoredWidth - baseX - baseWidth : baseX' in achievement
    for name in ('canonicalArtworkX', 'canonicalGameNameX', 'canonicalAchievementListX',
                 'canonicalProgressX'):
        assert f'achievementRoot.{name}' in achievement
    assert 'artworkFollowsParentRightRail && !headerFlipped' in achievement
    assert 'achievementRoot.headerFlipped' in achievement
    assert 'titleParentReflowWidth' in achievement
    assert 'id: customChildRequirement' not in achievement
    assert 'titleParentReflowWidth' in achievement
    assert 'achievementRoot.progressParentReflowY' in achievement
    assert 'abandonmentModel.customHeaderAlignment === "right"' in abandonment
    assert 'function textRailX(onAuthoredRail)' in abandonment
    assert 'flippedArtworkParentReflowX ? extraContentWidth' not in abandonment
    assert 'artworkFollowsFlippedRight ? extraContentWidth : 0.0' in abandonment
    assert 'headerFlipped && abandonmentRoot.backlogOnAuthoredRail' in abandonment
    assert 'id: customChildRequirement' not in abandonment
    assert 'backlogParentReflowX' in abandonment
    assert 'customArtworkXOffset' in abandonment
    assert 'customShelfGroupXOffset' in abandonment



def test_weather_authored_icon_alignment_is_a_placement_choice_not_an_image_mirror():
    weather = source('WeatherPresentation.qml')
    assert 'weatherModel.iconAlignment === "LEFT"' in weather
    assert 'weatherModel.iconAlignment === "RIGHT"' in weather
    assert 'id: leftConditionIcon' in weather
    assert 'id: rightConditionIcon' in weather
    assert 'anchors.left: parent.left' in weather
    assert 'anchors.right: parent.right' in weather
    assert 'fillMode: Image.PreserveAspectFit' in weather
    assert 'LayoutMirroring.enabled:' not in weather
    assert 'mirror: true' not in weather
    assert 'xScale: -1' not in weather
    # Weather's Settings-owned placement must not silently be shadowed by a
    # second CUSTOM-only widget-wide orientation field.
    assert 'headerFlipped' not in weather


def test_reddit_gmail_preferred_width_has_no_live_header_or_refresh_dependency():
    """No parent-width -> clipped-refresh -> preferred-width feedback cycle.

    A Header flip changes placement, never the authored preferred size.  The
    optional content-extent override remains the existing sole reflow input.
    """
    for family in ("GmailPresentation.qml", "RedditPresentation.qml"):
        qml = source(family)
        preferred = qml.split('    preferredContentWidth:', 1)[1].split(
            '    preferredContentHeight:', 1
        )[0]
        canonical = qml.split('    readonly property real canonicalPreferredWidth:', 1)[1].split(
            '    readonly property real canonicalAuthoredHeight:', 1
        )[0]
        assert '? cExtentW : canonicalPreferredWidth' in preferred
        assert 'refreshGlyph.width' not in preferred
        assert 'headerArea.width' not in preferred
        assert 'authoredRoot.width' not in preferred
        assert 'refreshTarget.implicitWidth' in canonical
        assert 'headerFrame.implicitWidth' in canonical
    reddit = source('RedditPresentation.qml')
    header = reddit.split('"roleId": "header"', 1)[1].split('})', 1)[0]
    refresh = reddit.split('"roleId": "refresh"', 1)[1].split('})', 1)[0]
    assert '"allowParentGrowth": false' not in header
    assert '"allowParentGrowth": false' not in refresh


def test_media_flip_drag_detachment_keeps_stable_slot_and_authoritative_offset():
    media = source('MediaPresentation.qml')
    # One initial flip displacement is folded into a CUSTOM offset at the
    # existing geometry owner, never recomputed from that live offset.
    assert 'readonly property real unflippedAuthoredX:' in media
    assert 'property real customEditPlacementCompensationX:' in media
    assert '? -unflippedAuthoredX : 0.0' in media
    assert 'mediaRoot.headerFlipped && mediaRoot.artworkOnAuthoredRail' in media
    # CUSTOM seek geometry must NOT determine the parent flow reservation.
    assert 'height: visible ? mediaRoot.canonicalProgressBandHeight : 0.0' in media
    assert 'height: visible ? progressTrack.height + 8.0 : 0.0' not in media
    artwork = media.split('id: artworkFrame', 1)[1].split('id: progressBand', 1)[0]
    assert 'readonly property real authoredSeekX:' in artwork
    assert 'progressTrack.x' not in artwork and 'progressTrack.width' not in artwork
    assert 'clip: true' in media
    assert 'clip: mediaRoot.mediaModel.contentExtentActive' not in media


def test_opt_in_geo_event_boundaries_do_not_trace_pointer_cadence():
    owner = (ROOT / 'rendering/quick/custom_layout_owner.py').read_text(encoding='utf-8')
    assert 'is_geometry_logging_enabled()' in owner
    assert '[GEO_CHILD] begin' in owner and '[GEO_CHILD] end' in owner
    assert '[GEO_CHILD] flip' in owner and '[GEO_CHILD] restore' in owner
    sample = owner.split('def update_child_move(', 1)[1].split('def flip_child_alignment(', 1)[0]
    assert sample.index('if finalize:') < sample.index('[GEO_CHILD] end')
