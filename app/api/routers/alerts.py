from datetime import date

from fastapi import APIRouter, Depends

from app.api.dependencies import get_uow
from app.api.schemas.alerts import AlertResponse
from app.infrastructure.unit_of_work import UnitOfWork
from app.services.alerts import AlertService


router = APIRouter(
    prefix="/api/alerts",
    tags=["alerts"],
)


@router.get(
    "",
    response_model=list[AlertResponse],
)
async def get_alerts(
    today: date | None = None,
    uow: UnitOfWork = Depends(get_uow),
):
    service = AlertService(uow)

    if today is None:
        today = date.today()

    return await service.get_alerts(today=today)