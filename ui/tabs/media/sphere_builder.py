"""Voxel Sphere's Settings body (mode id ``sphere``): the preset row and its Studio launcher.

Every Voxel Sphere control (including its audio analysis) is edited in the Studio, which has parity+ with the retired
buckets (``tests/test_visualizer_studio_parity.py`` proves it from the registries)."""
from ui.tabs.media.spec_mode_builder import build_studio_owned_mode_ui

INTRO = "The voxels, their finish, colour and reactivity are all edited live in the Studio."


def build_sphere_ui(tab, parent_layout) -> None:
    build_studio_owned_mode_ui(tab, parent_layout, "sphere", INTRO)
