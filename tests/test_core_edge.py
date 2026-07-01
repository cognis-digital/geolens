"""analyze_image, reverse_search_urls, and package-identity edge cases."""
import os
import sys
import unittest
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import geolens  # noqa: E402
from geolens.core import analyze_image, reverse_search_urls  # noqa: E402

DEMOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demos")
sys.path.insert(0, DEMOS)
import _common  # noqa: E402


class TestAnalyzeImage(unittest.TestCase):
    def test_geotagged_has_maps_url(self):
        out = analyze_image(_common.make_exif_jpeg(48.85, 2.29))
        self.assertTrue(out["has_exif"])
        self.assertIn("maps_url", out)

    def test_scrubbed_no_maps_url(self):
        out = analyze_image(b"\xff\xd8\xff\xd9")
        self.assertFalse(out["has_exif"])
        self.assertNotIn("maps_url", out)
        self.assertIsNone(out["gps"])

    def test_empty_bytes_safe(self):
        out = analyze_image(b"")
        self.assertFalse(out["has_exif"])

    def test_camera_surfaced_lowercase(self):
        out = analyze_image(_common.make_exif_jpeg(1, 2, make="Nikon", model="Z9 II"))
        self.assertEqual(out.get("make"), "Nikon")
        self.assertEqual(out.get("model"), "Z9 II")

    def test_reverse_search_uses_camera_when_no_url(self):
        out = analyze_image(_common.make_exif_jpeg(1, 2, make="Nikon", model="Z9 II"))
        self.assertIn("google_text", out["reverse_search"])

    def test_non_bytes_input_raises(self):
        with self.assertRaises(TypeError):
            analyze_image("path/to/file.jpg")

    def test_maps_url_is_well_formed(self):
        out = analyze_image(_common.make_exif_jpeg(48.85, 2.29))
        parsed = urlparse(out["maps_url"])
        self.assertEqual(parsed.scheme, "https")
        self.assertIn("openstreetmap.org", parsed.netloc)


class TestReverseSearchUrls(unittest.TestCase):
    def test_empty_when_no_args(self):
        self.assertEqual(reverse_search_urls(), {})

    def test_url_yields_four_image_engines(self):
        u = reverse_search_urls("https://e.com/a.jpg")
        for eng in ("google_lens", "yandex", "bing", "tineye"):
            self.assertIn(eng, u)

    def test_keywords_yield_text_engines(self):
        u = reverse_search_urls(keywords=["mont", "blanc"])
        self.assertIn("google_text", u)
        self.assertIn("openstreetmap", u)

    def test_url_is_percent_encoded(self):
        u = reverse_search_urls("https://e.com/a b.jpg")
        self.assertNotIn(" ", u["tineye"])

    def test_keywords_joined_and_encoded(self):
        u = reverse_search_urls(keywords=["eiffel tower", "paris"])
        self.assertNotIn(" ", u["google_text"])

    def test_all_urls_https(self):
        u = reverse_search_urls("https://e.com/a.jpg", ["x"])
        for v in u.values():
            self.assertTrue(v.startswith("https://"))


class TestPackageIdentity(unittest.TestCase):
    def test_tool_name(self):
        self.assertEqual(geolens.TOOL_NAME, "geolens")

    def test_version_present(self):
        self.assertTrue(geolens.__version__)

    def test_version_matches_version_file(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "VERSION"), encoding="utf-8") as fh:
            file_version = fh.read().strip()
        self.assertEqual(geolens.__version__, file_version)

    def test_public_api_reexported(self):
        for name in ("extract_exif", "gps_from_exif", "sun_position",
                     "estimate_latitude_from_shadow", "analyze_image",
                     "to_geojson", "to_stix", "export"):
            self.assertTrue(hasattr(geolens, name), f"missing {name}")


if __name__ == "__main__":
    unittest.main()
