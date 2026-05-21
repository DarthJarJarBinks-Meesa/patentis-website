from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.api.deps import get_db_session
from patentis_platform.db.models import Organization, User
from patentis_platform.enterprise import auth as auth_lib
from patentis_platform.enterprise.audit import write_audit
from patentis_platform.schemas.api import TokenOut, UserLogin, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
async def register(body: UserRegister, session: AsyncSession = Depends(get_db_session)):
    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    org = Organization(name=body.org_name, plan="standard")
    session.add(org)
    await session.flush()

    user = User(
        org_id=org.id,
        email=body.email,
        hashed_password=auth_lib.hash_password(body.password),
        role="admin",
    )
    session.add(user)
    await write_audit(
        session,
        action="user.register",
        org_id=org.id,
        actor_user_id=user.id,
        resource=f"user:{user.email}",
        detail={},
        commit=False,
    )
    await session.commit()
    token = auth_lib.create_access_token(sub=user.email, org_id=str(org.id), role=user.role)
    return TokenOut(access_token=token)


@router.post("/login", response_model=TokenOut)
async def login(body: UserLogin, session: AsyncSession = Depends(get_db_session)):
    res = await session.execute(select(User).where(User.email == body.email))
    user = res.scalar_one_or_none()
    if not user or not auth_lib.verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = auth_lib.create_access_token(sub=user.email, org_id=str(user.org_id), role=user.role)
    return TokenOut(access_token=token)
