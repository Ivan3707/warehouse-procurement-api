from datetime import date, datetime
from decimal import Decimal
from typing import List, Tuple
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.batch import Batch, BatchStatus
from app.infrastructure.database.models.movement import Movement, MovementType


class MovementRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, movement: Movement) -> Movement:
        self.session.add(movement)
        await self.session.flush()
        return movement

    async def get_by_id(self, movement_id: int) -> Movement | None:
        result = await self.session.execute(
            select(Movement).where(Movement.id == movement_id)
        )
        return result.scalar_one_or_none()

    async def get_stock(
        self,
        product_id: int,
        location_id: int,
    ) -> Decimal:
        delta = case(
            (Movement.operation_type == MovementType.RECEIPT, Movement.quantity),
            (Movement.operation_type == MovementType.RETURN, Movement.quantity),
            (Movement.operation_type == MovementType.CONSUME, -Movement.quantity),
            (Movement.operation_type == MovementType.WRITEOFF, -Movement.quantity),
            (Movement.operation_type == MovementType.CORRECTION, Movement.quantity),
            else_=0,
        )

        result = await self.session.execute(
            select(func.coalesce(func.sum(delta), 0))
            .where(
                Movement.product_id == product_id,
                Movement.location_id == location_id,
            )
        )

        return result.scalar_one()
    async def get_batch_stock(
        self,
        batch_id: int,
    ) -> Decimal:
        delta = case(
            (Movement.operation_type == MovementType.RECEIPT, Movement.quantity),
            (Movement.operation_type == MovementType.RETURN, Movement.quantity),
            (Movement.operation_type == MovementType.CONSUME, -Movement.quantity),
            (Movement.operation_type == MovementType.WRITEOFF, -Movement.quantity),
            (Movement.operation_type == MovementType.CORRECTION, Movement.quantity),
            else_=0,
        )

        result = await self.session.execute(
            select(func.coalesce(func.sum(delta), 0))
            .where(Movement.batch_id == batch_id)
        )

        return result.scalar_one()

    async def list(
        self,
        *,
        product_id: int | None = None,
        location_id: int | None = None,
        operation_type=None,
        date_from=None,
        date_to=None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Movement]:
        query = select(Movement)

        if product_id is not None:
            query = query.where(Movement.product_id == product_id)

        if location_id is not None:
            query = query.where(Movement.location_id == location_id)

        if operation_type is not None:
            query = query.where(Movement.operation_type == operation_type)

        if date_from is not None:
            query = query.where(Movement.operation_date >= date_from)

        if date_to is not None:
            query = query.where(Movement.operation_date <= date_to)

        query = query.order_by(Movement.operation_date.desc())

        if limit is not None:
            query = query.limit(limit)

        if offset:
            query = query.offset(offset)

        result = await self.session.execute(query)

        return list(result.scalars().all())

    async def count(
        self,
        *,
        product_id: int | None = None,
        location_id: int | None = None,
        operation_type=None,
        date_from=None,
        date_to=None,
    ) -> int:
        query = select(func.count(Movement.id))

        if product_id is not None:
            query = query.where(Movement.product_id == product_id)

        if location_id is not None:
            query = query.where(Movement.location_id == location_id)

        if operation_type is not None:
            query = query.where(Movement.operation_type == operation_type)

        if date_from is not None:
            query = query.where(Movement.operation_date >= date_from)

        if date_to is not None:
            query = query.where(Movement.operation_date <= date_to)

        result = await self.session.execute(query)

        return result.scalar_one()

    async def get_available_batches_with_stock(
        self,
        *,
        product_id: int,
        location_id: int,
        today: date,
    ) -> List[Tuple[Batch, Decimal]]:
        delta = case(
            (Movement.operation_type == MovementType.RECEIPT, Movement.quantity),
            (Movement.operation_type == MovementType.RETURN, Movement.quantity),
            (Movement.operation_type == MovementType.CONSUME, -Movement.quantity),
            (Movement.operation_type == MovementType.WRITEOFF, -Movement.quantity),
            (Movement.operation_type == MovementType.CORRECTION, Movement.quantity),
            else_=0,
        )

        stock = func.coalesce(func.sum(delta), 0)

        result = await self.session.execute(
            select(Batch, stock.label("stock"))
            .outerjoin(
                Movement,
                Movement.batch_id == Batch.id,
            )
            .where(
                Batch.product_id == product_id,
                Batch.location_id == location_id,
                Batch.status == BatchStatus.RECEIVED,
                or_(
                    Batch.expiry_date.is_(None),
                    Batch.expiry_date >= today,
                ),
            )
            .group_by(Batch.id)
            .having(stock > 0)
            .order_by(    
                Batch.expiry_date.is_(None),
                Batch.expiry_date.asc()
            )
        )

        return [
            (batch, Decimal(stock))
            for batch, stock in result.all()
        ]

    async def exists_by_document_number(
        self,
        document_number: str,
    ) -> bool:
        result = await self.session.execute(
            select(
                func.count(Movement.id)
            ).where(
                Movement.document_number == document_number
            )
        )
        return result.scalar_one() > 0

    async def get_consumption(
        self,
        product_id: int,
        location_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> Decimal:
        result = await self.session.execute(
            select(
                func.coalesce(
                    func.sum(Movement.quantity),
                    0,
                )
            ).where(
                Movement.product_id == product_id,
                Movement.location_id == location_id,
                Movement.operation_type == MovementType.CONSUME,
                Movement.operation_date >= start_date,
                Movement.operation_date < end_date,
            )
        )

        return result.scalar_one()