from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.infrastructure.unit_of_work import UnitOfWork


@dataclass
class StockResult:
    product_id: int
    location_id: int
    stock: Decimal
    average_daily_consumption: Decimal
    stock_days: Decimal | None
    nearest_expiry: date | None


@dataclass
class StockBatchResult:
    batch_number: str
    stock: Decimal
    expiry_date: date | None
    unit_price: Decimal
    invoice_number: str | None


@dataclass
class StockLocationResult:
    location: str
    stock: Decimal
    batches: list[StockBatchResult]


@dataclass
class StockDetailResult:
    sku: str
    name: str
    unit: str
    locations: list[StockLocationResult]

class StockService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def get_stock(
        self,
        *,
        product_id: int,
        location_id: int,
        today: date,
    ) -> StockResult:
        product = await self.uow.products.get_by_id(product_id)
        if product is None:
            raise ValueError("Product not found")

        location = await self.uow.locations.get_by_id(location_id)
        if location is None:
            raise ValueError("Location not found")

        stock = await self.uow.movements.get_stock(
            product_id=product_id,
            location_id=location_id,
        )

        end_date = datetime.combine(
            today + timedelta(days=1),
            datetime.min.time(),
        )

        start_date = end_date - timedelta(days=90)

        consumption = await self.uow.movements.get_consumption(
            product_id=product_id,
            location_id=location_id,
            start_date=start_date,
            end_date=end_date,
        )

        average_daily_consumption = consumption / Decimal("90")

        if average_daily_consumption > 0:
            stock_days = stock / average_daily_consumption
        else:
            stock_days = None

        batches = await self.uow.movements.get_available_batches_with_stock(
            product_id=product_id,
            location_id=location_id,
            today=today,
        )

        nearest_expiry = (
            batches[0][0].expiry_date
            if batches
            else None
        )

        return StockResult(
            product_id=product_id,
            location_id=location_id,
            stock=stock,
            average_daily_consumption=average_daily_consumption,
            stock_days=stock_days,
            nearest_expiry=nearest_expiry,
        )

    async def get_stock_detail(
        self,
        *,
        sku: str,
        today: date,
    ) -> StockDetailResult:
        product = await self.uow.products.get_by_sku(sku)

        if product is None:
            raise ValueError("Product not found")

        locations = await self.uow.locations.list()

        location_results = []

        for location in locations:
            batches = await self.uow.batches.get_batches_with_stock(
                product_id=product.id,
                location_id=location.id,
            )

            if not batches:
                continue

            batch_results = [
                StockBatchResult(
                    batch_number=batch.batch_number,
                    stock=stock,
                    expiry_date=batch.expiry_date,
                    unit_price=batch.unit_price,
                    invoice_number=batch.invoice_number,
                )
                for batch, stock in batches
            ]

            location_stock = sum(
                (batch.stock for batch in batch_results),
                Decimal("0"),
            )

            location_results.append(
                StockLocationResult(
                    location=location.code,
                    stock=location_stock,
                    batches=batch_results,
                )
            )

        return StockDetailResult(
            sku=product.sku,
            name=product.name,
            unit=product.unit,
            locations=location_results,
        )

    async def get_all_stock(
        self,
        *,
        today: date,
    ) -> list[StockResult]:
        products = await self.uow.products.list()
        locations = await self.uow.locations.list()

        results = []

        for product in products:
            for location in locations:
                result = await self.get_stock(
                    product_id=product.id,
                    location_id=location.id,
                    today=today,
                )

                results.append(result)

        return results