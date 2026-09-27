"""Static ordinary-widget family component registry.

This registry contains presentation component metadata only. Canonical widget
membership and activation remain owned by ``widget_family_catalog``; the Quick
scene only needs to know which retained component presents an admitted family.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrdinaryWidgetFamilyComponent:
    """One retained family component admitted to the Quick scene."""

    family_id: str
    qml_filename: str
    presentation_model_kind: str
    # The component's required model property (its one initial property).
    model_property: str


ORDINARY_WIDGET_FAMILY_COMPONENTS: tuple[OrdinaryWidgetFamilyComponent, ...] = (
    OrdinaryWidgetFamilyComponent(
        family_id="clocks",
        qml_filename="ClockPresentation.qml",
        presentation_model_kind="ClockPresentationModel",
        model_property="clockModel",
    ),
    OrdinaryWidgetFamilyComponent(
        family_id="weather",
        qml_filename="WeatherPresentation.qml",
        presentation_model_kind="WeatherPresentationModel",
        model_property="weatherModel",
    ),
    OrdinaryWidgetFamilyComponent(
        family_id="media",
        qml_filename="MediaPresentation.qml",
        presentation_model_kind="MediaPresentationModel",
        model_property="mediaModel",
    ),
    OrdinaryWidgetFamilyComponent(
        family_id="reddit",
        qml_filename="RedditPresentation.qml",
        presentation_model_kind="RedditPresentationModel",
        model_property="redditModel",
    ),
    OrdinaryWidgetFamilyComponent(
        family_id="feeds",
        qml_filename="FeedPresentation.qml",
        presentation_model_kind="FeedPresentationModel",
        model_property="feedModel",
    ),
    OrdinaryWidgetFamilyComponent(
        family_id="gmail",
        qml_filename="GmailPresentation.qml",
        presentation_model_kind="GmailPresentationModel",
        model_property="gmailModel",
    ),
    OrdinaryWidgetFamilyComponent(
        family_id="achievement_pulse",
        qml_filename="AchievementPulsePresentation.qml",
        presentation_model_kind="AchievementPulsePresentationModel",
        model_property="achievementModel",
    ),
    OrdinaryWidgetFamilyComponent(
        family_id="abandonment_issues",
        qml_filename="AbandonmentIssuesPresentation.qml",
        presentation_model_kind="AbandonmentIssuesPresentationModel",
        model_property="abandonmentModel",
    ),
    OrdinaryWidgetFamilyComponent(
        family_id="friend_pulse",
        qml_filename="FriendPulsePresentation.qml",
        presentation_model_kind="FriendPulsePresentationModel",
        model_property="friendPulseModel",
    ),
    OrdinaryWidgetFamilyComponent(
        family_id="steam_progress",
        qml_filename="GamesYouFollowPresentation.qml",
        presentation_model_kind="GamesYouFollowPresentationModel",
        model_property="followedModel",
    ),
    OrdinaryWidgetFamilyComponent(
        family_id="system_audio_osd",
        qml_filename="SystemAudioOSDPresentation.qml",
        presentation_model_kind="SystemAudioOSDPresentationModel",
        model_property="osdModel",
    ),
    OrdinaryWidgetFamilyComponent(
        family_id="system_stats",
        qml_filename="SystemStatsPresentation.qml",
        presentation_model_kind="SystemStatsPresentationModel",
        model_property="systemStatsModel",
    ),
)


def ordinary_widget_family_component(
    family_id: str,
) -> OrdinaryWidgetFamilyComponent:
    """Return the exact static component descriptor for ``family_id``."""

    normalized = str(family_id or "").strip().lower()
    for descriptor in ORDINARY_WIDGET_FAMILY_COMPONENTS:
        if descriptor.family_id == normalized:
            return descriptor
    raise KeyError(f"unknown ordinary-widget family: {family_id!r}")
