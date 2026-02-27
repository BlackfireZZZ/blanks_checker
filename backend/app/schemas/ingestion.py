from typing import Any, Literal

from pydantic import BaseModel, Field

ALLOWED_TABLES = {
    "people",
    "segments",
    "transaction",
    "offer",
    "merchant",
    "financial_account",
    "offer_seens",
    "offer_activation",
    "offer_reward",
    "receipts",
}


class DataBatchRequest(BaseModel):
    version: str
    table: str
    batch_id: int = Field(ge=1)
    total_batches: int = Field(ge=1)
    records: list[dict[str, Any]]


class DataBatchResponse(BaseModel):
    status: str
    table: str
    batch_id: int


class DataCommitRequest(BaseModel):
    version: str


class DataCommitResponse(BaseModel):
    status: str
    tables_received: list[str]
    action_taken: Literal["retrained", "none", "skipped"] | None = None

