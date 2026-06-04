import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_settings import SystemSettings


class SystemSettingsRepository:
    async def get_all(self, session: AsyncSession) -> dict[str, str]:
        result = await session.execute(select(SystemSettings))
        return {row.key: row.value for row in result.scalars().all()}

    async def get_one(self, session: AsyncSession, key: str) -> str | None:
        row = await session.get(SystemSettings, key)
        return row.value if row is not None else None

    async def bulk_upsert(self, session: AsyncSession, updates: dict[str, str]) -> None:
        for key, value in updates.items():
            stmt = pg_insert(SystemSettings).values(key=key, value=value)
            stmt = stmt.on_conflict_do_update(
                index_elements=["key"],
                set_={"value": stmt.excluded.value, "updated_at": sa.func.now()},
            )
            await session.execute(stmt)
