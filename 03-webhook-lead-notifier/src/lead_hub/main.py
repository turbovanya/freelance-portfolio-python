"""Сборка FastAPI-приложения и точка входа."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from . import __version__, admin, api, errors
from .config import Settings
from .db import LeadRepository, create_engine, init_db
from .notifier import Notifier, TelegramNotifier
from .security import RateLimiter
from .services import Delivery

log = logging.getLogger("lead_hub")
STATIC = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None, notifier: Notifier | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()
        settings.check_production_ready()
    engine = create_engine(settings.database_url)
    repo = LeadRepository(engine)
    notifier = notifier or TelegramNotifier(
        settings.telegram_bot_token.get_secret_value(), settings.telegram_chat_id
    )
    delivery = Delivery(repo, notifier, settings.tz)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await init_db(engine)
        if not notifier.enabled:
            log.warning("Telegram не настроен: заявки сохраняются, уведомления не отправляются")
        worker = asyncio.create_task(delivery.run_forever(settings.resend_interval_seconds))
        yield
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker
        await engine.dispose()

    app = FastAPI(
        title="Lead Hub",
        version=__version__,
        description="Приём заявок с сайта: проверка данных, сохранение, уведомление в Telegram.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.repo = repo
    app.state.delivery = delivery
    app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )
    errors.install(app)
    app.include_router(api.router)
    app.include_router(admin.router)

    @app.get("/health", tags=["Служебное"], summary="Проверка, что сервис жив")
    async def health() -> dict[str, object]:
        stats = await repo.stats()
        return {
            "status": "ok",
            "version": __version__,
            "telegram": notifier.enabled,
            "pending": stats["pending"],
        }

    @app.get("/", include_in_schema=False)
    async def index() -> RedirectResponse:
        return RedirectResponse("/admin" if settings.admin_enabled else "/docs")

    if settings.demo_form:

        @app.get("/demo", include_in_schema=False)
        async def demo() -> FileResponse:
            return FileResponse(STATIC / "demo-form.html")

    return app


def get_app() -> FastAPI:
    """Фабрика для uvicorn: uvicorn lead_hub.main:get_app --factory"""
    return create_app()


def run() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    uvicorn.run("lead_hub.main:get_app", factory=True, host="0.0.0.0", port=8000, proxy_headers=True)
