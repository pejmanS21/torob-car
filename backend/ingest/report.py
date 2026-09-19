from collections import Counter
from dataclasses import dataclass, field

MAX_REJECT_RATIO = 0.01


@dataclass(slots=True)
class IngestReport:
    rows_read: int = 0
    rows_upserted: int = 0
    rejected: Counter[str] = field(default_factory=Counter)
    nulled: Counter[str] = field(default_factory=Counter)
    estimate_basis: Counter[str] = field(default_factory=Counter)
    price_suspect: int = 0
    data_version: int = 0

    @property
    def rows_rejected(self) -> int:
        return sum(self.rejected.values())

    @property
    def too_many_rejects(self) -> bool:
        return (
            self.rows_read > 0
            and self.rows_rejected / self.rows_read > MAX_REJECT_RATIO
        )

    def render(self) -> str:
        lines = [
            f"rows read      {self.rows_read}",
            f"rows upserted  {self.rows_upserted}",
            f"rows rejected  {self.rows_rejected} {dict(self.rejected)}",
            f"fields nulled  {dict(self.nulled)}",
            f"estimate basis {dict(self.estimate_basis)}",
            f"price suspect  {self.price_suspect}",
            f"data version   {self.data_version}",
        ]
        return "\n".join(lines)
