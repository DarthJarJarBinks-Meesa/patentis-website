from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import User
from patentis_platform.db.session import get_db
from patentis_platform.enterprise import auth as auth_lib

security = HTTPBearer(auto_error=False)


async def get_db_session() -> AsyncSession:
    async for session in get_db():
        yield session


async def get_current_user_optional(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Optional[User]:
    if not creds:
        return None
    try:
        payload = auth_lib.decode_token(creds.credentials)
    except JWTError:
        return None
    email = payload.get("sub")
    if not email:
        return None
    res = await session.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()


async def require_user(
    user: Annotated[Optional[User], Depends(get_current_user_optional)],
) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def require_admin(user: Annotated[User, Depends(require_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


async def require_org_context(
    user: Annotated[User, Depends(require_user)],
    x_api_key: Annotated[Optional[str], Header()] = None,
) -> tuple[User, Optional[str]]:
    fp: Optional[str] = None
    if x_api_key:
        ok, fp = auth_lib.api_key_allowed(x_api_key)
        if not ok:
            raise HTTPException(status_code=403, detail="Invalid API key")
    return user, fp
