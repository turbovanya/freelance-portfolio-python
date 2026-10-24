"""Проверка ключа API, вход в панель и ограничение частоты запросов."""

import secrets
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .config import Settings

_basic = HTTPBasic(auto_error=False)


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def require_api_key(
    request: Request,
    key: str | None = Query(
        default=None, description="ключ, если конструктор сайта не умеет слать заголовки"
    ),
    settings: Settings = Depends(get_settings),
) -> None:
    provided = request.headers.get("x-api-key") or key or ""
    if not secrets.compare_digest(provided.encode(), settings.api_key.get_secret_value().encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный API-ключ")


def require_admin(
    credentials: HTTPBasicCredentials | None = Depends(_basic),
    settings: Settings = Depends(get_settings),
) -> str:
    if not settings.admin_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    ok = credentials is not None and (
        secrets.compare_digest(credentials.username.encode(), settings.admin_user.encode())
        & secrets.compare_digest(
            credentials.password.encode(), settings.admin_password.get_secret_value().encode()
        )
    )
    if not ok:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Нужен логин и пароль", headers={"WWW-Authenticate": "Basic"}
        )
    assert credentials is not None
    return credentials.username


class RateLimiter:
    """Скользящее окно в памяти: не больше N запросов в минуту с одного IP."""

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.per_minute = per_minute
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> bool:
        now = self._clock()
        hits = self._hits[key]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= self.per_minute:
            return False
        hits.append(now)
        return True


def client_ip(request: Request) -> str:
    # за nginx реальный IP подставляет uvicorn (--proxy-headers), сами X-Forwarded-For не читаем:
    # иначе любой обойдёт ограничение, подставив случайный заголовок
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request) -> None:
    limiter: RateLimiter = request.app.state.rate_limiter
    if not limiter.check(client_ip(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Слишком много запросов, попробуйте через минуту"
        )
