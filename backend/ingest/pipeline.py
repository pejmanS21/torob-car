"""CSV → normalised rows → upsert → estimates → cache invalidation (spec §6.4).
Idempotent: re-running with the same file changes nothing."""

import csv
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from core.cache import Cache
from core.text import jalali_year
from errors import IngestError
from ingest.report import IngestReport
from ingest.row_mapper import MappedRow, NormalizedListing, RowRejectedError, map_row
from ranking.estimator import PriceEstimator
from repositories.catalog_repository import CatalogEntry, CatalogKey, CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import ListingRepository

CSV_ENCODING = "utf-8"
_CATALOG_FIELDS = {"trim", "brand", "model", "city"}


def _read_rows(csv_path: Path) -> Iterator[dict[str, str]]:
    csv.field_size_limit(sys.maxsize)  # descriptions exceed the 128 KB default
    with csv_path.open(encoding=CSV_ENCODING, newline="") as handle:
        yield from csv.DictReader(handle)


def _catalog_key(listing: NormalizedListing) -> CatalogKey | None:
    return (listing.category, listing.trim) if listing.trim else None


class IngestPipeline:
    def __init__(
        self,
        cities: CityRepository,
        catalog: CatalogRepository,
        listings: ListingRepository,
        cache: Cache,
    ) -> None:
        self._cities = cities
        self._catalog = catalog
        self._listings = listings
        self._cache = cache

    async def run(self, csv_path: Path) -> IngestReport:
        report = IngestReport()
        mapped = self._map_rows(csv_path, report)
        if report.too_many_rejects:
            raise IngestError(
                "Too many rejected rows", {"rejected": dict(report.rejected)}
            )
        await self._upsert(mapped, report)
        await self._cities.refresh_statistics()
        await self._catalog.refresh_counts()
        await self._estimate(report)
        report.data_version = await self._cache.bump_data_version()
        return report

    @staticmethod
    def _map_rows(csv_path: Path, report: IngestReport) -> list[MappedRow]:
        mapped: list[MappedRow] = []
        for row in _read_rows(csv_path):
            report.rows_read += 1
            try:
                mapped_row = map_row(row)
            except RowRejectedError as rejected:
                report.rejected[rejected.reason] += 1
                continue
            report.nulled.update(mapped_row.nulled)
            mapped.append(mapped_row)
        return mapped

    async def _upsert(self, mapped: list[MappedRow], report: IngestReport) -> None:
        listings = [row.listing for row in mapped]
        city_ids = await self._cities.upsert_names(
            {listing.city for listing in listings}
        )
        entries = {
            CatalogEntry(listing.category, listing.brand, listing.model, listing.trim)
            for listing in listings
            if listing.trim and listing.brand and listing.model
        }
        catalog_ids = await self._catalog.upsert_entries(entries)
        rows = [self._to_row(listing, city_ids, catalog_ids) for listing in listings]
        await self._listings.upsert_many(rows)
        report.rows_upserted = len(rows)

    @staticmethod
    def _to_row(
        listing: NormalizedListing,
        city_ids: dict[str, Any],
        catalog_ids: dict[CatalogKey, Any],
    ) -> dict[str, Any]:
        row = listing.model_dump(exclude=_CATALOG_FIELDS)
        row["city_id"] = city_ids[listing.city]
        key = _catalog_key(listing)
        row["catalog_id"] = catalog_ids.get(key) if key else None
        return row

    async def _estimate(self, report: IngestReport) -> None:
        newest = await self._listings.newest_fetched_at()
        if newest is None:
            return
        inputs = await self._listings.load_estimator_inputs()
        estimates = PriceEstimator(inputs, jalali_year(newest.date())).estimate_all()
        await self._listings.apply_estimates(estimates)
        report.estimate_basis.update(estimate.est_basis.value for estimate in estimates)
        report.price_suspect = sum(estimate.price_suspect for estimate in estimates)
