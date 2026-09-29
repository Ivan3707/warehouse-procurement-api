from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.location import Location


class LocationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, location_id: int) -> Location | None:
        result = await self.session.execute(
            select(Location).where(Location.id == location_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Location | None:
        result = await self.session.execute(
            select(Location).where(Location.code == code)
        )
        return result.scalar_one_or_none()

    async def list(self) -> list[Location]:
        result = await self.session.execute(
            select(Location).where(Location.active.is_(True))
        )
        return list(result.scalars().all())