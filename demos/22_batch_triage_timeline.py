"""Scenario 22 - triage a collected image set: cluster, fingerprint, timeline.

An analyst is handed a mixed folder of photos. GEOLENS:

1. splits geotagged from scrubbed and spatially clusters the geotagged ones
   (single-linkage by great-circle distance) - the "who was where" view;
2. builds a movement timeline ordered by capture time, with per-leg distance
   and implied speed, then exports it as a GeoJSON track for a map;
3. runs a camera-fingerprint consistency check across the set to surface a
   spliced-in, different-camera image.

Everything is synthesised in memory (real EXIF bytes) and runs offline.
"""
import datetime as _dt
import json

from _common import make_exif_jpeg, rule
from geolens.core import analyze_image
from geolens.forensics import (
    batch_triage,
    build_timeline,
    fingerprint_consistency,
    timeline_to_geojson,
)


def _synth_folder():
    """A route through Paris + one Sydney outlier + one scrubbed image."""
    base = _dt.datetime(2026, 6, 21, 9, 0, tzinfo=_dt.timezone.utc)
    specs = [
        ("0900_eiffel.jpg", 48.8584, 2.2945, 0, "Apple", "iPhone 15 Pro"),
        ("0930_trocadero.jpg", 48.8620, 2.2890, 30, "Apple", "iPhone 15 Pro"),
        ("1015_louvre.jpg", 48.8606, 2.3376, 75, "Apple", "iPhone 15 Pro"),
        # a very different camera spliced in - the fingerprint check should notice
        ("1800_sydney.jpg", -33.8688, 151.2093, 540, "Nikon", "Z9"),
    ]
    records = []
    for name, lat, lon, mins, make, model in specs:
        img = make_exif_jpeg(lat, lon, make=make, model=model,
                             when=base + _dt.timedelta(minutes=mins))
        rec = analyze_image(img)
        rec["id"] = name
        records.append(rec)
    # a scrubbed image (no EXIF at all)
    scrub = analyze_image(b"\xff\xd8\xff\xd9")
    scrub["id"] = "unknown_scrubbed.jpg"
    records.append(scrub)
    return records


def main() -> None:
    rule("BATCH TRIAGE  -  cluster, timeline, fingerprint a collected set")
    records = _synth_folder()

    # 1) triage + clustering
    tri = batch_triage(records, radius_km=2.0)
    print(f"\n1) {tri['total']} images: {tri['geotagged']} geotagged, "
          f"{tri['scrubbed']} scrubbed -> {tri['cluster_count']} location clusters")
    for i, c in enumerate(tri["clusters"], 1):
        ids = ", ".join(m["id"] for m in c["members"])
        print(f"   cluster {i} (n={c['size']}) @ "
              f"{c['centroid']['latitude']:.4f},{c['centroid']['longitude']:.4f}: {ids}")
    if tri["scrubbed_ids"]:
        print(f"   scrubbed (no GPS): {', '.join(tri['scrubbed_ids'])}")

    # 2) movement timeline + GeoJSON track
    tl = build_timeline(records)
    print(f"\n2) Movement timeline: {tl['event_count']} time-stamped fixes")
    for leg in tl["legs"]:
        spd = f"{leg['implied_speed_kmh']} km/h" if leg["implied_speed_kmh"] else "n/a"
        print(f"   {leg['from']} -> {leg['to']}: "
              f"{leg['distance_km']:.1f} km in {leg['elapsed_s']/3600:.2f} h ({spd})")
    gj = json.loads(timeline_to_geojson(tl))
    print(f"   GeoJSON track: {len(gj['features'])} features "
          f"(points + path) ready for Leaflet/QGIS/kepler")

    # 3) camera fingerprint consistency
    exifs = [r["exif"] for r in records if r.get("exif")]
    fp = fingerprint_consistency(exifs)
    print(f"\n3) Fingerprint check across {fp['count']} images: "
          f"single-source likely = {fp['single_source_likely']}")
    for flag in fp["flags"]:
        print(f"   [!] {flag}")

    print("\nOne folder -> a map, a track, and a tampering flag - all offline.")


if __name__ == "__main__":
    main()
