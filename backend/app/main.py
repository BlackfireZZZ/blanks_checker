from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import router
from app.core.config import settings
from app.core.logger import logger
from app.db.models import ServiceStatusState
from app.db.session import AsyncSessionLocal
from app.schemas.blank_check import ErrorPayload, ErrorResponse
from app.services.state import check_infrastructure, ensure_bootstrap_state
from app.storage.s3 import get_s3_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSessionLocal() as session:
        await ensure_bootstrap_state(session)
        storage = await get_s3_client()
        ok, error = await check_infrastructure(session, storage)
        status = await session.get(ServiceStatusState, 1)
        if status is not None:
            status.ready = ok
            status.last_error = error
            await session.commit()
    yield


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)
app.include_router(router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    payload = ErrorResponse(
        error=ErrorPayload(
            code="VALIDATION_ERROR",
            message="Invalid request",
            details={"errors": exc.errors()},
        )
    )
    return JSONResponse(status_code=400, content=payload.model_dump())


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    # If the detail already follows the ErrorResponse schema, pass it through.
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = exc.detail
    else:
        payload = ErrorResponse(
            error=ErrorPayload(
                code="HTTP_ERROR",
                message=str(exc.detail),
                details={"status_code": exc.status_code},
            )
        )
        content = payload.model_dump()
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    payload = ErrorResponse(
        error=ErrorPayload(
            code="INTERNAL_ERROR",
            message="Service temporarily unavailable",
            details={"exception": type(exc).__name__},
        )
    )
    return JSONResponse(status_code=500, content=payload.model_dump())
