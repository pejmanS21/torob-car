"""POST /estimates: the ingest estimator's formulas for one hypothetical vehicle."""

from datetime import UTC, datetime

from core.text import jalali_year, normalize_persian
from errors import InvalidSearchError, NoComparablesError
from ranking.estimator import EstimateQuery, PriceEstimator, SingleEstimate
from repositories.catalog_repository import CatalogEntry, CatalogRepository
from repositories.listing_repository import ListingRepository
from schemas.estimate import (
    SIMILAR_YEAR_SPAN,
    EstimateBreakdown,
    EstimateRequest,
    EstimateResponse,
)
from schemas.listing import ListingCard
from schemas.search import SearchIntent, VehicleMention
from services.listing_views import verdict_of
from services.search_service import SearchService

SIMILAR_LIMIT = 4
FIRST_PAGE = 1
PERCENT = 100


class EstimateService:
    def __init__(
        self,
        catalog: CatalogRepository,
        listings: ListingRepository,
        search: SearchService,
    ) -> None:
        self._catalog = catalog
        self._listings = listings
        self._search = search

    async def estimate(self, request: EstimateRequest) -> EstimateResponse:
        entry = await self._catalog.find_trim(
            request.category, normalize_persian(request.trim)
        )
        if entry is None:
            raise InvalidSearchError("Unknown trim", {"trim": request.trim})
        estimate = await self._run_estimator(request, entry)
        if estimate.est_price is None or estimate.base is None:
            raise NoComparablesError([basis.value for basis in estimate.tried])
        asking_diff = _asking_diff(request, estimate.est_price)
        return EstimateResponse(
            est_price=estimate.est_price,
            low=estimate.low or estimate.est_price,
            high=estimate.high or estimate.est_price,
            est_basis=estimate.est_basis,
            est_sample_size=estimate.est_sample_size,
            breakdown=_breakdown(estimate, estimate.base),
            asking_verdict=verdict_of(asking_diff) if asking_diff is not None else None,
            asking_diff_pct=asking_diff,
            similar=await self._similar(request, entry),
        )

    async def _run_estimator(
        self, request: EstimateRequest, entry: CatalogEntry
    ) -> SingleEstimate:
        # ponytail: loads the category's rows (≈5k) per request; cache the built
        # estimator per data version if /estimates ever shows up in latency logs.
        newest = await self._listings.newest_fetched_at() or datetime.now(UTC)
        rows = await self._listings.load_estimator_inputs(request.category)
        query = EstimateQuery(
            category=request.category,
            trim=entry.trim,
            model=entry.model,
            year=request.year,
            km=request.km,
            insurance_months=request.insurance_months,
        )
        return PriceEstimator(rows, jalali_year(newest.date())).estimate_for(query)

    async def _similar(
        self, request: EstimateRequest, entry: CatalogEntry
    ) -> list[ListingCard]:
        intent = SearchIntent(
            category=request.category,
            vehicles=[VehicleMention(trim=entry.trim)],
            year_min=request.year - SIMILAR_YEAR_SPAN,
            year_max=request.year + SIMILAR_YEAR_SPAN,
        )
        ranked, _ = await self._search.rank(intent)
        return await self._search.page_of(ranked.results, FIRST_PAGE, SIMILAR_LIMIT)


def _breakdown(estimate: SingleEstimate, base: int) -> EstimateBreakdown:
    return EstimateBreakdown(
        base=base,
        km_adjustment=round(base * (estimate.km_factor - 1)),
        insurance_adjustment=round(base * (estimate.insurance_factor - 1)),
    )


def _asking_diff(request: EstimateRequest, est_price: int) -> float | None:
    if request.asking_price is None:
        return None
    return round((request.asking_price - est_price) / est_price * PERCENT, 1)
