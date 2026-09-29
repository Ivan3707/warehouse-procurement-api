from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_uow
from app.api.schemas.stock import StockDetailResponse, StockResponse
from app.infrastructure.unit_of_work import UnitOfWork
from app.services.stock import StockService


router = APIRouter(
    prefix="/api/stock",
    tags=["stock"],
)


@router.get(
    "",
    response_model=list[StockResponse],
)
async def get_stock(
    today: date | None = Query(default=None),
    uow: UnitOfWork = Depends(get_uow),
):
    service = StockService(uow)

    if today is None:
        today = date.today()

    return await service.get_all_stock(today=today)

@router.get(
    "/{sku}",
    response_model=StockDetailResponse,
)
async def get_stock_detail(
    sku: str,
    today: date | None = Query(default=None),
    uow: UnitOfWork = Depends(get_uow),
):
    service = StockService(uow)

    if today is None:
        today = date.today()

    try:
        result = await service.get_stock_detail(
            sku=sku,
            today=today,
        )
    except ValueError as exc:
        if str(exc) == "Product not found":
            raise HTTPException(
                status_code=404,
                detail="Product not found",
            ) from exc

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "sku": result.sku,
        "name": result.name,
        "unit": result.unit,
        "locations": [
            {
                "location": location.location,
                "stock": location.stock,
                "batches": [
                    {
                        "batch_number": batch.batch_number,
                        "stock": batch.stock,
                        "expiry_date": batch.expiry_date,
                        "unit_price": batch.unit_price,
                        "invoice_number": batch.invoice_number,
                    }
                    for batch in location.batches
                ],
            }
            for location in result.locations
        ],
    }