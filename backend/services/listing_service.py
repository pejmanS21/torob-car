import uuid
from collections.abc import Sequence

from errors import InvalidSearchError, ListingNotFoundError
from models.listing import Listing
from repositories.listing_repository import ListingRepository
from schemas.listing import ListingCard, ListingDetail
from schemas.search import SearchIntent, VehicleMention
from services.listing_views import to_card, to_detail
from services.search_service import SearchService

MAX_BATCH_IDS = 4
SIMILAR_PRICE_SPREAD = 0.15
FIRST_PAGE = 1


def _similar_intent(listing: Listing) -> SearchIntent:
    """ "Similar" is not a second algorithm: it is a search for this listing's own
    trim, year, price band and city (spec §7.6)."""
    price = None if listing.price_suspect else listing.price
    catalog = listing.catalog
    return SearchIntent(
        category=listing.category,
        vehicles=[VehicleMention(trim=catalog.trim)] if catalog else [],
        year_min=listing.year,
        year_max=listing.year,
        price_min=round(price * (1 - SIMILAR_PRICE_SPREAD)) if price else None,
        price_max=round(price * (1 + SIMILAR_PRICE_SPREAD)) if price else None,
        cities=[listing.city.name],
        text=None if catalog else listing.title,
    )


class ListingService:
    def __init__(self, listings: ListingRepository, search: SearchService) -> None:
        self._listings = listings
        self._search = search

    async def _require(self, listing_id: uuid.UUID) -> Listing:
        listing = await self._listings.get_by_id(listing_id)
        if listing is None:
            raise ListingNotFoundError(listing_id)
        return listing

    async def get_detail(self, listing_id: uuid.UUID) -> ListingDetail:
        return to_detail(await self._require(listing_id))

    async def get_many(self, listing_ids: Sequence[uuid.UUID]) -> list[ListingCard]:
        if len(listing_ids) > MAX_BATCH_IDS:
            raise InvalidSearchError(
                f"At most {MAX_BATCH_IDS} listings can be fetched at once",
                {"requested": len(listing_ids)},
            )
        listings = await self._listings.get_by_ids(list(listing_ids))
        return [to_card(listing) for listing in listings]

    async def get_similar(self, listing_id: uuid.UUID, limit: int) -> list[ListingCard]:
        listing = await self._require(listing_id)
        ranked, _ = await self._search.rank(_similar_intent(listing), listing.id)
        return await self._search.page_of(ranked.results, FIRST_PAGE, limit)
