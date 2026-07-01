"""Scenario 15 - a defensible STIX 2.1 case bundle (with self-check).

For a TIP / case-management platform, the STIX bundle has to be internally
consistent: every object_ref the report points at must resolve to an object in
the bundle, and every object must carry spec_version 2.1. This scenario builds a
bundle from a real analyzed image and validates those invariants itself, then
shows the graceful no-GPS variant. Offline.
"""
import json
import datetime as _dt

from _common import rule, make_exif_jpeg
from geolens import intel
from geolens.core import analyze_image


def _validate(bundle_json: str) -> list:
    doc = json.loads(bundle_json)
    problems = []
    if doc.get("type") != "bundle":
        problems.append("top-level type is not 'bundle'")
    objs = doc.get("objects", [])
    ids = {o["id"] for o in objs}
    for o in objs:
        if o.get("type") != "bundle" and o.get("spec_version") != "2.1":
            problems.append(f"{o.get('type')} missing spec_version 2.1")
    report = next((o for o in objs if o["type"] == "report"), None)
    if report:
        for ref in report.get("object_refs", []):
            if ref not in ids:
                problems.append(f"dangling ref {ref}")
    return problems


def main() -> None:
    rule("STIX CASE BUNDLE  -  build, then self-validate the invariants")

    img = make_exif_jpeg(50.4501, 30.5234, make="Sony", model="A7 IV",
                         when=_dt.datetime(2026, 4, 10, 9, tzinfo=_dt.timezone.utc),
                         altitude_m=180.0)
    r = analyze_image(img, image_url="https://example.com/evidence.jpg")
    bundle = intel.export(r, "stix")

    doc = json.loads(bundle)
    print(f"\nBundle {doc['id'][:46]}")
    print("Objects:")
    for o in doc["objects"]:
        extra = ""
        if o["type"] == "location":
            extra = f"  ({o['latitude']}, {o['longitude']})"
        print(f"   - {o['type']:<14} {o['id'][:44]}{extra}")

    problems = _validate(bundle)
    print(f"\nSelf-validation: {'CLEAN' if not problems else problems}")

    print("\nNo-GPS variant still validates (note-only, labelled no-exif):")
    empty = intel.export(analyze_image(b"\xff\xd8\xff\xd9"), "stix")
    print(f"   problems -> {_validate(empty) or 'none'}")


if __name__ == "__main__":
    main()
