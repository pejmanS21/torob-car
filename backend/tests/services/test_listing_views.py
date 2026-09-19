"""Test that sensitive data (phone numbers) is masked in detail views."""

import types
import uuid
from datetime import datetime

from core.phone import PHONE_PLACEHOLDER
from enums import BodyCondition, Category, EstimateBasis, Fuel, Gearbox
from services.listing_views import to_card, to_detail


def test_detail_description_masks_phone_numbers() -> None:
    """Phone numbers are masked in ListingDetail.description; prices and other
    digit sequences are preserved."""

    listing = types.SimpleNamespace(
        id=uuid.uuid4(),
        token="test-token",
        title="پژو ۲۰۶",
        category=Category.LIGHT,
        catalog=types.SimpleNamespace(brand="پژو", model="۲۰۶", trim="تیپ ۲"),
        city=types.SimpleNamespace(name="تهران", lat=35.7, lng=51.4),
        year=1398,
        km=60_000,
        price=800_000_000,
        district=None,
        lat=None,
        lng=None,
        gearbox=Gearbox.MANUAL,
        fuel=Fuel.PETROL,
        body_condition=BodyCondition.INTACT,
        insurance_months=3,
        thumbnail_urls=[],
        image_urls=["https://example.com/image.jpg"],
        posted_at=datetime.now(),
        est_price=850_000_000,
        diff_pct=0.05,
        deal_score=75,
        url="https://example.com/listing",
        description="تماس: ۰۹۱۲ ۳۴۵ ۶۷۸۹ قیمت ۹۷۰,۰۰۰,۰۰۰ تومان",
        color="سفید",
        is_dealer=False,
        attributes={},
        km_factor=1.0,
        insurance_factor=1.0,
        est_basis=EstimateBasis.TRIM_YEAR,
        est_sample_size=42,
    )

    detail = to_detail(listing)

    # Phone number is masked.
    assert PHONE_PLACEHOLDER in detail.description
    # Original digits are gone.
    assert "۰۹۱۲" not in detail.description
    # Price text is preserved (not a phone number).
    assert "۹۷۰,۰۰۰,۰۰۰" in detail.description


def test_detail_lat_lng_are_none_without_coordinates_while_card_keeps_city() -> None:
    """A listing with no coordinates of its own: the card still falls back to
    the city centroid (so every listing has a map pin), but the detail view
    must not — it reports the real (missing) location so the map hides."""

    listing = types.SimpleNamespace(
        id=uuid.uuid4(),
        token="test-token",
        title="پژو ۲۰۶",
        category=Category.LIGHT,
        catalog=types.SimpleNamespace(brand="پژو", model="۲۰۶", trim="تیپ ۲"),
        city=types.SimpleNamespace(name="تهران", lat=35.7, lng=51.4),
        year=1398,
        km=60_000,
        price=800_000_000,
        district=None,
        lat=None,
        lng=None,
        gearbox=Gearbox.MANUAL,
        fuel=Fuel.PETROL,
        body_condition=BodyCondition.INTACT,
        insurance_months=3,
        thumbnail_urls=[],
        image_urls=["https://example.com/image.jpg"],
        posted_at=datetime.now(),
        est_price=850_000_000,
        diff_pct=0.05,
        deal_score=75,
        url="https://example.com/listing",
        description="بدون پلاک",
        color="سفید",
        is_dealer=False,
        attributes={},
        km_factor=1.0,
        insurance_factor=1.0,
        est_basis=EstimateBasis.TRIM_YEAR,
        est_sample_size=42,
    )

    card = to_card(listing)
    detail = to_detail(listing)

    assert card.lat == listing.city.lat and card.lng == listing.city.lng
    assert detail.lat is None and detail.lng is None
