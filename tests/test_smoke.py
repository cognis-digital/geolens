"""Smoke tests for GEOLENS — stdlib only, no network."""
import datetime as dt
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geolens import TOOL_NAME, TOOL_VERSION
from geolens.cli import main
from geolens.core import (
    analyze_image,
    estimate_latitude_from_shadow,
    extract_exif,
    gps_from_exif,
    reverse_search_urls,
    sun_position,
)

DEMO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "demos", "01-basic", "sample_geotagged.jpg",
)


def _build_geotagged_jpeg():
    """Construct a big-endian EXIF JPEG with GPS = Eiffel Tower."""
    def rat(n, d):
        return struct.pack(">II", n, d)

    ifd0_off = 8
    ifd0_size = 2 + 1 * 12 + 4
    gps_ifd_off = ifd0_off + ifd0_size
    gps_tags = 5
    gps_ifd_size = 2 + gps_tags * 12 + 4
    vals_off = gps_ifd_off + gps_ifd_size
    lat_off, lon_off, alt_off = vals_off, vals_off + 24, vals_off + 48

    def entry(tag, ft, ct, payload):
        return struct.pack(">HHI", tag, ft, ct) + payload

    gps = struct.pack(">H", gps_tags)
    gps += entry(0x0001, 2, 2, b"N\x00\x00\x00")
    gps += entry(0x0002, 5, 3, struct.pack(">I", lat_off))
    gps += entry(0x0003, 2, 2, b"E\x00\x00\x00")
    gps += entry(0x0004, 5, 3, struct.pack(">I", lon_off))
    gps += entry(0x0006, 5, 1, struct.pack(">I", alt_off))
    gps += struct.pack(">I", 0)

    ifd0 = struct.pack(">H", 1)
    ifd0 += entry(0x8825, 4, 1, struct.pack(">I", gps_ifd_off))
    ifd0 += struct.pack(">I", 0)

    tiff = b"MM" + struct.pack(">H", 42) + struct.pack(">I", ifd0_off)
    tiff += ifd0 + gps
    tiff += rat(48, 1) + rat(51, 1) + rat(296, 10)
    tiff += rat(2, 1) + rat(17, 1) + rat(402, 10)
    tiff += rat(33, 1)

    payload = b"Exif\x00\x00" + tiff
    app1 = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    return b"\xff\xd8" + app1 + b"\xff\xd9"


class TestExif(unittest.TestCase):
    def test_extract_and_gps(self):
        data = _build_geotagged_jpeg()
        exif = extract_exif(data)
        self.assertIn("GPS", exif)
        gps = gps_from_exif(exif)
        self.assertIsNotNone(gps)
        self.assertAlmostEqual(gps["latitude"], 48.8582, places=2)
        self.assertAlmostEqual(gps["longitude"], 2.2945, places=2)
        self.assertEqual(gps["altitude_m"], 33.0)

    def test_no_exif(self):
        self.assertEqual(extract_exif(b"\xff\xd8\xff\xd9"), {})
        self.assertEqual(extract_exif(b"not a jpeg"), {})

    def test_analyze_image(self):
        data = _build_geotagged_jpeg()
        out = analyze_image(data, image_url="https://example.com/x.jpg")
        self.assertTrue(out["has_exif"])
        self.assertIn("maps_url", out)
        self.assertIn("yandex", out["reverse_search"])

    def test_demo_file_present(self):
        self.assertTrue(os.path.exists(DEMO))
        with open(DEMO, "rb") as fh:
            gps = gps_from_exif(extract_exif(fh.read()))
        self.assertIsNotNone(gps)


class TestSun(unittest.TestCase):
    def test_summer_solstice_paris(self):
        when = dt.datetime(2026, 6, 21, 12, 0, tzinfo=dt.timezone.utc)
        pos = sun_position(48.8582, 2.2945, when)
        self.assertGreater(pos["elevation_deg"], 55.0)
        self.assertGreater(pos["declination_deg"], 23.0)

    def test_azimuth_range(self):
        pos = sun_position(0.0, 0.0, dt.datetime(2026, 3, 20, 6, 0,
                                                 tzinfo=dt.timezone.utc))
        self.assertTrue(0.0 <= pos["azimuth_deg"] < 360.0)


class TestShadow(unittest.TestCase):
    def test_estimate(self):
        when = dt.datetime(2026, 6, 21, 12, 0, tzinfo=dt.timezone.utc)
        r = estimate_latitude_from_shadow(1.0, 1.0, when)
        self.assertAlmostEqual(r["sun_elevation_deg"], 45.0, places=1)
        self.assertIn("latitude_candidate_north", r)

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            estimate_latitude_from_shadow(
                1.0, 0.0, dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc))


class TestReverse(unittest.TestCase):
    def test_urls(self):
        u = reverse_search_urls("https://e.com/a.jpg", ["paris", "tower"])
        self.assertIn("tineye", u)
        self.assertIn("google_text", u)
        self.assertTrue(u["tineye"].startswith("https://"))


class TestCli(unittest.TestCase):
    def test_version_const(self):
        self.assertEqual(TOOL_NAME, "geolens")
        self.assertTrue(TOOL_VERSION)

    def test_exif_cmd_exit0(self):
        self.assertEqual(main(["--format", "json", "exif", DEMO]), 0)

    def test_sun_cmd(self):
        rc = main(["sun", "--lat", "48.86", "--lon", "2.29",
                   "--when", "2026-06-21T12:00:00Z"])
        self.assertEqual(rc, 0)

    def test_shadow_cmd(self):
        rc = main(["--format", "json", "shadow", "--height", "1",
                   "--shadow", "1.3", "--when", "2026-06-21T12:00:00Z"])
        self.assertEqual(rc, 0)

    def test_reverse_needs_args(self):
        self.assertEqual(main(["reverse"]), 2)


if __name__ == "__main__":
    unittest.main()
