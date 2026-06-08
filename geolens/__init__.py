"""GEOLENS — image geolocation toolkit (stdlib only).

EXIF GPS extraction, sun-position / shadow geolocation math, OCR-target
preprocessing hints, and reverse-search query generation. No network, no
third-party dependencies.
"""
from .core import (
    extract_exif,
    gps_from_exif,
    sun_position,
    shadow_bearing_to_azimuth,
    estimate_latitude_from_shadow,
    reverse_search_urls,
    analyze_image,
)

TOOL_NAME = "geolens"
TOOL_VERSION = "1.0.0"

__all__ = [
    "extract_exif",
    "gps_from_exif",
    "sun_position",
    "shadow_bearing_to_azimuth",
    "estimate_latitude_from_shadow",
    "reverse_search_urls",
    "analyze_image",
    "TOOL_NAME",
    "TOOL_VERSION",
]
