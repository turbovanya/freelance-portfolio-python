"""CLI: python main.py --max-pages 3 --min-rating 4 --format xlsx"""
import argparse
import logging
import os

from parser.config import Settings
from parser.export import to_csv, to_xlsx
from parser.scraper import filter_products, scrape
from parser.storage import PriceStore


def build_args():
    ap = argparse.ArgumentParser(description="Парсер каталога цен с экспортом в CSV/XLSX и отслеживанием изменений")
    ap.add_argument("--max-pages", type=int, help="сколько страниц обойти (0 = все)")
    ap.add_argument("--min-price", type=float)
    ap.add_argument("--max-price", type=float)
    ap.add_argument("--min-rating", type=int, choices=range(1, 6))
    ap.add_argument("--in-stock", action="store_true", help="только товары в наличии")
    ap.add_argument("--format", choices=["csv", "xlsx", "both"], default="both")
    return ap.parse_args()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_args()
    settings = Settings.from_env()
    if args.max_pages is not None:
        settings = Settings(**{**settings.__dict__, "max_pages": args.max_pages})

    products = scrape(settings)
    products = filter_products(products, args.min_price, args.max_price, args.min_rating, args.in_stock)

    store = PriceStore(settings.db_path)
    changes = store.save_and_diff(products)
    store.close()

    if args.format in ("csv", "both"):
        print("CSV :", to_csv(products, os.path.join(settings.output_dir, "products.csv")))
    if args.format in ("xlsx", "both"):
        print("XLSX:", to_xlsx(products, os.path.join(settings.output_dir, "products.xlsx"), changes))

    print(f"Товаров: {len(products)}, изменений цен с прошлого запуска: {len(changes)}")
    for c in changes[:10]:
        print(f"  {c['title']}: {c['old_price']} -> {c['new_price']} ({c['delta']:+})")


if __name__ == "__main__":
    main()
