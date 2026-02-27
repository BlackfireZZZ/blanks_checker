from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.schemas.blank_check import (
    CorrectionPayload,
    FieldReview,
    IssueCode,
    RecognizedCell,
    ValidationIssue,
)
from app.utils.format import DATE_DIGIT_INDICES


@dataclass
class RawField:
    field_id: str
    label: str
    symbols: list[str]
    row: int | None = None
    section: str | None = None  # e.g. "answers" / "repl"


def _normalize_symbol(sym: str | None) -> str | None:
    """
    Map pipeline symbols to validation domain.

    - 'E' -> empty (None)
    - 'S' -> unsupported symbol (kept as 'S' to mark an issue)
    - '0'-'9', '-' kept as-is
    - anything else -> unsupported symbol 'S'
    """
    if sym is None:
        return None
    if sym == "E":
        return None
    if sym in "0123456789-":
        return sym
    if sym == "S":
        return "S"
    return "S"


def _build_cells(
    symbols: list[str],
    *,
    row: int | None = None,
) -> list[RecognizedCell]:
    cells: list[RecognizedCell] = []
    for idx, raw in enumerate(symbols):
        norm = _normalize_symbol(raw)
        cells.append(
            RecognizedCell(
                index=idx,
                row=row,
                col=idx if row is not None else None,
                symbol=norm,
            )
        )
    return cells


def _validate_cells(
    field_id: str,
    label: str,
    cells: list[RecognizedCell],
    *,
    digit_only_indices: tuple[int, ...] | None = None,
) -> FieldReview:
    """
    Validate multi-cell numeric field.
    If digit_only_indices is set (e.g. (0,1,3,4,6,7) for date), only those
    indices are used for empty/non-empty and joined value; others are skipped.
    """
    issues: list[ValidationIssue] = []

    # Which indices count for "digit" part (default: all)
    if digit_only_indices is not None:
        digit_set = set(digit_only_indices)
        cells_for_digits = [c for c in cells if c.index in digit_set]
    else:
        digit_set = {c.index for c in cells}
        cells_for_digits = cells

    required_fields = ("variant", "date", "reg_number")

    # Collect simple properties
    indices = [c.index for c in cells]
    if not indices:
        if field_id in required_fields:
            issues.append(
                ValidationIssue(
                    field_id=field_id,
                    cell_indices=[],
                    code=IssueCode.REQUIRED_FIELD_EMPTY,
                    message="Поле обязательно для заполнения.",
                )
            )
            return FieldReview(
                field_id=field_id,
                label=label,
                cells=cells,
                issues=issues,
                proposed_joined="",
                parsed_integer=None,
                is_valid=False,
            )
        return FieldReview(
            field_id=field_id,
            label=label,
            cells=cells,
            issues=[],
            proposed_joined="",
            parsed_integer=None,
            is_valid=True,
        )

    # Find first/last non-empty cell (only in digit indices)
    non_empty_indices = [
        c.index
        for c in cells_for_digits
        if c.symbol not in (None, "",)
    ]

    # Fully empty field
    if not non_empty_indices:
        if field_id in required_fields:
            issues.append(
                ValidationIssue(
                    field_id=field_id,
                    cell_indices=[],
                    code=IssueCode.REQUIRED_FIELD_EMPTY,
                    message="Поле обязательно для заполнения.",
                )
            )
            return FieldReview(
                field_id=field_id,
                label=label,
                cells=cells,
                issues=issues,
                proposed_joined="",
                parsed_integer=None,
                is_valid=False,
            )
        return FieldReview(
            field_id=field_id,
            label=label,
            cells=cells,
            issues=[],
            proposed_joined="",
            parsed_integer=None,
            is_valid=True,
        )

    first = min(non_empty_indices)
    last = max(non_empty_indices)

    # Leading empties: empty digit cells before the first non-empty
    leading_empty_indices = [idx for idx in digit_set if idx < first]
    if leading_empty_indices:
        issues.append(
            ValidationIssue(
                field_id=field_id,
                cell_indices=leading_empty_indices,
                code=IssueCode.LEADING_EMPTY_CELL,
                message="Число не может начинаться с пустых клеток.",
            )
        )

    # Internal empties between first and last non-empty cells (digit indices only)
    internal_empty_indices: list[int] = []
    for idx in range(first, last + 1):
        if idx not in digit_set:
            continue
        cell = next((c for c in cells if c.index == idx), None)
        if cell is None:
            continue
        if cell.symbol in (None, "",):
            internal_empty_indices.append(idx)

    if internal_empty_indices:
        issues.append(
            ValidationIssue(
                field_id=field_id,
                cell_indices=internal_empty_indices,
                code=IssueCode.INTERNAL_EMPTY_CELL,
                message="Внутри числа есть пустые клетки.",
            )
        )

    # Minus sign positions (among digit cells)
    minus_indices = [c.index for c in cells_for_digits if c.symbol == "-"]
    if len(minus_indices) > 1:
        issues.append(
            ValidationIssue(
                field_id=field_id,
                cell_indices=minus_indices,
                code=IssueCode.MULTIPLE_MINUS,
                message="Допускается не более одного знака минус.",
            )
        )
    if minus_indices:
        first_non_empty = first
        if minus_indices[0] != first_non_empty:
            issues.append(
                ValidationIssue(
                    field_id=field_id,
                    cell_indices=[minus_indices[0]],
                    code=IssueCode.MINUS_NOT_LEADING,
                    message="Знак минус может быть только в первой непустой клетке.",
                )
            )

    # Unsupported symbols (e.g. 'S') in digit cells
    unsupported_indices = [c.index for c in cells_for_digits if c.symbol == "S"]
    if unsupported_indices:
        issues.append(
            ValidationIssue(
                field_id=field_id,
                cell_indices=unsupported_indices,
                code=IssueCode.UNSUPPORTED_SYMBOL,
                message="Обнаружены нечитаемые символы, требующие исправления.",
            )
        )

    # Build joined string from digit cells only, non-empty, non-'S'
    joined_parts: list[str] = []
    for c in cells_for_digits:
        if c.symbol in (None, "", "S"):
            continue
        joined_parts.append(c.symbol)
    proposed_joined = "".join(joined_parts)

    if not proposed_joined:
        # Only non-empty symbols were 'S' or similar — not a valid number
        issues.append(
            ValidationIssue(
                field_id=field_id,
                cell_indices=list(non_empty_indices),
                code=IssueCode.EMPTY_AFTER_TRIM,
                message="После удаления пустых клеток не осталось цифр.",
            )
        )
        return FieldReview(
            field_id=field_id,
            label=label,
            cells=cells,
            issues=issues,
            proposed_joined=proposed_joined,
            parsed_integer=None,
            is_valid=False,
        )

    # Required field that ended up empty after trim (should not happen often)
    if field_id in required_fields and not proposed_joined.strip():
        issues.append(
            ValidationIssue(
                field_id=field_id,
                cell_indices=list(non_empty_indices),
                code=IssueCode.REQUIRED_FIELD_EMPTY,
                message="Поле обязательно для заполнения.",
            )
        )
        return FieldReview(
            field_id=field_id,
            label=label,
            cells=cells,
            issues=issues,
            proposed_joined=proposed_joined,
            parsed_integer=None,
            is_valid=False,
        )

    # Integer syntax validation
    int_pattern = re.compile(r"^-?[0-9]+$")
    if not int_pattern.match(proposed_joined):
        issues.append(
            ValidationIssue(
                field_id=field_id,
                cell_indices=list(non_empty_indices),
                code=IssueCode.NOT_AN_INTEGER,
                message="Значение не является корректным целым числом.",
            )
        )
        return FieldReview(
            field_id=field_id,
            label=label,
            cells=cells,
            issues=issues,
            proposed_joined=proposed_joined,
            parsed_integer=None,
            is_valid=False,
        )

    try:
        parsed = int(proposed_joined)
    except ValueError:
        issues.append(
            ValidationIssue(
                field_id=field_id,
                cell_indices=list(non_empty_indices),
                code=IssueCode.NOT_AN_INTEGER,
                message="Значение не удалось преобразовать в целое число.",
            )
        )
        return FieldReview(
            field_id=field_id,
            label=label,
            cells=cells,
            issues=issues,
            proposed_joined=proposed_joined,
            parsed_integer=None,
            is_valid=False,
        )

    return FieldReview(
        field_id=field_id,
        label=label,
        cells=cells,
        issues=issues,
        proposed_joined=proposed_joined,
        parsed_integer=parsed,
        is_valid=not issues,
    )


def build_field_reviews(
    *,
    page: int,
    aligned_image_url: str | None,
    variant: Iterable[str],
    date: Iterable[str],
    reg_number: Iterable[str],
    answers: Iterable[Iterable[str]],
    repl: Iterable[Iterable[str]],
) -> CorrectionPayload | None:
    """
    Build FieldReview objects for all multi-cell numeric fields.

    Returns:
        - None, if all fields are valid integers.
        - CorrectionPayload with detailed issues otherwise.
    """
    raw_fields: list[RawField] = []

    variant_list = list(variant)
    raw_fields.append(
        RawField(field_id="variant", label="Вариант", symbols=variant_list)
    )

    date_list = list(date)
    raw_fields.append(
        RawField(field_id="date", label="Дата", symbols=date_list)
    )

    reg_list = list(reg_number)
    raw_fields.append(
        RawField(field_id="reg_number", label="Регистрационный номер", symbols=reg_list)
    )

    # Answers: one field per row
    for row_idx, row in enumerate(answers):
        row_list = list(row)
        if not row_list:
            continue
        raw_fields.append(
            RawField(
                field_id=f"answer_r{row_idx + 1:02d}",
                label=f"Ответы, строка {row_idx + 1}",
                symbols=row_list,
                row=row_idx,
                section="answers",
            )
        )

    # Replacement grid: one field per row
    for row_idx, row in enumerate(repl):
        row_list = list(row)
        if not row_list:
            continue
        raw_fields.append(
            RawField(
                field_id=f"repl_r{row_idx + 1:02d}",
                label=f"Замена, строка {row_idx + 1}",
                symbols=row_list,
                row=row_idx,
                section="repl",
            )
        )

    field_reviews: list[FieldReview] = []
    has_problem = False

    for raw in raw_fields:
        cells = _build_cells(raw.symbols, row=raw.row)
        digit_only: tuple[int, ...] | None = None
        if raw.field_id == "date":
            digit_only = DATE_DIGIT_INDICES
        review = _validate_cells(
            raw.field_id, raw.label, cells, digit_only_indices=digit_only
        )
        field_reviews.append(review)
        if not review.is_valid:
            has_problem = True

    if not has_problem:
        return None

    return CorrectionPayload(
        page=page,
        aligned_image_url=aligned_image_url,
        fields=field_reviews,
    )


def build_correction_payload_always(
    *,
    page: int,
    aligned_image_url: str | None,
    variant: Iterable[str],
    date: Iterable[str],
    reg_number: Iterable[str],
    answers: Iterable[Iterable[str]],
    repl: Iterable[Iterable[str]],
) -> CorrectionPayload:
    """
    Build CorrectionPayload with FieldReview for all multi-cell fields.
    Always returns a payload (for edit UI), unlike build_field_reviews which returns None when valid.
    """
    raw_fields: list[RawField] = []

    variant_list = list(variant)
    raw_fields.append(
        RawField(field_id="variant", label="Вариант", symbols=variant_list)
    )

    date_list = list(date)
    raw_fields.append(
        RawField(field_id="date", label="Дата", symbols=date_list)
    )

    reg_list = list(reg_number)
    raw_fields.append(
        RawField(field_id="reg_number", label="Регистрационный номер", symbols=reg_list)
    )

    for row_idx, row in enumerate(answers):
        row_list = list(row)
        if not row_list:
            continue
        raw_fields.append(
            RawField(
                field_id=f"answer_r{row_idx + 1:02d}",
                label=f"Ответы, строка {row_idx + 1}",
                symbols=row_list,
                row=row_idx,
                section="answers",
            )
        )

    for row_idx, row in enumerate(repl):
        row_list = list(row)
        if not row_list:
            continue
        raw_fields.append(
            RawField(
                field_id=f"repl_r{row_idx + 1:02d}",
                label=f"Замена, строка {row_idx + 1}",
                symbols=row_list,
                row=row_idx,
                section="repl",
            )
        )

    field_reviews = []
    for raw in raw_fields:
        cells = _build_cells(raw.symbols, row=raw.row)
        digit_only: tuple[int, ...] | None = None
        if raw.field_id == "date":
            digit_only = DATE_DIGIT_INDICES
        review = _validate_cells(
            raw.field_id, raw.label, cells, digit_only_indices=digit_only
        )
        field_reviews.append(review)

    return CorrectionPayload(
        page=page,
        aligned_image_url=aligned_image_url,
        fields=field_reviews,
    )

