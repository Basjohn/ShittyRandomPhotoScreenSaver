"""Neon Basin's canonical surface/body choices. Retired values migrate at input only."""
from types import MappingProxyType

BASIN_SURFACE_STYLES = MappingProxyType({
    "Vertices": 2, "Glass": 4, "Glass + Vertices": 6,
})
BASIN_BODY_MODES = MappingProxyType({"Sun": 0, "Moon": 1})
# Where Terrain Reaction's Growth may rise (the shader's uGrowthRegion): 0 is the neutral, no weighting at all.
BASIN_GROWTH_REGIONS = MappingProxyType({"Everywhere": 0, "Far Land": 1, "By Elevation": 2})
