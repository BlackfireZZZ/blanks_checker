from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RecognizedBlank


async def save_recognized_blank(
    *,
    session: AsyncSession,
    variant: Sequence[str],
    date: Sequence[str],
    reg_number: Sequence[str],
    answers: Sequence[Sequence[str]],
    repl: Sequence[Sequence[str]],
    page: int | None = None,
) -> int:
    """Persist one recognized blank into the database and return its id."""

    def _get(seq: Sequence[Any], idx: int) -> Any | None:
        return seq[idx] if idx < len(seq) else None

    data: dict[str, Any] = {
        "source_url": None,
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

