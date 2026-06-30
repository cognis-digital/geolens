"""Scenario 3 - law enforcement & incident response.

A device is seized (or a leak dump lands) and you have a folder of images. You
need a fast, defensible first pass: which files carry location metadata, which
are scrubbed, and a STIX bundle you can drop straight into the case management /
threat-intel platform. GEOLENS does this per file, offline, with no upload.

Mixes the bundled clean image with in-memory real-EXIF fixtures to model a
realistic seized folder.
"""
import datetime as _dt

from _common import rule, read_image, make_exif_jpeg, SAMPLE_NO_EXIF
from geolens import intel
from geolens.core import analyze_image


def main() -> None:
    rule("SEIZED-FOLDER TRIAGE  -  who is geotagged, who is scrubbed, + STIX")

    # A realistic mixed folder: two geotagged, one scrubbed.
    folder = [
        ("DCIM_0007.jpg", make_exif_jpeg(40.6892, -74.0445, make="Samsung",
            model="SM-S921B", when=_dt.datetime(2026, 5, 2, 14, 11, 0,
            tzinfo=_dt.timezone.utc), altitude_m=12.0)),
        ("DCIM_0042.jpg", make_exif_jpeg(51.5007, -0.1246, make="Canon",
            model="EOS R6", when=_dt.datetime(2026, 5, 3, 9, 30, 0,
            tzinfo=_dt.timezone.utc))),
        ("clean_export.jpg", read_image(SAMPLE_NO_EXIF)),  # scrubbed (bundled)
    ]

    print(f"\nProcessing {len(folder)} file(s):\n")
    geotagged = 0
    last_hit = None
    for name, data in folder:
        r = analyze_image(data)
        if r["gps"]:
            geotagged += 1
            last_hit = r
            cam = f"{r.get('make','?')} {r.get('model','?')}"
            print(f"  [GEOTAGGED] {name:<18} {r['gps']['latitude']:>9.4f}, "
                  f"{r['gps']['longitude']:>9.4f}   {cam}")
        else:
            label = "scrubbed" if not r["has_exif"] else "no-gps"
            print(f"  [{label.upper():<9}] {name:<18} (no location metadata)")

    print(f"\nSummary: {geotagged}/{len(folder)} file(s) carry a GPS fix.")

    print("\nSTIX 2.1 bundle for the last geotagged file (drops into OpenCTI / a TIP):\n")
    bundle = intel.export(last_hit, "stix")
    # show the object types in the bundle, not 100 lines of JSON
    import json
    objs = json.loads(bundle)["objects"]
    for o in objs:
        extra = ""
        if o["type"] == "location":
            extra = f"  lat={o['latitude']} lon={o['longitude']}"
        print(f"     - {o['type']:<14} {o['id'][:48]}{extra}")
    print(f"\n   ({len(bundle)} bytes of valid STIX; pipe `--format stix` to a file for the real thing.)")
    print("\nEvery determination here is reproducible from the bytes - defensible in a report.")


if __name__ == "__main__":
    main()
