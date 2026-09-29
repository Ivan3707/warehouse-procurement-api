from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class StockResponse(BaseModel):
    product_id: int
    location_id: int
    stock: Decimal
    average_daily_consumption: Decimal
    stock_days: Decimal | None
    nearest_expiry: date | None


class StockBatchResponse(BaseModel):
    batch_number: str
    stock: Decimal
    expiry_date: date | None
    unit_price: Decimal
    invoice_number: str | None


class StockLocationResponse(BaseModel):
    location: str
    stock: Decimal
    batches: list[StockBatchResponse]


class StockDetailResponse(BaseModel):
    sku: str
    name: str
    unit: str
    locations: list[StockLocationResponse]
