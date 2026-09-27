"""Every catalogued widget has a real display name, never its raw persistence key."""

from core.feeds.news import NEWS_WIDGET_IDS
from core.settings.widget_family_catalog import (
    _MEMBER_LABELS,
    get_widget_family_catalog,
    get_widget_member_label,
)


def test_every_member_has_an_authored_label():
    # The key-derived fallback is how "steam_progress" became "Steam Progress";
    # every catalogued member must resolve from an authored name instead.
    for family in get_widget_family_catalog():
        for member in family.member_widget_ids:
            authored = (
                member in _MEMBER_LABELS
                or member in NEWS_WIDGET_IDS
                or family.member_widget_ids == (member,)
            )
            assert authored, member
            assert get_widget_member_label(member).strip(), member


def test_arrange_wizard_and_predictor_share_the_catalog_name():
    from ui.onboarding.selection_pages import _member_label
    from ui.widget_stack_predictor import WidgetType, _get_widget_display_name

    for family in get_widget_family_catalog():
        if len(family.member_widget_ids) < 2:
            continue
        for member in family.member_widget_ids:
            assert _member_label(member, family) == get_widget_member_label(member)
    for widget_type in WidgetType:
        assert _get_widget_display_name(widget_type) == get_widget_member_label(widget_type.value)
