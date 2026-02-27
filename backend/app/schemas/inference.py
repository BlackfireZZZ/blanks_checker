from pydantic import BaseModel, Field


class LookalikeRequest(BaseModel):
    merchant_id: int = Field(ge=1)
    offer_id: int = Field(ge=1)
    top_n: int = Field(ge=1, le=1000)   # ограничения по тз


class AudienceItem(BaseModel):
    user_id: int
    score: float = Field(ge=0.0, le=1.0)


class ReasonItem(BaseModel):
    feature: str
    impact: float


class LookalikeResponse(BaseModel):
    merchant_id: int
    offer_id: int
    audience: list[AudienceItem]
    audience_size: int
    model_version: str
    reasons: list[ReasonItem] = Field(min_length=1)   # по openapi.yml reasons minItems=1


class LookalikeBatchRequest(BaseModel):
    requests: list[LookalikeRequest] = Field(min_length=1)


class LookalikeBatchResponse(BaseModel):
    results: list[LookalikeResponse]

