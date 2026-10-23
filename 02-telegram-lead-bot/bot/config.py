import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


def parse_admin_ids(raw: str) -> list:
    return [int(x) for x in raw.replace(" ", "").split(",") if x.strip().lstrip("-").isdigit()]


@dataclass(frozen=True)
class Config:
    token: str
    admin_ids: list = field(default_factory=list)
    db_path: str = "data/leads.db"
    faq_path: str = "faq.json"
    business_name: str = "Студия «Пример»"

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("BOT_TOKEN не задан. Скопируйте .env.example в .env и впишите токен от @BotFather.")
        return cls(
            token=token,
            admin_ids=parse_admin_ids(os.getenv("ADMIN_IDS", "")),
            db_path=os.getenv("DB_PATH", "data/leads.db"),
            faq_path=os.getenv("FAQ_PATH", "faq.json"),
            business_name=os.getenv("BUSINESS_NAME", "Студия «Пример»"),
        )
