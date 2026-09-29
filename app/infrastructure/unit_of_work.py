from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.repositories.batch import BatchRepository
from app.infrastructure.repositories.location import LocationRepository
from app.infrastructure.repositories.movement import MovementRepository
from app.infrastructure.repositories.product import ProductRepository
from app.infrastructure.repositories.product_supplier import (
    ProductSupplierRepository,
)
from app.infrastructure.repositories.supplier import SupplierRepository


class UnitOfWork:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self.session_factory = session_factory

    async def __aenter__(self):
        self.session = self.session_factory()

        self.products = ProductRepository(self.session)
        self.locations = LocationRepository(self.session)
        self.suppliers = SupplierRepository(self.session)
        self.product_suppliers = ProductSupplierRepository(self.session)
        self.batches = BatchRepository(self.session)
        self.movements = MovementRepository(self.session)

        return self

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

        await self.session.close()

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()