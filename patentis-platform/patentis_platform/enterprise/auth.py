"""Development auth + API keys."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

from patentis_platform.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    return pwd_context.verify(pw, hashed)


def create_access_token(sub: str, org_id: str, role: str) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(days=7)
    payload = {"sub": sub, "org": org_id, "role": role, "exp": expire}
    return jwt.encode(payload, settings.platform_jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.platform_jwt_secret, algorithms=["HS256"])


def api_key_allowed(raw_key: str) -> tuple[bool, str]:
    settings = get_settings()
    keys = [k.strip() for k in settings.platform_api_keys.split(",") if k.strip()]
    if not keys:
        return False, ""
    fp = hashlib.sha256(raw_key.encode()).hexdigest()[:16]
    return raw_key in keys, fp
