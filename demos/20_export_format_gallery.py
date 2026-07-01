"""Scenario 20 - one fix, every output format side by side.

A quick reference: take a single analyzed image and render it through every
GEOLENS output surface — table-style key/value, GeoJSON, and STIX 2.1 — plus the
graceful empty variants. Handy for deciding which format to pipe where. Offline.
"""
import json
import datetime as _dt

from _common import rule, make_exif_jpeg
from geolens import intel
from geolens.core import analyze_image


def main() -> None:
    rule("EXPORT GALLERY  -  one fix rendered every way")

    r = analyze_image(
        make_exif_jpeg(43.7696, 11.2558, make="Nikon", model="Z8",
                       when=_dt.datetime(2026, 6, 21, 11, tzinfo=_dt.timezone.utc),
                       altitude_m=50.0),
        image_url="https://example.com/firenze.jpg")

    print("\n1) FLAT KEY/VALUE (human triage):")
    for k in ("has_exif", "make", "model", "datetime"):
        if k in r:
            print(f"     {k:<12} {r[k]}")
    print(f"     gps          {r['gps']}")

    print("\n2) GEOJSON (maps):")
    gj = json.loads(intel.export(r, "geojson"))
    print(f"     {gj['type']}, {len(gj['features'])} feature, "
          f"coords {gj['features'][0]['geometry']['coordinates']}")

    print("\n3) STIX 2.1 (TIP):")
    stix = json.loads(intel.export(r, "stix"))
    print(f"     {stix['type']} with {len(stix['objects'])} objects: "
          f"{sorted({o['type'] for o in stix['objects']})}")

    print("\n4) GRACEFUL EMPTY (scrubbed image) — both formats still valid:")
    empty = analyze_image(b"\xff\xd8\xff\xd9")
    egj = json.loads(intel.export(empty, "geojson"))
    estix = json.loads(intel.export(empty, "stix"))
    print(f"     geojson features -> {len(egj['features'])}")
    print(f"     stix objects     -> {sorted({o['type'] for o in estix['objects']})}")

    print("\nPick table for eyes, GeoJSON for maps, STIX for the platform.")


if __name__ == "__main__":
    main()
