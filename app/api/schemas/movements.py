from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.infrastructure.database.models.movement import MovementType


class MovementCreate(BaseModel):
    product_id: int | None = None
    location_id: int | None = None

    sku: str | None = None
    object: str | None = None

    batch_id: int | None = None

    operation_type: MovementType

    quantity: Decimal
    operation_date: datetime

    batch_number: str | None = None
    expiry_date: date | None = None
    unit_price: Decimal | None = None
    invoice_number: str | None = None

    document_number: str

class MovementResponse(BaseModel):
    id: int
    operation_date: datetime
    product_id: int
    location_id: int
    batch_id: int | None
    operation_type: MovementType
    quantity: Decimal
    document_number: str

class MovementListResponse(BaseModel):
    items: list[MovementResponse]
    limit: int
    offset: int
    total: int

class MovementCreateResponse(BaseModel):
    movement_id: int
    stock: Decimal
    