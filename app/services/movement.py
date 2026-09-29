from decimal import Decimal
from datetime import date, datetime

from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.batch import Batch, BatchStatus
from app.infrastructure.database.models.movement import Movement, MovementType
from app.infrastructure.unit_of_work import UnitOfWork

from dataclasses import dataclass


@dataclass
class MovementResult:
    movement_id: int
    stock: Decimal

class MovementService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def writeoff_expired(
        self,
        *,
        product_id: int,
        location_id: int,
        operation_date: datetime,
        document_number: str,
    ) -> list[Movement]:
        batches = await self.uow.batches.get_expired_batches(
            product_id=product_id,
            location_id=location_id,
            today=operation_date.date(),
        )

        if await self.uow.movements.exists_by_document_number(
            document_number
        ):
            raise ValueError("Document number already exists")

        movements = []

        for batch in batches:
            stock = await self.uow.movements.get_batch_stock(batch.id)

            if stock <= 0:
                continue

            movement = Movement(
                operation_date=operation_date,
                product_id=product_id,
                location_id=location_id,
                batch_id=batch.id,
                operation_type=MovementType.WRITEOFF,
                quantity=stock,
                document_number=document_number,
            )

            await self.uow.movements.add(movement)
            movements.append(movement)

        return movements
    async def create_receipt(
        self,
        *,
        product_id: int,
        location_id: int,
        batch_number: str,
        quantity: Decimal,
        expiry_date: date | None,
        unit_price: Decimal,
        invoice_number: str | None,
        document_number: str,
        operation_date: datetime | None = None,
    ) -> MovementResult:
        product = await self.uow.products.get_by_id(product_id)
        if product is None:
            raise ValueError("Product not found")

        location = await self.uow.locations.get_by_id(location_id)
        if location is None:
            raise ValueError("Location not found")

        if quantity <= 0:
            raise ValueError("Receipt quantity must be greater than zero")

        if await self.uow.movements.exists_by_document_number(
            document_number
        ):
            raise ValueError("Document number already exists")
        
        if operation_date is None:
            operation_date = utc_now()

        batch = Batch(
            product_id=product_id,
            location_id=location_id,
            batch_number=batch_number,
            status=BatchStatus.RECEIVED,
            expiry_date=expiry_date,
            received_at=operation_date.date(),
            unit_price=unit_price,
            invoice_number=invoice_number,
            ordered_quantity=quantity,
        )

        await self.uow.batches.add(batch)

        movement = Movement(
            operation_date=operation_date,
            product_id=product_id,
            location_id=location_id,
            batch_id=batch.id,
            operation_type=MovementType.RECEIPT,
            quantity=quantity,
            document_number=document_number,
        )

        await self.uow.movements.add(movement)

        stock = await self.uow.movements.get_stock(
            product_id=product_id,
            location_id=location_id,
        )

        return MovementResult(
            movement_id=movement.id,
            stock=stock,
        )

    async def consume(
        self,
        *,
        product_id: int,
        location_id: int,
        quantity: Decimal,
        operation_date: datetime,
        document_number: str,
    ) -> list[Movement]:
        product = await self.uow.products.get_by_id(product_id)
        if product is None:
            raise ValueError("Product not found")

        location = await self.uow.locations.get_by_id(location_id)
        if location is None:
            raise ValueError("Location not found")

        if quantity <= 0:
            raise ValueError("Consume quantity must be greater than zero")

        if await self.uow.movements.exists_by_document_number(
            document_number
        ):
            raise ValueError("Document number already exists")

        available_batches = (
            await self.uow.movements.get_available_batches_with_stock(
                product_id=product_id,
                location_id=location_id,
                today=operation_date.date(),
            )
        )

        available_stock = sum(
            stock for _, stock in available_batches
        )

        if quantity > available_stock:
            raise ValueError(
                f"Insufficient stock: available {available_stock}"
            )

        remaining = quantity
        movements = []

        for batch, stock in available_batches:
            if remaining <= 0:
                break

            consume_quantity = min(remaining, stock)

            movement = Movement(
                operation_date=operation_date,
                product_id=product_id,
                location_id=location_id,
                batch_id=batch.id,
                operation_type=MovementType.CONSUME,
                quantity=consume_quantity,
                document_number=document_number,
            )

            await self.uow.movements.add(movement)
            movements.append(movement)

            remaining -= consume_quantity

        return movements

    async def create_return(
        self,
        *,
        product_id: int,
        location_id: int,
        batch_id: int,
        quantity: Decimal,
        operation_date: datetime,
        document_number: str,
    ) -> Movement:
        product = await self.uow.products.get_by_id(product_id)
        if product is None:
            raise ValueError("Product not found")

        location = await self.uow.locations.get_by_id(location_id)
        if location is None:
            raise ValueError("Location not found")

        if quantity <= 0:
            raise ValueError("Return quantity must be greater than zero")

        if await self.uow.movements.exists_by_document_number(
            document_number
        ):
            raise ValueError("Document number already exists")

        batch = await self.uow.batches.get_by_id(batch_id)
        if batch is None:
            raise ValueError("Batch not found")

        if (
            batch.product_id != product_id
            or batch.location_id != location_id
        ):
            raise ValueError("Batch does not belong to product and location")

        movement = Movement(
            operation_date=operation_date,
            product_id=product_id,
            location_id=location_id,
            batch_id=batch_id,
            operation_type=MovementType.RETURN,
            quantity=quantity,
            document_number=document_number,
        )

        await self.uow.movements.add(movement)

        return movement

    async def create_correction(
        self,
        *,
        product_id: int,
        location_id: int,
        batch_id: int | None,
        quantity: Decimal,
        operation_date: datetime,
        document_number: str,
    ) -> Movement:
        product = await self.uow.products.get_by_id(product_id)
        if product is None:
            raise ValueError("Product not found")

        location = await self.uow.locations.get_by_id(location_id)
        if location is None:
            raise ValueError("Location not found")

        if quantity == 0:
            raise ValueError("Correction quantity cannot be zero")

        if await self.uow.movements.exists_by_document_number(document_number):
            raise ValueError("Document number already exists")

        if batch_id is not None:
            batch = await self.uow.batches.get_by_id(batch_id)

            if batch is None:
                raise ValueError("Batch not found")

            if (
                batch.product_id != product_id
                or batch.location_id != location_id
            ):
                raise ValueError(
                    "Batch does not belong to product and location"
                )

        if quantity < 0:
            if batch_id is not None:
                available_stock = await self.uow.movements.get_batch_stock(
                    batch_id
                )
            else:
                available_stock = await self.uow.movements.get_stock(
                    product_id,
                    location_id,
                )

            if -quantity > available_stock:
                raise ValueError(
                    f"Insufficient stock: available {available_stock}"
                )

        movement = Movement(
            operation_date=operation_date,
            product_id=product_id,
            location_id=location_id,
            batch_id=batch_id,
            operation_type=MovementType.CORRECTION,
            quantity=quantity,
            document_number=document_number,
        )

        await self.uow.movements.add(movement)

        return movement