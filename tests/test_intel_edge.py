"""GeoJSON / STIX export edge cases and the altitude-key fix.

Confirms the exporters emit valid, deterministic documents across GPS/no-GPS
inputs, that altitude flows through under either key spelling, and that STIX
object_refs are internally consistent.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geolens import intel  # noqa: E402

WITH_ALT_M = {
    "has_exif": True,
    "gps": {"latitude": 38.8895, "longitude": -77.0353, "altitude_m": 18.0},
    "make": "Sony", "model": "ILCE-7M4",
    "maps_url": "https://www.openstreetmap.org/?mlat=38.8895&mlon=-77.0353",
}
WITH_ALT_LEGACY = {
    "has_exif": True,
    "gps": {"latitude": 1.0, "longitude": 2.0, "altitude": 42.0},
}
NO_ALT = {"has_exif": True, "gps": {"latitude": 10.0, "longitude": 20.0}}
NO_GPS = {"has_exif": False, "gps": None}
EMPTY = {}


def test_altitude_m_key_reaches_geojson():
    doc = json.loads(intel.to_geojson(WITH_ALT_M))
    coords = doc["features"][0]["geometry"]["coordinates"]
    assert coords == [-77.0353, 38.8895, 18.0]
    assert doc["features"][0]["properties"]["altitude"] == 18.0


def test_legacy_altitude_key_still_supported():
    doc = json.loads(intel.to_geojson(WITH_ALT_LEGACY))
    assert doc["features"][0]["geometry"]["coordinates"][2] == 42.0


def test_no_altitude_two_element_coordinates():
    doc = json.loads(intel.to_geojson(NO_ALT))
    assert doc["features"][0]["geometry"]["coordinates"] == [20.0, 10.0]
    assert "altitude" not in doc["features"][0]["properties"]


def test_geojson_empty_when_no_gps():
    assert json.loads(intel.to_geojson(NO_GPS))["features"] == []


def test_geojson_empty_when_result_empty():
    doc = json.loads(intel.to_geojson(EMPTY))
    assert doc["type"] == "FeatureCollection"
    assert doc["features"] == []


def test_geojson_partial_gps_missing_lon():
    doc = json.loads(intel.to_geojson({"gps": {"latitude": 5.0}}))
    assert doc["features"] == []


def test_stix_bundle_shape_with_gps():
    doc = json.loads(intel.to_stix(WITH_ALT_M))
    assert doc["type"] == "bundle"
    types = {o["type"] for o in doc["objects"]}
    assert {"report", "location", "observed-data", "note"} <= types


def test_stix_all_refs_resolve():
    doc = json.loads(intel.to_stix(WITH_ALT_M))
    ids = {o["id"] for o in doc["objects"]}
    report = next(o for o in doc["objects"] if o["type"] == "report")
    for ref in report["object_refs"]:
        assert ref in ids


def test_stix_spec_version_on_all_objects():
    doc = json.loads(intel.to_stix(WITH_ALT_M))
    for o in doc["objects"]:
        if o["type"] != "bundle":
            assert o.get("spec_version") == "2.1"


def test_stix_no_gps_note_only():
    doc = json.loads(intel.to_stix(NO_GPS))
    types = {o["type"] for o in doc["objects"]}
    assert "note" in types
    assert "location" not in types


def test_stix_no_gps_note_labels_include_no_exif():
    doc = json.loads(intel.to_stix(NO_GPS))
    note = next(o for o in doc["objects"] if o["type"] == "note")
    assert "no-exif" in note["labels"]


def test_stix_note_refs_itself_when_no_gps():
    doc = json.loads(intel.to_stix(NO_GPS))
    note = next(o for o in doc["objects"] if o["type"] == "note")
    assert note["object_refs"] == [note["id"]]


def test_deterministic_stix():
    assert intel.to_stix(WITH_ALT_M) == intel.to_stix(WITH_ALT_M)


def test_deterministic_geojson():
    assert intel.to_geojson(WITH_ALT_M) == intel.to_geojson(WITH_ALT_M)


def test_export_dispatch_geojson():
    assert json.loads(intel.export(WITH_ALT_M, "geojson"))["type"] == "FeatureCollection"


def test_export_dispatch_stix():
    assert json.loads(intel.export(WITH_ALT_M, "stix"))["type"] == "bundle"


def test_export_case_insensitive():
    assert json.loads(intel.export(WITH_ALT_M, "GeoJSON"))["type"] == "FeatureCollection"
    assert json.loads(intel.export(WITH_ALT_M, "STIX"))["type"] == "bundle"


def test_export_unknown_format_raises():
    with pytest.raises(ValueError):
        intel.export(WITH_ALT_M, "gpx")


def test_export_unknown_format_lists_options():
    with pytest.raises(ValueError) as exc:
        intel.export(WITH_ALT_M, "csv")
    assert "geojson" in str(exc.value) and "stix" in str(exc.value)


def test_maps_url_becomes_stix_external_reference():
    doc = json.loads(intel.to_stix(WITH_ALT_M))
    note = next(o for o in doc["objects"] if o["type"] == "note")
    refs = note.get("external_references", [])
    assert any(r["source_name"] == "openstreetmap" for r in refs)
