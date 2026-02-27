"""Bootstrap and infrastructure checks for lifespan."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ServiceStatusState


async def ensure_bootstrap_state(session: AsyncSession) -> None:
    """Create service status row with id=1 if it does not exist."""
    existing = await session.get(ServiceStatusState, 1)
    if existing is None:
        session.add(ServiceStatusState(id=1, ready=False, last_error=None))
        await session.commit()


async def check_infrastructure(session: AsyncSession, storage) -> tuple[bool, str | None]:
    """Check DB and S3 are reachable. Returns (ok, error_message)."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as e:
        return False, f"DB: {e!s}"
    try:
        await storage.ensure_bucket_exists()
    except Exception as e:
        return False, f"S3: {e!s}"
    return True, None
