from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    sku: str = Field(min_length=1)
    location: str = Field(min_length=1)

    horizon: int = Field(gt=0)
    horizon_unit: Literal["days", "months"]

    safety_stock_days: int = Field(ge=0)


class ForecastPeriod(BaseModel):
    from_date: date = Field(alias="from")
    to: date
    days: int


class ForecastExplanation(BaseModel):
    data_used: list[str]
    formulas: list[str]
    assumptions: list[str]
    as_of: date


class ForecastWarning(BaseModel):
    level: str
    message: str


class ForecastResponse(BaseModel):
    sku: str
    name: str
    unit: str
    location: str

    period: ForecastPeriod

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

    explanation: ForecastExplanation
    warnings: list[ForecastWarning]