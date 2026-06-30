"""Scenario 5 - platform / SOC engineers wiring geolens into a stack.

A geolocation finding is only useful if it lands where the rest of the team
works: a map, a TIP, a SIEM. GEOLENS ships native, zero-dependency exporters -
GeoJSON for Leaflet/Mapbox/QGIS/kepler, and a STIX 2.1 bundle for OpenCTI / a
threat-intel platform. This demo runs both off one analyzed image, offline, and
shows that they degrade gracefully when no GPS is present.
"""
import json
import datetime as _dt

from _common import rule, make_exif_jpeg
from geolens import intel
from geolens.core import analyze_image


def main() -> None:
    rule("EXPORT & INTEROP  -  one fix, GeoJSON for maps + STIX for the TIP")

    img = make_exif_jpeg(38.8895, -77.0353, make="Sony", model="ILCE-7M4",
                         when=_dt.datetime(2026, 6, 21, 17, 0, 0,
                                           tzinfo=_dt.timezone.utc), altitude_m=18.0)
    result = analyze_image(img, image_url="https://example.com/scene.jpg")
    print(f"\nAnalyzed image -> GPS {result['gps']}, camera {result.get('make')} "
          f"{result.get('model')}\n")

    print("1) GeoJSON (drop into Leaflet / Mapbox / QGIS / kepler.gl):\n")
    gj = json.loads(intel.export(result, "geojson"))
    feat = gj["features"][0]
    print(f"     type        {gj['type']}")
    print(f"     geometry    {feat['geometry']['type']} {feat['geometry']['coordinates']}  [lon, lat]")
    print(f"     source prop {feat['properties'].get('source')}")

    print("\n2) STIX 2.1 bundle (drop into OpenCTI / a TIP):\n")
    bundle = json.loads(intel.export(result, "stix"))
    print(f"     bundle id   {bundle['id'][:46]}")
    for o in bundle["objects"]:
        print(f"     - {o['type']}")

    print("\n3) graceful with NO GPS (scrubbed image) - still valid documents:\n")
    scrubbed = analyze_image(b"\xff\xd8\xff\xd9")  # a valid but metadata-free JPEG
    empty_gj = json.loads(intel.export(scrubbed, "geojson"))
    print(f"     GeoJSON features when scrubbed -> {len(empty_gj['features'])} (empty, still valid)")
    stix_no_gps = json.loads(intel.export(scrubbed, "stix"))
    note = [o for o in stix_no_gps["objects"] if o["type"] == "note"][0]
    print(f"     STIX note labels -> {note['labels']}")

    print("\nSafe to run unconditionally in a pipeline: it always emits valid output.")


if __name__ == "__main__":
    main()
