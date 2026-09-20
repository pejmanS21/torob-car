"""Shared enums — the single source of truth for every closed vocabulary."""

from enum import StrEnum


class Category(StrEnum):
    LIGHT = "light"
    HEAVY = "heavy"
    MOTORCYCLE = "motorcycle"
    RENTAL = "rental"
    CLASSIC = "classic"


class Gearbox(StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class Fuel(StrEnum):
    PETROL = "petrol"
    DUAL_FACTORY = "dual_factory"
    DUAL_AFTERMARKET = "dual_aftermarket"
    HYBRID = "hybrid"
    PLUGIN_HYBRID = "plugin_hybrid"
    ELECTRIC = "electric"
    DIESEL = "diesel"


class BodyCondition(StrEnum):
    INTACT = "intact"
    NO_PAINT = "no_paint"
    MINOR_SCRATCHES = "minor_scratches"
    PARTIAL_PAINT = "partial_paint"
    HEAVY_PAINT = "heavy_paint"
    DROPPED = "dropped"
    ACCIDENT = "accident"
    ORIGINAL = "original"
    RESTORED = "restored"


class Source(StrEnum):
    """The site an ad was crawled from."""

    DIVAR = "divar"
    BAMA = "bama"
    KARNAMEH = "karnameh"
    HAMRAH_MECHANIC = "hamrah_mechanic"


class PriceType(StrEnum):
    """How the asking price is offered. Unknown on sources that never state it."""

    LUMPSUM = "lumpsum"
    NEGOTIABLE = "negotiable"
    INSTALLMENT = "installment"


class DocumentStatus(StrEnum):
    """Title-deed status. Divar reports transfer readiness, Hamrah Mechanic reports the
    deed's page count — different questions, so their answers stay separate members."""

    TITLE_IN_NAME = "title_in_name"
    READY_TO_TRANSFER = "ready_to_transfer"
    WHITE_TITLE = "white_title"
    NO_TITLE = "no_title"
    MORTGAGED = "mortgaged"
    SINGLE_PAGE = "single_page"
    TWO_PAGE = "two_page"
    MULTI_PAGE = "multi_page"


class FacetDimension(StrEnum):
    """A filter whose options are counted. Counting one leaves its own filter out,
    so the alternatives to what is already ticked stay visible."""

    CATEGORY = "category"
    MODEL = "model"
    CITY = "city"
    SOURCE = "source"
    GEARBOX = "gearbox"


class EstimateBasis(StrEnum):
    TRIM_YEAR = "trim_year"
    TRIM_NEAR_YEAR = "trim_near_year"
    MODEL_YEAR = "model_year"
    MODEL_NEAR_YEAR = "model_near_year"
    NONE = "none"


class SortKey(StrEnum):
    RELEVANCE = "relevance"
    DEAL = "deal"
    PRICE = "price"
    KM = "km"
    NEWEST = "newest"


class Verdict(StrEnum):
    CHEAP = "cheap"
    FAIR = "fair"
    EXPENSIVE = "expensive"
    UNKNOWN = "unknown"


class LlmProvider(StrEnum):
    GOOGLE = "google"
    OPENAI_COMPATIBLE = "openai_compatible"


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ParsedBy(StrEnum):
    LLM = "llm"
    RULES = "rules"


class MentionLevel(StrEnum):
    BRAND = "brand"
    MODEL = "model"
    TRIM = "trim"


class Criterion(StrEnum):
    VEHICLE = "vehicle"
    PRICE = "price"
    YEAR = "year"
    CITY = "city"
    KM = "km"
    GEARBOX = "gearbox"
    FUEL = "fuel"
    TEXT = "text"
    COLOR = "color"


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
