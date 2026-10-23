import pytest
from fastapi.testclient import TestClient

from app.main import LeadStore, Settings, create_app

KEY = {"X-API-Key": "secret"}
GOOD = {"name": "Иван Петров", "phone": "8 (912) 345-67-89", "email": "ivan@example.com", "message": "Нужен  бот"}


class FakeNotifier:
    enabled = True

    def __init__(self, ok=True):
        self.ok, self.sent = ok, []

    async def send(self, text):
        self.sent.append(text)
        return self.ok


@pytest.fixture
def ctx():
    notifier, store = FakeNotifier(), LeadStore(":memory:")
    app = create_app(Settings(api_key="secret"), notifier, store)
    return TestClient(app), notifier, store


def test_lead_saved_and_sent(ctx):
    client, notifier, store = ctx
    r = client.post("/webhook/lead", json=GOOD, headers=KEY)
    assert r.status_code == 201 and r.json() == {"ok": True, "id": 1}
    row = store.all()[0]
    assert row["phone"] == "+79123456789" and row["message"] == "Нужен бот" and row["notified"] == 1
    assert "Заявка №1" in notifier.sent[0] and "+79123456789" in notifier.sent[0]


def test_requires_api_key(ctx):
    client, notifier, store = ctx
    assert client.post("/webhook/lead", json=GOOD).status_code == 401
    assert client.post("/webhook/lead", json=GOOD, headers={"X-API-Key": "bad"}).status_code == 401
    assert store.all() == [] and notifier.sent == []


@pytest.mark.parametrize("patch", [{"phone": "123"}, {"name": "A"}, {"email": "not-an-email"}])
def test_validation_errors(ctx, patch):
    client, _, store = ctx
    r = client.post("/webhook/lead", json={**GOOD, **patch}, headers=KEY)
    assert r.status_code == 422 and store.all() == []


def test_honeypot_ignored(ctx):
    client, notifier, store = ctx
    r = client.post("/webhook/lead", json={**GOOD, "website": "http://spam"}, headers=KEY)
    assert r.status_code == 201 and r.json()["id"] is None
    assert store.all() == [] and notifier.sent == []


def test_telegram_failure_keeps_lead():
    notifier, store = FakeNotifier(ok=False), LeadStore(":memory:")
    client = TestClient(create_app(Settings(api_key="secret"), notifier, store))
    assert client.post("/webhook/lead", json=GOOD, headers=KEY).status_code == 201
    assert store.all()[0]["notified"] == 0  # заявка не потеряна, видно что уведомление не ушло


def test_csv_export_and_health(ctx):
    client, _, _ = ctx
    client.post("/webhook/lead", json=GOOD, headers=KEY)
    assert client.get("/leads.csv").status_code == 401
    lines = client.get("/leads.csv", headers=KEY).content.decode("utf-8-sig").splitlines()
    assert len(lines) == 2 and "+79123456789" in lines[1]
    assert client.get("/health").json() == {"status": "ok", "telegram": True}
