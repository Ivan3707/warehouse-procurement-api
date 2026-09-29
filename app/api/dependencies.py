from collections.abc import AsyncGenerator

from app.infrastructure.database.session import async_session_maker
from app.infrastructure.unit_of_work import UnitOfWork


async def get_uow() -> AsyncGenerator[UnitOfWork, None]:
    async with UnitOfWork(async_session_maker) as uow:
        yield uow