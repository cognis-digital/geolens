"""Scenario 11 - N/S/E/W hemisphere round-trip through EXIF.

GPS coordinates carry hemisphere refs (N/S, E/W) that flip the sign. This
scenario synthesizes a real EXIF JPEG for a landmark in each quadrant of the
globe, parses it back, and confirms the signs survive the round trip — the kind
of regression that silently corrupts a whole map if a ref is dropped. Offline.
"""
from _common import rule, make_exif_jpeg
from geolens.core import analyze_image


def main() -> None:
    rule("HEMISPHERE MATRIX  -  N/S/E/W signs survive the EXIF round trip")

    landmarks = [
        ("Eiffel Tower (N,E)", 48.8584, 2.2945),
        ("Sydney Opera (S,E)", -33.8568, 151.2153),
        ("Statue of Liberty (N,W)", 40.6892, -74.0445),
        ("Christ Redeemer (S,W)", -22.9519, -43.2105),
    ]

    print("\n  {:<26} {:>10} {:>11}  {}".format("landmark", "lat", "lon", "ok?"))
    print("  " + "-" * 58)
    all_ok = True
    for name, lat, lon in landmarks:
        img = make_exif_jpeg(lat, lon)
        got = analyze_image(img)["gps"]
        ok = (abs(got["latitude"] - lat) < 0.01 and abs(got["longitude"] - lon) < 0.01
              and (got["latitude"] < 0) == (lat < 0)
              and (got["longitude"] < 0) == (lon < 0))
        all_ok = all_ok and ok
        print(f"  {name:<26} {got['latitude']:>10.4f} {got['longitude']:>11.4f}  "
              f"{'yes' if ok else 'NO'}")

    print(f"\nAll four quadrants round-trip cleanly: {all_ok}")
    print("If a hemisphere ref were dropped, a Sydney pin would land in the North Atlantic.")


if __name__ == "__main__":
    main()
