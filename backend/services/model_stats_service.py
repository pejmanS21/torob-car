from core.text import normalize_persian
from errors import ModelNotFoundError
from ranking.model_stats import summarize_model
from repositories.catalog_repository import CatalogRepository
from repositories.listing_repository import ListingRepository
from schemas.model_stats import HistogramBucketRead, ModelStats, TrimStatRead
from services.listing_views import to_card

TOP_DEALS = 6


class ModelStatsService:
    def __init__(self, catalog: CatalogRepository, listings: ListingRepository) -> None:
        self._catalog = catalog
        self._listings = listings

    async def get_stats(self, model: str) -> ModelStats:
        name = normalize_persian(model)
        info = await self._catalog.find_model(name)
        if info is None:
            raise ModelNotFoundError(model)
        rows = await self._listings.load_model_rows(name)
        summary = summarize_model(rows, TOP_DEALS)
        top = await self._listings.get_by_ids(list(summary.top_deal_ids))
        return ModelStats(
            model=info.model,
            brand=info.brand,
            category=info.category,
            count=summary.count,
            year_min=summary.year_min,
            year_max=summary.year_max,
            price_median=summary.price_median,
            price_min=summary.price_min,
            price_max=summary.price_max,
            histogram=[
                HistogramBucketRead(low=b.low, high=b.high, count=b.count)
                for b in summary.histogram
            ],
            trims=[
                TrimStatRead(trim=t.trim, count=t.count, price_median=t.price_median)
                for t in summary.trims
            ],
            top_deals=[to_card(listing) for listing in top],
        )
