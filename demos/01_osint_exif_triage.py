"""Scenario 1 - OSINT analysts.

The first question on any image: where was it taken, with what, and where do I
chase the source? GEOLENS reads the EXIF/GPS straight off the bytes (no cloud,
no upload), recovers the decimal fix, and hands you ready-to-open reverse-image
search URLs. This runs against the *bundled* geotagged sample image.
"""
from _common import rule, read_image, SAMPLE_GEOTAGGED
from geolens.core import analyze_image


def main() -> None:
    rule("OSINT EXIF TRIAGE  -  where, with what, and where to chase next")

    print("\nTarget image: demos/01-basic/sample_geotagged.jpg (read off disk, offline)\n")
    data = read_image(SAMPLE_GEOTAGGED)
    result = analyze_image(data, image_url="https://example.com/leaked.jpg")

    print(f"1) has_exif        -> {result['has_exif']}")
    gps = result["gps"]
    if gps:
        print(f"2) GPS fix         -> lat {gps['latitude']}, lon {gps['longitude']}")
        if "altitude_m" in gps:
            print(f"   altitude        -> {gps['altitude_m']} m")
        print(f"3) map link        -> {result['maps_url']}")

    print("\n4) reverse-search leads (open these to find where else it appears):")
    for engine, url in result["reverse_search"].items():
        print(f"     {engine:<14} {url}")

    print("\nFix recovered from metadata alone - no pixels analyzed, no network call.")
    print("That coordinate is the starting pin; the search URLs widen the net.")


if __name__ == "__main__":
    main()
