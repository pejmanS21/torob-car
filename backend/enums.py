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
