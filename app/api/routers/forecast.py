from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_uow
from app.api.schemas.forecast import (
    ForecastRequest,
    ForecastResponse,
)
from app.infrastructure.unit_of_work import UnitOfWork
from app.services.forecast import ForecastService


router = APIRouter(
    prefix="/api/forecast",
    tags=["forecast"],
)


@router.post(
    "",
    response_model=ForecastResponse,
)
async def create_forecast(
    data: ForecastRequest,
    uow: UnitOfWork = Depends(get_uow),
):
    service = ForecastService(uow)

    try:
        result = await service.forecast(
            sku=data.sku,
            location_code=data.location,
            horizon=data.horizon,
            horizon_unit=data.horizon_unit,
            safety_stock_days=data.safety_stock_days,
            today=date.today(),
        )

        return {
            "sku": result.sku,
            "name": result.name,
            "unit": result.unit,
            "location": result.location,
            "period": {
                "from": result.period.from_date,
                "to": result.period.to,
                "days": result.period.days,
            },
            "avg_daily_consumption": (
                result.avg_daily_consumption
            ),
            "forecast_demand": result.forecast_demand,
            "current_stock": result.current_stock,
            "incoming_qty": result.incoming_qty,
            "safety_stock": result.safety_stock,
            "reorder_point": result.reorder_point,
            "recommended_purchase_qty": (
                result.recommended_purchase_qty
            ),
            "unit_price": result.unit_price,
            "estimated_cost": result.estimated_cost,
            "recommended_order_date": (
                result.recommended_order_date
            ),
            "stockout_date": result.stockout_date,
            "explanation": {
                "data_used": (
                    result.explanation.data_used
                ),
                "formulas": (
                    result.explanation.formulas
                ),
                "assumptions": (
                    result.explanation.assumptions
                ),
                "as_of": result.explanation.as_of,
            },
            "warnings": [
                {
                    "level": warning.level,
                    "message": warning.message,
                }
                for warning in result.warnings
            ],
        }

    except ValueError as exc:
        message = str(exc)

        if "not found" in message.lower():
            raise HTTPException(
                status_code=404,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=422,
            detail=message,
        ) from exc