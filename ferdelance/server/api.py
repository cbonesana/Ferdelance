from ferdelance.config import conf
from ferdelance.database import DataBase, Base
from ferdelance.server.routes.client import client_router
from ferdelance.server.routes.manager import manager_router
from ferdelance.server.routes.workbench import workbench_router
from ferdelance.server.routes.worker import worker_router
from ferdelance.server.startup import ServerStartup

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import uvicorn

import logging

LOGGER = logging.getLogger(__name__)


def init_api() -> FastAPI:
    api = FastAPI()

    api.include_router(client_router)
    api.include_router(manager_router)
    api.include_router(workbench_router)
    api.include_router(worker_router)

    return api


api = init_api()


@api.on_event("startup")
async def populate_database() -> None:
    """All operations marked as `on_event('startup')` are executed when the API are started."""
    LOGGER.info("server startup procedure started")

    inst = DataBase()

    async with inst.engine.connect() as _:

        async with inst.engine.begin() as conn:
            LOGGER.info("database creation started")
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)
            LOGGER.info("database creation completed")

        async with inst.async_session() as session:
            ss = ServerStartup(session)
            await ss.startup()


@api.on_event("shutdown")
async def shutdown() -> None:
    LOGGER.info("server shutdown procedure started")
    inst = DataBase()
    if inst.engine:
        await inst.engine.dispose()


@api.get("/")
async def root():
    """This is the endpoint for the home page."""
    return "Hi! 😀"


@api.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
    LOGGER.error(f"{request}: {exc_str}")
    content = {"status_code": 10422, "message": exc_str, "data": None}
    return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


if __name__ == "__main__":
    uvicorn.run(api, host=conf.SERVER_INTERFACE, port=conf.SERVER_PORT)
