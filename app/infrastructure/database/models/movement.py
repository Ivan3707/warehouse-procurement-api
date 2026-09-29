from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
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
    from app.infrastructure.database.models.batch import Batch
    from app.infrastructure.database.models.location import Location
    from app.infrastructure.database.models.product import Product



class MovementType(str, Enum):
    RECEIPT = "receipt"
    CONSUME = "consume"
    WRITEOFF = "writeoff"
    RETURN = "return"
    CORRECTION = "correction"


class Movement(Base):
    __tablename__ = "movements"

    id: Mapped[int] = mapped_column(primary_key=True)

    operation_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
    )
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id"),
        nullable=False,
    )
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("batches.id"),
        nullable=True,
    )

    operation_type: Mapped[MovementType] = mapped_column(
        SQLEnum(MovementType),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )

    document_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    product: Mapped["Product"] = relationship(
        back_populates="movements",
    )

    location: Mapped["Location"] = relationship(
        back_populates="movements",
    )

    batch: Mapped["Batch | None"] = relationship(
        back_populates="movements",
    )
    __table_args__ = (
        UniqueConstraint(
            "document_number",
            "batch_id",
            name="uq_movements_document_batch",
        ),
    )