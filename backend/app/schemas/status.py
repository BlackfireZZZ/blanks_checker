from typing import Literal

from pydantic import BaseModel


class StatusResponse(BaseModel):
    ready: bool
    model_version: str
    data_version: str
    pipeline_status: Literal["idle", "running", "failed"]
    snapshot_version: str | None = None
    snapshot_built_at: str | None = None

