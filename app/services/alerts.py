from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.infrastructure.database.models.batch import Batch
from app.infrastructure.unit_of_work import UnitOfWork


@dataclass
class AlertResult:
    alert_type: str
    severity: str

    product_id: int
    location_id: int

    message: str

    stock: Decimal | None = None
    stock_days: Decimal | None = None
    lead_time_days: int | None = None

    batch_id: int | None = None
    expiry_date: date | None = None
    days_to_expiry: int | None = None

    last_movement_date: datetime | None = None
    days_without_movement: int | None = None


class AlertService:
    def __init__(
        self,
        uow: UnitOfWork,
        *,
        expiry_threshold_days: int = 30,
        no_movement_threshold_days: int = 30,
    ):
        self.uow = uow
        self.expiry_threshold_days = expiry_threshold_days
        self.no_movement_threshold_days = no_movement_threshold_days

    async def get_alerts(
        self,
        *,
        today: date,
    ) -> list[AlertResult]:
        products = await self.uow.products.list()
        locations = await self.uow.locations.list()

        alerts: list[AlertResult] = []

        for product in products:
            suppliers = await self.uow.product_suppliers.get_for_product(
                product.id
            )

            if suppliers:
                primary_supplier = next(
                    (
                        item
                        for item in suppliers
                        if item.is_primary
                    ),
                    suppliers[0],
                )

                supplier = await self.uow.suppliers.get_by_id(
                    primary_supplier.supplier_id
                )
            else:
                supplier = None

            lead_time_days = (
                supplier.lead_time_days
                if supplier is not None
                else None
            )

            for location in locations:
                stock = await self.uow.movements.get_stock(
                    product_id=product.id,
                    location_id=location.id,
                )

                alerts.extend(
                    await self._check_deficit(
                        product_id=product.id,
                        location_id=location.id,
                        stock=stock,
                        lead_time_days=lead_time_days,
                        today=today,
                    )
                )

                alerts.extend(
                    await self._check_expiry(
                        product_id=product.id,
                        location_id=location.id,
                        today=today,
                    )
                )

                alerts.extend(
                    await self._check_no_movement(
                        product_id=product.id,
                        location_id=location.id,
                        today=today,
                    )
                )

        return alerts

    async def _check_deficit(
        self,
        *,
        product_id: int,
        location_id: int,
        stock: Decimal,
        lead_time_days: int | None,
        today: date,
    ) -> list[AlertResult]:
        if lead_time_days is None:
            return []

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

        average_daily_consumption = (
            consumption / Decimal("90")
        )

        if average_daily_consumption <= 0:
            return []

        stock_days = stock / average_daily_consumption

        if stock_days >= Decimal(lead_time_days):
            return []

        if stock <= 0:
            severity = "critical"
        else:
            severity = "warning"

        return [
            AlertResult(
                alert_type="deficit_risk",
                severity=severity,
                product_id=product_id,
                location_id=location_id,
                message=(
                    f"Stock covers approximately "
                    f"{stock_days:.2f} days, while supplier "
                    f"lead time is {lead_time_days} days"
                ),
                stock=stock,
                stock_days=stock_days,
                lead_time_days=lead_time_days,
            )
        ]

    async def _check_expiry(
        self,
        *,
        product_id: int,
        location_id: int,
        today: date,
    ) -> list[AlertResult]:
        batches = await self.uow.movements.get_available_batches_with_stock(
            product_id=product_id,
            location_id=location_id,
            today=today,
        )

        alerts = []

        threshold_date = (
            today
            + timedelta(days=self.expiry_threshold_days)
        )

        for batch, stock in batches:
            if batch.expiry_date is None:
                continue

            if batch.expiry_date > threshold_date:
                continue

            days_to_expiry = (
                batch.expiry_date - today
            ).days

            if days_to_expiry <= 0:
                severity = "critical"
            elif days_to_expiry <= 7:
                severity = "critical"
            else:
                severity = "warning"

            alerts.append(
                AlertResult(
                    alert_type="approaching_expiry",
                    severity=severity,
                    product_id=product_id,
                    location_id=location_id,
                    message=(
                        f"Batch {batch.batch_number} expires "
                        f"in {days_to_expiry} days"
                    ),
                    stock=stock,
                    batch_id=batch.id,
                    expiry_date=batch.expiry_date,
                    days_to_expiry=days_to_expiry,
                )
            )

        return alerts

    async def _check_no_movement(
        self,
        *,
        product_id: int,
        location_id: int,
        today: date,
    ) -> list[AlertResult]:
        movements = await self.uow.movements.list(
            product_id=product_id,
            location_id=location_id,
        )

        if not movements:
            return [
                AlertResult(
                    alert_type="no_movement",
                    severity="warning",
                    product_id=product_id,
                    location_id=location_id,
                    message="No movements recorded for this product and location",
                    days_without_movement=None,
                )
            ]

        last_movement = movements[0].operation_date

        today_datetime = datetime.combine(
            today,
            datetime.min.time(),
        )

        days_without_movement = (
            today_datetime.date() - last_movement.date()
        ).days

        if days_without_movement < self.no_movement_threshold_days:
            return []

        return [
            AlertResult(
                alert_type="no_movement",
                severity="warning",
                product_id=product_id,
                location_id=location_id,
                message=(
                    f"No movement for "
                    f"{days_without_movement} days"
                ),
                last_movement_date=last_movement,
                days_without_movement=days_without_movement,
            )
        ]