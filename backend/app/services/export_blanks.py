"""Blanks export to Excel."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RecognizedBlank
from app.utils.format import format_date_xx_xx_xx


def _cell_str(val: str | None) -> str:
    if val is None:
        return ""
    s = val.strip() if isinstance(val, str) else ""
    return "" if s in ("", "E") else s


def _join_digits(cells: list[str | None], allow_minus: bool = False) -> str:
    s = "".join(_cell_str(c) for c in cells)
    if allow_minus:
        return "".join(c for c in s if c in "0123456789-")
    return "".join(c for c in s if c in "0123456789")


def _four_digits(cells: list[str | None]) -> str:
    """4-digit string with leading zeros from cell list."""
    s = _join_digits(cells)
    s = s[:4].zfill(4) if s else "0000"
    return s[:4]


def _effective_answer_row(
    answer_cells: list[str | None],
    repl_cells: list[str | None],
) -> str:
    """If repl row has any non-empty cell, use repl; else use answer. Return joined digit string."""
    repl_joined = _join_digits(repl_cells, allow_minus=True)
    if repl_joined:
        return repl_joined
    return _join_digits(answer_cells, allow_minus=True)


def _row_from_blank(rec: RecognizedBlank) -> dict[str, Any]:
    variant_cells = [
        getattr(rec, f"variant_{i:02d}") for i in range(1, 5)
    ]
    date_cells = [
        getattr(rec, f"date_{i:02d}") for i in range(1, 9)
    ]
    reg_cells = [
        getattr(rec, f"reg_number_{i:02d}") for i in range(1, 9)
    ]

    row: dict[str, Any] = {
        "reg_number": _four_digits(reg_cells),
        "date": format_date_xx_xx_xx(date_cells),
        "variant": _four_digits(variant_cells),
        "source_url": rec.source_url if rec.source_url else "",
        "source_filename": rec.source_filename if rec.source_filename else "",
    }

    for n in range(1, 11):
        answer_cells = [
            getattr(rec, f"answer_r{n:02d}_c{c:02d}") for c in range(1, 10)
        ]
        repl_cells = [
            getattr(rec, f"repl_r{n:02d}_c{c:02d}") for c in range(1, 10)
        ]
        raw = _effective_answer_row(answer_cells, repl_cells)
        if not raw:
            row[f"answer_{n}"] = None
        else:
            try:
                row[f"answer_{n}"] = int(raw)
            except ValueError:
                row[f"answer_{n}"] = None

    return row


async def export_blanks_to_xlsx(session: AsyncSession) -> bytes:
    """Load all RecognizedBlank rows and return Excel file as bytes."""
    result = await session.execute(select(RecognizedBlank).order_by(RecognizedBlank.id))
    records = result.scalars().all()

    wb = Workbook()
    ws = wb.active
    if ws is None:
        raise RuntimeError("No active sheet")
    ws.title = "Бланки"

    headers = [
        "Регистрационный номер",
        "Дата",
        "Вариант",
        "source_url",
        "source_filename",
        *[f"Ответ {i}" for i in range(1, 11)],
    ]
    ws.append(headers)

    # Only first row is header: bold (no Table object to avoid Excel treating multiple rows as headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    # Data rows
    for rec in records:
        row_data = _row_from_blank(rec)
        ws.append([
            row_data["reg_number"],
            row_data["date"],
            row_data["variant"],
            row_data["source_url"],
            row_data["source_filename"],
            *[row_data.get(f"answer_{i}") for i in range(1, 11)],
        ])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
