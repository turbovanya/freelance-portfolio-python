from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass(slots=True)
class Product:
    title: str
    url: str
    price: float
    currency: str = ""
    rating: int | None = None
    in_stock: bool | None = None
    image_url: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class PriceChange:
    title: str
    url: str
    old_price: float
    new_price: float

    @property
    def delta(self) -> float:
        return round(self.new_price - self.old_price, 2)

    @property
    def percent(self) -> float:
        if not self.old_price:
            return 0.0
        return round(self.delta / self.old_price * 100, 1)

    @property
    def is_increase(self) -> bool:
        return self.delta > 0


@dataclass(slots=True)
class RunResult:
    """Итог одного запуска: что собрали и что изменилось с прошлого раза."""

    profile: str
    started_at: datetime
    products: list[Product]
    changes: list[PriceChange] = field(default_factory=list)
    new_products: list[Product] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    pages: int = 0
    first_run: bool = False

    @property
    def increased(self) -> list[PriceChange]:
        return [c for c in self.changes if c.is_increase]

    @property
    def decreased(self) -> list[PriceChange]:
        return [c for c in self.changes if not c.is_increase]
