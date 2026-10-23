"""История цен в SQLite: что подорожало/подешевело между запусками."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    price REAL NOT NULL,
    scraped_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_url ON price_history(url, id);
"""


class PriceStore:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def last_prices(self) -> dict:
        rows = self.conn.execute(
            "SELECT url, price FROM price_history WHERE id IN (SELECT MAX(id) FROM price_history GROUP BY url)"
        )
        return dict(rows.fetchall())

    def save_and_diff(self, products) -> list:
        """Сохраняет снимок цен, возвращает изменения относительно прошлого запуска."""
        previous = self.last_prices()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        changes = []
        for p in products:
            old = previous.get(p.url)
            if old is not None and abs(old - p.price) > 1e-9:
                changes.append({
                    "title": p.title, "url": p.url, "old_price": old, "new_price": p.price,
                    "delta": round(p.price - old, 2),
                })
            if old is None or abs(old - p.price) > 1e-9:
                self.conn.execute(
                    "INSERT INTO price_history(url, title, price, scraped_at) VALUES (?,?,?,?)",
                    (p.url, p.title, p.price, now),
                )
        self.conn.commit()
        return changes

    def close(self):
        self.conn.close()
