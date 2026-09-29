from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, utc_now

if TYPE_CHECKING:
    from app.infrastructure.database.models.product import Product
    from app.infrastructure.database.models.supplier import Supplier


class ProductSupplier(Base):
    __tablename__ = "product_suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
    )
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id"),
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    product: Mapped["Product"] = relationship(
        back_populates="suppliers",
    )

    supplier: Mapped["Supplier"] = relationship(
        back_populates="products",
    )

    __table_args__ = (
        UniqueConstraint("product_id", "supplier_id"),
    )