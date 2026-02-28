from fastapi import Depends, HTTPException, Request

from app.services.auth import CurrentUser, decode_access_token


async def get_current_user(request: Request) -> CurrentUser:
    # 1) Authorization header
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth[7:].strip()
        user = decode_access_token(token)
        if user is not None:
            return user
    # 2) Query param ?token= (для запросов к /api/files/ из img/link)
    token = request.query_params.get("token")
    if token:
        user = decode_access_token(token)
        if user is not None:
            return user
    raise HTTPException(
        status_code=401,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
