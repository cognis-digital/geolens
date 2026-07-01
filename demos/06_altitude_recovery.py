"""Scenario 6 - altitude in the fix (and where it now shows up).

GPS EXIF can carry an altitude (with a below-sea-level flag). GEOLENS recovers
it as ``altitude_m`` and — as of the altitude-key fix — carries it straight into
the GeoJSON position as a third [lon, lat, alt] coordinate, so 3D-aware maps
(kepler.gl, CesiumJS) get the elevation for free. Fully offline.
"""
import json
import datetime as _dt

from _common import rule, make_exif_jpeg
from geolens import intel
from geolens.core import analyze_image


def main() -> None:
    rule("ALTITUDE RECOVERY  -  elevation into the GeoJSON position")

    # A drone shot high above a ridge, and a photo from below sea level.
    ridge = make_exif_jpeg(46.5197, 6.6323, make="DJI", model="Mavic 3",
                           when=_dt.datetime(2026, 6, 21, 10, tzinfo=_dt.timezone.utc),
                           altitude_m=1240.0)
    r = analyze_image(ridge)
    print(f"\n1) ridge shot -> fix {r['gps']['latitude']}, {r['gps']['longitude']}, "
          f"altitude {r['gps']['altitude_m']} m")

    gj = json.loads(intel.export(r, "geojson"))
    coords = gj["features"][0]["geometry"]["coordinates"]
    print(f"2) GeoJSON coordinates -> {coords}   [lon, lat, alt]")
    assert len(coords) == 3, "altitude should ride along in the position"
    print(f"3) altitude property   -> {gj['features'][0]['properties']['altitude']} m")

    print("\nAltitude is no longer dropped on the way to the map — 3D maps get it.")


if __name__ == "__main__":
    main()
