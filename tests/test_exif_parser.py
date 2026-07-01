"""EXIF/TIFF binary-parser edge cases and error paths.

These exercise the real binary walker in ``geolens.core`` against malformed,
truncated, byte-swapped, and metadata-free inputs — the failure modes a triage
tool actually meets on seized or scrubbed images.
"""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geolens.core import extract_exif, gps_from_exif  # noqa: E402

DEMOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demos")
sys.path.insert(0, DEMOS)
import _common  # noqa: E402


class TestNotAJpeg(unittest.TestCase):
    def test_empty_bytes(self):
        self.assertEqual(extract_exif(b""), {})

    def test_one_byte(self):
        self.assertEqual(extract_exif(b"\xff"), {})

    def test_random_bytes(self):
        self.assertEqual(extract_exif(b"this is not an image at all"), {})

    def test_png_signature(self):
        self.assertEqual(extract_exif(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20), {})

    def test_gif_signature(self):
        self.assertEqual(extract_exif(b"GIF89a" + b"\x00" * 20), {})

    def test_jpeg_soi_eoi_only(self):
        self.assertEqual(extract_exif(b"\xff\xd8\xff\xd9"), {})


class TestBytesLikeInputs(unittest.TestCase):
    def test_bytearray_accepted(self):
        img = bytearray(_common.make_exif_jpeg(48.8, 2.3))
        self.assertIn("GPS", extract_exif(img))

    def test_memoryview_accepted(self):
        img = memoryview(_common.make_exif_jpeg(48.8, 2.3))
        self.assertIn("GPS", extract_exif(img))

    def test_string_rejected(self):
        with self.assertRaises(TypeError):
            extract_exif("not bytes")

    def test_none_rejected(self):
        with self.assertRaises(TypeError):
            extract_exif(None)

    def test_int_rejected(self):
        with self.assertRaises(TypeError):
            extract_exif(1234)


class TestTruncatedAndMalformed(unittest.TestCase):
    def test_app1_header_but_truncated_payload(self):
        # declares a long APP1 segment but the bytes stop early
        data = b"\xff\xd8\xff\xe1\x00\x40Exif\x00\x00MM\x00\x2a\x00\x00\x00\x08"
        self.assertEqual(extract_exif(data), {})

    def test_bad_byte_order_marker(self):
        # valid APP1 Exif header but neither II nor MM
        payload = b"Exif\x00\x00" + b"XX" + struct.pack(">H", 42) + struct.pack(">I", 8)
        app1 = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
        self.assertEqual(extract_exif(b"\xff\xd8" + app1 + b"\xff\xd9"), {})

    def test_subifd_pointer_out_of_bounds(self):
        seg = b"MM" + struct.pack(">H", 42) + struct.pack(">I", 8)
        ifd0 = (struct.pack(">H", 1)
                + struct.pack(">HHI", 0x8769, 4, 1) + struct.pack(">I", 99999)
                + struct.pack(">I", 0))
        payload = b"Exif\x00\x00" + seg + ifd0
        app1 = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
        out = extract_exif(b"\xff\xd8" + app1 + b"\xff\xd9")
        # pointer is surfaced but the out-of-bounds sub-IFD yields no tags
        self.assertEqual(out, {"ExifIFDPointer": 99999})

    def test_ifd_count_larger_than_buffer(self):
        # claim 500 entries but provide none — parser must not crash
        seg = b"MM" + struct.pack(">H", 42) + struct.pack(">I", 8)
        ifd0 = struct.pack(">H", 500)  # no entries follow
        payload = b"Exif\x00\x00" + seg + ifd0
        app1 = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
        out = extract_exif(b"\xff\xd8" + app1 + b"\xff\xd9")
        self.assertEqual(out, {})

    def test_marker_scan_skips_restart_markers(self):
        # a JPEG whose only APP1 has no Exif header -> {}
        app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9
        self.assertEqual(extract_exif(b"\xff\xd8" + app0 + b"\xff\xd9"), {})


class TestByteOrder(unittest.TestCase):
    def test_bundled_sample_big_endian(self):
        with open(_common.SAMPLE_GEOTAGGED, "rb") as fh:
            exif = extract_exif(fh.read())
        self.assertIn("GPS", exif)

    def test_synth_roundtrips_gps(self):
        exif = extract_exif(_common.make_exif_jpeg(-12.34, 56.78))
        gps = gps_from_exif(exif)
        self.assertAlmostEqual(gps["latitude"], -12.34, places=3)
        self.assertAlmostEqual(gps["longitude"], 56.78, places=3)


class TestGpsFromExif(unittest.TestCase):
    def test_no_gps_key(self):
        self.assertIsNone(gps_from_exif({"Make": "Canon"}))

    def test_gps_present_but_no_lat(self):
        self.assertIsNone(gps_from_exif({"GPS": {"GPSLongitude": [(1, 1)] * 3}}))

    def test_gps_present_but_no_lon(self):
        self.assertIsNone(gps_from_exif({"GPS": {"GPSLatitude": [(1, 1)] * 3}}))

    def test_empty_gps_dict(self):
        self.assertIsNone(gps_from_exif({"GPS": {}}))

    def test_zero_denominator_does_not_divide_by_zero(self):
        gps = gps_from_exif({"GPS": {
            "GPSLatitude": [(48, 1), (0, 0), (0, 1)],   # min has 0/0 denom
            "GPSLongitude": [(2, 1), (0, 1), (0, 1)],
            "GPSLatitudeRef": "N", "GPSLongitudeRef": "E"}})
        self.assertAlmostEqual(gps["latitude"], 48.0, places=3)

    def test_south_west_refs_negate(self):
        gps = gps_from_exif({"GPS": {
            "GPSLatitude": [(33, 1), (0, 1), (0, 1)],
            "GPSLongitude": [(70, 1), (0, 1), (0, 1)],
            "GPSLatitudeRef": "S", "GPSLongitudeRef": "W"}})
        self.assertLess(gps["latitude"], 0)
        self.assertLess(gps["longitude"], 0)

    def test_default_refs_are_north_east(self):
        gps = gps_from_exif({"GPS": {
            "GPSLatitude": [(10, 1), (0, 1), (0, 1)],
            "GPSLongitude": [(20, 1), (0, 1), (0, 1)]}})
        self.assertGreater(gps["latitude"], 0)
        self.assertGreater(gps["longitude"], 0)

    def test_altitude_positive(self):
        gps = gps_from_exif({"GPS": {
            "GPSLatitude": [(1, 1), (0, 1), (0, 1)],
            "GPSLongitude": [(2, 1), (0, 1), (0, 1)],
            "GPSAltitude": (150, 1)}})
        self.assertEqual(gps["altitude_m"], 150.0)

    def test_altitude_below_sea_level_int_ref(self):
        gps = gps_from_exif({"GPS": {
            "GPSLatitude": [(1, 1), (0, 1), (0, 1)],
            "GPSLongitude": [(2, 1), (0, 1), (0, 1)],
            "GPSAltitude": (30, 1), "GPSAltitudeRef": 1}})
        self.assertEqual(gps["altitude_m"], -30.0)

    def test_altitude_below_sea_level_bytes_ref(self):
        gps = gps_from_exif({"GPS": {
            "GPSLatitude": [(1, 1), (0, 1), (0, 1)],
            "GPSLongitude": [(2, 1), (0, 1), (0, 1)],
            "GPSAltitude": (30, 1), "GPSAltitudeRef": b"\x01"}})
        self.assertEqual(gps["altitude_m"], -30.0)

    def test_altitude_zero_denominator_ignored(self):
        gps = gps_from_exif({"GPS": {
            "GPSLatitude": [(1, 1), (0, 1), (0, 1)],
            "GPSLongitude": [(2, 1), (0, 1), (0, 1)],
            "GPSAltitude": (30, 0)}})
        self.assertNotIn("altitude_m", gps)


if __name__ == "__main__":
    unittest.main()
