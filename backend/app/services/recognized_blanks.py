from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RecognizedBlank
from app.schemas.blank_check import BlankEditResponse, BlankListItem
from app.services.number_validation import build_correction_payload_always


def _blank_to_symbol_list(rec: RecognizedBlank, prefix: str, count: int) -> list[str]:
    """Read count cells from model (e.g. variant_01..04) as symbol list; None -> 'E'."""
    out: list[str] = []
    for i in range(1, count + 1):
        val = getattr(rec, f"{prefix}_{i:02d}", None)
        out.append(val if val is not None and str(val).strip() else "E")
    return out


def _blank_to_row(rec: RecognizedBlank, row_prefix: str, cols: int) -> list[str]:
    """Read one row of cells (e.g. answer_r01_c01..c09) as symbol list."""
    out: list[str] = []
    for c in range(1, cols + 1):
        val = getattr(rec, f"{row_prefix}_c{c:02d}", None)
        out.append(val if val is not None and str(val).strip() else "E")
    return out


def blank_to_list_item(rec: RecognizedBlank) -> BlankListItem:
    """Convert RecognizedBlank to BlankListItem for list API."""
    variant = _blank_to_symbol_list(rec, "variant", 4)
    date = _blank_to_symbol_list(rec, "date", 8)
    reg_number = _blank_to_symbol_list(rec, "reg_number", 8)
    created_at = rec.created_at.isoformat() if rec.created_at else ""
    verified_at = rec.verified_at.isoformat() if rec.verified_at else None
    return BlankListItem(
        id=rec.id,
        source_filename=rec.source_filename,
        source_url=rec.source_url,
        page_num=rec.page_num,
        created_at=created_at,
        verified=rec.verified,
        verified_at=verified_at,
        verified_by=rec.verified_by,
        variant=variant,
        date=date,
        reg_number=reg_number,
    )


def blank_to_edit_response(rec: RecognizedBlank) -> BlankEditResponse:
    """Convert RecognizedBlank to BlankEditResponse (CorrectionPayload + record_id) for edit API."""
    variant = _blank_to_symbol_list(rec, "variant", 4)
    date = _blank_to_symbol_list(rec, "date", 8)
    reg_number = _blank_to_symbol_list(rec, "reg_number", 8)
    answers: list[list[str]] = []
    for r in range(1, 11):
        row = _blank_to_row(rec, f"answer_r{r:02d}", 9)
        answers.append(row)
    repl: list[list[str]] = []
    for r in range(1, 11):
        row = _blank_to_row(rec, f"repl_r{r:02d}", 9)
        repl.append(row)

    page = rec.page_num if rec.page_num is not None else 0
    payload = build_correction_payload_always(
        page=page,
        aligned_image_url=rec.source_url,
        variant=variant,
        date=date,
        reg_number=reg_number,
        answers=answers,
        repl=repl,
    )
    verified_at = rec.verified_at.isoformat() if rec.verified_at else None
    return BlankEditResponse(
        record_id=rec.id,
        page=payload.page,
        aligned_image_url=payload.aligned_image_url,
        fields=payload.fields,
        verified=rec.verified,
        verified_at=verified_at,
        verified_by=rec.verified_by,
    )


async def list_blanks(
    session: AsyncSession,
    search: str | None = None,
    unchecked_only: bool = False,
) -> list[BlankListItem]:
    """Load list of RecognizedBlank ordered by id desc, optionally filtered by search and unchecked only."""
    q = select(RecognizedBlank).order_by(RecognizedBlank.id.desc())
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.where(
            (RecognizedBlank.source_filename.ilike(term))
            | (RecognizedBlank.source_url.ilike(term))
        )
    if unchecked_only:
        q = q.where(
            (RecognizedBlank.verified.is_(False)) | (RecognizedBlank.verified.is_(None))
        )
    result = await session.execute(q)
    rows = result.scalars().all()
    return [blank_to_list_item(rec) for rec in rows]


async def get_blank_by_id(
    session: AsyncSession,
    blank_id: int,
) -> BlankEditResponse | None:
    """Load one RecognizedBlank by id; return None if not found."""
    result = await session.execute(
        select(RecognizedBlank).where(RecognizedBlank.id == blank_id)
    )
    rec = result.scalars().one_or_none()
    if rec is None:
        return None
    return blank_to_edit_response(rec)


async def delete_blank(
    session: AsyncSession,
    blank_id: int,
) -> bool:
    """Delete RecognizedBlank by id. Returns True if deleted, False if not found."""
    result = await session.execute(
        select(RecognizedBlank).where(RecognizedBlank.id == blank_id)
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        return False
    await session.delete(rec)
    return True


async def save_recognized_blank(
    *,
    session: AsyncSession,
    variant: Sequence[str],
    date: Sequence[str],
    reg_number: Sequence[str],
    answers: Sequence[Sequence[str]],
    repl: Sequence[Sequence[str]],
    page: int | None = None,
    source_filename: str | None = None,
    source_url: str | None = None,
) -> int:
    """Persist one recognized blank into the database and return its id."""

    def _get(seq: Sequence[Any], idx: int) -> Any | None:
        return seq[idx] if idx < len(seq) else None

    data: dict[str, Any] = {
        "source_url": source_url,
        "source_filename": source_filename,
        "page_num": page,
    }

    # Header fields
    for i in range(4):
        data[f"variant_{i + 1:02d}"] = _get(variant, i)
    for i in range(8):
        data[f"date_{i + 1:02d}"] = _get(date, i)
    for i in range(8):
        data[f"reg_number_{i + 1:02d}"] = _get(reg_number, i)

    # Answers grid: 10 rows × 9 columns
    for row_idx in range(10):
        row = answers[row_idx] if row_idx < len(answers) else ()
        for col_idx in range(9):
            data[f"answer_r{row_idx + 1:02d}_c{col_idx + 1:02d}"] = _get(
                row, col_idx
            )

    # Replacement grid: 10 rows × 9 columns
    for row_idx in range(10):
        row = repl[row_idx] if row_idx < len(repl) else ()
        for col_idx in range(9):
            data[f"repl_r{row_idx + 1:02d}_c{col_idx + 1:02d}"] = _get(row, col_idx)

    obj = RecognizedBlank(**data)
    session.add(obj)
    await session.flush()
    return obj.id


async def update_recognized_blank(
    *,
    session: AsyncSession,
    record_id: int,
    variant: Sequence[str],
    date: Sequence[str],
    reg_number: Sequence[str],
    answers: Sequence[Sequence[str]],
    repl: Sequence[Sequence[str]],
    page: int | None = None,
    source_url: str | None = None,
) -> int:
    """Update an existing RecognizedBlank by id. Raises if not found (caller should 404)."""
    result = await session.execute(
        select(RecognizedBlank).where(RecognizedBlank.id == record_id)
    )
    rec = result.scalars().one_or_none()
    if rec is None:
        raise LookupError(f"RecognizedBlank id={record_id} not found")

    def _get(seq: Sequence[Any], idx: int) -> Any | None:
        return seq[idx] if idx < len(seq) else None

    rec.source_url = source_url
    rec.page_num = page

    for i in range(4):
        setattr(rec, f"variant_{i + 1:02d}", _get(variant, i))
    for i in range(8):
        setattr(rec, f"date_{i + 1:02d}", _get(date, i))
    for i in range(8):
        setattr(rec, f"reg_number_{i + 1:02d}", _get(reg_number, i))

    for row_idx in range(10):
        row = answers[row_idx] if row_idx < len(answers) else ()
        for col_idx in range(9):
            setattr(
                rec,
                f"answer_r{row_idx + 1:02d}_c{col_idx + 1:02d}",
                _get(row, col_idx),
            )
    for row_idx in range(10):
        row = repl[row_idx] if row_idx < len(repl) else ()
        for col_idx in range(9):
            setattr(
                rec,
                f"repl_r{row_idx + 1:02d}_c{col_idx + 1:02d}",
                _get(row, col_idx),
            )

    await session.flush()
    return rec.id


async def set_blank_verified(
    session: AsyncSession,
    blank_id: int,
    verified: bool,
    verified_by: str,
) -> bool:
    """Set verified flag on a blank. Returns True if updated, False if not found."""
    result = await session.execute(
        select(RecognizedBlank).where(RecognizedBlank.id == blank_id)
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        return False
    rec.verified = verified
    rec.verified_at = datetime.now(timezone.utc) if verified else None
    rec.verified_by = verified_by if verified else None
    await session.flush()
    return True

