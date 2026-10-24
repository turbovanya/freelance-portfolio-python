import csv
from pathlib import Path

from ..models import Product, RunResult
from .common import COLUMNS, csv_safe, display_value


def export_csv(result: RunResult, products: list[Product], path: Path) -> Path:
    """CSV под русский Excel: разделитель ';' и UTF-8 с BOM, открывается двойным кликом."""
    path = path.with_suffix(".csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([title for _, title in COLUMNS])
        for p in products:
            writer.writerow([csv_safe(display_value(p, key)) for key, _ in COLUMNS])
    return path
