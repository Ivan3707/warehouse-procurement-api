from fastapi import FastAPI

from app.api.routers.alerts import router as alerts_router
from app.api.routers.forecast import router as forecast_router
from app.api.routers.movements import router as movements_router
from app.api.routers.stock import router as stock_router


app = FastAPI(
    title="SPA",
    version="1.0.0",
)


app.include_router(movements_router)
app.include_router(stock_router)
app.include_router(forecast_router)
app.include_router(alerts_router)