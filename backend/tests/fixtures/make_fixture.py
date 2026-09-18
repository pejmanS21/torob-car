"""Builds tests/fixtures/listings_sample.csv from the real (untracked) Divar CSV.

    uv run python -m tests.fixtures.make_fixture <path-to-the-real-csv>

Deterministic: rows are picked in token order. Free text that can carry phone numbers
(description, SEO text) is blanked and long digit runs in titles are masked, so the
coordinates are rounded to ~100 m, so the committed fixture holds no personal data."""

import csv
import re
import sys
from collections import Counter
from pathlib import Path

from core.text import to_ascii_digits

OUTPUT = Path(__file__).with_name("listings_sample.csv")
BLANKED_COLUMNS = ("description", "seo_description", "seo_title", "subtitle")
KEEP_FIRST_URL_COLUMNS = ("image_urls", "thumbnail_urls")
COORDINATE_COLUMNS = ("latitude", "longitude")
COORDINATE_DECIMALS = 3  # ~100 m: enough for city-distance tests, not an address
TRIM_COLUMN = "برند و مدل"
LONG_DIGIT_RUN = re.compile(r"\d{7,}")
LIGHT_TRIMS_KEPT = 14
QUOTAS = {"light": 420, "motorcycles": 120, "heavy": 60, "rental": 8, "classic": 9}


def _segment(row: dict[str, str]) -> str:
    return row["webengage_cat_3"] or row["webengage_cat_2"]


def _scrub(row: dict[str, str]) -> dict[str, str]:
    for column in BLANKED_COLUMNS:
        row[column] = ""
    for column in KEEP_FIRST_URL_COLUMNS:
        row[column] = row[column].split(" | ")[0]
    for column in COORDINATE_COLUMNS:
        if row[column]:
            row[column] = str(round(float(row[column]), COORDINATE_DECIMALS))
    row["title"] = (
        LONG_DIGIT_RUN.sub("", to_ascii_digits(row["title"])).strip() or "آگهی"
    )
    return row


def build(source: Path) -> Counter[str]:
    csv.field_size_limit(sys.maxsize)
    with source.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows = sorted(reader, key=lambda row: row["token"])
    trims = Counter(row[TRIM_COLUMN] for row in rows if _segment(row) == "light")
    popular = {trim for trim, _ in trims.most_common(LIGHT_TRIMS_KEPT)}
    taken: Counter[str] = Counter()
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            segment = _segment(row)
            if segment == "light" and row[TRIM_COLUMN] not in popular:
                continue
            if taken[segment] < QUOTAS.get(segment, 0):
                taken[segment] += 1
                writer.writerow(_scrub(row))
    return taken


if __name__ == "__main__":
    print(dict(build(Path(sys.argv[1]))), "→", OUTPUT)
