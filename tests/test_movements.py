from datetime import date, datetime, timezone
from decimal import Decimal
from app.infrastructure.repositories.movement import MovementRepository
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.models.location import Location
from app.infrastructure.database.models.product import Product
from app.infrastructure.unit_of_work import UnitOfWork
from app.services.movement import MovementService


async def create_product_and_location(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[int, int]:
    async with session_factory() as session:
        product = Product(
            sku="TEST-MILK",
            name="Test Milk",
            unit="l",
            package_size=Decimal("10"),
            min_order_qty=Decimal("10"),
            active=True,
        )

        location = Location(
            code="TEST-WH",
            name="Test Warehouse",
            active=True,
        )

        session.add_all([product, location])
        await session.commit()

        return product.id, location.id


@pytest.mark.asyncio
async def test_consume_uses_fefo(
    session_factory: async_sessionmaker[AsyncSession],
):
    product_id, location_id = await create_product_and_location(
        session_factory
    )

    receipt_service = MovementService(
        UnitOfWork(session_factory)
    )

    async with receipt_service.uow:
        await receipt_service.create_receipt(
            product_id=product_id,
            location_id=location_id,
            batch_number="BATCH-OLD",
            quantity=Decimal("100"),
            expiry_date=date(2026, 10, 1),
            unit_price=Decimal("100"),
            invoice_number="INV-OLD",
            document_number="DOC-RECEIPT-OLD",
        )

    async with receipt_service.uow:
        await receipt_service.create_receipt(
            product_id=product_id,
            location_id=location_id,
            batch_number="BATCH-NEW",
            quantity=Decimal("100"),
            expiry_date=date(2026, 11, 1),
            unit_price=Decimal("110"),
            invoice_number="INV-NEW",
            document_number="DOC-RECEIPT-NEW",
        )

    consume_service = MovementService(
        UnitOfWork(session_factory)
    )

    async with consume_service.uow:
        movements = await consume_service.consume(
            product_id=product_id,
            location_id=location_id,
            quantity=Decimal("120"),
            operation_date=datetime(
                2026,
                9,
                29,
                tzinfo=timezone.utc,
            ),
            document_number="DOC-CONSUME-001",
        )

    assert len(movements) == 2

    assert movements[0].quantity == Decimal("100")
    assert movements[1].quantity == Decimal("20")

    assert movements[0].batch_id != movements[1].batch_id


@pytest.mark.asyncio
async def test_consume_rejects_quantity_greater_than_stock(
    session_factory: async_sessionmaker[AsyncSession],
):
    product_id, location_id = await create_product_and_location(
        session_factory
    )

    service = MovementService(
        UnitOfWork(session_factory)
    )

    async with service.uow:
        await service.create_receipt(
            product_id=product_id,
            location_id=location_id,
            batch_number="BATCH-ONLY",
            quantity=Decimal("50"),
            expiry_date=date(2026, 12, 1),
            unit_price=Decimal("100"),
            invoice_number="INV-ONLY",
            document_number="DOC-RECEIPT-ONLY",
        )

    async with service.uow:
        with pytest.raises(
            ValueError,
            match="Insufficient stock",
        ):
            await service.consume(
                product_id=product_id,
                location_id=location_id,
                quantity=Decimal("51"),
                operation_date=datetime(
                    2026,
                    9,
                    29,
                    tzinfo=timezone.utc,
                ),
                document_number="DOC-CONSUME-OVERSTOCK",
            )

@pytest.mark.asyncio
async def test_stock_is_calculated_from_movements(
    session_factory: async_sessionmaker[AsyncSession],
):
    product_id, location_id = await create_product_and_location(
        session_factory
    )

    service = MovementService(UnitOfWork(session_factory))

    async with service.uow:
        await service.create_receipt(
            product_id=product_id,
            location_id=location_id,
            batch_number="BATCH-STOCK",
            quantity=Decimal("100"),
            expiry_date=date(2026, 12, 1),
            unit_price=Decimal("100"),
            invoice_number="INV-STOCK",
            document_number="DOC-RECEIPT-STOCK",
        )

    async with service.uow:
        await service.consume(
            product_id=product_id,
            location_id=location_id,
            quantity=Decimal("30"),
            operation_date=datetime(
                2026, 9, 29, tzinfo=timezone.utc
            ),
            document_number="DOC-CONSUME-STOCK",
        )

    async with session_factory() as session:
        repository = MovementRepository(session)

        stock = await repository.get_stock(
            product_id=product_id,
            location_id=location_id,
        )

    assert stock == Decimal("70")

@pytest.mark.asyncio
async def test_consume_does_not_use_expired_batch(
    session_factory: async_sessionmaker[AsyncSession],
):
    product_id, location_id = await create_product_and_location(
        session_factory
    )

    service = MovementService(UnitOfWork(session_factory))

    async with service.uow:
        await service.create_receipt(
            product_id=product_id,
            location_id=location_id,
            batch_number="BATCH-EXPIRED",
            quantity=Decimal("100"),
            expiry_date=date(2026, 9, 28),
            unit_price=Decimal("100"),
            invoice_number="INV-EXPIRED",
            document_number="DOC-RECEIPT-EXPIRED",
        )

    async with service.uow:
        with pytest.raises(ValueError, match="Insufficient stock"):
            await service.consume(
                product_id=product_id,
                location_id=location_id,
                quantity=Decimal("1"),
                operation_date=datetime(
                    2026, 9, 29, tzinfo=timezone.utc
                ),
                document_number="DOC-CONSUME-EXPIRED",
            )