from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_uow
from app.api.schemas.movements import (
    MovementCreate,
    MovementCreateResponse,
    MovementListResponse,
    MovementResponse,
)
from app.infrastructure.database.models.movement import MovementType
from app.infrastructure.unit_of_work import UnitOfWork
from app.services.movement import MovementService


router = APIRouter(
    prefix="/api/movements",
    tags=["movements"],
)
@router.post(
    "",
    response_model=MovementCreateResponse,
)
async def create_movement(
    data: MovementCreate,
    uow: UnitOfWork = Depends(get_uow),
):
    service = MovementService(uow)
    if data.sku is not None:
        product = await uow.products.get_by_sku(data.sku)

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Product not found",
            )

        data.product_id = product.id

    if data.object is not None:
        location = await uow.locations.get_by_code(data.object)

        if location is None:
            raise HTTPException(
                status_code=404,
                detail="Location not found",
            )

        data.location_id = location.id

    if data.operation_date > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=422,
            detail="Operation date cannot be in the future",
        )

    try:
        if data.operation_type == MovementType.RECEIPT:
            if data.batch_number is None:
                raise ValueError(
                    "batch_number is required for receipt"
                )

            if data.unit_price is None:
                raise ValueError(
                    "unit_price is required for receipt"
                )

            result = await service.create_receipt(
                product_id=data.product_id,
                location_id=data.location_id,
                batch_number=data.batch_number,
                quantity=data.quantity,
                expiry_date=data.expiry_date,
                unit_price=data.unit_price,
                invoice_number=data.invoice_number,
                document_number=data.document_number,
                operation_date=data.operation_date,
            )

            return result

        if data.operation_type == MovementType.CONSUME:
            movements = await service.consume(
                product_id=data.product_id,
                location_id=data.location_id,
                quantity=data.quantity,
                operation_date=data.operation_date,
                document_number=data.document_number,
            )

            stock = await uow.movements.get_stock(
                product_id=data.product_id,
                location_id=data.location_id,
            )

            return MovementCreateResponse(
                movement_id=movements[0].id,
                stock=stock,
            )

        if data.operation_type == MovementType.RETURN:
            if data.batch_id is None:
                raise ValueError(
                    "batch_id is required for return"
                )

            movement = await service.create_return(
                product_id=data.product_id,
                location_id=data.location_id,
                batch_id=data.batch_id,
                quantity=data.quantity,
                operation_date=data.operation_date,
                document_number=data.document_number,
            )

            stock = await uow.movements.get_stock(
                product_id=data.product_id,
                location_id=data.location_id,
            )

            return MovementCreateResponse(
                movement_id=movement.id,
                stock=stock,
            )

        if data.operation_type == MovementType.CORRECTION:
            movement = await service.create_correction(
                product_id=data.product_id,
                location_id=data.location_id,
                batch_id=data.batch_id,
                quantity=data.quantity,
                operation_date=data.operation_date,
                document_number=data.document_number,
            )

            stock = await uow.movements.get_stock(
                product_id=data.product_id,
                location_id=data.location_id,
            )

            return MovementCreateResponse(
                movement_id=movement.id,
                stock=stock,
            )
        if data.operation_type == MovementType.WRITEOFF:
            movements = await service.writeoff_expired(
                product_id=data.product_id,
                location_id=data.location_id,
                operation_date=data.operation_date,
                document_number=data.document_number,
            )

            if not movements:
                raise ValueError(
                    "No expired stock available for writeoff"
                )

            stock = await uow.movements.get_stock(
                product_id=data.product_id,
                location_id=data.location_id,
            )

            return MovementCreateResponse(
                movement_id=movements[0].id,
                stock=stock,
            )
        raise ValueError("Unsupported operation type")

    except ValueError as exc:
        message = str(exc)

        if "not found" in message.lower():
            raise HTTPException(
                status_code=404,
                detail=message,
            ) from exc

        if "already exists" in message.lower():
            raise HTTPException(
                status_code=409,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=422,
            detail=message,
        ) from exc

@router.get(
    "",
    response_model=MovementListResponse,
)
async def list_movements(
    product_id: int | None = Query(default=None),
    location_id: int | None = Query(default=None),
    sku: str | None = Query(default=None),
    object: str | None = Query(default=None),
    operation_type: MovementType | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    uow: UnitOfWork = Depends(get_uow),
):
        
    if sku is not None:
        product = await uow.products.get_by_sku(sku)

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Product not found",
            )

        product_id = product.id

    if object is not None:
        location = await uow.locations.get_by_code(object)

        if location is None:
            raise HTTPException(
                status_code=404,
                detail="Location not found",
            )

        location_id = location.id
    total = await uow.movements.count(
        product_id=product_id,
        location_id=location_id,
        operation_type=operation_type,
        date_from=date_from,
        date_to=date_to,
    )

    movements = await uow.movements.list(
        product_id=product_id,
        location_id=location_id,
        operation_type=operation_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )

    return MovementListResponse(
        items=movements,
        limit=limit,
        offset=offset,
        total=total,
    )