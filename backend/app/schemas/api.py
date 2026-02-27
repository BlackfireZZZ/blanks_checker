"""
Compatibility schema barrel.

Historically, all API schemas lived in this module. They are now split into
domain modules under `app.schemas.*`, while this file re-exports the same
symbols to keep imports stable.
"""

from app.schemas.ingestion import (  # noqa: F401
    ALLOWED_TABLES,
    DataBatchRequest,
    DataBatchResponse,
    DataCommitRequest,
    DataCommitResponse,
)
from app.schemas.inference import (  # noqa: F401
    AudienceItem,
    LookalikeBatchRequest,
    LookalikeBatchResponse,
    LookalikeRequest,
    LookalikeResponse,
    ReasonItem,
)
from app.schemas.model import ModelInfoResponse  # noqa: F401
from app.schemas.monitoring import (  # noqa: F401
    DataQualityResponse,
    DriftResponse,
    ExperimentRun,
    ExperimentsResponse,
    FailedCheck,
)
from app.schemas.status import StatusResponse  # noqa: F401

__all__ = [
    "ALLOWED_TABLES",
    "DataBatchRequest",
    "DataBatchResponse",
    "DataCommitRequest",
    "DataCommitResponse",
    "StatusResponse",
    "LookalikeRequest",
    "AudienceItem",
    "ReasonItem",
    "LookalikeResponse",
    "LookalikeBatchRequest",
    "LookalikeBatchResponse",
    "ModelInfoResponse",
    "DriftResponse",
    "FailedCheck",
    "DataQualityResponse",
    "ExperimentRun",
    "ExperimentsResponse",
]
