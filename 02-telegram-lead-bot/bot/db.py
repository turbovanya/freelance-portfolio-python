import csv
import io
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL
);
"""


class LeadStorage:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def add(self, user_id: int, username, name: str, phone: str, comment: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO leads(user_id, username, name, phone, comment, created_at) VALUES (?,?,?,?,?,?)",
            (user_id, username, name, phone, comment, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        self.conn.commit()
        return cur.lastrowid

    def recent(self, limit: int = 10) -> list:
        return self.conn.execute("SELECT * FROM leads ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

    def stats(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        today = datetime.now(timezone.utc).date().isoformat()
        today_count = self.conn.execute(
            "SELECT COUNT(*) FROM leads WHERE created_at LIKE ?", (today + "%",)
        ).fetchone()[0]
        return {"total": total, "today": today_count}

    def export_csv(self) -> bytes:
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";")
        writer.writerow(["id", "user_id", "username", "name", "phone", "comment", "created_at"])
        for r in self.conn.execute("SELECT * FROM leads ORDER BY id"):
            writer.writerow([r["id"], r["user_id"], r["username"], r["name"], r["phone"], r["comment"], r["created_at"]])
        return buf.getvalue().encode("utf-8-sig")
