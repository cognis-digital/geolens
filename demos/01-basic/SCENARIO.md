# GEOLENS — Basic geolocation walkthrough

You receive an image and need to place it on the map. GEOLENS gives you three
independent geolocation signals, all offline (no API keys, no uploads).

The demo input `sample_geotagged.jpg` is a real JPEG carrying an EXIF GPS block
(big-endian TIFF, GPS IFD) pointing at the Eiffel Tower, Paris.

## 1. Pull EXIF + GPS and get reverse-search links

```sh
python -m geolens --format json exif demos/01-basic/sample_geotagged.jpg \
    --url https://example.com/photo.jpg
```

Expect `gps.latitude ~= 48.858`, `gps.longitude ~= 2.294`, a `maps_url`
pointing at OpenStreetMap, and `reverse_search` links for Google Lens, Yandex,
Bing, and TinEye. Exit code is `0` when EXIF is present, `2` when it is not —
so you can branch in a pipeline.

## 2. No EXIF? Geolocate from shadows (the "shadow stick")

A vertical 1.0 m pole casts a 1.3 m shadow at the photo's solar noon on a known
date. Recover the observer latitude:

```sh
python -m geolens --format json shadow --height 1.0 --shadow 1.3 \
    --when 2026-06-21T12:00:00Z
```

`latitude_candidate_north` / `_south` bracket the answer; the shadow's compass
direction tells you which hemisphere.

## 3. Verify a claimed location against the sun

Given a candidate lat/lon and the photo timestamp, compute where the sun
*should* be, then compare to the shadow azimuth in the image:

```sh
python -m geolens --format json sun --lat 48.8582 --lon 2.2945 \
    --when 2026-06-21T10:00:00Z
```

If the computed `azimuth_deg` / `elevation_deg` contradict the shadows you see,
the claimed location (or time) is wrong — a standard chronolocation check.
