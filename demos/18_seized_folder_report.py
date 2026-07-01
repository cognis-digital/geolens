"""Scenario 18 - a printable triage report for a seized folder.

Extends the law-enforcement scenario into a single, defensible summary block: a
per-file table plus counts (geotagged / scrubbed / has-EXIF-no-GPS) and the
distinct camera models seen — the kind of first-pass report that goes at the top
of a case file. Every line is derived from the bytes. Offline.
"""
import datetime as _dt

from _common import rule, make_exif_jpeg, read_image, SAMPLE_NO_EXIF
from geolens.core import analyze_image


def main() -> None:
    rule("SEIZED-FOLDER REPORT  -  counts, cameras, and a defensible summary")

    folder = [
        ("IMG_0001.jpg", make_exif_jpeg(48.8584, 2.2945, make="Apple", model="iPhone 15 Pro")),
        ("IMG_0002.jpg", make_exif_jpeg(51.5007, -0.1246, make="Apple", model="iPhone 15 Pro",
            when=_dt.datetime(2026, 5, 3, 9, 30, tzinfo=_dt.timezone.utc))),
        ("IMG_0003.jpg", make_exif_jpeg(40.6892, -74.0445, make="Samsung", model="SM-S921B")),
        ("export_clean.jpg", read_image(SAMPLE_NO_EXIF)),
        ("random.bin", b"not an image at all"),
    ]

    geotagged = scrubbed = exif_no_gps = 0
    cameras = set()
    print(f"\n  {'file':<18} {'status':<12} {'camera':<20} location")
    print("  " + "-" * 66)
    for name, data in folder:
        r = analyze_image(data)
        cam = f"{r.get('make','')} {r.get('model','')}".strip()
        if cam:
            cameras.add(cam)
        if r["gps"]:
            geotagged += 1
            status, loc = "GEOTAGGED", f"{r['gps']['latitude']:.4f},{r['gps']['longitude']:.4f}"
        elif r["has_exif"]:
            exif_no_gps += 1
            status, loc = "EXIF/no-GPS", "-"
        else:
            scrubbed += 1
            status, loc = "scrubbed", "-"
        print(f"  {name:<18} {status:<12} {cam or '-':<20} {loc}")

    print(f"\n  SUMMARY  files={len(folder)}  geotagged={geotagged}  "
          f"exif_no_gps={exif_no_gps}  scrubbed={scrubbed}")
    print(f"  distinct cameras: {sorted(cameras)}")
    print("\n  Every determination above is reproducible from the file bytes.")


if __name__ == "__main__":
    main()
