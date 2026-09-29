from datetime import date, datetime, timezone
from decimal import Decimal
from app.infrastructure.database.models.movement import Movement, MovementType
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.models.location import Location
from app.infrastructure.database.models.product import Product
from app.infrastructure.database.models.product_supplier import ProductSupplier
from app.infrastructure.database.models.supplier import Supplier
from app.infrastructure.unit_of_work import UnitOfWork
from app.services.alerts import AlertService
from app.services.movement import MovementService


async def create_product_location_and_supplier(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    lead_time_days: int = 5,
) -> tuple[int, int]:
    async with session_factory() as session:
        product = Product(
            sku="TEST-ALERT",
            name="Test Alert Product",
            unit="kg",
            package_size=Decimal("10"),
            min_order_qty=Decimal("10"),
            active=True,
        )

        location = Location(
            code="TEST-ALERT-WH",
            name="Test Alert Warehouse",
            active=True,
        )

        supplier = Supplier(
            name="Test Alert Supplier",
            lead_time_days=lead_time_days,
            active=True,
        )

        session.add_all([product, location, supplier])
        await session.flush()

        product_supplier = ProductSupplier(
            product_id=product.id,
            supplier_id=supplier.id,
            unit_price=Decimal("100"),
            is_primary=True,
        )

        session.add(product_supplier)
        await session.commit()

        return product.id, location.id


@pytest.mark.asyncio
async def test_expiry_alert_is_created_for_soon_expiring_batch(
    session_factory: async_sessionmaker[AsyncSession],
):
    product_id, location_id = await create_product_location_and_supplier(
        session_factory
    )

    movement_service = MovementService(UnitOfWork(session_factory))

    async with movement_service.uow:
        await movement_service.create_receipt(
            product_id=product_id,
            location_id=location_id,
            batch_number="BATCH-EXPIRING",
            quantity=Decimal("50"),
            expiry_date=date(2026, 10, 4),
            unit_price=Decimal("100"),
            invoice_number="INV-EXPIRING",
            document_number="DOC-ALERT-EXPIRY",
        )

    service = AlertService(UnitOfWork(session_factory))

    async with service.uow:
        alerts = await service.get_alerts(
            today=date(2026, 9, 29),
        )

    expiry_alerts = [
        alert
        for alert in alerts
        if alert.alert_type == "approaching_expiry"
    ]

    assert len(expiry_alerts) == 1

    alert = expiry_alerts[0]

    assert alert.severity == "critical"
    assert alert.product_id == product_id
    assert alert.location_id == location_id
    assert alert.stock == Decimal("50")
    assert alert.expiry_date == date(2026, 10, 4)
    assert alert.days_to_expiry == 5


@pytest.mark.asyncio
async def test_expiry_alert_is_warning_when_expiry_is_more_than_seven_days_away(
    session_factory: async_sessionmaker[AsyncSession],
):
    product_id, location_id = await create_product_location_and_supplier(
        session_factory
    )

    movement_service = MovementService(UnitOfWork(session_factory))

    async with movement_service.uow:
        await movement_service.create_receipt(
            product_id=product_id,
            location_id=location_id,
            batch_number="BATCH-EXPIRY-WARNING",
            quantity=Decimal("50"),
            expiry_date=date(2026, 10, 19),
            unit_price=Decimal("100"),
            invoice_number="INV-EXPIRY-WARNING",
            document_number="DOC-ALERT-EXPIRY-WARNING",
        )

    service = AlertService(UnitOfWork(session_factory))

    async with service.uow:
        alerts = await service.get_alerts(
            today=date(2026, 9, 29),
        )

    expiry_alerts = [
        alert
        for alert in alerts
        if alert.alert_type == "approaching_expiry"
    ]

    assert len(expiry_alerts) == 1
    assert expiry_alerts[0].severity == "warning"
    assert expiry_alerts[0].days_to_expiry == 20


@pytest.mark.asyncio
async def test_no_movement_alert_is_created_when_product_has_no_movements(
    session_factory: async_sessionmaker[AsyncSession],
):
    product_id, location_id = await create_product_location_and_supplier(
        session_factory
    )

    service = AlertService(UnitOfWork(session_factory))

    async with service.uow:
        alerts = await service.get_alerts(
            today=date(2026, 9, 29),
        )

    no_movement_alerts = [
        alert
        for alert in alerts
        if alert.alert_type == "no_movement"
    ]

    assert len(no_movement_alerts) == 1

    alert = no_movement_alerts[0]

    assert alert.severity == "warning"
    assert alert.product_id == product_id
    assert alert.location_id == location_id
    assert alert.days_without_movement is None


@pytest.mark.asyncio
async def test_no_movement_alert_is_created_after_threshold(
    session_factory: async_sessionmaker[AsyncSession],
):
    product_id, location_id = await create_product_location_and_supplier(
        session_factory
    )

    async with session_factory() as session:
        session.add(
            Movement(
                operation_date=datetime(
                    2026,
                    8,
                    1,
                    tzinfo=timezone.utc,
                ),
                product_id=product_id,
                location_id=location_id,
                batch_id=None,
                operation_type=MovementType.RECEIPT,
                quantity=Decimal("50"),
                document_number="DOC-OLD-MOVEMENT",
            )
        )
        await session.commit()

    service = AlertService(UnitOfWork(session_factory))

    async with service.uow:
        alerts = await service.get_alerts(
            today=date(2026, 9, 29),
        )

    no_movement_alerts = [
        alert
        for alert in alerts
        if alert.alert_type == "no_movement"
    ]

    assert len(no_movement_alerts) == 1
    assert no_movement_alerts[0].days_without_movement == 59


@pytest.mark.asyncio
async def test_deficit_risk_alert_is_created_when_stock_does_not_cover_lead_time(
    session_factory: async_sessionmaker[AsyncSession],
):
    product_id, location_id = await create_product_location_and_supplier(
        session_factory,
        lead_time_days=5,
    )

    movement_service = MovementService(UnitOfWork(session_factory))

    async with movement_service.uow:
        await movement_service.create_receipt(
            product_id=product_id,
            location_id=location_id,
            batch_number="BATCH-DEFICIT",
            quantity=Decimal("100"),
            expiry_date=date(2027, 1, 1),
            unit_price=Decimal("100"),
            invoice_number="INV-DEFICIT",
            document_number="DOC-DEFICIT-RECEIPT",
        )

    async with movement_service.uow:
        await movement_service.consume(
            product_id=product_id,
            location_id=location_id,
            quantity=Decimal("95"),
            operation_date=datetime(
                2026,
                9,
                29,
                tzinfo=timezone.utc,
            ),
            document_number="DOC-DEFICIT-CONSUME",
        )

    service = AlertService(UnitOfWork(session_factory))

    async with service.uow:
        alerts = await service.get_alerts(
            today=date(2026, 9, 29),
        )

    deficit_alerts = [
        alert
        for alert in alerts
        if alert.alert_type == "deficit_risk"
    ]

    assert len(deficit_alerts) == 1

    alert = deficit_alerts[0]

    assert alert.severity == "warning"
    assert alert.stock == Decimal("5")
    assert alert.lead_time_days == 5
    assert alert.stock_days < Decimal("5")


@pytest.mark.asyncio
async def test_critical_deficit_alert_is_created_when_stock_is_zero(
    session_factory: async_sessionmaker[AsyncSession],
):
    product_id, location_id = await create_product_location_and_supplier(
        session_factory,
        lead_time_days=5,
    )

    movement_service = MovementService(UnitOfWork(session_factory))

    async with movement_service.uow:
        await movement_service.create_receipt(
            product_id=product_id,
            location_id=location_id,
            batch_number="BATCH-ZERO-STOCK",
            quantity=Decimal("10"),
            expiry_date=date(2027, 1, 1),
            unit_price=Decimal("100"),
            invoice_number="INV-ZERO-STOCK",
            document_number="DOC-ZERO-STOCK-RECEIPT",
        )

    async with movement_service.uow:
        await movement_service.consume(
            product_id=product_id,
            location_id=location_id,
            quantity=Decimal("10"),
            operation_date=datetime(
                2026,
                9,
                29,
                tzinfo=timezone.utc,
            ),
            document_number="DOC-ZERO-STOCK-CONSUME",
        )

    service = AlertService(UnitOfWork(session_factory))

    async with service.uow:
        alerts = await service.get_alerts(
            today=date(2026, 9, 29),
        )

    deficit_alerts = [
        alert
        for alert in alerts
        if alert.alert_type == "deficit_risk"
    ]

    assert len(deficit_alerts) == 1
    assert deficit_alerts[0].severity == "critical"
    assert deficit_alerts[0].stock == Decimal("0")