from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import User

_BCRYPT_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > _BCRYPT_MAX_PASSWORD_BYTES:
        pw_bytes = pw_bytes[:_BCRYPT_MAX_PASSWORD_BYTES]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pw_bytes = plain_password.encode("utf-8")
    if len(pw_bytes) > _BCRYPT_MAX_PASSWORD_BYTES:
        pw_bytes = pw_bytes[:_BCRYPT_MAX_PASSWORD_BYTES]
    return bcrypt.checkpw(pw_bytes, hashed_password.encode("utf-8"))


@dataclass
class CurrentUser:
    login: str
    is_admin: bool


def _check_admin(login: str, password: str) -> bool:
    if not settings.ADMIN_LOGIN or not settings.ADMIN_PASSWORD:
        return False
    return (
        login == settings.ADMIN_LOGIN and password == settings.ADMIN_PASSWORD
    )


async def authenticate_user(
    login: str, password: str, session: AsyncSession
) -> CurrentUser | None:
    if _check_admin(login, password):
        return CurrentUser(login=login, is_admin=True)
    result = await session.execute(select(User).where(User.login == login))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return CurrentUser(login=user.login, is_admin=False)


def create_access_token(login: str, is_admin: bool) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_EXPIRE_MINUTES
    )
    payload = {"sub": login, "is_admin": is_admin, "exp": expire}
    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> CurrentUser | None:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        login = payload.get("sub")
        is_admin = payload.get("is_admin", False)
        if not login or not isinstance(login, str):
            return None
        return CurrentUser(login=login, is_admin=bool(is_admin))
    except JWTError:
        return None


async def list_users(session: AsyncSession) -> list[tuple[int, str, datetime]]:
    """Return list of (id, login, created_at) for all users in DB."""
    result = await session.execute(
        select(User.id, User.login, User.created_at).order_by(User.id)
    )
    return list(result.all())


async def create_user(
    session: AsyncSession, login: str, password: str
) -> User:
    """Create a new user. Raises ValueError if login already exists."""
    existing = await session.execute(select(User).where(User.login == login))
    if existing.scalar_one_or_none() is not None:
        raise ValueError("Login already exists")
    user = User(
        login=login,
        email=None,
        hashed_password=hash_password(password),
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user
