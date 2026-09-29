from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_CEILING

from app.infrastructure.database.models.batch import BatchStatus
from app.infrastructure.unit_of_work import UnitOfWork


@dataclass
class ForecastPeriodResult:
    from_date: date
    to: date
    days: int


@dataclass
class ForecastExplanationResult:
    data_used: list[str]
    formulas: list[str]
    assumptions: list[str]
    as_of: date


@dataclass
class ForecastWarningResult:
    level: str
    message: str


@dataclass
class ForecastResult:
    sku: str
    name: str
    unit: str
    location: str

    period: ForecastPeriodResult

    avg_daily_consumption: Decimal
    forecast_demand: Decimal
    current_stock: Decimal
    incoming_qty: Decimal
    safety_stock: Decimal
    reorder_point: Decimal

    recommended_purchase_qty: Decimal
    unit_price: Decimal
    estimated_cost: Decimal

    recommended_order_date: date
    stockout_date: date | None

    explanation: ForecastExplanationResult
    warnings: list[ForecastWarningResult]


class ForecastService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def forecast(
        self,
        *,
        sku: str,
        location_code: str,
        horizon: int,
        horizon_unit: str,
        safety_stock_days: int,
        today: date,
    ) -> ForecastResult:
        if horizon <= 0:
            raise ValueError("Horizon must be greater than zero")

        if horizon_unit not in {"days", "months"}:
            raise ValueError(
                "Horizon unit must be 'days' or 'months'"
            )

        if safety_stock_days < 0:
            raise ValueError(
                "Safety stock days cannot be negative"
            )

        product = await self.uow.products.get_by_sku(sku)

        if product is None:
            raise ValueError(
                f"Product with SKU '{sku}' not found"
            )

        location = await self.uow.locations.get_by_code(
            location_code
        )

        if location is None:
            raise ValueError(
                f"Location with code '{location_code}' not found"
            )

        period = self._build_period(
            today=today,
            horizon=horizon,
            horizon_unit=horizon_unit,
        )

        current_stock = await self.uow.movements.get_stock(
            product_id=product.id,
            location_id=location.id,
        )

        consumption_end = datetime.combine(
            today + timedelta(days=1),
            datetime.min.time(),
        )

        consumption_start = (
            consumption_end - timedelta(days=90)
        )

        consumption = await self.uow.movements.get_consumption(
            product_id=product.id,
            location_id=location.id,
            start_date=consumption_start,
            end_date=consumption_end,
        )

        average_daily_consumption = (
            consumption / Decimal("90")
        )

        forecast_demand = (
            average_daily_consumption
            * Decimal(period.days)
        )

        safety_stock = (
            average_daily_consumption
            * Decimal(safety_stock_days)
        )

        suppliers = await self.uow.product_suppliers.get_for_product(
            product.id
        )

        if not suppliers:
            raise ValueError(
                f"Supplier not found for product '{sku}'"
            )

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

        if supplier is None:
            raise ValueError(
                f"Supplier not found for product '{sku}'"
            )

        lead_time_days = supplier.lead_time_days

        reorder_point = (
            average_daily_consumption
            * Decimal(lead_time_days)
            + safety_stock
        )

        incoming_qty = await self._get_incoming_quantity(
            product_id=product.id,
            location_id=location.id,
            period_end=period.to,
        )

        recommended_purchase_qty = (
            forecast_demand
            + safety_stock
            - current_stock
            - incoming_qty
        )

        if recommended_purchase_qty < 0:
            recommended_purchase_qty = Decimal("0")

        recommended_purchase_qty = (
            self._round_purchase_quantity(
                quantity=recommended_purchase_qty,
                package_size=product.package_size,
                min_order_qty=product.min_order_qty,
            )
        )

        estimated_cost = (
            recommended_purchase_qty
            * primary_supplier.unit_price
        )

        recommended_order_date = (
            self._calculate_recommended_order_date(
                today=today,
                current_stock=current_stock,
                reorder_point=reorder_point,
                average_daily_consumption=(
                    average_daily_consumption
                ),
            )
        )

        stockout_date = self._calculate_stockout_date(
            today=today,
            current_stock=current_stock,
            average_daily_consumption=(
                average_daily_consumption
            ),
        )

        warnings = self._build_warnings(
            current_stock=current_stock,
            reorder_point=reorder_point,
            stockout_date=stockout_date,
            today=today,
            incoming_qty=incoming_qty,
        )

        explanation = ForecastExplanationResult(
            data_used=[
                "Движения товара за последние 90 дней",
                (
                    "Текущий остаток, рассчитанный "
                    "по движениям"
                ),
                (
                    "Открытые заказы поставщикам "
                    "с ожидаемой датой до конца периода"
                ),
                "Основной поставщик товара",
            ],
            formulas=[
                (
                    "средний расход/день = "
                    "расход за 90 дн. ÷ 90"
                ),
                (
                    "прогноз = "
                    "средний расход/день × дней в периоде"
                ),
                (
                    "страховой запас = "
                    "средний расход/день × "
                    "дней страхового запаса"
                ),
                (
                    "точка заказа = "
                    "средний расход/день × lead time "
                    "+ страховой запас"
                ),
                (
                    "объём закупки = "
                    "прогноз + страховой запас "
                    "− остаток − поставки в пути"
                ),
            ],
            assumptions=[
                "Цена принята на уровне выбранного поставщика.",
                (
                    "Прогноз спроса основан на среднем "
                    "расходе за последние 90 дней."
                ),
                (
                    "Поставки в пути учитываются, "
                    "если их ожидаемая дата не позже "
                    "конца прогнозного периода."
                ),
                (
                    "Рекомендуемое количество округляется "
                    "вверх до размера упаковки и не может "
                    "быть меньше минимальной партии заказа."
                ),
            ],
            as_of=today,
        )

        return ForecastResult(
            sku=product.sku,
            name=product.name,
            unit=product.unit,
            location=location.code,
            period=period,
            avg_daily_consumption=average_daily_consumption,
            forecast_demand=forecast_demand,
            current_stock=current_stock,
            incoming_qty=incoming_qty,
            safety_stock=safety_stock,
            reorder_point=reorder_point,
            recommended_purchase_qty=(
                recommended_purchase_qty
            ),
            unit_price=primary_supplier.unit_price,
            estimated_cost=estimated_cost,
            recommended_order_date=(
                recommended_order_date
            ),
            stockout_date=stockout_date,
            explanation=explanation,
            warnings=warnings,
        )

    async def _get_incoming_quantity(
        self,
        *,
        product_id: int,
        location_id: int,
        period_end: date,
    ) -> Decimal:
        ordered_batches = (
            await self.uow.batches.get_ordered_batches(
                product_id=product_id,
                location_id=location_id,
            )
        )

        incoming_qty = Decimal("0")

        for batch in ordered_batches:
            if (
                batch.expected_date is None
                or batch.expected_date <= period_end
            ):
                incoming_qty += batch.ordered_quantity

        return incoming_qty

    @staticmethod
    def _build_period(
        *,
        today: date,
        horizon: int,
        horizon_unit: str,
    ) -> ForecastPeriodResult:
        if horizon_unit == "days":
            period_end = today + timedelta(days=horizon)
        else:
            period_end = ForecastService._add_months(
                today,
                horizon,
            )

        days = (period_end - today).days

        return ForecastPeriodResult(
            from_date=today,
            to=period_end,
            days=days,
        )

    @staticmethod
    def _add_months(
        value: date,
        months: int,
    ) -> date:
        month_index = (
            value.year * 12
            + value.month
            - 1
            + months
        )

        year = month_index // 12
        month = month_index % 12 + 1

        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)

        last_day = (
            next_month - timedelta(days=1)
        ).day

        day = min(value.day, last_day)

        return date(year, month, day)

    @staticmethod
    def _round_purchase_quantity(
        *,
        quantity: Decimal,
        package_size: Decimal,
        min_order_qty: Decimal,
    ) -> Decimal:
        if quantity <= 0:
            return Decimal("0")

        result = quantity

        if package_size > 0:
            packages = (
                result / package_size
            ).quantize(
                Decimal("1"),
                rounding=ROUND_CEILING,
            )

            result = packages * package_size

        if result < min_order_qty:
            result = min_order_qty

        return result

    @staticmethod
    def _calculate_recommended_order_date(
        *,
        today: date,
        current_stock: Decimal,
        reorder_point: Decimal,
        average_daily_consumption: Decimal,
    ) -> date:
        if average_daily_consumption <= 0:
            return today

        if current_stock <= reorder_point:
            return today

        days_until_reorder = (
            current_stock - reorder_point
        ) / average_daily_consumption

        days_until_reorder = days_until_reorder.quantize(
            Decimal("1"),
            rounding=ROUND_CEILING,
        )

        return today + timedelta(
            days=int(days_until_reorder)
        )

    @staticmethod
    def _calculate_stockout_date(
        *,
        today: date,
        current_stock: Decimal,
        average_daily_consumption: Decimal,
    ) -> date | None:
        if current_stock <= 0:
            return today

        if average_daily_consumption <= 0:
            return None

        days_until_stockout = (
            current_stock
            / average_daily_consumption
        ).quantize(
            Decimal("1"),
            rounding=ROUND_CEILING,
        )

        return today + timedelta(
            days=int(days_until_stockout)
        )

    @staticmethod
    def _build_warnings(
        *,
        current_stock: Decimal,
        reorder_point: Decimal,
        stockout_date: date | None,
        today: date,
        incoming_qty: Decimal,
    ) -> list[ForecastWarningResult]:
        warnings: list[ForecastWarningResult] = []

        if current_stock <= reorder_point:
            warnings.append(
                ForecastWarningResult(
                    level="warning",
                    message="Остаток ниже точки заказа",
                )
            )

        if stockout_date is not None:
            days_to_stockout = (
                stockout_date - today
            ).days

            if days_to_stockout <= 0:
                warnings.append(
                    ForecastWarningResult(
                        level="critical",
                        message="Текущий остаток уже исчерпан",
                    )
                )
            elif days_to_stockout <= 7:
                warnings.append(
                    ForecastWarningResult(
                        level="warning",
                        message=(
                            "Остаток будет исчерпан "
                            "в течение 7 дней"
                        ),
                    )
                )

        if incoming_qty == 0:
            warnings.append(
                ForecastWarningResult(
                    level="info",
                    message="Поставки в пути отсутствуют",
                )
            )

        return warnings