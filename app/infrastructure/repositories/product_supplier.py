from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.product_supplier import ProductSupplier


class ProductSupplierRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_for_product(
        self,
        product_id: int,
    ) -> list[ProductSupplier]:
        result = await self.session.execute(
            select(ProductSupplier).where(
                ProductSupplier.product_id == product_id
            )
        )
        return list(result.scalars().all())