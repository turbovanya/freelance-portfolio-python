"""Модель заявки и работа с базой. По умолчанию SQLite, для продакшена можно указать PostgreSQL."""

import enum
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import BigInteger, DateTime, Enum, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool


class LeadStatus(enum.StrEnum):
    NEW = "new"
    IN_WORK = "in_work"
    DONE = "done"
    REJECTED = "rejected"

    @property
    def label(self) -> str:
        return {
            LeadStatus.NEW: "🆕 Новая",
            LeadStatus.IN_WORK: "🔧 В работе",
            LeadStatus.DONE: "✅ Выполнена",
            LeadStatus.REJECTED: "🚫 Отклонена",
        }[self]


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(50))
    phone: Mapped[str] = mapped_column(String(16))
    comment: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus, native_enum=False), default=LeadStatus.NEW)
    manager_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def created_local(self, tz: object) -> datetime:
        created = self.created_at if self.created_at.tzinfo else self.created_at.replace(tzinfo=UTC)
        return created.astimezone(tz)  # type: ignore[arg-type]


def create_engine(url: str) -> AsyncEngine:
    if url.startswith("sqlite") and ":memory:" not in url:
        Path(url.split("///", 1)[1]).parent.mkdir(parents=True, exist_ok=True)
    if ":memory:" in url:
        # одно соединение на всё время жизни, иначе у каждого запроса будет своя пустая база
        return create_async_engine(url, poolclass=StaticPool, connect_args={"check_same_thread": False})
    return create_async_engine(url, pool_pre_ping=True)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


class LeadRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def add(self, *, user_id: int, username: str | None, name: str, phone: str, comment: str) -> Lead:
        async with self._sessions() as session, session.begin():
            lead = Lead(user_id=user_id, username=username, name=name, phone=phone, comment=comment)
            session.add(lead)
        return lead

    async def get(self, lead_id: int) -> Lead | None:
        async with self._sessions() as session:
            return await session.get(Lead, lead_id)

    async def set_status(self, lead_id: int, status: LeadStatus, manager_id: int) -> Lead | None:
        async with self._sessions() as session, session.begin():
            lead = await session.get(Lead, lead_id)
            if lead is None:
                return None
            lead.status, lead.manager_id = status, manager_id
        return lead

    async def count_by_user_since(self, user_id: int, since: datetime) -> int:
        async with self._sessions() as session:
            query = select(func.count(Lead.id)).where(Lead.user_id == user_id, Lead.created_at >= since)
            return (await session.execute(query)).scalar_one()

    async def recent(self, limit: int = 10, status: LeadStatus | None = None) -> list[Lead]:
        async with self._sessions() as session:
            query = select(Lead).order_by(Lead.id.desc()).limit(limit)
            if status is not None:
                query = query.where(Lead.status == status)
            return list((await session.scalars(query)).all())

    async def all(self) -> list[Lead]:
        async with self._sessions() as session:
            return list((await session.scalars(select(Lead).order_by(Lead.id))).all())

    async def stats(self, now: datetime | None = None) -> dict[str, int]:
        now = now or utcnow()
        async with self._sessions() as session:
            by_status = dict(
                (await session.execute(select(Lead.status, func.count(Lead.id)).group_by(Lead.status))).all()
            )
            last_day = (
                await session.execute(
                    select(func.count(Lead.id)).where(Lead.created_at >= now - timedelta(days=1))
                )
            ).scalar_one()
            last_week = (
                await session.execute(
                    select(func.count(Lead.id)).where(Lead.created_at >= now - timedelta(days=7))
                )
            ).scalar_one()
        result = {status.value: by_status.get(status, 0) for status in LeadStatus}
        result.update(total=sum(by_status.values()), last_day=last_day, last_week=last_week)
        return result
