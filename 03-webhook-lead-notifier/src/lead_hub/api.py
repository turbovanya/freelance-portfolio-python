"""Публичный API: приём заявок с сайта и чтение для интеграций."""

import json
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from .config import Settings
from .db import LeadRepository
from .schemas import LeadCreated, LeadIn, LeadOut, LeadPage, normalize_payload
from .security import client_ip, get_settings, rate_limit, require_api_key
from .services import Delivery, leads_to_csv

router = APIRouter(prefix="/api/v1", tags=["Заявки"])


def get_repo(request: Request) -> LeadRepository:
    repo: LeadRepository = request.app.state.repo
    return repo


def get_delivery(request: Request) -> Delivery:
    delivery: Delivery = request.app.state.delivery
    return delivery


async def _read_payload(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Некорректный JSON") from exc
        if not isinstance(data, dict):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ожидается JSON-объект")
        return data
    # Tilda, WordPress и обычные HTML-формы присылают application/x-www-form-urlencoded
    form = await request.form()
    return {k: v for k, v in form.items() if isinstance(v, str)}


@router.post(
    "/leads",
    response_model=LeadCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
    summary="Принять заявку с сайта",
    description=(
        "Принимает JSON или обычную форму. Имена полей можно передавать как name/Name/fio, phone/tel и т.п."
    ),
)
async def create_lead(
    request: Request,
    repo: Annotated[LeadRepository, Depends(get_repo)],
    delivery: Annotated[Delivery, Depends(get_delivery)],
) -> LeadCreated | Response:
    raw = await _read_payload(request)
    if raw.get("test") == "test":
        # Tilda при подключении вебхука присылает проверочный запрос
        return Response("ok", media_type="text/plain")
    try:
        lead_in = LeadIn.model_validate(normalize_payload(raw))
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    if lead_in.website:
        # сработала ловушка для ботов: отвечаем как обычно, но ничего не сохраняем
        return LeadCreated(id=None)
    if await repo.is_duplicate(lead_in.phone):
        return LeadCreated(id=None, duplicate=True)

    lead = await repo.add(
        **lead_in.model_dump(exclude={"website", "page_url"}, mode="json"),
        page_url=lead_in.page_url or request.headers.get("referer"),
        ip=client_ip(request),
    )
    # сохраняем до отправки: если Telegram недоступен, заявку дошлёт фоновая задача
    await delivery.deliver(lead)
    return LeadCreated(id=lead.id)


@router.get(
    "/leads", response_model=LeadPage, dependencies=[Depends(require_api_key)], summary="Список заявок"
)
async def list_leads(
    repo: Annotated[LeadRepository, Depends(get_repo)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> LeadPage:
    items, total = await repo.find_page(limit, offset, search)
    return LeadPage(items=[LeadOut.model_validate(i) for i in items], total=total, limit=limit, offset=offset)


@router.get("/leads/export.csv", dependencies=[Depends(require_api_key)], summary="Выгрузка в CSV для Excel")
async def export_csv(
    repo: Annotated[LeadRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    filename = f"leads_{datetime.now(settings.tz):%Y-%m-%d}.csv"
    return Response(
        leads_to_csv(await repo.all(), settings.tz),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/stats", dependencies=[Depends(require_api_key)], summary="Статистика")
async def stats(repo: Annotated[LeadRepository, Depends(get_repo)]) -> dict[str, Any]:
    return await repo.stats()
