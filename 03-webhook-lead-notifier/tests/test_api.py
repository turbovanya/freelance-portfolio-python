import csv
import io

import pytest
from conftest import ADMIN, GOOD, KEY, make_settings, post
from fastapi.testclient import TestClient

from lead_hub.main import create_app


def test_lead_saved_and_sent(client, notifier):
    r = post(client)
    assert r.status_code == 201 and r.json() == {"ok": True, "id": 1, "duplicate": False}

    lead = client.get("/api/v1/leads", headers=KEY).json()["items"][0]
    assert lead["phone"] == "+79123456789" and lead["message"] == "Нужен бот" and lead["notified"]
    assert "Заявка №1" in notifier.sent[0] and "<code>+79123456789</code>" in notifier.sent[0]


def test_form_encoded_with_tilda_style_field_names(client, notifier):
    form = {
        "Name": "Мария",
        "Phone": "+7 999 000-11-22",
        "Comments": "Перезвоните",
        "formname": "tilda-header",
        "utm_source": "yandex",
        "utm_campaign": "autumn",
    }
    r = client.post("/api/v1/leads?key=" + "k" * 32, data=form)
    assert r.status_code == 201
    lead = client.get("/api/v1/leads", headers=KEY).json()["items"][0]
    assert (lead["name"], lead["source"], lead["utm_campaign"]) == ("Мария", "tilda-header", "autumn")
    assert "📈 yandex / autumn" in notifier.sent[0]


def test_tilda_test_request(client):
    r = client.post("/api/v1/leads", data={"test": "test"}, headers=KEY)
    assert r.status_code == 200 and r.text == "ok"


def test_requires_api_key(client, notifier):
    assert post(client, headers={}).status_code == 401
    assert post(client, headers={"X-API-Key": "wrong"}).status_code == 401
    assert notifier.sent == []


@pytest.mark.parametrize(
    "patch",
    [{"phone": "123"}, {"phone": "+7 000 000-00-00"}, {"name": "A"}, {"email": "not-an-email"}],
)
def test_validation_errors(client, patch):
    r = post(client, {**GOOD, **patch})
    assert r.status_code == 422
    assert r.json()["detail"] == "Проверьте поля формы" and r.json()["errors"][0]["field"] in patch
    assert client.get("/api/v1/leads", headers=KEY).json()["total"] == 0


def test_bad_json(client):
    r = client.post("/api/v1/leads", content=b"{oops", headers={**KEY, "Content-Type": "application/json"})
    assert r.status_code == 400


def test_honeypot_silently_ignored(client, notifier):
    r = post(client, {**GOOD, "website": "http://spam"})
    assert r.status_code == 201 and r.json()["id"] is None
    assert notifier.sent == []


def test_double_submit_is_not_duplicated(client, notifier):
    post(client)
    r = post(client, {**GOOD, "phone": "+7 912 345 67 89"})
    assert r.json() == {"ok": True, "id": None, "duplicate": True}
    assert len(notifier.sent) == 1


def test_telegram_failure_keeps_lead_and_resend_delivers(client, notifier):
    notifier.fail = True
    post(client)
    assert client.get("/health").json()["pending"] == 1

    notifier.fail = False
    r = client.post("/admin/resend", auth=ADMIN, follow_redirects=False)
    assert r.status_code == 303
    assert client.get("/health").json()["pending"] == 0
    assert "Заявка №1" in notifier.sent[0]


def test_rate_limit(notifier):
    app = create_app(make_settings(rate_limit_per_minute=2), notifier)
    with TestClient(app) as client:
        codes = [post(client, {**GOOD, "phone": f"+7912000000{i}"}).status_code for i in range(3)]
    assert codes == [201, 201, 429]


def test_csv_export_escapes_formulas(client):
    post(client, {**GOOD, "message": '=HYPERLINK("http://evil")'})
    assert client.get("/api/v1/leads/export.csv").status_code == 401
    r = client.get("/api/v1/leads/export.csv", headers=KEY)
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    assert rows[0][0] == "№" and rows[1][3] == "+79123456789" and rows[1][5].startswith("'=")


def test_list_search_and_pagination(client):
    for i, name in enumerate(["Анна", "Борис", "Вера"]):
        post(client, {**GOOD, "name": name, "phone": f"+7912000000{i}"})
    page = client.get("/api/v1/leads?limit=2", headers=KEY).json()
    assert page["total"] == 3 and [i["name"] for i in page["items"]] == ["Вера", "Борис"]
    found = client.get("/api/v1/leads?search=бор", headers=KEY).json()
    assert [i["name"] for i in found["items"]] == ["Борис"]


def test_stats(client):
    post(client)
    post(client, {**GOOD, "phone": "+79120000001", "source": "landing"})
    stats = client.get("/api/v1/stats", headers=KEY).json()
    assert stats["total"] == 2 and stats["today"] == 2 and stats["pending"] == 0
    assert {s["source"] for s in stats["sources"]} == {"website", "landing"}


def test_validation_messages_are_russian(client):
    r = post(client, {"name": "A", "phone": "123", "email": "x@"})
    messages = [e["message"] for e in r.json()["errors"]]
    assert messages == [
        "Имя: слишком короткое значение",
        "Телефон: некорректный номер телефона, нужен российский номер",
        "Email: некорректный email",
    ]
