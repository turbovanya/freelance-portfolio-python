"""История цен в SQLite.

Каждый запуск сохраняется в runs, а в prices попадает снимок цены на момент запуска.
Отсюда считаются изменения, новые товары и товары, пропавшие из каталога.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import TracebackType

from .models import PriceChange, Product

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    profile     TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    items       INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS prices (
    run_id   INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    url      TEXT NOT NULL,
    title    TEXT NOT NULL,
    price    REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (run_id, url)
);
CREATE INDEX IF NOT EXISTS idx_prices_url ON prices(url, run_id);
"""

EPSILON = 0.005


@dataclass(slots=True, frozen=True)
class HistoryPoint:
    seen_at: str
    price: float
    currency: str


@dataclass(slots=True)
class Diff:
    changes: list[PriceChange]
    new_products: list[Product]
    removed: list[str]
    first_run: bool


class PriceStore:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    def _last_run_id(self, profile: str) -> int | None:
        row = self.conn.execute("SELECT MAX(id) FROM runs WHERE profile = ?", (profile,)).fetchone()
        return row[0] if row else None

    def _snapshot(self, run_id: int) -> dict[str, tuple[str, float]]:
        rows = self.conn.execute("SELECT url, title, price FROM prices WHERE run_id = ?", (run_id,))
        return {url: (title, price) for url, title, price in rows}

    def save_run(self, profile: str, started_at: datetime, products: list[Product]) -> Diff:
        """Сохраняет снимок и возвращает разницу с предыдущим запуском этого профиля."""
        last_id = self._last_run_id(profile)
        previous = self._snapshot(last_id) if last_id else {}

        changes: list[PriceChange] = []
        new_products: list[Product] = []
        for p in products:
            if p.url not in previous:
                if last_id:
                    new_products.append(p)
                continue
            old_price = previous[p.url][1]
            if abs(old_price - p.price) > EPSILON:
                changes.append(PriceChange(p.title, p.url, old_price, p.price))
        current_urls = {p.url for p in products}
        removed = [title for url, (title, _) in previous.items() if url not in current_urls]

        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO runs(profile, started_at, items) VALUES (?, ?, ?)",
                (profile, started_at.isoformat(timespec="seconds"), len(products)),
            )
            self.conn.executemany(
                "INSERT OR REPLACE INTO prices(run_id, url, title, price, currency) VALUES (?, ?, ?, ?, ?)",
                [(cur.lastrowid, p.url, p.title, p.price, p.currency) for p in products],
            )
        changes.sort(key=lambda c: abs(c.percent), reverse=True)
        return Diff(changes, new_products, removed, first_run=last_id is None)

    def history(self, url: str, limit: int = 30) -> list[HistoryPoint]:
        rows = self.conn.execute(
            """SELECT r.started_at, p.price, p.currency FROM prices p JOIN runs r ON r.id = p.run_id
               WHERE p.url = ? ORDER BY r.id DESC LIMIT ?""",
            (url, limit),
        )
        return [HistoryPoint(*row) for row in rows]

    def runs(self, limit: int = 10) -> list[tuple[int, str, str, int]]:
        return self.conn.execute(
            "SELECT id, profile, started_at, items FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "PriceStore":
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()
