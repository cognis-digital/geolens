"""Scenario 13 - batch a folder into one GeoJSON FeatureCollection.

An analyst rarely has one photo — they have a folder. This scenario analyzes a
mixed set (several geotagged, one scrubbed), merges every recovered fix into a
single GeoJSON FeatureCollection ready to drop onto a Leaflet/QGIS map, and
reports how many pins made it. Offline; no fabricated coordinates.
"""
import json
import datetime as _dt

from _common import rule, make_exif_jpeg, read_image, SAMPLE_NO_EXIF
from geolens import intel
from geolens.core import analyze_image


def main() -> None:
    rule("BATCH -> GEOJSON  -  a folder of photos into one map layer")

    folder = [
        ("berlin.jpg", make_exif_jpeg(52.5163, 13.3777, make="Leica", model="Q3",
            when=_dt.datetime(2026, 5, 1, 10, tzinfo=_dt.timezone.utc))),
        ("rome.jpg", make_exif_jpeg(41.8902, 12.4922, make="Fuji", model="X100VI")),
        ("cairo.jpg", make_exif_jpeg(29.9792, 31.1342, make="Canon", model="R5",
            altitude_m=60.0)),
        ("scrubbed.jpg", read_image(SAMPLE_NO_EXIF)),
    ]

    features = []
    print(f"\nAnalyzing {len(folder)} files:\n")
    for name, data in folder:
        r = analyze_image(data)
        gj = json.loads(intel.export(r, "geojson"))
        n = len(gj["features"])
        for f in gj["features"]:
            f["properties"]["file"] = name
            features.append(f)
        tag = "pin" if n else "no fix"
        print(f"  {name:<14} -> {tag}")

    collection = {"type": "FeatureCollection", "features": features}
    print(f"\nMerged FeatureCollection: {len(features)} pin(s) across the folder.")
    print("Sample coordinates (lon, lat[, alt]):")
    for f in features:
        print(f"   {f['properties']['file']:<12} {f['geometry']['coordinates']}")

    # prove it serializes to valid JSON
    blob = json.dumps(collection)
    print(f"\nSerialized layer: {len(blob)} bytes of valid GeoJSON, ready for the map.")


if __name__ == "__main__":
    main()
