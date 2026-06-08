# Scenario: Bulk-sanitize check on a marketing image folder

Three images; two still have GPS.

## Expected findings

- GL-EXIF-GPS × 2

## Why this matters

Marketing teams routinely miss EXIF-strip in batch. Run this in CI on the marketing repo.
