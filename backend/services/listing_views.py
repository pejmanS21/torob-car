"""ORM Listing → API schemas. ORM objects never leave the service layer untranslated."""

from core.phone import mask_phone_numbers
from enums import Verdict
from models.listing import Listing
from ranking.types import RankedListing
from ranking.weights import CHEAP_DIFF_PCT, EXPENSIVE_DIFF_PCT
from schemas.listing import ListingCard, ListingDetail, PriceBreakdown


def verdict_of(diff_pct: float | None) -> Verdict:
    if diff_pct is None:
        return Verdict.UNKNOWN
    if diff_pct <= CHEAP_DIFF_PCT:
        return Verdict.CHEAP
    if diff_pct >= EXPENSIVE_DIFF_PCT:
        return Verdict.EXPENSIVE
    return Verdict.FAIR


def _card_fields(listing: Listing) -> dict[str, object]:
    catalog = listing.catalog
    thumbnails = listing.thumbnail_urls or listing.image_urls
    return {
        "id": listing.id,
        "token": listing.token,
        "title": listing.title,
        "source": listing.source,
        "category": listing.category,
        "brand": catalog.brand if catalog else None,
        "model": catalog.model if catalog else None,
        "trim": catalog.trim if catalog else None,
        "year": listing.year,
        "km": listing.km,
        "price": listing.price,
        "city": listing.city.name,
        "district": listing.district,
        # Map pins: a listing without coordinates sits on its city's centroid.
        "lat": listing.lat if listing.lat is not None else listing.city.lat,
        "lng": listing.lng if listing.lng is not None else listing.city.lng,
        "gearbox": listing.gearbox,
        "fuel": listing.fuel,
        "body_condition": listing.body_condition,
        "insurance_months": listing.insurance_months,
        "thumbnail_url": thumbnails[0] if thumbnails else None,
        "posted_at": listing.posted_at,
        "est_price": listing.est_price,
        "diff_pct": listing.diff_pct,
        "deal_score": listing.deal_score,
        "verdict": verdict_of(listing.diff_pct),
    }


def to_card(listing: Listing, ranked: RankedListing | None = None) -> ListingCard:
    fields = _card_fields(listing)
    if ranked is not None:
        fields |= {
            "match_score": ranked.match,
            "is_exact": ranked.is_exact,
            "near_miss_labels": list(ranked.labels),
        }
    return ListingCard(**fields)


def _price_breakdown(listing: Listing) -> PriceBreakdown:
    base = None
    km_adjustment = None
    insurance_adjustment = None
    if listing.est_price is not None:
        base = round(listing.est_price / (listing.km_factor * listing.insurance_factor))
        km_adjustment = round(base * (listing.km_factor - 1))
        insurance_adjustment = round(base * (listing.insurance_factor - 1))
    return PriceBreakdown(
        base=base,
        km_adjustment=km_adjustment,
        insurance_adjustment=insurance_adjustment,
        est_basis=listing.est_basis,
        est_sample_size=listing.est_sample_size,
    )


def to_detail(listing: Listing) -> ListingDetail:
    # Cards fall back to the city centroid so every listing has a map pin; the
    # detail page's own map must reflect the listing's real location (or hide
    # itself when there isn't one), so the fallback is overridden here.
    fields = _card_fields(listing) | {"lat": listing.lat, "lng": listing.lng}
    return ListingDetail(
        **fields,
        url=listing.url,
        description=mask_phone_numbers(listing.description),
        image_urls=listing.image_urls,
        color=listing.color,
        is_dealer=listing.is_dealer,
        price_type=listing.price_type,
        document_status=listing.document_status,
        attributes=listing.attributes,
        price_breakdown=_price_breakdown(listing),
    )
