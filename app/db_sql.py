from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, update, desc, and_
from app.config import settings
from app.models import Base, ScanRun, Lead, TargetInstitution
from datetime import datetime
import uuid


# Convert sync sqlite:// URLs to async sqlite+aiosqlite://
def _normalize_url(url: str) -> str:
    if url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


_engine = create_async_engine(
    _normalize_url(settings.database_url),
    echo=False,
)

_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def init_db():
    """Create tables if they don't exist (used as fallback; Alembic is preferred)."""
    from sqlalchemy import text
    async with _engine.begin() as conn:
        # WAL mode allows concurrent reads during writes — essential for SQLite
        if settings.database_url.startswith("sqlite"):
            await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.run_sync(Base.metadata.create_all)


def _row_to_dict(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


class SQLRepository:
    """SQLAlchemy-based repository (SQLite for dev, PostgreSQL for production)."""

    # ── ScanRun ───────────────────────────────────────────────────────────────

    async def create_scan_run(self, scan_run: dict) -> dict:
        scan_run.setdefault("id", str(uuid.uuid4()))
        scan_run.setdefault("started_at", datetime.utcnow())
        scan_run.setdefault("status", "running")
        scan_run.setdefault("total_found", 0)
        scan_run.setdefault("active_count", 0)
        obj = ScanRun(**scan_run)
        async with _session_factory() as session:
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return _row_to_dict(obj)

    async def update_scan_run(self, scan_id: str, updates: dict) -> dict:
        async with _session_factory() as session:
            await session.execute(
                update(ScanRun).where(ScanRun.id == scan_id).values(**updates)
            )
            await session.commit()
            result = await session.execute(select(ScanRun).where(ScanRun.id == scan_id))
            obj = result.scalar_one()
            return _row_to_dict(obj)

    async def get_scan_run(self, scan_id: str) -> dict | None:
        async with _session_factory() as session:
            result = await session.execute(select(ScanRun).where(ScanRun.id == scan_id))
            obj = result.scalar_one_or_none()
            return _row_to_dict(obj) if obj else None

    async def list_scan_runs(self, limit: int = 20) -> list[dict]:
        async with _session_factory() as session:
            result = await session.execute(
                select(ScanRun).order_by(desc(ScanRun.started_at)).limit(limit)
            )
            return [_row_to_dict(r) for r in result.scalars()]

    # ── Leads ──────────────────────────────────────────────────────────────────

    async def create_lead(self, lead: dict) -> dict:
        lead.setdefault("id", str(uuid.uuid4()))
        lead.setdefault("first_seen_at", datetime.utcnow())
        lead.setdefault("lead_status", "new")
        obj = Lead(**lead)
        async with _session_factory() as session:
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return _row_to_dict(obj)

    async def create_leads_batch(self, leads: list[dict]) -> list[dict]:
        now = datetime.utcnow()
        objs = []
        for lead in leads:
            lead.setdefault("id", str(uuid.uuid4()))
            lead.setdefault("first_seen_at", now)
            lead.setdefault("lead_status", "new")
            objs.append(Lead(**lead))
        async with _session_factory() as session:
            session.add_all(objs)
            await session.commit()
            return [_row_to_dict(o) for o in objs]

    async def get_lead(self, lead_id: str) -> dict | None:
        async with _session_factory() as session:
            result = await session.execute(select(Lead).where(Lead.id == lead_id))
            obj = result.scalar_one_or_none()
            return _row_to_dict(obj) if obj else None

    async def update_lead(self, lead_id: str, updates: dict) -> dict:
        async with _session_factory() as session:
            await session.execute(
                update(Lead).where(Lead.id == lead_id).values(**updates)
            )
            await session.commit()
            result = await session.execute(select(Lead).where(Lead.id == lead_id))
            obj = result.scalar_one()
            return _row_to_dict(obj)

    async def list_leads(
        self,
        filters: dict,
        sort_by: str = "relevance_score",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        async with _session_factory() as session:
            query = select(Lead)
            conditions = []

            freshness = filters.get("freshness")
            if freshness == "actionable":
                conditions.append(Lead.freshness.in_(["active", "stale"]))
            elif freshness:
                conditions.append(Lead.freshness == freshness)

            if filters.get("type"):
                conditions.append(Lead.type == filters["type"])

            if filters.get("country"):
                conditions.append(Lead.country == filters["country"])

            if filters.get("scan_run_id"):
                conditions.append(Lead.scan_run_id == filters["scan_run_id"])

            min_score = filters.get("min_score", 0)
            if min_score:
                conditions.append(Lead.relevance_score >= min_score)

            if conditions:
                query = query.where(and_(*conditions))

            sort_col = {
                "relevance_score": desc(Lead.relevance_score),
                "urgency": Lead.urgency,
                "freshness": Lead.freshness,
                "first_seen_at": desc(Lead.first_seen_at),
            }.get(sort_by, desc(Lead.relevance_score))

            query = query.order_by(sort_col).offset(offset).limit(limit)
            result = await session.execute(query)
            return [_row_to_dict(r) for r in result.scalars()]

    # ── Target Institutions ────────────────────────────────────────────────────

    async def create_targets_batch(self, targets: list[dict]) -> list[dict]:
        now = datetime.utcnow()
        objs = []
        for target in targets:
            target.setdefault("id", str(uuid.uuid4()))
            target.setdefault("discovered_at", now)
            objs.append(TargetInstitution(**{
                k: v for k, v in target.items()
                if hasattr(TargetInstitution, k)
            }))
        async with _session_factory() as session:
            session.add_all(objs)
            await session.commit()
            return [_row_to_dict(o) for o in objs]

    async def get_targets_for_lead(self, lead_id: str) -> list[dict]:
        async with _session_factory() as session:
            result = await session.execute(
                select(TargetInstitution).where(TargetInstitution.lead_id == lead_id)
            )
            return [_row_to_dict(r) for r in result.scalars()]

    async def update_target(self, target_id: str, updates: dict) -> dict:
        async with _session_factory() as session:
            await session.execute(
                update(TargetInstitution).where(TargetInstitution.id == target_id).values(**updates)
            )
            await session.commit()
            result = await session.execute(select(TargetInstitution).where(TargetInstitution.id == target_id))
            return _row_to_dict(result.scalar_one())

    async def list_targets(self, tier: str | None = None, country: str | None = None) -> list[dict]:
        async with _session_factory() as session:
            query = select(TargetInstitution)
            conditions = []
            if tier:
                conditions.append(TargetInstitution.market_tier == tier)
            if country:
                conditions.append(TargetInstitution.country == country)
            if conditions:
                query = query.where(and_(*conditions))
            query = query.order_by(TargetInstitution.market_tier, TargetInstitution.country)
            result = await session.execute(query)
            return [_row_to_dict(r) for r in result.scalars()]

    async def get_existing_lead_titles(self, limit: int = 500) -> list[str]:
        async with _session_factory() as session:
            result = await session.execute(
                select(Lead.title)
                .order_by(desc(Lead.first_seen_at))
                .limit(limit)
            )
            return [row[0] for row in result if row[0]]
