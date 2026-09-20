"""The parsed intent echoed back as short Persian chips, so the user sees what the
search understood."""

from core.text import to_persian_digits
from enums import MentionLevel
from ranking import labels
from ranking.types import VehicleTarget
from schemas.search import SearchIntent

KM_PER_THOUSAND = 1_000
ONLY_BELOW_MARKET = "فقط ارزان‌تر از بازار"


def _target_chip(target: VehicleTarget) -> str:
    if target.level is MentionLevel.TRIM and target.trim:
        return target.trim
    if target.level is MentionLevel.MODEL and target.model:
        return target.model
    return target.brand


def _year_chip(intent: SearchIntent) -> str | None:
    low, high = intent.year_min, intent.year_max
    if low and high:
        years = to_persian_digits(low)
        return (
            f"مدل {years}" if low == high else f"{years} تا {to_persian_digits(high)}"
        )
    if low:
        return f"از {to_persian_digits(low)}"
    return f"تا {to_persian_digits(high)}" if high else None


def build_chips(
    intent: SearchIntent, targets: tuple[VehicleTarget, ...], text: str | None
) -> tuple[str, ...]:
    chips: list[str | None] = [_target_chip(target) for target in targets]
    chips.append(_year_chip(intent))
    if intent.price_min:
        chips.append(f"از {labels.format_toman(intent.price_min)}")
    if intent.price_max:
        chips.append(f"زیر {labels.format_toman(intent.price_max)}")
    if intent.km_min:
        thousands = to_persian_digits(round(intent.km_min / KM_PER_THOUSAND))
        chips.append(f"کارکرد از {thousands} هزار")
    if intent.km_max:
        thousands = to_persian_digits(round(intent.km_max / KM_PER_THOUSAND))
        chips.append(f"کارکرد زیر {thousands} هزار")
    chips.extend(intent.cities)
    if intent.gearbox:
        chips.append(labels.GEARBOX_NAMES[intent.gearbox])
    if intent.fuel:
        chips.append(labels.FUEL_NAMES[intent.fuel])
    chips.extend(intent.colors)
    if intent.only_below_market:
        chips.append(ONLY_BELOW_MARKET)
    if text:
        chips.append(f"«{text}»")
    return tuple(chip for chip in chips if chip)
