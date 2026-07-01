"""Scenario 14 - build a reverse-search dossier from an image + keywords.

GEOLENS composes (never fires) the query URLs an analyst opens to chase an image
across the web: Google Lens, Yandex, Bing, TinEye for the picture; Google text
and OpenStreetMap for extracted keywords. This scenario builds a full dossier
and shows every URL is https and properly percent-encoded. Offline.
"""
from urllib.parse import urlparse

from _common import rule
from geolens.core import reverse_search_urls


def main() -> None:
    rule("REVERSE-SEARCH DOSSIER  -  the URLs an analyst opens next")

    image_url = "https://example.com/leaked photo (1).jpg"  # note spaces/parens
    keywords = ["red brick facade", "tram overhead lines", "Cyrillic sign"]

    print(f"\nSubject image: {image_url}")
    print(f"Extracted keywords: {keywords}\n")

    urls = reverse_search_urls(image_url, keywords)
    print(f"  {'engine':<16} {'https':<6} {'encoded':<8} url")
    print("  " + "-" * 70)
    for engine, url in urls.items():
        p = urlparse(url)
        https = p.scheme == "https"
        encoded = " " not in url  # spaces must be percent-encoded
        shown = url if len(url) <= 46 else url[:43] + "..."
        print(f"  {engine:<16} {str(https):<6} {str(encoded):<8} {shown}")

    print(f"\n{len(urls)} query URLs composed. No request was made — these are leads to open.")

    print("\nImage-only vs keyword-only dossiers:")
    print(f"   image only   -> {sorted(reverse_search_urls(image_url))}")
    print(f"   keyword only -> {sorted(reverse_search_urls(keywords=keywords))}")
    print(f"   nothing      -> {reverse_search_urls()} (empty is valid)")


if __name__ == "__main__":
    main()
