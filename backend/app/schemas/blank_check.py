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

