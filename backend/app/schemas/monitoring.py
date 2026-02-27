from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


def metrics_numeric_only(raw: dict[str, Any] | None) -> dict[str, float]:
    """
    Возвращает только числовые метрики, чтобы MLflow было вкусно
    """
    if not raw:
        return {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = float(v)
        elif isinstance(v, str):
            try:
                out[k] = float(v)
            except (ValueError, TypeError):
                pass
    return out


class DriftResponse(BaseModel):
    version: str
    drift_detected: bool
    drift_score: float
    action_taken: Literal["retrained", "none", "skipped"]


class FailedCheck(BaseModel):
    table: str
    check: str
    details: str


class DataQualityResponse(BaseModel):
    version: str
    valid: bool
    checks_total: int
    checks_passed: int
    checks_failed: int
    failed_checks: list[FailedCheck]


class ExperimentRun(BaseModel):
    run_id: str
    data_version: str
    model_version: str
    metrics: dict[str, float]
    params: dict[str, Any] | None = None
    timestamp: datetime


class ExperimentsResponse(BaseModel):
    experiments: list[ExperimentRun]

