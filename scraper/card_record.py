"""
Phase 3: the raw, uncleaned record read directly from a single website row.

Keep these as-is. Do not clean or merge here, that happens later in the
exporter pipeline.
"""

from dataclasses import dataclass, fields, asdict


@dataclass
class CardRecord:
    name: str = ""
    card_number: str = ""
    set: str = ""
    variant: str = ""
    variant_name: str = ""
    attributes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def csv_columns() -> list[str]:
        return [f.name for f in fields(CardRecord)]
