"""Colour ramps for water test strip charts.

These ramps are used both by:
- scripts/make_demo_strips.py to generate synthetic demo images
- the /api/strip-chart endpoint to document the reference chart swatches

Each ramp is keyed by canonical parameter name from standards.STRIP_PARAMS.
The swatches are labelled as the "reference chart used by synthetic demo strips", not a lab standard.

Source: Colour ramps loosely modelled on common retail 9-in-1 drinking water test strips.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# Colour ramps keyed by canonical parameter keys. Values are (value, (r,g,b)) tuples matching
# the original CHART in scripts/make_demo_strips.py so the script's output images do not change.
STRIP_CHARTS: Dict[str, Dict[str, object]] = {
    "ph": {
        "label": "pH",
        "unit": "",
        "swatches": [
            (6.0, (236, 160, 60)),
            (6.5, (230, 186, 70)),
            (7.0, (200, 190, 80)),
            (7.5, (150, 170, 90)),
            (8.0, (100, 150, 110)),
            (8.5, (70, 120, 130)),
        ],
    },
    "total_hardness": {
        "label": "Hardness",
        "unit": "ppm",
        "swatches": [
            (0, (60, 90, 170)),
            (50, (90, 90, 170)),
            (120, (130, 90, 160)),
            (250, (170, 80, 140)),
            (425, (200, 70, 120)),
            (1000, (210, 60, 100)),
        ],
    },
    "total_alkalinity": {
        "label": "Alkalinity",
        "unit": "ppm",
        "swatches": [
            (0, (225, 200, 90)),
            (40, (190, 190, 100)),
            (120, (130, 170, 120)),
            (180, (90, 150, 140)),
            (240, (60, 120, 140)),
            (360, (40, 100, 130)),
        ],
    },
    "nitrate": {
        "label": "Nitrate",
        "unit": "ppm",
        "swatches": [
            (0, (250, 245, 235)),
            (10, (245, 215, 225)),
            (25, (235, 180, 205)),
            (50, (220, 140, 180)),
            (100, (200, 100, 160)),
            (250, (170, 60, 130)),
        ],
    },
    "nitrite": {
        "label": "Nitrite",
        "unit": "ppm",
        "swatches": [
            (0, (250, 245, 235)),
            (0.5, (245, 225, 230)),
            (1, (240, 200, 215)),
            (3, (225, 160, 195)),
            (5, (205, 120, 175)),
            (10, (180, 80, 150)),
        ],
    },
    "free_chlorine": {
        "label": "Free Cl",
        "unit": "ppm",
        "swatches": [
            (0, (250, 248, 240)),
            (0.5, (225, 230, 240)),
            (1, (195, 210, 235)),
            (3, (150, 180, 225)),
            (5, (110, 150, 210)),
            (10, (70, 110, 190)),
        ],
    },
    "iron": {
        "label": "Iron",
        "unit": "ppm",
        "swatches": [
            (0, (250, 245, 230)),
            (0.3, (245, 230, 200)),
            (1, (235, 205, 160)),
            (3, (215, 170, 120)),
            (5, (195, 140, 90)),
            (10, (170, 110, 70)),
        ],
    },
    "fluoride": {
        "label": "Fluoride",
        "unit": "ppm",
        "swatches": [
            (0, (240, 120, 150)),
            (0.5, (235, 140, 165)),
            (1, (230, 165, 180)),
            (1.5, (225, 190, 195)),
            (2, (220, 210, 210)),
            (4, (215, 225, 225)),
        ],
    },
    "lead": {
        "label": "Lead",
        "unit": "ppm",
        "swatches": [
            (0, (250, 250, 245)),
            (0.01, (240, 235, 240)),
            (0.05, (225, 210, 230)),
            (0.1, (205, 180, 215)),
            (0.5, (180, 150, 200)),
            (1, (150, 120, 185)),
        ],
    },
    # other parameters (arsenic, copper, tds, chloride, sulphate, manganese) have no chart in the original
}


def rgb_tuple_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def get_swatches_by_param(canonical_key: str) -> List[Tuple[float, Tuple[int, int, int]]] | None:
    """Return list of (value, (r,g,b)) tuples for a parameter key, or None if not found."""
    chart = STRIP_CHARTS.get(canonical_key)
    return chart["swatches"] if chart else None


def get_swatches_hex_by_param(canonical_key: str) -> List[dict] | None:
    """Return list of {"value": v, "hex": "#rrggbb"} dicts for a parameter key, or None if not found.
    """
    sw = get_swatches_by_param(canonical_key)
    if not sw:
        return None
    return [{"value": v, "hex": rgb_tuple_to_hex(rgb)} for v, rgb in sw]
