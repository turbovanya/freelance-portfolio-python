from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(16), index=True)
    email: Mapped[str | None] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(80), default="website")
    page_url: Mapped[str | None] = mapped_column(String(500))
    utm_source: Mapped[str | None] = mapped_column(String(100))
    utm_medium: Mapped[str | None] = mapped_column(String(100))
    utm_campaign: Mapped[str | None] = mapped_column(String(100))
    ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notify_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(300))
    # SQLite не умеет регистронезависимый поиск по кириллице,
    # поэтому храним отдельный текст для поиска в нижнем регистре
    search_text: Mapped[str] = mapped_column(Text, default="")

    @property
    def notified(self) -> bool:
        return self.notified_at is not None

    def local_time(self, tz: Any) -> datetime:
        created = self.created_at if self.created_at.tzinfo else self.created_at.replace(tzinfo=UTC)
        return created.astimezone(tz)


def create_engine(url: str) -> AsyncEngine:
    if url.startswith("sqlite") and ":memory:" not in url:
        Path(url.split("///", 1)[1]).parent.mkdir(parents=True, exist_ok=True)
    if ":memory:" in url:
        return create_async_engine(url, poolclass=StaticPool, connect_args={"check_same_thread": False})
    return create_async_engine(url, pool_pre_ping=True)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


class LeadRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def add(self, **fields: Any) -> Lead:
        parts = (fields.get(k) for k in ("name", "phone", "email", "message", "source"))
        fields["search_text"] = " ".join(p for p in parts if p).lower()
        async with self._sessions() as session, session.begin():
            lead = Lead(**fields)
            session.add(lead)
        return lead

    async def get(self, lead_id: int) -> Lead | None:
        async with self._sessions() as session:
            return await session.get(Lead, lead_id)

    async def mark_notified(self, lead_id: int) -> None:
        async with self._sessions() as session, session.begin():
            lead = await session.get(Lead, lead_id)
            if lead:
                lead.notified_at = utcnow()
                lead.notify_attempts += 1
                lead.last_error = None

    async def mark_failed(self, lead_id: int, error: str) -> None:
        async with self._sessions() as session, session.begin():
            lead = await session.get(Lead, lead_id)
            if lead:
                lead.notify_attempts += 1
                lead.last_error = error[:300]

    async def pending(self, limit: int = 50) -> list[Lead]:
        async with self._sessions() as session:
            query = select(Lead).where(Lead.notified_at.is_(None)).order_by(Lead.id).limit(limit)
            return list((await session.scalars(query)).all())

    async def find_page(
        self, limit: int = 50, offset: int = 0, search: str | None = None
    ) -> tuple[list[Lead], int]:
        async with self._sessions() as session:
            query = select(Lead)
            if search:
                query = query.where(Lead.search_text.contains(search.lower(), autoescape=True))
            total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
            rows = await session.scalars(query.order_by(Lead.id.desc()).limit(limit).offset(offset))
            return list(rows.all()), total

    async def all(self) -> list[Lead]:
        async with self._sessions() as session:
            return list((await session.scalars(select(Lead).order_by(Lead.id))).all())

    async def is_duplicate(self, phone: str, within: timedelta = timedelta(minutes=10)) -> bool:
        """Один и тот же телефон за 10 минут: обычно двойной клик по кнопке «Отправить»."""
        async with self._sessions() as session:
            query = select(func.count(Lead.id)).where(
                Lead.phone == phone, Lead.created_at >= utcnow() - within
            )
            return (await session.execute(query)).scalar_one() > 0

    async def stats(self) -> dict[str, Any]:
        now = utcnow()
        async with self._sessions() as session:

            async def count(*where: Any) -> int:
                return (await session.execute(select(func.count(Lead.id)).where(*where))).scalar_one()

            sources = (
                await session.execute(
                    select(Lead.source, func.count(Lead.id))
                    .group_by(Lead.source)
                    .order_by(func.count(Lead.id).desc())
                    .limit(6)
                )
            ).all()
            return {
                "total": await count(),
                "today": await count(Lead.created_at >= now - timedelta(days=1)),
                "week": await count(Lead.created_at >= now - timedelta(days=7)),
                "pending": await count(Lead.notified_at.is_(None)),
                "sources": [{"source": s, "count": c} for s, c in sources],
            }
