"""Scenario 21 - KML for Google Earth (and QGIS / Google Maps).

Alongside GeoJSON and STIX, GEOLENS now emits KML: the format Google Earth and
Maps open natively. This scenario analyzes a real EXIF image, renders a KML
Placemark (with altitude), confirms it parses as well-formed XML, and shows the
graceful empty document when no GPS is present. Offline; standard library only.
"""
import datetime as _dt
from xml.dom import minidom

from _common import rule, make_exif_jpeg
from geolens import intel
from geolens.core import analyze_image


def main() -> None:
    rule("KML EXPORT  -  drop a fix straight into Google Earth")

    img = make_exif_jpeg(45.4642, 9.1900, make="Leica", model="M11",
                         when=_dt.datetime(2026, 6, 21, 11, tzinfo=_dt.timezone.utc),
                         altitude_m=120.0)
    r = analyze_image(img, image_url="https://example.com/milano.jpg")
    kml = intel.export(r, "kml")

    doc = minidom.parseString(kml)  # proves it is well-formed XML
    coord = doc.getElementsByTagName("coordinates")[0].firstChild.data
    print(f"\n1) analyzed fix -> {r['gps']}")
    print(f"2) KML Placemark coordinates -> {coord}   [lon,lat,alt]")
    print(f"3) altitude mode present -> {'altitudeMode' in kml}")
    print("\n   First lines of the KML:")
    for line in kml.splitlines()[:6]:
        print(f"     {line}")

    print("\n4) graceful with NO GPS (scrubbed) -> valid, empty Document:")
    empty = intel.export(analyze_image(b"\xff\xd8\xff\xd9"), "kml")
    edoc = minidom.parseString(empty)
    print(f"     Placemarks -> {len(edoc.getElementsByTagName('Placemark'))} "
          f"(document still well-formed)")

    print("\nSave the KML to a .kml file and double-click it into Google Earth.")


if __name__ == "__main__":
    main()
