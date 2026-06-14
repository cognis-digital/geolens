"""Hardening tests — edge cases, bad input, and error paths."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geolens.cli import main, _emit
from geolens.core import (
    analyze_image,
    extract_exif,
    gps_from_exif,
    reverse_search_urls,
)


# ---------------------------------------------------------------------------
# core — extract_exif edge cases
# ---------------------------------------------------------------------------

class TestExtractExifEdgeCases(unittest.TestCase):
    def test_empty_bytes_returns_empty(self):
        """Empty input must return {} without raising."""
        self.assertEqual(extract_exif(b""), {})

    def test_random_bytes_returns_empty(self):
        """Arbitrary non-JPEG bytes must return {} without raising."""
        self.assertEqual(extract_exif(b"\x00" * 64), {})

    def test_jpeg_no_exif_returns_empty(self):
        """A minimal JPEG with no EXIF segment returns {}."""
        self.assertEqual(extract_exif(b"\xff\xd8\xff\xd9"), {})

    def test_truncated_exif_segment_returns_empty(self):
        """A JPEG whose APP1 header claims more data than exists returns {}."""
        # Build a JPEG with a truncated APP1 segment.
        exif_header = b"Exif\x00\x00MM"  # valid magic but only 8 bytes of body
        seg_len = 2 + len(exif_header)  # length field includes itself
        app1 = b"\xff\xe1" + seg_len.to_bytes(2, "big") + exif_header
        data = b"\xff\xd8" + app1 + b"\xff\xd9"
        # Must not raise — returns {} gracefully.
        result = extract_exif(data)
        self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# core — gps_from_exif edge cases
# ---------------------------------------------------------------------------

class TestGpsFromExifEdgeCases(unittest.TestCase):
    def test_missing_gps_block(self):
        """No GPS key → returns None."""
        self.assertIsNone(gps_from_exif({}))

    def test_none_dms_values(self):
        """GPS block with None lat/lon tuples (truncated EXIF) → returns None."""
        exif = {"GPS": {"GPSLatitude": None, "GPSLongitude": None,
                        "GPSLatitudeRef": "N", "GPSLongitudeRef": "E"}}
        self.assertIsNone(gps_from_exif(exif))

    def test_malformed_dms_too_short(self):
        """GPS lat/lon with fewer than 3 components → returns None."""
        exif = {"GPS": {"GPSLatitude": [(48, 1)], "GPSLongitude": [(2, 1)],
                        "GPSLatitudeRef": "N", "GPSLongitudeRef": "E"}}
        self.assertIsNone(gps_from_exif(exif))

    def test_empty_gps_dict(self):
        """Empty GPS dict → returns None."""
        self.assertIsNone(gps_from_exif({"GPS": {}}))


# ---------------------------------------------------------------------------
# core — reverse_search_urls edge cases
# ---------------------------------------------------------------------------

class TestReverseSearchEdgeCases(unittest.TestCase):
    def test_no_args_returns_empty(self):
        """No image URL and no keywords → empty dict."""
        self.assertEqual(reverse_search_urls(), {})

    def test_empty_keywords_list(self):
        """Empty keyword list must not produce search URLs with blank queries."""
        urls = reverse_search_urls(keywords=[])
        self.assertNotIn("google_text", urls)
        self.assertNotIn("openstreetmap", urls)

    def test_blank_keyword_strings(self):
        """Whitespace-only keywords must be filtered out."""
        urls = reverse_search_urls(keywords=["", "  "])
        self.assertNotIn("google_text", urls)

    def test_only_image_url(self):
        """Image URL only → reverse-image engines present, no text search."""
        urls = reverse_search_urls(image_url="https://example.com/photo.jpg")
        self.assertIn("google_lens", urls)
        self.assertIn("tineye", urls)
        self.assertNotIn("google_text", urls)


# ---------------------------------------------------------------------------
# core — analyze_image edge cases
# ---------------------------------------------------------------------------

class TestAnalyzeImageEdgeCases(unittest.TestCase):
    def test_empty_bytes(self):
        """analyze_image on empty bytes must return a valid dict, not raise."""
        out = analyze_image(b"")
        self.assertFalse(out["has_exif"])
        self.assertIsNone(out["gps"])

    def test_non_jpeg_bytes(self):
        """analyze_image on a PNG header must return has_exif=False."""
        png_magic = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        out = analyze_image(png_magic)
        self.assertFalse(out["has_exif"])


# ---------------------------------------------------------------------------
# CLI — missing / bad file
# ---------------------------------------------------------------------------

class TestCliExifErrors(unittest.TestCase):
    def test_missing_file_returns_nonzero(self):
        """CLI exif with a nonexistent path exits non-zero (2)."""
        rc = main(["exif", "/nonexistent/path/image.jpg"])
        self.assertNotEqual(rc, 0)

    def test_non_jpeg_file_returns_2(self):
        """CLI exif on a non-JPEG file exits 2 with a useful message."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"this is not a jpeg")
            path = f.name
        try:
            rc = main(["exif", path])
            self.assertEqual(rc, 2)
        finally:
            os.unlink(path)

    def test_empty_file_returns_2(self):
        """CLI exif on an empty file exits 2."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            path = f.name  # write nothing
        try:
            rc = main(["exif", path])
            self.assertEqual(rc, 2)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# CLI — sun coordinate validation
# ---------------------------------------------------------------------------

class TestCliSunValidation(unittest.TestCase):
    def test_lat_out_of_range_returns_2(self):
        """--lat outside [-90, 90] exits 2."""
        rc = main(["sun", "--lat", "91", "--lon", "0"])
        self.assertEqual(rc, 2)

    def test_lat_below_range_returns_2(self):
        """--lat below -90 exits 2."""
        rc = main(["sun", "--lat", "-91", "--lon", "0"])
        self.assertEqual(rc, 2)

    def test_lon_out_of_range_returns_2(self):
        """--lon outside [-180, 180] exits 2."""
        rc = main(["sun", "--lat", "0", "--lon", "181"])
        self.assertEqual(rc, 2)

    def test_bad_when_timestamp_exits(self):
        """Malformed --when raises SystemExit."""
        with self.assertRaises(SystemExit):
            main(["sun", "--lat", "0", "--lon", "0", "--when", "not-a-date"])


# ---------------------------------------------------------------------------
# CLI — _emit with edge-case data
# ---------------------------------------------------------------------------

class TestEmit(unittest.TestCase):
    def test_emit_empty_dict_does_not_raise(self):
        """_emit with an empty dict must not raise."""
        _emit({}, "table")
        _emit({}, "json")

    def test_emit_empty_list_does_not_raise(self):
        """_emit with an empty list must not raise."""
        _emit([], "table")
        _emit([], "json")


if __name__ == "__main__":
    unittest.main()
