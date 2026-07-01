"""Native intel export — GeoJSON + STIX 2.1 for geolens image geolocation."""

import json

import pytest

from geolens import intel

_WITH_GPS = {
    "has_exif": True,
    "gps": {"latitude": 48.8584, "longitude": 2.2945, "altitude": 33.0},
    "make": "Canon", "model": "EOS 5D",
    "maps_url": "https://www.openstreetmap.org/?mlat=48.8584&mlon=2.2945",
}
_NO_GPS = {"has_exif": False, "gps": None}


def test_geojson_point_lonlat():
    doc = json.loads(intel.to_geojson(_WITH_GPS))
    assert doc["type"] == "FeatureCollection"
    assert len(doc["features"]) == 1
    # [lon, lat, alt] — altitude carried through when present (see _altitude)
    assert doc["features"][0]["geometry"]["coordinates"] == [2.2945, 48.8584, 33.0]
    assert doc["features"][0]["properties"]["make"] == "Canon"
    assert doc["features"][0]["properties"]["altitude"] == 33.0


def test_geojson_empty_without_gps():
    doc = json.loads(intel.to_geojson(_NO_GPS))
    assert doc["features"] == []


def test_stix_with_gps_has_location():
    doc = json.loads(intel.to_stix(_WITH_GPS))
    assert doc["type"] == "bundle"
    types = {o["type"] for o in doc["objects"]}
    assert {"report", "location", "observed-data", "note"} <= types
    loc = next(o for o in doc["objects"] if o["type"] == "location")
    assert loc["latitude"] == 48.8584 and loc["longitude"] == 2.2945
    for o in doc["objects"]:
        if o["type"] != "bundle":
            assert o.get("spec_version") == "2.1"


def test_stix_without_gps_still_valid():
    doc = json.loads(intel.to_stix(_NO_GPS))
    assert doc["type"] == "bundle"
    types = {o["type"] for o in doc["objects"]}
    assert "note" in types and "location" not in types
    report = next(o for o in doc["objects"] if o["type"] == "report")
    ids = {o["id"] for o in doc["objects"]}
    assert all(r in ids for r in report["object_refs"])


def test_deterministic():
    assert intel.to_stix(_WITH_GPS) == intel.to_stix(_WITH_GPS)
    assert intel.to_geojson(_WITH_GPS) == intel.to_geojson(_WITH_GPS)


def test_export_dispatch_and_error():
    assert json.loads(intel.export(_WITH_GPS, "geojson"))["type"] == "FeatureCollection"
    assert json.loads(intel.export(_WITH_GPS, "stix"))["type"] == "bundle"
    with pytest.raises(ValueError):
        intel.export(_WITH_GPS, "gpx")
