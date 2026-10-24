"""Панель менеджера: заявки, статистика, выгрузка. Вход по логину и паролю."""

from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from .api import get_delivery, get_repo
from .config import Settings
from .db import LeadRepository
from .security import get_settings, require_admin
from .services import Delivery, leads_to_csv

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
router = APIRouter(prefix="/admin", include_in_schema=False, dependencies=[Depends(require_admin)])

PAGE_SIZE = 25


@router.get("", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    repo: Annotated[LeadRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> HTMLResponse:
    leads, total = await repo.find_page(PAGE_SIZE, (page - 1) * PAGE_SIZE, q or None)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "leads": leads,
            "total": total,
            "stats": await repo.stats(),
            "q": q or "",
            "page": page,
            "pages": max(1, -(-total // PAGE_SIZE)),
            "tz": settings.tz,
            "telegram": request.app.state.delivery.notifier.enabled,
            "now": datetime.now(settings.tz),
        },
    )


@router.post("/resend")
async def resend(delivery: Annotated[Delivery, Depends(get_delivery)]) -> RedirectResponse:
    await delivery.resend_pending()
    return RedirectResponse("/admin", status_code=303)


@router.get("/export.csv")
async def export(
    repo: Annotated[LeadRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    filename = f"leads_{datetime.now(settings.tz):%Y-%m-%d}.csv"
    return Response(
        leads_to_csv(await repo.all(), settings.tz),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
