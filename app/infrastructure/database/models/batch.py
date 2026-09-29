from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, utc_now

if TYPE_CHECKING:
    from app.infrastructure.database.models.location import Location
    from app.infrastructure.database.models.movement import Movement
    from app.infrastructure.database.models.product import Product


class BatchStatus(str, Enum):
    ORDERED = "ordered"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
    )
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id"),
        nullable=False,
    )

    batch_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[BatchStatus] = mapped_column(
        SQLEnum(BatchStatus),
        nullable=False,
        default=BatchStatus.RECEIVED,
    )

    expected_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    received_at: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    expiry_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    invoice_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    ordered_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )

    product: Mapped["Product"] = relationship(
        back_populates="batches",
    )

    location: Mapped["Location"] = relationship(
        back_populates="batches",
    )

    movements: Mapped[list["Movement"]] = relationship(
        back_populates="batch",
    )


    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "location_id",
            "batch_number",
        ),
    )