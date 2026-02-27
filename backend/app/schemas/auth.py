from pydantic import BaseModel


class LoginRequest(BaseModel):
    login: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserMeResponse(BaseModel):
    login: str
    is_admin: bool


class UserCreateRequest(BaseModel):
    login: str
    password: str


class UserListItem(BaseModel):
    id: int
    login: str
    created_at: str
