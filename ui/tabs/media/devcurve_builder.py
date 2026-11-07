"""Spline Curve's Settings body (mode id ``devcurve``): the preset row and its Studio launcher.

Every Spline Curve control (including its audio analysis) is edited in the Studio, which has parity+ with the retired
buckets (``tests/test_visualizer_studio_parity.py`` proves it from the registries)."""
from ui.tabs.media.spec_mode_builder import build_studio_owned_mode_ui

INTRO = "Every layer's shape, colour and motion is edited live in the Studio."


def build_devcurve_ui(tab, parent_layout) -> None:
    build_studio_owned_mode_ui(tab, parent_layout, "devcurve", INTRO)
