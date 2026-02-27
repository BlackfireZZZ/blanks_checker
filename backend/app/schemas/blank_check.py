from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ErrorPayload(BaseModel):
    code: str = Field(..., description="Stable machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(
        default=None, description="Optional structured error details"
    )


class ErrorResponse(BaseModel):
    error: ErrorPayload


class BlankCheckRequest(BaseModel):
    page: int = Field(
        default=0,
        ge=0,
        description="Zero-based page index within the PDF. Optional in form-data.",
    )


class BlankCheckResponse(BaseModel):
    variant: list[str]
    date: list[str]
    reg_number: list[str]
    answers: list[list[str]]
    repl: list[list[str]]
    record_id: int
    warnings: list[str] = Field(default_factory=list)
    aligned_image_url: str | None = Field(
        default=None,
        description="URL для скачивания выровненного изображения страницы бланка",
    )
        

class IssueCode(str, Enum):
    MINUS_NOT_LEADING = "MINUS_NOT_LEADING"
    INTERNAL_EMPTY_CELL = "INTERNAL_EMPTY_CELL"
    LEADING_EMPTY_CELL = "LEADING_EMPTY_CELL"
    NOT_AN_INTEGER = "NOT_AN_INTEGER"
    MULTIPLE_MINUS = "MULTIPLE_MINUS"
    EMPTY_AFTER_TRIM = "EMPTY_AFTER_TRIM"
    UNSUPPORTED_SYMBOL = "UNSUPPORTED_SYMBOL"
    REQUIRED_FIELD_EMPTY = "REQUIRED_FIELD_EMPTY"


class RecognizedCell(BaseModel):
    index: int = Field(..., description="Zero-based index within the field")
    row: int | None = Field(
        default=None, description="Row index for grid-like fields (if applicable)"
    )
    col: int | None = Field(
        default=None, description="Column index for grid-like fields (if applicable)"
    )
    symbol: str | None = Field(
        default=None,
        description=(
            "Recognized symbol: '0'-'9', '-', 'E' (empty from OCR), "
            "'S' (unreadable), or null/empty when explicitly cleared"
        ),
    )


class ValidationIssue(BaseModel):
    field_id: str = Field(..., description="Identifier of the field with an issue")
    cell_indices: list[int] = Field(
        default_factory=list,
        description="Indices of cells related to this issue (within the field)",
    )
    code: IssueCode
    message: str


class FieldReview(BaseModel):
    field_id: str = Field(..., description="Stable identifier of the numeric field")
    label: str = Field(..., description="Human-friendly label for display in UI")
    cells: list[RecognizedCell]
    issues: list[ValidationIssue] = Field(default_factory=list)
    proposed_joined: str = Field(
        default="",
        description="Joined string built from non-empty symbols in order",
    )
    parsed_integer: int | None = Field(
        default=None, description="Parsed integer value if the field is valid"
    )
    is_valid: bool = Field(
        ..., description="True if the field passes all validation rules"
    )


class CorrectionFieldSubmission(BaseModel):
    field_id: str
    cells: list[RecognizedCell]
    joined_value: str | None = Field(
        default=None,
        description="Optional whole-number representation provided by the frontend",
    )


class CorrectionPayload(BaseModel):
    page: int = Field(..., description="Zero-based index of the processed PDF page")
    aligned_image_url: str | None = Field(
        default=None, description="URL of the aligned page image to show in UI"
    )
    fields: list[FieldReview] = Field(
        ..., description="Per-field layout, symbols, and validation issues"
    )


class BlankListItem(BaseModel):
    """One item in the list of uploaded blanks (GET /v1/blanks)."""

    id: int
    source_filename: str | None = None
    source_url: str | None = None
    page_num: int | None = None
    created_at: str = Field(..., description="ISO datetime")
    variant: list[str] = Field(default_factory=list)
    date: list[str] = Field(default_factory=list)
    reg_number: list[str] = Field(default_factory=list)


class BlankEditResponse(BaseModel):
    """Single blank for edit UI: CorrectionPayload + record_id (GET /v1/blanks/{id})."""

    record_id: int
    page: int
    aligned_image_url: str | None = None
    fields: list[FieldReview]


class CorrectionSubmission(BaseModel):
    page: int = Field(..., description="Zero-based index of the corrected page")
    fields: list[CorrectionFieldSubmission]
    aligned_image_url: str | None = Field(
        default=None,
        description="URL of the aligned page image (S3), to store in source_url when saving",
    )
    record_id: int | None = Field(
        default=None,
        description="If set, update this existing record instead of creating a new one",
    )