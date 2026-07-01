"""Scenario 7 - hostile inputs: corrupt, truncated, and non-image bytes.

A triage tool has to survive whatever lands in the folder. This scenario feeds
GEOLENS a gallery of broken inputs — empty bytes, a PNG, a truncated APP1
segment, garbage — and shows every one degrades to a clean ``{}`` / no-GPS
result instead of a crash. Offline, no exceptions escape.
"""
import struct

from _common import rule
from geolens.core import analyze_image, extract_exif


def main() -> None:
    rule("HOSTILE INPUTS  -  corrupt / truncated / non-image bytes never crash")

    cases = [
        ("empty bytes", b""),
        ("single byte", b"\xff"),
        ("plain text", b"this is a text file, not a photo"),
        ("PNG signature", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32),
        ("GIF signature", b"GIF89a" + b"\x00" * 32),
        ("JPEG SOI/EOI only", b"\xff\xd8\xff\xd9"),
        ("truncated APP1", b"\xff\xd8\xff\xe1\x00\x40Exif\x00\x00MM\x00\x2a\x00\x00\x00\x08"),
        ("bad byte-order", b"\xff\xd8\xff\xe1" + struct.pack(">H", 12)
            + b"Exif\x00\x00" + b"XX\x00\x2a"),
    ]

    print("\n{:<22} {:<12} {}".format("input", "has_exif", "gps"))
    print("-" * 56)
    survived = 0
    for label, data in cases:
        try:
            r = analyze_image(data)
            survived += 1
            print(f"{label:<22} {str(r['has_exif']):<12} {r['gps']}")
        except Exception as exc:  # pragma: no cover - would be a bug
            print(f"{label:<22} CRASHED: {type(exc).__name__}: {exc}")

    print(f"\n{survived}/{len(cases)} malformed inputs handled without an exception.")

    print("\nType safety: a non-bytes argument is rejected loudly (not silently wrong):")
    try:
        extract_exif("path/to/file.jpg")  # a common mistake: passing a path
    except TypeError as exc:
        print(f"   extract_exif('...path...') -> TypeError: {exc}")

    print("\nGarbage in, empty out — the parser is a safe first pass on any dump.")


if __name__ == "__main__":
    main()
