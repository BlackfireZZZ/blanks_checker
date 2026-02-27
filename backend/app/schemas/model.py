from pydantic import BaseModel


class ModelInfoResponse(BaseModel):
    model_name: str
    model_version: str
    trained_on: str
    features_count: int
    train_metrics: dict[str, float | int | str]

