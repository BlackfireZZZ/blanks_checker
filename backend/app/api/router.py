from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.blank_check import BlankCheckResponse, ErrorPayload, ErrorResponse
from app.services.pipeline import run_blanks_pipeline
from app.services.recognized_blanks import save_recognized_blank

router = APIRouter()


@router.get("/ready")
async def ready():
    """Healthcheck endpoint for docker and load balancers."""
    return {"status": "ok"}


@router.post(
    "/blank-check",
    response_model=BlankCheckResponse,
    summary="Upload PDF and get blank recognition result",
)
async def blank_check(
    file: UploadFile = File(..., description="PDF file"),
    page: int = Form(0, ge=0, description="Zero-based page index"),
    session: AsyncSession = Depends(get_db_session),
) -> BlankCheckResponse:
    return await _handle_blank_check(file=file, page=page, session=session)


@router.post(
    "/v1/blank-check",
    response_model=BlankCheckResponse,
    summary="Upload PDF and get blank recognition result (v1)",
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def blank_check_v1(
    file: UploadFile = File(..., description="PDF file"),
    page: int = Form(0, ge=0, description="Zero-based page index"),
    session: AsyncSession = Depends(get_db_session),
) -> BlankCheckResponse:
    return await _handle_blank_check(file=file, page=page, session=session)


async def _handle_blank_check(
    *, file: UploadFile, page: int, session: AsyncSession
) -> BlankCheckResponse:
    if not file.filename:
        payload = ErrorResponse(
            error=ErrorPayload(
                code="NO_FILE",
                message="No file was uploaded",
                details=None,
            )
        )
        raise HTTPException(status_code=400, detail=payload.model_dump())

    if not file.filename.lower().endswith(".pdf"):
        payload = ErrorResponse(
            error=ErrorPayload(
                code="INVALID_FILE_TYPE",
                message="Expected a PDF file",
                details={"filename": file.filename},
            )
        )
        raise HTTPException(status_code=400, detail=payload.model_dump())

    if page < 0:
        payload = ErrorResponse(
            error=ErrorPayload(
                code="INVALID_PAGE",
                message="Page index must be zero or positive",
                details={"page": page},
            )
        )
        raise HTTPException(status_code=400, detail=payload.model_dump())

    try:
        pdf_bytes = await file.read()
    except Exception as exc:  # pragma: no cover - defensive
        payload = ErrorResponse(
            error=ErrorPayload(
                code="READ_ERROR",
                message="Failed to read uploaded file",
                details={"filename": file.filename, "exception": type(exc).__name__},
            )
        )
        raise HTTPException(status_code=400, detail=payload.model_dump()) from exc

    if not pdf_bytes:
        payload = ErrorResponse(
            error=ErrorPayload(
                code="EMPTY_FILE",
                message="Uploaded file is empty",
                details={"filename": file.filename},
            )
        )
        raise HTTPException(status_code=400, detail=payload.model_dump())

    try:
        result = run_blanks_pipeline(pdf_bytes, page_index=page)
    except Exception as exc:
        payload = ErrorResponse(
            error=ErrorPayload(
                code="CANNOT_PROCESS",
                message="Cannot process the provided PDF page",
                details={
                    "page": page,
                    "filename": file.filename,
                    "exception": type(exc).__name__,
                },
            )
        )
        raise HTTPException(status_code=422, detail=payload.model_dump()) from exc

    record_id = await save_recognized_blank(
        session=session,
        variant=result["variant"],
        date=result["date"],
        reg_number=result["reg_number"],
        answers=result["answers"],
        repl=result["repl"],
        page=page,
    )

    warnings: list[str] = []

    return BlankCheckResponse(
        variant=result["variant"],
        date=result["date"],
        reg_number=result["reg_number"],
        answers=result["answers"],
        repl=result["repl"],
        record_id=record_id,
        warnings=warnings,
    )
