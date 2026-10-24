import pytest
from fastapi.testclient import TestClient

from lead_hub.config import Settings
from lead_hub.main import create_app
from lead_hub.notifier import NotifyError

KEY = {"X-API-Key": "k" * 32}
ADMIN = ("manager", "pass-123")
GOOD = {
    "name": "Иван Петров",
    "phone": "8 (912) 345-67-89",
    "email": "ivan@example.com",
    "message": "Нужен  бот",
}


class FakeNotifier:
    enabled = True

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.fail = False

    async def send(self, text: str) -> None:
        if self.fail:
            raise NotifyError("Telegram 502: Bad Gateway")
        self.sent.append(text)


def make_settings(**overrides):
    values = {
        "api_key": "k" * 32,
        "database_url": "sqlite+aiosqlite:///:memory:",
        "admin_user": ADMIN[0],
        "admin_password": ADMIN[1],
        "rate_limit_per_minute": 100,
        "resend_interval_seconds": 3600,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def notifier():
    return FakeNotifier()


@pytest.fixture
def client(notifier):
    app = create_app(make_settings(), notifier)
    with TestClient(app) as c:
        yield c


def post(client, data=None, *, headers=KEY, **kwargs):
    return client.post("/api/v1/leads", json=GOOD if data is None else data, headers=headers, **kwargs)
