"""CLI: `python -m ingest <csv-path>`. Run it inside the backend container
(`./.scripts/ingest.sh <csv-path>`), where `db` and `redis` are reachable."""

import asyncio
import sys
from pathlib import Path

from core.config import get_settings
from core.logging import configure_logging
from db.session import get_engine, get_session_factory
from dependencies.providers import get_cache
from ingest.pipeline import IngestPipeline
from ingest.report import IngestReport
from repositories.catalog_repository import CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import ListingRepository

USAGE = "usage: python -m ingest <csv-path>"


async def run_ingest(csv_path: Path) -> IngestReport:
    cache = get_cache()
    try:
        async with get_session_factory()() as session:
            pipeline = IngestPipeline(
                CityRepository(session),
                CatalogRepository(session),
                ListingRepository(session),
                cache,
            )
            report = await pipeline.run(csv_path)
            await session.commit()  # one transaction: a failed ingest changes nothing
    finally:
        await cache.close()
        await get_engine().dispose()
    return report


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(USAGE)
    csv_path = Path(sys.argv[1])
    if not csv_path.is_file():
        raise SystemExit(f"not a file: {csv_path}")
    configure_logging(get_settings().log_level)
    print(asyncio.run(run_ingest(csv_path)).render())


if __name__ == "__main__":
    main()
