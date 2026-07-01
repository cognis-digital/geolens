"""KML exporter — well-formed output, altitude, escaping, graceful empty."""
import os
import sys
from xml.dom import minidom

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geolens import intel  # noqa: E402

WITH_GPS = {
    "has_exif": True,
    "gps": {"latitude": 48.8584, "longitude": 2.2945, "altitude_m": 33.0},
    "make": "Canon", "model": "EOS 5D",
    "maps_url": "https://www.openstreetmap.org/?mlat=48.8584&mlon=2.2945",
}
NO_ALT = {"has_exif": True, "gps": {"latitude": 10.0, "longitude": 20.0}}
NO_GPS = {"has_exif": False, "gps": None}


def _parse(kml: str):
    return minidom.parseString(kml)  # raises if not well-formed XML


def test_kml_is_well_formed_xml():
    _parse(intel.to_kml(WITH_GPS))


def test_kml_has_placemark_with_gps():
    doc = _parse(intel.to_kml(WITH_GPS))
    assert doc.getElementsByTagName("Placemark")


def test_kml_coordinates_are_lon_lat_alt():
    doc = _parse(intel.to_kml(WITH_GPS))
    coord = doc.getElementsByTagName("coordinates")[0].firstChild.data
    assert coord == "2.2945,48.8584,33.0"


def test_kml_no_altitude_two_element_coord():
    doc = _parse(intel.to_kml(NO_ALT))
    coord = doc.getElementsByTagName("coordinates")[0].firstChild.data
    assert coord == "20.0,10.0"


def test_kml_altitude_mode_present_only_with_alt():
    assert "altitudeMode" in intel.to_kml(WITH_GPS)
    assert "altitudeMode" not in intel.to_kml(NO_ALT)


def test_kml_empty_but_valid_without_gps():
    kml = intel.to_kml(NO_GPS)
    doc = _parse(kml)
    assert doc.getElementsByTagName("Document")
    assert not doc.getElementsByTagName("Placemark")


def test_kml_description_carries_camera():
    doc = _parse(intel.to_kml(WITH_GPS))
    desc = doc.getElementsByTagName("description")[0].firstChild.data
    assert "Canon" in desc and "EOS 5D" in desc


def test_kml_escapes_xml_metacharacters():
    hostile = {"has_exif": True,
               "gps": {"latitude": 1.0, "longitude": 2.0},
               "make": "A&B", "model": "<script>"}
    kml = intel.to_kml(hostile)
    _parse(kml)  # must still be well-formed
    assert "&amp;" in kml
    assert "<script>" not in kml


def test_kml_deterministic():
    assert intel.to_kml(WITH_GPS) == intel.to_kml(WITH_GPS)


def test_export_dispatch_kml():
    assert intel.export(WITH_GPS, "kml").lstrip().startswith("<?xml")


def test_export_dispatch_kml_case_insensitive():
    assert "kml" in intel.export(WITH_GPS, "KML").lower()


def test_export_error_message_lists_kml():
    with pytest.raises(ValueError) as exc:
        intel.export(WITH_GPS, "gpx")
    assert "kml" in str(exc.value)


def test_reexported_from_package():
    import geolens
    assert hasattr(geolens, "to_kml")
