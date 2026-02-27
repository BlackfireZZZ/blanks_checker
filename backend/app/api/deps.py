from fastapi import Depends, HTTPException, Request

from app.services.auth import CurrentUser, decode_access_token


async def get_current_user(request: Request) -> CurrentUser:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth[7:].strip()
    user = decode_access_token(token)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
