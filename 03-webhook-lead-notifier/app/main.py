"""Приём заявок с сайта (форма -> POST /webhook/lead) -> SQLite + уведомление в Telegram."""
import csv
import io
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator


class Settings(BaseModel):
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    api_key: str = "change-me"
    db_path: str = "data/leads.db"
    allowed_origins: list = ["*"]

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            api_key=os.getenv("API_KEY", "change-me"),
            db_path=os.getenv("DB_PATH", "data/leads.db"),
            allowed_origins=[o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()],
        )


class LeadIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    phone: str
    email: Optional[str] = Field(default=None, max_length=120)
    message: str = Field(default="", max_length=1000)
    source: str = Field(default="website", max_length=80)
    website: str = ""  # honeypot: реальные пользователи это поле не видят и не заполняют

    @field_validator("name", "message", "source")
    @classmethod
    def squash(cls, v: str) -> str:
        return " ".join(v.split())

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) == 11 and digits[0] in "78":
            digits = digits[1:]
        if len(digits) != 10:
            raise ValueError("Некорректный номер телефона")
        return "+7" + digits

    @field_validator("email")
    @classmethod
    def email_ok(cls, v):
        if v and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            raise ValueError("Некорректный email")
        return v or None


class LeadStore:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT,"
            " email TEXT, message TEXT, source TEXT, notified INTEGER DEFAULT 0, created_at TEXT)"
        )

    def add(self, lead: LeadIn) -> int:
        cur = self.conn.execute(
            "INSERT INTO leads(name, phone, email, message, source, created_at) VALUES (?,?,?,?,?,?)",
            (lead.name, lead.phone, lead.email, lead.message, lead.source,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        self.conn.commit()
        return cur.lastrowid

    def mark_notified(self, lead_id: int):
        self.conn.execute("UPDATE leads SET notified=1 WHERE id=?", (lead_id,))
        self.conn.commit()

    def all(self) -> list:
        return self.conn.execute("SELECT * FROM leads ORDER BY id").fetchall()


def format_message(lead_id: int, lead: LeadIn) -> str:
    return (f"🔔 Заявка №{lead_id} ({lead.source})\n👤 {lead.name}\n📞 {lead.phone}\n"
            f"✉️ {lead.email or '—'}\n💬 {lead.message or '—'}")


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token, self.chat_id = token, chat_id

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    async def send(self, text: str) -> bool:
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={"chat_id": self.chat_id, "text": text},
                )
            return r.status_code == 200
        except httpx.HTTPError:
            return False


def create_app(settings: Optional[Settings] = None, notifier=None, store: Optional[LeadStore] = None) -> FastAPI:
    settings = settings or Settings.from_env()
    notifier = notifier or TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
    store = store or LeadStore(settings.db_path)
    app = FastAPI(title="Lead webhook")
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_methods=["POST", "GET"],
                       allow_headers=["*"])

    def require_key(x_api_key: str = Header(default="")):
        if not secrets.compare_digest(x_api_key, settings.api_key):
            raise HTTPException(status_code=401, detail="Неверный API-ключ")

    @app.get("/health")
    def health():
        return {"status": "ok", "telegram": notifier.enabled}

    @app.post("/webhook/lead", status_code=201, dependencies=[Depends(require_key)])
    async def receive(lead: LeadIn):
        if lead.website:  # honeypot сработал — тихо «принимаем», но ничего не сохраняем
            return {"ok": True, "id": None}
        lead_id = store.add(lead)
        if await notifier.send(format_message(lead_id, lead)):
            store.mark_notified(lead_id)
        return {"ok": True, "id": lead_id}

    @app.get("/leads.csv", dependencies=[Depends(require_key)])
    def export():
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["id", "name", "phone", "email", "message", "source", "notified", "created_at"])
        for r in store.all():
            w.writerow([r[k] for k in ("id", "name", "phone", "email", "message", "source", "notified", "created_at")])
        return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv; charset=utf-8")

    app.state.store = store
    return app


def get_app() -> FastAPI:  # uvicorn app.main:get_app --factory
    return create_app()
