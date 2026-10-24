import httpx
import pytest
from conftest import ADMIN, post
from fastapi.testclient import TestClient

from lead_hub.config import Settings
from lead_hub.main import create_app
from lead_hub.notifier import NotifyError, TelegramNotifier
from lead_hub.schemas import normalize_payload
from lead_hub.security import RateLimiter
from lead_hub.services import csv_safe


def test_admin_requires_password(client):
    assert client.get("/admin").status_code == 401
    assert client.get("/admin", auth=(ADMIN[0], "wrong")).status_code == 401


def test_admin_dashboard_shows_leads(client):
    post(client)
    html = client.get("/admin", auth=ADMIN).text
    assert "Иван Петров" in html and "доставлено" in html and "Скачать CSV" in html
    assert client.get("/admin?q=несуществующий", auth=ADMIN).text.count("<tr>") == 0


def test_admin_disabled_without_password(notifier):
    settings = Settings(_env_file=None, api_key="k" * 32, database_url="sqlite+aiosqlite:///:memory:")
    with TestClient(create_app(settings, notifier)) as client:
        assert client.get("/admin", auth=ADMIN).status_code == 404
        assert client.get("/", follow_redirects=False).headers["location"] == "/docs"


def test_insecure_api_key_is_refused():
    for weak in ("change-me", "short-key"):
        with pytest.raises(RuntimeError, match="API_KEY"):
            Settings(_env_file=None, api_key=weak).check_production_ready()
    Settings(_env_file=None, api_key="x" * 16).check_production_ready()


def test_normalize_payload_aliases():
    assert normalize_payload(
        {"Name": " Иван ", "TEL": "8912", "e-mail": "", "Comments": "hi", "junk": 1}
    ) == {
        "name": "Иван",
        "phone": "8912",
        "message": "hi",
    }


def test_csv_safe():
    assert csv_safe("=1+1") == "'=1+1" and csv_safe("@cmd") == "'@cmd"
    assert csv_safe("+79123456789") == "+79123456789" and csv_safe(None) == ""


def test_rate_limiter_window():
    now = [0.0]
    limiter = RateLimiter(2, clock=lambda: now[0])
    assert limiter.check("ip") and limiter.check("ip") and not limiter.check("ip")
    assert limiter.check("other-ip")
    now[0] = 61
    assert limiter.check("ip")


async def test_telegram_notifier_success_and_errors():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    notifier = TelegramNotifier("1:abc", "42", transport=httpx.MockTransport(handler))
    await notifier.send("<b>hi</b>")
    assert requests[0].url.path == "/bot1:abc/sendMessage"

    failing = TelegramNotifier("1:abc", "42", transport=httpx.MockTransport(lambda r: httpx.Response(403)))
    with pytest.raises(NotifyError, match="403"):
        await failing.send("x")

    with pytest.raises(NotifyError, match="не настроен"):
        await TelegramNotifier("", "").send("x")
