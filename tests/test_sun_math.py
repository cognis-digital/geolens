"""Solar-position math: physical corners, ranges, and error paths.

The NOAA algorithm is validated against known astronomy: equinox/solstice
declination, day/night sign of elevation, azimuth wrap, and pole/equator
behaviour, plus the input guards added to ``sun_position``.
"""
import datetime as dt
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geolens.core import sun_position, shadow_bearing_to_azimuth  # noqa: E402

UTC = dt.timezone.utc


class TestDeclination(unittest.TestCase):
    def test_summer_solstice_declination_near_positive_max(self):
        d = sun_position(0, 0, dt.datetime(2026, 6, 21, 12, tzinfo=UTC))["declination_deg"]
        self.assertAlmostEqual(d, 23.44, delta=0.3)

    def test_winter_solstice_declination_near_negative_max(self):
        d = sun_position(0, 0, dt.datetime(2026, 12, 21, 12, tzinfo=UTC))["declination_deg"]
        self.assertAlmostEqual(d, -23.44, delta=0.3)

    def test_march_equinox_declination_near_zero(self):
        d = sun_position(0, 0, dt.datetime(2026, 3, 20, 12, tzinfo=UTC))["declination_deg"]
        self.assertLess(abs(d), 1.0)

    def test_september_equinox_declination_near_zero(self):
        d = sun_position(0, 0, dt.datetime(2026, 9, 22, 12, tzinfo=UTC))["declination_deg"]
        self.assertLess(abs(d), 1.5)


class TestElevationSign(unittest.TestCase):
    def test_noon_sun_up_northern_summer(self):
        pos = sun_position(48.85, 2.29, dt.datetime(2026, 6, 21, 12, tzinfo=UTC))
        self.assertGreater(pos["elevation_deg"], 0)

    def test_antipode_is_night(self):
        # Sydney at Paris solar-noon UTC — sun well below horizon
        pos = sun_position(-33.87, 151.2, dt.datetime(2026, 6, 21, 12, tzinfo=UTC))
        self.assertLess(pos["elevation_deg"], 0)

    def test_elevation_never_exceeds_90(self):
        for month in range(1, 13):
            pos = sun_position(0, 0, dt.datetime(2026, month, 15, 12, tzinfo=UTC))
            self.assertLessEqual(pos["elevation_deg"], 90.0)
            self.assertGreaterEqual(pos["elevation_deg"], -90.0)


class TestAzimuth(unittest.TestCase):
    def test_azimuth_always_in_range(self):
        for hour in range(0, 24, 2):
            pos = sun_position(40.0, -74.0, dt.datetime(2026, 6, 21, hour, tzinfo=UTC))
            self.assertTrue(0.0 <= pos["azimuth_deg"] < 360.0)

    def test_afternoon_azimuth_is_west_of_south(self):
        # local afternoon in the northern hemisphere -> azimuth > 180
        pos = sun_position(40.0, 0.0, dt.datetime(2026, 6, 21, 14, tzinfo=UTC))
        self.assertGreater(pos["azimuth_deg"], 180.0)

    def test_morning_azimuth_is_east_of_south(self):
        pos = sun_position(40.0, 0.0, dt.datetime(2026, 6, 21, 8, tzinfo=UTC))
        self.assertLess(pos["azimuth_deg"], 180.0)


class TestTimezoneHandling(unittest.TestCase):
    def test_naive_datetime_treated_as_utc(self):
        naive = sun_position(48.85, 2.29, dt.datetime(2026, 6, 21, 12))
        aware = sun_position(48.85, 2.29, dt.datetime(2026, 6, 21, 12, tzinfo=UTC))
        self.assertAlmostEqual(naive["elevation_deg"], aware["elevation_deg"], places=3)

    def test_offset_timezone_normalized(self):
        # 12:00 at +02:00 == 10:00 UTC
        plus2 = dt.timezone(dt.timedelta(hours=2))
        a = sun_position(48.85, 2.29, dt.datetime(2026, 6, 21, 12, tzinfo=plus2))
        b = sun_position(48.85, 2.29, dt.datetime(2026, 6, 21, 10, tzinfo=UTC))
        self.assertAlmostEqual(a["elevation_deg"], b["elevation_deg"], places=3)


class TestPolesAndEquator(unittest.TestCase):
    def test_north_pole_summer_sun_up_all_day(self):
        for hour in (0, 6, 12, 18):
            pos = sun_position(90.0, 0.0, dt.datetime(2026, 6, 21, hour, tzinfo=UTC))
            self.assertGreater(pos["elevation_deg"], 0)

    def test_south_pole_summer_sun_down(self):
        pos = sun_position(-90.0, 0.0, dt.datetime(2026, 6, 21, 12, tzinfo=UTC))
        self.assertLess(pos["elevation_deg"], 0)

    def test_equator_equinox_high_sun(self):
        pos = sun_position(0.0, 0.0, dt.datetime(2026, 3, 20, 12, tzinfo=UTC))
        self.assertGreater(pos["elevation_deg"], 80.0)


class TestInputGuards(unittest.TestCase):
    def test_non_datetime_when_raises_typeerror(self):
        with self.assertRaises(TypeError):
            sun_position(0, 0, "2026-06-21")

    def test_lat_out_of_range(self):
        with self.assertRaises(ValueError):
            sun_position(91.0, 0.0, dt.datetime(2026, 6, 21, tzinfo=UTC))

    def test_lon_out_of_range(self):
        with self.assertRaises(ValueError):
            sun_position(0.0, 181.0, dt.datetime(2026, 6, 21, tzinfo=UTC))

    def test_nan_lat_rejected(self):
        with self.assertRaises(ValueError):
            sun_position(float("nan"), 0.0, dt.datetime(2026, 6, 21, tzinfo=UTC))

    def test_inf_lon_rejected(self):
        with self.assertRaises(ValueError):
            sun_position(0.0, float("inf"), dt.datetime(2026, 6, 21, tzinfo=UTC))

    def test_string_lat_rejected(self):
        with self.assertRaises(ValueError):
            sun_position("abc", 0.0, dt.datetime(2026, 6, 21, tzinfo=UTC))

    def test_boundary_lat_lon_accepted(self):
        for lat, lon in ((90, 180), (-90, -180), (0, 0)):
            pos = sun_position(lat, lon, dt.datetime(2026, 6, 21, 12, tzinfo=UTC))
            self.assertIn("elevation_deg", pos)


class TestShadowBearing(unittest.TestCase):
    def test_opposite_bearing(self):
        self.assertEqual(shadow_bearing_to_azimuth(0.0), 180.0)
        self.assertEqual(shadow_bearing_to_azimuth(90.0), 270.0)

    def test_wraps_mod_360(self):
        self.assertEqual(shadow_bearing_to_azimuth(270.0), 90.0)
        self.assertEqual(shadow_bearing_to_azimuth(360.0), 180.0)

    def test_result_always_in_range(self):
        for b in range(0, 360, 30):
            az = shadow_bearing_to_azimuth(float(b))
            self.assertTrue(0.0 <= az < 360.0)


if __name__ == "__main__":
    unittest.main()
