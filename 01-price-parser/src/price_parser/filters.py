from dataclasses import dataclass

from .models import Product


@dataclass(slots=True, frozen=True)
class ProductFilter:
    min_price: float | None = None
    max_price: float | None = None
    min_rating: int | None = None
    in_stock_only: bool = False

    def __call__(self, product: Product) -> bool:
        if self.min_price is not None and product.price < self.min_price:
            return False
        if self.max_price is not None and product.price > self.max_price:
            return False
        if self.min_rating is not None and (product.rating or 0) < self.min_rating:
            return False
        return not (self.in_stock_only and product.in_stock is False)

    def apply(self, products: list[Product]) -> list[Product]:
        return [p for p in products if self(p)]
