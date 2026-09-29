from datetime import datetime
from decimal import Decimal

from app.infrastructure.database.models.batch import Batch
from app.infrastructure.database.models.movement import Movement
from app.infrastructure.database.models.product_supplier import ProductSupplier
from sqlalchemy import Boolean, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, utc_now


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)

    package_size: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )
    min_order_qty: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    
    suppliers: Mapped[list["ProductSupplier"]] = relationship(
        back_populates="product",
    )
    batches: Mapped[list["Batch"]] = relationship(
        back_populates="product",
    )
    movements: Mapped[list["Movement"]] = relationship(
        back_populates="product",
    )