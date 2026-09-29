from datetime import date
from decimal import Decimal

from sqlalchemy import case, func,select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.batch import Batch, BatchStatus
from app.infrastructure.database.models.movement import Movement, MovementType


class BatchRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, batch_id: int) -> Batch | None:
        result = await self.session.execute(
            select(Batch).where(Batch.id == batch_id)
        )
        return result.scalar_one_or_none()

    async def get_available_batches(
        self,
        product_id: int,
        location_id: int,
    ) -> list[Batch]:
        result = await self.session.execute(
            select(Batch).where(
                Batch.product_id == product_id,
                Batch.location_id == location_id,
                Batch.status == "received",
            )
        )
        return list(result.scalars().all())

    async def get_ordered_batches(
        self,
        product_id: int,
        location_id: int,
    ) -> list[Batch]:
        result = await self.session.execute(
            select(Batch).where(
                Batch.product_id == product_id,
                Batch.location_id == location_id,
                Batch.status == "ordered",
            )
        )
        return list(result.scalars().all())

    async def get_expired_batches(
        self,
        product_id: int,
        location_id: int,
        today: date,
    ) -> list[Batch]:
        result = await self.session.execute(
            select(Batch).where(
                Batch.product_id == product_id,
                Batch.location_id == location_id,
                Batch.status == BatchStatus.RECEIVED,
                Batch.expiry_date.is_not(None),
                Batch.expiry_date < today,
            )
        )

        return list(result.scalars().all())

    async def add(self, batch: Batch) -> Batch:
        self.session.add(batch)
        await self.session.flush()
        return batch

    async def get_batches_with_stock(
        self,
        product_id: int,
        location_id: int,
    ) -> list:
        delta = case(
            (Movement.operation_type == MovementType.RECEIPT, Movement.quantity),
            (Movement.operation_type == MovementType.RETURN, Movement.quantity),
            (Movement.operation_type == MovementType.CONSUME, -Movement.quantity),
            (Movement.operation_type == MovementType.WRITEOFF, -Movement.quantity),
            (Movement.operation_type == MovementType.CORRECTION, Movement.quantity),
            else_=0,
        )

        stock = func.coalesce(
            func.sum(delta),
            Decimal("0"),
        ).label("stock")

        result = await self.session.execute(
            select(Batch, stock)
            .outerjoin(
                Movement,
                Movement.batch_id == Batch.id,
            )
            .where(
                Batch.product_id == product_id,
                Batch.location_id == location_id,
                Batch.status == BatchStatus.RECEIVED,
            )
            .group_by(Batch.id)
            .having(stock > 0)
            .order_by(
                Batch.expiry_date.asc().nulls_last(),
                Batch.id,
            )
        )

        return list(result.all())