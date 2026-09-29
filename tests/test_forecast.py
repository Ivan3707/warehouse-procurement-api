from datetime import date
from decimal import Decimal

from app.services.forecast import ForecastService


def test_purchase_quantity_is_rounded_to_package_and_minimum():
    result = ForecastService._round_purchase_quantity(
        quantity=Decimal("23"),
        package_size=Decimal("10"),
        min_order_qty=Decimal("20"),
    )

    assert result == Decimal("30")


def test_purchase_quantity_respects_minimum_order_qty():
    result = ForecastService._round_purchase_quantity(
        quantity=Decimal("3"),
        package_size=Decimal("10"),
        min_order_qty=Decimal("20"),
    )

    assert result == Decimal("20")


def test_purchase_quantity_is_zero_when_no_purchase_is_needed():
    result = ForecastService._round_purchase_quantity(
        quantity=Decimal("0"),
        package_size=Decimal("10"),
        min_order_qty=Decimal("20"),
    )

    assert result == Decimal("0")


def test_stockout_date_is_calculated_from_stock_and_daily_consumption():
    result = ForecastService._calculate_stockout_date(
        today=date(2026, 9, 29),
        current_stock=Decimal("50"),
        average_daily_consumption=Decimal("10"),
    )

    assert result == date(2026, 10, 4)


def test_stockout_date_is_today_when_stock_is_empty():
    result = ForecastService._calculate_stockout_date(
        today=date(2026, 9, 29),
        current_stock=Decimal("0"),
        average_daily_consumption=Decimal("10"),
    )

    assert result == date(2026, 9, 29)


def test_stockout_date_is_none_when_consumption_is_zero():
    result = ForecastService._calculate_stockout_date(
        today=date(2026, 9, 29),
        current_stock=Decimal("50"),
        average_daily_consumption=Decimal("0"),
    )

    assert result is None


def test_recommended_order_date_is_today_when_stock_is_at_reorder_point():
    result = ForecastService._calculate_recommended_order_date(
        today=date(2026, 9, 29),
        current_stock=Decimal("30"),
        reorder_point=Decimal("30"),
        average_daily_consumption=Decimal("10"),
    )

    assert result == date(2026, 9, 29)


def test_recommended_order_date_is_calculated_from_stock_surplus():
    result = ForecastService._calculate_recommended_order_date(
        today=date(2026, 9, 29),
        current_stock=Decimal("70"),
        reorder_point=Decimal("30"),
        average_daily_consumption=Decimal("10"),
    )

    assert result == date(2026, 10, 3)