import httpx
import pytest

from price_parser.http import FetchError, HttpClient

URL = "https://example.com/catalog"


def make_client(settings, responses):
    calls = []
    sleeps = []

    def handler(request):
        calls.append(request)
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    client = HttpClient(settings, transport=httpx.MockTransport(handler), sleep=sleeps.append)
    return client, calls, sleeps


def test_retries_network_errors_and_5xx(settings):
    client, calls, _ = make_client(
        settings, [httpx.ConnectError("down"), httpx.Response(503), httpx.Response(200, text="ok")]
    )
    assert client.get_text(URL) == "ok"
    assert len(calls) == 3


def test_does_not_retry_404(settings):
    client, calls, _ = make_client(settings, [httpx.Response(404), httpx.Response(200)])
    with pytest.raises(FetchError, match="404"):
        client.get_text(URL)
    assert len(calls) == 1


def test_respects_retry_after(settings):
    client, _, sleeps = make_client(
        settings, [httpx.Response(429, headers={"retry-after": "7"}), httpx.Response(200, text="ok")]
    )
    client.get_text(URL)
    assert 7.0 in sleeps


def test_gives_up_after_all_attempts(settings):
    client, calls, _ = make_client(settings, [httpx.Response(500)] * 3)
    with pytest.raises(FetchError, match="3 попыток"):
        client.get_text(URL)
    assert len(calls) == 3


def test_defaults_to_utf8_without_charset(settings):
    body = "£51.77".encode()
    client, _, _ = make_client(
        settings, [httpx.Response(200, content=body, headers={"content-type": "text/html"})]
    )
    assert client.get_text(URL) == "£51.77"
