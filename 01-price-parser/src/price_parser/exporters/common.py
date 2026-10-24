from ..models import Product

COLUMNS: list[tuple[str, str]] = [
    ("title", "Название"),
    ("price", "Цена"),
    ("currency", "Валюта"),
    ("rating", "Рейтинг"),
    ("in_stock", "В наличии"),
    ("url", "Ссылка"),
    ("image_url", "Картинка"),
]


def display_value(product: Product, key: str) -> object:
    value = getattr(product, key)
    if key == "in_stock":
        return {True: "да", False: "нет", None: ""}[value]
    return "" if value is None else value


def csv_safe(value: object) -> object:
    """Excel выполняет ячейки, начинающиеся с = + - @, как формулы. Данные с чужого сайта экранируем."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value
