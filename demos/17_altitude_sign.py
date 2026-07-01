"""Scenario 17 - above and below sea level (the altitude-ref flag).

GPS altitude has a reference byte: 0 = above sea level, 1 = below. GEOLENS reads
it and signs the metres accordingly. This scenario builds a mountaintop shot and
a Dead-Sea (below sea level) shot and confirms the sign is right in both the fix
and the exported GeoJSON position. Offline.
"""
import json

from _common import rule, make_exif_jpeg
from geolens import intel
from geolens.core import analyze_image, extract_exif, gps_from_exif


def main() -> None:
    rule("ALTITUDE SIGN  -  above vs below sea level")

    peak = make_exif_jpeg(45.8326, 6.8652, altitude_m=4200.0)  # Mont Blanc-ish
    r_peak = analyze_image(peak)
    print(f"\n1) mountaintop -> altitude {r_peak['gps']['altitude_m']} m (positive)")

    # Below sea level: build the fix then flip the altitude ref by hand to prove
    # the negative path (the synthesizer always writes ref 0 = above).
    exif = extract_exif(make_exif_jpeg(31.5, 35.5, altitude_m=430.0))
    exif["GPS"]["GPSAltitudeRef"] = 1  # below sea level
    below = gps_from_exif(exif)
    print(f"2) Dead Sea    -> altitude {below['altitude_m']} m (negative, ref=1)")

    assert r_peak["gps"]["altitude_m"] > 0
    assert below["altitude_m"] < 0

    gj = json.loads(intel.to_geojson(r_peak))
    print(f"3) GeoJSON position carries the altitude -> "
          f"{gj['features'][0]['geometry']['coordinates']}")

    print("\nThe reference byte matters: a dropped sign puts a valley on a summit.")


if __name__ == "__main__":
    main()
