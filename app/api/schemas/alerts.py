from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class AlertResponse(BaseModel):
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