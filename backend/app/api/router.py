from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.core.logger import logger
from app.db.session import get_db_session
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserCreateRequest,
    UserListItem,
    UserMeResponse,
)
from app.schemas.blank_check import (
    BlankCheckResponse,
    BlankEditResponse,
    BlankListItem,
    CorrectionSubmission,
    ErrorPayload,
    ErrorResponse,
)
from app.services.auth import (
    CurrentUser,
    authenticate_user,
    create_access_token,
    create_user,
    list_users,
)
from app.services.export_blanks import export_blanks_to_xlsx
from app.services.number_validation import build_field_reviews
from app.services.pipeline import run_blanks_pipeline
from app.services.recognized_blanks import (
    get_blank_by_id,
    list_blanks,
    save_recognized_blank,
    update_recognized_blank,
)
from app.storage import get_s3_client

router = APIRouter()


@router.get("/ready")
async def ready():
    """Healthcheck endpoint for docker and load balancers."""
    return {"status": "ok"}


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Login with login and password",
    responses={401: {"description": "Invalid credentials"}},
)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    user = await authenticate_user(body.login, body.password, session)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid login or password")
    return TokenResponse(
        access_token=create_access_token(user.login, user.is_admin),
        token_type="bearer",
    )


@router.get(
    "/auth/me",
    response_model=UserMeResponse,
    summary="Get current user info",
)
async def auth_me(
    current_user: CurrentUser = Depends(get_current_user),
) -> UserMeResponse:
    return UserMeResponse(login=current_user.login, is_admin=current_user.is_admin)


@router.get(
    "/v1/users",
    response_model=list[UserListItem],
    summary="List users (admin only)",
    responses={403: {"description": "Admin access required"}},
)
async def get_users_list(
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_admin),
) -> list[UserListItem]:
    rows = await list_users(session)
    return [
        UserListItem(
            id=row[0],
            login=row[1],
            created_at=row[2].isoformat() if row[2] else "",
        )
        for row in rows
    ]


@router.post(
    "/v1/users",
    response_model=UserListItem,
    summary="Create user (admin only)",
    responses={
        403: {"description": "Admin access required"},
        409: {"description": "Login already exists"},
    },
)
async def create_user_endpoint(
    body: UserCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_admin),
) -> UserListItem:
    try:
        user = await create_user(session, body.login, body.password)
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=409, detail="Login already exists") from e
        raise
    await session.commit()
    return UserListItem(
        id=user.id,
        login=user.login,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@router.get(
    "/v1/export",
    summary="Download all blanks as Excel table",
    response_class=Response,
)
async def export_blanks(
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """Return Excel file with all recognized blanks."""
    content = await export_blanks_to_xlsx(session)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=blanks.xlsx"},
    )


@router.get(
    "/v1/blanks",
    response_model=list[BlankListItem],
    summary="List uploaded blanks",
)
async def get_blanks_list(
    search: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[BlankListItem]:
    """Return list of recognized blanks, optionally filtered by search (filename/url)."""
    return await list_blanks(session, search=search)


@router.get(
    "/v1/blanks/{blank_id:int}",
    response_model=BlankEditResponse,
    summary="Get one blank for edit",
    responses={404: {"description": "Blank not found"}},
)
async def get_blank_edit(
    blank_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> BlankEditResponse:
    """Return one blank as CorrectionPayload + record_id for the edit UI."""
    data = await get_blank_by_id(session, blank_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Blank not found")
    return data


@router.post(
    "/blank-check",
    response_model=BlankCheckResponse,
    summary="Upload PDF and get blank recognition result",
)
async def blank_check(
    file: UploadFile = File(..., description="PDF file"),
    page: int = Form(0, ge=0, description="Zero-based page index"),
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
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
    current_user: CurrentUser = Depends(get_current_user),
) -> BlankCheckResponse:
    return await _handle_blank_check(file=file, page=page, session=session)


@router.post(
    "/v1/blank-check/corrections",
    response_model=BlankCheckResponse,
    summary="Save corrected recognition result after manual review",
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def save_corrected_blank(
    payload: CorrectionSubmission,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> BlankCheckResponse:
    """
    Accept corrected cell values from the frontend, re-validate them,
    and persist to the database if everything is valid.
    """
    # Reconstruct simple per-field symbol arrays from cells
    field_map: dict[str, list[str]] = {}
    for field in payload.fields:
        # sort cells by index to ensure stable order
        sorted_cells = sorted(field.cells, key=lambda c: c.index)
        symbols: list[str] = []
        for cell in sorted_cells:
            sym = cell.symbol or ""
            # normalize empties to 'E' for storage, keep digits and '-'
            if sym == "":
                symbols.append("E")
            elif sym in "0123456789-":
                symbols.append(sym)
            else:
                # anything else becomes 'E' but will be caught by backend validator
                symbols.append(sym)
        field_map[field.field_id] = symbols

    # Map back to the shapes expected by save_recognized_blank
    variant = field_map.get("variant", [])
    date = field_map.get("date", [])
    reg_number = field_map.get("reg_number", [])

    answers: list[list[str]] = []
    repl: list[list[str]] = []

    for key, symbols in field_map.items():
        if key.startswith("answer_r"):
            answers.append(symbols)
        elif key.startswith("repl_r"):
            repl.append(symbols)

    # Run backend validation again before saving
    correction = build_field_reviews(
        page=payload.page,
        aligned_image_url=None,
        variant=variant,
        date=date,
        reg_number=reg_number,
        answers=answers,
        repl=repl,
    )
    if correction is not None:
        error = ErrorResponse(
            error=ErrorPayload(
                code="REVIEW_REQUIRED",
                message="Исправьте выделенные поля перед сохранением.",
                details=correction.model_dump(),
            )
        )
        raise HTTPException(status_code=422, detail=error.model_dump())

    if payload.record_id is not None:
        try:
            record_id = await update_recognized_blank(
                session=session,
                record_id=payload.record_id,
                variant=variant,
                date=date,
                reg_number=reg_number,
                answers=answers,
                repl=repl,
                page=payload.page,
                source_url=payload.aligned_image_url,
            )
        except LookupError:
            raise HTTPException(status_code=404, detail="Blank not found")
    else:
        record_id = await save_recognized_blank(
            session=session,
            variant=variant,
            date=date,
            reg_number=reg_number,
            answers=answers,
            repl=repl,
            page=payload.page,
            source_filename=None,
            source_url=payload.aligned_image_url,
        )
    await session.commit()

    return BlankCheckResponse(
        variant=variant,
        date=date,
        reg_number=reg_number,
        answers=answers,
        repl=repl,
        record_id=record_id,
        warnings=[],
        aligned_image_url=payload.aligned_image_url,
    )


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
        result = run_blanks_pipeline(pdf_bytes, page_index=page, return_aligned_png=True)
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

    aligned_image_url: str | None = None

    try:
        aligned_png = result.get("aligned_png")
        if aligned_png:
            s3 = await get_s3_client()
            object_key = f"aligned/{uuid4().hex}.png"
            await s3.upload_bytes(
                aligned_png,
                object_key,
                content_type="image/png",
                metadata={
                    "source_filename": file.filename,
                    "page_index": page,
                },
            )
            aligned_image_url = await s3.get_file_url(object_key)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to upload aligned image to S3: %s", exc)

    # Run numeric validation over all multi-cell fields before saving.
    correction = build_field_reviews(
        page=page,
        aligned_image_url=aligned_image_url,
        variant=result["variant"],
        date=result["date"],
        reg_number=result["reg_number"],
        answers=result["answers"],
        repl=result["repl"],
    )
    if correction is not None:
        error = ErrorResponse(
            error=ErrorPayload(
                code="REVIEW_REQUIRED",
                message="Обнаружены поля, требующие ручной проверки.",
                details=correction.model_dump(),
            )
        )
        raise HTTPException(status_code=422, detail=error.model_dump())

    record_id = await save_recognized_blank(
        session=session,
        variant=result["variant"],
        date=result["date"],
        reg_number=result["reg_number"],
        answers=result["answers"],
        repl=result["repl"],
        page=page,
        source_filename=file.filename,
        source_url=aligned_image_url,
    )
    await session.commit()

    warnings: list[str] = []
    if aligned_image_url is None:
        warnings.append(
            "Не удалось сохранить или получить ссылку на выровненное изображение."
        )

    return BlankCheckResponse(
        variant=result["variant"],
        date=result["date"],
        reg_number=result["reg_number"],
        answers=result["answers"],
        repl=result["repl"],
        record_id=record_id,
        warnings=warnings,
        aligned_image_url=aligned_image_url,
    )
