from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.infrastructure.database.models.batch import Batch, BatchStatus
from app.infrastructure.database.models.location import Location
from app.infrastructure.database.models.movement import Movement, MovementType
from app.infrastructure.database.models.product import Product
from app.infrastructure.database.models.product_supplier import ProductSupplier
from app.infrastructure.database.models.supplier import Supplier
from app.infrastructure.database.session import async_session_maker


def utc_datetime(value: date) -> datetime:
    return datetime(
        value.year,
        value.month,
        value.day,
        tzinfo=timezone.utc,
    )


async def seed() -> None:
    async with async_session_maker() as session:
        existing_product = await session.scalar(
            select(Product).limit(1)
        )

        if existing_product is not None:
            print("Seed skipped: database already contains products")
            return

        today = date.today()

        # Locations

        wh1 = Location(
            code="WH-01",
            name="Main Warehouse",
            active=True,
        )

        wh2 = Location(
            code="WH-02",
            name="Secondary Warehouse",
            active=True,
        )

        session.add_all([wh1, wh2])
        await session.flush()

        # Products

        milk = Product(
            sku="MILK-001",
            name="Milk 2.5%",
            unit="l",
            package_size=Decimal("10"),
            min_order_qty=Decimal("20"),
            active=True,
        )

        bread = Product(
            sku="BREAD-001",
            name="White Bread",
            unit="pcs",
            package_size=Decimal("10"),
            min_order_qty=Decimal("30"),
            active=True,
        )

        cheese = Product(
            sku="CHEESE-001",
            name="Hard Cheese",
            unit="kg",
            package_size=Decimal("5"),
            min_order_qty=Decimal("10"),
            active=True,
        )

        session.add_all([milk, bread, cheese])
        await session.flush()

        # Suppliers

        supplier_a = Supplier(
            name="Fresh Food Supplier",
            lead_time_days=3,
            active=True,
        )

        supplier_b = Supplier(
            name="Regional Food Supplier",
            lead_time_days=7,
            active=True,
        )

        session.add_all([supplier_a, supplier_b])
        await session.flush()

        # Product suppliers

        session.add_all(
            [
                ProductSupplier(
                    product_id=milk.id,
                    supplier_id=supplier_a.id,
                    unit_price=Decimal("95.00"),
                    is_primary=True,
                ),
                ProductSupplier(
                    product_id=bread.id,
                    supplier_id=supplier_a.id,
                    unit_price=Decimal("45.00"),
                    is_primary=True,
                ),
                ProductSupplier(
                    product_id=cheese.id,
                    supplier_id=supplier_b.id,
                    unit_price=Decimal("680.00"),
                    is_primary=True,
                ),
            ]
        )
        await session.flush()

        # Batches

        milk_old = Batch(
            product_id=milk.id,
            location_id=wh1.id,
            batch_number="MILK-OLD",
            status=BatchStatus.RECEIVED,
            received_at=today - timedelta(days=20),
            expiry_date=today + timedelta(days=5),
            unit_price=Decimal("92.00"),
            invoice_number="INV-MILK-001",
            ordered_quantity=Decimal("100"),
        )

        milk_new = Batch(
            product_id=milk.id,
            location_id=wh1.id,
            batch_number="MILK-NEW",
            status=BatchStatus.RECEIVED,
            received_at=today - timedelta(days=5),
            expiry_date=today + timedelta(days=20),
            unit_price=Decimal("95.00"),
            invoice_number="INV-MILK-002",
            ordered_quantity=Decimal("100"),
        )

        milk_ordered = Batch(
            product_id=milk.id,
            location_id=wh1.id,
            batch_number="MILK-ORDERED",
            status=BatchStatus.ORDERED,
            expected_date=today + timedelta(days=4),
            expiry_date=today + timedelta(days=30),
            unit_price=Decimal("95.00"),
            invoice_number="INV-MILK-003",
            ordered_quantity=Decimal("100"),
        )

        bread_batch = Batch(
            product_id=bread.id,
            location_id=wh1.id,
            batch_number="BREAD-001",
            status=BatchStatus.RECEIVED,
            received_at=today - timedelta(days=10),
            expiry_date=today + timedelta(days=10),
            unit_price=Decimal("43.00"),
            invoice_number="INV-BREAD-001",
            ordered_quantity=Decimal("100"),
        )

        cheese_expired = Batch(
            product_id=cheese.id,
            location_id=wh2.id,
            batch_number="CHEESE-EXPIRED",
            status=BatchStatus.RECEIVED,
            received_at=today - timedelta(days=40),
            expiry_date=today - timedelta(days=5),
            unit_price=Decimal("650.00"),
            invoice_number="INV-CHEESE-001",
            ordered_quantity=Decimal("30"),
        )

        session.add_all(
            [
                milk_old,
                milk_new,
                milk_ordered,
                bread_batch,
                cheese_expired,
            ]
        )
        await session.flush()

        # Movements

        movements = [
            # Milk old batch: 100 received, 30 consumed => 70 left.
            Movement(
                operation_date=utc_datetime(today - timedelta(days=20)),
                product_id=milk.id,
                location_id=wh1.id,
                batch_id=milk_old.id,
                operation_type=MovementType.RECEIPT,
                quantity=Decimal("100"),
                document_number="REC-MILK-001",
            ),
            Movement(
                operation_date=utc_datetime(today - timedelta(days=15)),
                product_id=milk.id,
                location_id=wh1.id,
                batch_id=milk_old.id,
                operation_type=MovementType.CONSUME,
                quantity=Decimal("30"),
                document_number="CON-MILK-001",
            ),

            # Milk new batch: 100 received, 20 consumed => 80 left.
            Movement(
                operation_date=utc_datetime(today - timedelta(days=5)),
                product_id=milk.id,
                location_id=wh1.id,
                batch_id=milk_new.id,
                operation_type=MovementType.RECEIPT,
                quantity=Decimal("100"),
                document_number="REC-MILK-002",
            ),
            Movement(
                operation_date=utc_datetime(today - timedelta(days=2)),
                product_id=milk.id,
                location_id=wh1.id,
                batch_id=milk_new.id,
                operation_type=MovementType.CONSUME,
                quantity=Decimal("20"),
                document_number="CON-MILK-002",
            ),

            # Bread: 100 received, 85 consumed => 15 left.
            Movement(
                operation_date=utc_datetime(today - timedelta(days=10)),
                product_id=bread.id,
                location_id=wh1.id,
                batch_id=bread_batch.id,
                operation_type=MovementType.RECEIPT,
                quantity=Decimal("100"),
                document_number="REC-BREAD-001",
            ),
            Movement(
                operation_date=utc_datetime(today - timedelta(days=3)),
                product_id=bread.id,
                location_id=wh1.id,
                batch_id=bread_batch.id,
                operation_type=MovementType.CONSUME,
                quantity=Decimal("85"),
                document_number="CON-BREAD-001",
            ),

            # Cheese expired batch: 30 received, 5 already consumed => 25 remain.
            Movement(
                operation_date=utc_datetime(today - timedelta(days=40)),
                product_id=cheese.id,
                location_id=wh2.id,
                batch_id=cheese_expired.id,
                operation_type=MovementType.RECEIPT,
                quantity=Decimal("30"),
                document_number="REC-CHEESE-001",
            ),
            Movement(
                operation_date=utc_datetime(today - timedelta(days=30)),
                product_id=cheese.id,
                location_id=wh2.id,
                batch_id=cheese_expired.id,
                operation_type=MovementType.CONSUME,
                quantity=Decimal("5"),
                document_number="CON-CHEESE-001",
            ),
        ]

        session.add_all(movements)

        await session.commit()

        print("Seed completed successfully")


if __name__ == "__main__":
    import asyncio

    asyncio.run(seed())