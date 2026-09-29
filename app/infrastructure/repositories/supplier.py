from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.supplier import Supplier


class SupplierRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, supplier_id: int) -> Supplier | None:
        result = await self.session.execute(
            select(Supplier).where(Supplier.id == supplier_id)
        )
        return result.scalar_one_or_none()