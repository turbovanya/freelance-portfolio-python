"""HTTP-клиент с повторами, паузами и уважением к Retry-After."""

import logging
import time
from collections.abc import Callable
from types import TracebackType

import httpx

from .config import Settings

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    pass


class HttpClient:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self._sleep = sleep
        self._last_request = 0.0
        self._client = httpx.Client(
            headers={"User-Agent": settings.user_agent, "Accept-Language": "ru,en;q=0.8"},
            timeout=settings.request_timeout,
            follow_redirects=True,
            proxy=settings.proxy,
            transport=transport,
        )

    def _throttle(self) -> None:
        wait = self.settings.request_delay - (time.monotonic() - self._last_request)
        if wait > 0:
            self._sleep(wait)
        self._last_request = time.monotonic()

    def get_text(self, url: str, encoding: str | None = None) -> str:
        attempts = self.settings.retries
        for attempt in range(1, attempts + 1):
            self._throttle()
            try:
                resp = self._client.get(url)
            except httpx.TransportError as exc:
                reason, retry_after = str(exc) or type(exc).__name__, None
            else:
                if resp.status_code < 400:
                    if encoding:
                        resp.encoding = encoding
                    elif "charset" not in resp.headers.get("content-type", ""):
                        # без charset httpx может угадать неправильно и испортить символы
                        resp.encoding = "utf-8"
                    return resp.text
                if resp.status_code not in RETRY_STATUSES:
                    raise FetchError(f"{url}: HTTP {resp.status_code}")
                reason = f"HTTP {resp.status_code}"
                retry_after = _parse_retry_after(resp.headers.get("retry-after"))

            log.warning("%s: попытка %s/%s не удалась (%s)", url, attempt, attempts, reason)
            if attempt < attempts:
                self._sleep(
                    retry_after if retry_after is not None else self.settings.request_delay * 2**attempt
                )
        raise FetchError(f"{url}: не удалось загрузить за {attempts} попыток")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()


def _parse_retry_after(value: str | None) -> float | None:
    if value and value.isdigit():
        return min(float(value), 60.0)
    return None
