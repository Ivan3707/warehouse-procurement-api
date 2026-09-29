from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.models.location import Location
from app.infrastructure.database.models.product import Product
from app.infrastructure.unit_of_work import UnitOfWork
from app.services.movement import MovementService
from app.services.stock import StockService


async def create_product_and_location(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[int, int]:
    async with session_factory() as session:
        product = Product(
            sku="TEST-STOCK",
            name="Test Stock Product",
            unit="kg",
            package_size=Decimal("10"),
            min_order_qty=Decimal("10"),
            active=True,
        )

        location = Location(
            code="TEST-STOCK-WH",
            name="Test Stock Warehouse",
            active=True,
        )

        session.add_all([product, location])
        await session.commit()

        return product.id, location.id


@pytest.mark.asyncio
async def test_get_stock_returns_stock_and_stock_days(
    session_factory: async_sessionmaker[AsyncSession],
):
    product_id, location_id = await create_product_and_location(
        session_factory
    )

    movement_service = MovementService(UnitOfWork(session_factory))

    async with movement_service.uow:
        await movement_service.create_receipt(
            product_id=product_id,
            location_id=location_id,
            batch_number="BATCH-STOCK",
            quantity=Decimal("100"),
            expiry_date=date(2026, 12, 1),
            unit_price=Decimal("100"),
            invoice_number="INV-STOCK",
            document_number="DOC-STOCK-RECEIPT",
        )

    async with movement_service.uow:
        await movement_service.consume(
            product_id=product_id,
            location_id=location_id,
            quantity=Decimal("30"),
            operation_date=datetime(
                2026,
                9,
                29,
                tzinfo=timezone.utc,
            ),
            document_number="DOC-STOCK-CONSUME",
        )

    service = StockService(UnitOfWork(session_factory))

    async with service.uow:
        result = await service.get_stock(
            product_id=product_id,
            location_id=location_id,
            today=date(2026, 9, 29),
        )

    assert result.stock == Decimal("70")
    assert result.average_daily_consumption == Decimal("30") / Decimal("90")
    assert result.stock_days == Decimal("70") / (
        Decimal("30") / Decimal("90")
    )


@pytest.mark.asyncio
async def test_get_stock_returns_nearest_unexpired_batch(
    session_factory: async_sessionmaker[AsyncSession],
):
    product_id, location_id = await create_product_and_location(
        session_factory
    )

    movement_service = MovementService(UnitOfWork(session_factory))

    async with movement_service.uow:
        await movement_service.create_receipt(
            product_id=product_id,
            location_id=location_id,
            batch_number="BATCH-EXPIRED",
            quantity=Decimal("50"),
            expiry_date=date(2026, 9, 28),
            unit_price=Decimal("100"),
            invoice_number="INV-EXPIRED",
            document_number="DOC-EXPIRY-001",
        )

    async with movement_service.uow:
        await movement_service.create_receipt(
            product_id=product_id,
            location_id=location_id,
            batch_number="BATCH-VALID",
            quantity=Decimal("50"),
            expiry_date=date(2026, 10, 5),
            unit_price=Decimal("110"),
            invoice_number="INV-VALID",
            document_number="DOC-EXPIRY-002",
        )

    service = StockService(UnitOfWork(session_factory))

    async with service.uow:
        result = await service.get_stock(
            product_id=product_id,
            location_id=location_id,
            today=date(2026, 9, 29),
        )

    assert result.nearest_expiry == date(2026, 10, 5)


@pytest.mark.asyncio
async def test_get_stock_returns_none_stock_days_without_consumption(
    session_factory: async_sessionmaker[AsyncSession],
):
    product_id, location_id = await create_product_and_location(
        session_factory
    )

    movement_service = MovementService(UnitOfWork(session_factory))

    async with movement_service.uow:
        await movement_service.create_receipt(
            product_id=product_id,
            location_id=location_id,
            batch_number="BATCH-NO-CONSUMPTION",
            quantity=Decimal("50"),
            expiry_date=date(2026, 12, 1),
            unit_price=Decimal("100"),
            invoice_number="INV-NO-CONSUMPTION",
            document_number="DOC-NO-CONSUMPTION",
        )

    service = StockService(UnitOfWork(session_factory))

    async with service.uow:
        result = await service.get_stock(
            product_id=product_id,
            location_id=location_id,
            today=date(2026, 9, 29),
        )

    assert result.stock == Decimal("50")
    assert result.average_daily_consumption == Decimal("0")
    assert result.stock_days is None


@pytest.mark.asyncio
async def test_get_stock_detail_returns_batch_information(
    session_factory: async_sessionmaker[AsyncSession],
):
    product_id, location_id = await create_product_and_location(
        session_factory
    )

    movement_service = MovementService(UnitOfWork(session_factory))

    async with movement_service.uow:
        await movement_service.create_receipt(
            product_id=product_id,
            location_id=location_id,
            batch_number="BATCH-DETAIL",
            quantity=Decimal("80"),
            expiry_date=date(2026, 12, 15),
            unit_price=Decimal("125.50"),
            invoice_number="INV-DETAIL",
            document_number="DOC-DETAIL-001",
        )

    service = StockService(UnitOfWork(session_factory))

    async with service.uow:
        result = await service.get_stock_detail(
            sku="TEST-STOCK",
            today=date(2026, 9, 29),
        )

    assert result.sku == "TEST-STOCK"
    assert result.name == "Test Stock Product"
    assert result.unit == "kg"

    assert len(result.locations) == 1

    location = result.locations[0]

    assert location.location == "TEST-STOCK-WH"
    assert location.stock == Decimal("80")

    assert len(location.batches) == 1

    batch = location.batches[0]

    assert batch.batch_number == "BATCH-DETAIL"
    assert batch.stock == Decimal("80")
    assert batch.expiry_date == date(2026, 12, 15)
    assert batch.unit_price == Decimal("125.50")
    assert batch.invoice_number == "INV-DETAIL"


@pytest.mark.asyncio
async def test_get_stock_rejects_unknown_product(
    session_factory: async_sessionmaker[AsyncSession],
):
    service = StockService(UnitOfWork(session_factory))

    async with service.uow:
        with pytest.raises(ValueError, match="Product not found"):
            await service.get_stock(
                product_id=999999,
                location_id=1,
                today=date(2026, 9, 29),
            )


@pytest.mark.asyncio
async def test_get_stock_rejects_unknown_location(
    session_factory: async_sessionmaker[AsyncSession],
):
    product_id, _ = await create_product_and_location(
        session_factory
    )

    service = StockService(UnitOfWork(session_factory))

    async with service.uow:
        with pytest.raises(ValueError, match="Location not found"):
            await service.get_stock(
                product_id=product_id,
                location_id=999999,
                today=date(2026, 9, 29),
            )