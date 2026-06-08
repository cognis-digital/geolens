# Scenario: Executive's vacation photo with GPS metadata

A senior employee posted a vacation photo to LinkedIn. GEOLENS shows it still has GPS coordinates in EXIF.

## Expected findings

- GL-EXIF-GPS

## Why this matters

Trivial OPSEC fail. Strip EXIF before any public posting.
